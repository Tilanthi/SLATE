#!/usr/bin/env python3
"""
Direct test of perpetual futures backtest system
"""
from slate_core.discovery.perpetual_futures_backtest import PerpetualFuturesBacktester, PerpetualBacktestConfig
import pandas as pd

# Load the market data
print("Loading market data...")
df = pd.read_json('sol_data_cache/SOLUSDT_perpetual_1d_12m.csv')
df['timestamp'] = pd.to_datetime(df['timestamp'])
df.set_index('timestamp', inplace=True)
print(f"Loaded {len(df)} rows of data with proper datetime index")

# Create a simple EMA crossover signal function for testing
def simple_ema_signal(df, i, params):
    if i < 20:
        return 0
    # Simple EMA crossover
    if df['close'].iloc[i] > df['sma_20'].iloc[i]:
        return 1  # Long
    elif df['close'].iloc[i] < df['sma_20'].iloc[i]:
        return -1  # Short
    return 0

# Create backtest config
config = PerpetualBacktestConfig(
    initial_capital=10000.0,
    max_leverage=3,
    max_position_size=0.03,
    symbol='SOLUSDT',
    timeframe='1d'
)

# Create backtester
backtester = PerpetualFuturesBacktester(config)

# Run backtest
print("Running backtest...")
result = backtester.backtest_strategy(
    df=df,
    strategy_name='test_ema_crossover',
    strategy_description='Test EMA crossover strategy',
    edge_type='test',
    signal_function=simple_ema_signal,
    parameters={}
)

print('\n=== BACKTEST RESULTS ===')
print(f'Total Trades: {result.total_trades}')
print(f'Winning Trades: {result.winning_trades}')
print(f'Losing Trades: {result.losing_trades}')
print(f'Win Rate: {result.win_rate:.2%}')
print(f'Total Profit: ${result.total_profit_usdt:.2f}')
print(f'Total Fees: ${result.total_fees_usdt:.2f}')
print(f'Total Slippage: ${result.total_slippage_usdt:.2f}')
print(f'Final Capital: ${result.final_capital:.2f}')
print(f'Initial Capital: ${result.initial_capital:.2f}')
print(f'Total Return: {result.total_return_pct:.2%}')
print(f'Max Drawdown: {result.max_drawdown_pct:.2%}')
print(f'Sharpe Ratio: {result.sharpe_ratio:.2f}')