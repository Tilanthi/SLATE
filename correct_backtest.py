#!/usr/bin/env python3
"""
Run the ACTUAL regime switching backtest using the real algorithm from the discovery engine.
NO SIMULATED DATA - only real market data and actual strategy logic.
"""

import pandas as pd
import numpy as np
from pathlib import Path

def run_actual_backtest():
    """Run the actual regime switching backtest as implemented in the discovery engine."""

    # Load REAL market data
    data_path = "sol_data_cache/SOLUSDT_1h_1y.csv"
    df = pd.read_csv(data_path)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df = df.set_index('timestamp')

    print(f"Loaded {len(df)} REAL candles from {df.index[0]} to {df.index[-1]}")
    print(f"Price range: ${df['close'].min():.2f} - ${df['close'].max():.2f}")
    print("\nRunning ACTUAL regime switching backtest...")

    # Calculate indicators exactly as the discovery engine does
    df['sma_20'] = df['close'].rolling(20).mean()
    df['returns'] = df['close'].pct_change()
    df['atr'] = (df['high'] - df['low']).rolling(14).mean()

    # Calculate ATR ratio (current ATR / average ATR)
    avg_atr = df['atr'].mean()
    df['atr_ratio'] = df['atr'] / avg_atr

    # Apply the ACTUAL strategy logic from the discovery engine
    # From line 1264-1271 in edge_discovery_engine.py
    signals = []

    for idx in range(100, len(df)):  # Skip warmup period
        row = df.iloc[idx]

        # Regime switching logic (EXACT code from discovery engine)
        if row['atr_ratio'] < 1.0:  # Low vol regime
            if row['close'] > row['sma_20']:
                signals.append(1)  # Range trade - buy
            else:
                signals.append(0)
        else:  # High vol regime
            if row['returns'] > 0.01:
                signals.append(1)  # Momentum trade long
            elif row['returns'] < -0.01:
                signals.append(-1)  # Momentum trade short
            else:
                signals.append(0)

    df['signal'] = pd.Series(signals, index=df.index[100:])

    # Run backtest with BRUTALLY REALISTIC costs
    initial_capital = 10000
    capital = initial_capital
    position = 0
    entry_price = None
    trades = []
    equity = []

    maker_fee = 0.0002  # 0.02%
    taker_fee = 0.0005  # 0.05%
    base_slippage_bps = 10  # 10 bps

    for idx in range(100, len(df)):
        price = df['close'].iloc[idx]
        signal = df['signal'].iloc[idx]

        # Entry logic
        if signal != 0 and position == 0:
            # Calculate slippage based on volatility (as discovery engine does)
            volatility = df['atr'].iloc[idx] / price
            slippage_bps = base_slippage_bps * (1 + volatility * 100)

            if signal == 1:  # Long entry
                entry_price = price * (1 + slippage_bps/10000)
                position_size = (capital * 0.05) / entry_price  # 5% max position
                capital -= position_size * entry_price * (1 + taker_fee)
                position = position_size
            elif signal == -1:  # Short entry
                entry_price = price * (1 - slippage_bps/10000)
                position_size = (capital * 0.05) / entry_price
                capital -= position_size * entry_price * (1 + taker_fee)
                position = -position_size

        # Exit logic (opposite signal)
        elif position != 0:
            if (position > 0 and signal == -1) or (position < 0 and signal == 1) or signal == 0:
                # Exit position
                volatility = df['atr'].iloc[idx] / price
                slippage_bps = base_slippage_bps * (1 + volatility * 100)

                if position > 0:
                    exit_price = price * (1 - slippage_bps/10000)
                    pnl = position * exit_price * (1 - maker_fee)
                else:
                    exit_price = price * (1 + slippage_bps/10000)
                    pnl = abs(position) * exit_price * (1 - maker_fee)

                capital += abs(position) * exit_price * (1 - maker_fee)
                trades.append(pnl)
                position = 0
                entry_price = None

        # Calculate equity
        if position != 0:
            unrealized_pnl = position * price
            current_equity = capital + unrealized_pnl
        else:
            current_equity = capital

        equity.append({'time': df.index[idx], 'equity': current_equity})

    # Calculate actual metrics
    final_capital = capital
    total_return = (final_capital - initial_capital) / initial_capital

    # Calculate max drawdown properly
    equity_series = pd.Series([e['equity'] for e in equity])
    cummax = equity_series.cummax()
    drawdown = (equity_series - cummax) / cummax
    max_drawdown = drawdown.min()

    # Calculate Sharpe ratio
    returns = equity_series.pct_change().dropna()
    sharpe = returns.mean() / returns.std() * np.sqrt(252) if returns.std() > 0 else 0

    # Calculate win rate
    if trades:
        win_rate = sum(1 for t in trades if t > 0) / len(trades)
        gross_profit = sum(t for t in trades if t > 0)
        gross_loss = abs(sum(t for t in trades if t < 0))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0
    else:
        win_rate = 0
        profit_factor = 0

    print("\n" + "="*70)
    print("ACTUAL BACKTEST RESULTS (using real strategy logic)")
    print("="*70)
    print(f"Return: {total_return:.2%}")
    print(f"Profit: ${final_capital - initial_capital:.2f}")
    print(f"Sharpe: {sharpe:.2f}")
    print(f"Max Drawdown: {max_drawdown:.2%}")
    print(f"Win Rate: {win_rate:.2%}")
    print(f"Profit Factor: {profit_factor:.2f}")
    print(f"Total Trades: {len(trades)}")
    print("="*70)

    return equity, trades, df

if __name__ == "__main__":
    equity, trades, df = run_actual_backtest()
