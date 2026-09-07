"""Funding-persistence-timed carry vs naive carry — main honest backtest.

Real data: BASKET_*_{1d,FUNDING}.json for 24 coins. Honest costs via
slate_core.backtest.honest (CEX taker 0.05% + 15bps one-way; real funding).

Design (all signals are CAUSAL — decided at close of day t using data through t;
held during day t+1 by the backtester's held[t]=target[t-1] rule):

  rank_signal[t, c] = cross-sectional rank of fund_last[t, c] within universe at t,
                      scaled to [-1, +1]. Positive => high funding.

  NAIVE carry target[t, c]:  -rank_signal[t, c]  (short high funding, long low).
                              Dollar-neutral: long bottom-N, short top-N.
                              Always on when coin present.

  PERSIST-timed target:      -rank_signal[t, c] * persistence_mask[t, c]
                              where mask depends on variant:
    V1 (regime):   mask = 1 if rolling-30d AR(1) of coin funding > TAU, else 0.
    V2 (forecast): mask = 1 if AR(1) forecast f_hat[t+1] is same sign AND
                       |f_hat| > Q quantile of |f| historically, else 0.

The persistence filter is the ONLY difference between naive and timed. Aggregating
both through the same honest.backtest isolates the filter's marginal value.

Universe selection caveat: the 24-coin basket is a "still-listed" survivorship set.
We CANNOT fix that without delisting data, so it is a known optimistic bias.
"""
from __future__ import annotations
import sys
import numpy as np
import pandas as pd
sys.path.insert(0, "/Users/gjw255/astrodata/SWARM/SLATE")
sys.path.insert(0, "/Users/gjw255/astrodata/SWARM/SLATE/novel_findings")
from slate_core.backtest import backtest, CEX, bars_per_year_from_index
from _panel import build_panel, COINS


def cross_sectional_rank_signal(fund_last: pd.DataFrame) -> pd.DataFrame:
    """Per-date cross-sectional rank of funding, scaled to [-1,+1].
    High funding -> +1, low -> -1. Causal: uses only same-day funding values."""
    ranks = fund_last.rank(axis=1, pct=True) - 0.5    # (-0.5, +0.5)
    return ranks * 2.0                                # (-1, +1)


def naive_target(rank_signal: pd.DataFrame, top_n: int = 3) -> pd.DataFrame:
    """Dollar-neutral naive carry: short top-N, long bottom-N by funding.
    Position magnitude per active name = 1/(2N) so gross = 1."""
    tgt = pd.DataFrame(0.0, index=rank_signal.index, columns=rank_signal.columns)
    for t in rank_signal.index:
        s = rank_signal.loc[t].dropna()
        if len(s) < 2*top_n: continue
        shorts = s.nlargest(top_n).index    # high funding -> short
        longs  = s.nsmallest(top_n).index   # low funding -> long
        w = 1.0/(2*top_n)
        tgt.loc[t, shorts] = -w
        tgt.loc[t, longs]  = +w
    return tgt


def rolling_ar1(series: pd.Series, window: int = 30) -> pd.Series:
    """Rolling AR(1) coefficient (autocorr at lag 1)."""
    def _ar1(x):
        x = x[~np.isnan(x)]
        if len(x) < 5: return np.nan
        return np.corrcoef(x[:-1], x[1:])[0,1]
    return series.rolling(window, min_periods=10).apply(_ar1, raw=True)


def persistence_mask_v1(fund_last: pd.DataFrame, window: int = 30, tau: float = 0.4) -> pd.DataFrame:
    """Regime filter: 1 when coin's rolling AR(1) > tau, else 0."""
    mask = pd.DataFrame(0.0, index=fund_last.index, columns=fund_last.columns)
    for c in fund_last.columns:
        ar1 = rolling_ar1(fund_last[c], window=window)
        mask[c] = (ar1 > tau).astype(float)
    return mask


def persistence_mask_v2(fund_last: pd.DataFrame, window: int = 30, q: float = 0.5) -> pd.DataFrame:
    """Forecast filter: AR(1) forecast f_hat[t+1] = phi*f[t] + (1-phi)*mean.
    Enter only if sign(f_hat)==sign(f[t]) AND |f_hat| > rolling median |f|."""
    mask = pd.DataFrame(0.0, index=fund_last.index, columns=fund_last.columns)
    for c in fund_last.columns:
        s = fund_last[c]
        ar1 = rolling_ar1(s, window=window)
        mean = s.rolling(window, min_periods=10).mean()
        med_abs = s.abs().rolling(window, min_periods=10).median()
        f_hat = ar1 * s + (1 - ar1) * mean
        cond_sign = np.sign(f_hat) == np.sign(s)
        cond_mag  = f_hat.abs() > med_abs
        mask[c] = (cond_sign & cond_mag & s.notna()).astype(float)
    return mask


