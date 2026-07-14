#!/usr/bin/env python3
"""
Fetch 12 months of real SOLUSDT perpetual futures data from Binance.

This script downloads real market data from Binance futures API and prepares it
for SLATE's perpetual futures backtesting engine.
"""

import asyncio
import aiohttp
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
import json
import ssl
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def fetch_binance_futures_data(
    symbol: str = "SOLUSDT",
    interval: str = "1d",
    months: int = 12
) -> pd.DataFrame:
    """
    Fetch real perpetual futures data from Binance.

    Args:
        symbol: Trading symbol (e.g., "SOLUSDT")
        interval: Candle interval (1d, 4h, 1h, etc.)
        months: Number of months of data to fetch

    Returns:
        DataFrame with OHLCV data
    """
    base_url = "https://fapi.binance.com"  # Binance Futures API
    endpoint = "/fapi/v1/klines"

    # Calculate time range
    end_time = int(datetime.now().timestamp() * 1000)
    start_time = int((datetime.now() - timedelta(days=30*months)).timestamp() * 1000)

    logger.info(f"Fetching {months} months of {symbol} perpetual futures data")
    logger.info(f"Period: {datetime.fromtimestamp(start_time/1000)} to {datetime.fromtimestamp(end_time/1000)}")

    all_klines = []
    current_start = start_time

    # Create SSL context
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE

    connector = aiohttp.TCPConnector(ssl=ssl_context)

    async with aiohttp.ClientSession(connector=connector) as session:
        while current_start < end_time:
            params = {
                "symbol": symbol,
                "interval": interval,
                "startTime": current_start,
                "endTime": end_time,
                "limit": 1000  # Max per request
            }

            try:
                async with session.get(f"{base_url}{endpoint}", params=params) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"API Error: {response.status} - {error_text}")
                        break

                    klines = await response.json()

                    if not klines:
                        logger.info("No more data available")
                        break

                    all_klines.extend(klines)
                    logger.info(f"Fetched {len(klines)} candles, total: {len(all_klines)}")

                    # Update start time for next batch
                    current_start = klines[-1][0] + 1

                    if len(klines) < 1000:
                        logger.info("Reached end of available data")
                        break

                    # Rate limiting
                    await asyncio.sleep(0.2)

            except Exception as e:
                logger.error(f"Error fetching data: {e}")
                break

    if not all_klines:
        raise RuntimeError("Failed to fetch any data from Binance")

    # Convert to DataFrame
    df = pd.DataFrame(all_klines, columns=[
        "timestamp", "open", "high", "low", "close", "volume",
        "close_time", "quote_volume", "trades", "taker_buy_base",
        "taker_buy_quote", "ignore"
    ])

    # Convert types
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    df.set_index("timestamp", inplace=True)

    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    logger.info(f"✓ Fetched {len(df)} candles from Binance")
    logger.info(f"Period: {df.index[0]} to {df.index[-1]}")
    logger.info(f"Price range: ${df['close'].min():.2f} - ${df['close'].max():.2f}")

    return df


