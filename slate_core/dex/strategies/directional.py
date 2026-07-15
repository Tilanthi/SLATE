"""Directional archetype: long/short/flat via a {-1,0,1} signal, routed through
maker orders (configurable tif) so entries/exits can harvest rebates. This is the
CEX-style directional signal PLUS maker execution — the DEX-distinct upgrade and
the v1 archetype that is fully honest at bar level."""
from __future__ import annotations

from typing import Callable, List

from slate_core.dex.strategies.action import BarState, DexStrategy, Order

SignalFn = Callable[[BarState], int]


class DirectionalStrategy(DexStrategy):
    name = "directional"

    def __init__(self, signal_fn: SignalFn, size: float = 1.0,
                 tif: str = "Alo", edge_bps: float = 5.0):
        self.signal_fn = signal_fn
        self.size = size
        self.tif = tif                    # default Alo = pure maker (rebate or no fill)
        self.edge = edge_bps / 10000.0    # how far inside the mid to rest the order

    def act(self, state: BarState) -> List[Order]:
        sig = self.signal_fn(state)
        if sig not in (-1, 0, 1):
            sig = 0
        target = sig * self.size
        delta = target - state.position
        if abs(delta) < 1e-9:
            return []
        if delta > 0:                      # need to buy
            px = state.close * (1 - self.edge)
            return [Order("B", px=px, sz=delta, tif=self.tif)]
        px = state.close * (1 + self.edge)  # need to sell
        return [Order("A", px=px, sz=-delta, tif=self.tif)]