def aggregate_backtest(target_wide: pd.DataFrame, close_wide: pd.DataFrame,
                       fund_sum_wide: pd.DataFrame, vol_wide: pd.DataFrame,
                       capital: float = 1_000_000.0, impact: bool = True,
                       label: str = "") -> dict:
    """Run per-coin backtest with equal fraction of capital; aggregate returns.

    Per coin: df has close, volume, funding=fund_sum/3 (so the backtester's
    settlements_per_bar=3 yields correct total daily funding PnL = -sum*held).
    Equal capital split across coins present (could weight by signal; kept simple)."""
    n_coins_used = 0
    per_bar_rets = []
    metrics_list = []
    for c in target_wide.columns:
        # build single-coin df restricted to dates where target != 0 sometimes
        tgt = target_wide[c].dropna()
        if tgt.abs().sum() == 0:
            continue
        df = pd.DataFrame({"close": close_wide[c], "volume": vol_wide[c],
                           "funding": fund_sum_wide[c]/3.0}).dropna(subset=["close"])
        df = df.loc[df.index.intersection(tgt.index)]
        tgt = tgt.reindex(df.index).fillna(0.0)
        if len(df) < 30: continue
        # equal split of capital
        cap_c = capital / 24.0
        res = backtest(tgt.values, df, venue=CEX, impact=impact, capital=cap_c)
        # convert per-bar fractional returns on cap_c to dollar returns on `capital`
        rets_dollar = pd.Series(res["returns"], index=df.index) * cap_c
        per_bar_rets.append(rets_dollar)
        metrics_list.append((c, res["metrics"]))
        n_coins_used += 1
    # aggregate dollar returns per date, divide by total capital -> portfolio return
    if not per_bar_rets:
        return {"sharpe": np.nan, "ann_ret": np.nan, "label": label}
    agg = pd.concat(per_bar_rets, axis=1).sum(axis=1) / capital
    ppy = bars_per_year_from_index(agg.index)
    sharpe = agg.mean()/agg.std(ddof=1)*np.sqrt(ppy) if agg.std(ddof=1) > 0 else 0
    ann = (1+agg).prod()**(ppy/len(agg)) - 1
    equity = (1+agg).cumprod()
    max_dd = ((equity/np.maximum.accumulate(equity))-1).min()
    return {
        "label": label, "n_coins": n_coins_used, "n_bars": len(agg),
        "sharpe": float(sharpe), "ann_ret": float(ann),
        "total_ret": float(equity.iloc[-1]-1), "max_dd": float(max_dd),
        "rets": agg, "ppy": ppy,
    }


def main():
    close, fund_sum, fund_last, vol = build_panel()
    print(f"Panel: {close.index.min().date()} -> {close.index.max().date()} ({len(close)} days, {close.shape[1]} coins)")

    rank_signal = cross_sectional_rank_signal(fund_last)

    # -------- NAIVE BASELINE (full sample) --------
    tgt_naive = naive_target(rank_signal, top_n=3)
    res_naive = aggregate_backtest(tgt_naive, close, fund_sum, vol, label="naive_carry")
    print(f"\n=== NAIVE CARRY (full sample, in-sample) ===")
    print(f"  Sharpe: {res_naive['sharpe']:+.2f} | APR: {res_naive['ann_ret']*100:+.2f}% | maxDD: {res_naive['max_dd']*100:.1f}%")
    print(f"  coins used: {res_naive['n_coins']}")

    # -------- PERSISTENCE V1 (regime) --------
    for tau in [0.3, 0.4, 0.5, 0.6]:
        mask = persistence_mask_v1(fund_last, window=30, tau=tau)
        tgt = naive_target(rank_signal, top_n=3) * mask
        r = aggregate_backtest(tgt, close, fund_sum, vol, label=f"persist_v1_tau{tau}")
        print(f"  V1 (regime AR1>{tau}): Sharpe {r['sharpe']:+.2f} | APR {r['ann_ret']*100:+.2f}% | maxDD {r['max_dd']*100:.1f}% | bars {r['n_bars']}")

    # -------- PERSISTENCE V2 (forecast) --------
    for q in [0.3, 0.5, 0.7]:
        mask = persistence_mask_v2(fund_last, window=30, q=q)
        tgt = naive_target(rank_signal, top_n=3) * mask
        r = aggregate_backtest(tgt, close, fund_sum, vol, label=f"persist_v2_q{q}")
        print(f"  V2 (fcst q={q}):      Sharpe {r['sharpe']:+.2f} | APR {r['ann_ret']*100:+.2f}% | maxDD {r['max_dd']*100:.1f}% | bars {r['n_bars']}")

    # Save naive + best-persist rets for the next stage (OOS)
    res_naive["rets"].to_pickle("/tmp/rets_naive.pkl")
    mask_best = persistence_mask_v1(fund_last, window=30, tau=0.4)
    tgt_best = naive_target(rank_signal, top_n=3) * mask_best
    res_best = aggregate_backtest(tgt_best, close, fund_sum, vol, label="persist_v1_tau0.4")
    res_best["rets"].to_pickle("/tmp/rets_persist.pkl")
    print("\nSaved return series to /tmp/rets_*.pkl for OOS analysis.")


if __name__ == "__main__":
    main()
