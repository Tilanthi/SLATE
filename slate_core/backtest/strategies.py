"""Causal strategy signal generators for the honest discovery sweep.

Each generator returns a TARGET-position array aligned to df's index, where the
target at bar t is decided from data through close[t] ONLY (causal). The honest
backtester then lags it by one bar (held[t]=target[t-1]) before attributing
returns — so even a signal using close[t] cannot peek at bar t's move.

Conventions:
  +1 long, -1 short, 0 flat.   Funding sign: positive funding => longs pay shorts.
"""
from __future__ import annotations

from typing import Callable, Dict, List, Tuple

import numpy as np
import pandas as pd


def _closes(df):
    return df["close"].astype(float)


# ============================== TREND / MOMENTUM ==========================
def trend_ema_cross(df, fast: int = 20, slow: int = 50) -> np.ndarray:
    c = _closes(df)
    ef = c.ewm(span=fast, adjust=False).mean()
    es = c.ewm(span=slow, adjust=False).mean()
    return np.sign(ef - es).fillna(0).values


def trend_ema_slope(df, span: int = 50, thr: float = 0.0) -> np.ndarray:
    c = _closes(df)
    ema = c.ewm(span=span, adjust=False).mean()
    slope = ema.pct_change()
    sig = pd.Series(0.0, index=df.index)
    sig[slope > thr] = 1
    sig[slope < -thr] = -1
    return sig.values


def trend_price_ema(df, span: int = 50, thr: float = 0.02) -> np.ndarray:
    """Momentum: long when price > ema*(1+thr)."""
    c = _closes(df)
    ema = c.ewm(span=span, adjust=False).mean()
    dev = c / ema - 1.0
    sig = pd.Series(0.0, index=df.index)
    sig[dev > thr] = 1
    sig[dev < -thr] = -1
    return sig.values


def breakout_donchian(df, lb: int = 20) -> np.ndarray:
    c = _closes(df)
    hi = c.rolling(lb).max().shift(1)   # breakout vs PRIOR window (no same-bar peek)
    lo = c.rolling(lb).min().shift(1)
    sig = pd.Series(0.0, index=df.index)
    sig[c > hi] = 1
    sig[c < lo] = -1
    return sig.fillna(0).values


def momentum_ret(df, lb: int = 20, thr: float = 0.0) -> np.ndarray:
    c = _closes(df)
    ret = c.pct_change(lb)
    sig = pd.Series(0.0, index=df.index)
    sig[ret > thr] = 1
    sig[ret < -thr] = -1
    return sig.values


# ============================== MEAN REVERSION ============================
def meanrev_rsi(df, ob: int = 70, os_: int = 30) -> np.ndarray:
    c = _closes(df)
    delta = c.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi = (100 - 100 / (1 + rs)).fillna(50)
    sig = pd.Series(0.0, index=df.index)
    sig[rsi < os_] = 1
    sig[rsi > ob] = -1
    return sig.values


def meanrev_zscore(df, lb: int = 20, z: float = 2.0) -> np.ndarray:
    c = _closes(df)
    m = c.rolling(lb).mean()
    s = c.rolling(lb).std()
    zsc = (c - m) / s.replace(0, np.nan)
    sig = pd.Series(0.0, index=df.index)
    sig[zsc > z] = -1
    sig[zsc < -z] = 1
    return sig.fillna(0).values


def meanrev_bb(df, span: int = 20, mult: float = 2.0) -> np.ndarray:
    c = _closes(df)
    m = c.rolling(span).mean()
    s = c.rolling(span).std()
    sig = pd.Series(0.0, index=df.index)
    sig[c > m + mult * s] = -1
    sig[c < m - mult * s] = 1
    return sig.fillna(0).values


# ============================== CARRY / FUNDING ===========================
def carry_funding(df, thr: float = 0.0001) -> np.ndarray:
    """Short when funding > thr (collect carry); long when funding < -thr."""
    if "funding" not in df.columns:
        return np.zeros(len(df))
    f = df["funding"].astype(float)
    sig = pd.Series(0.0, index=df.index)
    sig[f > thr] = -1
    sig[f < -thr] = 1
    return sig.values


def carry_funding_percentile(df, lb: int = 100, hi: float = 0.8) -> np.ndarray:
    """Short at the top funding percentile (squeeze-risk avoided); long at bottom."""
    if "funding" not in df.columns:
        return np.zeros(len(df))
    f = df["funding"].astype(float)
    p_hi = f.rolling(lb).quantile(hi)
    p_lo = f.rolling(lb).quantile(1 - hi)
    sig = pd.Series(0.0, index=df.index)
    sig[f > p_hi] = -1
    sig[f < p_lo] = 1
    return sig.fillna(0).values


