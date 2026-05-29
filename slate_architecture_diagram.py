#!/usr/bin/env python3
"""
SLATE Architecture Diagram Generator
Creates a high-quality flow diagram of SLATE's core architecture
"""

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import numpy as np

# Set up figure with high DPI for quality output
fig, ax = plt.subplots(1, 1, figsize=(16, 12), dpi=300)
ax.set_xlim(0, 16)
ax.set_ylim(0, 12)
ax.axis('off')

# Color scheme - professional blues and grays
COLORS = {
    'data': '#2E86AB',      # Blue
    'discovery': '#A23B72', # Purple
    'intelligence': '#F18F01', # Orange
    'memory': '#C73E1D',   # Red
    'orchestration': '#6A994E', # Green
    'execution': '#3B1F2B', # Dark purple
    'interface': '#BC4B51', # Pink
    'light_grey': '#F0F0F0',
    'dark_grey': '#333333',
}

def create_box(x, y, width, height, text, color, fontsize=10, text_color='white', bold=False):
    """Create a styled box with text"""
    box = FancyBboxPatch((x, y), width, height,
                         boxstyle="round,pad=0.1",
                         facecolor=color,
                         edgecolor='black',
                         linewidth=1.5)
    ax.add_patch(box)

    fontweight = 'bold' if bold else 'normal'
    ax.text(x + width/2, y + height/2, text,
            ha='center', va='center',
            fontsize=fontsize,
            color=text_color,
            fontweight=fontweight,
            wrap=True)

def create_arrow(x1, y1, x2, y2, color='#333333', style='->', lw=1.5):
    """Create an arrow between two points"""
    arrow = FancyArrowPatch((x1, y1), (x2, y2),
                           arrowstyle=f'{style},head_width=0.15,head_length=0.3',
                           color=color,
                           linewidth=lw,
                           zorder=0)
    ax.add_patch(arrow)

# Title
ax.text(8, 11.5, 'SLATE - Strategy Learning & Autonomous Trading Engine',
        ha='center', va='center',
        fontsize=18, fontweight='bold', color='#333333')
ax.text(8, 11.2, 'Core Architecture Flow',
        ha='center', va='center',
        fontsize=12, color='#666666')

# === DATA LAYER (Top) ===
create_box(1, 9.5, 3, 0.8, 'REAL MARKET DATA\n(Binance SOLUSDT)',
           COLORS['data'], fontsize=10, bold=True)
create_box(4.5, 9.5, 2.5, 0.8, 'Data Cache\n(CSV Storage)',
           COLORS['data'], fontsize=9)

# === DISCOVERY LAYER ===
create_box(0.5, 8, 2.5, 0.7, 'Edge Discovery\nEngine',
           COLORS['discovery'], fontsize=9)
create_box(3.5, 8, 2.5, 0.7, 'NL Strategy\nGenerator',
           COLORS['discovery'], fontsize=9)
create_box(6.5, 8, 2.5, 0.7, 'Strategy Templates\n(35+ Variants)',
           COLORS['discovery'], fontsize=9)
create_box(9.5, 8, 2.5, 0.7, 'Monte Carlo\nValidation',
           COLORS['discovery'], fontsize=9)

# === BACKTEST LAYER ===
create_box(2, 6.8, 4, 0.7, 'BRUTALLY REALISTIC BACKTEST',
           COLORS['execution'], fontsize=10, bold=True)
create_box(0.5, 5.8, 2.2, 0.6, 'Maker Fee: 0.02%',
           COLORS['light_grey'], fontsize=8, text_color='black')
create_box(3, 5.8, 2.2, 0.6, 'Taker Fee: 0.05%',
           COLORS['light_grey'], fontsize=8, text_color='black')
create_box(5.5, 5.8, 2.2, 0.6, 'Slippage: 10-20bps',
           COLORS['light_grey'], fontsize=8, text_color='black')
create_box(8, 5.8, 2.2, 0.6, 'Fill Rate: 85%',
           COLORS['light_grey'], fontsize=8, text_color='black')

# === INTELLIGENCE LAYER ===
create_box(0.5, 4.5, 2.5, 0.7, 'Regime Detection\n(HMM)',
           COLORS['intelligence'], fontsize=9)
create_box(3.5, 4.5, 2.5, 0.7, 'Ensemble\nDiscovery',
           COLORS['intelligence'], fontsize=9)
create_box(6.5, 4.5, 2.5, 0.7, 'Genetic\nOptimizer',
           COLORS['intelligence'], fontsize=9)
create_box(9.5, 4.5, 2.5, 0.7, 'Bayesian\nInference',
           COLORS['intelligence'], fontsize=9)

