"""Generate the 3 honest figures for the PDF report (validated palette, print)."""
import numpy as np, pandas as pd
import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

mpl.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 10,
    "axes.edgecolor": "#52514e", "axes.labelcolor": "#0b0b0b",
    "xtick.color": "#52514e", "ytick.color": "#52514e", "text.color": "#0b0b0b",
    "axes.spines.top": False, "axes.spines.right": False,
    "grid.color": "#e4e3df", "grid.linewidth": 0.8, "axes.grid": True,
    "axes.axisbelow": True, "figure.facecolor": "#fcfcfb", "axes.facecolor": "#fcfcfb",
})
# validated palette (light surface)
BLUE, GREEN, MAG, YEL, AQUA, ORANGE, RED = "#2a78d6", "#008300", "#e87ba4", "#eda100", "#1baf7a", "#eb6834", "#d03b3b"
GOOD, WARN, SERIOUS, CRIT = "#0ca30c", "#fab219", "#ec835a", "#d03b3b"
SEC = "#52514e"

from slate_core.dex.data.load_data import load_candles, merge_funding
from slate_core.dex.data.hyperliquid_client import HLClient
from slate_core.discovery.regime_detector import RegimeDetector
from slate_core.discovery.mega_sweep import _precompute, gen_signals, fast_backtest
from slate_core.portfolio.regime_switch import DEFAULT_REGIME_MAP

# ---- FIG 1: the lookahead artifact — equity curves (buggy vs honest) ----
c = HLClient(); rd = RegimeDetector(use_hmm=False)
def equity(rets): return np.cumprod(1 + np.nan_to_num(rets))
buggy_eq = honest_eq = None
for coin in ["SOL", "BTC", "ETH"]:
    df = merge_funding(load_candles(f"sol_data_cache/HYPERLIQUID_{coin}_1h.json"), c, coin)
    ind = _precompute(df); rg = rd.detect(df).values; n = len(df); sig = np.zeros(n, int)
    for lab, (st, pa) in DEFAULT_REGIME_MAP.items():
        m = rg == lab
        if m.sum() >= 10: sig[m] = gen_signals(ind, st, **pa)[m]
    closes = df["close"].astype(float).values
    buggy = fast_backtest(sig, closes)              # now-honest fast_backtest (lagged)
    # reconstruct the OLD buggy attribution for the visual
    bar = np.zeros(n); bar[1:] = closes[1:] / closes[:-1] - 1
    buggy_old = sig * bar - np.abs(np.diff(sig, prepend=0)) * (0.0005 + 0.0015) * 0.85
    b = equity(buggy_old); h = equity(buggy)
    m = min(len(b), len(h))
    if buggy_eq is None:
        buggy_eq = np.zeros(m); honest_eq = np.zeros(m)
    m = min(m, len(buggy_eq))
    buggy_eq = buggy_eq[:m] + b[:m]
    honest_eq = honest_eq[:m] + h[:m]
buggy_eq /= 3; honest_eq = honest_eq / 3
m = min(len(buggy_eq), len(honest_eq)); buggy_eq = buggy_eq[:m]; honest_eq = honest_eq[:m]
fig, ax = plt.subplots(figsize=(6.4, 3.4))
ax.plot(buggy_eq, color=ORANGE, lw=2.0, label="Shipped (1-bar lookahead)")
ax.plot(honest_eq, color=BLUE, lw=2.0, label="Corrected (honest, 1-bar lag)")
ax.axhline(1.0, color=SEC, lw=0.8, ls="--")
ax.set_yscale("log")
ax.set_xlabel("hourly bar (Dec 2025 – Jul 2026)"); ax.set_ylabel("equity (log), start = 1")
ax.set_title("The +3.43 Sharpe was a lookahead artifact", fontsize=11, weight="bold", color="#0b0b0b")
ax.legend(frameon=False, loc="lower left", fontsize=9)
ax.text(0.985, 0.06, f"Shipped: Sharpe +3.43", transform=ax.transAxes, color=ORANGE,
        ha="right", va="bottom", fontsize=9, weight="bold")
ax.text(0.985, 0.94, f"Honest: Sharpe −5.98", transform=ax.transAxes, color=BLUE,
        ha="right", va="top", fontsize=9, weight="bold")
fig.tight_layout(); fig.savefig("report_fig1_lookahead.pdf"); plt.close(fig)
print("fig1 done")

# ---- FIG 2: positive rate by timeframe ----
res = pd.read_csv("honest_sweep_results.csv"); res = res[res["oos_sharpe"].notna()]
order = ["cex_1h_SOL", "cex_4h_SOL", "cex_8h_SOL", "cex_12h_SOL", "cex_daily_SOL"]
labels = ["1h", "4h", "8h", "12h", "Daily"]
pos = [100 * (res[res.dataset == d]["oos_sharpe"] > 0).mean() for d in order]
fig, ax = plt.subplots(figsize=(6.4, 3.0))
bars = ax.bar(labels, pos, color=[BLUE if l != "Daily" else GREEN for l in labels], width=0.62)
for b, v in zip(bars, pos):
    ax.text(b.get_x() + b.get_width() / 2, v + 0.6, f"{v:.0f}%", ha="center", va="bottom",
            fontsize=9, color="#0b0b0b", weight="bold")
ax.set_ylabel("% of variants with OOS Sharpe > 0")
ax.set_xlabel("bar timeframe (CEX SOL)")
ax.set_ylim(0, max(pos) * 1.25)
ax.set_title("Only the daily timeframe has signal — intraday is eaten by costs",
             fontsize=11, weight="bold", color="#0b0b0b")
fig.tight_layout(); fig.savefig("report_fig2_timeframe.pdf"); plt.close(fig)
print("fig2 done")

# ---- FIG 3: LP fee yield vs max IL by pool ----
import json
summ = json.load(open("sol_data_cache/amm_basket_summary.json"))
from slate_core.backtest.lp import backtest_lp
from run_lp import daily_close
eth = daily_close("ETHUSDT"); btc = daily_close("BTCUSDT")
def ratio_for(sym):
    s = sym.upper().replace("-", "")
    if "WETH" in s and "WBTC" not in s: return eth
    if "WBTC" in s and "WETH" not in s: return btc
    if "WBTC" in s and "WETH" in s: return (btc / eth).dropna()
    return None
rows = []
for p in summ:
    pr = ratio_for(p["symbol"])
    r = backtest_lp(p["pool"], price_ratio=pr)
    stable = pr is None
    rows.append((p["symbol"] + "\n" + p["chain"], r.fee_apr_pct, abs(r.max_il_pct), stable))
fig, ax = plt.subplots(figsize=(6.4, 3.6))
for name, fee, il, stable in rows:
    ax.scatter(fee, il, s=70, color=GOOD if stable else ORANGE, edgecolor="white", lw=1.0, zorder=3)
    ax.annotate(name, (fee, il), fontsize=7.2, color="#0b0b0b",
                xytext=(5, 4), textcoords="offset points")
ax.set_xlabel("realized fee APR (%)  —  DefiLlama apyBase")
ax.set_ylabel("max impermanent loss (%)")
ax.set_title("LP: stablecoin pools earn fees with ~zero IL; volatile pools pay IL",
             fontsize=10.5, weight="bold", color="#0b0b0b")
ax.scatter([], [], color=GOOD, label="stablecoin pair (IL ≈ 0)")
ax.scatter([], [], color=ORANGE, label="volatile pair")
ax.legend(frameon=False, fontsize=8.5, loc="upper left")
fig.tight_layout(); fig.savefig("report_fig3_lp.pdf"); plt.close(fig)
print("fig3 done")
