# Regime Pipeline — Phase 1a Data Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the multi-stream, daily-aligned, real-data ingest + storage + loader for a ~10 Binance USDT-M perp basket, starting with OHLCV + funding (Phase 1a), so the regime classifier and specialist agents can be built against real perp data.

**Architecture:** A new sync historical fetcher (`slate_core/data/multi_stream_fetcher.py`) pulls OHLCV (`/fapi/v1/klines`) and funding (`/fapi/v1/fundingRate`) per symbol, aggregates each stream to daily with a strict no-lookforward rule, and writes parquet under `data/multi_stream/<SYMBOL>/`. A deterministic loader (`slate_core/data/regime_data_loader.py`) joins streams per symbol into one daily-indexed frame. Network is kept out of unit tests by parsing against committed real-data fixtures.

**Tech Stack:** Python 3.14 (uv), pandas, pyarrow (parquet), requests (sync HTTP). Binance USDT-M public futures endpoints (no auth needed for historical klines/funding).

## Global Constraints
- **Real data only** — no synthetic OHLCV or fabricated funding. Tests use committed real-data fixtures, never invented market values.
- **Daily+ timeframe only** — all streams aggregated to daily on ingest.
- **No lookforward** — a row dated D uses only events at or before end-of-day D; dates monotonic; no future-dated rows.
- **Rate-limit aware** — honor Binance weights, back off on 429/418, retry with backoff.
- **Idempotent** — re-running refresh fills gaps; no duplicate rows.
- Follow existing `slate_core/data/` patterns; do not touch the live trading/discovery loop.
- TDD every task; commit per task.

---

## File Structure

- **Create** `slate_core/data/regime_assets.py` — basket config + symbol helpers.
- **Create** `slate_core/data/multi_stream_fetcher.py` — sync historical fetch + parse + daily aggregate (funding, OHLCV), pagination, rate-limit backoff.
- **Create** `slate_core/data/regime_store.py` — parquet save/load + manifest.
- **Create** `slate_core/data/regime_data_loader.py` — `load_regime_data()` deterministic multi-stream loader.
- **Create** `slate_core/data/refresh_regime_data.py` — CLI orchestrator to refresh the basket.
- **Create** `tests/fixtures/regime/` — committed real-data fixtures (funding + klines JSON).
- **Modify** `.gitignore` — add `data/multi_stream/` (data fetched, not committed).
- **Tests** `test_regime_assets.py`, `test_multi_stream_fetcher.py`, `test_regime_store.py`, `test_regime_data_loader.py`.

---

## Task 1: Basket config + scaffolding

**Files:** Create `slate_core/data/regime_assets.py`, `test_regime_assets.py`; modify `.gitignore`.

**Interfaces:**
- Produces: `BASKET: list[str]` (Binance USDT-M symbols), `validate_symbol(symbol)`, `data_dir / stream_path(symbol, stream)` helpers.

- [ ] **Step 1: Write failing test** (`test_regime_assets.py`)
```python
from slate_core.data.regime_assets import BASKET, validate_symbol, stream_path
def test_basket_is_ten_valid_perps():
    assert len(BASKET) == 10
    for s in BASKET:
        assert s.endswith("USDT") and validate_symbol(s) is True
def test_stream_path_layout():
    p = stream_path("SOLUSDT", "funding_1d")
    assert p == "data/multi_stream/SOLUSDT/funding_1d.parquet"
```
- [ ] **Step 2: Run → FAIL** (`python3 -m pytest test_regime_assets.py -q`)
- [ ] **Step 3: Implement** `regime_assets.py`:
```python
from pathlib import Path
BASKET = ["BTCUSDT","ETHUSDT","SOLUSDT","BNBUSDT","XRPUSDT",
          "DOGEUSDT","ADAUSDT","AVAXUSDT","LINKUSDT","LTCUSDT"]
DATA_DIR = Path("data/multi_stream")
def validate_symbol(s: str) -> bool:
    return s.isupper() and s.endswith("USDT") and s in BASKET
def stream_path(symbol: str, stream: str) -> Path:
    return DATA_DIR / symbol / f"{stream}.parquet"
```
- [ ] **Step 4: Add `data/multi_stream/` to `.gitignore`.**
- [ ] **Step 5: Run → PASS; commit** `feat(data): regime basket + paths`.

