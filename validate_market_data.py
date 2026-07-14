#!/usr/bin/env python3
import pandas as pd
import json

print('📊 Loading market data...')
with open('sol_data_cache/SOLUSDT_perpetual_1h_6m.csv', 'r') as f:
    data_lines = f.readlines()

# Parse JSON data from each line
all_data = []
for line in data_lines:
    line = line.strip()
    if line:
        try:
            data_list = json.loads(line)
            if isinstance(data_list, list):
                all_data.extend(data_list)
        except:
            continue

df = pd.DataFrame(all_data)
df['timestamp'] = pd.to_datetime(df['timestamp'])
df = df.sort_values('timestamp')
df.set_index('timestamp', inplace=True)

print(f'✅ Loaded {len(df)} days of data')
print(f'📅 Date Range: {df.index[0]} to {df.index[-1]}')
print(f'💰 Price Range: ${df["close"].min():.2f} - ${df["close"].max():.2f}')
print(f'📈 Volume: {df["volume"].mean():,.0f} average')

# Validate required columns for backtest
required_cols = ['open', 'high', 'low', 'close', 'volume']
available_cols = df.columns.tolist()

missing_cols = set(required_cols) - set(available_cols)
if missing_cols:
    print(f'❌ Missing required columns: {missing_cols}')
else:
    print(f'✅ All required columns present: {required_cols}')

# Check for indicators
indicators = ['atr', 'rsi', 'macd', 'bollinger_upper', 'bollinger_lower', 'sma_20', 'funding_rate']
available_indicators = [col for col in indicators if col in available_cols]
print(f'📊 Technical indicators available: {available_indicators}')

print(f'📊 Data quality check:')
print(f'  - No missing values: {df.isnull().sum().sum() == 0}')
print(f'  - Duplicate timestamps: {df.index.duplicated().sum()}')
print(f'  - Data completeness: {len(df) / 252 * 100:.1f}% of annual trading days')

print('✅ Market data validation complete!')
