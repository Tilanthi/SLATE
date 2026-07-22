"""Honest market-making / maker-rebate backtester (clean dollar accounting).

The rebate edge is structural (provide liquidity, capture the spread), not
directional. It lives or dies on ADVERSE SELECTION: resting orders fill
disproportionately when price runs through them against you.

Accounting (fully consistent, mark-to-close, no double counting):
  * post capital C=$1. Each fill trades `k=1/max_pos` of capital notional.
  * quote bid/ask around the PRIOR close (ref = close[t-1], no lookahead), skewed
    by inventory; resting BID fills iff low[t] <= bid, ASK iff high[t] >= ask;
  * each fill pays the venue MAKER fee (HL retail 0.015% PAID; whale rebates
    gated, ignored) on the notional traded;
  * inventory pays funding;
  * equity[t] = cash + qty*close[t]; return = (equity[t]-equity[t-1]) / C.

Spread capture AND adverse selection both fall out of the mark-to-close: a fill
at the quote is instantly marked to the bar's close, so a fill into a bar that
ran against you loses on the inventory leg (that IS the adverse selection).
There is no separate "spread credit" — it is implicit in buying below / selling
above the eventual close.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from slate_core.backtest.honest import bars_per_year_from_index, CEX, DEX


def mm_backtest(df: pd.DataFrame, half_spread: float = 0.0030,
                max_pos: int = 3, inv_skew: float = 0.5,
                extra_slip_bps: float = 0.0, venue=DEX) -> dict:
    """`extra_slip_bps`: additional one-way slippage/queue haircut per fill
    (0 = base mark-to-close; 5-10 bps = realistic-to-pessimistic, modelling that
    real fills suffer slippage beyond the quote and queue priority loss)."""
    close = df["close"].astype(float).values
    high = df["high"].astype(float).values
    low = df["low"].astype(float).values
    fund = df["funding"].astype(float).values if "funding" in df.columns else np.zeros(len(df))
    n = len(close)
    ppy = bars_per_year_from_index(df.index)
    hpb = 24.0
    if isinstance(df.index, pd.DatetimeIndex) and len(df) > 1:
        d = df.index.to_series().diff().median()
        if pd.notna(d):
            hpb = d.total_seconds() / 3600.0
    settlements_per_bar = hpb / venue.funding_interval_hours
    maker = venue.maker_fee
    C = 1.0
    k = 1.0 / max_pos                  # notional per fill (fraction of capital)

    cash = C                           # dollars
    qty = 0.0                          # signed units held
    fees = funding = 0.0
    nfill = 0
    equity = np.full(n, C)
    for t in range(1, n):
        ref = close[t - 1]
        notional = qty * close[t - 1]                 # signed, fraction of capital
        skew = inv_skew * half_spread * np.clip(notional, -1, 1)
        bid = ref * (1 - (half_spread + skew))
        ask = ref * (1 + (half_spread - skew))
        if low[t] <= bid and notional < 1.0 - 1e-9:   # room to buy more
            q = (k / ref)                              # units for k notional at ref
            buy_px = bid * (1 + extra_slip_bps / 1e4)   # pay a bit MORE (worse)
            cash -= q * buy_px; fees += k * maker; qty += q; nfill += 1
        notional = qty * close[t - 1]
        if high[t] >= ask and notional > -1.0 + 1e-9:  # room to sell more
            q = (k / ref)
            sell_px = ask * (1 - extra_slip_bps / 1e4)   # receive a bit LESS (worse)
            cash += q * sell_px; fees += k * maker; qty -= q; nfill += 1
        # funding on end-of-bar inventory
        if qty != 0.0:
            fp = -fund[t] * settlements_per_bar * (qty * close[t])
            funding += fp
            cash += fp                                  # realize funding in cash
        equity[t] = cash + qty * close[t]
    # final liquidation at taker cost
    liq = abs(qty) * close[-1] * venue.taker_fee
    equity[-1] -= liq
    rets = np.diff(equity) / equity[:-1]
    rets = np.nan_to_num(rets)
    mu, sd = rets.mean(), rets.std(ddof=1)
    sharpe = mu / sd * np.sqrt(ppy) if sd > 0 else 0.0
    eq = np.cumprod(1 + rets)
    return {
        "sharpe": float(sharpe), "total_ret": float(eq[-1] - 1),
        "max_dd": float(-(eq / np.maximum.accumulate(eq) - 1).min()),
        "n_fills": nfill, "fees_paid": float(fees), "funding_pnl": float(funding),
        "final_qty": float(qty), "half_spread": half_spread, "max_pos": max_pos,
        "inv_skew": inv_skew, "venue": venue.name, "ppy": ppy,
        "returns": rets, "equity": equity,
    }


__all__ = ["mm_backtest"]
