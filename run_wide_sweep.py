"""Run the wide strategy sweep across SOL/BTC/ETH with regime analysis."""
from slate_core.dex.data.load_data import load_candles, merge_funding
from slate_core.dex.data.hyperliquid_client import HLClient
from slate_core.discovery.wide_sweep import run_wide_sweep
from slate_core.discovery.regime_detector import RegimeDetector

client = HLClient()
coins = {}
for coin in ["SOL", "BTC", "ETH"]:
    df = load_candles(f"sol_data_cache/HYPERLIQUID_{coin}_1h.json")
    df = merge_funding(df, client, coin)
    coins[coin] = df
    print(f"loaded {coin}: {len(df)} bars")

# Run with simple regime detector first (fast)
rd = RegimeDetector(use_hmm=False)
results = run_wide_sweep(coins, regime_detector=rd)
