"""Run the honest LP backtest on the real-pool basket.

For each pool: real fee yield (DefiLlama apyBase) minus IL computed from the real
token price-ratio path (BTC/ETH from Hyperliquid; stables ~1). Reports the LP-vs-
HODL alpha (fees - IL), the absolute LP return, and the HODL benchmark, plus the
concentration ('volume-in-range') variant.
"""
from __future__ import annotations

import json
import numpy as np
import pandas as pd

from slate_core.backtest.lp import backtest_lp
from slate_core.dex.data.load_data import load_candles


def daily_close(sym):
    """Daily close from Binance (4yr), date-normalized index for clean alignment."""
    df = pd.read_json(f"sol_data_cache/AMM_{sym}_1d.json")
    df.index = pd.to_datetime(df.index).tz_localize(None).normalize()
    return df["close"].sort_index()


def main():
    summary = json.load(open("sol_data_cache/amm_basket_summary.json"))
    eth = daily_close("ETHUSDT")
    btc = daily_close("BTCUSDT")

    # map pool token-set -> price ratio series (or None for stables)
    def ratio_for(symbol):
        s = symbol.upper().replace("-", "")
        if "WETH" in s and "WBTC" not in s:
            return eth, "ETH"
        if "WBTC" in s and "WETH" not in s:
            return btc, "BTC"
        if "WBTC" in s and "WETH" in s:
            r = (btc / eth).dropna(); return r, "BTC/ETH"
        return None, "stable"

    print("=" * 94)
    print("HONEST LP BACKTEST — real fees (DefiLlama) minus real IL (price path)")
    print("=" * 94)
    print(f"{'pool':18s} {'chain':10s} {'fee_apr':>8s} {'termIL':>8s} {'maxIL':>8s} "
          f"{'net_vs_HODL':>12s} {'abs_LP':>9s} {'HODL':>9s} {'days':>5s}")
    for p in summary:
        pr, ref = ratio_for(p["symbol"])
        r = backtest_lp(p["pool"], price_ratio=pr)
        print(f"{p['symbol']:18s} {p['chain']:10s} {r.fee_apr_pct:7.2f}% "
              f"{r.terminal_il_pct:7.2f}% {r.max_il_pct:7.2f}% "
              f"{r.net_excess_apr_pct:+11.2f}% {r.abs_return_pct:+8.1f}% "
              f"{r.hodl_return_pct:+8.1f}% {r.days:5d}")

    print("\n--- concentration (volume-in-range) sweep on the WETH-USDC pool ---")
    weth = [p for p in summary if p["symbol"] == "USDC-WETH"][0]
    for band in [None, 0.10, 0.25, 0.50]:
        r = backtest_lp(weth["pool"], price_ratio=eth, band=band,
                        il_mult=1.0 if band is None else 2.0)
        tag = "full-range" if band is None else f"±{int(band*100)}% band"
        print(f"  {tag:16s}: fee_apr={r.fee_apr_pct:6.2f}%  net_vs_HODL={r.net_excess_apr_pct:+6.2f}%  "
              f"abs_LP={r.abs_return_pct:+7.1f}%  HODL={r.hodl_return_pct:+7.1f}%")


if __name__ == "__main__":
    main()
