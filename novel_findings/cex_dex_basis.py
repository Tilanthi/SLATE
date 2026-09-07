"""CEX<->DEX basis arbitrage prototype (SOL/BTC/ETH, Binance vs Hyperliquid).

REAL DATA ONLY. Aligns BASKET_{coin}USDT_1h (Binance) with HYPERLIQUID_{coin}_1h
(HL) on hourly UTC timestamps, computes basis, and simulates an honest
threshold-based arb with brutal retail taker costs on BOTH venues.

Cost model mirrors slate_core/backtest/honest.py one-way cost:
  CEX one-way taker = taker_fee 0.05% + slippage 15 bps = 20.0 bps
  DEX one-way taker = taker_fee 0.045% + slippage 10 bps = 14.5 bps
A full arb ROUND TRIP (enter on both venues + exit on both) = 2 * (20 + 14.5)
= 69.0 bps of notional.

No lookahead: signal decided at the close of bar t is executed at bar t+1
(held[t+1] = target[t]). Funding is ignored (the position is hedged; net funding
~0 across venues, and including it does not rescue the strategy).
"""
from __future__ import annotations
import json
import numpy as np
import pandas as pd

CACHE = "sol_data_cache"
CEX_OW = 0.0005 + 15e-4   # 0.05% fee + 15 bps slip = 20 bps
DEX_OW = 0.00045 + 10e-4  # 0.045% fee + 10 bps slip = 14.5 bps
ROUND_TRIP = 2 * (CEX_OW + DEX_OW)   # full round-trip notional cost, frac
print(f"Round-trip notional cost: {ROUND_TRIP*1e4:.1f} bps")


def load_pair(coin: str, sym: str) -> pd.DataFrame:
    with open(f"{CACHE}/BASKET_{sym}_1h.json") as f:
        d = json.load(f)
    bn = pd.DataFrame(d)
    bn["ts"] = pd.to_datetime(bn["timestamp"])
    bn = bn.set_index("ts")[["close"]].rename(columns={"close": "c_bn"})

    with open(f"{CACHE}/HYPERLIQUID_{coin}_1h.json") as f:
        d = json.load(f)
    hl = pd.DataFrame(d)
    hl["ts"] = pd.to_datetime(hl["t"], unit="ms", utc=True).dt.tz_localize(None)
    hl = hl.set_index("ts")
    hl["c_hl"] = hl["c"].astype(float)

    df = bn.join(hl[["c_hl"]], how="inner")
    df["basis"] = (df["c_hl"] - df["c_bn"]) / df["c_bn"]   # fraction
    df["basis_bps"] = df["basis"] * 1e4
    return df


