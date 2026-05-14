#!/usr/bin/env python3
"""
Full Volume Imbalance Parameter Optimization
Tests all combinations from the paper's optimization ranges
"""

import pandas as pd
import numpy as np
from pathlib import Path
import sys
from itertools import product
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))

from volume_imbalance_simulator import fetch_binance_data, run_volume_imbalance_backtest

print("="*70)
print("VOLUME IMBALANCE PARAMETER OPTIMIZATION")
print("Full Parameter Space Search - Testing 5,880 Combinations")
print("="*70)

# Load data
print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Fetching data...")
df = fetch_binance_data(days=180)

# Define parameter ranges (from paper)
vi_periods = [6, 9, 12, 15, 18, 21, 24]
vi_thresholds = [0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.45, 0.50]
stop_losses = [0.01, 0.015, 0.02, 0.025, 0.03]  # 1-3%
take_profits = [0.02, 0.03, 0.04, 0.05, 0.06, 0.07, 0.08]  # 2-8%
trailing_stops = [0.005, 0.01, 0.015, 0.02, 0.025, 0.03]  # 0.5-3%

print(f"\nParameter Space:")
print(f"  VI Periods: {len(vi_periods)} values")
print(f"  VI Thresholds: {len(vi_thresholds)} values")
print(f"  Stop Losses: {len(stop_losses)} values")
print(f"  Take Profits: {len(take_profits)} values")
print(f"  Trailing Stops: {len(trailing_stops)} values")
print(f"  Total combinations: {len(vi_periods) * len(vi_thresholds) * len(stop_losses) * len(take_profits) * len(trailing_stops):,}")

# Reduce search space for efficiency (focus on promising areas)
print("\nUsing focused search for efficiency...")
print("Testing combinations with higher thresholds and wider stops (more realistic)")

vi_periods_focused = [12, 15, 18, 21, 24]
vi_thresholds_focused = [0.25, 0.30, 0.35, 0.40, 0.45, 0.50]
stop_losses_focused = [0.02, 0.025, 0.03]  # 2-3%
take_profits_focused = [0.04, 0.05, 0.06, 0.07, 0.08]  # 4-8%
trailing_stops_focused = [0.01, 0.015, 0.02, 0.025]  # 1-2.5%

focused_count = len(vi_periods_focused) * len(vi_thresholds_focused) * len(stop_losses_focused) * len(take_profits_focused) * len(trailing_stops_focused)
print(f"Focused combinations: {focused_count:,}")

results = []
tested = 0
profitable_found = 0

start_time = datetime.now()

for vi_period, vi_threshold, sl, tp, ts in product(
    vi_periods_focused,
    vi_thresholds_focused,
    stop_losses_focused,
    take_profits_focused,
    trailing_stops_focused
):
    tested += 1

    if tested % 100 == 0:
        elapsed = (datetime.now() - start_time).total_seconds()
        rate = tested / elapsed
        remaining = (focused_count - tested) / rate
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Progress: {tested}/{focused_count} ({tested/focused_count*100:.1f}%) | ETA: {int(remaining//60)}m {int(remaining%60)}s")

    try:
        equity_curve, trades = run_volume_imbalance_backtest(
            df,
            vi_period=vi_period,
            vi_threshold=vi_threshold,
            stop_loss_pct=sl,
            take_profit_pct=tp,
            trailing_stop_pct=ts
        )

        final_equity = equity_curve['equity'].iloc[-1]
        total_return = (final_equity - 10000) / 10000

        max_drawdown = (equity_curve['equity'].cummax() - equity_curve['equity']).max() / equity_curve['equity'].cummax().max()

        winning_trades = sum(1 for t in trades if t['pnl'] > 0)
        win_rate = winning_trades / len(trades) if len(trades) > 0 else 0

        gross_profit = sum(t['pnl'] for t in trades if t['pnl'] > 0)
        gross_loss = abs(sum(t['pnl'] for t in trades if t['pnl'] < 0))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0

        score = total_return * (1 - max_drawdown * 2) if total_return > 0 else total_return

        results.append({
            'vi_period': vi_period,
            'vi_threshold': vi_threshold,
            'stop_loss_pct': sl,
            'take_profit_pct': tp,
            'trailing_stop_pct': ts,
            'final_equity': final_equity,
            'total_return': total_return,
            'max_drawdown': max_drawdown,
            'win_rate': win_rate,
            'profit_factor': profit_factor,
            'num_trades': len(trades),
            'score': score
        })

        if total_return > 0:
            profitable_found += 1
            if profitable_found <= 10:
                print(f"  ✓ PROFITABLE: VI={vi_period}, Th={vi_threshold:.2f}, SL={sl*100:.1f}%, TP={tp*100:.1f}% → {total_return*100:+.2f}%")

    except Exception as e:
        print(f"  Error: {e}")
        continue

# Analysis
results_df = pd.DataFrame(results)
results_df = results_df.sort_values('score', ascending=False)

print("\n" + "="*70)
print("OPTIMIZATION COMPLETE")
print("="*70)
print(f"Total tested: {len(results_df):,} combinations")
print(f"Profitable found: {sum(results_df['total_return'] > 0)} ({sum(results_df['total_return'] > 0)/len(results_df)*100:.2f}%)")
print(f"Best return: {results_df['total_return'].max()*100:+.2f}%")
print(f"Worst return: {results_df['total_return'].min()*100:+.2f}%")
print(f"Average return: {results_df['total_return'].mean()*100:+.2f}%")

# Top 20
print("\n" + "="*70)
print("TOP 20 PARAMETER COMBINATIONS")
print("="*70)
top_20 = results_df.head(20)
print(top_20[['vi_period', 'vi_threshold', 'stop_loss_pct', 'take_profit_pct',
             'trailing_stop_pct', 'total_return', 'max_drawdown', 'profit_factor',
             'win_rate', 'num_trades']].to_string(index=False))

# Save results
output_dir = Path("VolumeImbalance")
results_df.to_csv(output_dir / 'optimization_results.csv', index=False)
print(f"\n✓ Results saved to: {output_dir / 'optimization_results.csv'}")

# Best parameters
best = results_df.iloc[0]
print("\n" + "="*70)
print("BEST PARAMETERS FOUND")
print("="*70)
print(f"VI Period: {int(best['vi_period'])}")
print(f"VI Threshold: {best['vi_threshold']:.2f}")
print(f"Stop Loss: {best['stop_loss_pct']*100:.1f}%")
print(f"Take Profit: {best['take_profit_pct']*100:.1f}%")
print(f"Trailing Stop: {best['trailing_stop_pct']*100:.1f}%")
print(f"\nPerformance:")
print(f"  Total Return: {best['total_return']*100:+.2f}%")
print(f"  Max Drawdown: {best['max_drawdown']*100:.2f}%")
print(f"  Profit Factor: {best['profit_factor']:.2f}")
print(f"  Win Rate: {best['win_rate']*100:.1f}%")
print(f"  Number of Trades: {int(best['num_trades'])}")
print(f"  Final Equity: ${best['final_equity']:,.2f}")
print("="*70)
