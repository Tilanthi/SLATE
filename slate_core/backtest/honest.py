"""Honest vectorized backtester — the source of truth for strategy evaluation.

Why this exists: ``mega_sweep.fast_backtest`` attributed returns as
``rets[t] = signal[t] * (close[t]/close[t-1] - 1)`` — crediting a bar's own move
to a signal decided from that bar's close. That 1-bar lookahead manufactured a
+3.43 Sharpe that collapses to −5.98 once removed. This module cannot make that
class of mistake: the position HELD during bar ``t`` is the TARGET decided at
the close of bar ``t-1``::

    held[t] = target[t-1]            # 1-bar execution lag (the only honest way)
    gross[t] = held[t] * (close[t]/close[t-1] - 1)
    cost[t]  = |held[t] - held[t-1]| * one_way          # turnover-priced
    fund[t]  = -funding_rate[t] * settlements_per_bar * held[t]   # signed
    net[t]   = gross[t] - cost[t] + fund[t]

Costs are brutally realistic and per-venue:

==============  ===========  ===========  ============  ==================
venue           maker/side   taker/side   slip (bps)    funding
==============  ===========  ===========  ============  ==================
CEX (Binance)   0.02%        0.05%        15            8h, real
DEX (HL, retail) 0.015%*     0.045%       10            8h, real
==============  ===========  ===========  ============  ==================
* HL maker is a FEE for retail (0.015%); rebates (−0.001..−0.003%) are
  whale-gated at >$500M 14d volume. Maker fills are not guaranteed and suffer
  adverse selection — modelled separately in the MM backtester, not here.
  This directional backtester prices maker execution at the maker fee WITHOUT
  modelling fill risk, so it is OPTIMISTIC for maker strategies. Use it for
  taker (directional) strategies, or the dedicated MM evaluator for rebates.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, Optional

import numpy as np
import pandas as pd


# --------------------------------------------------------------------------
# Venues
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class Venue:
    name: str
    maker_fee: float            # per side, fraction. >0 = fee paid, <0 = rebate
    taker_fee: float            # per side, fraction
    slippage_bps: float         # one-way slippage for taker market orders
    funding_interval_hours: int  # CEX & HL perps settle funding every 8h
    latency_bars: float = 0.0   # extra execution lag beyond the mandatory 1-bar decision lag
    impact_k: float = 0.3       # square-root market-impact coefficient (Almgren/Ddonier)
    tick_bps: float = 1.0       # tick size in bps (for discrete quoting)


CEX = Venue("cex", maker_fee=0.0002, taker_fee=0.0005,
            slippage_bps=15.0, funding_interval_hours=8,
            latency_bars=0.0, impact_k=0.3, tick_bps=1.0)
DEX = Venue("dex", maker_fee=0.00015, taker_fee=0.00045,
            slippage_bps=10.0, funding_interval_hours=8,
            latency_bars=0.0, impact_k=0.3, tick_bps=1.0)
# Whale-tier DEX (reference, for sensitivity): net maker rebate after volume gating.
DEX_WHALE = Venue("dex_whale", maker_fee=-0.0001, taker_fee=0.00045,
                  slippage_bps=10.0, funding_interval_hours=8,
                  latency_bars=0.0, impact_k=0.3, tick_bps=1.0)


# --------------------------------------------------------------------------
# Annualization from the index (crypto trades 24/7)
# --------------------------------------------------------------------------
def bars_per_year_from_index(idx) -> int:
    """bars/year from a DatetimeIndex's median bar spacing (365*24/hours_per_bar)."""
    if not isinstance(idx, pd.DatetimeIndex) or len(idx) < 3:
        return 365
    delta = idx.to_series().diff().median()
    if pd.isna(delta) or delta.total_seconds() <= 0:
        return 365
    hours_per_bar = delta.total_seconds() / 3600.0
    return max(1, int(round(365 * 24 / hours_per_bar)))


def _hours_per_bar(df: pd.DataFrame) -> float:
    if isinstance(df.index, pd.DatetimeIndex) and len(df) > 1:
        d = df.index.to_series().diff().median()
        if pd.notna(d):
            return max(1e-6, d.total_seconds() / 3600.0)
    return 24.0


