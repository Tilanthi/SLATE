"""Reproduce the +3.43 regime-switch Sharpe, then test the 1-bar-lookahead
hypothesis with a corrected backtester. ONE variable changed at a time:
same data, same signals, same costs — only the return-attribution timing.

Current code : rets[t]   = signal[t]   * (close[t]/close[t-1] - 1)   <- lookahead
Corrected    : rets[t]   = signal[t-1] * (close[t]/close[t-1] - 1)   <- decide at close[t-1], earn bar t

signal[t] is computed from close[t] (trend_follow uses c[t]/ema[t], momentum
uses c[t]/c[t-lb], etc.), so crediting it the return that ENDS at close[t] uses
information you could not have had at the start of bar t.
"""
from __future__ import annotations
import numpy as np

from slate_core.dex.data.load_data import load_candles, merge_funding
from slate_core.dex.data.hyperliquid_client import HLClient
from slate_core.discovery.regime_detector import RegimeDetector, ALL_REGIMES
from slate_core.discovery.mega_sweep import _precompute, gen_signals, fast_backtest
from slate_core.portfolio.regime_switch import DEFAULT_REGIME_MAP
from slate_core.statistics.equity_curve import portfolio_metrics

PPY = 8760  # hourly — same as the original pipeline


def combined_signals(df, detector, regime_map):
    ind = _precompute(df)
    regime = detector.detect(df).values
    n = len(df)
    combined = np.zeros(n, dtype=int)
    for label, (stype, params) in regime_map.items():
        mask = regime == label
        if mask.sum() < 10:
            continue
        sub = gen_signals(ind, stype, **params)
        combined[mask] = sub[mask]
    return combined


def corrected_backtest(signals, closes, fee=0.0005, slippage_bps=15.0, fill_rate=0.85):
    """Same cost model as fast_backtest, but signal is lagged by 1 bar so a
    decision made at close[t-1] earns the bar-t return (close[t]/close[t-1]-1)."""
    n = len(signals)
    bar_ret = np.zeros(n)
    bar_ret[1:] = closes[1:] / closes[:-1] - 1.0
    pos_held = np.zeros(n)               # position actually held during bar t
    pos_held[1:] = signals[:-1].astype(float)   # decided at close[t-1]
    cost_per_side = (fee + slippage_bps / 10000.0) * fill_rate
    trade_cost = np.abs(np.diff(pos_held, prepend=0)) * cost_per_side
    return pos_held * bar_ret - trade_cost


def run():
    client = HLClient()
    coins = {}
    for coin in ["SOL", "BTC", "ETH"]:
        df = load_candles(f"sol_data_cache/HYPERLIQUID_{coin}_1h.json")
        df = merge_funding(df, client, coin)
        coins[coin] = df
    rd = RegimeDetector(use_hmm=False)

    # equal-weight across coins, same as run_regime_switch_backtest
    all_orig, all_corr = [], []
    per_coin = {}
    for coin, df in coins.items():
        sig = combined_signals(df, rd, DEFAULT_REGIME_MAP)
        closes = df["close"].astype(float).values
        n_trades = int(np.sum(np.abs(np.diff(sig, prepend=0))) // 2)
        r_orig = fast_backtest(sig, closes)
        r_corr = corrected_backtest(sig, closes)
        mo = portfolio_metrics(r_orig, periods_per_year=PPY)
        mc = portfolio_metrics(r_corr, periods_per_year=PPY)
        per_coin[coin] = (n_trades, mo["sharpe"], mc["sharpe"])
        all_orig.append(r_orig)
        all_corr.append(r_corr)

    min_len = min(len(x) for x in all_orig)
    P_orig = np.zeros(min_len)
    P_corr = np.zeros(min_len)
    w = 1.0 / len(coins)
    for ro, rc in zip(all_orig, all_corr):
        P_orig += w * ro[:min_len]
        P_corr += w * rc[:min_len]

    Mo = portfolio_metrics(P_orig, periods_per_year=PPY)
    Mc = portfolio_metrics(P_corr, periods_per_year=PPY)

    print("=" * 72)
    print(f"{'coin':6s} {'#roundtrips':>11s} {'orig Sharpe':>12s} {'corrected':>10s}")
    for coin, (nt, so, sc) in per_coin.items():
        print(f"{coin:6s} {nt:>11d} {so:>+12.2f} {sc:>+10.2f}")
    print("-" * 72)
    print(f"{'PORTFOLIO (equal-wt)':20s} orig Sharpe={Mo['sharpe']:+.2f}  "
          f"ann={Mo['annualized_return']:+.3%}  maxDD={Mo['max_drawdown']:.3f}")
    print(f"{'PORTFOLIO (1-bar lag)':20s} corr Sharpe={Mc['sharpe']:+.2f}  "
          f"ann={Mc['annualized_return']:+.3%}  maxDD={Mc['max_drawdown']:.3f}")
    print("=" * 72)

    # 5-fold walk-forward on the corrected portfolio (same flawed method, for
    # comparison) — does the positivity survive the lookahead fix?
    fs = min_len // 5
    print("corrected walk-forward (chronological folds, in-sample regime map):")
    for f in range(5):
        s = f * fs
        e = s + fs if f < 4 else min_len
        m = portfolio_metrics(P_corr[s:e], periods_per_year=PPY)
        print(f"  fold {f}: sharpe={m['sharpe']:+.2f}  ann={m['annualized_return']:+.3%}")


if __name__ == "__main__":
    run()
