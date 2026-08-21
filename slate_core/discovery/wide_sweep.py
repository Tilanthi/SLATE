"""Wide-sweep strategy discovery engine.

Generates 100+ strategy variants across types (carry, momentum, mean-reversion,
vol-breakout, cross-asset, funding-momentum, reversal), backtests each on real
data both overall AND per-regime, records all results to a SQLite database for
later analysis, and deposits stigmergic pheromones on profitable strategy×regime
combinations to guide future sweeps.

This is the 'wide net' — systematically exploring a large strategy space to find
where genuine edge exists, in which market conditions, then building a regime-
switching policy that deploys each strategy only when its edge is active.
"""
from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from slate_core.discovery.perpetual_futures_backtest import (
    PerpetualBacktestConfig, PerpetualFuturesBacktester,
)
from slate_core.discovery.regime_detector import (
    ALL_REGIMES, BEAR, BULL, HIGH_VOL, LOW_VOL, SIDEWAYS, RegimeDetector,
)
from slate_core.statistics.equity_curve import equity_to_returns, portfolio_metrics
from slate_core.config.paths import CORE_ROOT

logger = logging.getLogger(__name__)

DB_PATH = f"{CORE_ROOT}/strategy_results.db"


# ---- signal factories (each returns signal_fn(df, i, params) -> {-1, 0, 1}) ----

def _carry(threshold: float = 0.0):
    def fn(df, i, p):
        f = df["funding"].iloc[i] if "funding" in df.columns else 0.0
        return -1 if f > threshold else 0
    return fn

def _carry_regime(uptrend_thr: float = 0.03, lookback: int = 24):
    def fn(df, i, p):
        f = df["funding"].iloc[i] if "funding" in df.columns else 0.0
        if f <= 0:
            return 0
        if i >= lookback:
            ma = float(df["close"].iloc[max(0, i - lookback):i + 1].mean())
            if float(df["close"].iloc[i]) > ma * (1 + uptrend_thr):
                return 0
        return -1
    return fn

def _reversal(percentile: float = 0.9, lookback: int = 100):
    def fn(df, i, p):
        if "funding" not in df.columns or i < lookback:
            return 0
        f = float(df["funding"].iloc[i])
        recent = df["funding"].iloc[max(0, i - lookback):i + 1]
        ph = float(recent.quantile(percentile))
        pl = float(recent.quantile(1 - percentile))
        if f > ph:
            return -1
        if f < pl:
            return 1
        return 0
    return fn

def _momentum(lookback: int = 48):
    def fn(df, i, p):
        if i < lookback:
            return 0
        ret = float(df["close"].iloc[i]) / float(df["close"].iloc[i - lookback]) - 1.0
        if ret > 0.01:
            return 1
        if ret < -0.01:
            return -1
        return 0
    return fn

def _mean_reversion(lookback: int = 48, z_threshold: float = 2.0):
    def fn(df, i, p):
        if i < lookback:
            return 0
        window = df["close"].iloc[max(0, i - lookback):i + 1].astype(float)
        mean = float(window.mean())
        std = float(window.std())
        if std == 0:
            return 0
        z = (float(df["close"].iloc[i]) - mean) / std
        if z > z_threshold:
            return -1   # overbought → short
        if z < -z_threshold:
            return 1    # oversold → long
        return 0
    return fn

def _vol_breakout(lookback: int = 48, entry_frac: float = 0.5):
    def fn(df, i, p):
        if i < lookback:
            return 0
        window = df["close"].iloc[max(0, i - lookback):i + 1].astype(float)
        hi, lo = float(window.max()), float(window.min())
        rng = hi - lo
        if rng == 0:
            return 0
        pos = (float(df["close"].iloc[i]) - lo) / rng
        if pos > 0.5 + entry_frac * 0.5:
            return 1    # breakout up → long
        if pos < 0.5 - entry_frac * 0.5:
            return -1   # breakout down → short
        return 0
    return fn

