"""Tests for the EvolutionService background loop (evolution/evolution_service.py)."""
import asyncio

from slate_core.discovery.evolution.evolution_service import EvolutionService
from slate_core.discovery.evolution.llm_client import MockLLMClient, LLMConfig


def _svc(tmp_path, **kw):
    return EvolutionService(
        persist_path=str(tmp_path / "evo.db"),
        llm_client=MockLLMClient(LLMConfig()),
        interval_s=0,
        steps_per_cycle=1,
        seed_limit=20,
        **kw,
    )


def test_service_seed_and_status_shape(tmp_path):
    svc = _svc(tmp_path)
    svc.seed(limit=20)
    st = svc.status()
    assert st["running"] is False
    assert st["llm_backend"] == "mock"
    assert st["gate_preset"] == "exploration"
    for key in ("niches", "pool_size", "best_fitness", "stats"):
        assert key in st
    assert "cycles" in st["stats"]


def test_service_start_stop_runs_a_cycle(tmp_path):
    svc = _svc(tmp_path)
    svc.seed(limit=20)

    async def go():
        ok = await svc.start()
        assert ok is True
        await asyncio.sleep(1.0)        # let one cycle run
        await svc.stop()

    asyncio.run(go())
    s = svc.status()
    assert s["running"] is False
    assert s["stats"]["cycles"] >= 1
    assert s["stats"]["produced"] >= 0


def test_service_start_is_idempotent(tmp_path):
    svc = _svc(tmp_path)

    async def go():
        first = await svc.start()
        second = await svc.start()      # already running
        await svc.stop()
        return first, second

    first, second = asyncio.run(go())
    assert first is True
    assert second is False              # no duplicate task
