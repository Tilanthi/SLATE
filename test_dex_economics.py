"""Tests for HL economics + bar-level fill model (slate_core.dex.backtester)."""
from slate_core.dex.backtester.economics import (
    HLFeeSchedule, fee_for, min_notional_ok, oracle_ok,
)
from slate_core.dex.backtester.fill_model import bar_fill, bar_fill_l2
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


# ---- slippage (HL-realistic: taker fills walk the book) ----

def test_buy_taker_has_slippage():
    sch = HLFeeSchedule(slippage_bps=2.0)
    o = Order("B", px=0, sz=1, tif="Market")
    _, fpx, maker, _ = bar_fill(o, *_bar(), oracle_px=100, schedule=sch)
    assert not maker and abs(fpx - 100.02) < 1e-6      # 2bps worse on buy


def test_sell_taker_has_negative_slippage():
    sch = HLFeeSchedule(slippage_bps=2.0)
    o = Order("A", px=0, sz=1, tif="Market")
    _, fpx, maker, _ = bar_fill(o, *_bar(), oracle_px=100, schedule=sch)
    assert not maker and abs(fpx - 99.98) < 1e-6       # 2bps worse on sell


def test_maker_fill_no_slippage():
    sch = HLFeeSchedule(slippage_bps=2.0)
    o = Order("B", px=99.5, sz=1, tif="Limit")
    _, fpx, maker, _ = bar_fill(o, *_bar(), oracle_px=100, schedule=sch)
    assert maker and abs(fpx - 99.5) < 1e-6            # exact limit, no slip


# ---- fill model ----

def test_buy_resting_touched_fills_maker():
    o = Order("B", px=99.5, sz=1, tif="Limit")
    filled, fpx, maker, rej = bar_fill(o, *_bar(), oracle_px=100, schedule=SCH)
    assert filled and maker and abs(fpx - 99.5) < 1e-9 and rej is None


def test_buy_crossing_open_fills_taker():
    o = Order("B", px=100.5, sz=1)                     # >= open -> crosses
    filled, fpx, maker, rej = bar_fill(o, *_bar(), oracle_px=100, schedule=SCH)
    assert filled and not maker and abs(fpx - 100 * (1 + SCH.slippage_bps / 10000.0)) < 1e-9


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
    assert filled and not maker and abs(fpx - 100 * (1 + SCH.slippage_bps / 10000.0)) < 1e-9


def test_min_notional_rejected():
    o = Order("B", px=100, sz=0.05, tif="Market")      # notional 5 < 10
    filled, fpx, maker, rej = bar_fill(o, *_bar(), oracle_px=100, schedule=SCH)
    assert not filled and rej == "min_notional_rejected"


def test_oracle_rejected_when_price_far():
    o = Order("B", px=200, sz=1)                       # 100% from oracle
    filled, fpx, maker, rej = bar_fill(o, *_bar(), oracle_px=100, schedule=SCH)
    assert not filled and rej == "oracle_rejected"


# ---- queue-aware maker fill (L2) ----

def test_bar_fill_l2_blocks_maker_when_queue_exceeds_volume():
    o = Order("B", px=99.5, sz=1, tif="Limit")         # touched (low 99 <= 99.5)
    blocked = bar_fill_l2(o, *_bar(), oracle_px=100, schedule=SCH,
                          queue_ahead=500, bar_volume=10)
    assert not blocked[0] and blocked[3] is None        # queued behind, no reject
    fills = bar_fill_l2(o, *_bar(), oracle_px=100, schedule=SCH,
                        queue_ahead=1, bar_volume=10)
    assert fills[0] and fills[2]                        # small queue -> maker fill


def test_bar_fill_l2_taker_unaffected_by_queue():
    o = Order("B", px=100.5, sz=1)                     # crosses open -> taker
    r = bar_fill_l2(o, *_bar(), oracle_px=100, schedule=SCH,
                    queue_ahead=999, bar_volume=1)
    assert r[0] and not r[2]                            # taker fills regardless of queue


def test_bar_fill_l2_none_queue_falls_back_to_proxy():
    o = Order("B", px=99.5, sz=1)
    r = bar_fill_l2(o, *_bar(), oracle_px=100, schedule=SCH,
                    queue_ahead=None, bar_volume=None)
    assert r[0] and r[2]                                # proxy: touched = filled
