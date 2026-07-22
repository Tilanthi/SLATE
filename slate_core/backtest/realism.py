"""Realism upgrades that quantify what a vectorized, flat-cost backtester misses.

1. DEFLATED SHARPE RATIO (Bailey & López de Prado 2014) — corrects an observed
   Sharpe for the selection bias from running N trials. With N=547 variants the
   best Sharpe has a large expected right tail under the null; a survivor must
   clear that bar, not just zero. This is the rigorous multiple-testing control
   our plain bootstrap only approximates.

2. SQUARE-ROOT MARKET IMPACT + CAPACITY (Almgren; Bouchaud; Donier for crypto) —
   slippage ∝ σ·√(order_size / market_volume), validated on crypto limit-order
   books. Replaces the flat bps assumption with a size-dependent cost and yields
   the honest *capacity*: the AUM at which an edge is eroded by own impact.
"""
from __future__ import annotations

import numpy as np
from scipy.stats import norm

EULER_GAMMA = 0.5772156649015329


def expected_max_null(n_trials: int) -> float:
    """E[max of n_trials iid standard normals] — the multiple-testing hurdle."""
    if n_trials <= 1:
        return 0.0
    e = np.e
    return ((1 - EULER_GAMMA) * norm.ppf(1 - 1 / n_trials)
            + EULER_GAMMA * norm.ppf(1 - 1 / (n_trials * e)))


def deflated_sharpe(sharpe_annualized: float, n_trials: int, n_bars: int,
                    ppy: int, skew: float = 0.0, kurt: float = 3.0) -> dict:
    """Probability that the TRUE Sharpe > 0 after deflating for N trials.

    Returns dict with the per-period Sharpe, the multiple-testing hurdle
    (annualized), the deflated Sharpe p-value, and a verdict. Uses the non-IID
    Sharpe estimator variance (Lo 2002 / Bailey-LdP)."""
    sr = sharpe_annualized / np.sqrt(ppy)            # per-bar Sharpe
    em = expected_max_null(n_trials)
    # std of the Sharpe estimator, non-IID correction
    var_sr = (1 - skew * sr + (kurt - 1) / 4 * sr ** 2) / max(n_bars - 1, 1)
    std_sr = np.sqrt(max(var_sr, 1e-12))
    hurdle_annual = em * std_sr * np.sqrt(ppy)        # the Sharpe you'd "need"
    # DSR = P(true SR > 0 | observed, deflated)
    z = (sr - em * std_sr) / std_sr
    dsr_p = float(norm.cdf(z))
    return {"sharpe_per_bar": sr, "hurdle_sharpe_annual": float(hurdle_annual),
            "em_null_z": float(em), "dsr_p": dsr_p,
            "significant": dsr_p > 0.95,
            "verdict": ("SIGNIFICANT (even after N trials)" if dsr_p > 0.95
                        else "not significant after deflation")}


def sqrt_impact_bps(order_notional: float, market_volume_notional: float,
                    bar_vol: float, k: float = 0.3) -> float:
    """One-way market-impact slippage in bps (Almgren square-root law).

    impact = k · σ · sqrt(Q / V) · 1e4 (bps), with Q=order, V=market volume,
    σ=bar volatility (fraction). k≈0.3 is a mid-range empirical coefficient
    (Almgren ~0.1-0.5; validated for crypto by Donier et al.)."""
    if market_volume_notional <= 0:
        return 0.0
    return float(k * bar_vol * np.sqrt(order_notional / market_volume_notional) * 1e4)


def capacity_curve(edge_apr_net_of_flatcost: float, turnover_per_yr: float,
                   market_daily_volume_notional: float, bar_vol: float = 0.03,
                   k: float = 0.3, flat_one_way_bps: float = 20.0) -> dict:
    """At what AUM does impact erode a strategy with a given net edge?

    Adds square-root impact (per side) to the flat cost; finds the AUM at which
    total cost equals the gross edge (edge → 0) and at which it halves the edge."""
    edge = edge_apr_net_of_flatcost           # already net of flat costs (fraction/yr)
    sides_per_yr = turnover_per_yr * 2
    breakeven_aum = None
    half_aum = None
    for aum in [1e3, 1e4, 5e4, 1e5, 5e5, 1e6, 5e6, 1e7, 5e7, 1e8, 5e8, 1e9]:
        order_notional = aum / sides_per_yr if sides_per_yr > 0 else 0
        impact_bps = sqrt_impact_bps(order_notional, market_daily_volume_notional, bar_vol, k)
        impact_cost_yr = impact_bps / 1e4 * sides_per_yr
        net = edge - impact_cost_yr
        if breakeven_aum is None and net <= 0:
            breakeven_aum = aum
        if half_aum is None and net <= edge / 2:
            half_aum = aum
    return {"edge_apr": edge, "turnover_per_yr": turnover_per_yr,
            "impact_halves_edge_at_aum": half_aum, "edge_dies_at_aum": breakeven_aum,
            "flat_one_way_bps": flat_one_way_bps}


__all__ = ["expected_max_null", "deflated_sharpe", "sqrt_impact_bps", "capacity_curve"]
