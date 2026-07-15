"""Tests for HL economics + bar-level fill model (slate_core.dex.backtester)."""
from slate_core.dex.backtester.economics import (
    HLFeeSchedule, fee_for, min_notional_ok, oracle_ok,
)
from slate_core.dex.backtester.fill_model import bar_fill
from slate_core.dex.strategies.action import Order

SCH = HLFeeSchedule()


def _bar(o=100.0, h=101.0, l=99.0, c=100.0):
    return o, h, l, c


# ---- economics ----

def test_fee_taker_maker_and_rebate():
    assert abs(fee_for(10000, False, SCH) - 10000 * 0.00045) < 1e-9
    assert abs(fee_for(10000, True, SCH) - 10000 * 0.00015) < 1e-9
    reb = HLFeeSchedule(maker=-0.0001)                 # a rebate tier
    assert fee_for(10000, True, reb) < 0               # negative = cash in


def test_min_notional():
    assert min_notional_ok(0.1, 50, SCH) is False      # 5 < 10
    assert min_notional_ok(0.5, 50, SCH) is True       # 25 >= 10


def test_oracle_ok_tolerance():
    assert oracle_ok(100, 100, SCH) is True
    assert oracle_ok(115, 100, SCH) is True            # 15% == tol
    assert oracle_ok(120, 100, SCH) is False           # 20% > tol


# ---- fill model ----

def test_buy_resting_touched_fills_maker():
    o = Order("B", px=99.5, sz=1, tif="Limit")
    filled, fpx, maker, rej = bar_fill(o, *_bar(), oracle_px=100, schedule=SCH)
    assert filled and maker and abs(fpx - 99.5) < 1e-9 and rej is None


def test_buy_crossing_open_fills_taker():
    o = Order("B", px=100.5, sz=1)                     # >= open -> crosses
    filled, fpx, maker, rej = bar_fill(o, *_bar(), oracle_px=100, schedule=SCH)
    assert filled and not maker and abs(fpx - 100) < 1e-9


def test_alo_crossing_is_rejected():
    o = Order("B", px=100.5, sz=1, tif="Alo")
    filled, fpx, maker, rej = bar_fill(o, *_bar(), oracle_px=100, schedule=SCH)
    assert not filled and rej == "badAloPxRejected"


def test_sell_resting_touched_fills_maker():
    o = Order("A", px=100.5, sz=1)
    filled, fpx, maker, rej = bar_fill(o, 100, 101, 99, 100, oracle_px=100, schedule=SCH)
    assert filled and maker and abs(fpx - 100.5) < 1e-9


def test_not_touched_not_filled_no_reject():
    o = Order("B", px=98.0, sz=1)                      # below low 99
    filled, fpx, maker, rej = bar_fill(o, *_bar(), oracle_px=100, schedule=SCH)
    assert not filled and rej is None


def test_market_order_fills_taker_at_open():
    o = Order("B", px=0.0, sz=1, tif="Market")
    filled, fpx, maker, rej = bar_fill(o, *_bar(), oracle_px=100, schedule=SCH)
    assert filled and not maker and abs(fpx - 100) < 1e-9


def test_min_notional_rejected():
    o = Order("B", px=100, sz=0.05, tif="Market")      # notional 5 < 10
    filled, fpx, maker, rej = bar_fill(o, *_bar(), oracle_px=100, schedule=SCH)
    assert not filled and rej == "min_notional_rejected"


def test_oracle_rejected_when_price_far():
    o = Order("B", px=200, sz=1)                       # 100% from oracle
    filled, fpx, maker, rej = bar_fill(o, *_bar(), oracle_px=100, schedule=SCH)
    assert not filled and rej == "oracle_rejected"
