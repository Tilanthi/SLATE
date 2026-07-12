"""Phase 1b availability probe (Task 7).

Probes whether the Phase 1b streams - historical liquidations, historical
basis/mark, open interest, long/short ratio - are obtainable from public Binance
endpoints, so Phase 1b scope can be set against real availability (the spec's
Known Risks). Run: python3 -m slate_core.data.probe_1b_streams
"""
from __future__ import annotations

import datetime
import json

import requests

FAPI = "https://fapi.binance.com"


def probe(symbol: str = "SOLUSDT", days: int = 7) -> dict:
    now = datetime.datetime.now(datetime.UTC)
    e = int(now.timestamp() * 1000)
    s = int((now - datetime.timedelta(days=days)).timestamp() * 1000)
    out: dict = {}

    def try_get(name, endpoint, **params):
        try:
            r = requests.get(FAPI + endpoint, params={"symbol": symbol, **params}, timeout=15)
            body = r.json()
            if isinstance(body, list):
                out[name] = {"status": r.status_code, "rows": len(body),
                             "sample": body[0] if body else None}
            else:
                out[name] = {"status": r.status_code, "body": str(body)[:160]}
        except Exception as exc:  # noqa: BLE001
            out[name] = {"error": str(exc)[:160]}

    try_get("liquidations_allForceOrders(public)", "/fapi/v1/allForceOrders",
            startTime=s, endTime=e, limit=10)
    try_get("liquidations_forceOrders(auth)", "/fapi/v1/forceOrders",
            startTime=s, endTime=e, limit=10)
    try_get("openInterestHist(1d)", "/futures/data/openInterestHist",
            period="1d", startTime=s, endTime=e, limit=10)
    try_get("longShortAccountRatio(1d)", "/futures/data/topLongShortAccountRatio",
            period="1d", startTime=s, endTime=e, limit=10)
    try_get("longShortPositionRatio(1d)", "/futures/data/topLongShortPositionRatio",
            period="1d", startTime=s, endTime=e, limit=10)

    # premiumIndex is a current snapshot (mark + index) - basis now, not history
    try:
        r = requests.get(FAPI + "/fapi/v1/premiumIndex", params={"symbol": symbol}, timeout=15)
        d = r.json()
        out["premiumIndex(snapshot basis)"] = {
            "status": r.status_code, "has_mark_index": ("markPrice" in d and "indexPrice" in d),
            "mark": d.get("markPrice"), "index": d.get("indexPrice"),
            "note": "snapshot only - no history from this endpoint",
        }
    except Exception as exc:  # noqa: BLE001
        out["premiumIndex"] = {"error": str(exc)[:160]}

    print(json.dumps(out, indent=2, default=str))
    return out


if __name__ == "__main__":
    probe()
