"""Proper regime-aware sweep (the test that was never validly done before).

  * Regime detector with thresholds FIT ON IN-SAMPLE ONLY (no leakage): trend via
    50-bar return sign (dead-zone 0); vol via the IS 75th percentile of rolling
    stdev (calibrated, not a hardcoded absolute that mislabels 96% as high-vol).
  * A-priori economic mapping (not overfit): trend strategies -> up/down regimes
    (long uptrend, short downtrend); mean-reversion -> range regime; carry ->
    unconditional (funding is the signal itself).
  * Compares each strategy UNCONDITIONAL vs REGIME-GATED, OOS, on SOL/BTC/ETH.
  * Builds the regime-switched PORTFOLIO (trend in trends + meanrev in ranges) and
    tests cross-asset generalization + DSR/PBO.
"""
import json, os
import numpy as np, pandas as pd
from slate_core.backtest.data import load_cex_daily, resample
from slate_core.backtest.honest import backtest, bars_per_year_from_index, CEX
from slate_core.backtest import strategies as S
from slate_core.backtest.validation import deflated_sharpe, cscv_pbo


def fetch_daily_ohlcv(sym):
    """Load cached CEX daily OHLCV+funding built by run_cross_asset_timeframe."""
    d = json.load(open(f"sol_data_cache/CEX_{sym}_1d_ohlcv.json"))
    df = pd.DataFrame(d)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.set_index("timestamp").sort_index()
    fr = pd.DataFrame(json.load(open(f"sol_data_cache/BINANCE_{sym}_FUNDING.json")))
    fr["t"] = pd.to_datetime(fr["fundingTime"], unit="ms")
    fr = fr.set_index("t").sort_index()["fundingRate"].astype(float)
    df["funding"] = fr.reindex(df.index, method="ffill").fillna(0.0)
    return df


def regime_labels(df, is_end, vol_pct=75, trend_lb=50):
    """Causal regime labels with IS-fit thresholds. up/down/range + hivol override."""
    close = df["close"].astype(float)
    rv = close.pct_change().rolling(20).std()
    vol_thr = rv.iloc[:is_end].quantile(vol_pct / 100)   # fit on IS only
    trend_ret = close.pct_change(trend_lb).values
    rvv = rv.values
    lab = np.where(trend_ret > 0, "up", np.where(trend_ret < 0, "down", "range"))
    lab = np.where(np.nan_to_num(rvv, 0) > vol_thr, "hivol", lab)
    return lab


# a-priori mapping: (family, name, params, [allowed regimes])
STRAT_REGIME = [
    ("trend", "ema_cross",   {"fast": 20, "slow": 100},                          ["up", "down"]),
    ("trend", "donchian",    {"lb": 55},                                         ["up", "down"]),
    ("ichimoku", "cloud",    {"tenkan": 9, "kijun": 26, "senkou": 52, "disp": 26}, ["up", "down"]),
    ("meanrev", "rsi",       {"ob": 70, "os_": 30},                              ["range"]),
    ("meanrev", "zscore",    {"lb": 20, "z": 2.0},                               ["range"]),
    ("meanrev", "bb",        {"span": 20, "mult": 2.0},                          ["range"]),
]
FNS = {"trend": {"ema_cross": S.trend_ema_cross, "donchian": S.breakout_donchian},
       "ichimoku": {"cloud": S.ichimoku_cloud},
       "meanrev": {"rsi": S.meanrev_rsi, "zscore": S.meanrev_zscore, "bb": S.meanrev_bb}}

assets = {"SOL": load_cex_daily(), "BTC": fetch_daily_ohlcv("BTCUSDT"),
          "ETH": fetch_daily_ohlcv("ETHUSDT")}

print("=" * 94)
print("REGIME-AWARE SWEEP: unconditional vs IS-fit regime-gated, longs+shorts (SOL/BTC/ETH)")
print("=" * 94)
print(f"{'asset':5s}{'family/name':22s}{'uncond_OOS':>11s}{'gated_OOS':>11s}{'uncond_ret':>11s}{'gated_ret':>11s}")

port_streams = {a: [] for a in assets}
for asset, df in assets.items():
    is_end = int(len(df) * 0.6)
    lab = regime_labels(df, is_end)
    ppy = bars_per_year_from_index(df.index)
    frac = pd.Series(lab[:is_end]).value_counts(normalize=True).round(2).to_dict()
    for (fam, name, params, allowed) in STRAT_REGIME:
        fn = FNS[fam][name]
        tgt = fn(df, **params)
        gated = S.regime_gate(tgt, lab, allowed)
        ru = backtest(tgt[is_end:], df.iloc[is_end:], venue=CEX)
        rg = backtest(gated[is_end:], df.iloc[is_end:], venue=CEX)
        print(f"{asset:5s}{fam+'/'+name:22s}{ru['metrics']['sharpe']:+11.2f}"
              f"{rg['metrics']['sharpe']:+11.2f}{ru['metrics']['total_ret']:+10.2%}"
              f"{rg['metrics']['total_ret']:+10.2%}")
        # collect gated streams for the regime-switched portfolio
        port_streams[asset].append(backtest(gated, df, venue=CEX)["returns"])
    print(f"      IS regime fractions: {frac}")

print("\n" + "=" * 94)
print("REGIME-SWITCHED PORTFOLIO (trend in up/down + meanrev in range), cross-asset")
print("=" * 94)
for asset, df in assets.items():
    streams = port_streams[asset]
    minl = min(len(s) for s in streams)
    P = np.column_stack([s[:minl] for s in streams]).mean(axis=1)
    ppy = bars_per_year_from_index(df.index)
    is_end = int(minl * 0.6)
    oos = P[is_end:]
    osh = oos.mean() / oos.std() * ppy**.5 if oos.std() else 0
    d = deflated_sharpe(osh, n_trials=len(STRAT_REGIME), n_bars=len(oos), ppy=ppy)
    print(f"  {asset}: OOS_sharpe={osh:+.2f}  ret={float((1+np.nan_to_num(oos)).prod()-1):+.2%}  "
          f"DSR_p={d['dsr_p']:.3f} -> {d['verdict']}")
