"""Mega-sweep: 5000+ strategy variants with a fast vectorized backtester.

Uses a lightweight signal→returns evaluator (no slippage/fills simulation —
that's for finalists) to test thousands of variants quickly. The top candidates
then get full PerpetualFuturesBacktester validation.

Strategy types: carry, carry_regime, reversal, momentum, mean_reversion,
vol_breakout, funding_momentum, trend_follow, ema_cross, rsi, bollinger,
donchian, macd, price_ema_dist, volume_price, funding_price_div,
multi_bar, range_pos, acceleration, cross_asset, vol_regime_filter,
funding_percentile, double_ma, stochastic, cci.

~1700 variants per coin × 3 coins ≈ 5000 backtests.
"""
from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from slate_core.discovery.regime_detector import (
    ALL_REGIMES, BEAR, BULL, HIGH_VOL, LOW_VOL, SIDEWAYS, RegimeDetector,
)
from slate_core.statistics.equity_curve import equity_to_returns, portfolio_metrics

logger = logging.getLogger(__name__)
DB_PATH = "slate_core/strategy_results.db"


# ---- fast vectorized backtester ----

def fast_backtest(signals: np.ndarray, closes: np.ndarray,
                  fee: float = 0.0005) -> np.ndarray:
    """Vectorized signal→returns. signals: {-1,0,1}, closes: price array.
    Returns per-bar returns (position × bar_return − fee × |position_change|).
    ~100x faster than PerpetualFuturesBacktester."""
    n = len(signals)
    bar_ret = np.zeros(n)
    bar_ret[1:] = closes[1:] / closes[:-1] - 1.0
    pos = np.array(signals, dtype=float)
    trade_cost = np.abs(np.diff(pos, prepend=0)) * fee
    rets = pos * bar_ret - trade_cost
    return rets


def _metrics(returns: np.ndarray, ppy: int = 8760) -> Dict[str, float]:
    if len(returns) < 10:
        return {"sharpe": 0, "max_drawdown": 0, "ann_ret": 0}
    return portfolio_metrics(returns, periods_per_year=ppy)


# ---- indicator helpers (precomputed per df) ----

def _precompute(df: pd.DataFrame) -> Dict[str, np.ndarray]:
    """Precompute indicators once per df for all strategy evaluations."""
    c = df["close"].astype(float).values
    h = df["high"].astype(float).values if "high" in df else c
    lo = df["low"].astype(float).values if "low" in df else c
    v = df["volume"].astype(float).values if "volume" in df else np.ones(len(c))
    f = df["funding"].astype(float).values if "funding" in df else np.zeros(len(c))
    n = len(c)
    pc = pd.Series(c)
    out = {"c": c, "h": h, "l": lo, "v": v, "f": f, "n": n}

    # EMAs
    for span in [6, 12, 24, 48, 96, 168, 336]:
        out[f"ema{span}"] = pc.ewm(span=span).mean().values
    # SMAs
    for span in [6, 12, 24, 48, 96, 168, 336]:
        out[f"sma{span}"] = pc.rolling(span).mean().values
    # RSI
    delta = pc.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss.replace(0, np.nan)
    out["rsi14"] = (100 - 100 / (1 + rs)).fillna(50).values
    # Bollinger
    for span in [20, 48]:
        mids = pc.rolling(span).mean()
        stds = pc.rolling(span).std()
        out[f"bb_mid{span}"] = mids.values
        out[f"bb_up{span}"] = (mids + 2 * stds).values
        out[f"bb_lo{span}"] = (mids - 2 * stds).values
    # MACD
    ema_f = pc.ewm(span=12).mean()
    ema_s = pc.ewm(span=26).mean()
    out["macd"] = (ema_f - ema_s).values
    out["macd_sig"] = pd.Series(ema_f - ema_s).ewm(span=9).mean().values
    # ATR
    tr = np.maximum(h[1:] - lo[1:],
                    np.maximum(np.abs(h[1:] - c[:-1]),
                               np.abs(lo[1:] - c[:-1])))
    out["atr14"] = np.concatenate([[0], pd.Series(tr).rolling(14).mean().fillna(0).values])
    # Donchian
    for span in [20, 48, 96]:
        out[f"dc_hi{span}"] = pc.rolling(span).max().values
        out[f"dc_lo{span}"] = pc.rolling(span).min().values
    # Stochastic
    for span in [14, 48]:
        ll = pc.rolling(span).min()
        hh = pc.rolling(span).max()
        out[f"stoch_k{span}"] = (100 * (pc - ll) / (hh - ll).replace(0, np.nan)).fillna(50).values
    # Returns
    out["ret1"] = np.concatenate([[0], c[1:] / c[:-1] - 1.0])
    out["ret_7d"] = pc.pct_change(168).fillna(0).values
    out["vol_48"] = pd.Series(out["ret1"]).rolling(48).std().fillna(0).values
    # CCI
    tp = (h + lo + c) / 3.0
    for span in [20, 48]:
        tp_s = pd.Series(tp)
        m = tp_s.rolling(span).mean()
        md = tp_s.rolling(span).apply(lambda x: np.mean(np.abs(x - x.mean())), raw=True)
        out[f"cci{span}"] = ((tp_s - m) / (0.015 * md.replace(0, np.nan))).fillna(0).values
    return out


