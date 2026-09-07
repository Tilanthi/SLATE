"""
Leveraged stablecoin-LP looping — honest prototype test on REAL data.

Structure:
  Equity E, borrow B at stable rate r_b, LP A = E + B earning APY y_lp.
  Leverage L = A / E = 1 + B/E.
  Net carry (annualized):  y_net = L * y_lp - (L-1) * r_b  - fee_drag
  - LP leg: REAL 1,549-day USDC-USDT Uniswap V3 Ethereum APY history (DefiLlama).
  - Borrow leg: Aave/Compound stable borrow. We don't have a real time-series for
    this in the cache, so we run an honest sensitivity sweep (4-8%) plus a model
    where borrow = max(4%, LP_APY*0.85) — i.e., borrow tracks LP yield somewhat
    (Aave stable rates DO rise when LP yields rise because both respond to on-chain
    demand).
  - Tail: REAL stablecoin depeg events (Mar-2023 USDC -13%, etc.) applied to
    collateral; liquidation when LTV breach.

NO SYNTHETIC PRICE DATA. Only real APY history + documented historical depeg moves.
"""
import json
import numpy as np
from pathlib import Path

CACHE = Path("/Users/gjw255/astrodata/SWARM/SLATE/sol_data_cache")
OUT = Path("/Users/gjw255/astrodata/SWARM/SLATE/novel_findings")
OUT.mkdir(exist_ok=True, parents=True)

# -----------------------------------------------------------------------------
# 1. Load REAL LP APY history (USDC-USDT Uniswap V3 Ethereum, 1549 days)
# -----------------------------------------------------------------------------
with open(CACHE / "amm_pool_e737d721-f45c-40f0-9793-9f56261862b9.json") as f:
    pool = json.load(f)

ts = [r["timestamp"][:10] for r in pool]
apy_base_pct = np.array([r["apyBase"] if r["apyBase"] is not None else np.nan for r in pool], float)
apy_reward_pct = np.array([r["apyReward"] if r["apyReward"] is not None else 0.0 for r in pool], float)
tvl = np.array([r["tvlUsd"] if r["tvlUsd"] is not None else np.nan for r in pool], float)

# Total APY = base + reward (reward is the extra token emissions)
apy_total_pct = np.where(np.isfinite(apy_base_pct), apy_base_pct, 0.0) + apy_reward_pct
apy_total_frac = apy_total_pct / 100.0
apy_daily = apy_total_frac / 365.0  # convert annual % to daily fraction

print("=" * 72)
print("REAL DATA: USDC-USDT Uniswap V3 Ethereum (the canonical stablecoin LP)")
print(f"  Period: {ts[0]} to {ts[-1]}  ({len(ts)} days, ~{len(ts)/365:.1f} yrs)")
print(f"  TVL now: ${tvl[-1]/1e6:.1f}M  (peak ${np.nanmax(tvl)/1e6:.1f}M)")
print(f"  apyBase:    mean={np.nanmean(apy_base_pct):.2f}%  "
      f"median={np.nanmedian(apy_base_pct):.2f}%  "
      f"std={np.nanstd(apy_base_pct):.2f}%  "
      f"p5={np.nanpercentile(apy_base_pct,5):.2f}%  "
      f"p95={np.nanpercentile(apy_base_pct,95):.2f}%")
print(f"  apyReward:  mean={np.nanmean(apy_reward_pct):.3f}%  "
      f"(usually 0 for this pool)")
print(f"  apyTotal:   mean={np.nanmean(apy_total_pct):.2f}%  "
      f"median={np.nanmedian(apy_total_pct):.2f}%  "
      f"std={np.nanstd(apy_total_pct):.2f}%")

# -----------------------------------------------------------------------------
# 2. ANALYTICAL: net yield surface across (leverage, borrow rate)
#    y_net = L * y_lp - (L-1) * r_b
# -----------------------------------------------------------------------------
print("\n" + "=" * 72)
print("ANALYTICAL NET YIELD:  y_net(L, r_b) = L * y_lp - (L-1) * r_b")
print("  Using realized median LP apyBase = "
      f"{np.nanmedian(apy_base_pct):.2f}% (no reward tokens, conservative)")
y_lp = np.nanmedian(apy_base_pct) / 100.0  # use median base only

print(f"\n  {'r_borrow':>9s}", end="")
for L in [1.0, 1.5, 2.0, 3.0, 5.0, 8.0, 10.0]:
    print(f"  L={L:>4.1f}x", end="")
