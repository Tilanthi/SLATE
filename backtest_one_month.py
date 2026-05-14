#!/usr/bin/env python3
"""
One Month Volume Imbalance Backtest
Run a focused 1-month backtest on recent historical data

Refactored to use consolidated SLATE modules - eliminates code duplication
"""

import matplotlib.pyplot as plt
import pandas as pd

# Use consolidated modules instead of duplicated code
import sys
sys.path.insert(0, '/Users/gjw255/astrodata/SWARM/SLATE')

from slate_core.data.binance_fetcher import BinanceFetcher
from slate_core.indicators.volume_imbalance import VolumeImbalance
from slate_core.config.constants import (
    DEFAULT_SYMBOL,
    DEFAULT_INTERVAL,
    VI_PERIOD_DEFAULT,
    VI_THRESHOLD_DEFAULT,
    DEFAULT_INITIAL_CAPITAL_USDT,
    DEFAULT_LOT_SIZE_BTC,
    DEFAULT_STOP_LOSS_PCT,
    DEFAULT_TAKE_PROFIT_PCT,
    DEFAULT_TRAILING_STOP_PCT
)

def create_visualization(df, equity_curve, trades):
    """Create comprehensive visualization."""
    fig = plt.figure(figsize=(16, 10))

    gs = fig.add_gridspec(3, 1, height_ratios=[2, 1, 1], hspace=0.3)

    # Plot 1: Price with entries and exits
    ax1 = fig.add_subplot(gs[0])
    ax1.plot(df.index, df['close'], color='#2c3e50', linewidth=1.5, alpha=0.7, label='BTCUSDT Price')

    # Plot entries
    long_entries = [t for t in trades if t['type'] == 'LONG']
    short_entries = [t for t in trades if t['type'] == 'SHORT']

    if long_entries:
        entry_times = [t['entry_time'] for t in long_entries]
        entry_prices = [t['entry_price'] for t in long_entries]
        ax1.scatter(entry_times, entry_prices, marker='^', color='#27ae60', s=120,
                   label=f'Long Entries ({len(long_entries)})', zorder=5, edgecolors='darkgreen', linewidths=1.5)

    if short_entries:
        entry_times = [t['entry_time'] for t in short_entries]
        entry_prices = [t['entry_price'] for t in short_entries]
        ax1.scatter(entry_times, entry_prices, marker='v', color='#e74c3c', s=120,
                   label=f'Short Entries ({len(short_entries)})', zorder=5, edgecolors='darkred', linewidths=1.5)

    # Plot exits
    closed_trades = [t for t in trades if t['exit_time'] is not None]
    if closed_trades:
        exit_times = [t['exit_time'] for t in closed_trades]
        exit_prices = [t['exit_price'] for t in closed_trades]
        colors = ['#27ae60' if t['pnl'] > 0 else '#e74c3c' for t in closed_trades]
        ax1.scatter(exit_times, exit_prices, marker='x', color=colors, s=80,
                   label=f'Exits ({len(closed_trades)})', zorder=5, linewidths=2)

    ax1.set_ylabel('Price (USDT)', fontsize=11, fontweight='bold')
    ax1.set_title('BTCUSDT Price - Volume Imbalance Strategy Entries & Exits', fontsize=13, fontweight='bold')
    ax1.legend(loc='upper left', fontsize=10)
    ax1.grid(True, alpha=0.3)
    ax1.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'${x:,.0f}'))

    # Plot 2: Volume Imbalance indicator
    ax2 = fig.add_subplot(gs[1], sharex=ax1)
    ax2.plot(df.index, df['vi'], color='#3498db', linewidth=1.5, label='Volume Imbalance')
    ax2.axhline(y=0, color='gray', linestyle='--', linewidth=0.8, alpha=0.5)
    ax2.axhline(y=VI_THRESHOLD_DEFAULT, color='#27ae60', linestyle='--', linewidth=1.5, alpha=0.6, label='Long Threshold')
    ax2.axhline(y=-VI_THRESHOLD_DEFAULT, color='#e74c3c', linestyle='--', linewidth=1.5, alpha=0.6, label='Short Threshold')
    ax2.fill_between(df.index, 0, df['vi'], where=(df['vi'] > 0), color='#27ae60', alpha=0.15)
    ax2.fill_between(df.index, 0, df['vi'], where=(df['vi'] < 0), color='#e74c3c', alpha=0.15)

    ax2.set_ylabel('Volume Imbalance', fontsize=11, fontweight='bold')
    ax2.set_title(f'Volume Imbalance Indicator (Period: {VI_PERIOD_DEFAULT}, Threshold: ±{VI_THRESHOLD_DEFAULT:.2f})', fontsize=12, fontweight='bold')
    ax2.legend(loc='upper left', fontsize=9)
    ax2.grid(True, alpha=0.3)
    ax2.set_ylim([-1.1, 1.1])

    # Plot 3: Equity Curve
    ax3 = fig.add_subplot(gs[2], sharex=ax1)
    ax3.plot(equity_curve.index, equity_curve['equity'], color='#f39c12', linewidth=2, label='Portfolio Value')
    ax3.axhline(y=DEFAULT_INITIAL_CAPITAL_USDT, color='#95a5a6', linestyle='--', linewidth=1.5, label='Initial Capital')

    # Shade drawdown areas
    cummax = equity_curve['equity'].cummax()
    ax3.fill_between(equity_curve.index, equity_curve['equity'], cummax,
                     where=(equity_curve['equity'] < cummax), color='#e74c3c', alpha=0.2, label='Drawdown')

    # Calculate statistics
    final_equity = equity_curve['equity'].iloc[-1]
    total_return = (final_equity - DEFAULT_INITIAL_CAPITAL_USDT) / DEFAULT_INITIAL_CAPITAL_USDT
    max_drawdown = (equity_curve['equity'].min() - equity_curve['equity'].max()) / equity_curve['equity'].max()

    closed_trades = [t for t in trades if t['exit_time'] is not None]
    winning_trades = sum(1 for t in closed_trades if t['pnl'] > 0)
    total_trades = len(closed_trades)
    win_rate = winning_trades / total_trades if total_trades > 0 else 0

    gross_profit = sum(t['pnl'] for t in closed_trades if t['pnl'] > 0)
    gross_loss = abs(sum(t['pnl'] for t in closed_trades if t['pnl'] < 0))
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0

    ax3.set_ylabel('Portfolio Value (USDT)', fontsize=11, fontweight='bold')
    ax3.set_xlabel('Time', fontsize=11, fontweight='bold')
    ax3.set_title(f'Equity Curve - Final: ${final_equity:,.2f} ({total_return*100:+.2f}%) | Max DD: {max_drawdown:.2%} | Trades: {total_trades} | Win Rate: {win_rate:.1%} | PF: {profit_factor:.2f}',
                  fontsize=12, fontweight='bold')
    ax3.legend(loc='upper left', fontsize=9)
    ax3.grid(True, alpha=0.3)
    ax3.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'${x:,.0f}'))

    fig.suptitle('Volume Imbalance Strategy - 1 Month Backtest', fontsize=15, fontweight='bold', y=0.995)

    return fig

