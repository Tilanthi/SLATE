"""Simple vs GMM (probabilistic) regime detector + vol-target sizing.

Answers: (1) is a probabilistic regime detector better than the simple threshold
one? (2) does intelligent (vol-target) sizing help? Both fit on IS only.
"""
import json
import numpy as np, pandas as pd
from slate_core.backtest.data import load_cex_daily
from slate_core.backtest.honest import backtest, bars_per_year_from_index, CEX
from slate_core.backtest import strategies as S
from slate_core.backtest.regime_ml import gmm_regime, vol_target


def fetch(sym):
    d = json.load(open(f"sol_data_cache/CEX_{sym}_1d_ohlcv.json"))
    df = pd.DataFrame(d); df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.set_index("timestamp").sort_index()
    fr = pd.DataFrame(json.load(open(f"sol_data_cache/BINANCE_{sym}_FUNDING.json")))
    fr["t"] = pd.to_datetime(fr["fundingTime"], unit="ms"); fr = fr.set_index("t")["fundingRate"].astype(float)
    df["funding"] = fr.reindex(df.index, method="ffill").fillna(0.0)
    return df


def simple_labels(df, is_end):
    c = df["close"].astype(float); rv = c.pct_change().rolling(20).std()
    vt = rv.iloc[:is_end].quantile(0.75)
    tr = c.pct_change(50).values
    lab = np.where(tr > 0, "up", np.where(tr < 0, "down", "range"))
    lab = np.where(np.nan_to_num(rv.values, 0) > vt, "hivol", lab)
    return lab


assets = {"SOL": load_cex_daily(), "BTC": fetch("BTCUSDT"), "ETH": fetch("ETHUSDT")}
FNS = [("ema_cross", S.trend_ema_cross, {"fast": 20, "slow": 100}),
       ("donchian", S.breakout_donchian, {"lb": 55}),
       ("ichimoku", S.ichimoku_cloud, {"tenkan": 9, "kijun": 26, "senkou": 52, "disp": 26})]

print("=" * 96)
print("REGIME DETECTOR COMPARISON: none vs simple(IS-fit) vs GMM-probabilistic(IS-fit)  [trend->up/down]")
print("=" * 96)
print(f"{'asset':5s}{'strategy':12s}{'none':>8s}{'simple':>8s}{'gmm':>8s}{'best':>8s}")
agg = {"none": [], "simple": [], "gmm": []}
for asset, df in assets.items():
    is_end = int(len(df) * 0.6)
    ppy = bars_per_year_from_index(df.index)
    lab_s = simple_labels(df, is_end)
    lab_g = gmm_regime(df, is_end, n_states=4)
    for name, fn, p in FNS:
        tgt = fn(df, **p)
        r_none = backtest(tgt[is_end:], df.iloc[is_end:], venue=CEX)["metrics"]["sharpe"]
        r_s = backtest(S.regime_gate(tgt, lab_s, ["up", "down"])[is_end:], df.iloc[is_end:], venue=CEX)["metrics"]["sharpe"]
        r_g = backtest(S.regime_gate(tgt, lab_g, ["up", "down"])[is_end:], df.iloc[is_end:], venue=CEX)["metrics"]["sharpe"]
        agg["none"].append(r_none); agg["simple"].append(r_s); agg["gmm"].append(r_g)
        best = ("none", r_none) if r_none >= max(r_s, r_g) else (("simple", r_s) if r_s >= r_g else ("gmm", r_g))
        print(f"{asset:5s}{name:12s}{r_none:+8.2f}{r_s:+8.2f}{r_g:+8.2f}{best[0]:>8s}")
print(f"\n  mean OOS Sharpe across all 9 trend-lines: "
      f"none={np.mean(agg['none']):+.2f}  simple={np.mean(agg['simple']):+.2f}  gmm={np.mean(agg['gmm']):+.2f}")

print("\n" + "=" * 96)
print("VOL-TARGET SIZING effect (does constant-risk sizing help the best trend lines?)")
print("=" * 96)
for asset, df in assets.items():
    is_end = int(len(df) * 0.6); ppy = bars_per_year_from_index(df.index)
    for name, fn, p in [("ema_cross", S.trend_ema_cross, {"fast": 20, "slow": 100})]:
        tgt = fn(df, **p)
        sized = vol_target(tgt, df, target_vol=0.6, cap=2.0, ppy=ppy)
        r_fixed = backtest(tgt[is_end:], df.iloc[is_end:], venue=CEX)["metrics"]
        r_sized = backtest(sized[is_end:], df.iloc[is_end:], venue=CEX)["metrics"]
        print(f"  {asset} {name}: fixed Sharpe={r_fixed['sharpe']:+.2f} (ret {r_fixed['total_ret']:+.2%})  "
              f"vol-target Sharpe={r_sized['sharpe']:+.2f} (ret {r_sized['total_ret']:+.2%}, "
              f"maxdd {r_fixed['max_dd']:.2f}->{r_sized['max_dd']:.2f})")
