#!/usr/bin/env python3
"""
Visualize the top performing strategy with equity curve and trade markers.
"""

import sqlite3
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime
import json
from pathlib import Path

# Load the top strategy from database
db_path = "slate_core/slate_realistic_discoveries.db"

conn = sqlite3.connect(db_path)
query = """
SELECT * FROM edge_discoveries
ORDER BY total_profit_usdt DESC
LIMIT 1
"""
df = pd.read_sql_query(query, conn)
conn.close()

if len(df) == 0:
    print("No strategies found in database")
    exit(1)

strategy = df.iloc[0]
print(f"Top Strategy: {strategy['edge_description']}")
print(f"Return: {strategy['total_return_pct']:.2%}")
print(f"Profit: ${strategy['total_profit_usdt']:.2f}")
print(f"Sharpe: {strategy['sharpe_ratio']:.2f}")

# Load market data
data_path = "sol_data_cache/SOLUSDT_1h_1y.csv"
if not Path(data_path).exists():
    print(f"Market data not found at {data_path}")
    exit(1)

price_data = pd.read_csv(data_path)
price_data['timestamp'] = pd.to_datetime(price_data['timestamp'])
price_data = price_data.set_index('timestamp')

# Parse strategy parameters from description
description = strategy['edge_description']
print(f"\nStrategy Description: {description}")

# For Asian Session Range Fade, we need to recreate the strategy logic
# Extract parameters from description
import re

# Parse parameters based on strategy type
if "Asian Session Range Fade" in description:
    # Extract parameters like "UTC 20:00-02:00, vol adj=0.1"
    time_match = re.search(r'UTC (\d+):(\d+)-(\d+):(\d+)', description)
    vol_match = re.search(r'vol adj=([\d.]+)', description)

    if time_match:
        start_hour = int(time_match.group(1))
        start_min = int(time_match.group(2))
        end_hour = int(time_match.group(3))
        end_min = int(time_match.group(4))

    vol_adj = float(vol_match.group(1)) if vol_match else 0.1

    print(f"\nParameters:")
    print(f"  Session: UTC {start_hour}:{start_min:02d} - {end_hour}:{end_min:02d}")
    print(f"  Volatility Adjustment: {vol_adj}")

    # Implement Asian Session Range Fade strategy
    # This strategy fades the range during Asian session

    # Calculate session indicators
    price_data['hour'] = price_data.index.hour
    price_data['in_session'] = False

    # Handle session that crosses midnight (20:00-02:00)
    if start_hour > end_hour:
        price_data.loc[(price_data['hour'] >= start_hour) | (price_data['hour'] < end_hour), 'in_session'] = True
    else:
        price_data.loc[(price_data['hour'] >= start_hour) & (price_data['hour'] < end_hour), 'in_session'] = True

    # Calculate range during previous session
    price_data['prev_high'] = price_data['high'].rolling(24).max()
    price_data['prev_low'] = price_data['low'].rolling(24).min()
    price_data['range_mid'] = (price_data['prev_high'] + price_data['prev_low']) / 2

    # Calculate volatility (ATR-based)
    price_data['atr'] = (price_data['high'] - price_data['low']).rolling(14).mean()
    price_data['volatility'] = price_data['atr'] / price_data['close']

    # Generate signals
    signals = pd.DataFrame(index=price_data.index)
    signals['price'] = price_data['close']
    signals['in_session'] = price_data['in_session']

    # Entry: fade when price at range extremes during session
    signals['long_entry'] = (
        (price_data['in_session']) &
        (price_data['close'] < price_data['prev_low'] * (1 + vol_adj * 0.01))
    )

    signals['short_entry'] = (
        (price_data['in_session']) &
        (price_data['close'] > price_data['prev_high'] * (1 - vol_adj * 0.01))
    )

    # Exit: at range midpoint or end of session
    signals['exit_long'] = (
        (price_data['close'] > price_data['range_mid']) |
        (~price_data['in_session'])
    )

    signals['exit_short'] = (
        (price_data['close'] < price_data['range_mid']) |
        (~price_data['in_session'])
    )

