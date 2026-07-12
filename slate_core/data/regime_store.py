"""Parquet storage + manifest for the regime data layer (Phase 1a, Task 4).

One parquet file per (symbol, stream) daily series under data/multi_stream/, and
a manifest.json recording coverage (rows, start, end) per symbol/stream so the
loader and refresh logic know what's present. DATA_DIR is the module global from
regime_assets; tests monkeypatch it to a tmp dir.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from slate_core.data.regime_assets import DATA_DIR


def _stream_file(symbol: str, stream: str) -> Path:
    p = DATA_DIR / symbol / f"{stream}.parquet"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _manifest_file() -> Path:
    return DATA_DIR / "manifest.json"


def save_stream(symbol: str, stream: str, df: pd.DataFrame) -> bool:
    """Persist a daily series to parquet and update the manifest."""
    df.to_parquet(_stream_file(symbol, stream))
    _update_manifest(symbol, stream, df)
    return True


def load_stream(symbol: str, stream: str) -> pd.DataFrame:
    """Load a daily series; raises FileNotFoundError if absent."""
    p = _stream_file(symbol, stream)
    if not p.exists():
        raise FileNotFoundError(p)
    return pd.read_parquet(p)


def has_stream(symbol: str, stream: str) -> bool:
    return _stream_file(symbol, stream).exists()


def read_manifest() -> dict:
    p = _manifest_file()
    if not p.exists():
        return {}
    return json.loads(p.read_text())


def _update_manifest(symbol: str, stream: str, df: pd.DataFrame) -> None:
    manifest = read_manifest()
    idx = df.index
    manifest.setdefault(symbol, {})[stream] = {
        "rows": int(len(df)),
        "start": str(idx.min()) if len(idx) else None,
        "end": str(idx.max()) if len(idx) else None,
    }
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    _manifest_file().write_text(json.dumps(manifest, indent=2))
