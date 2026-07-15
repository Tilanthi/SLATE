"""Bar-level maker/taker fill model for the DEX backtester.

A resting (maker) limit fills only if the bar's range touches its price; an
order that would cross at the open fills immediately as taker at the open. Alo
(post-only) orders that would cross are rejected. Market orders fill as taker at
the open. Honors oracle rejection + min-notional (economics).
"""
from __future__ import annotations

from typing import Optional, Tuple

from slate_core.dex.backtester.economics import (
    HLFeeSchedule, min_notional_ok, oracle_ok,
)
from slate_core.dex.strategies.action import Order
from typing import Optional


def bar_fill(order: Order, o: float, h: float, l: float, c: float,
             oracle_px: float, schedule: HLFeeSchedule
             ) -> Tuple[bool, float, bool, Optional[str]]:
    """Resolve an order against one bar.

    Returns (filled, fill_px, is_maker, reject_reason).
      filled=False + reject_reason set => rejected (not placed).
      filled=False + reject_reason None => not touched this bar (still usable).
    """
    px, sz, side, tif = order.px, order.sz, order.side, order.tif

    # min-notional uses the fill reference price: open for Market, limit px otherwise.
    ref_px = o if tif == "Market" else px
    if not min_notional_ok(sz, ref_px, schedule):
        return False, 0.0, False, "min_notional_rejected"
    if tif != "Market" and not oracle_ok(px, oracle_px, schedule):
        return False, 0.0, False, "oracle_rejected"

    # Slippage: taker fills walk the book (HL CLOB, price-time priority).
    # Maker (resting) fills get their exact limit price. 1bps is realistic for
    # deep HL books (SOL perp: $100K+ within 10bps of mid).
    slip = schedule.slippage_bps / 10000.0

    if tif == "Market":
        return True, o * (1 + slip if side == "B" else 1 - slip), False, None

    if side == "B":
        if px >= o:                            # would cross at the open
            if tif == "Alo":
                return False, 0.0, False, "badAloPxRejected"
            return True, o * (1 + slip), False, None  # taker at open + slippage
        if l <= px:                            # resting bid touched
            return True, px, True, None        # maker fill at the bid (no slip)
        return False, 0.0, False, None
    else:                                      # sell
        if px <= o:                            # would cross at the open
            if tif == "Alo":
                return False, 0.0, False, "badAloPxRejected"
            return True, o * (1 - slip), False, None  # taker at open + slippage
        if h >= px:                            # resting ask touched
            return True, px, True, None        # maker fill at the ask (no slip)
        return False, 0.0, False, None


def bar_fill_l2(order: Order, o: float, h: float, l: float, c: float,
                oracle_px: float, schedule: HLFeeSchedule,
                queue_ahead: Optional[float], bar_volume: Optional[float],
                fill_share: float = 0.5
                ) -> Tuple[bool, float, bool, Optional[str]]:
    """Queue-aware maker fill — graduates market-making from INDICATIVE (touched =
    filled) to DEFINITIVE: a resting maker fills only if the bar's traded volume at
    the level consumes the queue resting ahead of it. Taker fills and rejections are
    unchanged. queue_ahead/bar_volume None => falls back to the bar proxy.

    Without per-level historical trade data we approximate traded-at-level as
    bar_volume * fill_share; a real L2/trade feed (third-party, or accumulated
    l2_book snapshots) supplies exact values via the same call signature.
    """
    filled, fpx, maker, rej = bar_fill(order, o, h, l, c, oracle_px, schedule)
    if rej or not filled:
        return filled, fpx, maker, rej
    if maker and queue_ahead is not None and bar_volume is not None:
        if queue_ahead > bar_volume * fill_share:
            return False, 0.0, False, None     # queued behind; not filled this bar
    return filled, fpx, maker, rej
