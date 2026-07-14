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
