"""Fetch REAL concentrated-liquidity pool data from DefiLlama (keyless).

DefiLlama's yields API exposes, per pool, a full daily history of:
  apy / apyBase     — realized FEE yield (from actual swap fees), annualized
  il7d              — realized 7-day IMPERMANENT LOSS
  tvlUsd            — real total value locked
  pricePerShare     — LP-share price evolution
This is REAL data (aggregated from on-chain by DefiLlama) — not the vol-scaled
synthetic proxy the old `amm/pool_data.py` used. It lets us backtest LP honestly.

We pick a basket of Uniswap-V3 pools (stablecoin pairs = low IL; volatile pairs
= high IL) across chains, fetch each pool's history, and cache it.
"""
from __future__ import annotations

import json
import os
import time
from typing import Dict, List

import requests

CACHE = "sol_data_cache"
POOLS_INDEX = f"{CACHE}/amm_pools_index.json"


def fetch_pools_index() -> List[dict]:
    if os.path.exists(POOLS_INDEX):
        return json.load(open(POOLS_INDEX))
    r = requests.get("https://yields.llama.fi/pools", timeout=40)
    data = r.json()["data"]
    json.dump(data, open(POOLS_INDEX, "w"))
    return data


def pick_basket(pools: List[dict]) -> List[dict]:
    """Token-level (order-independent) match on Uniswap V3, highest TVL each."""
    def toks(s):
        return set(t.strip().upper() for t in (s or "").replace(",", "-").split("-") if t.strip())
    # (frozenset of tokens, project, chain)
    targets = {
        (frozenset(["USDC", "USDT"]), "uniswap-v3", "Ethereum"),
        (frozenset(["USDC", "USDT"]), "uniswap-v3", "Arbitrum"),
        (frozenset(["DAI", "USDC"]), "uniswap-v3", "Ethereum"),
        (frozenset(["WETH", "USDC"]), "uniswap-v3", "Ethereum"),
        (frozenset(["WETH", "USDT"]), "uniswap-v3", "Ethereum"),
        (frozenset(["WBTC", "WETH"]), "uniswap-v3", "Ethereum"),
        (frozenset(["WBTC", "USDC"]), "uniswap-v3", "Ethereum"),
        (frozenset(["USDC", "USDT"]), "curve", "Ethereum"),      # stable AMM baseline
    }
    out = {}
    for p in pools:
        key = (frozenset(toks(p.get("symbol"))), p.get("project"), p.get("chain"))
        if key in targets and p.get("tvlUsd", 0) > 2e6:
            if key not in out or p.get("tvlUsd", 0) > out[key].get("tvlUsd", 0):
                out[key] = p
    return list(out.values())


def fetch_chart(pool_id: str) -> List[dict]:
    path = f"{CACHE}/amm_pool_{pool_id}.json"
    if os.path.exists(path):
        return json.load(open(path))
    r = requests.get(f"https://yields.llama.fi/chart/{pool_id}", timeout=40)
    data = r.json().get("data", [])
    json.dump(data, open(path, "w"))
    return data


def main():
    os.makedirs(CACHE, exist_ok=True)
    pools = fetch_pools_index()
    print(f"DefiLlama index: {len(pools)} pools")
    basket = pick_basket(pools)
    print(f"basket: {len(basket)} target pools")
    summary = []
    for p in basket:
        sym = p.get("symbol"); proj = p.get("project"); chain = p.get("chain")
        pid = p["pool"]
        try:
            hist = fetch_chart(pid)
        except Exception as e:
            print(f"  {sym:12s} {proj:12s} {chain:10s} ERR {e}")
            continue
        apys = [x.get("apyBase", 0) or 0 for x in hist]
        ils = [abs(x.get("il7d", 0) or 0) for x in hist]
        tvls = [x.get("tvlUsd", 0) or 0 for x in hist]
        n = len(hist)
        import statistics
        med_apy = statistics.median(apys) if apys else 0
        med_il = statistics.median(ils) if ils else 0
        summary.append({"symbol": sym, "project": proj, "chain": chain,
                        "pool": pid, "n_days": n, "tvl_now": p.get("tvlUsd"),
                        "median_apyBase_pct": round(med_apy, 3),
                        "median_abs_il7d_pct": round(med_il, 3)})
        print(f"  {sym:12s} {proj:12s} {chain:10s} n={n:4d} tvl=${p.get('tvlUsd',0)/1e6:.1f}M  "
              f"med_apyBase={med_apy:.2f}%  med_|il7d|={med_il:.2f}%")
    json.dump(summary, open(f"{CACHE}/amm_basket_summary.json", "w"), indent=2)
    print(f"\nsaved summary -> {CACHE}/amm_basket_summary.json")


if __name__ == "__main__":
    main()
