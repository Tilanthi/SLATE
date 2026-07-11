"""EvolutionService: a long-running evolution loop hosted by the server (D3).

Wraps the controller + program database + LLM pool into a startable/stoppable
background task that runs alongside the existing closed-loop discovery. Loads
DAILY data (load_data.load_daily_data), uses the 'exploration' gate preset by
default so the loop produces survivors, and persists the population between
restarts. Status is exposed via the /api/evolution/* endpoints.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

from slate_core.discovery.evolution.controller import EvolutionConfig, run_evolution
from slate_core.discovery.evolution.fitness_evaluator import FitnessConfig
from slate_core.discovery.evolution.load_data import REAL_DATA_DEFAULT, load_daily_data
from slate_core.discovery.evolution.llm_client import LLMClient, LLMConfig, get_llm_client
from slate_core.discovery.evolution.llm_pool import LLMPool, LLMPoolConfig
from slate_core.discovery.evolution.program_database import ProgramDBConfig, ProgramDatabase
from slate_core.discovery.evolution.prompt_sampler import PromptSampler

logger = logging.getLogger(__name__)

DISCOVERIES_DB_DEFAULT = "slate_core/slate_realistic_discoveries.db"
EVOLUTION_DB_DEFAULT = "slate_core/slate_evolution.db"


class EvolutionService:
    def __init__(
        self,
        data_path: str = REAL_DATA_DEFAULT,
        discoveries_db_path: str = DISCOVERIES_DB_DEFAULT,
        persist_path: str = EVOLUTION_DB_DEFAULT,
        llm_client: Optional[LLMClient] = None,
        gate_preset: str = "exploration",
        interval_s: float = 60.0,
        steps_per_cycle: int = 2,
        seed_limit: int = 200,
    ):
        self.data_path = data_path
        self.discoveries_db_path = discoveries_db_path
        self.gate_preset = gate_preset
        self.interval_s = interval_s
        self.steps_per_cycle = steps_per_cycle
        self.seed_limit = seed_limit

        self.fitness_config = (
            FitnessConfig.exploration() if gate_preset == "exploration"
            else FitnessConfig.strict()
        )
        self.evolution_config = EvolutionConfig()

        self.db = ProgramDatabase(ProgramDBConfig(persist_path=persist_path))
        self.db.load()                       # restore population if present
        self.sampler = PromptSampler()
        self.llm = llm_client or get_llm_client(LLMConfig())
        self.pool = LLMPool(self.llm, self.llm, LLMPoolConfig())

        self._task: Optional[asyncio.Task] = None
        self._running = False
        self._df = None
        self.stats = {"cycles": 0, "produced": 0, "rejected": 0, "last_error": ""}

    # ----- data -----
    def _load_df(self):
        if self._df is None:
            self._df = load_daily_data(self.data_path)
        return self._df

    # ----- public ops -----
    def seed(self, limit: Optional[int] = None) -> int:
        return self.db.seed_from_discoveries(
            self.discoveries_db_path, limit=limit or self.seed_limit
        )

    def status(self) -> dict:
        best = self.db.best()
        return {
            "running": self._running,
            "gate_preset": self.gate_preset,
            "llm_backend": self.llm.name,
            "interval_s": self.interval_s,
            "steps_per_cycle": self.steps_per_cycle,
            "niches": len(self.db.occupied_niches()),
            "pool_size": len(self.db.island_pool()),
            "best_fitness": (best.fitness_score if best else None),
            "best_id": (best.candidate_id if best else None),
            "data_rows": (len(self._df) if self._df is not None else None),
            "data_is_daily": True,
            "stats": dict(self.stats),
        }

    async def start(self) -> bool:
        if self._running:
            return False
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info("EvolutionService started (preset=%s, llm=%s)",
                    self.gate_preset, self.llm.name)
        return True

    async def stop(self) -> bool:
        self._running = False
        if self._task is not None:
            self._task.cancel()
            self._task = None
        logger.info("EvolutionService stopped")
        return True

    async def _loop(self):
        while self._running:
            try:
                df = self._load_df()
                produced = await run_evolution(
                    self.db, self.sampler, self.pool, df,
                    n_steps=self.steps_per_cycle,
                    config=self.evolution_config,
                    fitness_config=self.fitness_config,
                )
                self.stats["cycles"] += 1
                self.stats["produced"] += len(produced)
                self.stats["rejected"] += max(0, self.steps_per_cycle - len(produced))
                self.db.save()
            except asyncio.CancelledError:
                break
            except Exception as exc:  # noqa: BLE001 - never crash the loop
                self.stats["last_error"] = str(exc)[:200]
                logger.warning("evolution cycle error: %s", str(exc)[:200])
            await asyncio.sleep(self.interval_s)