# === ORCHESTRATION LAYER ===
create_box(0.5, 3.3, 2.3, 0.7, 'Event Bus',
           COLORS['orchestration'], fontsize=9)
create_box(3.2, 3.3, 2.3, 0.7, 'Service Mesh',
           COLORS['orchestration'], fontsize=9)
create_box(5.9, 3.3, 2.3, 0.7, 'Health Monitor',
           COLORS['orchestration'], fontsize=9)
create_box(8.6, 3.3, 2.3, 0.7, 'Degradation\nDetection',
           COLORS['orchestration'], fontsize=9)

# === MEMORY LAYER ===
create_box(1.5, 2, 3, 0.7, 'PERSISTENT MEMORY\n(GraphPalace Knowledge Graph)',
           COLORS['memory'], fontsize=10, bold=True)
create_box(5, 2, 2.5, 0.7, 'Reflection\nMemory',
           COLORS['memory'], fontsize=9)
create_box(8, 2, 2.5, 0.7, 'Checkpoint/\nRecovery',
           COLORS['memory'], fontsize=9)

# === INTERFACE LAYER ===
create_box(1, 0.7, 3, 0.7, 'Web Dashboard\n(Real-time UI)',
           COLORS['interface'], fontsize=9)
create_box(5, 0.7, 3, 0.7, 'REST API\n(FastAPI)',
           COLORS['interface'], fontsize=9)
create_box(9.5, 0.7, 3, 0.7, 'SQLite Database\n(Results Storage)',
           COLORS['interface'], fontsize=9)

# === ARROWS (Data Flow) ===
# Data to Discovery
create_arrow(2.5, 9.5, 2.5, 8.5)
create_arrow(5.75, 9.5, 5.75, 8.5)

# Discovery to Backtest
create_arrow(1.75, 8, 3.5, 7.2)
create_arrow(4.75, 8, 4.5, 7.2)
create_arrow(7.75, 8, 5.5, 7.2)

# Backtest to Intelligence
create_arrow(4, 6.8, 2.5, 5.5)
create_arrow(4, 6.8, 4.5, 5.5)
create_arrow(4, 6.8, 7.5, 5.5)

# Intelligence to Orchestration
create_arrow(1.75, 4.5, 1.65, 4.2)
create_arrow(4.75, 4.5, 4.35, 4.2)
create_arrow(7.75, 4.5, 7.05, 4.2)

# Orchestration to Memory
create_arrow(1.65, 3.3, 2.5, 2.9)
create_arrow(4.35, 3.3, 4.5, 2.9)
create_arrow(7.05, 3.3, 7.5, 2.9)

# Memory to Interface
create_arrow(3, 2, 2.5, 1.5)
create_arrow(6.25, 2, 6.5, 1.5)

# Side annotations
ax.text(13.5, 9.5, 'KEY FEATURES',
        ha='center', va='center',
        fontsize=11, fontweight='bold', color='#333333')

features = [
    '✓ Real Data Only',
    '✓ No Synthetic Data',
    '✓ Brutal Cost Realism',
    '✓ 35+ Strategy Types',
    '✓ Regime Adaptation',
    '✓ Bayesian Uncertainty',
    '✓ Persistent Memory',
    '✓ Swarm Intelligence',
    '✓ Explainable Decisions',
    '✓ Continuous Learning'
]

for i, feature in enumerate(features):
    ax.text(13.5, 8.8 - i*0.35, feature,
           ha='center', va='center',
           fontsize=9, color='#555555')

# Add version/status info
ax.text(0.5, 0.2, 'Paper Trading Only | No Real Money Risk',
        fontsize=8, color='#888888',
        bbox=dict(boxstyle="round,pad=0.3",
                 facecolor='#FFF5E6',
                 edgecolor='orange',
                 linewidth=1))

ax.text(13.5, 5.8, 'VS TRADITIONAL AI/ML:',
        ha='center', va='center',
        fontsize=10, fontweight='bold', color='#333333')

differences = [
    '• Causal vs Correlation',
    '• Uncertainty Quantified',
    '• Explainable Traces',
    '• Regime Adaptive',
    '• Persistent Learning',
    '• Multi-Scale Analysis',
    '• Swarm Validation'
]

for i, diff in enumerate(differences):
    ax.text(13.5, 5.4 - i*0.25, diff,
           ha='center', va='center',
           fontsize=8, color='#666666')

plt.tight_layout()
plt.savefig('/Users/gjw255/astrodata/SWARM/SLATE/slate_architecture.jpg',
            format='jpg', dpi=300, bbox_inches='tight',
            facecolor='white', edgecolor='none')
print("Architecture diagram saved to: slate_architecture.jpg")
plt.close()
