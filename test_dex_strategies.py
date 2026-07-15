"""Tests for the DEX strategy archetypes (slate_core.dex.strategies)."""
import pandas as pd

from slate_core.dex.backtester.dex_backtester import DexBacktester, DexBacktestConfig
from slate_core.dex.strategies.action import BarState
from slate_core.dex.strategies.directional import DirectionalStrategy
from slate_core.dex.strategies.market_maker import MarketMakerStrategy


def _state(close=100.0, position=0.0):
    return BarState(i=0, open=100, high=101, low=99, close=close, position=position,
                    entry_px=0.0, equity=10000.0)


# ---- directional ----

def test_directional_buys_on_long_signal_with_maker_edge():
    s = DirectionalStrategy(lambda st: 1, size=2.0, tif="Alo", edge_bps=10)
    orders = s.act(_state(close=100.0))
    assert len(orders) == 1
    assert orders[0].side == "B" and orders[0].tif == "Alo"
    assert abs(orders[0].sz - 2.0) < 1e-9
    assert orders[0].px < 100.0          # resting below mid


def test_directional_sells_on_short_signal():
    s = DirectionalStrategy(lambda st: -1, size=2.0)
    orders = s.act(_state(close=100.0))
    assert len(orders) == 1 and orders[0].side == "A" and orders[0].px > 100.0


def test_directional_flat_when_at_target():
    s = DirectionalStrategy(lambda st: 1, size=2.0)
    assert s.act(_state(close=100.0, position=2.0)) == []


def test_directional_momentum_makes_money_on_uptrend():
    # clear uptrend; momentum signal goes long and rides it (Limit so it fills)
    rows = [(100 + k, 100 + k, 99 + k, 100 + k) for k in range(30)]
    df = pd.DataFrame(rows, columns=["open", "high", "low", "close"],
                      index=pd.date_range("2026-01-01", periods=30, freq="1h"))
    mom = lambda st: 1 if len(st.history) > 1 and st.close > st.history["close"].iloc[-2] else 0
    s = DirectionalStrategy(mom, size=1.0, tif="Market")
    r = DexBacktester(DexBacktestConfig(warmup=2, funding_interval_bars=0)).backtest(s, df)
    assert r.total_pnl > 0 and r.total_trades > 0


# ---- market maker ----

def test_mm_quotes_both_sides_around_mid():
    s = MarketMakerStrategy(half_spread_bps=10, size=0.5)
    orders = s.act(_state(close=100.0))
    assert len(orders) == 2
    buy = [o for o in orders if o.side == "B"][0]
    sell = [o for o in orders if o.side == "A"][0]
    assert buy.px < 100.0 < sell.px
    assert buy.tif == "Alo" and sell.tif == "Alo"


def test_mm_skews_down_and_stops_bidding_at_max_long():
    s = MarketMakerStrategy(half_spread_bps=10, inv_skew_bps=20, max_size=2.0)
    flat = s.act(_state(close=100.0, position=0.0))
    long_max = s.act(_state(close=100.0, position=2.0))
    assert all(o.side == "A" for o in long_max)          # no buy at max long
    flat_ask = [o for o in flat if o.side == "A"][0].px
    long_ask = [o for o in long_max if o.side == "A"][0].px
    assert long_ask < flat_ask                            # skewed down to encourage selling
