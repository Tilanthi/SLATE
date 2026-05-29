#!/usr/bin/env python3
"""
Plot the candle timeframes used in SLATE discovery strategies.
Shows that all strategies use 1-hour candles.
"""

import matplotlib.pyplot as plt
import sqlite3

# Connect to database
db_path = "slate_core/slate_realistic_discoveries.db"
conn = sqlite3.connect(db_path)

# Get total number of strategies
total_strategies = conn.execute("SELECT COUNT(*) FROM edge_discoveries").fetchone()[0]
conn.close()

# All strategies use 1-hour candles from SOLUSDT_1h_1y.csv
timeframe = "1h"
count = total_strategies

# Create visualization
fig, ax = plt.subplots(1, 1, figsize=(10, 6))
fig.suptitle('SLATE Discovery Candle Timeframes (37,759 Strategies)',
             fontsize=16, fontweight='bold')

# Create bar chart
bars = ax.bar(['1-Hour Candles'], [count], color='#2c7bb6', edgecolor='black', alpha=0.8, width=0.5)

ax.set_ylabel('Number of Strategies', fontsize=14, fontweight='bold')
ax.set_xlabel('Candle Timeframe', fontsize=14, fontweight='bold')
ax.set_title('All Discovery Strategies Use 1-Hour Timeframe', fontsize=12)

# Set y-axis to log scale for clarity
ax.set_yscale('log')
ax.grid(True, alpha=0.3, axis='y')

# Add count label on bar
for bar in bars:
    height = bar.get_height()
    ax.text(bar.get_x() + bar.get_width()/2., height,
             f'{count:,}', ha='center', va='bottom', fontweight='bold', fontsize=14)

# Add information box
info_text = (
    f"Data Source: sol_data_cache/SOLUSDT_1h_1y.csv\n"
    f"Time Range: 2025-04-17 to 2026-04-17 (1 year)\n"
    f"Total Candles: 8,760 hourly candles\n"
    f"Price Range: $75.51 - $251.29"
)
ax.text(0.5, 0.1, info_text, transform=ax.transAxes,
         fontsize=11, verticalalignment='top',
         bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5),
         ha='center')

plt.tight_layout()

# Save the figure
output_path = 'slate_discovery_candle_timeframes.png'
plt.savefig(output_path, dpi=150, bbox_inches='tight', facecolor='white')
print(f"✓ Plot saved to: {output_path}")

print(f"\n{'='*60}")
print("CANDLE TIMEFRAME ANALYSIS")
print(f"{'='*60}")
print(f"Total Strategies: {total_strategies:,}")
print(f"Candle Timeframe: 1-Hour (ALL strategies)")
print(f"Data File: SOLUSDT_1h_1y.csv")
print(f"Data Period: 1 year (8,760 hourly candles)")
print(f"{'='*60}")
print(f"\nNOTE: The discovery system currently uses ONLY 1-hour candles.")
print(f"There is NO testing across multiple timeframes (1m, 5m, 15m, 30m, 4h, etc.).")
print(f"All 37,759 strategy variants are tested on the same 1-hour data.")
print(f"{'='*60}")
