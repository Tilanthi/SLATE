#!/usr/bin/env python3
"""
Extract and plot timescales from SLATE discovery database.
Shows the distribution of lookback periods, hold periods, and pattern sizes tested.
"""

import sqlite3
import re
import matplotlib.pyplot as plt
import numpy as np
from collections import defaultdict

# Connect to database
db_path = "slate_core/slate_realistic_discoveries.db"
conn = sqlite3.connect(db_path)

# Get all strategy descriptions
query = "SELECT edge_description FROM edge_discoveries"
descriptions = [row[0] for row in conn.execute(query)]
conn.close()

print(f"Analyzing {len(descriptions)} strategies for timescale patterns...")

# Extract timescales using various patterns
timescales = []
timescale_sources = []

for desc in descriptions:
    # Pattern 1: "N-period" (e.g., "45-period", "13-period")
    matches = re.findall(r'(\d+)-period', desc)
    for m in matches:
        timescales.append(int(m))
        timescale_sources.append('period')

    # Pattern 2: "N-bar" (e.g., "20-bar hold", "24-bar pattern")
    matches = re.findall(r'(\d+)-bar', desc)
    for m in matches:
        timescales.append(int(m))
        timescale_sources.append('bar')

    # Pattern 3: "RSIN" (e.g., "RSI38", "RSI50")
    matches = re.findall(r'RSI(\d+)', desc)
    for m in matches:
        timescales.append(int(m))
        timescale_sources.append('RSI')

    # Pattern 4: "UTC HH:MM-HH:MM" (convert to hours)
    matches = re.findall(r'UTC (\d+):(\d+)-(\d+):(\d+)', desc)
    for start_hr, start_min, end_hr, end_min in matches:
        start_time = int(start_hr) + int(start_min) / 60
        end_time = int(end_hr) + int(end_min) / 60
        # Handle crossing midnight
        if end_time < start_time:
            duration = (24 - start_time) + end_time
        else:
            duration = end_time - start_time
        timescales.append(duration)
        timescale_sources.append('hour_session')

    # Pattern 5: "ATR<N>" or similar
    matches = re.findall(r'ATR(\d+)', desc)
    for m in matches:
        timescales.append(int(m))
        timescale_sources.append('ATR')

    # Pattern 6: "ema" or "sma" with numbers (e.g., "ema20", "sma50")
    matches = re.findall(r'[ems]ma(\d+)', desc, re.IGNORECASE)
    for m in matches:
        timescales.append(int(m))
        timescale_sources.append('MA')

print(f"Extracted {len(timescales)} timescale values from {len(descriptions)} strategies")

# Create visualization
fig, axes = plt.subplots(2, 2, figsize=(15, 12))
fig.suptitle('SLATE Discovery Timescales Distribution (23,947 Strategies)',
             fontsize=16, fontweight='bold')

# Plot 1: Overall distribution (histogram)
ax1 = axes[0, 0]
timescales_array = np.array(timescales)
bins = np.logspace(np.log10(1), np.log10(200), 50)
ax1.hist(timescales_array, bins=bins, edgecolor='black', alpha=0.7, color='steelblue')
ax1.set_xscale('log')
ax1.set_xlabel('Timescale (bars/hours) - Log Scale', fontsize=12, fontweight='bold')
ax1.set_ylabel('Frequency', fontsize=12, fontweight='bold')
ax1.set_title('Distribution of All Timescales', fontsize=14, fontweight='bold')
ax1.grid(True, alpha=0.3, which='both')
ax1.axvline(np.median(timescales_array), color='red', linestyle='--', linewidth=2, label=f'Median: {np.median(timescales_array):.1f}')
ax1.legend(fontsize=10)

# Plot 2: By timescale category
ax2 = axes[0, 1]
categories = {}
for i, source in enumerate(timescale_sources):
    if source not in categories:
        categories[source] = []
    categories[source].append(timescales[i])

# Create box plot by category
category_names = list(categories.keys())
category_data = [categories[name] for name in category_names]
positions = range(1, len(category_names) + 1)

bp = ax2.boxplot(category_data, positions=positions, vert=True, patch_artist=True)
for patch in bp['boxes']:
    patch.set_facecolor('lightblue')
    patch.set_alpha(0.7)

