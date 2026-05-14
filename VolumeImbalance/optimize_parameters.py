#!/usr/bin/env python3
"""
Volume Imbalance Strategy Parameter Optimizer

Uses Bayesian Optimization and Multi-Objective Search to find optimal parameters.

Based on the optimization ranges from the paper:
- VI_Period: 6-24
- VI_Threshold: 0.15-0.50
- Stop Loss: 1.0%-3.5%
- Take Profit: 2.0%-8.0%
- Trailing Stop: 0.5%-3.0%

Optimization Objectives:
1. Maximize Total Return
2. Minimize Max Drawdown
3. Maximize Sharpe Ratio
4. Maximize Profit Factor
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
import requests
from pathlib import Path
import json
from itertools import product
from concurrent.futures import ProcessPoolExecutor, as_completed
import warnings
warnings.filterwarnings('ignore')

# Use consolidated SLATE modules to eliminate code duplication
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from slate_core.data.binance_fetcher import BinanceFetcher
from slate_core.indicators.volume_imbalance import VolumeImbalance
from slate_core.config.constants import (
    DEFAULT_SYMBOL,
    DEFAULT_INTERVAL,
    DEFAULT_INITIAL_CAPITAL_USDT,
    DEFAULT_LOT_SIZE_BTC,
    MAKER_FEE,
    TAKER_FEE,
    BASE_SLIPPAGE_BPS
)

# Try to import scikit-optimize for Bayesian optimization
try:
    from skopt import gp_minimize
    from skopt.space import Real, Integer
    from skopt.utils import use_named_args
    BAYESIAN_AVAILABLE = True
except ImportError:
    BAYESIAN_AVAILABLE = False
    print("Warning: scikit-optimize not available, using grid search instead")

def fetch_binance_data_cached(symbol="BTCUSDT", interval="1h", days=180):
    """Fetch and cache REAL data from Binance."""
    cache_file = Path(f"VolumeImbalance/cache_{symbol}_{interval}_{days}d.csv")

    if cache_file.exists():
        print(f"Loading cached data from {cache_file}")
        df = pd.read_csv(cache_file, index_col='timestamp', parse_dates=True)
        print(f"✓ Loaded {len(df)} candles from {df.index[0]} to {df.index[-1]}")
        return df

    base_url = "https://api.binance.com/api/v3/klines"
    end_time = int(datetime.now().timestamp() * 1000)
    start_time = int((datetime.now() - timedelta(days=days)).timestamp() * 1000)

    all_klines = []
    current_start = start_time

    print(f"Fetching {days} days of {interval} data from Binance for {symbol}...")

    while current_start < end_time:
        params = {
            "symbol": symbol,
            "interval": interval,
            "startTime": current_start,
            "endTime": end_time,
            "limit": 1000
        }

        try:
            response = requests.get(base_url, params=params, timeout=10)
            response.raise_for_status()
            klines = response.json()

            if not klines:
                break

            all_klines.extend(klines)
            current_start = klines[-1][0] + 1

        except Exception as e:
            print(f"Error fetching data: {e}")
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

    df = df.sort_index()

    # Cache the data
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(cache_file)

    print(f"✓ Loaded {len(df)} candles from {df.index[0]} to {df.index[-1]}")
    return df

def calculate_vi_fast(df, period):
    """Fast Volume Imbalance calculation (using consolidated module)."""
    vi_calc = VolumeImbalance(period=period)
    return vi_calc.calculate_fast(df)

def backtest_single_params(params, df):
    """
    Run a single backtest with given parameters.

    Returns a dict with performance metrics.
    """
    vi_period = int(params['vi_period'])
    vi_threshold = params['vi_threshold']
    stop_loss_pct = params['stop_loss_pct']
    take_profit_pct = params['take_profit_pct']
    trailing_stop_pct = params['trailing_stop_pct']

    initial_capital = 10000
    lot_size = 0.01

    # Calculate VI
    df_temp = df.copy()
    df_temp['vi'] = calculate_vi_fast(df_temp, vi_period)

    # Backtest variables
    capital = initial_capital
    position = None
    entry_price = None
    stop_loss_price = None
    take_profit_price = None
    highest_price = None
    lowest_price = None

    trades = []
    equity_values = []

    for i in range(vi_period, len(df_temp)):
        close = df_temp['close'].iloc[i]
        high = df_temp['high'].iloc[i]
        low = df_temp['low'].iloc[i]
        vi = df_temp['vi'].iloc[i]

        if pd.isna(vi):
            equity_values.append(capital)
            continue

        # Entry logic
        if position is None:
            if vi > vi_threshold:
                position = 'long'
                entry_price = close
                highest_price = close
                stop_loss_price = entry_price * (1 - stop_loss_pct)
                take_profit_price = entry_price * (1 + take_profit_pct)
            elif vi < -vi_threshold:
                position = 'short'
                entry_price = close
                lowest_price = close
                stop_loss_price = entry_price * (1 + stop_loss_pct)
                take_profit_price = entry_price * (1 - take_profit_pct)

        # Exit logic
        elif position == 'long':
            highest_price = max(highest_price, high)
            trailing_stop = highest_price * (1 - trailing_stop_pct)
            stop_loss_price = max(stop_loss_price, trailing_stop)

            if low <= stop_loss_price:
                pnl = (stop_loss_price - entry_price) * lot_size
                capital += pnl
                trades.append(pnl)
                position = None
                entry_price = None
            elif high >= take_profit_price:
                pnl = (take_profit_price - entry_price) * lot_size
                capital += pnl
                trades.append(pnl)
                position = None
                entry_price = None
            elif vi < -vi_threshold:
                pnl = (close - entry_price) * lot_size
                capital += pnl
                trades.append(pnl)
                position = None
                entry_price = None

        elif position == 'short':
            lowest_price = min(lowest_price, low)
            trailing_stop = lowest_price * (1 + trailing_stop_pct)
            stop_loss_price = min(stop_loss_price, trailing_stop)

            if high >= stop_loss_price:
                pnl = (entry_price - stop_loss_price) * lot_size
                capital += pnl
                trades.append(pnl)
                position = None
                entry_price = None
            elif low <= take_profit_price:
                pnl = (entry_price - take_profit_price) * lot_size
                capital += pnl
                trades.append(pnl)
                position = None
                entry_price = None
            elif vi > vi_threshold:
                pnl = (entry_price - close) * lot_size
                capital += pnl
                trades.append(pnl)
                position = None
                entry_price = None

        equity_values.append(capital)

    # Calculate metrics
    final_equity = capital
    total_return = (final_equity - initial_capital) / initial_capital

    if len(equity_values) > 0:
        equity_series = pd.Series(equity_values)
        max_drawdown = (equity_series.cummax() - equity_series).max() / equity_series.cummax().max()
    else:
        max_drawdown = 0

    if len(trades) > 0:
        winning_trades = sum(1 for t in trades if t > 0)
        win_rate = winning_trades / len(trades)
        gross_profit = sum(t for t in trades if t > 0)
        gross_loss = abs(sum(t for t in trades if t < 0))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0

        # Calculate Sharpe ratio (simplified)
        if len(trades) > 1:
            returns = pd.Series(trades)
            sharpe = returns.mean() / returns.std() * np.sqrt(252) if returns.std() > 0 else 0
        else:
            sharpe = 0
    else:
        win_rate = 0
        profit_factor = 0
        sharpe = 0

    # Composite score (higher is better)
    # Penalize heavily for losses
    if total_return <= 0:
        score = total_return  # Negative returns get negative score
    else:
        # Reward returns, penalize drawdown
        score = total_return * (1 - max_drawdown * 2)

    return {
        'vi_period': vi_period,
        'vi_threshold': vi_threshold,
        'stop_loss_pct': stop_loss_pct,
        'take_profit_pct': take_profit_pct,
        'trailing_stop_pct': trailing_stop_pct,
        'final_equity': final_equity,
        'total_return': total_return,
        'max_drawdown': max_drawdown,
        'win_rate': win_rate,
        'profit_factor': profit_factor,
        'sharpe_ratio': sharpe,
        'num_trades': len(trades),
        'score': score
    }

def grid_search_optimization(df, param_ranges, n_workers=4):
    """
    Perform grid search optimization over parameter ranges.

    param_ranges format:
    {
        'vi_period': [6, 9, 12, 15, 18, 21, 24],
        'vi_threshold': [0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.45, 0.50],
        'stop_loss_pct': [0.01, 0.015, 0.02, 0.025, 0.03],
        'take_profit_pct': [0.02, 0.03, 0.04, 0.05, 0.06, 0.07, 0.08],
        'trailing_stop_pct': [0.005, 0.01, 0.015, 0.02, 0.025]
    }
    """
    # Generate all combinations
    keys = list(param_ranges.keys())
    values = list(param_ranges.values())
    all_combinations = list(product(*values))

    print(f"\nGrid Search: {len(all_combinations)} total combinations to test")
    print(f"Using {n_workers} workers for parallel processing")

    results = []
    tested = 0

    with ProcessPoolExecutor(max_workers=n_workers) as executor:
        futures = {}

        for combo in all_combinations:
            params = dict(zip(keys, combo))
            future = executor.submit(backtest_single_params, params, df)
            futures[future] = params

        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            tested += 1

            if tested % 100 == 0:
                print(f"  Progress: {tested}/{len(all_combinations)} ({tested/len(all_combinations)*100:.1f}%)")

    return pd.DataFrame(results)

def smart_grid_search(df, n_workers=4):
    """
    Smart grid search - coarse search first, then refine around best results.

    Two-stage optimization:
    1. Coarse grid over wide ranges
    2. Fine grid around best 10 parameters from stage 1
    """
    print("\n" + "="*60)
    print("SMART GRID SEARCH OPTIMIZATION")
    print("="*60)

    # Stage 1: Coarse search
    print("\n--- STAGE 1: Coarse Grid Search ---")

    coarse_ranges = {
        'vi_period': [6, 9, 12, 15, 18, 21, 24],
        'vi_threshold': [0.20, 0.30, 0.40, 0.50],
        'stop_loss_pct': [0.015, 0.02, 0.025, 0.03],
        'take_profit_pct': [0.03, 0.04, 0.05, 0.06, 0.08],
        'trailing_stop_pct': [0.01, 0.015, 0.02]
    }

    coarse_results = grid_search_optimization(df, coarse_ranges, n_workers)

    # Find best parameters
    coarse_results = coarse_results.sort_values('score', ascending=False)
    top_10 = coarse_results.head(10)

    print("\nTop 10 from Stage 1:")
    print(top_10[['vi_period', 'vi_threshold', 'stop_loss_pct', 'take_profit_pct',
                 'trailing_stop_pct', 'total_return', 'max_drawdown', 'profit_factor']])

    # Stage 2: Fine search around top 10
    print("\n--- STAGE 2: Fine Grid Search around Top 10 ---")

    fine_results = []

    for _, row in top_10.iterrows():
        # Create fine ranges around each top parameter
        fine_ranges = {
            'vi_period': [max(6, row['vi_period'] - 3), row['vi_period'],
                         min(24, row['vi_period'] + 3)],
            'vi_threshold': [max(0.1, row['vi_threshold'] - 0.05), row['vi_threshold'],
                           min(0.6, row['vi_threshold'] + 0.05)],
            'stop_loss_pct': [max(0.01, row['stop_loss_pct'] - 0.005), row['stop_loss_pct'],
                            min(0.04, row['stop_loss_pct'] + 0.005)],
            'take_profit_pct': [max(0.02, row['take_profit_pct'] - 0.01), row['take_profit_pct'],
                              min(0.10, row['take_profit_pct'] + 0.01)],
            'trailing_stop_pct': [max(0.005, row['trailing_stop_pct'] - 0.005), row['trailing_stop_pct'],
                                 min(0.03, row['trailing_stop_pct'] + 0.005)]
        }

        # Remove duplicates
        for key in fine_ranges:
            fine_ranges[key] = list(set(fine_ranges[key]))

        # Run fine search
        stage_results = grid_search_optimization(df, fine_ranges, n_workers)
        fine_results.append(stage_results)

    # Combine all results
    all_results = pd.concat([coarse_results] + fine_results, ignore_index=True)

    # Remove duplicates (keep best score)
    all_results = all_results.sort_values('score', ascending=False)
    all_results = all_results.drop_duplicates(
        subset=['vi_period', 'vi_threshold', 'stop_loss_pct', 'take_profit_pct', 'trailing_stop_pct'],
        keep='first'
    )

    return all_results

def analyze_results(results_df, output_dir=Path("VolumeImbalance")):
    """Analyze and visualize optimization results."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Sort by score
    results_sorted = results_df.sort_values('score', ascending=False)

    # Save full results
    results_path = output_dir / 'optimization_results.csv'
    results_sorted.to_csv(results_path, index=False)
    print(f"\n✓ Full results saved to: {results_path}")

    # Get top 20
    top_20 = results_sorted.head(20)

    print("\n" + "="*60)
    print("TOP 20 PARAMETER COMBINATIONS")
    print("="*60)
    print(top_20[['vi_period', 'vi_threshold', 'stop_loss_pct', 'take_profit_pct',
                 'trailing_stop_pct', 'total_return', 'max_drawdown', 'profit_factor',
                 'sharpe_ratio', 'win_rate', 'num_trades']].to_string(index=False))

    # Create visualizations
    create_optimization_visualizations(results_sorted, top_20, output_dir)

    # Save top parameters summary
    summary_path = output_dir / 'optimization_summary.txt'
    with open(summary_path, 'w') as f:
        f.write("="*60 + "\n")
        f.write("VOLUME IMBALANCE OPTIMIZATION SUMMARY\n")
        f.write("="*60 + "\n\n")

        f.write(f"Total Combinations Tested: {len(results_sorted)}\n")
        f.write(f"Profitable Combinations: {sum(results_sorted['total_return'] > 0)}\n")
        f.write(f"Success Rate: {sum(results_sorted['total_return'] > 0) / len(results_sorted) * 100:.2f}%\n\n")

        f.write("="*60 + "\n")
        f.write("TOP 10 OPTIMIZED PARAMETERS\n")
        f.write("="*60 + "\n\n")

        for i, (_, row) in enumerate(top_10.head(10).iterrows(), 1):
            f.write(f"Rank {i}:\n")
            f.write(f"  VI Period: {row['vi_period']}\n")
            f.write(f"  VI Threshold: {row['vi_threshold']:.2f}\n")
            f.write(f"  Stop Loss: {row['stop_loss_pct']*100:.1f}%\n")
            f.write(f"  Take Profit: {row['take_profit_pct']*100:.1f}%\n")
            f.write(f"  Trailing Stop: {row['trailing_stop_pct']*100:.1f}%\n")
            f.write(f"  Total Return: {row['total_return']*100:+.2f}%\n")
            f.write(f"  Max Drawdown: {row['max_drawdown']*100:.2f}%\n")
            f.write(f"  Profit Factor: {row['profit_factor']:.2f}\n")
            f.write(f"  Sharpe Ratio: {row['sharpe_ratio']:.2f}\n")
            f.write(f"  Win Rate: {row['win_rate']*100:.1f}%\n")
            f.write(f"  Number of Trades: {row['num_trades']}\n")
            f.write(f"  Final Equity: ${row['final_equity']:,.2f}\n\n")

    print(f"✓ Summary saved to: {summary_path}")

    return top_20.iloc[0]  # Return best parameters