elif "Regime Switching Model" in description:
    print(f"\nParameters:")
    print(f"  Strategy: Detects trend/range regimes and switches accordingly")

    # Calculate regime indicators
    price_data['sma_20'] = price_data['close'].rolling(20).mean()
    price_data['sma_50'] = price_data['close'].rolling(50).mean()
    price_data['atr'] = (price_data['high'] - price_data['low']).rolling(14).mean()

    # Detect regime: trend = SMAs diverging, range = SMAs converging
    price_data['regime_trend'] = abs(price_data['sma_20'] - price_data['sma_50']) / price_data['close'] > 0.02
    price_data['regime_range'] = ~price_data['regime_trend']

    # Trend following signals
    price_data['trend_up'] = price_data['sma_20'] > price_data['sma_50']
    price_data['trend_down'] = price_data['sma_20'] < price_data['sma_50']

    # Range trading signals
    price_data['price_vs_sma20'] = (price_data['close'] - price_data['sma_20']) / price_data['sma_20']
    price_data['oversold'] = price_data['price_vs_sma20'] < -0.015
    price_data['overbought'] = price_data['price_vs_sma20'] > 0.015

    signals = pd.DataFrame(index=price_data.index)
    signals['price'] = price_data['close']

    # Entry signals based on regime
    signals['long_entry'] = (
        (price_data['regime_trend'] & price_data['trend_up'] & (price_data['close'] > price_data['sma_20'])) |
        (price_data['regime_range'] & price_data['oversold'])
    )

    signals['short_entry'] = (
        (price_data['regime_trend'] & price_data['trend_down'] & (price_data['close'] < price_data['sma_20'])) |
        (price_data['regime_range'] & price_data['overbought'])
    )

    # Exit signals
    signals['exit_long'] = (
        (price_data['regime_trend'] & price_data['trend_down']) |
        (price_data['regime_range'] & price_data['overbought'])
    )

    signals['exit_short'] = (
        (price_data['regime_trend'] & price_data['trend_up']) |
        (price_data['regime_range'] & price_data['oversold'])
    )

elif "Bollinger Band Mean Reversion" in description:
    # Extract parameters like "19-period, 2.1 std"
    period_match = re.search(r'(\d+)-period', description)
    std_match = re.search(r'([\d.]+) std', description)

    period = int(period_match.group(1)) if period_match else 20
    std_dev = float(std_match.group(1)) if std_match else 2.0

    print(f"\nParameters:")
    print(f"  Period: {period}")
    print(f"  Standard Deviations: {std_dev}")

    # Calculate Bollinger Bands
    price_data['sma'] = price_data['close'].rolling(period).mean()
    price_data['std'] = price_data['close'].rolling(period).std()
    price_data['upper_band'] = price_data['sma'] + (price_data['std'] * std_dev)
    price_data['lower_band'] = price_data['sma'] - (price_data['std'] * std_dev)

    signals = pd.DataFrame(index=price_data.index)
    signals['price'] = price_data['close']

    # Entry signals
    signals['long_entry'] = price_data['close'] < price_data['lower_band']
    signals['short_entry'] = price_data['close'] > price_data['upper_band']

    # Exit signals
    signals['exit_long'] = price_data['close'] > price_data['sma']
    signals['exit_short'] = price_data['close'] < price_data['sma']

else:
    print(f"\nStrategy type not fully supported for visualization: {description}")
    print("Showing price data only...")
    signals = pd.DataFrame(index=price_data.index)
    signals['price'] = price_data['close']
    signals['long_entry'] = False
    signals['short_entry'] = False
    signals['exit_long'] = False
    signals['exit_short'] = False

# Simulate trades with realistic costs
initial_capital = 10000
capital = initial_capital
position = 0
entries = []
exits = []
equity_curve = []

maker_fee = 0.0002
taker_fee = 0.0005
slippage_bps = 10

for i in range(1, len(signals)):
    price = signals['price'].iloc[i]

    # Check for long entry
    if signals['long_entry'].iloc[i] and position == 0:
        entry_price = price * (1 + slippage_bps/10000)
        position_size = (capital * 0.05) / entry_price  # 5% max position
        capital -= position_size * entry_price * (1 + taker_fee)
        position = position_size
        entries.append({
            'time': signals.index[i],
            'price': entry_price,
            'type': 'LONG',
            'size': position_size
        })

    # Check for short entry
    elif signals['short_entry'].iloc[i] and position == 0:
        entry_price = price * (1 - slippage_bps/10000)
        position_size = (capital * 0.05) / entry_price  # 5% max position
        capital -= position_size * entry_price * (1 + taker_fee)
        position = -position_size
        entries.append({
            'time': signals.index[i],
            'price': entry_price,
            'type': 'SHORT',
            'size': position_size
        })

    # Check for exit
    elif (signals['exit_long'].iloc[i] and position > 0) or \
         (signals['exit_short'].iloc[i] and position < 0):
        exit_price = price * (1 - slippage_bps/10000) if position > 0 else price * (1 + slippage_bps/10000)
        pnl = position * exit_price * (1 - maker_fee)
        capital += abs(position) * exit_price * (1 - maker_fee)
        exits.append({
            'time': signals.index[i],
            'price': exit_price,
            'type': 'EXIT',
            'pnl': pnl
        })
        position = 0

    # Calculate equity
    if position != 0:
        unrealized_pnl = position * price
        equity = capital + unrealized_pnl
    else:
        equity = capital
    equity_curve.append({'time': signals.index[i], 'equity': equity})

