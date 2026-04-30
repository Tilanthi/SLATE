#!/usr/bin/env python3
"""
Create high-quality diagrams for SLATE User Manual.
"""

import os
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import matplotlib.pyplot as plt

# Set the directory to this script's location
os.chdir(os.path.dirname(os.path.abspath(__file__)))
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import numpy as np

# Set style for professional look
plt.style.use('seaborn-v0_8-darkgrid')
fig = plt.figure(figsize=(16, 12))
ax = fig.add_subplot(111)
ax.set_xlim(0, 16)
ax.set_ylim(0, 12)
ax.axis('off')

# Title
ax.text(8, 11.5, 'SLATE Architecture Overview',
        fontsize=24, fontweight='bold', ha='center', color='#2C3E50')

# Main components
components = [
    (1, 9, 2.5, 1.5, 'FastAPI Server\n(Port 8788)', '#3498DB', '#ECF0F1'),
    (5, 9, 2.5, 1.5, 'Trading Engine\n(OODA Cycle)', '#E74C3C', '#ECF0F1'),
    (9, 9, 2.5, 1.5, 'Discovery System', '#27AE60', '#ECF0F1'),
    (13, 9, 2.5, 1.5, 'Risk Management', '#F39C12', '#ECF0F1'),

    (1, 6.5, 2.5, 1.5, 'Data Fetchers\n(Binance, Bitget)', '#9B59B6', '#ECF0F1'),
    (5, 6.5, 2.5, 1.5, 'Strategy Manager\n& Backtester', '#1ABC9C', '#ECF0F1'),
    (9, 6.5, 2.5, 1.5, 'Language Compilers\n(Pine, HaasScript)', '#34495E', '#ECF0F1'),
    (13, 6.5, 2.5, 1.5, 'Portfolio\nOptimization', '#D35400', '#ECF0F1'),

    (3, 4, 3, 1.5, 'GraphPalace Database\n(Knowledge Graph)', '#8E44AD', '#ECF0F1'),
    (10, 4, 3, 1.5, 'Discovery Database\n(SQLite)', '#C0392B', '#ECF0F1'),

    (3, 1.5, 3, 1.5, 'Stigmergic\nCoordination', '#16A085', '#ECF0F1'),
    (10, 1.5, 3, 1.5, 'Self-Evolution\nEngine', '#2ECC71', '#ECF0F1'),
]

# Draw components
for x, y, w, h, text, fill_color, text_color in components:
    box = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.1",
                          edgecolor='black', facecolor=fill_color,
                          linewidth=2, alpha=0.8)
    ax.add_patch(box)
    ax.text(x + w/2, y + h/2, text, fontsize=10, fontweight='bold',
            ha='center', va='center', color=text_color)

# Add arrows showing connections
arrows = [
    ((2.25, 9), (3.75, 9)),  # Server to Engine
    ((6.25, 9), (7.75, 9)),  # Engine to Discovery
    ((10.25, 9), (11.75, 9)),  # Discovery to Risk

    ((2.25, 7.25), (3.75, 7.25)),  # Data to Strategy
    ((6.25, 7.25), (7.75, 7.25)),  # Strategy to Language
    ((10.25, 7.25), (11.75, 7.25)),  # Language to Portfolio

    ((4.5, 6.5), (4.5, 5.5)),  # Strategy to GraphPalace
    ((11.5, 6.5), (11.5, 5.5)),  # Language to Discovery DB

    ((4.5, 4), (4.5, 3)),  # GraphPalace to Stigmergic
    ((11.5, 4), (11.5, 3)),  # Discovery DB to Evolution

    ((6, 2.25), (10, 2.25)),  # Stigmergic to Evolution
]

for start, end in arrows:
    arrow = FancyArrowPatch(start, end, connectionstyle="arc3,rad=0.1",
                            arrowstyle='->,head_width=0.4,head_length=0.4',
                            color='#34495E', linewidth=2, alpha=0.6)
    ax.add_patch(arrow)

