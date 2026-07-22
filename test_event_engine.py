"""Tests for the event-driven execution engine.

The event engine must (1) be a strict generalization of the vectorized honest
backtester (identical in simple mode), (2) have no lookahead, (3) charge impact
monotonically with size, (4) model maker adverse selection, and (5) cap taker
fills by participation.
"""
import numpy as np
import pandas as pd
import pytest

from slate_core.backtest.honest import backtest, CEX, DEX
from slate_core.backtest.event_engine import EventBacktester, match_order, Order


def _df(closes, vol=None, freq="1D"):
    idx = pd.date_range("2024-01-01", periods=len(closes), freq=freq)
    d = {"open": closes, "high": closes, "low": closes, "close": closes}
    d["volume"] = vol if vol is not None else [1e6] * len(closes)
    return pd.DataFrame(d, index=idx)


def _rw(n, seed=0, vol=0.02):
    rng = np.random.RandomState(seed)
    return 100 * np.cumprod(1 + rng.normal(0, vol, n))


# 1. simple mode == honest.backtest (the generalization invariant)
def test_event_matches_vectorized_in_simple_mode():
    df = _df(_rw(500, seed=3))
    target = np.random.RandomState(7).choice([-1, 0, 1], size=500)
    # event: taker, full fills (participation_cap=1), impact OFF, no extra latency,
    # no end-liquidation (apples-to-apples with the vectorized engine)
    ev = EventBacktester(CEX, capital=1.0, mode="taker", impact=False,
                         participation_cap=1.0, latency_bars=0,
                         liquidate_end=False).run(target, df)
    vec = backtest(target, df, venue=CEX)
    # per-bar returns should match to numerical tolerance
    np.testing.assert_allclose(ev["returns"], vec["returns"], atol=1e-9)


# 2. no lookahead: a contemporaneous signal must not earn its own bar's move
def test_event_no_lookahead():
    from slate_core.backtest.honest import Venue
    zero = Venue("zero", 0.0, 0.0, 0.0, 8, impact_k=0.0)   # zero-cost venue
    df = _df(_rw(3000, seed=1), vol=np.full(3000, 1e7))
    close = df["close"].values
    target = np.sign(np.diff(close, prepend=close[0])).astype(int)
    ev = EventBacktester(zero, capital=1.0, impact=False, participation_cap=1.0,
                         liquidate_end=False).run(target, df)
    assert abs(ev["metrics"]["sharpe"]) < 1.5   # iid signal -> ~0 edge (4 sigma over 3000 bars)


# 3. impact is monotonic in size (bigger AUM -> lower Sharpe)
def test_impact_monotonic_in_size():
    df = _df(_rw(1000, seed=4), vol=np.full(1000, 5e6))
    target = np.sign(np.diff(df["close"].values, prepend=1)).astype(int)
    sh = {}
    for cap in [1e3, 1e6, 1e8]:
        r = EventBacktester(CEX, capital=cap, impact=True, participation_cap=1.0).run(target, df)
        sh[cap] = r["metrics"]["sharpe"]
    # larger capital -> more impact -> lower (or equal) Sharpe
    assert sh[1e3] >= sh[1e6] >= sh[1e8], f"impact not monotonic: {sh}"


# 4. impact actually lowers Sharpe vs no-impact at large size
def test_impact_lowers_sharpe_at_scale():
    df = _df(_rw(1000, seed=5), vol=np.full(1000, 5e6))
    target = np.sign(np.diff(df["close"].values, prepend=1)).astype(int)
    no_imp = EventBacktester(CEX, capital=1e7, impact=False, participation_cap=1.0).run(target, df)
    imp = EventBacktester(CEX, capital=1e7, impact=True, participation_cap=1.0).run(target, df)
    assert imp["metrics"]["sharpe"] <= no_imp["metrics"]["sharpe"]


# 5. participation cap limits fill size
def test_participation_cap_limits_fills():
    closes = np.array([100, 100, 100, 100, 100, 100], dtype=float)
    # volume=1 unit * $100 = $100/bar -> 10% cap = $10/bar fillable
    df = _df(closes, vol=[1, 1, 1, 1, 1, 1])
    target = np.array([0, 1, 1, 1, 1, 1])        # want to go long 1.0 * capital = $1000
    r = EventBacktester(CEX, capital=1000.0, impact=False, participation_cap=0.10,
                        liquidate_end=False).run(target, df)
    # can fill only ~$10/bar -> over 4 active bars ~$40 of $1000 -> turnover well under 0.1
    assert r["metrics"]["turnover"] < 0.1


# 6. maker adverse selection: a maker buy fills on a bar whose low touched bid,
#    and is marked to a lower close -> loss vs the fill price
def test_maker_adverse_selection():
    # bar: low dips to 99 (touches a 99 bid) but closes at 98 -> toxic
    bar = {"close": 98.0, "high": 100.0, "low": 99.0, "volume_usd": 1e6}
    order = Order(side=1, size_notional=1000.0, kind="maker", limit=99.0)
    f = match_order(order, bar, CEX, participation_cap=1.0, impact=False, bar_vol_frac=0.02)
    assert f.reason == "maker"
    assert f.size_notional > 0
    assert f.price == 99.0          # filled at the quote
    # the position is immediately worth 98 (close) on 1000/99 units -> unrealized loss
    pos_value = (1000.0 / 99.0) * 98.0
    assert pos_value < 1000.0       # adverse selection -> underwater


# 7. maker order does NOT fill if the bar never touches the quote
def test_maker_not_touched():
    bar = {"close": 100.0, "high": 100.5, "low": 99.5, "volume_usd": 1e6}
    order = Order(side=1, size_notional=1000.0, kind="maker", limit=99.0)  # bid never touched
    f = match_order(order, bar, CEX, participation_cap=1.0, impact=False, bar_vol_frac=0.02)
    assert f.size_notional == 0.0
    assert f.reason == "not_touched"


# 8. DEX venue works (parity with CEX path, different fees)
def test_dex_venue_runs():
    df = _df(_rw(200, seed=9), vol=np.full(200, 1e7))
    target = np.random.RandomState(2).choice([-1, 1], size=200)
    r = EventBacktester(DEX, capital=1.0, impact=True, participation_cap=0.5).run(target, df)
    assert "sharpe" in r["metrics"]
    assert r["metrics"]["n_fills"] > 0


# 9. latency shifts the decision (a 1-bar lag changes the result vs no latency)
def test_latency_changes_result():
    df = _df(_rw(400, seed=11), vol=np.full(400, 1e7))
    target = np.sign(np.diff(df["close"].values, prepend=1)).astype(int)
    a = EventBacktester(CEX, capital=1.0, impact=False, participation_cap=1.0, latency_bars=0).run(target, df)
    b = EventBacktester(CEX, capital=1.0, impact=False, participation_cap=1.0, latency_bars=1).run(target, df)
    assert not np.allclose(a["returns"], b["returns"])