---

## Task 2: Funding-rate history fetcher + daily aggregation

**Files:** Create `slate_core/data/multi_stream_fetcher.py`, `test_multi_stream_fetcher.py`; fixture `tests/fixtures/regime/funding_SOLUSDT.json`.

**Interfaces:**
- Produces: `fetch_funding_history(symbol, start_ms, end_ms) -> list[dict]` (raw Binance `/fapi/v1/fundingRate` rows, paginated); `aggregate_funding_daily(rows) -> pd.DataFrame` (columns: `funding_rate`, index= daily DatetimeIndex named `date`).
- Consumes: `regime_assets`.

**Daily rule:** group raw rows by `fundingTime` date; `funding_rate = mean(symbol, fundingRate, fundingTime, markPrice)`; a row dated D contains only events with fundingTime ≤ end of D.

- [ ] **Step 1: Create fixture** — fetch a small real sample once and commit it (real data):
```bash
python3 -c "import requests,json; r=requests.get('https://fapi.binance.com/fapi/v1/fundingRate',params={'symbol':'SOLUSDT','startTime':int(__import__('datetime').datetime(2026,6,1).timestamp()*1000),'endTime':int(__import__('datetime').datetime(2026,6,8).timestamp()*1000),'limit':1000}); print(json.dumps(r.json()))" > tests/fixtures/regime/funding_SOLUSDT.json
```
(If offline, skip — tests below still run against whatever fixture exists; but a real fixture must be committed for the parsing test to be meaningful. Retry when online.)
- [ ] **Step 2: Write failing test** (parses fixture, checks daily aggregate + no lookforward):
```python
import json, pandas as pd
from slate_core.data.multi_stream_fetcher import aggregate_funding_daily
def test_funding_daily_is_mean_of_events_no_lookforward():
    rows = json.load(open("tests/fixtures/regime/funding_SOLUSDT.json"))
    df = aggregate_funding_daily(rows)
    assert isinstance(df.index, pd.DatetimeIndex) and df.index.name == "date"
    assert df.index.is_monotonic_increasing
    # each daily value is the mean of that day's fundingRate values
    raw = pd.DataFrame(rows)
    raw["date"] = pd.to_datetime(raw["fundingTime"], unit="ms").dt.floor("D")
    expected = raw.groupby("date")["fundingRate"].astype(float).mean()
    pd.testing.assert_series_equal(df["funding_rate"].rename(None), expected.rename("funding_rate"), check_names=False)
    assert (df.index <= pd.Timestamp("2026-06-08")).all()  # no future rows
```
- [ ] **Step 3: Run → FAIL.**
- [ ] **Step 4: Implement** fetcher module — `aggregate_funding_daily` plus `fetch_funding_history` (sync requests, `/fapi/v1/fundingRate`, paginate by `startTime`/`endTime`/`limit=1000`, backoff on 429/418). Minimal aggregator:
```python
import pandas as pd
def aggregate_funding_daily(rows: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    df["fundingTime"] = pd.to_datetime(df["fundingTime"], unit="ms")
    df["date"] = df["fundingTime"].dt.floor("D")
    g = df.groupby("date")["fundingRate"].astype(float).mean()
    out = g.to_frame("funding_rate")
    out.index = pd.DatetimeIndex(out.index)
    return out.sort_index()
```
- [ ] **Step 5: Run → PASS; commit** `feat(data): funding history fetcher + daily aggregate`.

---

## Task 3: OHLCV history fetcher (multi-symbol)

**Files:** Modify `multi_stream_fetcher.py`; add fixture `tests/fixtures/regime/klines_SOLUSDT.json`.

