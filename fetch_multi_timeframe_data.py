#!/usr/bin/env python3
"""
Fetch REAL SOLUSDT data from Binance for ALL required timeframes.
Timeframes: 1m, 5m, 10m, 15m, 30m, 1h, 4h, 8h, 12h, 1d
"""

import pandas as pd
from datetime import datetime, timedelta
import time
from pathlib import Path

def fetch_binance_klines(symbol, interval, days=365):
    """Fetch kline data from Binance."""
    import requests

    base_url = "https://api.binance.com/api/v3/klines"

    # Calculate timestamps
    end_time = int(datetime.now().timestamp() * 1000)
    start_time = int((datetime.now() - timedelta(days=days)).timestamp() * 1000)

    all_klines = []
    current_start = start_time

    print(f"  Fetching {interval} data from {datetime.fromtimestamp(start_time/1000)}...")

    while current_start < end_time:
        params = {
            "symbol": symbol,
            "interval": interval,
            "startTime": current_start,
            "endTime": end_time,
            "limit": 1000  # Binance max limit
        }

        try:
            response = requests.get(base_url, params=params, timeout=10)
            response.raise_for_status()
            klines = response.json()

            if not klines:
                break

            all_klines.extend(klines)
            current_start = klines[-1][0] + 1  # Next timestamp after last candle

            # Rate limiting
            time.sleep(0.1)

        except Exception as e:
            print(f"  Error fetching {interval}: {e}")
            break

    # Convert to DataFrame
    if all_klines:
        df = pd.DataFrame(all_klines, columns=[
            'timestamp', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_volume', 'trades', 'taker_buy_base',
            'taker_buy_quote', 'ignore'
        ])

        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df = df.set_index('timestamp')

        # Convert to numeric
        for col in ['open', 'high', 'low', 'close', 'volume']:
            df[col] = pd.to_numeric(df[col], errors='coerce')

        # Sort by timestamp
        df = df.sort_index()

        print(f"  ✓ Fetched {len(df)} candles for {interval}")
        return df
    else:
        print(f"  ✗ No data fetched for {interval}")
        return None

def main():
    symbol = "SOLUSDT"
    timeframes = ['1m', '5m', '10m', '15m', '30m', '1h', '4h', '8h', '12h', '1d']

    # Create data directory
    data_dir = Path("sol_data_cache")
    data_dir.mkdir(exist_ok=True)

    print(f"Fetching REAL data from Binance for {symbol}")
    print(f"Timeframes: {', '.join(timeframes)}")
    print(f"Period: 1 year (365 days)")
    print("=" * 60)

    for timeframe in timeframes:
        df = fetch_binance_klines(symbol, timeframe, days=365)

        if df is not None:
            # Save to CSV
            filename = f"SOLUSDT_{timeframe}_1y.csv"
            filepath = data_dir / filename
            df.to_csv(filepath)
            print(f"  ✓ Saved to {filepath}")

            # Print stats
            print(f"    Range: {df.index[0]} to {df.index[-1]}")
            print(f"    Price: ${df['close'].min():.2f} - ${df['close'].max():.2f}")
        else:
            print(f"  ✗ Failed to fetch {timeframe}")

        print()

    print("=" * 60)
    print("✓ Data fetching complete!")
    print(f"Files saved to: {data_dir.absolute()}")

if __name__ == "__main__":
    main()
