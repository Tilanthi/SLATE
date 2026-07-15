"""Thin Hyperliquid REST client (first-party /info endpoint).

Fetches candles, funding history, and perp meta from Hyperliquid. The candle
endpoint caps history at the most recent 5,000 candles and paginates 500/req,
so this client pages forward using each batch's last open-time +1. Used only for
*historical* data discovery (paper backtests) — never places orders.

Per Hyperliquid docs: https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/info-endpoint
"""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

import requests

HL_API = "https://api.hyperliquid.xyz/info"
PAGE = 500  # max elements per info response


def _default_post(body: Dict[str, Any], timeout: float = 30.0) -> Any:
    r = requests.post(HL_API, json=body,
                      headers={"Content-Type": "application/json"}, timeout=timeout)
    r.raise_for_status()
    return r.json()


class HLClient:
    """POSTs JSON to the /info endpoint. `post_fn` is injectable for tests."""

    def __init__(self, post_fn: Optional[Callable[[Dict[str, Any]], Any]] = None,
                 page: int = PAGE):
        self._post = post_fn or _default_post
        self.page = page

    def candles(self, coin: str, interval: str, start_ms: Optional[int] = None,
                end_ms: Optional[int] = None) -> List[Dict[str, Any]]:
        """OHLCV candles for a perp. With start_ms, pages forward (≤5000 by API).
        Without start_ms, returns the most recent ~500 only."""
        req: Dict[str, Any] = {"coin": coin, "interval": interval}
        if start_ms is not None:
            req["startTime"] = start_ms
        if end_ms is not None:
            req["endTime"] = end_ms
        out: List[Dict[str, Any]] = []
        while True:
            batch = self._post({"type": "candleSnapshot", "req": dict(req)}) or []
            if not batch:
                break
            out.extend(batch)
            if len(batch) < self.page:
                break
            req["startTime"] = batch[-1]["t"] + 1          # advance past last open time
        return out

    def funding_history(self, coin: str, start_ms: Optional[int] = None,
                        end_ms: Optional[int] = None) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        params: Dict[str, Any] = {"type": "fundingHistory", "coin": coin}
        if start_ms is not None:
            params["startTime"] = start_ms
        if end_ms is not None:
            params["endTime"] = end_ms
        while True:
            batch = self._post(dict(params)) or []
            if not batch:
                break
            out.extend(batch)
            if len(batch) < self.page:
                break
            params["startTime"] = batch[-1]["time"] + 1
        return out

    def meta(self) -> Dict[str, Any]:
        return self._post({"type": "meta"}) or {}
