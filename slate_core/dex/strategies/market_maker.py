"""Market-maker archetype: continuously quote a bid + ask around mid, earn the
spread + maker rebate, and skew quotes against inventory (long inventory ->
shift both quotes down to encourage selling). This is the DEX flagship enabled
by zero-gas + maker rebates. Bar-level v1: quotes rest for one bar and fill only
if the bar's range touches them; with an l2_provider the backtester applies
queue-aware fills (definitive).

The quoting logic is EVOLVABLE: pass `quote_fn(state) -> (half_spread_bps,
inv_skew_bps, size)` (sandbox-compiled via signal_sandbox.compile_function) and
the strategy re-derives its quotes each bar from it. Without quote_fn it uses the
fixed constructor params.
"""
from __future__ import annotations

from typing import Callable, List, Optional, Tuple

from slate_core.dex.strategies.action import BarState, DexStrategy, Order

QuoteFn = Callable[[BarState], Optional[Tuple[float, float, float]]]


def _parse_quote(params) -> Tuple[float, float, float]:
    """Accept a (half_spread_bps, inv_skew_bps, size) tuple or a dict."""
    if isinstance(params, dict):
        return (params.get("half_spread_bps", 10.0),
                params.get("inv_skew_bps", 2.0),
                params.get("size", 0.5))
    try:
        half, skew, size = params
        return float(half), float(skew), float(size)
    except Exception:  # noqa: BLE001
        return 10.0, 2.0, 0.5


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


class MarketMakerStrategy(DexStrategy):
    name = "market_maker"

    def __init__(self, quote_fn: Optional[QuoteFn] = None,
                 half_spread_bps: float = 10.0, size: float = 0.5,
                 inv_skew_bps: float = 2.0, max_size: float = 2.0):
        self.quote_fn = quote_fn
        self.half = half_spread_bps / 10000.0
        self.size = size
        self.skew = inv_skew_bps / 10000.0
        self.max_size = max_size

    def _quotes(self, state: BarState):
        """Return (half, skew, size) as fractions/units for this bar."""
        if self.quote_fn is None:
            return self.half, self.skew, self.size
        params = self.quote_fn(state)
        if params is None:
            return None
        half_bps, skew_bps, size = _parse_quote(params)
        # clamp evolved params to sane ranges so a runaway quote can't break things
        half = _clamp(half_bps, 1.0, 500.0) / 10000.0
        skew = _clamp(skew_bps, -200.0, 200.0) / 10000.0
        sz = _clamp(size, 0.0, self.max_size)
        return half, skew, sz

    def act(self, state: BarState) -> List[Order]:
        quotes = self._quotes(state)
        if quotes is None:
            return []
        half, skew, sz = quotes
        mid = state.close
        inv_frac = (state.position / self.max_size) if self.max_size > 0 else 0.0
        adj = -skew * inv_frac                       # long inventory -> quotes down
        bid_px = mid * (1 - half + adj)
        ask_px = mid * (1 + half + adj)
        orders: List[Order] = []
        if state.position < self.max_size and sz > 0:   # room + size to buy
            orders.append(Order("B", px=bid_px, sz=sz, tif="Alo"))
        if state.position > -self.max_size and sz > 0:  # room + size to sell
            orders.append(Order("A", px=ask_px, sz=sz, tif="Alo"))
        return orders