def create_optimization_visualizations(results_df, top_20, output_dir):
    """Create comprehensive visualizations of optimization results."""

    fig = plt.figure(figsize=(16, 12))
    gs = fig.add_gridspec(3, 3, hspace=0.35, wspace=0.3)

    # 1. Return vs Drawdown scatter
    ax1 = fig.add_subplot(gs[0, 0])
    scatter = ax1.scatter(results_df['max_drawdown'] * 100,
                         results_df['total_return'] * 100,
                         c=results_df['score'], cmap='RdYlGn',
                         alpha=0.5, s=20)
    ax1.set_xlabel('Max Drawdown (%)', fontweight='bold')
    ax1.set_ylabel('Total Return (%)', fontweight='bold')
    ax1.set_title('Return vs Drawdown\n(Color = Composite Score)',
                  fontweight='bold')
    ax1.grid(True, alpha=0.3)
    ax1.axhline(y=0, color='gray', linestyle='--', linewidth=0.8)
    plt.colorbar(scatter, ax=ax1, label='Score')

    # 2. VI Period distribution
    ax2 = fig.add_subplot(gs[0, 1])
    profitable = results_df[results_df['total_return'] > 0]
    if len(profitable) > 0:
        period_counts = profitable['vi_period'].value_counts().sort_index()
        ax2.bar(period_counts.index, period_counts.values, color='#27ae60', alpha=0.7)
        ax2.set_xlabel('VI Period', fontweight='bold')
        ax2.set_ylabel('Count of Profitable Results', fontweight='bold')
        ax2.set_title('VI Period Distribution (Profitable Only)',
                      fontweight='bold')
        ax2.grid(True, alpha=0.3, axis='y')

    # 3. VI Threshold distribution
    ax3 = fig.add_subplot(gs[0, 2])
    if len(profitable) > 0:
        threshold_counts = profitable['vi_threshold'].value_counts().sort_index()
        ax3.bar(threshold_counts.index, threshold_counts.values,
               color='#3498db', alpha=0.7, width=0.03)
        ax3.set_xlabel('VI Threshold', fontweight='bold')
        ax3.set_ylabel('Count of Profitable Results', fontweight='bold')
        ax3.set_title('VI Threshold Distribution (Profitable Only)',
                      fontweight='bold')
        ax3.grid(True, alpha=0.3, axis='y')

    # 4. Stop Loss vs Return
    ax4 = fig.add_subplot(gs[1, 0])
    if len(results_df) > 0:
        sl_returns = results_df.groupby('stop_loss_pct')['total_return'].mean()
        ax4.plot(sl_returns.index * 100, sl_returns.values * 100,
                marker='o', linewidth=2, markersize=8)
        ax4.set_xlabel('Stop Loss (%)', fontweight='bold')
        ax4.set_ylabel('Avg Return (%)', fontweight='bold')
        ax4.set_title('Average Return by Stop Loss',
                      fontweight='bold')
        ax4.grid(True, alpha=0.3)
        ax4.axhline(y=0, color='gray', linestyle='--', linewidth=0.8)

    # 5. Take Profit vs Return
    ax5 = fig.add_subplot(gs[1, 1])
    if len(results_df) > 0:
        tp_returns = results_df.groupby('take_profit_pct')['total_return'].mean()
        ax5.plot(tp_returns.index * 100, tp_returns.values * 100,
                marker='s', linewidth=2, markersize=8, color='#e74c3c')
        ax5.set_xlabel('Take Profit (%)', fontweight='bold')
        ax5.set_ylabel('Avg Return (%)', fontweight='bold')
        ax5.set_title('Average Return by Take Profit',
                      fontweight='bold')
        ax5.grid(True, alpha=0.3)
        ax5.axhline(y=0, color='gray', linestyle='--', linewidth=0.8)

    # 6. Profit Factor distribution
    ax6 = fig.add_subplot(gs[1, 2])
    pf_data = results_df[results_df['profit_factor'] > 0]['profit_factor']
    if len(pf_data) > 0:
        ax6.hist(pf_data, bins=50, color='#f39c12', alpha=0.7, edgecolor='black')
        ax6.axvline(x=1.0, color='green', linestyle='--', linewidth=2,
                   label='Breakeven (PF=1.0)')
        ax6.set_xlabel('Profit Factor', fontweight='bold')
        ax6.set_ylabel('Frequency', fontweight='bold')
        ax6.set_title('Profit Factor Distribution',
                      fontweight='bold')
        ax6.legend()
        ax6.grid(True, alpha=0.3, axis='y')

    # 7. Top 20 comparison
    ax7 = fig.add_subplot(gs[2, :])
    top_20_sorted = top_20.sort_values('total_return', ascending=False)
    x_pos = range(len(top_20_sorted))

    bars = ax7.bar(x_pos, top_20_sorted['total_return'] * 100,
                   color=['#27ae60' if x > 0 else '#e74c3c'
                         for x in top_20_sorted['total_return']])

    ax7.set_xlabel('Rank', fontweight='bold')
    ax7.set_ylabel('Total Return (%)', fontweight='bold')
    ax7.set_title('Top 20 Parameter Combinations by Return',
                  fontweight='bold')
    ax7.set_xticks(x_pos)
    ax7.set_xticklabels([f"#{i+1}" for i in range(len(top_20_sorted))])
    ax7.grid(True, alpha=0.3, axis='y')
    ax7.axhline(y=0, color='gray', linestyle='--', linewidth=1)

    # Add value labels on bars
    for i, (bar, val) in enumerate(zip(bars, top_20_sorted['total_return'] * 100)):
        ax7.text(bar.get_x() + bar.get_width()/2, bar.get_height() + (0.5 if val > 0 else -0.5),
                f'{val:.1f}%', ha='center', va='bottom' if val > 0 else 'top',
                fontsize=8, fontweight='bold')

    # Main title
    fig.suptitle('Volume Imbalance Parameter Optimization Results\n' +
                 f'Tested: {len(results_df):,} Combinations',
                 fontsize=14, fontweight='bold')

    plt.savefig(output_dir / 'optimization_visualizations.png',
                dpi=150, bbox_inches='tight', facecolor='white')
    print(f"✓ Visualizations saved to: {output_dir / 'optimization_visualizations.png'}")

