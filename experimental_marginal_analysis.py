#!/usr/bin/env python3
"""
Experimental Marginal Timeframe Analysis
Analyzes the barely-profitable 8h and 12h timeframes to determine if they represent
genuine opportunities or statistical noise.
"""

import sqlite3
import statistics
from typing import List, Dict

def analyze_marginal_timeframes():
    """Analyze marginal timeframe profitability"""

    conn = sqlite3.connect('/Users/gjw255/astrodata/SWARM/SLATE/slate_core/slate_realistic_discoveries.db')
    cursor = conn.cursor()

    print('🔬 EXPERIMENTAL MARGINAL TIMEFRAME ANALYSIS')
    print('=' * 70)

    for timeframe in ['12h', '8h']:
        # Get profitable strategies for this timeframe
        cursor.execute(f'SELECT * FROM edge_discoveries WHERE timeframe = ? AND total_profit_usdt > 0', (timeframe,))
        rows = cursor.fetchall()

        if rows:
            # Get column names
            columns = [description[0] for description in cursor.description]

            print(f'\n📊 {timeframe} Timeframe - "Profitable" Strategies Analysis:')
            print('-' * 70)

            profits = []
            returns = []
            sharpes = []
            win_rates = []

            for row in rows:
                profit_dict = dict(zip(columns, row))
                profits.append(profit_dict['total_profit_usdt'])
                returns.append(profit_dict['total_return_pct'])
                sharpes.append(profit_dict['sharpe_ratio'])
                win_rates.append(profit_dict['win_rate'])

            # Statistical analysis
            print(f'Total "Profitable" Strategies: {len(profits)}')
            print(f'\nProfit Statistics (USDT):')
            print(f'  Mean: ${statistics.mean(profits):.2f}')
            print(f'  Median: ${statistics.median(profits):.2f}')
            print(f'  Max: ${max(profits):.2f}')
            print(f'  Min: ${min(profits):.2f}')
            print(f'  Std Dev: ${statistics.stdev(profits) if len(profits) > 1 else 0:.2f}')

            print(f'\nReturn Statistics (%):')
            print(f'  Mean: {statistics.mean(returns):.3f}%')
            print(f'  Median: {statistics.median(returns):.3f}%')
            print(f'  Max: {max(returns):.3f}%')
            print(f'  Min: {min(returns):.3f}%')

            print(f'\nRisk Metrics:')
            print(f'  Mean Sharpe Ratio: {statistics.mean(sharpes):.2f}')
            print(f'  Mean Win Rate: {statistics.mean(win_rates):.2%}')

            # Check for statistical significance
            if len(profits) >= 30:
                # Rough check for statistical significance
                mean_profit = statistics.mean(profits)
                std_dev = statistics.stdev(profits)

                # Simple t-test approximation
                t_stat = mean_profit / (std_dev / (len(profits) ** 0.5))

                print(f'\nStatistical Significance Check:')
                print(f'  T-Statistic: {t_stat:.2f}')
                print(f'  Sample Size: {len(profits)}')

                if t_stat > 2.0:
                    print(f'  ✅ POTENTIALLY SIGNIFICANT (t > 2.0)')
                else:
                    print(f'  ❌ LIKELY STATISTICAL NOISE (t < 2.0)')
            else:
                print(f'\n⚠️  INSUFFICIENT SAMPLE SIZE for statistical significance (need 30+, have {len(profits)})')

    # Compare with daily timeframe profitability
    print(f'\n' + '=' * 70)
    print('COMPARISON WITH DAILY TIMEFRAME:')
    print('-' * 70)

    cursor.execute('SELECT total_profit_usdt FROM edge_discoveries WHERE timeframe = "1d" AND total_profit_usdt > 0')
    daily_profits = [row[0] for row in cursor.fetchall()]

    if daily_profits:
        print(f'Daily (1d) Profitable Strategies: {len(daily_profits)}')
        print(f'  Mean Profit: ${statistics.mean(daily_profits):.2f}')
        print(f'  Median Profit: ${statistics.median(daily_profits):.2f}')
        print(f'  Max Profit: ${max(daily_profits):.2f}')
        print(f'  Success Rate: {len(daily_profits)/22518*100:.1f}%')

    conn.close()

if __name__ == '__main__':
    analyze_marginal_timeframes()