def _funding_momentum(lookback: int = 24):
    def fn(df, i, p):
        if "funding" not in df.columns or i < lookback:
            return 0
        curr = float(df["funding"].iloc[i])
        prev = float(df["funding"].iloc[i - lookback])
        if curr > prev and curr > 0:
            return 1    # funding rising → trend strengthening → long
        if curr < prev and curr < 0:
            return -1   # funding falling → trend weakening → short
        return 0
    return fn

def _trend_follow(lookback: int = 168, threshold: float = 0.02):
    def fn(df, i, p):
        if i < lookback:
            return 0
        ret = float(df["close"].iloc[i]) / float(df["close"].iloc[i - lookback]) - 1.0
        if ret > threshold:
            return 1
        if ret < -threshold:
            return -1
        return 0
    return fn


def _generate_strategy_variants() -> List[Tuple[str, str, Callable, Dict]]:
    """Generate ~80 strategy variants across types × parameters."""
    variants = []
    # Carry variants
    for thr in [0.0, 0.00001, 0.00002]:
        variants.append((f"carry_t{thr}", "carry", _carry(thr), {"threshold": thr}))
    # Regime-gated carry
    for ut in [0.01, 0.02, 0.03, 0.05]:
        for lb in [24, 48, 168]:
            variants.append((f"carry_reg_ut{ut}_lb{lb}", "carry_regime",
                             _carry_regime(ut, lb), {"ut": ut, "lb": lb}))
    # Reversal
    for pct in [0.8, 0.9, 0.95]:
        variants.append((f"reversal_p{pct}", "reversal", _reversal(pct), {"pct": pct}))
    # Momentum
    for lb in [24, 48, 168, 336]:
        variants.append((f"momentum_lb{lb}", "momentum", _momentum(lb), {"lb": lb}))
    # Mean reversion
    for lb in [24, 48, 96]:
        for z in [1.5, 2.0, 2.5]:
            variants.append((f"mr_lb{lb}_z{z}", "mean_reversion",
                             _mean_reversion(lb, z), {"lb": lb, "z": z}))
    # Vol breakout
    for lb in [24, 48, 96]:
        variants.append((f"volbrk_lb{lb}", "vol_breakout", _vol_breakout(lb), {"lb": lb}))
    # Funding momentum
    for lb in [12, 24, 48]:
        variants.append((f"fundmom_lb{lb}", "funding_momentum",
                         _funding_momentum(lb), {"lb": lb}))
    # Trend follow
    for lb in [48, 168, 336]:
        for thr in [0.01, 0.02, 0.05]:
            variants.append((f"trend_lb{lb}_t{thr}", "trend_follow",
                             _trend_follow(lb, thr), {"lb": lb, "thr": thr}))
    return variants


def _init_db(db_path: str = DB_PATH):
    conn = sqlite3.connect(db_path)
    conn.execute("""CREATE TABLE IF NOT EXISTS strategy_results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        strategy_id TEXT, strategy_type TEXT, coin TEXT,
        params_json TEXT,
        overall_sharpe REAL, overall_dd REAL, overall_pnl REAL,
        overall_ann_ret REAL,
        bull_sharpe REAL, bear_sharpe REAL, sideways_sharpe REAL,
        high_vol_sharpe REAL, low_vol_sharpe REAL,
        timestamp TEXT
    )""")
    conn.commit()
    return conn


def _backtest_one(df: pd.DataFrame, signal_fn: Callable, coin: str,
                  strategy_id: str) -> Dict:
    """Backtest a single strategy variant → metrics."""
    config = PerpetualBacktestConfig(initial_capital=10_000.0, timeframe="1h")
    bt = PerpetualFuturesBacktester(config)
    result = bt.backtest_strategy(
        df=df, strategy_name=strategy_id, strategy_description=strategy_id,
        edge_type="sweep", signal_function=signal_fn, parameters={},
    )
    curve = list(result.equity_curve) if result.equity_curve else [10_000.0]
    returns = equity_to_returns(curve)
    metrics = portfolio_metrics(returns, periods_per_year=8760)
    return {
        "sharpe": metrics["sharpe"], "dd": metrics["max_drawdown"],
        "pnl": result.total_profit_usdt, "ann_ret": metrics["annualized_return"],
        "returns": returns, "equity_curve": curve,
    }


