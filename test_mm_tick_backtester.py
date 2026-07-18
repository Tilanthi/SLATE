"""Tests for the tick/L2 market-maker backtester (mm_tick_backtester.py).

Verify the HONEST fill model: a resting maker order fills only after traded
volume (book-depth delta) consumes the size resting at better prices (price-time
priority), not merely because its price was touched. Scenarios use a STABLE
constant-depth tail so only the intended side's depth delta produces fills.
"""
from slate_core.dex.backtester.mm_tick_backtester import MMPolicy, backtest_mm
from slate_core.dex.backtester.economics import HLFeeSchedule


def _snap(t, mid, bids, asks):
    return {"t": t, "coin": "SOL", "mid": mid, "spread_bps": 1.0, "imbalance": 0.0,
            "bids": [[px, sz] for px, sz in bids],
            "asks": [[px, sz] for px, sz in asks]}


def _stable(t, mid, depth=5.0):
    # Constant-depth book on both sides -> zero depth delta -> no fills.
    return _snap(t, mid, [(mid * 0.999, depth)], [(mid * 1.001, depth)])


def test_no_fill_without_traded_volume():
    snaps = [_stable(i, 100.0) for i in range(6)]
    res = backtest_mm(snaps, MMPolicy(half_spread_bps=10.0, size=0.5))
    assert res.maker_fills == 0
    assert abs(res.total_pnl) < 1e-9
    assert res.adverse_selection_cost == 0.0


def test_fill_when_sell_consumes_through_to_our_bid():
    # Only BID depth drops (sellers). Our resting bid at the best level
    # (size_ahead = 0) fills at our maker price; mid then falls -> adverse.
    s0 = _snap(0, 100.0, [(99.9, 5.0), (99.85, 3.0)], [(100.1, 5.0)])
    s1 = _snap(1, 100.0, [(99.9, 5.0), (99.85, 3.0)], [(100.1, 5.0)])
    s2 = _snap(2, 99.5, [(99.6, 1.0)], [(100.1, 5.0)])   # bid depth 8 -> 1 (selling)
    tail = [_stable(i, 99.0) for i in range(3, 8)]       # stable, mid low -> adverse
    snaps = [s0, s1, s2] + tail
    res = backtest_mm(snaps, MMPolicy(half_spread_bps=10.0, inv_skew_bps=0.0, size=0.5),
                      adv_lookback=2)
    assert res.maker_fills == 1               # bought at our 99.9 bid only
    assert res.taker_fills == 1               # residual force-closed at last mid
    assert res.total_pnl < 0.0                # bought 99.9, ended ~99 -> loss
    assert res.adverse_selection_cost > 0.0   # mid fell after the fill


def test_no_fill_when_buried_behind_deep_book():
    # Our bid sits BELOW the top of book; modest selling never consumes the
    # size ahead of us, so we never fill.
    s0 = _snap(0, 100.0, [(99.9, 50.0), (99.8, 50.0)], [(100.1, 50.0)])
    s1 = _snap(1, 100.0, [(99.9, 50.0), (99.8, 50.0)], [(100.1, 50.0)])
    s2 = _snap(2, 99.9, [(99.9, 45.0), (99.8, 50.0)], [(100.0, 50.0)])  # only 5 consumed
    tail = [_stable(i, 99.9, depth=50.0) for i in range(3, 8)]
    snaps = [s0, s1, s2] + tail
    res = backtest_mm(snaps, MMPolicy(half_spread_bps=30.0, size=0.5), adv_lookback=2)
    assert res.maker_fills == 0               # buried: selling never reached 99.7


def test_maker_rebate_with_negative_maker_fee():
    # Rebate-tier schedule (maker < 0): a maker fill returns cash. Only bid depth
    # drops (sellers) but mid stays ~stable -> negligible adverse selection.
    s0 = _snap(0, 100.0, [(99.9, 5.0)], [(100.1, 5.0)])
    s1 = _snap(1, 100.0, [(99.9, 5.0)], [(100.1, 5.0)])
    s2 = _snap(2, 100.0, [(99.9, 2.0)], [(100.1, 5.0)])  # bid depth 5 -> 2
    tail = [_stable(i, 100.0) for i in range(3, 8)]      # mid stable
    snaps = [s0, s1, s2] + tail
    sched = HLFeeSchedule(taker=0.00045, maker=-0.0001)  # negative maker = rebate
    res = backtest_mm(snaps, MMPolicy(half_spread_bps=10.0, size=0.5), schedule=sched,
                      adv_lookback=2)
    assert res.maker_fills == 1
    assert res.total_rebates > 0.0            # rebate accrued
    assert res.total_fees >= 0.0


def test_size_clamped_to_order_size():
    # Massive selling consumes the whole bid book, but we fill only `size` per interval.
    s0 = _snap(0, 100.0, [(99.9, 5.0)], [(100.1, 5.0)])
    s1 = _snap(1, 100.0, [(99.9, 5.0)], [(100.1, 5.0)])
    s2 = _snap(2, 99.0, [(98.9, 0.1)], [(100.1, 5.0)])   # bid depth 5 -> 0.1 (huge sell)
    tail = [_stable(i, 99.0) for i in range(3, 8)]
    snaps = [s0, s1, s2] + tail
    res = backtest_mm(snaps, MMPolicy(half_spread_bps=10.0, size=0.3), adv_lookback=2)
    assert res.maker_fills == 1
    assert abs(res.inventory_turnover - 0.3) < 1e-9      # capped at order size


def test_two_sided_round_trip_when_both_sides_trade():
    # When sellers hit our bid THEN buyers hit our ask, we complete a round trip
    # and capture the spread. Sanity check that two-sided operation works.
    s0 = _snap(0, 100.0, [(99.9, 5.0)], [(100.1, 5.0)])
    s1 = _snap(1, 100.0, [(99.9, 5.0)], [(100.1, 5.0)])
    s2 = _snap(2, 100.0, [(99.9, 1.0)], [(100.1, 5.0)])  # sellers (bid consumed)
    s3 = _snap(3, 100.0, [(99.9, 5.0)], [(100.1, 1.0)])  # buyers (ask consumed)
    tail = [_stable(i, 100.0) for i in range(4, 9)]
    snaps = [s0, s1, s2, s3] + tail
    res = backtest_mm(snaps, MMPolicy(half_spread_bps=10.0, size=0.5), adv_lookback=2)
    assert res.maker_fills >= 2              # a buy and a sell
    assert res.total_pnl > 0.0               # bought 99.9, sold 100.1 -> spread captured