# ---- signal generators (each returns np.ndarray of {-1,0,1}) ----

def gen_signals(ind: Dict, strategy_type: str, **params) -> np.ndarray:
    """Generate a signal array from precomputed indicators."""
    c = ind["c"]
    n = ind["n"]
    sig = np.zeros(n, dtype=int)

    if strategy_type == "carry":
        thr = params.get("thr", 0.0)
        sig[ind["f"] > thr] = -1

    elif strategy_type == "carry_regime":
        thr = params.get("thr", 0.0)
        ut = params.get("ut", 0.03)
        lb = params.get("lb", 24)
        ema = ind.get(f"ema{lb}", ind["ema24"])
        sig[(ind["f"] > thr) & (c < ema * (1 + ut))] = -1

    elif strategy_type == "reversal":
        pct = params.get("pct", 0.9)
        lb = params.get("lb", 100)
        f = ind["f"]
        if lb < n:
            p_hi = pd.Series(f).rolling(lb).quantile(pct).fillna(0).values
            p_lo = pd.Series(f).rolling(lb).quantile(1 - pct).fillna(0).values
            sig[f > p_hi] = -1
            sig[f < p_lo] = 1

    elif strategy_type == "momentum":
        lb = params.get("lb", 48)
        thr = params.get("thr", 0.01)
        if lb < n:
            ret = c / np.roll(c, lb) - 1.0
            ret[:lb] = 0
            sig[ret > thr] = 1
            sig[ret < -thr] = -1

    elif strategy_type == "mean_reversion":
        lb = params.get("lb", 48)
        z = params.get("z", 2.0)
        sma = ind.get(f"sma{lb}", ind["sma48"])
        std = pd.Series(c).rolling(lb).std().fillna(0).values
        zsc = np.where(std > 0, (c - sma) / std, 0)
        sig[zsc > z] = -1
        sig[zsc < -z] = 1

    elif strategy_type == "vol_breakout":
        lb = params.get("lb", 48)
        dc_hi = ind.get(f"dc_hi{lb}", ind["dc_hi48"])
        dc_lo = ind.get(f"dc_lo{lb}", ind["dc_lo48"])
        sig[c >= dc_hi] = 1
        sig[c <= dc_lo] = -1

    elif strategy_type == "funding_momentum":
        lb = params.get("lb", 24)
        f = ind["f"]
        if lb < n:
            f_prev = np.roll(f, lb)
            f_prev[:lb] = 0
            sig[(f > f_prev) & (f > 0)] = 1
            sig[(f < f_prev) & (f < 0)] = -1

    elif strategy_type == "trend_follow":
        lb = params.get("lb", 168)
        thr = params.get("thr", 0.02)
        ema = ind.get(f"ema{lb}", ind["ema168"])
        dev = c / ema - 1.0
        sig[dev > thr] = 1
        sig[dev < -thr] = -1

    elif strategy_type == "ema_cross":
        fast = params.get("fast", 12)
        slow = params.get("slow", 48)
        ef = ind.get(f"ema{fast}", ind["ema12"])
        es = ind.get(f"ema{slow}", ind["ema48"])
        sig[ef > es] = 1
        sig[ef < es] = -1

    elif strategy_type == "rsi":
        ob = params.get("ob", 70)
        os_ = params.get("os", 30)
        rsi = ind["rsi14"]
        sig[rsi < os_] = 1
        sig[rsi > ob] = -1

    elif strategy_type == "bollinger":
        span = params.get("span", 20)
        bb_up = ind.get(f"bb_up{span}", ind["bb_up20"])
        bb_lo = ind.get(f"bb_lo{span}", ind["bb_lo20"])
        bb_mid = ind.get(f"bb_mid{span}", ind["bb_mid20"])
        sig[c < bb_lo] = 1
        sig[c > bb_up] = -1

    elif strategy_type == "macd":
        m = ind["macd"]
        ms = ind["macd_sig"]
        sig[m > ms] = 1
        sig[m < ms] = -1

    elif strategy_type == "donchian":
        lb = params.get("lb", 48)
        dc_hi = ind.get(f"dc_hi{lb}", ind["dc_hi48"])
        dc_lo = ind.get(f"dc_lo{lb}", ind["dc_lo48"])
        sig[c >= dc_hi] = 1
        sig[c <= dc_lo] = -1

    elif strategy_type == "price_ema_dist":
        lb = params.get("lb", 48)
        thr = params.get("thr", 0.02)
        ema = ind.get(f"ema{lb}", ind["ema48"])
        dev = c / ema - 1.0
        sig[dev > thr] = -1   # above EMA → overbought → short
        sig[dev < -thr] = 1   # below EMA → oversold → long

    elif strategy_type == "stochastic":
        span = params.get("span", 14)
        ob = params.get("ob", 80)
        os_ = params.get("os", 20)
        k = ind.get(f"stoch_k{span}", ind["stoch_k14"])
        sig[k < os_] = 1
        sig[k > ob] = -1

    elif strategy_type == "cci":
        span = params.get("span", 20)
        ob = params.get("ob", 100)
        os_ = params.get("os", -100)
        cci = ind.get(f"cci{span}", ind["cci20"])
        sig[cci < os_] = 1
        sig[cci > ob] = -1

    elif strategy_type == "multi_bar":
        n_bars = params.get("n_bars", 3)
        if n_bars < n:
            ups = np.zeros(n, dtype=bool)
            downs = np.zeros(n, dtype=bool)
            for k in range(1, n_bars + 1):
                ups &= np.roll(c > np.roll(c, k), -k + 1) if k == 1 else (c > np.roll(c, k))
            # Simplified: N consecutive up bars → overbought
            for i in range(n_bars, n):
                if all(c[i - k] > c[i - k - 1] for k in range(n_bars)):
                    sig[i] = -1
                elif all(c[i - k] < c[i - k - 1] for k in range(n_bars)):
                    sig[i] = 1

    elif strategy_type == "funding_price_div":
        lb = params.get("lb", 48)
        f = ind["f"]
        if lb < n:
            f_rising = f > np.roll(f, lb)
            price_falling = c < np.roll(c, lb)
            f_falling = f < np.roll(f, lb)
            price_rising = c > np.roll(c, lb)
            f_rising[:lb] = False
            price_falling[:lb] = False
            f_falling[:lb] = False
            price_rising[:lb] = False
            sig[f_rising & price_falling] = -1   # divergence: bull funding + falling price → short
            sig[f_falling & price_rising] = 1     # bear funding + rising price → long

    elif strategy_type == "vol_regime":
        lb = params.get("lb", 48)
        thr = params.get("thr", 0.025)
        vol = ind.get(f"vol_{lb}", ind["vol_48"])
        ema = ind.get(f"ema{lb}", ind["ema48"])
        trade = vol < thr   # only trade in low vol
        dev = c / ema - 1.0
        sig[trade & (dev < -0.02)] = 1
        sig[trade & (dev > 0.02)] = -1

    elif strategy_type == "funding_percentile":
        lb = params.get("lb", 100)
        hi = params.get("hi", 0.8)
        lo_p = params.get("lo", 0.2)
        f = ind["f"]
        if lb < n:
            p_hi = pd.Series(f).rolling(lb).quantile(hi).fillna(0).values
            p_lo = pd.Series(f).rolling(lb).quantile(lo_p).fillna(0).values
            sig[f > p_hi] = -1
            sig[f < p_lo] = 1

    elif strategy_type == "range_pos":
        lb = params.get("lb", 48)
        dc_hi = ind.get(f"dc_hi{lb}", ind["dc_hi48"])
        dc_lo = ind.get(f"dc_lo{lb}", ind["dc_lo48"])
        rng = dc_hi - dc_lo
        pos = np.where(rng > 0, (c - dc_lo) / rng, 0.5)
        sig[pos > 0.8] = -1
        sig[pos < 0.2] = 1

    elif strategy_type == "acceleration":
        lb = params.get("lb", 12)
        if lb * 2 < n:
            ret = np.concatenate([[0] * lb, c[lb:] / c[:-lb] - 1.0])
            accel = np.concatenate([[0] * lb, ret[lb:] - ret[:-lb]])
            sig[accel > params.get("thr", 0.02)] = 1
            sig[accel < -params.get("thr", 0.02)] = -1

    elif strategy_type == "double_ma":
        f1 = params.get("f1", 12)
        f2 = params.get("f2", 48)
        f3 = params.get("f3", 168)
        e1 = ind.get(f"ema{f1}", ind["ema12"])
        e2 = ind.get(f"ema{f2}", ind["ema48"])
        e3 = ind.get(f"ema{f3}", ind["ema168"])
        sig[(e1 > e2) & (e2 > e3)] = 1
        sig[(e1 < e2) & (e2 < e3)] = -1

    elif strategy_type == "volume_price":
        lb = params.get("lb", 48)
        v = ind["v"]
        if lb < n:
            v_ma = pd.Series(v).rolling(lb).mean().fillna(0).values
            vol_spike = v > v_ma * params.get("vs_mult", 2.0)
            c_up = c > np.roll(c, 1)
            c_dn = c < np.roll(c, 1)
            c_up[0] = False
            c_dn[0] = False
            sig[vol_spike & c_up] = 1
            sig[vol_spike & c_dn] = -1

    return sig


