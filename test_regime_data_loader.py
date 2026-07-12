"""Tests for the deterministic multi-stream loader (Phase 1a, Task 6)."""
import pandas as pd
import pytest

from slate_core.data import regime_store
from slate_core.data.regime_data_loader import load_regime_data


def _seed_funding(symbol, dates, vals, tmp_path, monkeypatch):
    monkeypatch.setattr(regime_store, "DATA_DIR", tmp_path)
    df = pd.DataFrame({"funding_rate": vals}, index=pd.to_datetime(dates))
    regime_store.save_stream(symbol, "funding_1d", df)


def test_loader_deterministic(tmp_path, monkeypatch):
    _seed_funding("SOLUSDT", ["2026-06-01", "2026-06-02", "2026-06-03"],
                  [0.001, 0.002, 0.003], tmp_path, monkeypatch)
    a = load_regime_data(["SOLUSDT"], "2026-06-01", "2026-06-03")
    b = load_regime_data(["SOLUSDT"], "2026-06-01", "2026-06-03")
    pd.testing.assert_frame_equal(a["SOLUSDT"], b["SOLUSDT"])
    assert "funding_rate" in a["SOLUSDT"].columns
    assert a["SOLUSDT"].index[0] == pd.Timestamp("2026-06-01")


def test_loader_marks_multi_day_gap_nan(tmp_path, monkeypatch):
    # 2-day gap (06-02, 06-03) between real rows -> must stay NaN
    _seed_funding("SOLUSDT", ["2026-06-01", "2026-06-04"],
                  [0.001, 0.004], tmp_path, monkeypatch)
    d = load_regime_data(["SOLUSDT"], "2026-06-01", "2026-06-04")["SOLUSDT"]
    assert pd.isna(d.loc["2026-06-02", "funding_rate"])
    assert pd.isna(d.loc["2026-06-03", "funding_rate"])


def test_loader_fills_isolated_single_day_gap(tmp_path, monkeypatch):
    # one missing day between real rows -> filled (no fabrication: neighbours anchor it)
    _seed_funding("SOLUSDT", ["2026-06-01", "2026-06-03"],
                  [0.001, 0.003], tmp_path, monkeypatch)
    d = load_regime_data(["SOLUSDT"], "2026-06-01", "2026-06-03")["SOLUSDT"]
    assert d.loc["2026-06-02", "funding_rate"] == 0.001  # forward-filled from 06-01


def test_loader_rejects_future_rows(tmp_path, monkeypatch):
    _seed_funding("SOLUSDT", ["2030-01-01"], [0.001], tmp_path, monkeypatch)
    with pytest.raises(ValueError):
        load_regime_data(["SOLUSDT"], "2026-06-01", "2026-06-03")
