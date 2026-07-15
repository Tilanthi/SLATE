"""DexEvolutionService: a long-running DEX evolution loop hosted by the server.

Mirrors EvolutionService (CEX) but runs the DEX controller on Hyperliquid candle
data, with a separate population DB (slate_core/dex_evolution.db) and verdict log
(slate_core/dex_verdicts.jsonl). Selected by SLATE_PIPELINE=dex; otherwise the CEX
evolution runs. Paper/discovery only — never places live HL orders.
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
from slate_core.dex.data.load_data import REAL_DATA_DEFAULT, load_candles
from slate_core.dex.evolution.dex_controller import (
    DexPromptSampler, run_dex_evolution,
)

logger = logging.getLogger(__name__)

DEX_EVOLUTION_DB_DEFAULT = "slate_core/dex_evolution.db"


class DexEvolutionService:
    def __init__(self, data_path: str = REAL_DATA_DEFAULT,
                 persist_path: str = DEX_EVOLUTION_DB_DEFAULT,
                 llm_client: Optional[LLMClient] = None,
                 gate_preset: str = "exploration",
                 interval_s: float = 60.0, steps_per_cycle: int = 2):
        self.data_path = data_path
        self.gate_preset = gate_preset
        self.interval_s = interval_s
        self.steps_per_cycle = steps_per_cycle
        self.fitness_config = (FitnessConfig.exploration() if gate_preset == "exploration"
                               else FitnessConfig.strict())
        self.evolution_config = EvolutionConfig()
        self.db = ProgramDatabase(ProgramDBConfig(persist_path=persist_path))
        self.db.load()
        self.sampler = DexPromptSampler()
        self.llm = llm_client or get_llm_client(LLMConfig())
        self.pool = LLMPool(self.llm, self.llm, LLMPoolConfig())
        self._task: Optional[asyncio.Task] = None
        self._running = False
        self._df = None
        self.stats = {"cycles": 0, "produced": 0, "rejected": 0, "last_error": ""}

    def _load_df(self):
        if self._df is None:
            self._df = load_candles(self.data_path)
        return self._df

    def status(self) -> dict:
        best = self.db.best()
        return {
            "pipeline": "dex",
            "running": self._running,
            "venue": "hyperliquid",
            "gate_preset": self.gate_preset,
            "llm_backend": self.llm.name,
            "interval_s": self.interval_s,
            "steps_per_cycle": self.steps_per_cycle,
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
        logger.info("DexEvolutionService started (preset=%s, llm=%s, venue=hyperliquid)",
                    self.gate_preset, self.llm.name)
        return True

    async def stop(self) -> bool:
        self._running = False
        if self._task is not None:
            self._task.cancel()
            self._task = None
        logger.info("DexEvolutionService stopped")
        return True

    async def _loop(self):
        while self._running:
            try:
                df = self._load_df()
                produced = await run_dex_evolution(
                    self.db, self.sampler, self.pool, df,
                    n_steps=self.steps_per_cycle,
                    config=self.evolution_config, fitness_config=self.fitness_config,
                )
                self.stats["cycles"] += 1
                self.stats["produced"] += len(produced)
                self.stats["rejected"] += max(0, self.steps_per_cycle - len(produced))
                self.db.save()
            except asyncio.CancelledError:
                break
            except Exception as exc:  # noqa: BLE001
                self.stats["last_error"] = str(exc)[:200]
                logger.warning("dex evolution cycle error: %s", str(exc)[:200])
            await asyncio.sleep(self.interval_s)