if __name__ == "__main__":
    # Fetch data using consolidated module
    fetcher = BinanceFetcher()
    df = fetcher.fetch_months(symbol=DEFAULT_SYMBOL, interval=DEFAULT_INTERVAL, months_back=1)

    if len(df) > 100:
        # Calculate VI using consolidated module
        vi_calc = VolumeImbalance(period=VI_PERIOD_DEFAULT)
        df['vi'] = vi_calc.calculate(df)

        capital = DEFAULT_INITIAL_CAPITAL_USDT
        position = None
        entry_price = None
        entry_time = None
        stop_loss = None
        take_profit = None
        highest_since_entry = None
        lowest_since_entry = None

        trades = []
        equity_curve = []

        print(f"\n{'='*60}")
        print(f"BACKTEST: 1 Month Volume Imbalance Strategy")
        print(f"{'='*60}")
        print(f"VI Period: {VI_PERIOD_DEFAULT}, Threshold: ±{VI_THRESHOLD_DEFAULT:.2f}")
        print(f"Initial Capital: ${capital:,.0f}")
        print(f"Stop Loss: {DEFAULT_STOP_LOSS_PCT*100:.1f}%, Take Profit: {DEFAULT_TAKE_PROFIT_PCT*100:.1f}%, Trailing Stop: {DEFAULT_TRAILING_STOP_PCT*100:.1f}%")
        print(f"{'='*60}\n")

        for i in range(VI_PERIOD_DEFAULT, len(df)):
            current_time = df.index[i]
            close = df['close'].iloc[i]
            high = df['high'].iloc[i]
            low = df['low'].iloc[i]
            vi = df['vi'].iloc[i]

            if pd.isna(vi):
                continue

            if position is None:
                if vi > VI_THRESHOLD_DEFAULT:
                    position = 'long'
                    entry_price = close
                    entry_time = current_time
                    highest_since_entry = close
                    stop_loss = entry_price * (1 - DEFAULT_STOP_LOSS_PCT)
                    take_profit = entry_price * (1 + DEFAULT_TAKE_PROFIT_PCT)
                    trades.append({
                        'entry_time': current_time,
                        'entry_price': close,
                        'type': 'LONG',
                        'vi_at_entry': vi,
                        'exit_time': None,
                        'exit_price': None,
                        'pnl': None,
                        'reason': None
                    })
                    print(f"LONG  | {current_time.strftime('%m/%d %H:%M')} | ${close:,.2f} | VI: {vi:+.2f}")

                elif vi < -VI_THRESHOLD_DEFAULT:
                    position = 'short'
                    entry_price = close
                    entry_time = current_time
                    lowest_since_entry = close
                    stop_loss = entry_price * (1 + DEFAULT_STOP_LOSS_PCT)
                    take_profit = entry_price * (1 - DEFAULT_TAKE_PROFIT_PCT)
                    trades.append({
                        'entry_time': current_time,
                        'entry_price': close,
                        'type': 'SHORT',
                        'vi_at_entry': vi,
                        'exit_time': None,
                        'exit_price': None,
                        'pnl': None,
                        'reason': None
                    })
                    print(f"SHORT | {current_time.strftime('%m/%d %H:%M')} | ${close:,.2f} | VI: {vi:+.2f}")

            elif position == 'long':
                highest_since_entry = max(highest_since_entry, high)
                trailing_stop = highest_since_entry * (1 - DEFAULT_TRAILING_STOP_PCT)
                stop_loss = max(stop_loss, trailing_stop)

                exit_triggered = False
                exit_price = None
                exit_reason = None

                if low <= stop_loss:
                    exit_price = stop_loss
                    exit_reason = 'SL'
                    exit_triggered = True
                elif high >= take_profit:
                    exit_price = take_profit
                    exit_reason = 'TP'
                    exit_triggered = True
                elif vi < -VI_THRESHOLD_DEFAULT:
                    exit_price = close
                    exit_reason = 'REV'
                    exit_triggered = True

                if exit_triggered:
                    pnl = (exit_price - entry_price) * DEFAULT_LOT_SIZE_BTC
                    capital += pnl
                    trades[-1].update({
                        'exit_time': current_time,
                        'exit_price': exit_price,
                        'pnl': pnl,
                        'reason': exit_reason
                    })
                    print(f"EXIT LONG | {current_time.strftime('%m/%d %H:%M')} | ${exit_price:,.2f} | {exit_reason} | PnL: ${pnl:+.2f}")
                    position = None

            elif position == 'short':
                lowest_since_entry = min(lowest_since_entry, low)
                trailing_stop = lowest_since_entry * (1 + DEFAULT_TRAILING_STOP_PCT)
                stop_loss = min(stop_loss, trailing_stop)

                exit_triggered = False
                exit_price = None
                exit_reason = None

                if high >= stop_loss:
                    exit_price = stop_loss
                    exit_reason = 'SL'
                    exit_triggered = True
                elif low <= take_profit:
                    exit_price = take_profit
                    exit_reason = 'TP'
                    exit_triggered = True
                elif vi > VI_THRESHOLD_DEFAULT:
                    exit_price = close
                    exit_reason = 'REV'
                    exit_triggered = True

                if exit_triggered:
                    pnl = (entry_price - exit_price) * DEFAULT_LOT_SIZE_BTC
                    capital += pnl
                    trades[-1].update({
                        'exit_time': current_time,
                        'exit_price': exit_price,
                        'pnl': pnl,
                        'reason': exit_reason
                    })
                    print(f"EXIT SHORT| {current_time.strftime('%m/%d %H:%M')} | ${exit_price:,.2f} | {exit_reason} | PnL: ${pnl:+.2f}")
                    position = None

            equity = capital
            if position == 'long' and entry_price:
                equity += (close - entry_price) * DEFAULT_LOT_SIZE_BTC
            elif position == 'short' and entry_price:
                equity += (entry_price - close) * DEFAULT_LOT_SIZE_BTC

            equity_curve.append({'time': current_time, 'equity': equity})

        equity = pd.DataFrame(equity_curve).set_index('time')

        print(f"\n{'='*60}")
        print(f"FINAL RESULTS")
        print(f"{'='*60}")

        closed_trades = [t for t in trades if t['exit_time'] is not None]
        total_trades = len(closed_trades)
        winning_trades = sum(1 for t in closed_trades if t['pnl'] > 0)
        win_rate = winning_trades / total_trades if total_trades > 0 else 0

        gross_profit = sum(t['pnl'] for t in closed_trades if t['pnl'] > 0)
        gross_loss = abs(sum(t['pnl'] for t in closed_trades if t['pnl'] < 0))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0

        long_trades = [t for t in trades if t['type'] == 'LONG' and t['exit_time']]
        short_trades = [t for t in trades if t['type'] == 'SHORT' and t['exit_time']]

        print(f"Total Trades: {total_trades}")
        print(f"Win Rate: {win_rate:.1%}")
        print(f"Final Capital: ${capital:,.2f}")
        print(f"Return: {(capital - DEFAULT_INITIAL_CAPITAL_USDT) / DEFAULT_INITIAL_CAPITAL_USDT * 100:+.2f}%")
        print(f"Profit Factor: {profit_factor:.2f}")
        print(f"Long Trades: {len(long_trades)}")
        print(f"Short Trades: {len(short_trades)}")

        exit_breakdown = {}
        for t in closed_trades:
            reason = t['reason']
            exit_breakdown[reason] = exit_breakdown.get(reason, 0) + 1

        print(f"\nExit Reasons:")
        for reason, count in exit_breakdown.items():
            print(f"  {reason}: {count}")

        fig = create_visualization(df, equity, trades)
        plt.savefig('one_month_backtest.png', dpi=150, bbox_inches='tight', facecolor='white')
        print(f"\nChart saved: one_month_backtest.png")