def carry_funding_mom(df, lb: int = 24) -> np.ndarray:
    """Funding momentum: rising funding → short (crowding)."""
    if "funding" not in df.columns:
        return np.zeros(len(df))
    f = df["funding"].astype(float)
    diff = f.diff(lb)
    sig = pd.Series(0.0, index=df.index)
    sig[diff > 0] = -1
    sig[diff < 0] = 1
    return sig.values


def funding_price_div(df, lb: int = 48) -> np.ndarray:
    """Divergence: funding rising + price falling → short; opposite → long."""
    if "funding" not in df.columns:
        return np.zeros(len(df))
    f = df["funding"].astype(float)
    c = _closes(df)
    f_rise = f.diff(lb) > 0
    p_fall = c.diff(lb) < 0
    f_fall = f.diff(lb) < 0
    p_rise = c.diff(lb) > 0
    sig = pd.Series(0.0, index=df.index)
    sig[f_rise & p_fall] = -1
    sig[f_fall & p_rise] = 1
    return sig.values


# ============================== VOL / BREAKOUT ============================
def vol_breakout(df, lb: int = 24) -> np.ndarray:
    """Range expansion breakout vs prior Donchian channel."""
    return breakout_donchian(df, lb)


# ============================== ICHIMOKU (causal) =========================
def _ichimoku(df, tenkan=9, kijun=26, senkou=52, disp=26):
    """Return the AUTHENTIC, causal Ichimoku cloud displayed at each bar.

    The cloud displayed at bar t is computed from data 26 bars earlier (the
    Senkou spans are projected forward by `disp`). Implemented via a FORWARD
    pandas shift (displayed[t] = raw[t-disp]), which is CAUSAL: deciding at
    close[t] you know the cloud because it was fixed at close[t-disp]. A
    backward shift (shift(-disp)) would be the classic Ichimoku lookahead trap
    and is deliberately NOT used. Chikou (lagging span) is omitted — used
    causally it is just `disp`-bar momentum (already covered by momentum_ret)."""
    h = df["high"].astype(float); l = df["low"].astype(float)
    tenkan_sen = (h.rolling(tenkan).max() + l.rolling(tenkan).min()) / 2.0
    kijun_sen = (h.rolling(kijun).max() + l.rolling(kijun).min()) / 2.0
    spanA_raw = (tenkan_sen + kijun_sen) / 2.0
    spanB_raw = (h.rolling(senkou).max() + l.rolling(senkou).min()) / 2.0
    # forward shift: cloud at t = raw computed at t-disp (causal)
    cloudA = spanA_raw.shift(disp)
    cloudB = spanB_raw.shift(disp)
    return tenkan_sen, kijun_sen, cloudA, cloudB


def ichimoku_cloud(df, tenkan: int = 9, kijun: int = 26,
                   senkou: int = 52, disp: int = 26) -> np.ndarray:
    """Price vs Kumo cloud: +1 above the cloud, -1 below, 0 inside it."""
    c = _closes(df)
    _, _, ca, cb = _ichimoku(df, tenkan, kijun, senkou, disp)
    top = np.maximum(ca, cb); bot = np.minimum(ca, cb)
    sig = pd.Series(0.0, index=df.index)
    sig[c > top] = 1
    sig[c < bot] = -1
    return sig.fillna(0).values


def ichimoku_tk(df, tenkan: int = 9, kijun: int = 26) -> np.ndarray:
    """Tenkan/Kijun cross: +1 when Tenkan above Kijun, -1 below."""
    t, k, _, _ = _ichimoku(df, tenkan, kijun)
    return np.sign(t - k).fillna(0).values


def ichimoku_combo(df, tenkan: int = 9, kijun: int = 26,
                   senkou: int = 52, disp: int = 26) -> np.ndarray:
    """Only take a position when the cloud and the TK cross agree; else flat."""
    cloud = ichimoku_cloud(df, tenkan, kijun, senkou, disp)
    tk = ichimoku_tk(df, tenkan, kijun)
    out = np.where((cloud == tk) & (cloud != 0), cloud, 0.0)
    return out


# ============================== REGIME (causal, fixed params) =============
def regime_label(df, trend_span: int = 50, vol_lb: int = 20,
                 vol_thr: float = 0.02) -> np.ndarray:
    """Causal regime labels: 'up','down','range','hivol'. Fixed a-priori params
    (NOT optimized) to avoid an extra overfitting surface."""
    c = _closes(df)
    ema = c.ewm(span=trend_span, adjust=False).mean()
    rv = c.pct_change().rolling(vol_lb).std()
    slope = ema.pct_change(trend_span)
    lab = np.array(["range"] * len(df), dtype=object)
    lab[(slope.values > 0.01)] = "up"
    lab[(slope.values < -0.01)] = "down"
    lab[np.nan_to_num(rv.values, 0.0) > vol_thr] = "hivol"
    return lab