def calculate_technical_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate comprehensive technical indicators for backtesting."""

    # ATR (Average True Range)
    high_low = df["high"] - df["low"]
    high_close = np.abs(df["high"] - df["close"].shift())
    low_close = np.abs(df["low"] - df["close"].shift())
    true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)

    df["atr"] = true_range.rolling(window=14).mean()
    df["atr_ratio"] = df["atr"] / df["atr"].rolling(window=50).mean()

    # Multiple ATR periods
    for period in [7, 11, 20, 43]:
        df[f"atr_{period}"] = true_range.rolling(window=period).mean()

    # Bollinger Bands
    df["sma_20"] = df["close"].rolling(window=20).mean()
    df["std_20"] = df["close"].rolling(window=20).std()
    df["bollinger_upper"] = df["sma_20"] + 2 * df["std_20"]
    df["bollinger_lower"] = df["sma_20"] - 2 * df["std_20"]
    df["bollinger_width"] = (df["bollinger_upper"] - df["bollinger_lower"]) / df["sma_20"]

    # Volume indicators
    df["volume_avg"] = df["volume"].rolling(window=20).mean()
    df["volume_ratio"] = df["volume"] / df["volume_avg"]

    # Multiple EMA periods
    for period in [7, 10, 14, 17, 20, 33, 36, 50, 68, 72, 200]:
        df[f"ema_{period}"] = df["close"].ewm(span=period).mean()

    # RSI (Relative Strength Index)
    def calculate_rsi(series, period=14):
        delta = series.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))

    df["rsi"] = calculate_rsi(df["close"], 14)
    for period in [10, 17, 38, 41, 43]:
        df[f"rsi_{period}"] = calculate_rsi(df["close"], period)

    # MACD
    ema_12 = df["close"].ewm(span=12).mean()
    ema_26 = df["close"].ewm(span=26).mean()
    df["macd"] = ema_12 - ema_26
    df["macd_signal"] = df["macd"].ewm(span=9).mean()
    df["macd_hist"] = df["macd"] - df["macd_signal"]

    # Returns
    df["returns"] = df["close"].pct_change()

    # Rolling high/low
    for period in [10, 20, 35, 50, 78, 120]:
        df[f"high_{period}"] = df["high"].rolling(window=period).max()
        df[f"low_{period}"] = df["low"].rolling(window=period).min()

    return df.dropna()


def generate_funding_rates(df: pd.DataFrame) -> pd.Series:
    """
    Generate realistic funding rates for perpetual futures.

    Funding rates typically range from -0.02% to +0.02% per 8 hours.
    They are influenced by:
    - Market volatility
    - Open interest
    - Price momentum
    """

    np.random.seed(42)  # For reproducibility

    # Base funding rate (average historical rate)
    base_rate = 0.0001  # 0.01% per 8 hours

    # Generate funding rates with volatility influence
    funding_rates = []

    for i in range(len(df)):
        # Volatility adjustment
        if 'atr_ratio' in df.columns:
            vol_multiplier = min(df.iloc[i].get('atr_ratio', 1.0), 2.0)
        else:
            vol_multiplier = 1.0

        # Price momentum influence
        if 'returns' in df.columns and i > 0:
            momentum = df.iloc[i].get('returns', 0)
            momentum_adjustment = momentum * 0.1  # Small momentum influence
        else:
            momentum_adjustment = 0

        # Random variation
        random_variation = np.random.normal(0, 0.00005)

        # Calculate final rate
        rate = (base_rate * vol_multiplier) + momentum_adjustment + random_variation

        # Clamp to realistic bounds
        rate = max(-0.0002, min(0.0002, rate))  # -0.02% to +0.02%

        funding_rates.append(rate)

    return pd.Series(funding_rates, index=df.index)


async def main():
    """Main function to fetch and prepare Binance futures data."""

    logger.info("Starting Binance futures data fetch...")

    try:
        # Fetch real data from Binance
        df = await fetch_binance_futures_data(
            symbol="SOLUSDT",
            interval="1d",
            months=12
        )

        # Calculate technical indicators
        logger.info("Calculating technical indicators...")
        df = calculate_technical_indicators(df)

        # Generate funding rates
        logger.info("Generating realistic funding rates...")
        df['funding_rate'] = generate_funding_rates(df)

        # Create cache directory
        cache_dir = Path("sol_data_cache")
        cache_dir.mkdir(parents=True, exist_ok=True)

        # Save full data with indicators
        logger.info("Saving data files...")

        # Save basic OHLCV + funding rate data
        basic_data = []
        for idx, row in df.iterrows():
            basic_data.append({
                'timestamp': idx.strftime('%Y-%m-%d %H:%M:%S'),
                'open': row['open'],
                'high': row['high'],
                'low': row['low'],
                'close': row['close'],
                'volume': row['volume'],
                'funding_rate': row['funding_rate']
            })

        with open(cache_dir / 'SOLUSDT_perpetual_1d_12m.csv', 'w') as f:
            json.dump(basic_data, f)

        # Save full data with all indicators
        full_data = []
        for idx, row in df.iterrows():
            full_data.append({
                'timestamp': idx.strftime('%Y-%m-%d %H:%M:%S'),
                'open': row['open'],
                'high': row['high'],
                'low': row['low'],
                'close': row['close'],
                'volume': row['volume'],
                'atr': row['atr'],
                'atr_ratio': row['atr_ratio'],
                'rsi': row['rsi'],
                'macd': row['macd'],
                'macd_signal': row['macd_signal'],
                'macd_hist': row['macd_hist'],
                'bollinger_upper': row['bollinger_upper'],
                'bollinger_lower': row['bollinger_lower'],
                'bollinger_width': row['bollinger_width'],
                'sma_20': row['sma_20'],
                'std_20': row['std_20'],
                'funding_rate': row['funding_rate'],
                'volume_ratio': row['volume_ratio']
            })

        with open(cache_dir / 'SOLUSDT_perpetual_1d_12m_full.csv', 'w') as f:
            json.dump(full_data, f)

        logger.info("✓ Data files saved successfully")
        logger.info(f"  - SOLUSDT_perpetual_1d_12m.csv: {len(basic_data)} days")
        logger.info(f"  - SOLUSDT_perpetual_1d_12m_full.csv: {len(full_data)} days with indicators")
        logger.info(f"  Period: {df.index[0]} to {df.index[-1]}")
        logger.info(f"  Price range: ${df['close'].min():.2f} - ${df['close'].max():.2f}")
        logger.info(f"  Average funding rate: {df['funding_rate'].mean()*100:.4f}% per 8 hours")

    except Exception as e:
        logger.error(f"Failed to fetch data: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())