ax2.set_yscale('log')
ax2.set_xticks(positions)
ax2.set_xticklabels(category_names, rotation=45, ha='right')
ax2.set_ylabel('Timescale (bars/hours) - Log Scale', fontsize=12, fontweight='bold')
ax2.set_title('Timescales by Category', fontsize=14, fontweight='bold')
ax2.grid(True, alpha=0.3, axis='y', which='both')

# Plot 3: Timescale ranges
ax3 = axes[1, 0]
# Define ranges
ranges = [
    (1, 5, 'Ultra-Short\n(1-5 bars)'),
    (5, 15, 'Short\n(5-15 bars)'),
    (15, 50, 'Medium\n(15-50 bars)'),
    (50, 100, 'Long\n(50-100 bars)'),
    (100, 200, 'Very Long\n(100+ bars)')
]

range_counts = []
range_labels = []
range_colors = ['#fee5d9', '#fcae91', '#fd8d3c', '#e6550d', '#a63603']

for min_val, max_val, label in ranges:
    count = sum(1 for t in timescales if min_val <= t < max_val)
    range_counts.append(count)
    range_labels.append(label)

bars = ax3.bar(range_labels, range_counts, color=range_colors, edgecolor='black', alpha=0.8)
ax3.set_ylabel('Number of Strategies', fontsize=12, fontweight='bold')
ax3.set_title('Strategies by Timescale Range', fontsize=14, fontweight='bold')
ax3.grid(True, alpha=0.3, axis='y')

# Add count labels on bars
for i, (bar, count) in enumerate(zip(bars, range_counts)):
    height = bar.get_height()
    ax3.text(bar.get_x() + bar.get_width()/2., height,
             f'{count:,}', ha='center', va='bottom', fontweight='bold', fontsize=11)

# Plot 4: Cumulative distribution
ax4 = axes[1, 1]
sorted_timescales = np.sort(timescales_array)
cumulative = np.arange(1, len(sorted_timescales) + 1) / len(sorted_timescales) * 100

ax4.plot(sorted_timescales, cumulative, linewidth=2, color='#d94801')
ax4.fill_between(sorted_timescales, cumulative, alpha=0.3, color='#fd8d3c')
ax4.set_xscale('log')
ax4.set_xlabel('Timescale (bars/hours) - Log Scale', fontsize=12, fontweight='bold')
ax4.set_ylabel('Cumulative Percentage', fontsize=12, fontweight='bold')
ax4.set_title('Cumulative Distribution of Timescales', fontsize=14, fontweight='bold')
ax4.grid(True, alpha=0.3, which='both')

# Add percentile markers
percentiles = [10, 25, 50, 75, 90]
for p in percentiles:
    value = np.percentile(sorted_timescales, p)
    ax4.axhline(y=p, color='gray', linestyle=':', linewidth=1, alpha=0.7)
    ax4.axvline(x=value, color='gray', linestyle=':', linewidth=1, alpha=0.7)
    ax4.text(value, p + 2, f'P{p}: {value:.0f}', fontsize=9, ha='left')

plt.tight_layout(rect=[0, 0.03, 1, 0.95])

# Save the figure
output_path = 'slate_discovery_timescales.png'
plt.savefig(output_path, dpi=150, bbox_inches='tight', facecolor='white')
print(f"\n✓ Plot saved to: {output_path}")

# Print statistics
print(f"\n{'='*60}")
print("TIMESCALE STATISTICS")
print(f"{'='*60}")
print(f"Total timescales extracted: {len(timescales):,}")
print(f"Minimum: {np.min(timescales_array):.1f} bars/hours")
print(f"Maximum: {np.max(timescales_array):.1f} bars/hours")
print(f"Mean: {np.mean(timescales_array):.1f} bars/hours")
print(f"Median: {np.median(timescales_array):.1f} bars/hours")
print(f"Std Dev: {np.std(timescales_array):.1f} bars/hours")
print(f"\nPercentiles:")
for p in [10, 25, 50, 75, 90, 95, 99]:
    print(f"  P{p}: {np.percentile(timescales_array, p):.1f} bars/hours")
print(f"{'='*60}")

# By category
print(f"\nBy Category:")
for name in sorted(category_names):
    data = categories[name]
    print(f"  {name:15s}: n={len(data):>5,}, min={min(data):>4.0f}, max={max(data):>4.0f}, median={np.median(data):>5.1f}")
