#!/usr/bin/env python3
"""
Test different data loading methods to see which works
"""
import pandas as pd

print("Testing data loading methods...")
print("=" * 60)

# Try 1: read_csv (current method)
try:
    print("\n1. Trying pd.read_csv():")
    df_csv = pd.read_csv('sol_data_cache/SOLUSDT_perpetual_1h_6m.csv')
    print(f"   Shape: {df_csv.shape}")
    print(f"   Columns: {df_csv.columns.tolist()[:5]}")
    print(f"   Index type: {type(df_csv.index)}")
except Exception as e:
    print(f"   ❌ Error: {e}")

# Try 2: read_json (correct method)
try:
    print("\n2. Trying pd.read_json():")
    df_json = pd.read_json('sol_data_cache/SOLUSDT_perpetual_1h_6m.csv')
    print(f"   Shape: {df_json.shape}")
    print(f"   Columns: {df_json.columns.tolist()[:5]}")
    print(f"   Index type: {type(df_json.index)}")
    print(f"   First index value: {df_json.index[0]}")

    # Check timestamp column
    if 'timestamp' in df_json.columns:
        print(f"   Timestamp column type: {type(df_json['timestamp'].iloc[0])}")

    # Try to set timestamp as index
    df_json['timestamp'] = pd.to_datetime(df_json['timestamp'])
    df_json.set_index('timestamp', inplace=True)
    print(f"   After set_index: {type(df_json.index)}")
    print(f"   First index value: {df_json.index[0]}")

    # Test timedelta calculation
    time_diff = df_json.index[5] - df_json.index[0]
    print(f"   Time diff test: {time_diff}, type: {type(time_diff)}")
    print(f"   Days attribute: {hasattr(time_diff, 'days')}")

except Exception as e:
    print(f"   ❌ Error: {e}")

print("\n" + "=" * 60)
print("CONCLUSION: The data file is JSON format, not CSV format!")
print("The startup coordinator needs to be fixed to use read_json()")