def run_optimized_backtest(df, best_params, output_dir=Path("VolumeImbalance")):
    """Run full backtest with optimized parameters and create equity curve."""
    from volume_imbalance_simulator import (
        run_volume_imbalance_backtest,
        create_visualization,
        save_trade_statistics
    )

    print("\n" + "="*60)
    print("RUNNING OPTIMIZED BACKTEST")
    print("="*60)
    print(f"\nOptimized Parameters:")
    print(f"  VI Period: {int(best_params['vi_period'])}")
    print(f"  VI Threshold: {best_params['vi_threshold']:.2f}")
    print(f"  Stop Loss: {best_params['stop_loss_pct']*100:.1f}%")
    print(f"  Take Profit: {best_params['take_profit_pct']*100:.1f}%")
    print(f"  Trailing Stop: {best_params['trailing_stop_pct']*100:.1f}%")

    equity_curve, trades = run_volume_imbalance_backtest(
        df,
        vi_period=int(best_params['vi_period']),
        vi_threshold=best_params['vi_threshold'],
        stop_loss_pct=best_params['stop_loss_pct'],
        take_profit_pct=best_params['take_profit_pct'],
        trailing_stop_pct=best_params['trailing_stop_pct']
    )

    # Create visualization
    output_path = create_visualization(df, equity_curve, trades, output_dir)

    # Save statistics
    stats_path = save_trade_statistics(trades, equity_curve, output_dir)

    # Rename files to indicate optimized
    old_eq = output_dir / 'volume_imbalance_equity_curve.png'
    new_eq = output_dir / 'optimized_equity_curve.png'
    old_eq.rename(new_eq)

    old_stats = output_dir / 'volume_imbalance_statistics.txt'
    new_stats = output_dir / 'optimized_statistics.txt'
    old_stats.rename(new_stats)

    print(f"\n✓ Optimized equity curve: {new_eq}")
    print(f"✓ Optimized statistics: {new_stats}")

    return equity_curve, trades