# Add legend
legend_elements = [
    mpatches.Patch(color='#3498DB', label='API Layer'),
    mpatches.Patch(color='#E74C3C', label='Core Engine'),
    mpatches.Patch(color='#27AE60', label='Discovery'),
    mpatches.Patch(color='#F39C12', label='Risk'),
    mpatches.Patch(color='#8E44AD', label='Database'),
]
ax.legend(handles=legend_elements, loc='lower center', bbox_to_anchor=(0.5, -0.05),
           ncol=5, fontsize=10)

plt.tight_layout()
plt.savefig('images/architecture_overview.png', dpi=300, bbox_inches='tight')
plt.close()

# Create OODA Cycle diagram
fig, ax = plt.subplots(figsize=(14, 10))
ax.set_xlim(0, 14)
ax.set_ylim(0, 10)
ax.axis('off')

ax.text(7, 9.5, 'SLATE OODA Trading Cycle',
        fontsize=22, fontweight='bold', ha='center', color='#2C3E50')

# OODA phases
phases = [
    (2, 6, 'OBSERVE', '#3498DB',
     '• Collect market data\n• Fetch price candles\n• Get orderbook depth\n• Monitor volume\n• Track market events'),
    (6, 6, 'ORIENT', '#F39C12',
     '• Analyze market regime\n• Calculate indicators\n• Assess risk levels\n• Rank strategies\n• Generate signals'),
    (10, 6, 'DECIDE', '#E74C3C',
     '• Select best strategy\n• Calculate position size\n• Set entry/exit points\n• Apply risk rules\n• Generate trade signals'),
    (6, 2, 'ACT', '#27AE60',
     '• Execute paper trades\n• Monitor positions\n• Track performance\n• Record results\n• Update learning'),
]

# Draw cycle
for x, y, phase, color, description in phases:
    # Draw circle
    circle = plt.Circle((x, y), 1.5, color=color, alpha=0.3, ec='black', lw=3)
    ax.add_patch(circle)

    # Phase label
    ax.text(x, y + 0.3, phase, fontsize=14, fontweight='bold',
            ha='center', va='center', color='white')

    # Description
    ax.text(x, y - 0.5, description, fontsize=9, ha='center', va='center', color='#2C3E50')

# Draw arrows between phases
arrow_props = dict(arrowstyle='->,head_width=0.5,head_length=0.5', lw=3, color='#34495E')

# Observe → Orient
ax.annotate('', xy=(5, 6), xytext=(3.5, 6), arrowprops=arrow_props)
# Orient → Decide
ax.annotate('', xy=(9, 6), xytext=(7.5, 6), arrowprops=arrow_props)
# Decide → Act
ax.annotate('', xy=(6, 3.5), xytext=(10, 3.5), arrowprops=arrow_props)
# Act → Observe (feedback loop)
ax.annotate('', xy=(2, 3.5), xytext=(5, 3.5), arrowprops=arrow_props)

# Add LEARN phase in center
ax.text(7, 4.5, 'LEARN\n&\nADAPT', fontsize=10, fontweight='bold',
        ha='center', va='center', color='#8E44AD',
        bbox=dict(boxstyle='round,pad=0.5', facecolor='#F4ECF7', edgecolor='#8E44AD', lw=2))

# Add paper trading notice
ax.text(7, 0.5, '⚠️ PAPER TRADING ONLY - No real money is ever risked',
        fontsize=12, ha='center', va='center', color='#C0392B', fontweight='bold',
        bbox=dict(boxstyle='round,pad=0.3', facecolor='#FADBD8', edgecolor='#C0392B', lw=2))

plt.tight_layout()
plt.savefig('images/ooda_cycle.png', dpi=300, bbox_inches='tight')
plt.close()

# Create Discovery System diagram
fig, ax = plt.subplots(figsize=(16, 12))
ax.set_xlim(0, 16)
ax.set_ylim(0, 12)
ax.axis('off')

