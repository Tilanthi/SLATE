"""DEX action model — richer than the CEX {-1,0,1} directional signal.

A DEX strategy emits *orders* (maker/taker, resting/crossing, sized), which is
what unlocks maker-rebate capture and two-sided quoting. The backtester asks the
strategy each bar for the orders it wants active THAT bar, then fills them
against the bar's OHLC. Orders do not persist across bars (re-quoted each bar) —
a deliberate bar-level simplification; true persistent-queue realism needs L2
data (deferred).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Optional


@dataclass
class Order:
    side: str               # "B" = buy (add to long / close short), "A" = sell
    px: float               # limit price (ignored for Market)
    sz: float               # base-asset size (>0)
    tif: str = "Limit"      # "Limit" | "Alo" (post-only) | "Market"
    reduce_only: bool = False


@dataclass
class BarState:
    """Read-only market + account view the strategy sees at bar i (past-only:
    `history` is df.iloc[:i+1], set by the backtester's lookahead cage)."""
    i: int
    open: float
    high: float
    low: float
    close: float
    position: float = 0.0        # signed base units (+ long, - short)
    entry_px: float = 0.0        # average entry of the current position
    equity: float = 0.0          # mark-to-close equity in USDC
    timestamp: Any = None
    history: Any = None          # full OHLCV frame up to and including bar i


class DexStrategy:
    """Base class / protocol. Subclasses implement act()."""
    name: str = "dex"

    def act(self, state: BarState) -> List[Order]:  # pragma: no cover - interface
        raise NotImplementedError
