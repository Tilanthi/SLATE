"""Market regime detector — classifies each bar into a latent market state.

Simple mode: multi-signal (trend + volatility + momentum) thresholds.
HMM mode: hidden Markov model over returns (if hmmlearn available).

The regime labels enable regime-conditional strategy evaluation: backtest each
strategy per-regime to find WHERE it works, then build a switch policy that
deploys it only in the right conditions.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd


# Regime labels
BULL = "bull"
BEAR = "bear"
SIDEWAYS = "sideways"
HIGH_VOL = "high_vol"
LOW_VOL = "low_vol"

ALL_REGIMES = [BULL, BEAR, SIDEWAYS, HIGH_VOL, LOW_VOL]


class RegimeDetector:
    """Detect market regimes from OHLCV data."""

    def __init__(self, trend_lookback: int = 168, vol_lookback: int = 48,
                 trend_threshold: float = 0.03, vol_threshold: float = 0.025,
                 use_hmm: bool = False, n_hmm_states: int = 3):
        self.trend_lb = trend_lookback
        self.vol_lb = vol_lookback
        self.trend_thr = trend_threshold
        self.vol_thr = vol_threshold
        self.use_hmm = use_hmm
        self.n_states = n_hmm_states
        self._hmm = None

    def detect(self, df: pd.DataFrame) -> pd.Series:
        """Return a Series of regime labels aligned to df's index."""
        close = df["close"].astype(float)
        # Trend: rolling return over trend_lookback bars
        trend_ret = close.pct_change(self.trend_lb)
        # Volatility: rolling std of 1-bar returns
        rets = close.pct_change()
        vol = rets.rolling(self.vol_lb).std()

        if self.use_hmm:
            return self._detect_hmm(rets, vol, trend_ret)
        return self._detect_simple(trend_ret, vol)

    def _detect_simple(self, trend_ret: pd.Series, vol: pd.Series) -> pd.Series:
        """Multi-signal threshold classification."""
        regime = pd.Series(SIDEWAYS, index=trend_ret.index)

        # High-vol override
        high_vol = vol > self.vol_thr
        regime[high_vol] = HIGH_VOL

        # Trend classification (within normal vol)
        normal_vol = ~high_vol
        bull = normal_vol & (trend_ret > self.trend_thr)
        bear = normal_vol & (trend_ret < -self.trend_thr)
        regime[bull] = BULL
        regime[bear] = BEAR

        # Low-vol sideways
        low_vol = normal_vol & (vol < self.vol_thr * 0.5) & ~bull & ~bear
        regime[low_vol] = LOW_VOL

        # Fill NaN (warmup period)
        regime = regime.fillna(SIDEWAYS)
        return regime

    def _detect_hmm(self, rets: pd.Series, vol: pd.Series,
                    trend_ret: pd.Series) -> pd.Series:
        """HMM-based regime detection (if hmmlearn available)."""
        try:
            from hmmlearn.hmm import GaussianHMM
        except ImportError:
            return self._detect_simple(trend_ret, vol)

        # Features: returns + volatility
        features = pd.DataFrame({"ret": rets, "vol": vol}).fillna(0)
        X = features.values

        # Fit HMM
        self._hmm = GaussianHMM(n_components=self.n_states, covariance_type="full",
                                n_iter=100, random_state=42)
        self._hmm.fit(X)
        states = self._hmm.predict(X)

        # Map HMM states to regime labels by their characteristics
        state_means = []
        for s in range(self.n_states):
            mask = states == s
            if mask.sum() > 0:
                mean_ret = features["ret"][mask].mean()
                mean_vol = features["vol"][mask].mean()
                state_means.append((s, mean_ret, mean_vol))
            else:
                state_means.append((s, 0, 0))

        # Sort states by mean return (most positive = bull, most negative = bear)
        state_means.sort(key=lambda x: x[1])
        labels = {}
        n = len(state_means)
        for i, (s, mr, mv) in enumerate(state_means):
            if i == 0:
                labels[s] = BEAR
            elif i == n - 1:
                labels[s] = BULL
            elif mv > self.vol_thr:
                labels[s] = HIGH_VOL
            else:
                labels[s] = SIDEWAYS

        regime = pd.Series([labels.get(s, SIDEWAYS) for s in states],
                           index=rets.index)
        return regime

    def regime_summary(self, regime: pd.Series) -> Dict[str, float]:
        """Fraction of bars in each regime."""
        counts = regime.value_counts()
        total = len(regime)
        return {r: counts.get(r, 0) / total for r in ALL_REGIMES}


__all__ = ["RegimeDetector", "BULL", "BEAR", "SIDEWAYS", "HIGH_VOL", "LOW_VOL", "ALL_REGIMES"]
