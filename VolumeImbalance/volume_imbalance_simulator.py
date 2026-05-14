#!/usr/bin/env python3
"""
Volume Imbalance Strategy Simulator
Based on the Medium_Volume_Imbalance.pdf paper

Strategy:
- Calculate Volume Imbalance (VI) over a period
- Long when VI > threshold (buying pressure dominant)
- Short when VI < -threshold (selling pressure dominant)
- Use trailing stop loss
- Fixed lot size money management

Refactored to use consolidated SLATE modules - eliminates code duplication
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path

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

# Backward compatibility aliases - map old function names to new modules
def fetch_binance_data(symbol="BTCUSDT", interval="1h", days=180):
    """
    Fetch REAL data from Binance.

    Parameters:
    - symbol: Trading pair (default: BTCUSDT)
    - interval: Candle timeframe (default: 1h)
    - days: Number of days of history (default: 180 for ~6 months)

    Returns:
    - DataFrame with OHLCV data
    """
    from datetime import datetime, timedelta

    end_time = datetime.now()
    start_time = end_time - timedelta(days=days)

    fetcher = BinanceFetcher()
    df = fetcher.fetch_klines(symbol=symbol, interval=interval,
                              start_date=start_time, end_date=end_time)

    print(f"✓ Loaded {len(df)} candles from {df.index[0]} to {df.index[-1]}")
    print(f"Price range: ${df['close'].min():,.2f} - ${df['close'].max():,.2f}")

    return df

def calculate_volume_imbalance(df, period=12):
    """
    Calculate Volume Imbalance (VI) indicator.

    VI = (Volume of up bars - Volume of down bars) / Total Volume

    Parameters:
    - df: DataFrame with OHLCV data
    - period: Lookback period for VI calculation (default: 12)

    Returns:
    - Series with VI values
    """
    vi_calc = VolumeImbalance(period=period)
    return vi_calc.calculate(df)

def run_volume_imbalance_backtest(df,
                                   vi_period=12,
                                   vi_threshold=0.30,
                                   initial_capital=10000,
                                   lot_size=0.01,
                                   stop_loss_pct=0.02,
                                   take_profit_pct=0.04,
                                   trailing_stop_pct=0.015):
    """
    Run Volume Imbalance strategy backtest.

    Parameters:
    - df: DataFrame with OHLCV data
    - vi_period: VI calculation period (default: 12)
    - vi_threshold: VI threshold for entries (default: 0.30)
    - initial_capital: Starting capital in USDT (default: 10000)
    - lot_size: Fixed lot size in BTC (default: 0.01)
    - stop_loss_pct: Stop loss percentage (default: 2%)
    - take_profit_pct: Take profit percentage (default: 4%)
    - trailing_stop_pct: Trailing stop percentage (default: 1.5%)

    Returns:
    - DataFrame with equity curve
    - List of trades
    """

    # Calculate Volume Imbalance
    df['vi'] = calculate_volume_imbalance(df, period=vi_period)

    # Initialize tracking
    capital = initial_capital
    position = None  # None, 'long', or 'short'
    entry_price = None
    entry_time = None
    stop_loss_price = None
    take_profit_price = None
    highest_price_since_entry = None
    lowest_price_since_entry = None

    trades = []
    equity_curve = []

    print(f"\n{'='*60}")
    print(f"VOLUME IMBALANCE BACKTEST PARAMETERS")
    print(f"{'='*60}")
    print(f"VI Period: {vi_period}")
    print(f"VI Threshold: {vi_threshold:.2f}")
    print(f"Initial Capital: ${initial_capital:,.2f}")
    print(f"Lot Size: {lot_size} BTC")
    print(f"Stop Loss: {stop_loss_pct*100:.1f}%")
    print(f"Take Profit: {take_profit_pct*100:.1f}%")
    print(f"Trailing Stop: {trailing_stop_pct*100:.1f}%")
    print(f"{'='*60}\n")

    for i in range(vi_period, len(df)):
        current_time = df.index[i]
        close = df['close'].iloc[i]
        high = df['high'].iloc[i]
        low = df['low'].iloc[i]
        vi = df['vi'].iloc[i]

        # Skip if VI is NaN
        if pd.isna(vi):
            equity_curve.append({
                'time': current_time,
                'equity': capital,
                'position': position
            })
            continue

        # Check for entry signals if no position
        if position is None:
            # Long entry: VI > threshold (buying pressure)
            if vi > vi_threshold:
                position = 'long'
                entry_price = close
                entry_time = current_time
                highest_price_since_entry = close

                stop_loss_price = entry_price * (1 - stop_loss_pct)
                take_profit_price = entry_price * (1 + take_profit_pct)

            # Short entry: VI < -threshold (selling pressure)
            elif vi < -vi_threshold:
                position = 'short'
                entry_price = close
                entry_time = current_time
                lowest_price_since_entry = close

                stop_loss_price = entry_price * (1 + stop_loss_pct)
                take_profit_price = entry_price * (1 - take_profit_pct)

        # Check exit conditions if in position
        elif position == 'long':
            # Update highest price for trailing stop
            highest_price_since_entry = max(highest_price_since_entry, high)

            # Update trailing stop
            trailing_stop = highest_price_since_entry * (1 - trailing_stop_pct)
            stop_loss_price = max(stop_loss_price, trailing_stop)

            # Check stop loss
            if low <= stop_loss_price:
                exit_price = stop_loss_price
                pnl = (exit_price - entry_price) * lot_size
                capital += pnl

                trades.append({
                    'entry_time': entry_time,
                    'exit_time': current_time,
                    'type': 'LONG',
                    'entry_price': entry_price,
                    'exit_price': exit_price,
                    'pnl': pnl,
                    'exit_reason': 'stop_loss'
                })

                position = None
                entry_price = None

            # Check take profit
            elif high >= take_profit_price:
                exit_price = take_profit_price
                pnl = (exit_price - entry_price) * lot_size
                capital += pnl

                trades.append({
                    'entry_time': entry_time,
                    'exit_time': current_time,
                    'type': 'LONG',
                    'entry_price': entry_price,
                    'exit_price': exit_price,
                    'pnl': pnl,
                    'exit_reason': 'take_profit'
                })

                position = None
                entry_price = None

            # Check reverse signal
            elif vi < -vi_threshold:
                exit_price = close
                pnl = (exit_price - entry_price) * lot_size
                capital += pnl

                trades.append({
                    'entry_time': entry_time,
                    'exit_time': current_time,
                    'type': 'LONG',
                    'entry_price': entry_price,
                    'exit_price': exit_price,
                    'pnl': pnl,
                    'exit_reason': 'signal_reverse'
                })

                position = None
                entry_price = None

        elif position == 'short':
            # Update lowest price for trailing stop
            lowest_price_since_entry = min(lowest_price_since_entry, low)

            # Update trailing stop
            trailing_stop = lowest_price_since_entry * (1 + trailing_stop_pct)
            stop_loss_price = min(stop_loss_price, trailing_stop)

            # Check stop loss
            if high >= stop_loss_price:
                exit_price = stop_loss_price
                pnl = (entry_price - exit_price) * lot_size
                capital += pnl

                trades.append({
                    'entry_time': entry_time,
                    'exit_time': current_time,
                    'type': 'SHORT',
                    'entry_price': entry_price,
                    'exit_price': exit_price,
                    'pnl': pnl,
                    'exit_reason': 'stop_loss'
                })

                position = None
                entry_price = None

            # Check take profit
            elif low <= take_profit_price:
                exit_price = take_profit
                pnl = (entry_price - exit_price) * lot_size
                capital += pnl

                trades.append({
                    'entry_time': entry_time,
                    'exit_time': current_time,
                    'type': 'SHORT',
                    'entry_price': entry_price,
                    'exit_price': exit_price,
                    'pnl': pnl,
                    'exit_reason': 'take_profit'
                })

                position = None
                entry_price = None

            # Check reverse signal
            elif vi > vi_threshold:
                exit_price = close
                pnl = (entry_price - exit_price) * lot_size
                capital += pnl

                trades.append({
                    'entry_time': entry_time,
                    'exit_time': current_time,
                    'type': 'SHORT',
                    'entry_price': entry_price,
                    'exit_price': exit_price,
                    'pnl': pnl,
                    'exit_reason': 'signal_reverse'
                })

                position = None
                entry_price = None

        # Calculate unrealized PnL for equity curve
        equity = capital
        if position == 'long' and entry_price:
            equity += (close - entry_price) * lot_size
        elif position == 'short' and entry_price:
            equity += (entry_price - close) * lot_size

        equity_curve.append({
            'time': current_time,
            'equity': equity,
            'position': position
        })

    return pd.DataFrame(equity_curve).set_index('time'), trades

def create_visualization(df, equity_curve, trades, output_dir=Path("VolumeImbalance")):
    """
    Create visualization similar to Figure 4 from the paper.

    Parameters:
    - df: Original price data
    - equity_curve: Equity curve DataFrame
    - trades: List of trades
    - output_dir: Output directory for plots
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    fig = plt.figure(figsize=(14, 10))

    # Create grid spec
    gs = fig.add_gridspec(3, 1, height_ratios=[2, 1, 1], hspace=0.3)

    # Plot 1: Price chart with trades
    ax1 = fig.add_subplot(gs[0])
    ax1.plot(df.index, df['close'], label='BTCUSDT Price', color='#2c3e50', linewidth=1, alpha=0.7)

    # Plot trade entries and exits
    long_trades = [t for t in trades if t['type'] == 'LONG']
    short_trades = [t for t in trades if t['type'] == 'SHORT']

    if long_trades:
        entry_times = [t['entry_time'] for t in long_trades]
        entry_prices = [t['entry_price'] for t in long_trades]
        ax1.scatter(entry_times, entry_prices, marker='^', color='#27ae60', s=80,
                   label=f'Long Entries ({len(long_trades)})', zorder=5, alpha=0.8)

    if short_trades:
        entry_times = [t['entry_time'] for t in short_trades]
        entry_prices = [t['entry_price'] for t in short_trades]
        ax1.scatter(entry_times, entry_prices, marker='v', color='#e74c3c', s=80,
                   label=f'Short Entries ({len(short_trades)})', zorder=5, alpha=0.8)

    ax1.set_ylabel('Price (USDT)', fontsize=11, fontweight='bold')
    ax1.set_title('BTCUSDT Price with Volume Imbalance Trade Entries',
                  fontsize=12, fontweight='bold')
    ax1.legend(loc='upper left', fontsize=9)
    ax1.grid(True, alpha=0.3)
    ax1.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'${x:,.0f}'))

    # Plot 2: Volume Imbalance indicator
    ax2 = fig.add_subplot(gs[1], sharex=ax1)
    ax2.plot(df.index, df['vi'], label='Volume Imbalance', color='#3498db', linewidth=1.5)
    ax2.axhline(y=0, color='gray', linestyle='--', linewidth=0.8, alpha=0.5)
    ax2.axhline(y=0.30, color='#27ae60', linestyle='--', linewidth=0.8, alpha=0.5, label='Long Threshold')
    ax2.axhline(y=-0.30, color='#e74c3c', linestyle='--', linewidth=0.8, alpha=0.5, label='Short Threshold')
    ax2.fill_between(df.index, 0, df['vi'], where=(df['vi'] > 0), color='#27ae60', alpha=0.2)
    ax2.fill_between(df.index, 0, df['vi'], where=(df['vi'] < 0), color='#e74c3c', alpha=0.2)

    ax2.set_ylabel('Volume Imbalance', fontsize=11, fontweight='bold')
    ax2.set_title('Volume Imbalance Indicator (VI Period: 12, Threshold: ±0.30)',
                  fontsize=12, fontweight='bold')
    ax2.legend(loc='upper left', fontsize=9)
    ax2.grid(True, alpha=0.3)
    ax2.set_ylim([-1.1, 1.1])

    # Plot 3: Equity Curve
    ax3 = fig.add_subplot(gs[2], sharex=ax1)
    ax3.plot(equity_curve.index, equity_curve['equity'],
             label='Portfolio Value', color='#f39c12', linewidth=2)
    ax3.axhline(y=10000, color='#95a5a6', linestyle='--', linewidth=1.5,
                label='Initial Capital ($10,000)')

    # Shade drawdown areas
    cummax = equity_curve['equity'].cummax()
    ax3.fill_between(equity_curve.index, equity_curve['equity'], cummax,
                     where=(equity_curve['equity'] < cummax), color='#e74c3c', alpha=0.2, label='Drawdown')

    # Calculate final statistics
    final_equity = equity_curve['equity'].iloc[-1]
    total_return = (final_equity - 10000) / 10000
    max_drawdown = (equity_curve['equity'].min() - equity_curve['equity'].max()) / equity_curve['equity'].max()

    # Calculate trade statistics
    winning_trades = sum(1 for t in trades if t['pnl'] > 0)
    total_trades = len(trades)
    win_rate = winning_trades / total_trades if total_trades > 0 else 0

    gross_profit = sum(t['pnl'] for t in trades if t['pnl'] > 0)
    gross_loss = abs(sum(t['pnl'] for t in trades if t['pnl'] < 0))
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0

    ax3.set_ylabel('Portfolio Value (USDT)', fontsize=11, fontweight='bold')
    ax3.set_xlabel('Time', fontsize=11, fontweight='bold')
    ax3.set_title(f'Equity Curve - Final: ${final_equity:,.2f} ({total_return:+.2%}) | Max DD: {max_drawdown:.2%} | Trades: {total_trades} | Win Rate: {win_rate:.1%} | PF: {profit_factor:.2f}',
                  fontsize=12, fontweight='bold')
    ax3.legend(loc='upper left', fontsize=9)
    ax3.grid(True, alpha=0.3)
    ax3.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'${x:,.0f}'))

    # Main title
    fig.suptitle('Volume Imbalance Strategy Backtest (BTCUSDT 1H)\nReproducing Figure 4 - No Optimization Applied',
                 fontsize=14, fontweight='bold', y=0.995)

    plt.tight_layout()

    # Save figure
    output_path = output_dir / 'volume_imbalance_equity_curve.png'
    plt.savefig(output_path, dpi=150, bbox_inches='tight', facecolor='white')
    print(f"\n✓ Visualization saved to: {output_path}")

    return output_path

