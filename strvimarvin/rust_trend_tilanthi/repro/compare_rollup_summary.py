#!/usr/bin/env python3
from __future__ import annotations

import json
import math
import sys
from pathlib import Path


FIELDS = [
    ("starting_balance", 0.01),
    ("final_balance", 0.05),
    ("total_pnl", 0.05),
    ("net_return_pct", 0.001),
    ("max_drawdown_pct", 0.001),
    ("profit_factor", 0.0001),
    ("trades", 0.0),
]


def load(path: str) -> dict:
    return json.loads(Path(path).read_text())


def close(a: float, b: float, tolerance: float) -> bool:
    if tolerance == 0.0:
        return int(a) == int(b)
    return math.isclose(float(a), float(b), rel_tol=0.0, abs_tol=tolerance)


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: compare_rollup_summary.py <reference_summary.json> <new_summary.json>", file=sys.stderr)
        return 2
    ref = load(sys.argv[1])
    got = load(sys.argv[2])
    failures = 0
    for field, tolerance in FIELDS:
        ok = close(ref[field], got[field], tolerance)
        status = "PASS" if ok else "FAIL"
        print(f"{status} {field}: reference={ref[field]} new={got[field]} tolerance={tolerance}")
        failures += 0 if ok else 1
    ref_status = ref.get("provenance_validation_status")
    got_status = got.get("provenance_validation_status")
    status_ok = ref_status == got_status
    print(f"{'PASS' if status_ok else 'FAIL'} provenance_validation_status: reference={ref_status!r} new={got_status!r}")
    failures += 0 if status_ok else 1
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
