"""Rigorous validation suite (López de Prado / Bailey) — Tier 1c.

  * deflated_sharpe()        — import from realism.py (multiple-testing hurdle).
  * cscv_pbo()               — Probability of Backtest Overfitting (Bailey-LdP).
  * cpcv()                   — Combinatorial Purged Cross-Validation paths.

These replace plain walk-forward as the default for any strategy SELECTION from
a pool: PBO quantifies how overfit the selection is, CPCV produces deflated OOS
paths with leakage purged + embargoed. Plain walk-forward stays for single-
strategy stability; these govern selection.
"""
from __future__ import annotations

from itertools import combinations
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

from slate_core.backtest.realism import deflated_sharpe  # re-export


def _sharpe(R: np.ndarray, ppy: int, axis: int = 0) -> np.ndarray:
    mu = R.mean(axis=axis)
    sd = R.std(axis=axis, ddof=1)
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(sd > 0, mu / sd * np.sqrt(ppy), 0.0)


def cscv_pbo(pool_returns: np.ndarray, ppy: int, n_groups: int = 16,
             max_combos: int = 2000, seed: int = 0) -> Dict:
    """Probability of Backtest Overfitting via Combinatorially Symmetric CV.

    pool_returns: (T x S) array of per-bar returns for S candidate strategies.
    Splits into n_groups contiguous blocks; for each way to choose half as OOS,
    picks the IS-best strategy and checks whether it lands in the BOTTOM half of
    OOS ranks. PBO = fraction of combinations where it does. PBO > 0.5 => the
    selection is more likely overfit than not. Returns {pbo, n_combos, ...}."""
    R = np.asarray(pool_returns, dtype=float)
    T, S = R.shape
    n_groups = min(n_groups, T // 4)
    if n_groups < 4 or S < 2:
        return {"pbo": float("nan"), "n_combos": 0, "verdict": "too few groups/strategies"}
    blocks = np.array_split(R, n_groups, axis=0)
    half = n_groups // 2
    all_combos = list(combinations(range(n_groups), half))
    rng = np.random.RandomState(seed)
    if len(all_combos) > max_combos:
        idx = rng.choice(len(all_combos), size=max_combos, replace=False)
        all_combos = [all_combos[i] for i in idx]
    pbo_hits = 0
    logit_sum = 0.0
    for test_idx in all_combos:
        test_set = set(test_idx)
        test = np.vstack([blocks[i] for i in test_idx])
        train = np.vstack([blocks[i] for i in range(n_groups) if i not in test_set])
        is_sh = _sharpe(train, ppy)
        oos_sh = _sharpe(test, ppy)
        best = int(np.argmax(is_sh))
        oos_rank = pd.Series(oos_sh).rank(method="average").iloc[best]   # 1..S
        if oos_rank <= S / 2:                  # IS-best in bottom half OOS
            pbo_hits += 1
        # logit for the lambda distribution (Bailey-LdP)
        if 0 < oos_rank < S:
            logit_sum += -np.log((S - oos_rank) / oos_rank)
    pbo = pbo_hits / len(all_combos)
    return {"pbo": pbo, "n_combos": len(all_combos),
            "verdict": ("likely OVERFIT (PBO>0.5)" if pbo > 0.5
                        else "low overfit risk (PBO<=0.5)")}


def cpcv(returns: np.ndarray, ppy: int, n_groups: int = 6, n_test: int = 2,
         purge: int = 0, embargo: int = 0) -> Dict:
    """Combinatorial Purged Cross-Validation for ONE strategy's return stream.

    Generates C(n_groups, n_test) train/test paths (purging `purge` bars around
    each test group and embargoing `embargo` after). Reports the distribution of
    OOS Sharpe across paths — the honest, leakage-controlled read on a strategy.
    For SELECTION over many strategies use cscv_pbo()."""
    R = np.asarray(returns, dtype=float).reshape(-1, 1)
    T = len(R)
    n_groups = min(n_groups, T // 4)
    if n_groups < n_test + 2:
        return {"paths": [], "oos_sharpe_median": float("nan")}
    bounds = np.linspace(0, T, n_groups + 1, dtype=int)
    oos_sharpes = []
    for test_idx in combinations(range(n_groups), n_test):
        test_mask = np.zeros(T, dtype=bool)
        for g in test_idx:
            a, b = bounds[g], bounds[g + 1]
            test_mask[max(0, a - purge): min(T, b + embargo)] = True
        train = R[~test_mask]
        test = R[test_mask]
        if len(train) < 20 or len(test) < 10:
            continue
        oos_sharpes.append(float(_sharpe(test, ppy)[0]))
    oos = np.array(oos_sharpes)
    return {"paths": len(oos), "oos_sharpe_median": float(np.median(oos)) if len(oos) else float("nan"),
            "oos_sharpe_p10": float(np.percentile(oos, 10)) if len(oos) else float("nan"),
            "oos_sharpe_p90": float(np.percentile(oos, 90)) if len(oos) else float("nan"),
            "n_positive": int((oos > 0).sum()), "n_total": int(len(oos))}


__all__ = ["deflated_sharpe", "cscv_pbo", "cpcv", "_sharpe"]
