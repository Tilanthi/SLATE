#!/usr/bin/env python3
"""
Quick test of Volume Imbalance optimization
Tests limited parameter set to verify functionality
"""

import pandas as pd
import numpy as np
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent))

from volume_imbalance_simulator import (
    fetch_binance_data,
    run_volume_imbalance_backtest
)

print("="*60)
print("VOLUME IMBALANCE OPTIMIZATION TEST")
print("Testing limited parameter set")
print("="*60)

# Load data
print("\nFetching data...")
df = fetch_binance_data(days=180)

if df is None or len(df) < 100:
    print("Error: Could not load data")
    sys.exit(1)

# Define test parameters (smaller set)
test_params = [
    {'vi_period': 9, 'vi_threshold': 0.20, 'stop_loss_pct': 0.02, 'take_profit_pct': 0.04, 'trailing_stop_pct': 0.015},
    {'vi_period': 12, 'vi_threshold': 0.25, 'stop_loss_pct': 0.02, 'take_profit_pct': 0.05, 'trailing_stop_pct': 0.01},
    {'vi_period': 15, 'vi_threshold': 0.30, 'stop_loss_pct': 0.025, 'take_profit_pct': 0.06, 'trailing_stop_pct': 0.015},
    {'vi_period': 18, 'vi_threshold': 0.35, 'stop_loss_pct': 0.015, 'take_profit_pct': 0.04, 'trailing_stop_pct': 0.02},
    {'vi_period': 21, 'vi_threshold': 0.40, 'stop_loss_pct': 0.03, 'take_profit_pct': 0.07, 'trailing_stop_pct': 0.015},
]

print(f"\nTesting {len(test_params)} parameter combinations...\n")

results = []

for i, params in enumerate(test_params, 1):
    print(f"[{i}/{len(test_params)}] Testing VI Period={params['vi_period']}, Threshold={params['vi_threshold']}...")

    equity_curve, trades = run_volume_imbalance_backtest(
        df,
        vi_period=params['vi_period'],
        vi_threshold=params['vi_threshold'],
        stop_loss_pct=params['stop_loss_pct'],
        take_profit_pct=params['take_profit_pct'],
        trailing_stop_pct=params['trailing_stop_pct']
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
        'vi_period': params['vi_period'],
        'vi_threshold': params['vi_threshold'],
        'stop_loss_pct': params['stop_loss_pct'],
        'take_profit_pct': params['take_profit_pct'],
        'trailing_stop_pct': params['trailing_stop_pct'],
        'final_equity': final_equity,
        'total_return': total_return,
        'max_drawdown': max_drawdown,
        'win_rate': win_rate,
        'profit_factor': profit_factor,
        'num_trades': len(trades),
        'score': score
    })

    print(f"  → Return: {total_return*100:+.2f}%, DD: {max_drawdown*100:.2f}%, PF: {profit_factor:.2f}, Score: {score:.3f}")

# Show results
results_df = pd.DataFrame(results)
results_df = results_df.sort_values('score', ascending=False)

print("\n" + "="*60)
print("RESULTS RANKED BY SCORE")
print("="*60)
print(results_df[['vi_period', 'vi_threshold', 'total_return', 'max_drawdown',
                 'profit_factor', 'score']].to_string(index=False))

best = results_df.iloc[0]
print("\n" + "="*60)
print("BEST PARAMETERS")
print("="*60)
print(f"VI Period: {int(best['vi_period'])}")
print(f"VI Threshold: {best['vi_threshold']:.2f}")
print(f"Stop Loss: {best['stop_loss_pct']*100:.1f}%")
print(f"Take Profit: {best['take_profit_pct']*100:.1f}%")
print(f"Trailing Stop: {best['trailing_stop_pct']*100:.1f}%")
print(f"\nExpected Return: {best['total_return']*100:+.2f}%")
print(f"Max Drawdown: {best['max_drawdown']*100:.2f}%")
print(f"Profit Factor: {best['profit_factor']:.2f}")
print("="*60)

print("\n✓ Test completed successfully!")
print("✓ Optimization framework is working correctly")
print("\nReady to run full optimization...")
