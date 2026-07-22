"""Timeframe study: does the 'coarser candle is better' trend CONTINUE past daily,
or plateau? Resample the 3-yr CEX SOL daily series to 2-day / 3-day / weekly and
re-run the full strategy grid through the honest pipeline.

Honest caveat built in: bars shrink fast (1080 daily -> ~154 weekly), so Sharpe
estimates get noisy and warmup eats more of the sample. We report bar counts and
treat weekly as near the edge of testability.
"""
import numpy as np
from slate_core.backtest.data import load_cex_daily, resample
from slate_core.backtest.honest import backtest, bars_per_year_from_index, CEX
from slate_core.backtest import strategies as S
from slate_core.backtest.validation import deflated_sharpe

daily = load_cex_daily()
datasets = {
    "1D":  daily,
    "2D":  resample(daily, "2D"),
    "3D":  resample(daily, "3D"),
    "1W":  resample(daily, "W"),
}
variants = S.expand_grid()

print("=" * 90)
print("TIMEFRAME STUDY: 1D -> 2D -> 3D -> 1W  (CEX SOL, 3yr, honest costs)")
print("=" * 90)
print(f"{'TF':4s} {'bars':>5s} {'variants':>9s} {'med_OOS':>8s} {'%pos':>6s} "
      f"{'%>1':>6s} {'robust':>7s} {'best_OOS':>9s}")

summary = {}
for tf, df in datasets.items():
    ppy = bars_per_year_from_index(df.index)
    venue = CEX
    oos_sh, n_pos, n_gt1, robust, best = [], 0, 0, 0, -9
    best_row = None
    for fam, name, fn, p in variants:
        try:
            t = fn(df, **p)
            if np.nansum(np.abs(t)) == 0:
                continue
            k = int(len(df) * 0.6)
            ish = backtest(t[:k], df.iloc[:k], venue=venue)["metrics"]["sharpe"]
            oos = backtest(t[k:], df.iloc[k:], venue=venue)
            sh = oos["metrics"]["sharpe"]
            oos_sh.append(sh)
            if sh > 0: n_pos += 1
            if sh > 1: n_gt1 += 1
            if ish > 0 and sh > 0 and oos["metrics"]["n_trades"] >= 8: robust += 1
            if sh > best:
                best = sh; best_row = (fam, name, p, sh, oos["metrics"]["n_trades"])
        except Exception:
            pass
    n = len(oos_sh)
    med = float(np.median(oos_sh)) if n else float("nan")
    summary[tf] = (len(df), n, med, n_pos / n if n else 0, robust, best_row, ppy)
    print(f"{tf:4s} {len(df):5d} {n:9d} {med:+8.2f} {100*(n_pos/n) if n else 0:5.0f}% "
          f"{100*(n_gt1/n) if n else 0:5.0f}% {robust:7d} {best:+9.2f}")

print("\n--- best line per timeframe (OOS) ---")
for tf, (nb, n, med, pos, rob, brow, ppy) in summary.items():
    if brow:
        fam, name, p, sh, trd = brow
        d = deflated_sharpe(sh, n_trials=len(variants), n_bars=int(nb*0.4), ppy=ppy)
        print(f"  {tf}: {fam}/{name} {p}  OOS_sh={sh:+.2f} (trd={int(trd)})  "
              f"DSR_p={d['dsr_p']:.3f} -> {d['verdict']}")

print("\n--- read on the trend ---")
meds = {tf: summary[tf][2] for tf in datasets}
print("  median OOS Sharpe by TF:", {tf: round(m, 2) for tf, m in meds.items()})
