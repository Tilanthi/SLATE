"""
Create visualizations for SOLUSDT backtest results
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime
import json
from pathlib import Path

def load_backtest_results():
    """Load backtest results and data."""

    # Load results
    with open('solusdt_ml_500_5h_rigorous_backtest_results.json', 'r') as f:
        results = json.load(f)

    # Load price data
    df = pd.read_csv('sol_data_cache/SOLUSDT_1h_1y.csv', index_col='timestamp', parse_dates=True)

    return results, df

def create_equity_curve(results):
    """Create equity curve visualization."""

    equity_curve = results['equity_curve']

    # Convert to DataFrame
    df_equity = pd.DataFrame(equity_curve)
    df_equity['timestamp'] = pd.to_datetime(df_equity['timestamp'])
    df_equity.set_index('timestamp', inplace=True)

    # Create figure
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10))

    # Plot 1: Equity Curve
    ax1.plot(df_equity.index, df_equity['capital'],
             linewidth=2, color='#2E86AB', label='Portfolio Value')

    # Add initial capital line
    ax1.axhline(y=100000, color='gray', linestyle='--', alpha=0.5,
                label='Initial Capital')

    # Add peak line
    peak_capital = df_equity['capital'].max()
    ax1.axhline(y=peak_capital, color='green', linestyle=':', alpha=0.5,
                label=f'Peak Capital: ${peak_capital:,.0f}')

    # Highlight drawdown periods
    df_equity['peak'] = df_equity['capital'].cummax()
    df_equity['drawdown_pct'] = (df_equity['peak'] - df_equity['capital']) / df_equity['peak']

    # Fill drawdown areas
    ax1.fill_between(df_equity.index, df_equity['capital'], df_equity['peak'],
                     where=df_equity['drawdown_pct'] > 0,
                     color='red', alpha=0.2, label='Drawdown')

    ax1.set_title('SOLUSDT ML-500-5h Strategy - Equity Curve', fontsize=16, fontweight='bold')
    ax1.set_ylabel('Portfolio Value ($)', fontsize=12)
    ax1.grid(True, alpha=0.3)
    ax1.legend(loc='upper left', fontsize=10)

    # Format y-axis
    ax1.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'${x/1000:.1f}K'))

    # Plot 2: Drawdown Percentage
    ax2.fill_between(df_equity.index, df_equity['drawdown_pct'] * 100,
                     color='red', alpha=0.3)
    ax2.plot(df_equity.index, df_equity['drawdown_pct'] * 100,
             color='red', linewidth=1.5)

    ax2.set_title('Drawdown Percentage', fontsize=14, fontweight='bold')
    ax2.set_xlabel('Date', fontsize=12)
    ax2.set_ylabel('Drawdown (%)', fontsize=12)
    ax2.grid(True, alpha=0.3)
    ax2.fill_between(df_equity.index, -20, df_equity['drawdown_pct'] * 100,
                     color='red', alpha=0.1)

    # Format x-axis
    for ax in [ax1, ax2]:
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
        ax.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=45)

    plt.tight_layout()

    # Save figure
    plt.savefig('solusdt_equity_curve.png', dpi=150, bbox_inches='tight')
    print("✓ Saved equity curve to solusdt_equity_curve.png")

    plt.close()

    return df_equity

def create_price_chart_with_trades(results, df):
    """Create price chart with entry/exit points."""

    trades = results['trades']

    if not trades:
        print("No trades to visualize")
        return

    # Create figure
    fig, ax = plt.subplots(figsize=(16, 10))

    # Plot price
    ax.plot(df.index, df['close'], linewidth=1.5, color='#2C3E50',
            label='SOLUSDT Price', alpha=0.8)

    # Plot entry and exit points
    long_entries = []
    long_exits = []
    short_entries = []
    short_exits = []

    for trade in trades:
        entry_time = pd.to_datetime(trade['entry_time'])
        exit_time = pd.to_datetime(trade['exit_time'])
        entry_price = trade['entry_price']
        exit_price = trade['exit_price']

        if trade['type'] == 'long':
            long_entries.append((entry_time, entry_price))
            long_exits.append((exit_time, exit_price))
        else:
            short_entries.append((entry_time, entry_price))
            short_exits.append((exit_time, exit_price))

    # Plot long entries (green triangles up)
    if long_entries:
        entry_times, entry_prices = zip(*long_entries)
        ax.scatter(entry_times, entry_prices, marker='^', s=150,
                  color='#27AE60', label=f'Long Entry ({len(long_entries)})',
                  zorder=5, edgecolors='black', linewidths=0.5)

    # Plot long exits (green circles)
    if long_exits:
        exit_times, exit_prices = zip(*long_exits)
        ax.scatter(exit_times, exit_prices, marker='o', s=100,
                  color='#27AE60', alpha=0.6, label=f'Long Exit ({len(long_exits)})',
                  zorder=4, edgecolors='black', linewidths=0.5)

    # Plot short entries (red triangles down)
    if short_entries:
        entry_times, entry_prices = zip(*short_entries)
        ax.scatter(entry_times, entry_prices, marker='v', s=150,
                  color='#E74C3C', label=f'Short Entry ({len(short_entries)})',
                  zorder=5, edgecolors='black', linewidths=0.5)

    # Plot short exits (red circles)
    if short_exits:
        exit_times, exit_prices = zip(*short_exits)
        ax.scatter(exit_times, exit_prices, marker='o', s=100,
                  color='#E74C3C', alpha=0.6, label=f'Short Exit ({len(short_exits)})',
                  zorder=4, edgecolors='black', linewidths=0.5)

    # Draw lines connecting entries to exits
    for trade in trades:
        entry_time = pd.to_datetime(trade['entry_time'])
        exit_time = pd.to_datetime(trade['exit_time'])
        entry_price = trade['entry_price']
        exit_price = trade['exit_price']

        if trade['pnl'] > 0:
            color = '#27AE60'  # Green for profit
            alpha = 0.3
        else:
            color = '#E74C3C'  # Red for loss
            alpha = 0.3

        ax.plot([entry_time, exit_time], [entry_price, exit_price],
                color=color, linewidth=1.5, alpha=alpha, linestyle='--')

    # Add title and labels
    results_data = results['results']

    title = f'SOLUSDT ML-500-5h Strategy - Price Chart with Trade Entries & Exits\n'
    title += f'Return: {results_data["total_return"]*100:+.2f}% | '
    title += f'Sharpe: {results_data["sharpe_ratio"]:.2f} | '
    title += f'Max DD: {results_data["max_drawdown"]*100:.2f}% | '
    title += f'Trades: {results_data["total_trades"]}'

    ax.set_title(title, fontsize=14, fontweight='bold')
    ax.set_xlabel('Date', fontsize=12)
    ax.set_ylabel('Price ($)', fontsize=12)
    ax.grid(True, alpha=0.3)
    ax.legend(loc='upper left', fontsize=10, framealpha=0.9)

    # Format y-axis
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'${x:.0f}'))

    # Format x-axis
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=45)

    plt.tight_layout()

    # Save figure
    plt.savefig('solusdt_price_chart_with_trades.png', dpi=150, bbox_inches='tight')
    print("✓ Saved price chart to solusdt_price_chart_with_trades.png")

    plt.close()

def create_trade_analysis(results):
    """Create trade analysis visualization."""

    trades = results['trades']

    if not trades:
        print("No trades to analyze")
        return

    # Create figure with subplots
    fig = plt.figure(figsize=(16, 12))
    gs = fig.add_gridspec(3, 2, hspace=0.3, wspace=0.3)

    # 1. Trade Returns Distribution
    ax1 = fig.add_subplot(gs[0, 0])

    returns = [t['pnl_pct'] * 100 for t in trades]
    colors = ['#27AE60' if r > 0 else '#E74C3C' for r in returns]

    ax1.bar(range(len(returns)), returns, color=colors, edgecolor='black', linewidth=0.5)
    ax1.axhline(y=0, color='black', linestyle='-', linewidth=0.5)
    ax1.set_title('Trade Returns Distribution', fontsize=12, fontweight='bold')
    ax1.set_xlabel('Trade Number')
    ax1.set_ylabel('Return (%)')
    ax1.grid(True, alpha=0.3, axis='y')

    # 2. Win/Loss Pie Chart
    ax2 = fig.add_subplot(gs[0, 1])

    win_count = sum(1 for t in trades if t['pnl'] > 0)
    loss_count = sum(1 for t in trades if t['pnl'] <= 0)

    ax2.pie([win_count, loss_count],
            labels=[f'Wins ({win_count})', f'Losses ({loss_count})'],
            colors=['#27AE60', '#E74C3C'],
            autopct='%1.1f%%',
            startangle=90,
            textprops={'fontsize': 11, 'weight': 'bold'})
    ax2.set_title('Win/Loss Distribution', fontsize=12, fontweight='bold')

    # 3. Cumulative Returns
    ax3 = fig.add_subplot(gs[1, :])

    cumulative_returns = []
    running_return = 0
    for t in trades:
        running_return += t['pnl_pct']
        cumulative_returns.append(running_return * 100)

    trade_times = [pd.to_datetime(t['entry_time']) for t in trades]

    ax3.plot(trade_times, cumulative_returns, linewidth=2, color='#2E86AB')
    ax3.axhline(y=0, color='black', linestyle='--', alpha=0.5)
    ax3.fill_between(trade_times, 0, cumulative_returns,
                     where=[r > 0 for r in cumulative_returns],
                     color='#27AE60', alpha=0.3)
    ax3.fill_between(trade_times, 0, cumulative_returns,
                     where=[r < 0 for r in cumulative_returns],
                     color='#E74C3C', alpha=0.3)

    ax3.set_title('Cumulative Returns Over Time', fontsize=12, fontweight='bold')
    ax3.set_xlabel('Date')
    ax3.set_ylabel('Cumulative Return (%)')
    ax3.grid(True, alpha=0.3)
    ax3.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
    plt.setp(ax3.xaxis.get_majorticklabels(), rotation=45)

    # 4. Trade Duration Analysis
    ax4 = fig.add_subplot(gs[2, 0])

    hold_times = [t['hold_hours'] for t in trades]
    win_times = [t['hold_hours'] for t in trades if t['pnl'] > 0]
    loss_times = [t['hold_hours'] for t in trades if t['pnl'] <= 0]

    ax4.hist(win_times, bins=20, color='#27AE60', alpha=0.6,
             label=f'Wins (avg: {np.mean(win_times):.1f}h)')
    ax4.hist(loss_times, bins=20, color='#E74C3C', alpha=0.6,
             label=f'Losses (avg: {np.mean(loss_times):.1f}h)')

    ax4.set_title('Trade Duration Distribution', fontsize=12, fontweight='bold')
    ax4.set_xlabel('Hold Time (hours)')
    ax4.set_ylabel('Frequency')
    ax4.legend()
    ax4.grid(True, alpha=0.3, axis='y')

    # 5. Confidence vs Return
    ax5 = fig.add_subplot(gs[2, 1])

    confidences = [t['confidence'] * 100 for t in trades]
    returns = [t['pnl_pct'] * 100 for t in trades]

    colors_conf = ['#27AE60' if r > 0 else '#E74C3C' for r in returns]

    ax5.scatter(confidences, returns, c=colors_conf, s=80,
               edgecolors='black', linewidths=0.5, alpha=0.7)
    ax5.axhline(y=0, color='black', linestyle='-', linewidth=0.5)

    # Add trend line
    if len(confidences) > 1:
        z = np.polyfit(confidences, returns, 1)
        p = np.poly1d(z)
        ax5.plot(confidences, p(confidences), "r--", alpha=0.5, linewidth=2)

    ax5.set_title('Prediction Confidence vs Return', fontsize=12, fontweight='bold')
    ax5.set_xlabel('Confidence (%)')
    ax5.set_ylabel('Return (%)')
    ax5.grid(True, alpha=0.3)

    plt.suptitle('SOLUSDT ML-500-5h Strategy - Trade Analysis',
                 fontsize=16, fontweight='bold', y=0.995)

    plt.savefig('solusdt_trade_analysis.png', dpi=150, bbox_inches='tight')
    print("✓ Saved trade analysis to solusdt_trade_analysis.png")

    plt.close()

def main():
    """Create all visualizations."""

    print("\n" + "=" * 80)
    print("CREATING SOLUSDT BACKTEST VISUALIZATIONS")
    print("=" * 80)

    # Load results
    print("\nLoading backtest results...")
    results, df = load_backtest_results()
    print("✓ Results loaded")

    # Create visualizations
    print("\nCreating visualizations...")

    print("\n1. Creating equity curve...")
    create_equity_curve(results)

    print("\n2. Creating price chart with trades...")
    create_price_chart_with_trades(results, df)

    print("\n3. Creating trade analysis...")
    create_trade_analysis(results)

    print("\n" + "=" * 80)
    print("✓ ALL VISUALIZATIONS CREATED")
    print("=" * 80)
    print("\nGenerated files:")
    print("  • solusdt_equity_curve.png - Portfolio value over time")
    print("  • solusdt_price_chart_with_trades.png - Price chart with entry/exit points")
    print("  • solusdt_trade_analysis.png - Detailed trade analysis")
    print("\n✓ Complete!")

if __name__ == "__main__":
    main()