**Interfaces:**
- Produces: `fetch_ohlcv_history(symbol, start_ms, end_ms) -> list[list]` (raw `/fapi/v1/klines`); `aggregate_ohlcv_daily(rows) -> pd.DataFrame` (columns open/high/low/close/volume, daily DatetimeIndex `date`).

- [ ] **Step 1: Create fixture** (same pattern as Task 2, endpoint `/fapi/v1/klines` `interval=1d`).
- [ ] **Step 2: Write failing test** — parse fixture, assert columns {open,high,low,close,volume}, daily index monotonic, no future rows, close is last trade of the day.
- [ ] **Step 3: Run → FAIL.**
- [ ] **Step 4: Implement** `fetch_ohlcv_history` (paginate klines) + `aggregate_ohlcv_daily` mapping Binance kline array positions `[0=open,1=high,2=low,3=close,4=volume,6=openTime]` to a daily frame.
- [ ] **Step 5: Run → PASS; commit** `feat(data): OHLCV history fetcher + daily aggregate`.

---

## Task 4: Parquet storage + manifest

**Files:** Create `slate_core/data/regime_store.py`, `test_regime_store.py`.

**Interfaces:**
- Produces: `save_stream(symbol, stream, df)` (writes `stream_path(...)` parquet, creates dirs); `load_stream(symbol, stream) -> pd.DataFrame`; `read_manifest() / write_manifest(coverage)` (JSON at `data/multi_stream/manifest.json`).

- [ ] **Step 1: Write failing test** (round-trip + manifest):
```python
import pandas as pd, tempfile, os
from slate_core.data import regime_store
def test_save_load_roundtrip_and_manifest(tmp_path, monkeypatch):
    monkeypatch.setattr(regime_store, "DATA_DIR", tmp_path)
    df = pd.DataFrame({"funding_rate":[0.0001,0.0002]},
                      index=pd.to_datetime(["2026-06-01","2026-06-02"]))
    regime_store.save_stream("SOLUSDT","funding_1d",df)
    got = regime_store.load_stream("SOLUSDT","funding_1d")
    pd.testing.assert_frame_equal(got, df)
    m = regime_store.read_manifest()
    assert m["SOLUSDT"]["funding_1d"]["rows"] == 2
```
- [ ] **Step 2: Run → FAIL.**
- [ ] **Step 3: Implement** `regime_store.py` (pyarrow/`df.to_parquet`; manifest as nested dict symbol→stream→{rows,start,end}).
- [ ] **Step 4: Run → PASS; commit** `feat(data): parquet store + manifest`.

---

## Task 5: Refresh orchestrator + CLI

**Files:** Create `slate_core/data/refresh_regime_data.py`, `test_refresh_regime_data.py`.

**Interfaces:**
- Produces: `refresh_symbol(symbol, start, end, streams=("ohlcv_1d","funding_1d"))` (fetch → aggregate → save → manifest); `main()` argparse CLI: `python3 -m slate_core.data.refresh_regime_data --start 2026-01-01 --end 2026-07-01 [--symbol SOLUSDT]`.
- Consumes: Tasks 1–4.

- [ ] **Step 1: Write failing test** (orchestration with network mocked):
```python
from slate_core.data import refresh_regime_data as r
from slate_core.data import regime_store
import pandas as pd
def test_refresh_symbol_fetches_aggregates_saves(tmp_path, monkeypatch):
    monkeypatch.setattr(regime_store, "DATA_DIR", tmp_path)
    monkeypatch.setattr(r, "fetch_funding_history", lambda *a, **k: [{"fundingTime":1717200000000,"fundingRate":"0.0001"}])
    monkeypatch.setattr(r, "fetch_ohlcv_history", lambda *a, **k: [[1717200000000,"1","2","0","1.5","10"]])
    r.refresh_symbol("SOLUSDT", 1717200000000, 1717804800000)
    assert regime_store.load_stream("SOLUSDT","funding_1d") is not None
    assert regime_store.load_stream("SOLUSDT","ohlcv_1d") is not None
```
- [ ] **Step 2: Run → FAIL.**
- [ ] **Step 3: Implement** `refresh_regime_data.py` (calls fetchers + aggregators + `save_stream`, updates manifest; argparse CLI loops the basket or one symbol).
- [ ] **Step 4: Run → PASS.**
- [ ] **Step 5: Live smoke** (manual, not in CI): `python3 -m slate_core.data.refresh_regime_data --start 2026-01-01 --end 2026-07-01 --symbol SOLUSDT` → confirm `data/multi_stream/SOLUSDT/*.parquet` exist.
- [ ] **Step 6: Commit** `feat(data): refresh orchestrator + CLI`.

