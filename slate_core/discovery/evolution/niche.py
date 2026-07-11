"""MAP-Elites niche descriptor for SLATE's program database.

A niche is the MAP-Elites grid cell. Phase 1 uses a 2-D grid:
(strategy_family, regime_bucket) — cheap metadata that already exists on every
discovery row. Phase 3 will extend this with a behavioural signature and
return-correlation novelty.
"""
from __future__ import annotations

from typing import Any, Dict, Tuple

Niche = Tuple[str, str]


def compute_niche(strategy_meta: Dict[str, Any]) -> Niche:
    """Return (family, regime_bucket), normalised to lowercase, 'unknown' if absent."""
    family = str(strategy_meta.get("edge_type") or "unknown").strip().lower() or "unknown"
    regime = str(strategy_meta.get("volatility_regime") or "unknown").strip().lower() or "unknown"
    return (family, regime)
