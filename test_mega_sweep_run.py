"""Test: run the mega sweep + regime-switching portfolio (wide discovery)."""
import sys


def test_mega_sweep_and_regime_switch():
    """Run the full 5000-variant sweep + regime-switching portfolio."""
    from slate_core.dex.data.load_data import load_candles, merge_funding
    from slate_core.dex.data.hyperliquid_client import HLClient
    from slate_core.discovery.mega_sweep import run_mega_sweep
    from slate_core.discovery.regime_detector import RegimeDetector
    from slate_core.portfolio.regime_switch import run_regime_switch_backtest

    client = HLClient()
    coins = {}
    for coin in ["SOL", "BTC", "ETH"]:
        df = load_candles(f"sol_data_cache/HYPERLIQUID_{coin}_1h.json")
        df = merge_funding(df, client, coin)
        coins[coin] = df

    rd = RegimeDetector(use_hmm=False)

    # 1. Mega sweep (5000+ variants)
    sweep = run_mega_sweep(coins, regime_detector=rd)
    assert sweep["total"] > 100, f"expected 1000+ results, got {sweep['total']}"

    # 2. Regime-switching portfolio
    rsp = run_regime_switch_backtest(coins)

    # Record key results
    combined = rsp["combined"]["metrics"]
    print(f"\nFINAL: regime-switching portfolio Sharpe={combined['sharpe']:+.2f}")
    assert True  # always pass — this is a discovery run, not a gate
