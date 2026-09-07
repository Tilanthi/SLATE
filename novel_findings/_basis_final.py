"""Final variants:
1) Higher z_entry (only true extremes), with holding period
2) Soft tanh sizing
3) Confirm capacity (the edge per dollar is tiny; how much AUM can it absorb?)
4) Per-trade economics: gross per trade vs cost per trade
"""
import sys
sys.path.insert(0, "novel_findings")
from _basis_backtest import (load_basis, basis_backtest, signal_zfade, signal_zfade_tanh,
                              PERP_ONE_WAY, SPOT_ONE_WAY)
import numpy as np, pandas as pd

df = load_basis("SOL")
print(f"SOL: {len(df)} bars  basis mean={df['basis'].mean()*1e4:.1f}bps std={df['basis'].std()*1e4:.1f}bps")

# (1) Per-trade economics at the BEST in-sample config (w=120, z=3)
print("\n=== Per-trade economics (w=120 z=3, taker costs) ===")
t = signal_zfade(df, window=120, z_entry=3.0)
r = basis_backtest(t, df, perp_one_way=PERP_ONE_WAY, spot_one_way=SPOT_ONE_WAY)
m = r["metrics"]
n_trades = m.n_trades
print(f"Trades: {n_trades:.0f}, round-trip cost: {(PERP_ONE_WAY+SPOT_ONE_WAY)*200:.0f}bps")
print(f"Total gross: {m.total_gross*100:.2f}%   avg gross/trade: {m.total_gross/max(n_trades,1)*1e4:.0f}bps")
print(f"Total funding: {m.total_funding*100:.2f}%  avg funding/trade: {m.total_funding/max(n_trades,1)*1e4:.0f}bps")
print(f"Total cost: {m.total_cost*100:.2f}%   avg cost/trade: {m.total_cost/max(n_trades,1)*1e4:.0f}bps")
print(f"Net: APR={m.apr*100:.2f}%  Sharpe={m.sharpe:.2f}")

# (2) Soft sizing (tanh)
print("\n=== Soft (tanh) sizing — full sample, taker ===")
for w in [60, 90, 120]:
    for z in [1.5, 2.0]:
        for zsat in [2.0, 3.0]:
            t = signal_zfade_tanh(df, window=w, z_entry=z, z_sat=zsat)
            r = basis_backtest(t, df, perp_one_way=PERP_ONE_WAY, spot_one_way=SPOT_ONE_WAY)
            m = r["metrics"]
            print(f"  w={w} z={z} zsat={zsat}: trades={m.n_trades:.0f} sharpe={m.sharpe:.2f} APR={m.apr*100:.2f}% cost={m.total_cost*100:.1f}%")

# (3) Robustness: how many of the 18 winning trades came from FTX window (2022-11)?
print("\n=== Are the winners FTX-only? ===")
df_ftx = df.copy()
df_ftx["year"] = df_ftx.index.year
df_ftx["month"] = df_ftx.index.month
df_ftx["ftx_window"] = ((df_ftx.index >= "2022-11-01") & (df_ftx.index <= "2023-03-01"))
t = signal_zfade(df, window=120, z_entry=3.0)
# decompose per-bar PnL by period
held = np.zeros(len(df)); held[1:] = t[:-1]
perp_ret = df["perp"].pct_change().fillna(0).values
spot_ret = df["spot"].pct_change().fillna(0).values
basis_ret = perp_ret - spot_ret
gross = held * basis_ret
fund = -df["fund_rate"].values * 3 * held
dhold = np.abs(np.diff(held, prepend=0))
cost = dhold * (PERP_ONE_WAY + SPOT_ONE_WAY)
net = gross + fund - cost
ftx_mask = df_ftx["ftx_window"].values
print(f"FTX window bars: {ftx_mask.sum()}  ({ftx_mask.sum()/len(df)*100:.1f}% of total)")
print(f"Gross PnL FTX window: {gross[ftx_mask].sum()*100:+.2f}%")
print(f"Gross PnL outside FTX: {gross[~ftx_mask].sum()*100:+.2f}%")
print(f"Net PnL FTX window:  {net[ftx_mask].sum()*100:+.2f}%")
print(f"Net PnL outside FTX: {net[~ftx_mask].sum()*100:+.2f}%")