def regime_gate(target: np.ndarray, labels: np.ndarray, allowed) -> np.ndarray:
    """Zero the target outside the allowed regime(s)."""
    out = np.zeros(len(target))
    mask = np.isin(labels, allowed)
    out[mask] = np.asarray(target)[mask]
    return out


# ============================== CROSS-ASSET ===============================
def cross_asset_lead(df_sig, df_lead, lb: int = 24, thr: float = 0.0) -> np.ndarray:
    """Lead-lag: lead asset's lb-return (shifted to align) → signal on df_sig.
    df_sig and df_lead must share an index. Uses the lead's PAST return only."""
    lead_ret = df_lead["close"].astype(float).pct_change(lb)
    aligned = lead_ret.reindex(df_sig.index).fillna(0.0)
    sig = pd.Series(0.0, index=df_sig.index)
    sig[aligned > thr] = 1
    sig[aligned < -thr] = -1
    return sig.values


# ============================== REGISTRY ==================================
# (family, name, fn, params) — fn(df, **params) -> target array (single-asset).
# Cross-asset & regime-gated variants are composed in the sweep.
GRID: List[Tuple[str, str, Callable, Dict]] = [
    ("trend", "ema_cross", trend_ema_cross,
     {"fast": [10, 20, 50], "slow": [50, 100, 200]}),
    ("trend", "ema_slope", trend_ema_slope,
     {"span": [20, 50, 100], "thr": [0.0, 0.001, 0.005]}),
    ("trend", "price_ema", trend_price_ema,
     {"span": [20, 50, 100], "thr": [0.0, 0.02, 0.05]}),
    ("trend", "donchian", breakout_donchian, {"lb": [10, 20, 55]}),
    ("momentum", "mom_ret", momentum_ret,
     {"lb": [5, 10, 20, 50], "thr": [0.0, 0.02, 0.05]}),
    ("meanrev", "rsi", meanrev_rsi, {"ob": [65, 70, 80], "os_": [20, 30, 35]}),
    ("meanrev", "zscore", meanrev_zscore, {"lb": [20, 50], "z": [1.5, 2.0, 2.5]}),
    ("meanrev", "bb", meanrev_bb, {"span": [20, 50], "mult": [1.5, 2.0, 2.5]}),
    ("carry", "funding", carry_funding, {"thr": [0.00005, 0.0001, 0.0002, 0.0005]}),
    ("carry", "funding_pct", carry_funding_percentile, {"lb": [100, 500], "hi": [0.8, 0.9, 0.95]}),
    ("carry", "funding_mom", carry_funding_mom, {"lb": [24, 100, 500]}),
    ("carry", "funding_price_div", funding_price_div, {"lb": [24, 100, 500]}),
    # Ichimoku (causal cloud + TK cross); curated standard/fast/slow param sets
    ("ichimoku", "cloud", ichimoku_cloud,
     {"tenkan": [9], "kijun": [26], "senkou": [52], "disp": [26]}),
    ("ichimoku", "cloud_fast", ichimoku_cloud,
     {"tenkan": [7], "kijun": [14], "senkou": [28], "disp": [14]}),
    ("ichimoku", "cloud_slow", ichimoku_cloud,
     {"tenkan": [12], "kijun": [24], "senkou": [52], "disp": [24]}),
    ("ichimoku", "tk", ichimoku_tk, {"tenkan": [9], "kijun": [26]}),
    ("ichimoku", "combo", ichimoku_combo,
     {"tenkan": [9], "kijun": [26], "senkou": [52], "disp": [26]}),
]


def expand_grid(grid=GRID) -> List[Tuple[str, str, Callable, Dict]]:
    """Expand the param grid into one (family, name, fn, params) per variant."""
    import itertools
    out = []
    for family, name, fn, params in grid:
        keys = list(params.keys())
        for combo in itertools.product(*[params[k] for k in keys]):
            out.append((family, name, fn, dict(zip(keys, combo))))
    return out


__all__ = [g.__name__ for g in [trend_ema_cross, trend_ema_slope, trend_price_ema,
          breakout_donchian, momentum_ret, meanrev_rsi, meanrev_zscore,
          meanrev_bb, carry_funding, carry_funding_percentile, carry_funding_mom,
          funding_price_div, vol_breakout, regime_label, regime_gate,
          cross_asset_lead]] + ["GRID", "expand_grid", "regime_label", "regime_gate"]
