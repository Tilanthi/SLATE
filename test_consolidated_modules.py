#!/usr/bin/env python3
"""
Test script for consolidated SLATE modules
Verifies the new unified modules work correctly
"""

import sys
sys.path.insert(0, '/Users/gjw255/astrodata/SWARM/SLATE')

# Import modules directly to avoid dependency issues
from slate_core.data.binance_fetcher import BinanceFetcher
from slate_core.indicators.volume_imbalance import VolumeImbalance
from slate_core.backtest.engine import BacktestEngine, BacktestConfig

print("=" * 60)
print("Testing Consolidated SLATE Modules")
print("=" * 60)

# Test 1: Data fetching
print("\n1. Testing unified data fetcher...")
fetcher = BinanceFetcher()
df = fetcher.fetch_months(symbol="BTCUSDT", interval="1h", months_back=1)
print(f"   ✓ Fetched {len(df)} candles")
print(f"   ✓ Price range: ${df['close'].min():,.2f} - ${df['close'].max():,.2f}")

# Test 2: VI calculation
print("\n2. Testing Volume Imbalance calculator...")
vi_calc = VolumeImbalance(period=12)
vi = vi_calc.calculate(df)
print(f"   ✓ VI calculated for {len(vi)} candles")
print(f"   ✓ VI range: {vi.min():.2f} to {vi.max():.2f}")

# Test 3: Backtest engine
print("\n3. Testing unified backtest engine...")
config = BacktestConfig(
    vi_period=12,
    vi_threshold=0.30,
    initial_capital=10000,
    lot_size=0.01
)
engine = BacktestEngine(config)
results = engine.run(df, verbose=False)

print(f"   ✓ Backtest complete")
print(f"   ✓ Trades: {results.total_trades}")
print(f"   ✓ Final Capital: ${results.final_capital:,.2f}")
print(f"   ✓ Return: {results.total_return*100:+.2f}%")
print(f"   ✓ Win Rate: {results.win_rate:.1%}")

print("\n" + "=" * 60)
print("All modules working correctly!")
print("=" * 60)
