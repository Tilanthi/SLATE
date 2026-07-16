"""LP evolution service — long-running loop hosted by the server.

Mirrors DexEvolutionService. Loads pool data, runs LP evolution concurrently,
persists the population. Selected via SLATE_PIPELINE=amm.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

from slate_core.discovery.evolution.controller import EvolutionConfig
from slate_core.discovery.evolution.fitness_evaluator import FitnessConfig
from slate_core.discovery.evolution.llm_client import LLMClient, LLMConfig, get_llm_client
from slate_core.discovery.evolution.llm_pool import LLMPool, LLMPoolConfig
from slate_core.discovery.evolution.program_database import ProgramDBConfig, ProgramDatabase
from slate_core.amm.lp_controller import (
    LPPromptSampler, run_lp_evolution_parallel, log_lp_verdict,
)
from slate_core.amm.pool_data import load_pool_data

logger = logging.getLogger(__name__)

LP_EVOLUTION_DB_DEFAULT = "slate_core/amm_evolution.db"


class LPEvolutionService:
    def __init__(self, pair: str = "USDCUSDT",
                 persist_path: str = LP_EVOLUTION_DB_DEFAULT,
                 llm_client: Optional[LLMClient] = None,
                 gate_preset: str = "exploration",
                 interval_s: float = 60.0, steps_per_cycle: int = 2,
                 concurrency: int = 4):
        self.pair = pair
        self.gate_preset = gate_preset
        self.interval_s = interval_s
        self.steps_per_cycle = steps_per_cycle
        self.concurrency = concurrency
        self.fitness_config = (FitnessConfig.exploration() if gate_preset == "exploration"
                               else FitnessConfig.strict())
        self.evolution_config = EvolutionConfig(max_signal_complexity=350)
        self.db = ProgramDatabase(ProgramDBConfig(persist_path=persist_path))
        self.db.load()
        self.sampler = LPPromptSampler()
        self.llm = llm_client or get_llm_client(LLMConfig())
        self.pool = LLMPool(self.llm, self.llm, LLMPoolConfig())
        self._task = None
        self._running = False
        self._df = None
        self.stats = {"cycles": 0, "produced": 0, "rejected": 0, "last_error": ""}

    def _load_df(self):
        if self._df is None:
            self._df = load_pool_data(self.pair)
        return self._df

    def status(self) -> dict:
        best = self.db.best()
        return {
            "pipeline": "amm", "running": self._running,
            "pair": self.pair, "gate_preset": self.gate_preset,
            "llm_backend": self.llm.name, "interval_s": self.interval_s,
            "niches": len(self.db.occupied_niches()),
            "pool_size": len(self.db.island_pool()),
            "best_fitness": (best.fitness_score if best else None),
            "best_id": (best.candidate_id if best else None),
            "data_rows": (len(self._df) if self._df is not None else None),
            "stats": dict(self.stats),
        }

    async def start(self) -> bool:
        if self._running:
            return False
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info("LPEvolutionService started (pair=%s, llm=%s)", self.pair, self.llm.name)
        return True

    async def stop(self) -> bool:
        self._running = False
        if self._task is not None:
            self._task.cancel()
            self._task = None
        logger.info("LPEvolutionService stopped")
        return True

    async def _loop(self):
        while self._running:
            try:
                df = self._load_df()
                produced = await run_lp_evolution_parallel(
                    self.db, self.sampler, self.pool, df,
                    n_steps=self.steps_per_cycle, concurrency=self.concurrency,
                    config=self.evolution_config, fitness_config=self.fitness_config)
                self.stats["cycles"] += 1
                self.stats["produced"] += len(produced)
                self.stats["rejected"] += max(0, self.steps_per_cycle - len(produced))
                self.db.save()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                self.stats["last_error"] = str(exc)[:200]
                logger.warning("amm lp cycle error: %s", str(exc)[:200])
            await asyncio.sleep(self.interval_s)
