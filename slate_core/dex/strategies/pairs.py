"""Pairs (stat-arb) archetype: mean-revert the log-price-ratio spread between two
assets. When A is cheap vs B (spread z-score < -thresh), go long A / short B; when
A is rich (z > +thresh), go short A / long B; else flat. A classic market-neutral
edge class distinct from directional trading.
"""
from __future__ import annotations

import math

import numpy as np


def spread_zscore_signal(dfA, dfB, i, window: int = 50, thresh: float = 1.5) -> int:
    if i < window:
        return 0
    la = np.log(dfA["close"].astype(float).iloc[i - window:i].values)
    lb = np.log(dfB["close"].astype(float).iloc[i - window:i].values)
    spread = la - lb
    sd = float(spread.std())
    if sd <= 0:
        return 0
    mu = float(spread.mean())
    cur = math.log(float(dfA["close"].iloc[i])) - math.log(float(dfB["close"].iloc[i]))
    z = (cur - mu) / sd
    if z < -thresh:
        return 1            # A cheap vs B -> long A / short B
    if z > thresh:
        return -1           # A rich vs B -> short A / long B
    return 0
