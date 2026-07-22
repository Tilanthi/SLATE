"""Live-calibration loop (Tier 3) — the only thing that closes the residual gap.

The backtest model predicts slippage = base + k·σ·√(size/volume). Live fills are
the ground truth. This module ingests live fills (order-intended vs realized
price), fits the model's (base, k) to the realized slippage distribution by OLS,
and returns a calibrated Venue to feed back into the backtester. The closed loop
is: backtest -> paper -> small live -> measure shortfall -> recalibrate -> repeat.

Even with no live data yet, the harness is complete and self-tested (it recovers
a known impact model from synthetic fills), so it is ready the moment live fills
arrive. The ingestion format is a list of LiveFill records.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import List, Optional

import numpy as np

from slate_core.backtest.honest import Venue, CEX, DEX
from slate_core.backtest.realism import sqrt_impact_bps


@dataclass
class LiveFill:
    side: int                      # +1 buy / -1 sell
    intended_price: float          # the price the strategy intended (e.g. the close)
    realized_price: float          # the actual fill price
    size_notional: float           # dollars traded
    bar_volume_usd: float          # $ volume of the bar
    bar_vol: float                 # bar volatility (fraction)


def realized_slippage_bps(fills: List[LiveFill]) -> np.ndarray:
    """Realized slippage in bps, signed adverse (positive = cost paid against you)."""
    out = []
    for f in fills:
        # adverse slippage = how much worse than intended, in bps, in the direction against the trader
        rel = (f.realized_price / f.intended_price - 1.0) * f.side   # +ve => worse
        out.append(rel * 1e4)
    return np.array(out)


def calibrate(fills: List[LiveFill], venue: Venue) -> dict:
    """Fit base slippage (bps) and impact coefficient k to realized fills via OLS.

    Model: realized_bps = base + k · σ · sqrt(size/volume). Returns calibrated
    base/k, goodness-of-fit, mean residual (backtest-vs-live bias), and a new
    calibrated Venue."""
    if len(fills) < 8:
        return {"status": "need >=8 live fills", "n": len(fills)}
    y = realized_slippage_bps(fills)
    X = np.array([f.bar_vol * np.sqrt(f.size_notional / max(f.bar_volume_usd, 1e-9)) * 1e4
                  for f in fills])           # sqrt-impact regressor (in bps; matches sqrt_impact_bps)
    A = np.column_stack([np.ones_like(X), X])
    coef, *_ = np.linalg.lstsq(A, y, rcond=None)
    base_bps, k = float(coef[0]), float(coef[1])
    pred = A @ coef
    resid = y - pred
    ss_res = float((resid ** 2).sum())
    ss_tot = float(((y - y.mean()) ** 2).sum())
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0.0
    calibrated = replace(venue, slippage_bps=max(base_bps, 0.0), impact_k=max(k, 0.0))
    return {"n": len(fills), "base_bps": base_bps, "impact_k": k, "r2": r2,
            "mean_residual_bps": float(resid.mean()),
            "mean_realized_bps": float(y.mean()),
            "backtest_minus_live_bps": float(pred.mean() - y.mean()),
            "calibrated_venue": calibrated,
            "status": "calibrated" if r2 > 0.1 else "weak fit (low R^2)"}


def simulate_live_fills(venue: Venue, n=200, seed=0) -> List[LiveFill]:
    """Generate synthetic live fills from a KNOWN model, for self-test/demo."""
    rng = np.random.RandomState(seed)
    fills = []
    for _ in range(n):
        side = rng.choice([-1, 1])
        intended = 100.0
        size = rng.uniform(1e3, 1e6)
        vol = rng.uniform(1e7, 5e8)
        sigma = rng.uniform(0.01, 0.05)
        slip = venue.slippage_bps + sqrt_impact_bps(size, vol, sigma, venue.impact_k)
        realized = intended * (1 + side * slip / 1e4)   # adverse
        fills.append(LiveFill(side, intended, realized, size, vol, sigma))
    return fills


__all__ = ["LiveFill", "realized_slippage_bps", "calibrate", "simulate_live_fills"]
