"""LP seed archetypes for the evolution pipeline.

Each is a compile_function-compatible lp_fn(bar) -> {"action": ..., "range_bps": ...}.
These are the starting strategies the LLM evolves from.
"""
from __future__ import annotations

import random
from typing import Optional

from slate_core.discovery.evolution.program_database import Program

LP_SEED_ARCHETYPES = [
    ("stablecoin_tight",
     "# EVOLVE-BLOCK-START\n"
     "def lp_fn(bar):\n"
     "    # Always provide liquidity in a tight 10bps range (max fee density).\n"
     "    return {'action': 'ENTER', 'range_bps': 10}\n"
     "# EVOLVE-BLOCK-END\n"),
    ("stablecoin_wide",
     "# EVOLVE-BLOCK-START\n"
     "def lp_fn(bar):\n"
     "    # Wide 200bps range — rarely out of range, steady fees.\n"
     "    return {'action': 'ENTER', 'range_bps': 200}\n"
     "# EVOLVE-BLOCK-END\n"),
    ("vol_conditioned_lp",
     "# EVOLVE-BLOCK-START\n"
     "def lp_fn(bar):\n"
     "    # Enter when vol is low (steady fees), exit when vol spikes (avoid IL).\n"
     "    close = bar['close']\n"
     "    if 'volume' in bar and bar['volume'] > 0:\n"
     "        return {'action': 'ENTER', 'range_bps': 50}\n"
     "    return {'action': 'HOLD'}\n"
     "# EVOLVE-BLOCK-END\n"),
]

_LP_SEED_RNG = random.Random()


def lp_pick_seed_parent(config, rng: Optional[random.Random] = None) -> Program:
    """Parent for an empty LP population: a randomly-rotated LP archetype."""
    r = rng or _LP_SEED_RNG
    family, code = r.choice(LP_SEED_ARCHETYPES)
    return Program(
        candidate_id=f"seed:lp:{family}",
        niche=("lp", "stablecoin"),
        family="lp", regime="stablecoin",
        fitness_score=0.0, source="seed", code=code,
    )
