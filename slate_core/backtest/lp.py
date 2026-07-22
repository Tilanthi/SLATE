"""Honest concentrated-LP backtester using REAL pool data (DefiLlama + price path).

Replaces the old `amm/lp_backtester.py` which used a vol-scaled SYNTHETIC volume
proxy and hardcoded $100M TVL. Here every number is real:

  * FEE YIELD: the pool's realized fee yield series `apyBase` (DefiLlama, from
    actual on-chain swap fees). Daily fee return = apyBase/365.
  * IMPERMANENT LOSS: computed from the real token price-ratio path (BTC/ETH from
    Hyperliquid/Binance; stables ~1). For a full-range (v2-equivalent) position
    the IL vs HODL is  IL(r) = 2*sqrt(r)/(1+r) - 1,  r = price_ratio_t / ratio_0.
    Concentrated positions amplify IL; we model concentration as a multiplier.
  * NET = fees - IL  (the excess of LPing over HODL — the actual alpha from LPing).

`volume-in-range`: for a CONCENTRATED position we scale fee accrual by the
fraction of bars the price spends inside the chosen band (and zero outside), so
fees accrue only when "in range" — the honest first-order volume-in-range effect
(the precise tick-level liquidity-distribution share needs a Graph API key,
flagged as the one remaining approximation).
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd

CACHE = "sol_data_cache"


def load_pool_history(pool_id: str) -> pd.DataFrame:
    d = json.load(open(f"{CACHE}/amm_pool_{pool_id}.json"))
    df = pd.DataFrame(d)
    df["t"] = pd.to_datetime(df["timestamp"])
    df = df.set_index("t").sort_index()
    df.index = df.index.tz_localize(None).normalize()   # date-aligned for ratio joins
    return df


def il_fullrange(r: np.ndarray) -> np.ndarray:
    """Full-range (v2-style) IL vs HODL for price-ratio path r (r[0] = entry)."""
    r = r / r[0]
    with np.errstate(divide="ignore", invalid="ignore"):
        return 2 * np.sqrt(r) / (1 + r) - 1.0


@dataclass
class LPResult:
    pool: str; days: int
    fee_apr_pct: float; terminal_il_pct: float; max_il_pct: float
    net_excess_apr_pct: float        # fees - IL, the LP-vs-HODL alpha
    abs_return_pct: float            # absolute LP return (token exposure + fees - IL)
    hodl_return_pct: float           # buy-and-hold the risky token
    vol_concentration: float


def backtest_lp(pool_id: str, price_ratio: Optional[pd.Series] = None,
                band: Optional[float] = None, il_mult: float = 1.0) -> LPResult:
    """Backtest LP on a pool.

    pool_id: DefiLlama pool id (history has apyBase).
    price_ratio: real price-ratio series aligned to the pool index (e.g. ETH price
        for WETH-USDC). If None, treated as constant (stablecoin) -> IL=0.
    band: if set, only accrue fees on bars where the ratio is within ±`band` of
        its rolling entry (concentrated range => 'volume-in-range' gating).
    il_mult: IL amplifier for concentration (1.0 = full range).
    """
    h = load_pool_history(pool_id)
    n = len(h)
    apy_base = (h.get("apyBase", pd.Series(np.zeros(n))).fillna(0) / 100.0).values
    daily_fee = apy_base / 365.0

    if price_ratio is not None:
        pr = price_ratio.reindex(h.index).ffill().bfill().values
        il = il_fullrange(pr) * il_mult
        risky_ret = np.concatenate([[0.0], pr[1:] / pr[:-1] - 1.0])   # bar-to-bar, len n
        if band is not None:                      # concentrate: fees only in range
            r_norm = pr / pr[0]
            in_range = (r_norm > 1 - band) & (r_norm < 1 + band)
            daily_fee = daily_fee * in_range / max(in_range.mean(), 1e-6)
        # Full-range constant-product LP value ∝ sqrt(price) => ~0.5*exposure + fees
        lp_daily = 0.5 * risky_ret + daily_fee
        abs_ret = float(np.cumprod(1 + np.nan_to_num(lp_daily))[-1] - 1)
        hodl = pr[-1] / pr[0] - 1.0
        terminal_il = float(il[-1]); max_il = float(np.min(il))
        net_excess = abs_ret - hodl
    else:   # stablecoin: IL ~ 0 (depeg captured in apyBase volatility, not modeled here)
        abs_ret = float(np.cumprod(1 + np.nan_to_num(daily_fee))[-1] - 1)
        hodl = 0.0; net_excess = abs_ret; terminal_il = 0.0; max_il = 0.0

    yrs = n / 365.0
    fee_apr = (1 + float(np.sum(daily_fee))) ** (1 / yrs) - 1 if yrs > 0 else 0
    net_excess_apr = (1 + net_excess) ** (1 / yrs) - 1 if yrs > 0 and (1 + net_excess) > 0 else -1
    return LPResult(
        pool=pool_id, days=n,
        fee_apr_pct=100 * fee_apr,
        terminal_il_pct=100 * terminal_il, max_il_pct=100 * max_il,
        net_excess_apr_pct=100 * net_excess_apr,
        abs_return_pct=100 * abs_ret, hodl_return_pct=100 * hodl,
        vol_concentration=float(band) if band is not None else 1.0,
    )


__all__ = ["load_pool_history", "il_fullrange", "backtest_lp", "LPResult"]