print()
peak_net = -99; peak_L = 0; peak_rb = 0
for rb_pct in [3.0, 4.0, 5.0, 6.0, 7.0, 8.0]:
    rb = rb_pct / 100.0
    print(f"  {rb_pct:>7.1f}% ", end="")
    for L in [1.0, 1.5, 2.0, 3.0, 5.0, 8.0, 10.0]:
        ynet = L * y_lp - (L - 1) * rb
        print(f"  {ynet*100:>6.2f}%", end="")
        if ynet > peak_net:
            peak_net = ynet; peak_L = L; peak_rb = rb_pct
    print()

print(f"\n  -> Peak analytical net = {peak_net*100:.2f}% at L={peak_L}x, r_b={peak_rb}%")
print("  -> NOTE: when r_borrow > y_lp, leverage AMPLIFIES LOSSES (negative carry).")
print(f"  -> Break-even borrow rate at any L: r_b = y_lp = {y_lp*100:.2f}% "
      "(independent of L for the linear model).")

# -----------------------------------------------------------------------------
# 3. TIME-SERIES BACKTEST: compound daily, real APY path, sweep leverage
#    Per day: equity *= (1 + L*y_lp_d - (L-1)*r_b_d)
#    Two borrow models: (a) constant 5%, (b) borrow tracks LP (r_b = 0.85*max(4%, y_lp))
# -----------------------------------------------------------------------------
print("\n" + "=" * 72)
print("TIME-SERIES BACKTEST (compound real daily APY, 1549 days)")

def run_loop(apy_daily_arr, rb_daily_arr, L):
    """Compound the looping strategy. Returns daily equity curve."""
    eq = np.ones(len(apy_daily_arr))
    for i in range(1, len(eq)):
        # gross: LP earns on full A = L*E; borrow cost on B = (L-1)*E
        ret = L * apy_daily_arr[i] - (L - 1) * rb_daily_arr[i]
        eq[i] = eq[i-1] * (1.0 + ret)
    return eq

def metrics(eq, years):
    total = eq[-1] / eq[0] - 1
    apr = (eq[-1] / eq[0]) ** (1 / years) - 1
    rets = np.diff(eq) / eq[:-1]
    if rets.std() > 0:
        sharpe = np.sqrt(365) * rets.mean() / rets.std()
    else:
        sharpe = 0.0
    dd = np.maximum.accumulate(eq)
    mdd = np.min(eq / dd - 1)
    return dict(total=total, apr=apr, sharpe=sharpe, mdd=mdd)

years = len(apy_daily) / 365.0
yrs = years

print(f"\n  Window: {years:.2f} years")
print(f"\n  === Borrow model A: constant 5% (Aave/Compound typical stable) ===")
print(f"  {'Leverage':>9s}  {'APR':>8s}  {'Sharpe':>7s}  {'MaxDD':>8s}  {'Equity':>8s}")
rb_const = np.full(len(apy_daily), 0.05 / 365.0)
results_A = {}
for L in [1.0, 1.5, 2.0, 3.0, 5.0, 8.0]:
    eq = run_loop(apy_daily, rb_const, L)
    m = metrics(eq, yrs)
    results_A[L] = (m, eq)
    print(f"  {L:>7.1f}x  {m['apr']*100:>6.2f}%  {m['sharpe']:>6.2f}  "
          f"{m['mdd']*100:>6.2f}%  {eq[-1]:>7.2f}x")

print(f"\n  === Borrow model B: borrow tracks LP yield (r_b = 0.85*y_lp, floored 3%) ===")
print(f"  (Mimics Aave variable stable rate rising with on-chain demand)")
rb_track = np.maximum(0.03/365.0, 0.85 * apy_daily)
print(f"  {'Leverage':>9s}  {'APR':>8s}  {'Sharpe':>7s}  {'MaxDD':>8s}  {'Equity':>8s}")
results_B = {}
for L in [1.0, 1.5, 2.0, 3.0, 5.0, 8.0]:
    eq = run_loop(apy_daily, rb_track, L)
    m = metrics(eq, yrs)
    results_B[L] = (m, eq)
    print(f"  {L:>7.1f}x  {m['apr']*100:>6.2f}%  {m['sharpe']:>6.2f}  "
          f"{m['mdd']*100:>6.2f}%  {eq[-1]:>7.2f}x")

