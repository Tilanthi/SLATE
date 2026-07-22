"""Causal ML-based regime detector + intelligent position sizing.

  * gmm_regime(): probabilistic regime labels from a Gaussian Mixture on
    (return, volatility), FIT ON IN-SAMPLE ONLY and predicted out-of-sample
    (no leakage). sklearn GMM is used as the probabilistic detector because
    hmmlearn is not installable in this env; an HMM would add Markov state-
    persistence smoothing but is unlikely to change the qualitative conclusion.
    States are mapped to up/down/range/hivol by their IN-SAMPLE characteristics.
  * vol_target(): intelligent position sizing — scale the target by target_vol /
    realized_vol (capped), so each strategy contributes constant risk. Improves
    risk-adjusted return IF signal exists; cannot manufacture edge.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from typing import Tuple


def _features(df, trend_lb=50, vol_lb=20):
    c = df["close"].astype(float)
    trend = c.pct_change(trend_lb)
    vol = c.pct_change().rolling(vol_lb).std()
    return np.column_stack([trend.fillna(0).values, vol.fillna(0).values]), trend, vol


def gmm_regime(df, is_end: int, n_states: int = 4, seed: int = 0) -> np.ndarray:
    """Probabilistic regime labels (up/down/range/hivol). GMM fit on IS[0:is_end],
    predicted over the full series; states mapped to labels by IS characteristics."""
    from sklearn.mixture import GaussianMixture
    X, trend, vol = _features(df)
    is_X = X[:is_end]
    try:
        gmm = GaussianMixture(n_components=n_states, covariance_type="diag",
                              random_state=seed, n_init=3).fit(is_X)
    except Exception:
        # fallback: simple threshold labels
        from slate_core.backtest.strategies import regime_label
        return regime_label(df)
    states = gmm.predict(X)
    # map states -> labels by IS mean (return, vol)
    info = []
    for s in range(n_states):
        m = states[:is_end] == s
        if m.sum() > 0:
            info.append((s, trend.values[:is_end][m].mean(), vol.values[:is_end][m].mean()))
        else:
            info.append((s, 0.0, 0.0))
    vol_thr = float(np.nanpercentile(vol.values[:is_end], 75))
    # rank by mean return
    info.sort(key=lambda t: t[1])
    lab = np.array(["range"] * len(df), dtype=object)
    down_s = info[0][0]; up_s = info[-1][0]
    mid = [t[0] for t in info[1:-1]]
    for s, mr, mv in info:
        if s == down_s:
            l = "down"
        elif s == up_s:
            l = "up"
        elif mv > vol_thr:
            l = "hivol"
        else:
            l = "range"
        lab[states == s] = l
    return lab


def vol_target(target: np.ndarray, df, target_vol: float = 0.6,
               vol_lb: int = 20, cap: float = 2.0, ppy: int = 365) -> np.ndarray:
    """Scale target by target_vol / realized_vol (capped). Constant-risk sizing.
    target_vol is annualized; realized_vol annualized from rolling bar stdev."""
    c = df["close"].astype(float)
    rv = c.pct_change().rolling(vol_lb).std().values * np.sqrt(ppy)
    scale = np.where(rv > 0, target_vol / np.where(rv > 0, rv, 1.0), 1.0)
    scale = np.clip(scale, 0.0, cap)
    return np.asarray(target, dtype=float) * scale


__all__ = ["gmm_regime", "vol_target"]