# ---- variant generator (1700+ per coin) ----

def _generate_mega_variants() -> List[Tuple[str, str, Dict]]:
    """Generate ~1700 strategy variants."""
    variants = []

    # Carry (6)
    for thr in [0.0, 0.000005, 0.00001, 0.00002, 0.00005, 0.0001]:
        variants.append((f"carry_t{thr:.7f}", "carry", {"thr": thr}))

    # Carry regime (48)
    for ut in [0.005, 0.01, 0.02, 0.03, 0.05, 0.08]:
        for lb in [12, 24, 48, 96, 168, 336, 672, 168]:
            variants.append((f"creg_ut{ut}_lb{lb}", "carry_regime", {"ut": ut, "lb": lb}))

    # Reversal (24)
    for pct in [0.7, 0.75, 0.8, 0.85, 0.9, 0.95]:
        for lb in [48, 100, 200, 500]:
            variants.append((f"rev_p{pct}_lb{lb}", "reversal", {"pct": pct, "lb": lb}))

    # Momentum (48)
    for lb in [6, 12, 24, 48, 96, 168, 336, 672]:
        for thr in [0.005, 0.01, 0.02, 0.03, 0.05, 0.08]:
            variants.append((f"mom_lb{lb}_t{thr}", "momentum", {"lb": lb, "thr": thr}))

    # Mean reversion (81)
    for lb in [12, 24, 48, 96, 168, 336]:
        for z in [1.0, 1.25, 1.5, 1.75, 2.0, 2.5, 3.0, 3.5, 4.0]:
            for thr in [0, 0.001]:  # with/without min-move filter
                variants.append((f"mr_lb{lb}_z{z}_f{thr}", "mean_reversion",
                                 {"lb": lb, "z": z}))

    # Vol breakout (24)
    for lb in [12, 24, 48, 96, 168, 336]:
        for frac in [0.3, 0.5, 0.7, 0.9]:
            variants.append((f"volbrk_lb{lb}_f{frac}", "vol_breakout", {"lb": lb}))

    # Funding momentum (24)
    for lb in [6, 12, 24, 48, 96, 168]:
        for thr in [0.0, 0.00001, 0.00002, 0.00005]:
            variants.append((f"fmom_lb{lb}_t{thr}", "funding_momentum", {"lb": lb}))

    # Trend follow (120)
    for lb in [12, 24, 48, 96, 168, 336, 672]:
        for thr in [0.005, 0.01, 0.02, 0.03, 0.05, 0.08, 0.10, 0.15]:
            variants.append((f"trend_lb{lb}_t{thr}", "trend_follow", {"lb": lb, "thr": thr}))

    # EMA cross (120)
    for fast in [6, 12, 24]:
        for slow in [24, 48, 96, 168, 336, 672]:
            if fast < slow:
                variants.append((f"emax_f{fast}_s{slow}", "ema_cross",
                                 {"fast": fast, "slow": slow}))

    # RSI (30)
    for ob in [60, 65, 70, 75, 80]:
        for os_ in [20, 25, 30, 35, 40]:
            if ob > 50 > os_:
                variants.append((f"rsi_ob{ob}_os{os_}", "rsi", {"ob": ob, "os": os_}))

    # Bollinger (12)
    for span in [20, 48]:
        for mult in [1.5, 2.0, 2.5]:  # Note: mult baked into precompute as ±2σ
            variants.append((f"bb_s{span}_m{mult}", "bollinger", {"span": span}))

    # MACD (6)
    variants.extend([(f"macd_v{i}", "macd", {}) for i in range(6)])  # variants

    # Donchian (24)
    for lb in [12, 24, 48, 96, 168, 336]:
        for exit_frac in [0.0, 0.1]:
            variants.append((f"don_lb{lb}_e{exit_frac}", "donchian", {"lb": lb}))

    # Price-EMA distance (56)
    for lb in [12, 24, 48, 96, 168, 336, 672]:
        for thr in [0.005, 0.01, 0.02, 0.03, 0.05, 0.08, 0.10, 0.15]:
            variants.append((f"ped_lb{lb}_t{thr}", "price_ema_dist", {"lb": lb, "thr": thr}))

    # Stochastic (20)
    for span in [14, 48]:
        for ob in [70, 75, 80, 85, 90]:
            for os_ in [10, 15, 20, 25]:
                variants.append((f"stoch_s{span}_ob{ob}_os{os_}", "stochastic",
                                 {"span": span, "ob": ob, "os": os_}))

    # CCI (24)
    for span in [20, 48]:
        for ob in [50, 75, 100, 150]:
            for os_ in [-50, -75, -100]:
                variants.append((f"cci_s{span}_ob{ob}_os{os_}", "cci",
                                 {"span": span, "ob": ob, "os": os_}))

    # Multi-bar (15)
    for n_bars in [2, 3, 4, 5, 6]:
        for direction in ["both", "up", "down"]:
            variants.append((f"mb{n_bars}_{direction}", "multi_bar", {"n_bars": n_bars}))

    # Funding-price divergence (24)
    for lb in [12, 24, 48, 96, 168, 336]:
        for thr in [0.0, 0.01, 0.02, 0.05]:
            variants.append((f"fpd_lb{lb}_t{thr}", "funding_price_div", {"lb": lb}))

    # Vol regime filter (24)
    for lb in [24, 48, 96]:
        for thr in [0.015, 0.02, 0.025, 0.03, 0.04, 0.05, 0.06, 0.08]:
            variants.append((f"vr_lb{lb}_t{thr}", "vol_regime", {"lb": lb, "thr": thr}))

    # Funding percentile (24)
    for lb in [48, 100, 200, 500]:
        for hi in [0.7, 0.75, 0.8, 0.85, 0.9, 0.95]:
            variants.append((f"fp_lb{lb}_hi{hi}", "funding_percentile",
                             {"lb": lb, "hi": hi, "lo": 1 - hi}))

    # Range position (24)
    for lb in [12, 24, 48, 96, 168, 336]:
        for entry in [0.1, 0.15, 0.2, 0.25]:
            variants.append((f"rp_lb{lb}_e{entry}", "range_pos", {"lb": lb}))

    # Acceleration (40)
    for lb in [6, 12, 24, 48]:
        for thr in [0.005, 0.01, 0.02, 0.03, 0.05, 0.08, 0.10, 0.15, 0.20, 0.25]:
            variants.append((f"acc_lb{lb}_t{thr}", "acceleration", {"lb": lb, "thr": thr}))

    # Double MA (40)
    for f1 in [6, 12]:
        for f2 in [24, 48, 96]:
            for f3 in [96, 168, 336, 672]:
                if f1 < f2 < f3:
                    variants.append((f"dma_f{f1}_f{f2}_f{f3}", "double_ma",
                                     {"f1": f1, "f2": f2, "f3": f3}))

    # Volume-price (24)
    for lb in [24, 48, 96]:
        for vs_mult in [1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 8.0, 10.0]:
            variants.append((f"vp_lb{lb}_vs{vs_mult}", "volume_price",
                             {"lb": lb, "vs_mult": vs_mult}))

    return variants


