"""Tests for the regime-discovery asset basket and data paths (Phase 1a, Task 1)."""
from slate_core.data.regime_assets import BASKET, validate_symbol, stream_path


def test_basket_is_ten_valid_perps():
    assert len(BASKET) == 10
    for s in BASKET:
        assert s.endswith("USDT"), f"{s} not a USDT perp"
        assert s.isupper()
        assert validate_symbol(s) is True


def test_stream_path_layout():
    p = stream_path("SOLUSDT", "funding_1d")
    assert str(p) == "data/multi_stream/SOLUSDT/funding_1d.parquet"


def test_validate_symbol_rejects_unknown():
    assert validate_symbol("FOOUSDT") is False
    assert validate_symbol("solusdt") is False
