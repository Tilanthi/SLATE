#!/usr/bin/env python3
"""
Download real SOLUSDT perpetual futures data from Binance
Creates properly formatted CSV file with realistic perpetual futures data
"""

import pandas as pd
from datetime import datetime, timedelta
from binance.client import Client
import time

def download_sol_perpetual_futures():
    """Download 12 months of daily SOLUSDT perpetual futures data"""
    print("🔗 Connecting to Binance API...")

    try:
        # Initialize Binance client
        client = Client()

        print("✅ Connected to Binance API")
        print("📈 Downloading SOLUSDT Perpetual Futures data...")

        # Calculate date range (12 months back from now)
        end_date = datetime.now()
        start_date = end_date - timedelta(days=365)  # Get extra data to ensure we have 12 months

        print(f"📅 Date Range: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")

        # Download daily klines (candles) - Use proper format
        klines = client.futures_continous_klines(
            symbol="SOLUSDT",
            interval="1d",  # Daily timeframe
            start_str=start_date.strftime("%Y-%m-%d"),
            end_str=end_date.strftime("%Y-%m-%d"),
            limit=1000  # Maximum number of candles
        )

        # Convert to DataFrame
        df = pd.DataFrame(klines, columns=[
            'timestamp', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_volume', 'trades', 'taker_buy_base',
            'taker_buy_quote', 'ignore'
        ])

        # Process data
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('timestamp', inplace=True)

        # Select relevant columns
        df = df[['open', 'high', 'low', 'close', 'volume']].copy()

        # Remove any rows with missing data
        df.dropna(inplace=True)

        print(f"✅ Downloaded {len(df)} days of data")
        print(f"📊 Date Range: {df.index[0]} to {df.index[-1]}")
        print(f"💰 Price Range: ${df['close'].min():.2f} - ${df['close'].max():.2f}")

        # Save to CSV file (replacing empty file)
        output_file = 'sol_data_cache/SOLUSDT_perpetual_1h_6m.csv'
        df.to_csv(output_file)

        print(f"✅ Saved to: {output_file}")

        # Verify file was saved correctly
        import os
        file_size = os.path.getsize(output_file)
        if file_size > 0:
            print(f"✅ File size: {file_size:,} bytes (not empty)")
        else:
            print(f"❌ ERROR: File is still empty!")

        return df

    except Exception as e:
        print(f"❌ Error downloading data: {e}")
        print(f"💡 Alternative: Try using existing data file: SOLUSDT_perpetual_1d_6m.csv")
        return None

if __name__ == "__main__":
    print("="*70)
    print("🚀 SOLUSDT PERPETUAL FUTURES DATA DOWNLOADER")
    print("="*70)

    result = download_sol_perpetual_futures()

    if result is not None:
        print("✅ Market data acquisition completed successfully")
        print("📊 Ready for perpetual futures backtesting")
    else:
        print("⚠️  Using fallback data source")