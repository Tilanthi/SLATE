#!/usr/bin/env python3
"""
Volume Imbalance Strategy - Daily Timeframe Analysis

Testing the hypothesis that daily timeframes (where SLATE found 57% success rate)
will perform better than hourly for Volume Imbalance strategy.
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
import requests
from pathlib import Path
import sys
from itertools import product

sys.path.insert(0, str(Path(__file__).parent))

# Use consolidated SLATE modules to eliminate code duplication
sys.path.insert(0, str(Path(__file__).parent.parent))
from slate_core.data.binance_fetcher import BinanceFetcher
from slate_core.indicators.volume_imbalance import VolumeImbalance

def fetch_binance_daily_data(days=365):
    """Fetch REAL daily data from Binance (using consolidated module)."""
    print(f"Fetching {days} days of DAILY data from Binance for BTCUSDT...")

    end_time = datetime.now()
    start_time = end_time - timedelta(days=days)

    fetcher = BinanceFetcher()
    df = fetcher.fetch_klines(symbol="BTCUSDT", interval="1d",
                              start_date=start_time, end_time=end_time)

    print(f"✓ Loaded {len(df)} daily candles from {df.index[0]} to {df.index[-1]}")
    print(f"Price range: ${df['close'].min():,.2f} - ${df['close'].max():,.2f}")

    return df

def calculate_vi(df, period):
    """Calculate Volume Imbalance (using consolidated module)."""
    vi_calc = VolumeImbalance(period=period)
    return vi_calc.calculate(df)

def run_backtest_daily(df, vi_period=12, vi_threshold=0.30,
                       sl_pct=0.02, tp_pct=0.04, trail_pct=0.015):
    """Run backtest on daily data."""

    df_temp = df.copy()
    df_temp['vi'] = calculate_vi(df_temp, vi_period)

    capital = 10000
    lot_size = 0.01
    position = None
    entry_price = None
    sl_price = None
    tp_price = None
    highest = None
    lowest = None

    trades = []
    equity = []

    for i in range(vi_period, len(df_temp)):
        close = df_temp['close'].iloc[i]
        high = df_temp['high'].iloc[i]
        low = df_temp['low'].iloc[i]
        vi = df_temp['vi'].iloc[i]

        if pd.isna(vi):
            equity.append(capital)
            continue

        # Entry
        if position is None:
            if vi > vi_threshold:
                position = 'long'
                entry_price = close
                highest = close
                sl_price = entry_price * (1 - sl_pct)
                tp_price = entry_price * (1 + tp_pct)
            elif vi < -vi_threshold:
                position = 'short'
                entry_price = close
                lowest = close
                sl_price = entry_price * (1 + sl_pct)
                tp_price = entry_price * (1 - tp_pct)

        # Exit
        elif position == 'long':
            highest = max(highest, high)
            trail = highest * (1 - trail_pct)
            sl_price = max(sl_price, trail)

            if low <= sl_price:
                pnl = (sl_price - entry_price) * lot_size
                capital += pnl
                trades.append({'type': 'LONG', 'pnl': pnl, 'exit': 'sl'})
                position = None
            elif high >= tp_price:
                pnl = (tp_price - entry_price) * lot_size
                capital += pnl
                trades.append({'type': 'LONG', 'pnl': pnl, 'exit': 'tp'})
                position = None
            elif vi < -vi_threshold:
                pnl = (close - entry_price) * lot_size
                capital += pnl
                trades.append({'type': 'LONG', 'pnl': pnl, 'exit': 'signal'})
                position = None

        elif position == 'short':
            lowest = min(lowest, low)
            trail = lowest * (1 + trail_pct)
            sl_price = min(sl_price, trail)

            if high >= sl_price:
                pnl = (entry_price - sl_price) * lot_size
                capital += pnl
                trades.append({'type': 'SHORT', 'pnl': pnl, 'exit': 'sl'})
                position = None
            elif low <= tp_price:
                pnl = (entry_price - tp_price) * lot_size
                capital += pnl
                trades.append({'type': 'SHORT', 'pnl': pnl, 'exit': 'tp'})
                position = None
            elif vi > vi_threshold:
                pnl = (entry_price - close) * lot_size
                capital += pnl
                trades.append({'type': 'SHORT', 'pnl': pnl, 'exit': 'signal'})
                position = None

        equity.append(capital)

    return capital, trades, equity

def optimize_daily(df):
    """Optimize parameters on daily timeframe."""

    print("\n" + "="*70)
    print("OPTIMIZING ON DAILY TIMEFRAME")
    print("="*70)

    # Parameter ranges
    vi_periods = [9, 12, 15, 18, 21, 24, 30]
    vi_thresholds = [0.20, 0.25, 0.30, 0.35, 0.40, 0.45, 0.50]
    sls = [0.015, 0.02, 0.025, 0.03, 0.04]  # 1.5-4%
    tps = [0.03, 0.04, 0.05, 0.06, 0.08, 0.10]  # 3-10%
    trails = [0.01, 0.015, 0.02, 0.025, 0.03]

    total = len(vi_periods) * len(vi_thresholds) * len(sls) * len(tps) * len(trails)
    print(f"Testing {total:,} combinations...")

    results = []
    tested = 0
    profitable = 0

    for vp, vt, sl, tp, tr in product(vi_periods, vi_thresholds, sls, tps, trails):
        tested += 1

        if tested % 100 == 0:
            print(f"  Progress: {tested}/{total} ({tested/total*100:.1f}%)")

        try:
            final_cap, trades, _ = run_backtest_daily(df, vp, vt, sl, tp, tr)
            total_return = (final_cap - 10000) / 10000

            # Calculate metrics
            if len(trades) > 0:
                win_rate = sum(1 for t in trades if t['pnl'] > 0) / len(trades)
                gross_profit = sum(t['pnl'] for t in trades if t['pnl'] > 0)
                gross_loss = abs(sum(t['pnl'] for t in trades if t['pnl'] < 0))
                pf = gross_profit / gross_loss if gross_loss > 0 else 0
            else:
                win_rate = 0
                pf = 0

            score = total_return * (1 - abs(total_return) * 2) if total_return > 0 else total_return

            results.append({
                'vi_period': vp,
                'vi_threshold': vt,
                'sl': sl,
                'tp': tp,
                'trail': tr,
                'final_cap': final_cap,
                'return': total_return,
                'win_rate': win_rate,
                'profit_factor': pf,
                'num_trades': len(trades),
                'score': score
            })

            if total_return > 0:
                profitable += 1

        except Exception as e:
            continue

    results_df = pd.DataFrame(results)
    results_df = results_df.sort_values('score', ascending=False)

    print(f"\n✓ Tested {tested:,} combinations")
    print(f"✓ Profitable: {profitable} ({profitable/tested*100:.2f}%)")
    print(f"✓ Best return: {results_df['return'].max()*100:+.2f}%")

    return results_df

def create_comparison_plot(df, original_equity, original_trades,
                            optimized_equity, optimized_trades,
                            best_params, output_dir):
    """Create side-by-side comparison."""

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    fig = plt.figure(figsize=(18, 12))
    gs = fig.add_gridspec(3, 2, hspace=0.3, wspace=0.3)

    # Original - Price with trades
    ax1 = fig.add_subplot(gs[0, 0])
    ax1.plot(df.index, df['close'], color='#2c3e50', linewidth=1.5, label='BTCUSDT')

    long_trades = [t for t in original_trades if t['type'] == 'LONG']
    short_trades = [t for t in original_trades if t['type'] == 'SHORT']

    if long_trades:
        # This is simplified - we'd need entry times for proper plotting
        pass

    ax1.set_title('Original Parameters (Daily) - Price', fontweight='bold', fontsize=12)
    ax1.set_ylabel('Price (USDT)', fontweight='bold')
    ax1.grid(True, alpha=0.3)
    ax1.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'${x:,.0f}'))

    # Original - Equity
    ax2 = fig.add_subplot(gs[1, 0])
    ax2.plot(df.index[len(df)-len(original_equity):], original_equity,
             color='#e74c3c', linewidth=2, label='Portfolio')
    ax2.axhline(y=10000, color='gray', linestyle='--', label='Start')

    orig_return = (original_equity[-1] - 10000) / 10000
    orig_max_dd = (pd.Series(original_equity).cummax() - pd.Series(original_equity)).max() / 10000

    ax2.set_title(f'Original - Return: {orig_return*100:+.2f}%, DD: {orig_max_dd*100:.2f}%',
                  fontweight='bold', fontsize=12)
    ax2.set_ylabel('Portfolio ($)', fontweight='bold')
    ax2.grid(True, alpha=0.3)
    ax2.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'${x:,.0f}'))
    ax2.legend()

    # Original - VI
    ax3 = fig.add_subplot(gs[2, 0])
    vi = calculate_vi(df, 12)
    ax3.plot(df.index, vi, color='#3498db', linewidth=1.5)
    ax3.axhline(y=0.30, color='green', linestyle='--', alpha=0.5, label='Long')
    ax3.axhline(y=-0.30, color='red', linestyle='--', alpha=0.5, label='Short')
    ax3.fill_between(df.index, 0, vi, where=(vi > 0), color='green', alpha=0.1)
    ax3.fill_between(df.index, 0, vi, where=(vi < 0), color='red', alpha=0.1)
    ax3.set_title('Original - Volume Imbalance (Period: 12, Threshold: ±0.30)',
                  fontweight='bold', fontsize=12)
    ax3.set_ylabel('VI', fontweight='bold')
    ax3.set_ylim([-1.1, 1.1])
    ax3.grid(True, alpha=0.3)
    ax3.legend(loc='upper right')

    # Optimized - Price
    ax4 = fig.add_subplot(gs[0, 1])
    ax4.plot(df.index, df['close'], color='#2c3e50', linewidth=1.5, label='BTCUSDT')
    ax4.set_title(f'Optimized Parameters (Daily) - Price\n' +
                  f'VI Period: {int(best_params["vi_period"])}, Th: {best_params["vi_threshold"]:.2f}, ' +
                  f'SL: {best_params["sl"]*100:.1f}%, TP: {best_params["tp"]*100:.1f}%',
                  fontweight='bold', fontsize=12)
    ax4.set_ylabel('Price (USDT)', fontweight='bold')
    ax4.grid(True, alpha=0.3)
    ax4.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'${x:,.0f}'))

    # Optimized - Equity
    ax5 = fig.add_subplot(gs[1, 1])
    ax5.plot(df.index[len(df)-len(optimized_equity):], optimized_equity,
             color='#27ae60', linewidth=2, label='Portfolio')
    ax5.axhline(y=10000, color='gray', linestyle='--', label='Start')

    opt_return = (optimized_equity[-1] - 10000) / 10000
    opt_max_dd = (pd.Series(optimized_equity).cummax() - pd.Series(optimized_equity)).max() / 10000

    ax5.set_title(f'Optimized - Return: {opt_return*100:+.2f}%, DD: {opt_max_dd*100:.2f}%',
                  fontweight='bold', fontsize=12)
    ax5.set_ylabel('Portfolio ($)', fontweight='bold')
    ax5.grid(True, alpha=0.3)
    ax5.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'${x:,.0f}'))
    ax5.legend()

    # Optimized - VI
    ax6 = fig.add_subplot(gs[2, 1])
    vi_opt = calculate_vi(df, int(best_params['vi_period']))
    ax6.plot(df.index, vi_opt, color='#3498db', linewidth=1.5)
    ax6.axhline(y=best_params['vi_threshold'], color='green', linestyle='--', alpha=0.5)
    ax6.axhline(y=-best_params['vi_threshold'], color='red', linestyle='--', alpha=0.5)
    ax6.fill_between(df.index, 0, vi_opt, where=(vi_opt > 0), color='green', alpha=0.1)
    ax6.fill_between(df.index, 0, vi_opt, where=(vi_opt < 0), color='red', alpha=0.1)
    ax6.set_title(f'Optimized - Volume Imbalance (Period: {int(best_params["vi_period"])}, Threshold: ±{best_params["vi_threshold"]:.2f})',
                  fontweight='bold', fontsize=12)
    ax6.set_ylabel('VI', fontweight='bold')
    ax6.set_ylim([-1.1, 1.1])
    ax6.grid(True, alpha=0.3)

    # Main title
    fig.suptitle('Volume Imbalance Strategy: Daily Timeframe Comparison\n' +
                 'Original vs Optimized Parameters (1 Year of Data)',
                 fontsize=14, fontweight='bold')

    plt.savefig(output_dir / 'daily_comparison.png', dpi=150, bbox_inches='tight', facecolor='white')
    print(f"\n✓ Comparison saved to: {output_dir / 'daily_comparison.png'}")

    return output_dir / 'daily_comparison.png'

# Main
if __name__ == "__main__":
    print("="*70)
    print("VOLUME IMBALANCE - DAILY TIMEFRAME ANALYSIS")
    print("Testing hypothesis: Daily timeframes improve performance")
    print("="*70)

    # Fetch daily data
    df = fetch_binance_daily_data(days=365)

    if df is None or len(df) < 100:
        print("Error: Could not fetch data")
        sys.exit(1)

    # Original parameters (from paper)
    print("\n" + "="*70)
    print("RUNNING ORIGINAL PARAMETERS (Daily Timeframe)")
    print("="*70)
    print("VI Period: 12, Threshold: ±0.30, SL: 2%, TP: 4%, Trail: 1.5%")

    orig_cap, orig_trades, orig_equity = run_backtest_daily(
        df, vi_period=12, vi_threshold=0.30,
        sl_pct=0.02, tp_pct=0.04, trail_pct=0.015
    )

    orig_return = (orig_cap - 10000) / 10000
    orig_dd = (pd.Series(orig_equity).cummax() - pd.Series(orig_equity)).max() / 10000
    orig_wr = sum(1 for t in orig_trades if t['pnl'] > 0) / len(orig_trades) if orig_trades else 0

    print(f"\nOriginal Results (Daily):")
    print(f"  Return: {orig_return*100:+.2f}%")
    print(f"  Max DD: {orig_dd*100:.2f}%")
    print(f"  Win Rate: {orig_wr*100:.1f}%")
    print(f"  Trades: {len(orig_trades)}")

    # Optimize
    results_df = optimize_daily(df)

    # Get best parameters
    best = results_df.iloc[0]

    print("\n" + "="*70)
    print("BEST OPTIMIZED PARAMETERS")
    print("="*70)
    print(f"VI Period: {int(best['vi_period'])}")
    print(f"VI Threshold: {best['vi_threshold']:.2f}")
    print(f"Stop Loss: {best['sl']*100:.1f}%")
    print(f"Take Profit: {best['tp']*100:.1f}%")
    print(f"Trailing Stop: {best['trail']*100:.1f}%")
    print(f"\nOptimized Results:")
    print(f"  Return: {best['return']*100:+.2f}%")
    print(f"  Win Rate: {best['win_rate']*100:.1f}%")
    print(f"  Profit Factor: {best['profit_factor']:.2f}")
    print(f"  Trades: {int(best['num_trades'])}")

    # Run optimized backtest for full equity curve
    opt_cap, opt_trades, opt_equity = run_backtest_daily(
        df,
        vi_period=int(best['vi_period']),
        vi_threshold=best['vi_threshold'],
        sl_pct=best['sl'],
        tp_pct=best['tp'],
        trail_pct=best['trail']
    )

    # Create comparison
    create_comparison_plot(df, orig_equity, orig_trades, opt_equity, opt_trades,
                           best, Path("VolumeImbalance"))

    # Save summary
    summary_path = Path("VolumeImbalance/daily_summary.txt")
    with open(summary_path, 'w') as f:
        f.write("="*70 + "\n")
        f.write("VOLUME IMBALANCE - DAILY TIMEFRAME RESULTS\n")
        f.write("="*70 + "\n\n")

        f.write("ORIGINAL PARAMETERS\n")
        f.write("-"*70 + "\n")
        f.write(f"VI Period: 12, Threshold: 0.30, SL: 2%, TP: 4%, Trail: 1.5%\n")
        f.write(f"Return: {orig_return*100:+.2f}%\n")
        f.write(f"Max Drawdown: {orig_dd*100:.2f}%\n")
        f.write(f"Win Rate: {orig_wr*100:.1f}%\n")
        f.write(f"Trades: {len(orig_trades)}\n\n")

        f.write("OPTIMIZED PARAMETERS\n")
        f.write("-"*70 + "\n")
        f.write(f"VI Period: {int(best['vi_period'])}\n")
        f.write(f"VI Threshold: {best['vi_threshold']:.2f}\n")
        f.write(f"Stop Loss: {best['sl']*100:.1f}%\n")
        f.write(f"Take Profit: {best['tp']*100:.1f}%\n")
        f.write(f"Trailing Stop: {best['trail']*100:.1f}%\n")
        f.write(f"Return: {best['return']*100:+.2f}%\n")
        f.write(f"Win Rate: {best['win_rate']*100:.1f}%\n")
        f.write(f"Profit Factor: {best['profit_factor']:.2f}\n")
        f.write(f"Trades: {int(best['num_trades'])}\n\n")

        f.write("IMPROVEMENT\n")
        f.write("-"*70 + "\n")
        f.write(f"Return Improvement: {(best['return'] - orig_return)*100:+.2f}%\n")
        f.write(f"Relative Improvement: {(best['return']/orig_return - 1)*100:+.1f}%\n")

    print(f"\n✓ Summary saved to: {summary_path}")

    # Save full results
    results_df.to_csv(Path("VolumeImbalance/daily_optimization_results.csv"), index=False)
    print(f"✓ Full optimization results saved to: VolumeImbalance/daily_optimization_results.csv")

    print("\n" + "="*70)
    print("DAILY TIMEFRAME ANALYSIS COMPLETE")
    print("="*70)