ax.text(8, 11.5, 'SLATE Discovery System',
        fontsize=24, fontweight='bold', ha='center', color='#2C3E50')

# Discovery components
discovery_boxes = [
    (1, 8, 3, 2, 'Realistic\nBacktesting', '#3498DB',
     '• 0.02% maker fee\n• 0.05% taker fee\n• 5bps slippage\n• 95% fill rate\n• No artificial profits'),
    (5, 8, 3, 2, 'Strategy\nGenerator', '#E74C3C',
     '• 10+ strategy types\n• Multiple timeframes\n• Parameter mutation\n• Cross-asset'),
    (9, 8, 3, 2, 'Multi-Path\nTesting', '#F39C12',
     '• Bootstrap resampling\n• Monte Carlo sims\n• 100+ paths\n• Robust metrics'),
    (13, 8, 3, 2, 'Self-Evolution\nEngine', '#27AE60',
     '• Survival of fittest\n• Parameter optimization\n• Performance tracking\n• Continuous learning'),

    (1, 5, 3, 2, 'Stigmergic\nCoordination', '#9B59B6',
     '• Swarm intelligence\n• Pheromone trails\n• Collective learning\n• Diversity maintenance'),
    (5, 5, 3, 2, 'Risk\nManagement', '#1ABC9C',
     '• Kelly Criterion\n• VaR calculations\n• Drawdown limits\n• Position sizing'),
    (9, 5, 3, 2, 'Memory\nSystem', '#34495E',
     '• Discovery graph\n• Performance history\n• Edge tracking\n• Knowledge base'),
    (13, 5, 3, 2, 'API\nEndpoints', '#E67E22',
     '• REST API\n• Webhooks\n• Real-time updates\n• Dashboard data'),

    (3, 2, 4, 1.5, 'GraphPalace\nKnowledge Graph', '#8E44AD',
     '• Strategy relationships\n• Performance evolution\n• Market context\n• Temporal tracking'),
    (11, 2, 4, 1.5, 'Discovery\nDatabase', '#C0392B',
     '• Tiered storage\n• Auto-cleanup\n• Historical results\n• Performance metrics'),
]

for x, y, w, h, title, color, features in discovery_boxes:
    box = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.1",
                          edgecolor='black', facecolor=color,
                          linewidth=2, alpha=0.7)
    ax.add_patch(box)
    ax.text(x + w/2, y + h - 0.3, title, fontsize=11, fontweight='bold',
            ha='center', va='center', color='white')
    ax.text(x + w/2, y + h/2 - 0.2, features, fontsize=8,
            ha='center', va='center', color='#ECF0F1')

# Add workflow arrows
workflow_arrows = [
    ((2.5, 8), (5, 8)),  # Backtesting → Generator
    ((6.5, 8), (9, 8)),  # Generator → Multi-Path
    ((10.5, 8), (13, 8)),  # Multi-Path → Evolution
    ((14.5, 8), (14.5, 7)),  # Evolution down
    ((14.5, 7), (14.5, 6)),  # to API
    ((14.5, 6), (10.5, 6)),  # to Memory
    ((2.5, 5), (2.5, 4)),  # Stigmergic down
    ((2.5, 4), (3.5, 3.5)),  # to GraphPalace
    ((6.5, 5), (6.5, 4)),  # Risk down
    ((6.5, 4), (4.5, 3.5)),  # to GraphPalace
]

for start, end in workflow_arrows:
    arrow = FancyArrowPatch(start, end, connectionstyle="arc3,rad=0.1",
                            arrowstyle='->,head_width=0.3,head_length=0.3',
                            color='#2C3E50', linewidth=2, alpha=0.7)
    ax.add_patch(arrow)

plt.tight_layout()
plt.savefig('images/discovery_system.png', dpi=300, bbox_inches='tight')
plt.close()

print("✓ Created architecture diagrams:")
print("  - images/architecture_overview.png")
print("  - images/ooda_cycle.png")
print("  - images/discovery_system.png")
