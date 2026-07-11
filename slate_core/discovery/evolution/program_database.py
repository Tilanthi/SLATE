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
import json
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

    def pareto_archive(self, objectives=None):
        """Non-dominated elite programs across multiple objectives (Phase 3).

        Imports pareto lazily to avoid a circular import (pareto -> Program).
        """
        from slate_core.discovery.evolution.pareto import pareto_front, DEFAULT_OBJECTIVES
        return pareto_front(list(self._elites.values()), objectives or DEFAULT_OBJECTIVES)

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

    def seed_from_discoveries(self, db_path: str, limit: Optional[int] = None,
                              require_validated: bool = False) -> int:
        """Seed the population from existing perpetual_discoveries rows.

        Legacy rows carry metrics but no signal code, so seeded Programs are
        usable as fitness/niche references and inspirations, not as
        re-executable parents (code=None). A row is kept if it shows an edge
        (vs_buy_hold_usdt > 0, else total_profit_usdt > 0).

        require_validated: historically SLATE's validation column is unreliable
        (entire 118k-row backup has passed_validation=0), so it defaults False.
        Set True to only seed rows that passed rigorous validation.
        """
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        where = "WHERE passed_validation = 1" if require_validated else ""
        query = (
            "SELECT strategy_name, edge_type, volatility_regime, total_profit_usdt, "
            "vs_buy_hold_usdt, sharpe_ratio, beat_market, passed_validation, total_trades "
            f"FROM perpetual_discoveries {where} ORDER BY vs_buy_hold_usdt DESC"
        )
        rows = conn.execute(query).fetchall()
        conn.close()
        if limit:
            rows = rows[:limit]
        count = 0
        for row in rows:
            vs_bh = float(row["vs_buy_hold_usdt"]) if row["vs_buy_hold_usdt"] is not None else 0.0
            profit = float(row["total_profit_usdt"]) if row["total_profit_usdt"] is not None else 0.0
            # Prefer the evolved-fitness proxy (edge vs buy-hold); fall back to
            # absolute profit when vs_buy_hold is unpopulated (the production DB
            # currently stores 0.0 there). Skip rows with no edge at all.
            if vs_bh > 0:
                fitness = vs_bh
            elif profit > 0:
                fitness = profit
            else:
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
                fitness_score=fitness,
                source="seed",
                metrics={
                    "total_profit_usdt": profit,
                    "vs_buy_hold_usdt": vs_bh,
                    "sharpe_ratio": float(row["sharpe_ratio"] or 0),
                    "total_trades": int(row["total_trades"] or 0),
                    "beat_market": bool(row["beat_market"]),
                },
            ))
            count += 1
        return count

    def _all_programs(self) -> List[Program]:
        """Deduplicated elites ∪ pool, keyed by candidate_id (elites win ties)."""
        seen: Dict[str, Program] = {}
        for p in list(self._elites.values()) + self._pool:
            seen.setdefault(p.candidate_id, p)
        return list(seen.values())

    def save(self) -> None:
        """Persist the population to sqlite (evolution_population table).

        Idempotent via INSERT OR REPLACE on candidate_id. Path comes from
        config.persist_path; skipped silently if None.
        """
        if not self.config.persist_path:
            return
        conn = sqlite3.connect(self.config.persist_path)
        c = conn.cursor()
        c.execute("""CREATE TABLE IF NOT EXISTS evolution_population (
            candidate_id TEXT PRIMARY KEY,
            niche_family TEXT NOT NULL,
            niche_regime TEXT NOT NULL,
            fitness_score REAL NOT NULL,
            source TEXT,
            parameters_json TEXT,
            code TEXT,
            metrics_json TEXT,
            parent_id TEXT,
            generation INTEGER,
            timestamp TEXT)""")
        for p in self._all_programs():
            c.execute(
                "INSERT OR REPLACE INTO evolution_population "
                "(candidate_id, niche_family, niche_regime, fitness_score, source, "
                " parameters_json, code, metrics_json, parent_id, generation, timestamp) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (
                    p.candidate_id, p.family, p.regime, p.fitness_score, p.source,
                    json.dumps(p.parameters), p.code, json.dumps(p.metrics),
                    p.parent_id, p.generation, p.timestamp,
                ),
            )
        conn.commit()
        conn.close()

    def load(self) -> int:
        """Load the population from sqlite. Returns the number of programs loaded."""
        if not self.config.persist_path:
            return 0
        conn = sqlite3.connect(self.config.persist_path)
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute("SELECT * FROM evolution_population").fetchall()
        except sqlite3.OperationalError:
            rows = []
        conn.close()
        count = 0
        for row in rows:
            self.add(Program(
                candidate_id=row["candidate_id"],
                niche=(row["niche_family"], row["niche_regime"]),
                family=row["niche_family"],
                regime=row["niche_regime"],
                fitness_score=float(row["fitness_score"]),
                source=row["source"] or "evolved",
                parameters=json.loads(row["parameters_json"] or "{}"),
                code=row["code"],
                metrics=json.loads(row["metrics_json"] or "{}"),
                parent_id=row["parent_id"],
                generation=int(row["generation"] or 0),
                timestamp=row["timestamp"] or "",
            ))
            count += 1
        return count