# --------------------------------------------------------------------------
# Core backtest
# --------------------------------------------------------------------------
def backtest(target, df: pd.DataFrame, venue: Venue = CEX, *,
             maker: bool = False, funding: Optional[np.ndarray] = None,
             fee: Optional[float] = None, slippage_bps: Optional[float] = None,
             notional: float = 1.0, impact: bool = False,
             capital: float = 1.0) -> Dict:
    """Run an honest backtest.

    Args:
        target: array (len n) of TARGET position decided at the close of each
            bar using ONLY info through that bar. Held during bar t = target[t-1].
            Values typically {-1,0,1}; continuous sizing in [-1,1] also works.
        df: OHLCV frame with a ``close`` column (and ``high``/``low``/``volume``
            optional). A ``funding`` column is used if ``funding`` arg is None.
        venue: CEX or DEX cost/funding schedule (now carries latency_bars,
            impact_k, tick_bps for the event engine).
        maker: if True, price turnover at maker_fee (note: OPTIMISTIC — no fill
            risk; use the MM/event backtester for real maker/rebate strategies).
        funding: explicit funding-rate array aligned to df; else df['funding'].
        impact: if True (and df has ``volume``), add square-root market impact
            ``k·σ·√(trade_size/bar_volume)`` to the per-side cost. Scale depends
            on ``capital`` (AUM): impact is negligible at retail and grows with
            size — so set ``capital`` to the deployable AUM for a realistic read.
        capital: AUM in dollars, used only for the impact term and capacity report.

    Returns:
        dict with ``returns``, ``equity``, ``metrics`` (incl. capacity).
    """
    close = df["close"].astype(float).values
    n = len(close)
    target = np.asarray(target, dtype=float)
    assert len(target) == n, f"target len {len(target)} != n bars {n}"

    # ---- position held during bar t = decision at close of t-1 (no lookahead)
    held = np.zeros(n)
    held[1:] = target[:-1]
    held[0] = 0.0  # cannot hold during bar 0 (no prior decision)

    # ---- gross market PnL
    bar_ret = np.zeros(n)
    bar_ret[1:] = close[1:] / close[:-1] - 1.0
    gross = held * bar_ret

    # ---- transaction cost (turnover-priced, one-way per side)
    one_way_fee = (fee if fee is not None else (venue.maker_fee if maker else venue.taker_fee))
    slip = (slippage_bps if slippage_bps is not None else venue.slippage_bps) / 1e4
    one_way = one_way_fee + slip
    dhold = np.abs(np.diff(held, prepend=0.0))
    cost = dhold * one_way

    # ---- square-root market impact (size-dependent; only if volume + AUM given)
    impact_cost = np.zeros(n)
    if impact and "volume" in df.columns:
        vol_notional = np.abs(df["volume"].astype(float).values * close)  # $ volume/bar
        sigma = pd.Series(bar_ret).rolling(20, min_periods=2).std().fillna(
            pd.Series(bar_ret).std()).values
        trade_notional = dhold * capital                 # $ traded at this AUM
        with np.errstate(divide="ignore", invalid="ignore"):
            imp_bps = venue.impact_k * sigma * np.sqrt(
                np.where(vol_notional > 0, trade_notional / vol_notional, 0.0)) * 1e4
        impact_cost = dhold * imp_bps / 1e4

    # ---- funding (realized rate, signed; spread across settlements in the bar)
    fund_pnl = np.zeros(n)
    if funding is None and "funding" in df.columns:
        funding = df["funding"].astype(float).values
    if funding is None:
        funding = np.zeros(n)
    settlements_per_bar = _hours_per_bar(df) / venue.funding_interval_hours
    # positive funding => longs pay shorts. holder PnL = -rate * held.
    fund_pnl = -np.asarray(funding, dtype=float) * settlements_per_bar * held

    net = (gross - cost - impact_cost + fund_pnl) * notional

    equity = np.cumprod(1.0 + np.nan_to_num(net))
    ppy = bars_per_year_from_index(df.index)
    metrics = _metrics(net, equity, ppy)
    metrics["turnover"] = float(dhold.sum())
    metrics["n_trades"] = float(dhold.sum() / 2.0)          # round trips
    metrics["total_cost"] = float((cost + impact_cost).sum() * notional)
    metrics["total_funding"] = float(fund_pnl.sum() * notional)
    metrics["gross_ret"] = float(np.sum(gross * notional))
    metrics["impact_cost"] = float(impact_cost.sum() * notional)
    metrics["bars_per_year"] = ppy
    metrics["capacity"] = _capacity(metrics, dhold, df, close, venue, ppy)
    return {"returns": net, "equity": equity, "metrics": metrics,
            "held": held, "venue": venue.name}


def _capacity(metrics, dhold, df, close, venue, ppy) -> Dict:
    """AUM at which square-root impact halves / erases the net edge."""
    try:
        from slate_core.backtest.realism import capacity_curve
        if "volume" in df.columns:
            med_vol = float(np.nanmedian(np.abs(df["volume"].astype(float).values * close)))
            # scale median per-bar $ volume to a daily figure
            hpb = _hours_per_bar(df)
            daily_vol = med_vol * (24.0 / hpb)
            n_bars = len(close)
            turnover_per_year = metrics["turnover"] * ppy / max(n_bars, 1)  # one-way/yr
            return capacity_curve(edge_apr_net_of_flatcost=metrics["annualized_return"],
                                  turnover_per_yr=turnover_per_year,
                                  market_daily_volume_notional=max(daily_vol, 1.0),
                                  k=venue.impact_k)
    except Exception:
        pass
    return {}


