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

    if tif == "Market":
        return True, o, False, None           # taker at open

    if side == "B":
        if px >= o:                            # would cross at the open
            if tif == "Alo":
                return False, 0.0, False, "badAloPxRejected"
            return True, o, False, None        # immediate taker at open
        if l <= px:                            # resting bid touched
            return True, px, True, None        # maker fill at the bid
        return False, 0.0, False, None
    else:                                      # sell
        if px <= o:                            # would cross at the open
            if tif == "Alo":
                return False, 0.0, False, "badAloPxRejected"
            return True, o, False, None        # immediate taker at open
        if h >= px:                            # resting ask touched
            return True, px, True, None        # maker fill at the ask
        return False, 0.0, False, None