# -----------------------------------------------------------------------------
# 4. DEPEG TAIL RISK — the real killer for leveraged stablecoin LP
#    Documented historical depeg events (real, not synthesized):
#      - Mar 11-13, 2023: USDC depegged to ~$0.87 (SVB collapse); USDT briefly to $1.06
#      - May 9-12, 2022: UST collapse $1 -> $0.01 (full loss)
#      - Nov 2022: USDC briefly $0.996 (FTX); USDT briefly $0.98
#      - Feb 2023: USDC briefly $0.998 (BYDFi); many small USDT blips $0.995-1.005
#    For a stablecoin-vs-stablecoin LP (USDC-USDT), if both stay near $1, IL is ~0
#    and the LP value in USD barely moves. The real risk is if EITHER side depegs
#    badly while you hold leveraged exposure.
# -----------------------------------------------------------------------------
print("\n" + "=" * 72)
print("DEPEG TAIL RISK — applied to leveraged stablecoin LP")
print("  Documented historical events (NOT simulated):")
print("    USDC Mar-2023 (SVB):      -13% intraday, recovered in 3 days")
print("    UST  May-2022 (Terra):    -100% (permanent, never recovered)")
print("    USDT Nov-2022 (FTX):       -2% intraday, recovered same day")
print("    DAI  Mar-2020 (Covid):     -3% intraday, recovered in 1 day")
print()

# For USDC-USDT LP: if USDC depegs to (1-d), LP holds 50% USDC + 50% USDT
# In Uniswap V3 concentrated liquidity, this is more complex, but for full-range
# stable LP the LP value drops roughly proportional to the depeg of ONE side
# (the OTHER side is the reference). Worst case both move opposite: LP effectively
# takes the move. Conservative: LP value drops ~d/2 for a one-sided depeg of size d.
#
# In a leveraged loop: equity E = A - B, A = LP value (drops d*0.5), B = stable debt
# (constant in $ terms). So equity loss = (d/2) * A / E = (d/2) * L. Liquidation when
# LTV > threshold (Aave stable LTV ~ 80%, so liquidation at equity/A < 0.20, i.e. L>5).

def leveraged_depeg_loss(L, depeg_size, liq_ltv=0.80, liq_bonus=0.05):
    """
    Return fractional equity loss for a levered stable LP when one side depegs by
    `depeg_size` (fraction, e.g. 0.13 for 13%).
    Aave-style: liquidation triggers when LTV > liq_ltv. Liquidator takes
    (1 - bonus) of collateral at favourable price => additional penalty.
    """
    # LP value drop: roughly half the depeg (only one side moved; full-range LP)
    lp_drop = 0.5 * depeg_size
    # New leverage after move
    A0 = L  # initial assets per $1 equity, so equity = 1, debt = L-1
    A1 = A0 * (1 - lp_drop)
    E1 = A1 - (L - 1)
    if E1 <= 0:
        return -1.0  # full wipeout
    new_L = A1 / E1
    new_ltv = (L - 1) / A1
    loss = E1 - 1.0
    if new_ltv > liq_ltv:
        # Liquidation: protocol sells collateral at bonus discount -> extra loss
        # Crude: liquidator repays enough to bring LTV back to target; LP keeps
        # residual. The bonus burns ~5% of liquidated collateral.
        # For simplicity: extra liq penalty = bonus * (fraction liquidated)
        frac_liq = (new_ltv - 0.75) / new_ltv  # bring to 75%
        liq_penalty = liq_bonus * frac_liq * A1
        loss -= liq_penalty
        if loss < -1.0:
            loss = -1.0
    return loss

print("  Equity loss under historical depeg events (per $1 equity):")
print(f"  {'Event':>30s}  {'Depeg':>7s}", end="")
for L in [1.0, 2.0, 3.0, 5.0, 8.0]:
    print(f"  L={L:.0f}x", end="")
print()
for name, d in [("USDC SVB Mar-2023", 0.13),
                ("USDT FTX Nov-2022", 0.02),
                ("DAI Covid Mar-2020", 0.03),
                ("UST Terra May-2022 (paired)", 0.50),  # if paired with UST
                ("Severe combined depeg", 0.20)]:
    print(f"  {name:>30s}  {d*100:>5.1f}% ", end="")
    for L in [1.0, 2.0, 3.0, 5.0, 8.0]:
        loss = leveraged_depeg_loss(L, d)
        print(f"  {loss*100:>5.1f}%", end="")
    print()

print("\n  -> At L=5x, a USDC SVB-style depeg (-13%) wipes ~30% of equity.")
print("  -> At L=5x, a UST-style -50% depeg is TOTAL WIPEOUT.")
print("  -> Aave-style liquidation at LTV>80% => max safe L ~ 1/0.8 = 5x theoretical")
print("     but real-world oracles lag and stable LTVs are set 77-80%.")