# (4) Capacity: the SOL spot + perp mkt is deep, but basis volume is small.
# At $5M AUM, 18 trades x ~$5M notional per leg, with each side 0.32% one-way cost incl 15bps slip.
# Square-root impact is tiny vs the 15bps fixed slip already in cost. So capacity >> $50M for the rare entries.
# BUT the edge itself is < 1%/yr — so even at infinite capacity, the strategy is irrelevant.
print("\n=== Capacity ===")
print("Capacity is a non-issue: 18 trades/4yr = ~5/yr. SOL daily spot+perp volume > $1B.")
print("At $5M AUM, each entry is <0.5% of daily volume — negligible impact.")
print("The constraint is NOT capacity; it's that net APR is ~0 even at zero impact.")

# (5) The single most-likely-to-work variant: enter only when funding ALSO supports the trade
# (basis extreme AND funding paying the right way). This filters out momentum-driven basis.
print("\n=== Conditional entry: basis extreme AND funding aligned ===")
print("(Long basis when basis<-z AND funding<-0.03%/8h [shorts paying, long basis carry+];)")
print("(Short basis when basis>+z AND funding>+0.03%/8h)")
for w in [60, 120]:
    for z in [2.0, 2.5]:
        b = df["basis"].values
        s = pd.Series(b)
        mean = s.rolling(w, min_periods=w//2).mean().values
        std = s.rolling(w, min_periods=w//2).std().values
        zsc = np.where(std>0, (b-mean)/std, 0)
        fr = df["fund_rate"].values
        t = np.zeros(len(df))
        # long basis: basis discount + funding paying longs (negative funding = longs receive)
        t[(zsc < -z) & (fr < -3e-4)] = +1.0
        # short basis: basis premium + funding paying shorts (positive funding = shorts receive)
        t[(zsc > +z) & (fr > +3e-4)] = -1.0
        r = basis_backtest(t, df, perp_one_way=PERP_ONE_WAY, spot_one_way=SPOT_ONE_WAY)
        m = r["metrics"]
        nentries = ((t!=0)).sum()
        print(f"  w={w} z={z} fund-aligned: entries={nentries}({m.n_trades:.0f} trades) sharpe={m.sharpe:.2f} APR={m.apr*100:.2f}% gross={m.total_gross*100:.1f}% cost={m.total_cost*100:.1f}%")

# (6) Honest IS/OOS half-and-half on the most-likely variant
print("\n=== Honest IS/OOS half split on fund-aligned variant (w=60 z=2.0) ===")
b = df["basis"].values
s = pd.Series(b)
w = 60; z = 2.0
mean = s.rolling(w, min_periods=w//2).mean().values
std = s.rolling(w, min_periods=w//2).std().values
zsc = np.where(std>0, (b-mean)/std, 0)
fr = df["fund_rate"].values
t = np.zeros(len(df))
t[(zsc < -z) & (fr < -3e-4)] = +1.0
t[(zsc > +z) & (fr > +3e-4)] = -1.0
isfrac = 0.6
k = int(len(df)*isfrac)
df_is, df_oos = df.iloc[:k], df.iloc[k:]
t_is, t_oos = t[:k], t[k:]
r_is = basis_backtest(t_is, df_is, perp_one_way=PERP_ONE_WAY, spot_one_way=SPOT_ONE_WAY)
r_oos = basis_backtest(t_oos, df_oos, perp_one_way=PERP_ONE_WAY, spot_one_way=SPOT_ONE_WAY)
print(f"  IS ({len(df_is)}b):  sharpe={r_is['metrics'].sharpe:.2f} APR={r_is['metrics'].apr*100:.2f}% trades={r_is['metrics'].n_trades:.0f}")
print(f"  OOS ({len(df_oos)}b): sharpe={r_oos['metrics'].sharpe:.2f} APR={r_oos['metrics'].apr*100:.2f}% trades={r_oos['metrics'].n_trades:.0f}")
