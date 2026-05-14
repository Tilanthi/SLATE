#!/usr/bin/env python3
"""
Volume Imbalance Strategy - Perpetual Futures
1x Leverage, 5% Position Sizing, Both Long & Short

Complete backtest with equity curve visualization
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
import requests
from pathlib import Path

def fetch_binance_futures_daily(days=365):
    """Fetch perpetual futures data."""
    base_url = "https://fapi.binance.com/fapi/v1/klines"
    end_time = int(datetime.now().timestamp() * 1000)
    start_time = int((datetime.now() - timedelta(days=days)).timestamp() * 1000)

    all_klines = []
    current_start = start_time

    print(f"Fetching {days} days of BTCUSDT perpetual futures data...")

    while current_start < end_time:
        params = {"symbol": "BTCUSDT", "interval": "1d",
                   "startTime": current_start, "endTime": end_time, "limit": 1000}
        try:
            response = requests.get(base_url, params=params, timeout=10)
            response.raise_for_status()
            klines = response.json()
            if not klines:
                break
            all_klines.extend(klines)
            current_start = klines[-1][0] + 1
        except Exception as e:
            print(f"Error: {e}")
            break

    df = pd.DataFrame(all_klines, columns=[
        'timestamp', 'open', 'high', 'low', 'close', 'volume',
        'close_time', 'quote_volume', 'trades', 'taker_buy_base',
        'taker_buy_quote', 'ignore'
    ])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    df = df.set_index('timestamp')
    for col in ['open', 'high', 'low', 'close', 'volume']:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    df['atr'] = (df['high'] - df['low']).rolling(14).mean()
    df['volatility'] = df['atr'] / df['close']
    df = df.sort_index()
    print(f"✓ Loaded {len(df)} daily candles from {df.index[0]} to {df.index[-1]}")
    return df

def calculate_vi(df, period):
    """Calculate Volume Imbalance."""
    df_temp = df.copy()
    df_temp['is_up'] = df_temp['close'] > df_temp['open']
    df_temp['up_volume'] = df_temp['volume'] * df_temp['is_up']
    df_temp['down_volume'] = df_temp['volume'] * (~df_temp['is_up'])
    up_vol_sum = df_temp['up_volume'].rolling(window=period).sum()
    down_vol_sum = df_temp['down_volume'].rolling(window=period).sum()
    total_vol = df_temp['volume'].rolling(window=period).sum()
    vi = (up_vol_sum - down_vol_sum) / total_vol
    return vi

def run_backtest(df, vi_period=9, vi_threshold=0.20,
                  sl_pct=0.015, tp_pct=0.03, trail_pct=0.01,
                  position_size_pct=0.05, leverage=1):
    """Run backtest with perpetual futures and realistic costs."""

    df_temp = df.copy()
    df_temp['vi'] = calculate_vi(df_temp, vi_period)

    # Transaction costs
    maker_fee = 0.0002
    taker_fee = 0.0004
    base_slippage_bps = 10

    capital = 10000
    position = None
    entry_price = None
    entry_btc_price = None
    sl_price = None
    tp_price = None
    highest = None
    lowest = None
    position_btc = None

    trades = []
    equity = []

    for i in range(vi_period, len(df_temp)):
        close = df_temp['close'].iloc[i]
        high = df_temp['high'].iloc[i]
        low = df_temp['low'].iloc[i]
        vi = df_temp['vi'].iloc[i]
        volatility = df_temp['volatility'].iloc[i]

        if pd.isna(vi) or pd.isna(volatility):
            equity.append(capital)
            continue

        # Volatility-adjusted slippage
        slippage_bps = base_slippage_bps * (1 + volatility * 5)
        slippage_bps = max(5, min(slippage_bps, 25))

        # Fill rate
        fill_rate = max(0.80, min(0.98, 0.90 - (volatility * 0.5)))

        # Entry
        if position is None:
            if vi > vi_threshold:
                if np.random.random() > fill_rate:
                    equity.append(capital)
                    continue

                entry_price = close * (1 + slippage_bps / 10000)
                entry_btc_price = entry_price

                # 5% position sizing
                position_value = capital * position_size_pct * leverage
                position_btc = position_value / entry_btc_price

                if np.random.random() < 0.15:
                    fill_pct = np.random.uniform(0.30, 0.70)
                    position_btc *= fill_pct

                position = 'long'
                highest = close
                sl_price = entry_price * (1 - sl_pct)
                tp_price = entry_price * (1 + tp_pct)

                trades.append({
                    'time': df_temp.index[i],
                    'type': 'LONG',
                    'entry': entry_price,
                    'vi': vi
                })

            elif vi < -vi_threshold:
                if np.random.random() > fill_rate:
                    equity.append(capital)
                    continue

                entry_price = close * (1 - slippage_bps / 10000)
                entry_btc_price = entry_price

                position_value = capital * position_size_pct * leverage
                position_btc = position_value / entry_btc_price

                if np.random.random() < 0.15:
                    fill_pct = np.random.uniform(0.30, 0.70)
                    position_btc *= fill_pct

                position = 'short'
                lowest = close
                sl_price = entry_price * (1 + sl_pct)
                tp_price = entry_price * (1 - tp_pct)

                trades.append({
                    'time': df_temp.index[i],
                    'type': 'SHORT',
                    'entry': entry_price,
                    'vi': vi
                })

        # Exit
        elif position == 'long':
            highest = max(highest, high)
            trail = highest * (1 - trail_pct)
            sl_price = max(sl_price, trail)

            if low <= sl_price:
                exit_price = sl_price * (1 - slippage_bps / 10000)
                pnl = position_btc * (exit_price - entry_btc_price) * (1 - taker_fee)
                capital += pnl
                trades[-1]['exit'] = exit_price
                trades[-1]['exit_time'] = df_temp.index[i]
                trades[-1]['pnl'] = pnl
                trades[-1]['reason'] = 'stop_loss'
                position = None
                position_btc = None

            elif high >= tp_price:
                exit_price = tp_price * (1 - slippage_bps / 10000)
                pnl = position_btc * (exit_price - entry_btc_price) * (1 - taker_fee)
                capital += pnl
                trades[-1]['exit'] = exit_price
                trades[-1]['exit_time'] = df_temp.index[i]
                trades[-1]['pnl'] = pnl
                trades[-1]['reason'] = 'take_profit'
                position = None
                position_btc = None

            elif vi < -vi_threshold:
                exit_price = close * (1 - slippage_bps / 10000)
                pnl = position_btc * (exit_price - entry_btc_price) * (1 - taker_fee)
                capital += pnl
                trades[-1]['exit'] = exit_price
                trades[-1]['exit_time'] = df_temp.index[i]
                trades[-1]['pnl'] = pnl
                trades[-1]['reason'] = 'signal_reverse'
                position = None
                position_btc = None

        elif position == 'short':
            lowest = min(lowest, low)
            trail = lowest * (1 + trail_pct)
            sl_price = min(sl_price, trail)

            if high >= sl_price:
                exit_price = sl_price * (1 + slippage_bps / 10000)
                pnl = position_btc * (entry_btc_price - exit_price) * (1 - taker_fee)
                capital += pnl
                trades[-1]['exit'] = exit_price
                trades[-1]['exit_time'] = df_temp.index[i]
                trades[-1]['pnl'] = pnl
                trades[-1]['reason'] = 'stop_loss'
                position = None
                position_btc = None

            elif low <= tp_price:
                exit_price = tp_price * (1 + slippage_bps / 10000)
                pnl = position_btc * (entry_btc_price - exit_price) * (1 - taker_fee)
                capital += pnl
                trades[-1]['exit'] = exit_price
                trades[-1]['exit_time'] = df_temp.index[i]
                trades[-1]['pnl'] = pnl
                trades[-1]['reason'] = 'take_profit'
                position = None
                position_btc = None

            elif vi > vi_threshold:
                exit_price = close * (1 - slippage_bps / 10000)
                pnl = position_btc * (entry_btc_price - exit_price) * (1 - taker_fee)
                capital += pnl
                trades[-1]['exit'] = exit_price
                trades[-1]['exit_time'] = df_temp.index[i]
                trades[-1]['pnl'] = pnl
                trades[-1]['reason'] = 'signal_reverse'
                position = None
                position_btc = None

        equity.append(capital)

    return capital, trades, equity, df_temp

def create_equity_visualization(df, trades, equity):
    """Create comprehensive visualization."""

    fig = plt.figure(figsize=(18, 10))
    gs = fig.add_gridspec(3, 2, hspace=0.3, wspace=0.3)

    # Convert to DataFrame
    equity_df = pd.DataFrame({
        'time': df.index[len(df)-len(equity):],
        'equity': equity
    }).set_index('time')

    # Plot 1: Price with trades
    ax1 = fig.add_subplot(gs[0, :])
    ax1.plot(df.index, df['close'], color='#2c3e50', linewidth=1.5, label='BTCUSDT Perpetual', alpha=0.7)

    # Plot trades
    long_trades = [t for t in trades if 'entry' in t and t.get('type') == 'LONG']
    short_trades = [t for t in trades if 'entry' in t and t.get('type') == 'SHORT']

    if long_trades:
        entry_times = [t['time'] for t in long_trades]
        entry_prices = [t['entry'] for t in long_trades]
        ax1.scatter(entry_times, entry_prices, marker='^', color='#27ae60', s=120,
                   label=f'Long Entries ({len(long_trades)})', zorder=5, alpha=0.8, edgecolors='black', linewidth=1)

    if short_trades:
        entry_times = [t['time'] for t in short_trades]
        entry_prices = [t['entry'] for t in short_trades]
        ax1.scatter(entry_times, entry_prices, marker='v', color='#e74c3c', s=120,
                   label=f'Short Entries ({len(short_trades)})', zorder=5, alpha=0.8, edgecolors='black', linewidth=1)

    # Plot exits
    exit_trades = [t for t in trades if 'exit' in t]
    tp_trades = [t for t in exit_trades if t.get('reason') == 'take_profit']
    sl_trades = [t for t in exit_trades if t.get('reason') == 'stop_loss']
    rev_trades = [t for t in exit_trades if t.get('reason') == 'signal_reverse']

    if tp_trades:
        exit_times = [t['exit_time'] for t in tp_trades]
        exit_prices = [t['exit'] for t in tp_trades]
        ax1.scatter(exit_times, exit_prices, marker='o', color='#27ae60', s=60,
                   label=f'TP ({len(tp_trades)})', zorder=4, alpha=0.7)

    if sl_trades:
        exit_times = [t['exit_time'] for t in sl_trades]
        exit_prices = [t['exit'] for t in sl_trades]
        ax1.scatter(exit_times, exit_prices, marker='x', color='#e74c3c', s=60,
                   label=f'SL ({len(sl_trades)})', zorder=4, alpha=0.7)

    if rev_trades:
        exit_times = [t['exit_time'] for t in rev_trades]
        exit_prices = [t['exit'] for t in rev_trades]
        ax1.scatter(exit_times, exit_prices, marker='s', color='#95a5a6', s=40,
                   label=f'Reverse ({len(rev_trades)})', zorder=4, alpha=0.7)

    ax1.set_ylabel('Price (USDT)', fontsize=11, fontweight='bold')
    ax1.set_title('BTCUSDT Perpetual Futures - Daily Timeframe\n' +
                   f'{df.index[0].strftime("%Y-%m-%d")} to {df.index[-1].strftime("%Y-%m-%d")}',
                   fontsize=12, fontweight='bold')
    ax1.legend(loc='upper left', fontsize=9, ncol=3)
    ax1.grid(True, alpha=0.3)
    ax1.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'${x:,.0f}'))

    # Plot 2: Volume Imbalance indicator
    ax2 = fig.add_subplot(gs[1, :], sharex=ax1)
    ax2.plot(df.index, df['vi'], color='#3498db', linewidth=1.5, label='Volume Imbalance')
    ax2.axhline(y=0, color='gray', linestyle='-', linewidth=0.8, alpha=0.5)
    ax2.axhline(y=0.20, color='#27ae60', linestyle='--', linewidth=1.5, alpha=0.6, label='Long Threshold')
    ax2.axhline(y=-0.20, color='#e74c3c', linestyle='--', linewidth=1.5, alpha=0.6, label='Short Threshold')
    ax2.fill_between(df.index, 0, df['vi'], where=(df['vi'] > 0), color='#27ae60', alpha=0.15)
    ax2.fill_between(df.index, 0, df['vi'], where=(df['vi'] < 0), color='#e74c3c', alpha=0.15)
    ax2.set_ylabel('Volume Imbalance', fontsize=11, fontweight='bold')
    ax2.set_title('Volume Imbalance Indicator (Period: 9, Threshold: ±0.20)',
                   fontsize=12, fontweight='bold')
    ax2.legend(loc='upper left', fontsize=9)
    ax2.grid(True, alpha=0.3)
    ax2.set_ylim([-1.1, 1.1])

    # Plot 3: Equity curve
    ax3 = fig.add_subplot(gs[2, :], sharex=ax1)
    ax3.plot(equity_df.index, equity_df['equity'],
             color='#f39c12', linewidth=2.5, label='Portfolio Value')
    ax3.axhline(y=10000, color='#95a5a6', linestyle='--', linewidth=1.5,
                label='Initial Capital ($10,000)')

    # Shade drawdown
    cummax = equity_df['equity'].cummax()
    ax3.fill_between(equity_df.index, equity_df['equity'], cummax,
                     where=(equity_df['equity'] < cummax), color='#e74c3c', alpha=0.2, label='Drawdown')

    # Calculate statistics
    final_equity = equity_df['equity'].iloc[-1]
    total_return = (final_equity - 10000) / 10000
    max_dd = (equity_df['equity'].cummax() - equity_df['equity']).max() / 10000

    winning_trades = sum(1 for t in trades if t.get('pnl', 0) > 0)
    total_trades = len([t for t in trades if 'pnl' in t])
    win_rate = winning_trades / total_trades if total_trades > 0 else 0

    gross_profit = sum(t['pnl'] for t in trades if t.get('pnl', 0) > 0)
    gross_loss = abs(sum(t['pnl'] for t in trades if t.get('pnl', 0) < 0))
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0

    ax3.set_ylabel('Portfolio Value (USDT)', fontsize=11, fontweight='bold')
    ax3.set_xlabel('Time', fontsize=11, fontweight='bold')
    ax3.set_title(f'Equity Curve - Final: ${final_equity:,.2f} ({total_return:+.2f}) | ' +
                   f'Max DD: {max_dd:.2%} | Trades: {len(trades)} entries, {total_trades} exits | ' +
                   f'Win Rate: {win_rate:.1%} | PF: {profit_factor:.2f}',
                   fontsize=12, fontweight='bold')
    ax3.legend(loc='upper left', fontsize=9)
    ax3.grid(True, alpha=0.3)
    ax3.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'${x:,.0f}'))

    # Main title
    fig.suptitle('Volume Imbalance Strategy - Perpetual Futures (1x Leverage, 5% Position)\n' +
                 'Daily Timeframe | BTCUSDT | Realistic Transaction Costs',
                 fontsize=14, fontweight='bold')

    plt.tight_layout()

    output_path = Path('VolumeImbalance/equity_curve_5pct.png')
    plt.savefig(output_path, dpi=150, bbox_inches='tight', facecolor='white')
    print(f"\n✓ Equity curve saved to: {output_path}")

    return {
        'final_equity': final_equity,
        'total_return': total_return,
        'max_dd': max_dd,
        'win_rate': win_rate,
        'profit_factor': profit_factor,
        'total_trades': len(trades),
        'exits': total_trades
    }

# Main
print("="*70)
print("VOLUME IMBALANCE STRATEGY - COMPLETE BACKTEST")
print("Perpetual Futures | 1x Leverage | 5% Position Sizing")
print("="*70)

df = fetch_binance_futures_daily(days=365)

print("\nRunning backtest...")
print("Parameters: VI Period=9, Threshold=0.20, SL=1.5%, TP=3%, Trail=1%")
print("Position Size: 5% of capital")
print("Leverage: 1x\n")

capital, trades, equity, df_with_vi = run_backtest(df)

print("\n" + "="*70)
print("BACKTEST RESULTS")
print("="*70)

results = create_equity_visualization(df_with_vi, trades, equity)

print(f"\nInitial Capital: $10,000.00")
print(f"Final Capital: ${results['final_equity']:,.2f}")
print(f"Total Return: {results['total_return']*100:+.2f}%")
print(f"Max Drawdown: {results['max_dd']*100:.2f}%")
print(f"Win Rate: {results['win_rate']*100:.1f}%")
print(f"Profit Factor: {results['profit_factor']:.2f}")
print(f"Total Trades: {results['total_trades']}")
print("="*70)

# Save detailed trade log
trades_df = pd.DataFrame([t for t in trades if 'pnl' in t])
if len(trades_df) > 0:
    trades_df.to_csv('VolumeImbalance/trade_log_5pct.csv', index=False)
    print(f"\n✓ Trade log saved to: VolumeImbalance/trade_log_5pct.csv")
    print(f"  Winning trades: {sum(1 for _, row in trades_df.iterrows() if row['pnl'] > 0)}")
    print(f"  Losing trades: {sum(1 for _, row in trades_df.iterrows() if row['pnl'] < 0)}")

print(f"\n✓ Equity curve saved to: VolumeImbalance/equity_curve_5pct.png")
