"""Market-maker archetype: continuously quote a bid + ask around mid, earn the
spread + maker rebate, and skew quotes against inventory (long inventory ->
shift both quotes down to encourage selling). This is the DEX flagship enabled
by zero-gas + maker rebates. Bar-level v1: quotes rest for one bar and fill only
if the bar's range touches them (a fill-probability proxy for queue/adverse
selection — honest verdicts need the deferred L2 phase)."""
from __future__ import annotations

from typing import List

from slate_core.dex.strategies.action import BarState, DexStrategy, Order


class MarketMakerStrategy(DexStrategy):
    name = "market_maker"

    def __init__(self, half_spread_bps: float = 10.0, size: float = 0.5,
                 inv_skew_bps: float = 2.0, max_size: float = 2.0):
        self.half = half_spread_bps / 10000.0
        self.size = size
        self.skew = inv_skew_bps / 10000.0
        self.max_size = max_size

    def act(self, state: BarState) -> List[Order]:
        mid = state.close
        inv_frac = (state.position / self.max_size) if self.max_size > 0 else 0.0
        adj = -self.skew * inv_frac                       # long inventory -> quotes down
        bid_px = mid * (1 - self.half + adj)
        ask_px = mid * (1 + self.half + adj)
        orders: List[Order] = []
        if state.position < self.max_size:                # room to buy
            orders.append(Order("B", px=bid_px, sz=self.size, tif="Alo"))
        if state.position > -self.max_size:               # room to sell
            orders.append(Order("A", px=ask_px, sz=self.size, tif="Alo"))
        return orders