def save_trade_statistics(trades, equity_curve, output_dir=Path("VolumeImbalance")):
    """
    Save detailed trade statistics to file.

    Parameters:
    - trades: List of trades
    - equity_curve: Equity curve DataFrame
    - output_dir: Output directory
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    stats_path = output_dir / 'volume_imbalance_statistics.txt'

    with open(stats_path, 'w') as f:
        f.write(f"{'='*60}\n")
        f.write("VOLUME IMBALANCE STRATEGY BACKTEST RESULTS\n")
        f.write(f"{'='*60}\n\n")

        # Calculate statistics
        final_equity = equity_curve['equity'].iloc[-1]
        total_return = (final_equity - 10000) / 10000
        max_drawdown = (equity_curve['equity'].min() - equity_curve['equity'].max()) / equity_curve['equity'].max()

        winning_trades = sum(1 for t in trades if t['pnl'] > 0)
        total_trades = len(trades)
        win_rate = winning_trades / total_trades if total_trades > 0 else 0

        gross_profit = sum(t['pnl'] for t in trades if t['pnl'] > 0)
        gross_loss = abs(sum(t['pnl'] for t in trades if t['pnl'] < 0))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0

        avg_win = gross_profit / winning_trades if winning_trades > 0 else 0
        avg_loss = gross_loss / (total_trades - winning_trades) if (total_trades - winning_trades) > 0 else 0

        long_trades = [t for t in trades if t['type'] == 'LONG']
        short_trades = [t for t in trades if t['type'] == 'SHORT']

        long_wins = sum(1 for t in long_trades if t['pnl'] > 0)
        short_wins = sum(1 for t in short_trades if t['pnl'] > 0)

        f.write(f"PERFORMANCE METRICS\n")
        f.write(f"{'='*60}\n")
        f.write(f"Initial Capital: $10,000.00\n")
        f.write(f"Final Equity: ${final_equity:,.2f}\n")
        f.write(f"Total Return: {total_return:+.2%}\n")
        f.write(f"Total Profit: ${final_equity - 10000:+,.2f}\n")
        f.write(f"Max Drawdown: {max_drawdown:.2%}\n\n")

        f.write(f"TRADE STATISTICS\n")
        f.write(f"{'='*60}\n")
        f.write(f"Total Trades: {total_trades}\n")
        f.write(f"Winning Trades: {winning_trades}\n")
        f.write(f"Losing Trades: {total_trades - winning_trades}\n")
        f.write(f"Win Rate: {win_rate:.2%}\n")
        f.write(f"Profit Factor: {profit_factor:.2f}\n")
        f.write(f"Average Win: ${avg_win:.2f}\n")
        f.write(f"Average Loss: ${avg_loss:.2f}\n")
        f.write(f"Payoff Ratio: {avg_win / avg_loss if avg_loss > 0 else 0:.2f}\n\n")

        f.write(f"LONG vs SHORT PERFORMANCE\n")
        f.write(f"{'='*60}\n")
        f.write(f"Long Trades: {len(long_trades)}\n")
        f.write(f"Long Win Rate: {long_wins / len(long_trades) if len(long_trades) > 0 else 0:.2%}\n")
        f.write(f"Short Trades: {len(short_trades)}\n")
        f.write(f"Short Win Rate: {short_wins / len(short_trades) if len(short_trades) > 0 else 0:.2%}\n\n")

        f.write(f"EXIT REASON BREAKDOWN\n")
        f.write(f"{'='*60}\n")
        for reason in ['stop_loss', 'take_profit', 'signal_reverse']:
            reason_trades = [t for t in trades if t['exit_reason'] == reason]
            f.write(f"{reason.replace('_', ' ').title()}: {len(reason_trades)}\n")

    print(f"✓ Statistics saved to: {stats_path}")

    return stats_path

# Main execution
if __name__ == "__main__":
    print("="*60)
    print("VOLUME IMBALANCE STRATEGY SIMULATOR")
    print("Reproducing Figure 4 from Medium_Volume_Imbalance.pdf")
    print("="*60)

    # Fetch real data from Binance (using consolidated module)
    print("\nFetching REAL data from Binance...")
    df = fetch_binance_data(symbol="BTCUSDT", interval="1h", days=180)

    if df is not None and len(df) > 100:
        # Run backtest with default parameters (no optimization)
        print("\nRunning Volume Imbalance backtest...")
        equity_curve, trades = run_volume_imbalance_backtest(
            df,
            vi_period=12,           # Default period from paper
            vi_threshold=0.30,       # Default threshold from paper
            initial_capital=10000,
            lot_size=0.01,
            stop_loss_pct=0.02,
            take_profit_pct=0.04,
            trailing_stop_pct=0.015
        )

        # Create visualization
        print("\nCreating visualization...")
        create_visualization(df, equity_curve, trades)

        # Save statistics
        print("\nSaving trade statistics...")
        save_trade_statistics(trades, equity_curve)

        print(f"\n{'='*60}")
        print("SIMULATION COMPLETE")
        print(f"{'='*60}")
        print(f"All results saved to: VolumeImbalance/")
        print(f"  - volume_imbalance_equity_curve.png")
        print(f"  - volume_imbalance_statistics.txt")
        print(f"{'='*60}")
    else:
        print("Error: Could not fetch sufficient data")