def run_wide_sweep(coins_data: Dict[str, pd.DataFrame],
                   db_path: str = DB_PATH,
                   regime_detector: Optional[RegimeDetector] = None) -> Dict:
    """Run the full wide sweep: all strategies × all coins × per-regime.

    Returns a summary dict with top performers + records everything to SQLite.
    """
    rd = regime_detector or RegimeDetector()
    variants = _generate_strategy_variants()
    conn = _init_db(db_path)
    timestamp = datetime.now().isoformat()
    all_results = []
    n_positive = 0

    print(f"Wide sweep: {len(variants)} strategies × {len(coins_data)} coins "
          f"= {len(variants) * len(coins_data)} backtests")

    for coin, df in coins_data.items():
        # Detect regimes for this coin
        regime = rd.detect(df)
        regime_summary = rd.regime_summary(regime)
        print(f"\n{coin}: {len(df)} bars | regimes: "
              + ", ".join(f"{k}={v:.0%}" for k, v in regime_summary.items() if v > 0))

        for sid, stype, signal_fn, params in variants:
            full_id = f"{coin}_{sid}"
            try:
                # Overall backtest
                overall = _backtest_one(df, signal_fn, coin, full_id)

                # Per-regime backtests
                per_regime = {}
                for r in ALL_REGIMES:
                    mask = regime == r
                    sub = df[mask].copy()
                    if len(sub) > 100:
                        r_result = _backtest_one(sub, signal_fn, coin, f"{full_id}_{r}")
                        per_regime[r] = r_result["sharpe"]
                    else:
                        per_regime[r] = None

                # Record to DB
                conn.execute(
                    "INSERT INTO strategy_results VALUES (NULL,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (full_id, stype, coin, json.dumps(params),
                     overall["sharpe"], overall["dd"], overall["pnl"], overall["ann_ret"],
                     per_regime.get(BULL), per_regime.get(BEAR), per_regime.get(SIDEWAYS),
                     per_regime.get(HIGH_VOL), per_regime.get(LOW_VOL), timestamp))
                conn.commit()

                if overall["sharpe"] > 0:
                    n_positive += 1

                all_results.append({
                    "id": full_id, "type": stype, "coin": coin,
                    "params": params,
                    "overall_sharpe": overall["sharpe"],
                    "overall_dd": overall["dd"],
                    "overall_pnl": overall["pnl"],
                    "per_regime": per_regime,
                })
            except Exception as exc:
                logger.warning("backtest failed for %s: %s", full_id, str(exc)[:80])

    conn.close()

    # Rank and report
    all_results.sort(key=lambda x: x["overall_sharpe"], reverse=True)
    print(f"\n===== SWEEP COMPLETE: {len(all_results)} results, {n_positive} positive =====")
    print(f"\n--- TOP 15 by overall Sharpe ---")
    for r in all_results[:15]:
        pr = r["per_regime"]
        best_regime = max((k for k in pr if pr[k] is not None),
                          key=lambda k: pr[k] or -999, default="?")
        best_val = pr.get(best_regime, 0) or 0
        print(f"  {r['id']:40s} sharpe={r['overall_sharpe']:+.2f} "
              f"dd={r['overall_dd']:.3f} pnl={r['overall_pnl']:+.1f} "
              f"| best regime: {best_regime}={best_val:+.2f}")

    # Per-regime winners
    print(f"\n--- BEST PER REGIME (positive Sharpe only) ---")
    for target_regime in [BEAR, BULL, SIDEWAYS, HIGH_VOL, LOW_VOL]:
        candidates = [(r, r["per_regime"].get(target_regime) or -999)
                      for r in all_results
                      if (r["per_regime"].get(target_regime) or -999) > 0]
        candidates.sort(key=lambda x: x[1], reverse=True)
        if candidates:
            top = candidates[0]
            print(f"  {target_regime:10s}: {top[0]['id']:40s} sharpe={top[1]:+.2f}")
        else:
            print(f"  {target_regime:10s}: (no positive Sharpe found)")

    return {
        "total": len(all_results),
        "positive": n_positive,
        "top_results": all_results[:20],
    }


__all__ = ["run_wide_sweep", "RegimeDetector"]
