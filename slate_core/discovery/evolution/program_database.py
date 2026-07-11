"""Program database for SLATE evolution: MAP-Elites elites + island pool (Phase 1).

The AlphaEvolve component that turns SLATE's independent discoveries into an
accumulating, diversity-maintained population. Each MAP-Elites niche
(strategy-family x regime) keeps its single best program; a bounded island pool
holds recent diverse programs for exploration. The controller primitive
sample() -> (parent, inspirations) is added in Task 1.3.
"""
from __future__ import annotations

import random
import sqlite3
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

Niche = Tuple[str, str]


@dataclass
class ProgramDBConfig:
    island_pool_size: int = 50             # exploration pool cap
    inspiration_count: int = 3             # inspirations returned by sample()
    novelty_correlation_max: float = 0.7   # reserved for Phase 3 diversity
    persist_path: Optional[str] = "slate_core/slate_evolution.db"


@dataclass
class Program:
    """One candidate in the population. fitness_score = -inf means rejected."""
    candidate_id: str
    niche: Niche
    family: str
    regime: str
    fitness_score: float
    source: str = "evolved"                # "seed" | "evolved"
    parameters: Dict[str, Any] = field(default_factory=dict)
    code: Optional[str] = None             # present for Phase 4 evolved programs
    metrics: Dict[str, Any] = field(default_factory=dict)
    parent_id: Optional[str] = None
    generation: int = 0
    timestamp: str = ""


class ProgramDatabase:
    """MAP-Elites elites (best per niche) + bounded island exploration pool."""

    def __init__(self, config: Optional[ProgramDBConfig] = None):
        self.config = config or ProgramDBConfig()
        self._elites: Dict[Niche, Program] = {}
        self._pool: List[Program] = []

    def add(self, program: Program) -> None:
        """MAP-Elites: replace the niche elite iff strictly better; cap the pool."""
        current = self._elites.get(program.niche)
        if current is None or program.fitness_score > current.fitness_score:
            self._elites[program.niche] = program
        self._pool.append(program)
        if len(self._pool) > self.config.island_pool_size:
            self._pool.sort(key=lambda p: p.fitness_score, reverse=True)
            self._pool = self._pool[: self.config.island_pool_size]

    def elite(self, niche: Niche) -> Optional[Program]:
        return self._elites.get(niche)

    def island_pool(self) -> List[Program]:
        return list(self._pool)

    def best(self) -> Optional[Program]:
        if not self._elites:
            return None
        return max(self._elites.values(), key=lambda p: p.fitness_score)

    def sample(self, rng: Optional[random.Random] = None):
        """AlphaEvolve controller primitive: return (parent, inspirations).

        70% exploit the global best, 30% explore a random niche elite.
        Inspirations are drawn from OTHER niches for diversity. Deterministic
        when rng is seeded. Returns (None, []) on an empty database.
        """
        r = rng or random.Random()
        if not self._elites:
            return None, []
        niches = list(self._elites.keys())
        if r.random() < 0.7:
            parent = self.best()
        else:
            parent = self._elites[r.choice(niches)]
        others = [self._elites[n] for n in niches if n != parent.niche]
        r.shuffle(others)
        inspirations = others[: self.config.inspiration_count]
        return parent, inspirations

    def occupied_niches(self) -> List[Niche]:
        return list(self._elites.keys())

    def seed_from_discoveries(self, db_path: str, limit: Optional[int] = None) -> int:
        """Seed the population from existing perpetual_discoveries rows.

        Legacy rows carry metrics but no signal code, so seeded Programs are
        usable as fitness/niche references and inspirations, not as
        re-executable parents (code=None). Only validated rows with a positive
        OOS-style edge (vs_buy_hold_usdt > 0) are kept — they add real niche
        value; non-edges are skipped.
        """
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        query = (
            "SELECT strategy_name, edge_type, volatility_regime, total_profit_usdt, "
            "vs_buy_hold_usdt, sharpe_ratio, beat_market, passed_validation, total_trades "
            "FROM perpetual_discoveries WHERE passed_validation = 1 "
            "ORDER BY vs_buy_hold_usdt DESC"
        )
        rows = conn.execute(query).fetchall()
        conn.close()
        if limit:
            rows = rows[:limit]
        count = 0
        for row in rows:
            vs_bh = float(row["vs_buy_hold_usdt"]) if row["vs_buy_hold_usdt"] is not None else 0.0
            if vs_bh <= 0:
                continue
            niche = (
                str(row["edge_type"] or "unknown").lower(),
                str(row["volatility_regime"] or "unknown").lower(),
            )
            self.add(Program(
                candidate_id=f"seed:{row['strategy_name']}",
                niche=niche,
                family=niche[0],
                regime=niche[1],
                fitness_score=vs_bh,
                source="seed",
                metrics={
                    "total_profit_usdt": float(row["total_profit_usdt"] or 0),
                    "sharpe_ratio": float(row["sharpe_ratio"] or 0),
                    "total_trades": int(row["total_trades"] or 0),
                    "beat_market": bool(row["beat_market"]),
                },
            ))
            count += 1
        return count