# Main execution
if __name__ == "__main__":
    print("="*60)
    print("VOLUME IMBALANCE PARAMETER OPTIMIZATION")
    print("Using Smart Grid Search with Multi-Objective Scoring")
    print("="*60)

    # Fetch data
    print("\nFetching data...")
    df = fetch_binance_data_cached(days=180)

    if df is not None and len(df) > 100:
        # Run optimization
        print("\nStarting optimization...")
        print("This will test thousands of parameter combinations.")
        print("Please be patient - this may take 10-30 minutes...\n")

        best_params = analyze_results(
            smart_grid_search(df, n_workers=4),
            output_dir=Path("VolumeImbalance")
        )

        print("\n" + "="*60)
        print("OPTIMIZATION COMPLETE")
        print("="*60)
        print(f"\nBest Parameters Found:")
        print(f"  VI Period: {int(best_params['vi_period'])}")
        print(f"  VI Threshold: {best_params['vi_threshold']:.2f}")
        print(f"  Stop Loss: {best_params['stop_loss_pct']*100:.1f}%")
        print(f"  Take Profit: {best_params['take_profit_pct']*100:.1f}%")
        print(f"  Trailing Stop: {best_params['trailing_stop_pct']*100:.1f}%")
        print(f"\nExpected Performance:")
        print(f"  Total Return: {best_params['total_return']*100:+.2f}%")
        print(f"  Max Drawdown: {best_params['max_drawdown']*100:.2f}%")
        print(f"  Profit Factor: {best_params['profit_factor']:.2f}")
        print(f"  Sharpe Ratio: {best_params['sharpe_ratio']:.2f}")

        # Run optimized backtest
        print("\nRunning full backtest with optimized parameters...")
        equity_curve, trades = run_optimized_backtest(df, best_params)

        print(f"\n{'='*60}")
        print("ALL RESULTS SAVED TO: VolumeImbalance/")
        print(f"{'='*60}")
        print("Files created:")
        print("  - optimization_results.csv (all combinations)")
        print("  - optimization_summary.txt (top 10 summary)")
        print("  - optimization_visualizations.png (6-panel analysis)")
        print("  - optimized_equity_curve.png (best params equity curve)")
        print("  - optimized_statistics.txt (detailed trade stats)")
    else:
        print("Error: Could not fetch data")
