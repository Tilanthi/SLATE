"""Robustness checks for CEX-DEX basis arb.

1. How much GROSS edge exists (cost = 0)? Upper bound.
2. Maker pricing on both legs (optimistic; ignores fill risk).
3. Break-even round-trip cost.
4. Sanity: lookahead-free (already enforced) and aggregate (no selection bias).
"""
from __future__ import annotations
import json
import numpy as np
import pandas as pd

CACHE = "sol_data_cache"
CEX_TAKER_OW = 0.0005 + 15e-4    # 20 bps
DEX_TAKER_OW = 0.00045 + 10e-4   # 14.5 bps
CEX_MAKER_OW = 0.0002            # 2 bps maker fee (no slip on maker; optimistic)
DEX_MAKER_OW = 0.00015           # 1.5 bps maker fee (optimistic; retail pays fee)
DEX_WHALE_OW  = -0.0001          # -1 bps rebate (whale-tier, gated)


def load_pair(coin: str, sym: str) -> pd.DataFrame:
    with open(f"{CACHE}/BASKET_{sym}_1h.json") as f:
        bn = pd.DataFrame(json.load(f))
    bn["ts"] = pd.to_datetime(bn["timestamp"])
    bn = bn.set_index("ts")[["close"]].rename(columns={"close": "c_bn"})
    with open(f"{CACHE}/HYPERLIQUID_{coin}_1h.json") as f:
        hl = pd.DataFrame(json.load(f))
    hl["ts"] = pd.to_datetime(hl["t"], unit="ms", utc=True).dt.tz_localize(None)
    hl = hl.set_index("ts")
    hl["c_hl"] = hl["c"].astype(float)
    df = bn.join(hl[["c_hl"]], how="inner")
    df["basis_bps"] = (df["c_hl"] - df["c_bn"]) / df["c_bn"] * 1e4
    return df


def simulate(df, entry_bps, exit_bps, cex_ow, dex_ow):
    n = len(df); b = df["basis_bps"].values
    c_bn = df["c_bn"].values.astype(float)
    c_hl = df["c_hl"].values.astype(float)
    tbn = np.zeros(n); thl = np.zeros(n); pos = 0
    for t in range(n):
        if pos == 0:
            if b[t] > entry_bps:
                tbn[t] = +1; thl[t] = -1; pos = +1
            elif b[t] < -entry_bps:
                tbn[t] = -1; thl[t] = +1; pos = -1
        else:
            if abs(b[t]) <= exit_bps:
                tbn[t] = 0; thl[t] = 0; pos = 0
            else:
                tbn[t] = +pos; thl[t] = -pos
    hbn = np.zeros(n); hhl = np.zeros(n)
    hbn[1:] = tbn[:-1]; hhl[1:] = thl[:-1]
    rbn = np.zeros(n); rhl = np.zeros(n)
    rbn[1:] = c_bn[1:]/c_bn[:-1] - 1
    rhl[1:] = c_hl[1:]/c_hl[:-1] - 1
    g = hbn*rbn + hhl*rhl
    dhbn = np.abs(np.diff(hbn, prepend=0)); dhhl = np.abs(np.diff(hhl, prepend=0))
    cost = dhbn*cex_ow + dhhl*dex_ow
    net = (g - cost)/2
    eq = np.cumprod(1+np.nan_to_num(net))
    ppy = 365*24
    sd = net.std(ddof=1)
    sharpe = net.mean()/sd*np.sqrt(ppy) if sd>0 else 0
    ann = eq[-1]**(ppy/len(net))-1 if eq[-1]>0 else -1
    sig = np.sign(tbn)
    entries = (sig[1:]!=sig[:-1]) & (sig[1:]!=0)
    n_trades = int(entries.sum())
    return {"n_trades": n_trades, "gross%": g.sum()/2*100,
            "cost%": cost.sum()/2*100, "net%": (eq[-1]-1)*100,
            "APR%": ann*100, "sharpe": sharpe}


def main():
    print("="*78)
    print("ROBUSTNESS: CEX<->DEX basis arb\n")
    for coin, sym in [("SOL","SOLUSDT"),("BTC","BTCUSDT"),("ETH","ETHUSDT")]:
        df = load_pair(coin, sym)
        print(f"\n### {coin}  ({len(df)} hourly bars)")
        print(f"{'scheme':<32}{'entry':>6}{'trades':>8}{'gross%':>9}"
              f"{'cost%':>9}{'net%':>9}{'APR%':>9}{'sharpe':>8}")
        for entry in [5, 10, 15, 20]:
            exit_t = entry/2
            r = simulate(df, entry, exit_t, 0.0, 0.0)
            print(f"{'zero-cost ceiling':<32}{entry:>6}{r['n_trades']:>8}"
                  f"{r['gross%']:>9.2f}{0.0:>9.2f}{r['gross%']:>9.2f}"
                  f"{r['APR%']:>9.2f}{r['sharpe']:>8.2f}")
            r = simulate(df, entry, exit_t, CEX_MAKER_OW, DEX_MAKER_OW)
            print(f"{'maker-maker (OPTIMISTIC)':<32}{entry:>6}{r['n_trades']:>8}"
                  f"{r['gross%']:>9.2f}{r['cost%']:>9.2f}{r['net%']:>9.2f}"
                  f"{r['APR%']:>9.2f}{r['sharpe']:>8.2f}")
            r = simulate(df, entry, exit_t, CEX_MAKER_OW, DEX_WHALE_OW)
            print(f"{'cex-maker/dex-whale (UNREAL)':<32}{entry:>6}{r['n_trades']:>8}"
                  f"{r['gross%']:>9.2f}{r['cost%']:>9.2f}{r['net%']:>9.2f}"
                  f"{r['APR%']:>9.2f}{r['sharpe']:>8.2f}")
            r = simulate(df, entry, exit_t, CEX_TAKER_OW, DEX_TAKER_OW)
            print(f"{'taker-taker (HONEST retail)':<32}{entry:>6}{r['n_trades']:>8}"
                  f"{r['gross%']:>9.2f}{r['cost%']:>9.2f}{r['net%']:>9.2f}"
                  f"{r['APR%']:>9.2f}{r['sharpe']:>8.2f}")
            print()

    # Break-even analysis: what round-trip cost would make entry=10bps strategy break even?
    print("="*78)
    print("BREAK-EVEN ROUND-TRIP COST (entry=10bps, exit=5bps)")
    print(f"{'coin':<6}{'gross bps/trade':>18}{'break-even RT (bps)':>22}"
          f"{'actual RT (bps)':>18}{'verdict':>12}")
    for coin, sym in [("SOL","SOLUSDT"),("BTC","BTCUSDT"),("ETH","ETHUSDT")]:
        df = load_pair(coin, sym)
        r = simulate(df, 10, 5, 0.0, 0.0)
        if r["n_trades"] > 0:
            gross_per_trade_bps = r["gross%"]*100 / r["n_trades"] * 2  # to bps of notional
            # actual round-trip cost in bps of notional: 2*(cex_ow + dex_ow)*1e4
            actual_rt = 2*(CEX_TAKER_OW + DEX_TAKER_OW)*1e4
            verdict = "PROFIT" if gross_per_trade_bps > actual_rt else "LOSS"
            print(f"{coin:<6}{gross_per_trade_bps:>18.2f}{gross_per_trade_bps:>22.2f}"
                  f"{actual_rt:>18.1f}{verdict:>12}")


if __name__ == "__main__":
    main()
