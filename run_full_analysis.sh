#!/bin/bash
cd /Users/gjw255/astrodata/SWARM/SLATE

echo "=== STEP 1: MEGA SWEEP (5000 variants) ==="
python3 run_mega_sweep.py 2>&1

echo ""
echo "=== STEP 2: REGIME-SWITCHING PORTFOLIO ==="
python3 -c "
from slate_core.dex.data.load_data import load_candles, merge_funding
from slate_core.dex.data.hyperliquid_client import HLClient
from slate_core.portfolio.regime_switch import run_regime_switch_backtest

client = HLClient()
coins = {}
for coin in ['SOL','BTC','ETH']:
    df = load_candles(f'sol_data_cache/HYPERLIQUID_{coin}_1h.json')
    df = merge_funding(df, client, coin)
    coins[coin] = df

run_regime_switch_backtest(coins)
" 2>&1

echo ""
echo "=== STEP 3: COMMIT RESULTS ==="
git add slate_core/strategy_results.db slate_core/discovery/mega_sweep.py
git commit -m "data: mega sweep 5000 + regime-switching portfolio results" 2>/dev/null
git push origin main 2>/dev/null

echo "=== DONE ==="
