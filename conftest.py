"""Root pytest configuration for SLATE.

Shared fixtures used by the evolution test suite. Market data is REAL (loaded
from sol_data_cache via pd.read_json) — no synthetic OHLCV, per project rules.
"""
import pandas as pd
import pytest
from pathlib import Path

REAL_DATA = Path("sol_data_cache/SOLUSDT_perpetual_1h_6m.csv")  # JSON array, .csv ext


@pytest.fixture(scope="session")
def sol_slice() -> pd.DataFrame:
    """A 120-row slice of REAL SOL perpetual data for fast tests.

    The file is a JSON array despite its .csv extension (see server.py:362),
    so we read it with pd.read_json, not pd.read_csv.
    """
    assert REAL_DATA.exists(), f"Real market data not found at {REAL_DATA.resolve()}"
    df = pd.read_json(REAL_DATA)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.set_index("timestamp").sort_index()
    assert "close" in df.columns, "real data must have a 'close' column"
    return df.head(120).copy()


@pytest.fixture(autouse=True)
def _redirect_verdict_log(tmp_path):
    """Never let the funnel verdict logger (ASTRA §7.2) write to its real default
    path during tests. Redirect BOTH the CEX singleton and the DEX module-level
    logger to throwaway tmp files so tests don't pollute slate_core/."""
    from slate_core.discovery.evolution.verdict_log import (
        VerdictLogger, set_verdict_logger,
    )
    set_verdict_logger(VerdictLogger(str(tmp_path / "test_verdicts.jsonl")))
    # Clear the DEX hash-dedup set so identical mock code in one test doesn't
    # dedupe a later test's candidate (test isolation).
    try:
        from slate_core.dex.evolution.dex_controller import _EVALUATED_HASHES
        _EVALUATED_HASHES.clear()
    except Exception:
        pass
    # Redirect the DEX + AMM verdict loggers (separate module-level instances).
    try:
        import slate_core.dex.evolution.dex_controller as _dex_ctrl
        _dex_ctrl._dex_logger = VerdictLogger(str(tmp_path / "test_dex_verdicts.jsonl"))
    except Exception:
        pass
    try:
        import slate_core.amm.lp_controller as _lp_ctrl
        _lp_ctrl._lp_logger = VerdictLogger(str(tmp_path / "test_lp_verdicts.jsonl"))
        _lp_ctrl._LP_EVALUATED_HASHES.clear()
    except Exception:
        pass
    # Redirect the DEX verdict logger (separate module-level instance, NOT the
    # CEX singleton — without this, DEX controller tests leak mock verdicts into
    # the production dex_verdicts.jsonl).
    try:
        import slate_core.dex.evolution.dex_controller as _dex_ctrl
        _dex_ctrl._dex_logger = VerdictLogger(str(tmp_path / "test_dex_verdicts.jsonl"))
    except Exception:
        pass
    yield
    set_verdict_logger(None)
