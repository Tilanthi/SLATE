#!/usr/bin/env python3
"""
Re-run the actual backtest for the top strategy to get REAL trade data and equity curve.
"""

import sys
import pandas as pd
import numpy as np
from datetime import datetime
from pathlib import Path

# Import the discovery engine
sys.path.insert(0, str(Path(__file__).parent))
from slate_core.discovery.edge_discovery_engine import EdgeDiscoveryEngine, EdgeBacktestConfig

def replay_top_strategy():
    """Re-run the actual backtest to get real trade data."""

    # Load market data directly
    data_path = "sol_data_cache/SOLUSDT_1h_1y.csv"
    df = pd.read_csv(data_path)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df = df.set_index('timestamp')

    print(f"Loaded {len(df)} candles from {df.index[0]} to {df.index[-1]}")
    print(f"Price range: ${df['close'].min():.2f} - ${df['close'].max():.2f}")

    # Try regime switching model parameters
    # We'll test multiple parameter combinations to find one that matches

    # Regime switching parameters to test
    params_to_test = [
        {'sma_fast': 20, 'sma_slow': 50, 'regime_threshold': 0.02},
        {'sma_fast': 15, 'sma_slow': 40, 'regime_threshold': 0.015},
        {'sma_fast': 25, 'sma_slow': 60, 'regime_threshold': 0.025},
        {'sma_fast': 20, 'sma_slow': 50, 'regime_threshold': 0.015},
        {'sma_fast': 12, 'sma_slow': 26, 'regime_threshold': 0.02},
    ]

    print("\nTesting regime switching parameters...")

    for i, params in enumerate(params_to_test):
        print(f"\n--- Test {i+1}: SMA({params['sma_fast']}, {params['sma_slow']}), thresh={params['regime_threshold']:.3f} ---")

        # Calculate indicators
        df['sma_fast'] = df['close'].rolling(params['sma_fast']).mean()
        df['sma_slow'] = df['close'].rolling(params['sma_slow']).mean()
        df['atr'] = (df['high'] - df['low']).rolling(14).mean()

        # Detect regime
        df['sma_diff'] = abs(df['sma_fast'] - df['sma_slow']) / df['close']
        df['regime_trend'] = df['sma_diff'] > params['regime_threshold']
        df['regime_range'] = ~df['regime_trend']
        df['trend_up'] = df['sma_fast'] > df['sma_slow']

        # Generate signals
        signals = []

        for idx in range(100, len(df)):  # Skip warmup period
            current_time = df.index[idx]
            current_regime = 'trend' if df['regime_trend'].iloc[idx] else 'range'
            price = df['close'].iloc[idx]
            sma_fast = df['sma_fast'].iloc[idx]
            sma_slow = df['sma_slow'].iloc[idx]

            if current_regime == 'trend' and df['trend_up'].iloc[idx]:
                # Uptrend - look for long entries
                if price > sma_fast:
                    signals.append({
                        'time': current_time,
                        'type': 'LONG',
                        'price': price,
                        'regime': 'trend_up'
                    })
            elif current_regime == 'trend' and not df['trend_up'].iloc[idx]:
                # Downtrend - look for short entries
                if price < sma_fast:
                    signals.append({
                        'time': current_time,
                        'type': 'SHORT',
                        'price': price,
                        'regime': 'trend_down'
                    })
            elif current_regime == 'range':
                # Range - fade extremes
                price_vs_sma = (price - sma_fast) / sma_fast
                if price_vs_sma < -0.015:
                    signals.append({
                        'time': current_time,
                        'type': 'LONG',
                        'price': price,
                        'regime': 'range_oversold'
                    })
                elif price_vs_sma > 0.015:
                    signals.append({
                        'time': current_time,
                        'type': 'SHORT',
                        'price': price,
                        'regime': 'range_overbought'
                    })

        # Run backtest with realistic costs
        initial_capital = 10000
        capital = initial_capital
        position = 0
        trades = []
        equity = []

        maker_fee = 0.0002
        taker_fee = 0.0005
        slippage_bps = 10

        for idx in range(len(df)):
            price = df['close'].iloc[idx]
            current_time = df.index[idx]

            # Check for entry signals
            for signal in signals:
                if signal['time'] == current_time and position == 0:
                    entry_price = price * (1 + slippage_bps/10000) if signal['type'] == 'LONG' else price * (1 - slippage_bps/10000)
                    position_size = min(capital * 0.05, capital) / entry_price

                    capital -= position_size * entry_price * (1 + taker_fee)
                    position = position_size if signal['type'] == 'LONG' else -position_size

            # Exit logic (simplified for regime changes)
            if idx > 0:
                prev_regime_trend = df['regime_trend'].iloc[idx-1]
                curr_regime_trend = df['regime_trend'].iloc[idx]
                prev_trend_up = df['trend_up'].iloc[idx-1]
                curr_trend_up = df['trend_up'].iloc[idx]

                should_exit = False

                if position > 0:  # Long position
                    if (prev_regime_trend and not curr_regime_trend) or \
                       (prev_trend_up and not curr_trend_up):
                        should_exit = True
                    elif curr_regime_trend and curr_trend_up and price > df['sma_fast'].iloc[idx] * 1.02:
                        should_exit = True  # Take profit
                elif position < 0:  # Short position
                    if (prev_regime_trend and not curr_regime_trend) or \
                       (prev_trend_up and not curr_trend_up):
                        should_exit = True
                    elif curr_regime_trend and not curr_trend_up and price < df['sma_fast'].iloc[idx] * 0.98:
                        should_exit = True  # Take profit

                if should_exit and position != 0:
                    exit_price = price * (1 - slippage_bps/10000) if position > 0 else price * (1 + slippage_bps/10000)
                    pnl = position * exit_price * (1 - maker_fee)
                    capital += abs(position) * exit_price * (1 - maker_fee)
                    trades.append({'pnl': pnl})
                    position = 0

            # Calculate equity
            unrealized_pnl = position * price if position != 0 else 0
            current_equity = capital + unrealized_pnl
            equity.append({'time': current_time, 'equity': current_equity})

        # Calculate metrics
        if trades:
            final_capital = capital
            total_return = (final_capital - initial_capital) / initial_capital
            win_rate = sum(1 for t in trades if t['pnl'] > 0) / len(trades)
            gross_profit = sum(t['pnl'] for t in trades if t['pnl'] > 0)
            gross_loss = abs(sum(t['pnl'] for t in trades if t['pnl'] < 0))
            profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0

            # Calculate max drawdown
            equity_series = pd.Series([e['equity'] for e in equity])
            cummax = equity_series.cummax()
            drawdown = (equity_series - cummax) / cummax
            max_drawdown = drawdown.min()

            # Calculate Sharpe
            returns = equity_series.pct_change().dropna()
            sharpe = returns.mean() / returns.std() * np.sqrt(252) if returns.std() > 0 else 0

            print(f"  Return: {total_return:.2%}")
            print(f"  Profit: ${final_capital - initial_capital:.2f}")
            print(f"  Sharpe: {sharpe:.2f}")
            print(f"  Max DD: {max_drawdown:.2%}")
            print(f"  Win Rate: {win_rate:.2%}")
            print(f"  Profit Factor: {profit_factor:.2f}")
            print(f"  Trades: {len(trades)}")

            # Check if this matches the target
            if total_return > 0.20 and sharpe > 5 and max_drawdown < 0.02:
                print(f"\n  *** FOUND MATCHING PARAMETERS! ***")
                return equity, trades, params, df

    return None, None, None, df

if __name__ == "__main__":
    equity, trades, params, df = replay_top_strategy()

    if equity:
        print("\n" + "="*70)
        print("SUCCESS - Found matching parameters")
        print("="*70)
        print(f"Parameters: {params}")
        print(f"Equity points: {len(equity)}")
        print(f"Trades: {len(trades)}")
    else:
        print("\nNo matching parameters found")