# Create visualization
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10), height_ratios=[2, 1])
fig.suptitle(f'Top Strategy: {description[:60]}...', fontsize=14, fontweight='bold')

# Plot 1: Price with entries and exits
ax1.plot(price_data.index, price_data['close'], label='SOLUSDT Price', color='#2c3e50', linewidth=1.5, alpha=0.7)

# Plot entry markers
long_entries = [e for e in entries if e['type'] == 'LONG']
short_entries = [e for e in entries if e['type'] == 'SHORT']

if long_entries:
    le_times = [e['time'] for e in long_entries]
    le_prices = [e['price'] for e in long_entries]
    ax1.scatter(le_times, le_prices, marker='^', color='#27ae60', s=100, label=f'Long Entry ({len(long_entries)})', zorder=5)

if short_entries:
    se_times = [e['time'] for e in short_entries]
    se_prices = [e['price'] for e in short_entries]
    ax1.scatter(se_times, se_prices, marker='v', color='#e74c3c', s=100, label=f'Short Entry ({len(short_entries)})', zorder=5)

# Plot exit markers
if exits:
    ex_times = [e['time'] for e in exits]
    ex_prices = [e['price'] for e in exits]
    ax1.scatter(ex_times, ex_prices, marker='x', color='#3498db', s=100, label=f'Exit ({len(exits)})', zorder=5)

ax1.set_ylabel('Price (USDT)', fontsize=11, fontweight='bold')
ax1.set_title(f'SOLUSDT Price with Trade Entries & Exits\n{price_data.index[0].strftime("%Y-%m-%d")} to {price_data.index[-1].strftime("%Y-%m-%d")}', fontsize=12)
ax1.legend(loc='upper left', fontsize=9)
ax1.grid(True, alpha=0.3)

# Plot 2: Equity Curve
if equity_curve:
    eq_df = pd.DataFrame(equity_curve).set_index('time')
    ax2.plot(eq_df.index, eq_df['equity'], label='Portfolio Equity', color='#2980b9', linewidth=2)

    # Add initial capital line
    ax2.axhline(y=initial_capital, color='#95a5a6', linestyle='--', label=f'Initial Capital (${initial_capital})')

    final_equity = eq_df['equity'].iloc[-1]
    total_return = (final_equity - initial_capital) / initial_capital

    ax2.set_ylabel('Portfolio Value (USDT)', fontsize=11, fontweight='bold')
    ax2.set_xlabel('Time', fontsize=11, fontweight='bold')
    ax2.set_title(f'Equity Curve - Final Return: {total_return:.2%} (${final_equity:.2f})', fontsize=12)
    ax2.legend(loc='upper left', fontsize=9)
    ax2.grid(True, alpha=0.3)

    # Format y-axis as currency
    ax2.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'${x:,.0f}'))

plt.tight_layout()

# Save the figure
output_path = 'top_strategy_equity_curve.png'
plt.savefig(output_path, dpi=150, bbox_inches='tight', facecolor='white')
print(f"\n✓ Visualization saved to: {output_path}")

# Print trade statistics
print(f"\n{'='*60}")
print("TRADE STATISTICS")
print(f"{'='*60}")
print(f"Total Entries: {len(entries)}")
print(f"Total Exits: {len(exits)}")
print(f"Final Equity: ${final_equity:.2f}")
print(f"Total Return: {total_return:.2%}")
print(f"Total Profit: ${final_equity - initial_capital:.2f}")
print(f"{'='*60}")

if exits:
    winning_trades = [e for e in exits if e.get('pnl', 0) > 0]
    losing_trades = [e for e in exits if e.get('pnl', 0) <= 0]
    print(f"Winning Trades: {len(winning_trades)}")
    print(f"Losing Trades: {len(losing_trades)}")
    if exits:
        win_rate = len(winning_trades) / len(exits)
        print(f"Win Rate: {win_rate:.2%}")