# -----------------------------------------------------------------------------
# 5. CAPACITY: TVL of USDC-USDT Uniswap V3 ETH = $34.7M
#    The APY comes from swap fees on a fixed volume; adding LP dilutes APY.
#    Realistic capacity for an institutional-size position: ~5% of pool TVL
#    before slippage/IL on entry and APY dilution become material.
# -----------------------------------------------------------------------------
print("\n" + "=" * 72)
print("CAPACITY ANALYSIS")
print(f"  Pool TVL (now): ${tvl[-1]/1e6:.1f}M")
print(f"  Pool TVL (peak): ${np.nanmax(tvl)/1e6:.1f}M")
print(f"  Median TVL: ${np.nanmedian(tvl)/1e6:.1f}M")
print(f"  Realistic position cap (5% of pool, post-dilution): "
      f"~${0.05*tvl[-1]/1e6:.2f}M LP notional")
print(f"  At L=3x with $5M equity -> need ${5*2}M=$10M LP notional")
print(f"    ($10M / ${tvl[-1]/1e6:.1f}M = {10/(tvl[-1]/1e6)*100:.1f}% of pool TVL => "
      "significant APY dilution expected)")
print(f"  At L=5x with $5M equity -> need $20M LP notional")
print(f"    ($20M / ${tvl[-1]/1e6:.1f}M = {20/(tvl[-1]/1e6)*100:.1f}% of pool TVL => "
      "you ARE the pool; APY you earn comes from your own entry slippage)")

# -----------------------------------------------------------------------------
# 6. FINAL HONEST VERDICT
# -----------------------------------------------------------------------------
print("\n" + "=" * 72)
print("HONEST VERDICT")
# Pick the best honest case: borrow=5% (Aave typical), best L
best_L = 1.0
best_apr = -99
for L in [1.0, 1.5, 2.0, 3.0, 5.0]:
    m, _ = results_A[L]
    # Penalize by tail risk: subtract expected annual depeg loss
    # Expected annual: ~1 severe depeg per 3 yrs @ avg 30% loss * probability L>1 affected
    # Conservative annual expected tail loss = (1/3) * depeg_loss(L, 0.13)
    tail_loss = (1/3) * abs(leveraged_depeg_loss(L, 0.13))
    honest_apr = m['apr'] - tail_loss
    if honest_apr > best_apr:
        best_apr = honest_apr
        best_L = L
        best_naive_apr = m['apr']
        best_sharpe = m['sharpe']
print(f"  Best leverage (after tail penalty): L={best_L:.1f}x")
print(f"  Naive APR (no tail): {best_naive_apr*100:.2f}%")
print(f"  Tail-adjusted APR:   {best_apr*100:.2f}%")
print(f"  Sharpe (no tail):    {best_sharpe:.2f}")
print(f"  Tail reserve needed (USDC SVB-style at chosen L): "
      f"{abs(leveraged_depeg_loss(best_L, 0.13))*100:.1f}% of equity")

# Save data for the markdown report
result = {
    "pool": "USDC-USDT Uniswap V3 Ethereum",
    "period": f"{ts[0]} to {ts[-1]}",
    "n_days": len(ts),
    "apy_base_mean_pct": float(np.nanmean(apy_base_pct)),
    "apy_base_median_pct": float(np.nanmedian(apy_base_pct)),
    "apy_base_std_pct": float(np.nanstd(apy_base_pct)),
    "apy_base_p5_pct": float(np.nanpercentile(apy_base_pct, 5)),
    "apy_base_p95_pct": float(np.nanpercentile(apy_base_pct, 95)),
    "tvl_now_musd": float(tvl[-1] / 1e6),
    "tvl_peak_musd": float(np.nanmax(tvl) / 1e6),
    "results_A_const_5pct_borrow": {L: {"apr": m["apr"], "sharpe": m["sharpe"],
                                          "mdd": m["mdd"], "equity_x": float(eq[-1])}
                                     for L, (m, eq) in results_A.items()},
    "results_B_tracked_borrow": {L: {"apr": m["apr"], "sharpe": m["sharpe"],
                                      "mdd": m["mdd"], "equity_x": float(eq[-1])}
                                  for L, (m, eq) in results_B.items()},
    "best_L_after_tail": best_L,
    "naive_apr_pct": best_naive_apr * 100,
    "tail_adj_apr_pct": best_apr * 100,
    "sharpe": best_sharpe,
}
with open(OUT / "_prototypes/leveraged_lp_loop_results.json", "w") as f:
    json.dump(result, f, indent=2)
print(f"\nResults saved -> {OUT}/_prototypes/leveraged_lp_loop_results.json")