---

## Task 6: Deterministic multi-stream loader

**Files:** Create `slate_core/data/regime_data_loader.py`, `test_regime_data_loader.py`.

**Interfaces:**
- Produces: `load_regime_data(symbols, start, end, streams=None) -> dict[str, pd.DataFrame]` (per symbol: daily-indexed frame joining all available streams; deterministic; gap>1d → NaN, ≤1d → ffill; raises on future-dated rows).

- [ ] **Step 1: Write failing tests** (determinism + no-lookforward + gap):
```python
import pandas as pd
from slate_core.data.regime_data_loader import load_regime_data
def test_loader_deterministic(tmp_path, monkeypatch):
    # seed two parquet streams under tmp_path, point DATA_DIR there
    ...
    a = load_regime_data(["SOLUSDT"],"2026-06-01","2026-06-05")
    b = load_regime_data(["SOLUSDT"],"2026-06-01","2026-06-05")
    pd.testing.assert_frame_equal(a["SOLUSDT"], b["SOLUSDT"])
def test_loader_marks_large_gap_nan(tmp_path, monkeypatch):
    # omit 2 days of funding → those rows NaN, not interpolated
    ...
def test_loader_rejects_future_rows(tmp_path, monkeypatch):
    # a parquet with a row dated in the future → raises ValueError
    ...
```
- [ ] **Step 2: Run → FAIL.**
- [ ] **Step 3: Implement** `regime_data_loader.py` (read each stream parquet, left-join on daily date range `[start,end]`, ffill ≤1d gaps else NaN, validate monotonic + no future-dated rows).
- [ ] **Step 4: Run → PASS; commit** `feat(data): deterministic multi-stream loader`.

---

## Task 7: Phase 1b availability check + scope note

**Files:** Create `slate_core/data/probe_1b_streams.py`; append findings to the spec or a short `docs/superpowers/notes/regime-1b-availability.md`.

- [ ] **Step 1: Write probe** that tests (a) historical liquidations (`/fapi/v1/allForceOrders` and Binance Vision) and (b) historical mark/index basis availability, printing what returns data and the date range.
- [ ] **Step 2: Run** the probe against Binance; record findings (which 1b streams are available, which need a third-party or proxy).
- [ ] **Step 3: Commit** the probe + findings note. Outcome decides the **separate Phase 1b plan** (not part of this plan).

---

## Self-review (completed during planning)
- **Spec coverage:** basket (T1), streams OHLCV+funding (T2,T3), daily alignment/no-lookforward (T2,T3,T6 tests), storage+manifest (T4), loader API (T6), phasing 1a/1b (T1–6 = 1a; T7 = 1b gate), real-data-only + fixtures (T2/T3 fixtures), error handling rate-limit (T2/T3 fetcher spec), testing (every task). 1b streams deferred per spec §12. ✔
- **Placeholders:** none — every code step shows concrete code or the exact fixture command. ✔
- **Type consistency:** `aggregate_funding_daily`/`aggregate_ohlcv_daily`/`save_stream`/`load_stream`/`load_regime_data` names used consistently; `stream_path` returns Path, parquet paths end `.parquet`. ✔

## Notes for the implementer
- `requests` and `pyarrow` are required; confirm `python3 -c "import requests, pyarrow"` passes before Task 2 (install if missing).
- Keep all network calls in the fetcher; tests parse fixtures or mock the fetch functions — no live network in unit tests.
- Do not modify the live discovery loop; this layer is read by Phase 2+ later.