def simulate_arb(df: pd.DataFrame, entry_bps: float, exit_bps: float,
                 z_exit: bool = False) -> dict:
    """Threshold basis arb.

    - If basis_bps > +entry_bps  -> SHORT HL / LONG Binance (sell expensive HL)
      target_bn = +1, target_hl = -1
    - If basis_bps < -entry_bps  -> LONG HL / SHORT Binance
      target_bn = -1, target_hl = +1
    - Exit (flatten both legs) when |basis_bps| <= exit_bps.

    1-bar execution lag: held[t] = target[t-1]. PnL and costs computed per leg,
    summed for the arb. Both legs notional = 1 unit each; total capital
    effectively 2x, so returns reported per $ of AUM assume equal capital
    allocation to each leg (so arb return / 2).
    """
    n = len(df)
    c_bn = df["c_bn"].values.astype(float)
    c_hl = df["c_hl"].values.astype(float)
    b = df["basis_bps"].values.astype(float)

    target_bn = np.zeros(n)
    target_hl = np.zeros(n)
    pos = 0   # current position: +1 = long Binance/short HL, -1 = reverse, 0 = flat
    for t in range(n):
        # Decision at close of bar t using info through t (basis at t).
        if pos == 0:
            if b[t] > entry_bps:
                target_bn[t] = +1.0; target_hl[t] = -1.0; pos = +1
            elif b[t] < -entry_bps:
                target_bn[t] = -1.0; target_hl[t] = +1.0; pos = -1
        else:
            if abs(b[t]) <= exit_bps:
                target_bn[t] = 0.0; target_hl[t] = 0.0; pos = 0
            else:
                target_bn[t] = +1.0 * pos
                target_hl[t] = -1.0 * pos

    # 1-bar execution lag
    held_bn = np.zeros(n); held_hl = np.zeros(n)
    held_bn[1:] = target_bn[:-1]
    held_hl[1:] = target_hl[:-1]

    # Gross PnL per leg (per unit notional)
    ret_bn = np.zeros(n); ret_hl = np.zeros(n)
    ret_bn[1:] = c_bn[1:] / c_bn[:-1] - 1.0
    ret_hl[1:] = c_hl[1:] / c_hl[:-1] - 1.0
    gross_bn = held_bn * ret_bn
    gross_hl = held_hl * ret_hl

    # Costs: |dhold| * one_way per leg
    dhold_bn = np.abs(np.diff(held_bn, prepend=0.0))
    dhold_hl = np.abs(np.diff(held_hl, prepend=0.0))
    cost_bn = dhold_bn * CEX_OW
    cost_hl = dhold_hl * DEX_OW

    # Combined arb PnL per bar (each leg is 1 unit of capital; total AUM = 2 units)
    gross = gross_bn + gross_hl
    cost = cost_bn + cost_hl
    net_per_bar = gross - cost

    # Per-$-of-AUM return: capital split evenly between two legs, so divide by 2
    net_per_aum = net_per_bar / 2.0
    equity = np.cumprod(1.0 + np.nan_to_num(net_per_aum))

    ppy = 365 * 24
    n_bars = len(net_per_bar)
    mu = net_per_aum.mean(); sd = net_per_aum.std(ddof=1)
    sharpe = (mu / sd * np.sqrt(ppy)) if sd > 0 else 0.0
    total_ret = float(equity[-1] - 1.0)
    ann = float(equity[-1] ** (ppy / n_bars) - 1.0) if equity[-1] > 0 else -1.0
    # Count entries: transitions into a non-zero position
    sig = np.sign(target_bn)
    entries = (sig[1:] != sig[:-1]) & (sig[1:] != 0)
    n_entries = int(entries.sum())
    return {
        "entry_bps": entry_bps, "exit_bps": exit_bps,
        "n_entries": n_entries,
        "n_bars_in_market": int(np.sum(held_bn != 0)),
        "gross_ret_per_aum": float(gross.sum() / 2.0),
        "total_cost_per_aum": float(cost.sum() / 2.0),
        "total_ret": total_ret,
        "annualized_return": ann,
        "sharpe": float(sharpe),
        "turnover_per_aum": float((dhold_bn + dhold_hl).sum() / 2.0),
    }


def main():
    print("="*78)
    for coin, sym in [("SOL", "SOLUSDT"), ("BTC", "BTCUSDT"), ("ETH", "ETHUSDT")]:
        df = load_pair(coin, sym)
        print(f"\n### {coin}: {len(df)} bars  {df.index.min()} -> {df.index.max()}")
        b = df["basis_bps"]
        print(f"  basis mean={b.mean():+.2f} bps, std={b.std():.2f}, "
              f"median|b|={b.abs().median():.2f}, "
              f"p99|b|={b.abs().quantile(.99):.2f}, max|b|={b.abs().max():.2f}")
        print(f"  frac bars |basis| > {ROUND_TRIP*1e4/2:.0f} bps (1-way): "
              f"{(b.abs() > ROUND_TRIP*1e4/2).mean()*100:.3f}%")
        print(f"  frac bars |basis| > {ROUND_TRIP*1e4:.0f} bps (round-trip): "
              f"{(b.abs() > ROUND_TRIP*1e4).mean()*100:.3f}%")

        # Sweep entry thresholds
        print(f"\n  Arb simulation (entry threshold sweep, exit=half entry):")
        print(f"  {'entry':>7} {'exit':>6} {'trades':>7} {'bars_in':>7} "
              f"{'gross%':>9} {'cost%':>9} {'net%':>9} {'APR%':>9} {'sharpe':>7}")
        results = []
        for entry in [5, 10, 15, 20, 25, 30, 40, 50, 70]:
            exit_t = entry / 2.0
            r = simulate_arb(df, entry, exit_t)
            results.append(r)
            print(f"  {entry:>7.0f} {exit_t:>6.1f} {r['n_entries']:>7d} "
                  f"{r['n_bars_in_market']:>7d} "
                  f"{r['gross_ret_per_aum']*100:>9.2f} "
                  f"{r['total_cost_per_aum']*100:>9.2f} "
                  f"{r['total_ret']*100:>9.2f} "
                  f"{r['annualized_return']*100:>9.2f} "
                  f"{r['sharpe']:>7.2f}")
    print("\n" + "="*78)
    print("NOTE: 'net%' is total return per $ of AUM (capital split across both")
    print("legs). 'cost%' is total round-trip fees+slippage paid per $ of AUM.")


if __name__ == "__main__":
    main()
