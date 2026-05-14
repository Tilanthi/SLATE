#!/usr/bin/env python3
"""
Backtest Haasscript Donchian Channel strategy on REAL BTCUSDT futures data.
4-hour candles, 9 months, 20 BTC starting capital with 20x leverage.

Refactored to use consolidated SLATE modules - eliminates code duplication
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime, timedelta

# Use consolidated modules instead of duplicated code
import sys
sys.path.insert(0, '/Users/gjw255/astrodata/SWARM/SLATE')

from slate_core.data.binance_fetcher import BinanceFetcher
from slate_core.config.constants import MAKER_FEE, TAKER_FEE

def fetch_binance_futures_data(symbol="BTCUSDT", interval="4h", months=9):
    """Fetch REAL data from Binance Futures (using consolidated module)."""
    print(f"Fetching {months} months of {interval} data from Binance Futures for {symbol}...")

    end_time = datetime.now()
    start_time = end_time - timedelta(days=months*30)

    fetcher = BinanceFetcher()
    df = fetcher.fetch_klines(symbol=symbol, interval=interval,
                              start_date=start_time, end_time=end_time,
                              use_futures=True)

    print(f"✓ Loaded {len(df)} candles from {df.index[0]} to {df.index[-1]}")
    print(f"Price range: ${df['close'].min():,.2f} - ${df['close'].max():,.2f}")

    return df

def calculate_indicators(df, period=50, filter_pct=0.10):
    """Calculate Donchian Channel indicators."""
    df['dc_upper'] = df['high'].rolling(window=period).max()
    df['dc_lower'] = df['low'].rolling(window=period).min()

    # Apply filter
    upper_filter = df['dc_upper'] * (1 + filter_pct/100)
    lower_filter = df['dc_lower'] * (1 - filter_pct/100)

    return df['dc_upper'], df['lower_filter']

def run_backtest(df, period=20, filter_pct=0.0, leverage=2):  # 20-period, 2x leverage for safety
    """
    Run the Haasscript Donchian Channel backtest.

    Strategy:
    - Buy when close crosses above lower band
    - Sell when close crosses below upper band
    - Take Profit: 5 ATR
    - Stop Loss: 2 ATR
    - Initial Capital: 20 BTC
    - Leverage: 20x
    """

    # Calculate ATR for position sizing
    df['atr'] = (df['high'] - df['low']).rolling(14).mean()

    # Calculate Donchian Channel (shifted by 1 to avoid look-ahead bias)
    # We use the PREVIOUS period's channel for entry signals
    dc_upper = df['high'].rolling(window=period).max().shift(1)
    dc_lower = df['low'].rolling(window=period).min().shift(1)

    # Apply filter (breakout confirmation)
    # Buy when price breaks above upper channel + filter
    # Sell when price breaks below lower channel - filter
    breakout_upper = dc_upper * (1 + filter_pct/100)
    breakout_lower = dc_lower * (1 - filter_pct/100)

    # Initialize tracking
    initial_btc = 20.0  # Starting capital
    position_size_btc = initial_btc * leverage  # Position size based on leverage

    capital = initial_btc  # In BTC
    bankruptcy_threshold = initial_btc * 0.1  # Bankruptcy at 90% loss
    position = 0  # 1 = long, -1 = short
    entry_price = None
    entry_btc_price = None
    stop_loss_price = None
    take_profit_price = None

    entries = []
    exits = []
    equity = []

    # Transaction costs (realistic futures trading)
    maker_fee = 0.0002  # 0.02%
    taker_fee = 0.0004  # 0.04% (futures rates)
    slippage_bps = 5  # 5 bps on futures

    print(f"\n{'='*60}")
    print(f"BACKTEST PARAMETERS")
    print(f"{'='*60}")
    print(f"Symbol: BTCUSDT Futures Perpetual")
    print(f"Timeframe: 4-hour candles")
    print(f"Period: {period} (Donchian Channel)")
    print(f"Filter: {filter_pct*100:.1f}%")
    print(f"Initial Capital: {initial_btc} BTC")
    print(f"Leverage: {leverage}x")
    print(f"Position Size: {position_size_btc:.1f} BTC")
    print(f"Maker Fee: {maker_fee*100:.3f}%")
    print(f"Taker Fee: {taker_fee*100:.3f}%")
    print(f"Slippage: {slippage_bps} bps")
    print(f"Take Profit: 5 ATR")
    print(f"Stop Loss: 2 ATR")
    print(f"{'='*60}\n")

    # Debug: Check if any breakouts exist in dataset
    any_upper_breakout = (df['close'] > dc_upper).any()
    any_lower_breakdown = (df['close'] < dc_lower).any()
    print(f"\nDEBUG: Any upper breakouts in dataset: {any_upper_breakout}")
    print(f"DEBUG: Any lower breakdowns in dataset: {any_lower_breakdown}")

    if any_upper_breakout:
        breakout_bars = df[df['close'] > dc_upper]
        print(f"DEBUG: Found {len(breakout_bars)} upper breakout bars")
        print(f"DEBUG: First breakout at index {breakout_bars.index[0]}")

    # Debug: Count potential signals
    potential_long_signals = 0
    potential_short_signals = 0

    for i in range(period, len(df)):
        close = df['close'].iloc[i]
        high = df['high'].iloc[i]
        low = df['low'].iloc[i]
        atr = df['atr'].iloc[i]

        # Check for entries
        if position == 0:
            # Buy signal: cross above upper breakout band (breakout)
            if close > breakout_upper.iloc[i] and df['close'].iloc[i-1] <= breakout_upper.iloc[i-1]:
                potential_long_signals += 1
                entry_price = close * (1 + slippage_bps/10000)
                entry_btc_price = entry_price
                stop_loss_price = entry_price * (1 - 2 * atr / entry_price)
                take_profit_price = entry_price * (1 + 5 * atr / entry_price)

                position = 1
                entries.append({
                    'time': df.index[i],
                    'type': 'LONG',
                    'price': entry_price,
                    'sl': stop_loss_price,
                    'tp': take_profit_price
                })

            # Sell signal: cross below lower breakout band (breakdown)
            elif close < breakout_lower.iloc[i] and df['close'].iloc[i-1] >= breakout_lower.iloc[i-1]:
                potential_short_signals += 1
                entry_price = close * (1 - slippage_bps/10000)
                entry_btc_price = entry_price
                stop_loss_price = entry_price * (1 + 2 * atr / entry_price)
                take_profit_price = entry_price * (1 - 5 * atr / entry_price)

                position = -1
                entries.append({
                    'time': df.index[i],
                    'type': 'SHORT',
                    'price': entry_price,
                    'sl': stop_loss_price,
                    'tp': take_profit_price
                })

        # Check exits for existing positions
        elif position == 1:  # Long position
            # Check stop loss
            if low <= stop_loss_price:
                exit_price = stop_loss_price * (1 - slippage_bps/10000)
                pnl = position_size_btc * (exit_price - entry_btc_price) * (1 - taker_fee)
                capital += pnl / entry_btc_price  # Convert to BTC
                exits.append({
                    'time': df.index[i],
                    'type': 'SL',
                    'price': exit_price,
                    'pnl_btc': pnl / entry_btc_price,
                    'reason': 'stop_loss'
                })
                position = 0
                entry_price = None

            # Check take profit
            elif high >= take_profit_price:
                exit_price = take_profit_price * (1 - slippage_bps/10000)
                pnl = position_size_btc * (exit_price - entry_btc_price) * (1 - taker_fee)
                capital += pnl / entry_btc_price
                exits.append({
                    'time': df.index[i],
                    'type': 'TP',
                    'price': exit_price,
                    'pnl_btc': pnl / entry_btc_price,
                    'reason': 'take_profit'
                })
                position = 0
                entry_price = None

            # Check reverse signal (cross below lower breakout band)
            elif close < breakout_lower.iloc[i] and df['close'].iloc[i-1] >= breakout_lower.iloc[i-1]:
                # Close existing long, potentially open short
                exit_price = close * (1 - slippage_bps/10000)
                pnl = position_size_btc * (exit_price - entry_btc_price) * (1 - taker_fee)
                capital += pnl / entry_btc_price
                exits.append({
                    'time': df.index[i],
                    'type': 'REVERSE',
                    'price': exit_price,
                    'pnl_btc': pnl / entry_btc_price,
                    'reason': 'signal_reverse'
                })
                position = 0
                entry_price = None

        elif position == -1:  # Short position
            # Check stop loss
            if high >= stop_loss_price:
                exit_price = stop_loss_price * (1 + slippage_bps/10000)
                pnl = position_size_btc * (entry_btc_price - exit_price) * (1 - taker_fee)
                capital += pnl / entry_btc_price
                exits.append({
                    'time': df.index[i],
                    'type': 'SL',
                    'price': exit_price,
                    'pnl_btc': pnl / entry_btc_price,
                    'reason': 'stop_loss'
                })
                position = 0
                entry_price = None

            # Check take profit
            elif low <= take_profit_price:
                exit_price = take_profit_price * (1 + slippage_bps/10000)
                pnl = position_size_btc * (entry_btc_price - exit_price) * (1 - taker_fee)
                capital += pnl / entry_btc_price
                exits.append({
                    'time': df.index[i],
                    'type': 'TP',
                    'price': exit_price,
                    'pnl_btc': pnl / entry_btc_price,
                    'reason': 'take_profit'
                })
                position = 0
                entry_price = None

            # Check reverse signal (cross above upper breakout band)
            elif close > breakout_upper.iloc[i] and df['close'].iloc[i-1] <= breakout_upper.iloc[i-1]:
                exit_price = close * (1 + slippage_bps/10000)
                pnl = position_size_btc * (entry_btc_price - exit_price) * (1 - taker_fee)
                capital += pnl / entry_btc_price
                exits.append({
                    'time': df.index[i],
                    'type': 'REVERSE',
                    'price': exit_price,
                    'pnl_btc': pnl / entry_btc_price,
                    'reason': 'signal_reverse'
                })
                position = 0
                entry_price = None

        # Bankruptcy check
        if capital < bankruptcy_threshold:
            print(f"\n⚠️  BANKRUPTCY: Capital dropped to {capital:.2f} BTC, stopping trading")
            break

        # Calculate equity
        if position != 0:
            unrealized_pnl_btc = position_size_btc * (close - entry_btc_price)
            if position == 1:
                current_equity_btc = capital + unrealized_pnl_btc / entry_btc_price
            else:
                current_equity_btc = capital + unrealized_pnl_btc / entry_btc_price
        else:
            current_equity_btc = capital

        equity.append({'time': df.index[i], 'equity_btc': current_equity_btc})

    # Debug output
    print(f"\nDEBUG: Potential long signals: {potential_long_signals}")
    print(f"DEBUG: Potential short signals: {potential_short_signals}")
    print(f"DEBUG: Total bars analyzed: {len(df) - period}")

    return df, entries, exits, equity, leverage

def create_backtest_visualization(df, entries, exits, equity, leverage=2):
    """Create visualization with price, entries, exits, and equity curve."""
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(16, 10), height_ratios=[2, 1])
    fig.suptitle('Haasscript Donchian Channel Strategy - BTCUSDT Futures 4H\n9 Month Backtest | 20 BTC Start | 20x Leverage | Realistic Costs',
                 fontsize=14, fontweight='bold')

    # Plot 1: Price with entries and exits
    ax1.plot(df.index, df['close'], label='BTCUSDT Price', color='#2c3e50', linewidth=1.5, alpha=0.7)

    # Plot Donchian Channel
    dc_upper = df['high'].rolling(window=50).max()
    dc_lower = df['low'].rolling(window=50).min()
    ax1.fill_between(df.index, dc_lower, dc_upper, alpha=0.1, color='gray', label='Donchian Channel')

    # Plot entries
    long_entries = [e for e in entries if e['type'] == 'LONG']
    short_entries = [e for e in entries if e['type'] == 'SHORT']

    if long_entries:
        le_times = [e['time'] for e in long_entries]
        le_prices = [e['price'] for e in long_entries]
        ax1.scatter(le_times, le_prices, marker='^', color='#27ae60', s=100,
                   label=f'Long Entry ({len(long_entries)})', zorder=5, alpha=0.8)

    if short_entries:
        se_times = [e['time'] for e in short_entries]
        se_prices = [e['price'] for e in short_entries]
        ax1.scatter(se_times, se_prices, marker='v', color='#e74c3c', s=100,
                   label=f'Short Entry ({len(short_entries)})', zorder=5, alpha=0.8)

    # Plot exits
    take_profits = [e for e in exits if e['reason'] == 'take_profit']
    stop_losses = [e for e in exits if e['reason'] == 'stop_loss']
    reverses = [e for e in exits if e['reason'] == 'signal_reverse']

    if take_profits:
        tp_times = [e['time'] for e in take_profits]
        tp_prices = [e['price'] for e in take_profits]
        ax1.scatter(tp_times, tp_prices, marker='o', color='#27ae60', s=60,
                   label=f'TP ({len(take_profits)})', zorder=5)

    if stop_losses:
        sl_times = [e['time'] for e in stop_losses]
        sl_prices = [e['price'] for e in stop_losses]
        ax1.scatter(sl_times, sl_prices, marker='x', color='#e74c3c', s=60,
                   label=f'SL ({len(stop_losses)})', zorder=5)

    if reverses:
        rev_times = [e['time'] for e in reverses]
        rev_prices = [e['price'] for e in reverses]
        ax1.scatter(rev_times, rev_prices, marker='s', color='#95a5a6', s=40,
                   label=f'Reverse ({len(reverses)})', zorder=5)

    ax1.set_ylabel('Price (USDT)', fontsize=11, fontweight='bold')
    ax1.set_title(f'BTCUSDT Price with Trade Entries & Exits\n{df.index[0].strftime("%Y-%m-%d")} to {df.index[-1].strftime("%Y-%m-%d")}',
                  fontsize=12, fontweight='bold')
    ax1.legend(loc='upper left', fontsize=9, ncol=3)
    ax1.grid(True, alpha=0.3)

    # Format y-axis as currency
    ax1.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'${x:,.0f}'))

    # Plot 2: Equity curve
    equity_df = pd.DataFrame(equity).set_index('time')
    equity_df['equity_btc'] = equity_df['equity_btc']

    # Convert equity to USDT for display (approximate)
    first_price = df['close'].iloc[0]
    equity_df['equity_usdt'] = equity_df['equity_btc'] * first_price

    ax2.plot(equity_df.index, equity_df['equity_btc'], label='Portfolio (BTC)', color='#f39c12', linewidth=2.5)

    # Add initial capital line
    initial_capital_btc = 20
    ax2.axhline(y=initial_capital_btc, color='#95a5a6', linestyle='--', linewidth=1.5,
                label=f'Initial Capital ({initial_capital_btc} BTC)')

    # Shade drawdown areas
    cummax = equity_df['equity_btc'].cummax()
    drawdown = (equity_df['equity_btc'] - cummax) / cummax
    ax2.fill_between(equity_df.index, equity_df['equity_btc'], cummax,
                     where=(equity_df['equity_btc'] < cummax), color='#e74c3c', alpha=0.2, label='Drawdown')

    # Calculate final statistics
    final_btc = equity_df['equity_btc'].iloc[-1]
    total_return_btc = final_btc - initial_capital_btc
    total_return_pct = total_return_btc / initial_capital_btc

    # Calculate max drawdown
    max_drawdown_btc = (equity_df['equity_btc'].min() - equity_df['equity_btc'].max()) / equity_df['equity_btc'].max()

    # Calculate trade statistics
    winning_trades = sum(1 for e in exits if e['pnl_btc'] > 0)
    total_trades = len(exits)
    win_rate = winning_trades / total_trades if total_trades > 0 else 0

    gross_profit_btc = sum(e['pnl_btc'] for e in exits if e['pnl_btc'] > 0)
    gross_loss_btc = abs(sum(e['pnl_btc'] for e in exits if e['pnl_btc'] < 0))
    profit_factor = gross_profit_btc / gross_loss_btc if gross_loss_btc > 0 else 0

    ax2.set_ylabel('Portfolio (BTC)', fontsize=11, fontweight='bold')
    ax2.set_xlabel('Time', fontsize=11, fontweight='bold')
    ax2.set_title(f'Equity Curve - Final: {final_btc:.2f} BTC ({total_return_pct:+.2%}) | Max DD: {max_drawdown_btc:.2%} | Trades: {len(entries)} entries, {len(exits)} exits',
                  fontsize=12, fontweight='bold')
    ax2.legend(loc='upper left', fontsize=9, ncol=3)
    ax2.grid(True, alpha=0.3)

    plt.tight_layout()

    # Save figure
    output_path = '/Users/gjw255/astrodata/SWARM/SLATE/haasscript_backtest.png'
    plt.savefig(output_path, dpi=150, bbox_inches='tight', facecolor='white')
    print(f"\n✓ Visualization saved to: {output_path}")

    # Print statistics
    print(f"\n{'='*60}")
    print("BACKTEST RESULTS")
    print(f"{'='*60}")
    print(f"Initial Capital: {initial_capital_btc} BTC")
    print(f"Leverage: {leverage}x")
    print(f"Final Capital: {final_btc:.2f} BTC")
    print(f"Total Return: {total_return_pct:+.2%}")
    print(f"Total Profit: {total_return_btc:.2f} BTC")
    print(f"Max Drawdown: {max_drawdown_btc:.2%}")
    print(f"Total Trades: {len(entries)} entries, {len(exits)} exits")
    print(f"Win Rate: {win_rate:.2%} ({winning_trades}/{total_trades})")
    print(f"Profit Factor: {profit_factor:.2f}")

    # Calculate approximate USD value (using average price)
    avg_price = df['close'].mean()
    # Note: position_size calculation depends on leverage, using simple estimate here
    if total_trades > 0:
        total_profit_usd_approx = total_return_btc * initial_capital_btc * avg_price
        print(f"\nApprox USD Value at ${avg_price:,.0f}/BTC: ${total_profit_usd_approx:,.0f}")
    print(f"{'='*60}")

    return {
        'final_btc': final_btc,
        'total_return_pct': total_return_pct,
        'max_drawdown_pct': max_drawdown_btc,
        'total_trades': len(exits),
        'win_rate': win_rate
    }

# Run the backtest
print("Fetching REAL data from Binance Futures...")
df = fetch_binance_futures_data(symbol="BTCUSDT", interval="4h", months=9)

if df is not None and len(df) > 100:
    print("\nRunning backtest with Haasscript Donchian Channel strategy...")
    df, entries, exits, equity, leverage_used = run_backtest(df)
    results = create_backtest_visualization(df, entries, exits, equity, leverage_used)
else:
    print("Error: Could not fetch sufficient data")
