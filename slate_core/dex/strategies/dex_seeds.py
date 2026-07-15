"""DEX anomaly seed archetypes — non-obvious starting points for the evolution,
replacing the EMH-dead textbook TA (momentum/MR/breakout). Each is a CEX-form
signal_fn(df, i, params) -> {-1,0,1} so the sandbox/SEARCH-REPLACE machinery is
reused. Targets where a real perp edge is plausible: funding carry, residual
mean-reversion, volatility-regime conditioning.
"""
from __future__ import annotations

import random
from typing import Optional

from slate_core.discovery.evolution.program_database import Program

DEX_SEED_ARCHETYPES = [
    ("funding_carry",
     "# EVOLVE-BLOCK-START\n"
     "def signal_fn(df, i, params):\n"
     "    \"\"\"Funding carry: short when funding is positive (longs pay), long when negative.\"\"\"\n"
     "    if 'funding' not in df.columns:\n"
     "        return 0\n"
     "    fr = df['funding'].iloc[i]\n"
     "    if fr > 0.0001:\n"
     "        return -1\n"
     "    if fr < -0.0001:\n"
     "        return 1\n"
     "    return 0\n"
     "# EVOLVE-BLOCK-END\n"),
    ("residual_mr",
     "# EVOLVE-BLOCK-START\n"
     "def signal_fn(df, i, params):\n"
     "    \"\"\"Mean-revert the detrended residual (close vs its 20-EMA).\"\"\"\n"
     "    close = df['close'].iloc[i]\n"
     "    ema = df['ema_20'].iloc[i] if 'ema_20' in df.columns else close\n"
     "    resid = (close - ema) / ema\n"
     "    if resid < -0.01:\n"
     "        return 1\n"
     "    if resid > 0.01:\n"
     "        return -1\n"
     "    return 0\n"
     "# EVOLVE-BLOCK-END\n"),
    ("vol_regime",
     "# EVOLVE-BLOCK-START\n"
     "def signal_fn(df, i, params):\n"
     "    \"\"\"Trend-follow only in a high-volatility regime (20-bar range expansion).\"\"\"\n"
     "    if i < 20 or 'ema_20' not in df.columns:\n"
     "        return 0\n"
     "    window_range = df['high'].iloc[i - 20:i].max() - df['low'].iloc[i - 20:i].min()\n"
     "    close = df['close'].iloc[i]\n"
     "    if close > 0 and window_range / close > 0.08:\n"
     "        return 1 if close > df['ema_20'].iloc[i] else -1\n"
     "    return 0\n"
     "# EVOLVE-BLOCK-END\n"),
    ("liquidation_aware",
     "# EVOLVE-BLOCK-START\n"
     "def signal_fn(df, i, params):\n"
     "    \"\"\"Liquidation cascade: sharp drop + volume spike = forced selling.\"\"\"\n"
     "    if i < 20:\n"
     "        return 0\n"
     "    ret = df['close'].iloc[i] / df['close'].iloc[i - 1] - 1\n"
     "    avg_vol = df['volume'].iloc[i - 20:i].mean()\n"
     "    if avg_vol <= 0:\n"
     "        return 0\n"
     "    vol_ratio = df['volume'].iloc[i] / avg_vol\n"
     "    if ret < -0.02 and vol_ratio > 2:\n"
     "        return -1\n"
     "    if ret > 0.02 and vol_ratio > 2:\n"
     "        return 1\n"
     "    return 0\n"
     "# EVOLVE-BLOCK-END\n"),
]

_DEX_SEED_RNG = random.Random()


def dex_pick_seed_parent(config, rng: Optional[random.Random] = None) -> Program:
    """Parent for an EMPTY DEX population: a randomly-rotated anomaly archetype
    (funding carry / residual MR / vol-regime), not EMH-dead textbook TA."""
    r = rng or _DEX_SEED_RNG
    if not DEX_SEED_ARCHETYPES:
        from slate_core.discovery.evolution.controller import pick_seed_parent
        return pick_seed_parent(config)
    family, code = r.choice(DEX_SEED_ARCHETYPES)
    return Program(
        candidate_id=f"seed:dex:{family}",
        niche=(family, config.regime_default),
        family=family, regime=config.regime_default,
        fitness_score=0.0, source="seed", code=code,
    )