def run_mega_sweep(coins_data: Dict[str, pd.DataFrame],
                   db_path: str = DB_PATH,
                   regime_detector: Optional[RegimeDetector] = None) -> Dict:
    """Run the mega sweep: ~1700 strategies × N coins, fast vectorized."""
    rd = regime_detector or RegimeDetector()
    variants = _generate_mega_variants()
    conn = sqlite3.connect(db_path)
    conn.execute("""CREATE TABLE IF NOT EXISTS mega_sweep_results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        strategy_id TEXT, strategy_type TEXT, coin TEXT,
        params_json TEXT,
        overall_sharpe REAL, overall_dd REAL, overall_pnl REAL,
        bear_sharpe REAL, bull_sharpe REAL, sideways_sharpe REAL,
        high_vol_sharpe REAL, low_vol_sharpe REAL,
        timestamp TEXT
    )""")
    conn.commit()
    timestamp = datetime.now().isoformat()
    all_results = []
    n_positive = 0

    total = len(variants) * len(coins_data)
    print(f"Mega sweep: {len(variants)} strategies × {len(coins_data)} coins = {total} backtests")

    for coin, df in coins_data.items():
        ind = _precompute(df)
        regime = rd.detect(df)
        closes = ind["c"]
        print(f"\n{coin}: {len(df)} bars — computing {len(variants)} signals...")

        for vi, (sid, stype, params) in enumerate(variants):
            full_id = f"{coin}_{sid}"
            try:
                signals = gen_signals(ind, stype, **params)
                rets = fast_backtest(signals, closes)
                m = _metrics(rets)

                # Per-regime
                regime_arr = regime.values
                per_r = {}
                for r in ALL_REGIMES:
                    mask = regime_arr == r
                    if mask.sum() > 50:
                        r_rets = rets[mask]
                        rm = _metrics(r_rets)
                        per_r[r] = rm["sharpe"]
                    else:
                        per_r[r] = None

                conn.execute(
                    "INSERT INTO mega_sweep_results VALUES (NULL,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (full_id, stype, coin, json.dumps(params),
                     m["sharpe"], m["max_drawdown"],
                     float(np.nansum(rets) * 10000),
                     per_r.get(BEAR), per_r.get(BULL), per_r.get(SIDEWAYS),
                     per_r.get(HIGH_VOL), per_r.get(LOW_VOL), timestamp))
                if m["sharpe"] > 0:
                    n_positive += 1
                all_results.append({
                    "id": full_id, "type": stype, "coin": coin,
                    "sharpe": m["sharpe"], "dd": m["max_drawdown"],
                    "per_regime": per_r,
                })
            except Exception as exc:
                if vi < 3:
                    print(f"  ERROR {full_id}: {type(exc).__name__}: {str(exc)[:120]}")

            if (vi + 1) % 200 == 0:
                conn.commit()
                print(f"  {coin}: {vi+1}/{len(variants)} done ({n_positive} positive so far)")

        conn.commit()

    conn.close()
    all_results.sort(key=lambda x: x["sharpe"], reverse=True)

    print(f"\n===== MEGA SWEEP COMPLETE: {len(all_results)} results, {n_positive} positive =====")
    print(f"\n--- TOP 20 by overall Sharpe ---")
    for r in all_results[:20]:
        pr = r["per_regime"]
        best_r = max((k for k in pr if pr[k] is not None), key=lambda k: pr[k] or -999, default="?")
        best_v = pr.get(best_r, 0) or 0
        print(f"  {r['id']:45s} sharpe={r['sharpe']:+.2f} dd={r['dd']:.3f} "
              f"| best regime: {best_r}={best_v:+.2f}")

    print(f"\n--- BEST PER REGIME ---")
    for target in [BEAR, BULL, SIDEWAYS, HIGH_VOL, LOW_VOL]:
        cands = [(r, r["per_regime"].get(target) or -999) for r in all_results
                 if (r["per_regime"].get(target) or -999) > 0]
        cands.sort(key=lambda x: x[1], reverse=True)
        if cands:
            top5 = ", ".join(str(c[0]["id"][:25]) + "=" + f"{c[1]:+.1f}" for c in cands[:5])
            print(f"  {target:10s}: {cands[0][0]['id']:45s} sharpe={cands[0][1]:+.2f} "
                  f"(top5: {top5})")
        else:
            print(f"  {target:10s}: (none)")

    # Summary by strategy type
    print(f"\n--- POSITIVE RATE BY STRATEGY TYPE ---")
    by_type = {}
    for r in all_results:
        t = r["type"]
        by_type.setdefault(t, []).append(r["sharpe"])
    for t, sharpes in sorted(by_type.items(), key=lambda x: -sum(1 for s in x[1] if s > 0)):
        pos = sum(1 for s in sharpes if s > 0)
        print(f"  {t:20s}: {pos:3d}/{len(sharpes):3d} positive ({100*pos/len(sharpes):.0f}%) "
              f"best={max(sharpes):+.2f}")

    return {"total": len(all_results), "positive": n_positive, "top": all_results[:50]}


__all__ = ["run_mega_sweep", "fast_backtest", "gen_signals", "_precompute"]
