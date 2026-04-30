"""
Fetch 1 year of SOLUSDT perpetuals data from Binance
"""

import pandas as pd
import requests
from datetime import datetime, timedelta
from pathlib import Path
import time

def fetch_solusdt_perpetual_data(interval='1h', years=1):
    """Fetch SOLUSDT perpetual futures data from Binance."""

    print("Fetching SOLUSDT perpetual data from Binance...")
    print(f"Interval: {interval}, Period: {years} year(s)")

    # Calculate time range
    end_time = datetime.now()
    start_time = end_time - timedelta(days=365*years)

    # Binance Futures API
    base_url = "https://fapi.binance.com"

    # Convert to milliseconds
    start_ms = int(start_time.timestamp() * 1000)
    end_ms = int(end_time.timestamp() * 1000)

    all_klines = []
    current_time = start_ms

    while current_time < end_ms:
        # Fetch klines (candlestick data)
        params = {
            'symbol': 'SOLUSDT',
            'interval': interval,
            'startTime': current_time,
            'endTime': end_ms,
            'limit': 1500  # Max per request
        }

        try:
            response = requests.get(f"{base_url}/fapi/v1/klines", params=params, timeout=10)
            response.raise_for_status()
            klines = response.json()

            if not klines:
                break

            all_klines.extend(klines)

            # Move to next batch
            current_time = klines[-1][0] + 1

            print(f"  Fetched {len(klines)} candles, total: {len(all_klines)}")

            # Rate limit
            time.sleep(0.2)

        except Exception as e:
            print(f"Error fetching data: {e}")
            break

    # Convert to DataFrame
    df = pd.DataFrame(all_klines, columns=[
        'timestamp', 'open', 'high', 'low', 'close', 'volume',
        'close_time', 'quote_volume', 'trades', 'taker_buy_base',
        'taker_buy_quote', 'ignore'
    ])

    # Convert types
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    df['open'] = df['open'].astype(float)
    df['high'] = df['high'].astype(float)
    df['low'] = df['low'].astype(float)
    df['close'] = df['close'].astype(float)
    df['volume'] = df['volume'].astype(float)

    # Set timestamp as index
    df.set_index('timestamp', inplace=True)

    # Remove duplicates
    df = df[~df.index.duplicated(keep='first')]

    # Sort by timestamp
    df.sort_index(inplace=True)

    print(f"\n✓ Successfully fetched {len(df)} candles")
    print(f"  Date range: {df.index[0]} to {df.index[-1]}")
    print(f"  Price range: ${df['low'].min():.2f} - ${df['high'].max():.2f}")

    return df

if __name__ == "__main__":
    # Create cache directory
    cache_dir = Path("sol_data_cache")
    cache_dir.mkdir(exist_ok=True)

    # Fetch data
    df = fetch_solusdt_perpetual_data(interval='1h', years=1)

    # Cache to CSV
    cache_file = cache_dir / "SOLUSDT_1h_1y.csv"
    df.to_csv(cache_file)
    print(f"\n✓ Data cached to {cache_file}")