def _metrics(returns: np.ndarray, equity: np.ndarray, ppy: int) -> Dict[str, float]:
    returns = np.nan_to_num(returns)
    n = len(returns)
    if n < 2:
        return {"sharpe": 0.0, "sortino": 0.0, "calmar": 0.0,
                "max_dd": 0.0, "total_ret": 0.0, "annualized_return": 0.0}
    mu = returns.mean()
    sd = returns.std(ddof=1)
    sharpe = (mu / sd * np.sqrt(ppy)) if sd > 0 else 0.0
    downside = returns[returns < 0]
    dsd = downside.std(ddof=1) if len(downside) > 1 else 0.0
    sortino = (mu / dsd * np.sqrt(ppy)) if dsd > 0 else 0.0
    total_ret = float(equity[-1] - 1.0)
    ann = float(equity[-1] ** (ppy / n) - 1.0) if equity[-1] > 0 else -1.0
    running_max = np.maximum.accumulate(equity)
    dd = (equity - running_max) / np.where(running_max > 0, running_max, 1.0)
    max_dd = float(-dd.min())
    calmar = (ann / max_dd) if max_dd > 0 else 0.0
    return {"sharpe": float(sharpe), "sortino": float(sortino),
            "calmar": float(calmar), "max_dd": max_dd,
            "total_ret": total_ret, "annualized_return": ann}


# --------------------------------------------------------------------------
# IS/OOS split + expanding walk-forward
# --------------------------------------------------------------------------
def split_is_oos(df: pd.DataFrame, is_frac: float = 0.6):
    n = len(df)
    k = int(n * is_frac)
    return df.iloc[:k], df.iloc[k:]


def walk_forward(df: pd.DataFrame, fit_fn: Callable, eval_fn: Callable, *,
                 n_folds: int = 5, min_train: int = 100) -> Dict:
    """Expanding-window walk-forward that RE-FITS params on each fold's train.

    fit_fn(train_df) -> params     (selected using ONLY train data)
    eval_fn(params, test_df) -> result dict (must contain 'returns' + 'metrics')

    Returns per-fold metrics + the concatenated OOS return stream (the only
    honest OOS Sharpe — each bar evaluated under params that never saw it).
    """
    n = len(df)
    fold = max(1, (n - min_train) // n_folds)
    folds, oos_rets = [], []
    for f in range(n_folds):
        train_end = min_train + f * fold
        test_end = min(train_end + fold, n)
        if train_end >= n or test_end <= train_end:
            break
        train, test = df.iloc[:train_end], df.iloc[train_end:test_end]
        params = fit_fn(train)
        res = eval_fn(params, test)
        folds.append({"fold": f, "train_bars": len(train), "test_bars": len(test),
                      **{k: v for k, v in res.get("metrics", {}).items()
                         if k in ("sharpe", "max_dd", "total_ret", "annualized_return")}})
        oos_rets.append(res["returns"])
    oos = np.concatenate(oos_rets) if oos_rets else np.array([])
    ppy = bars_per_year_from_index(df.index)
    oos_metrics = _metrics(oos, np.cumprod(1 + np.nan_to_num(oos)), ppy) if len(oos) else {}
    n_pos = sum(1 for f in folds if f.get("sharpe", 0) > 0)
    return {"folds": folds, "n_folds": len(folds), "n_positive": n_pos,
            "oos_returns": oos, "oos_metrics": oos_metrics,
            "oos_sharpe": oos_metrics.get("sharpe", 0.0)}


# --------------------------------------------------------------------------
# Lookahead guard for signal functions of the form fn(df, i) -> signal
# --------------------------------------------------------------------------
def assert_causal(signal_fn: Callable, df: pd.DataFrame, i: int) -> bool:
    """Return True iff signal_fn(df, i) is unchanged when FUTURE bars (>= i+1)
    are perturbed — i.e. the signal at i depends only on data through i."""
    base = df.copy()
    s_orig = signal_fn(base, i)
    perturbed = df.copy()
    # mangle everything strictly after i
    tail = perturbed.iloc[i + 1:].copy()
    for col in ["open", "high", "low", "close", "volume", "funding"]:
        if col in tail.columns:
            tail[col] = tail[col].values[::-1] * 3.14 + 1e6
    perturbed.iloc[i + 1:] = tail
    s_pert = signal_fn(perturbed, i)
    return bool(np.array_equal(np.atleast_1d(s_orig), np.atleast_1d(s_pert)))


__all__ = ["Venue", "CEX", "DEX", "backtest", "_metrics",
           "bars_per_year_from_index", "split_is_oos", "walk_forward",
           "assert_causal"]
