"""L2 + trade accumulator for Hyperliquid microstructure data.

Captures real-time L2 order-book snapshots (via polling l2_book every ~1s) and
individual trade events (via WebSocket subscription), storing them as JSONL for
future tick-level backtesting. This is the data infrastructure needed to capture
the real HL edge (orderbook-imbalance scalping at sub-second resolution).

Run as a background process:
    python3 -m slate_core.dex.data.l2_accumulator SOL
    python3 -m slate_core.dex.data.l2_accumulator SOL,BTC,ETH

The Cyril analysis showed: profitable HL strategies use orderbook imbalance
(bid_depth vs ask_depth) to fade temporary pressure, with 5-7 second holds.
This accumulator captures the L2 depth needed to compute that signal, growing
history from now forward.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from typing import List

import aiohttp

from slate_core.dex.data.hyperliquid_client import HLClient

logger = logging.getLogger(__name__)
HL_WS_URL = "wss://api.hyperliquid.xyz/ws"
L2_STORE_DIR = "sol_data_cache"


def _l2_path(coin: str) -> str:
    return os.path.join(L2_STORE_DIR, f"L2_{coin}.jsonl")


def _trades_path(coin: str) -> str:
    return os.path.join(L2_STORE_DIR, f"TRADES_{coin}.jsonl")


def snapshot_l2(client: HLClient, coin: str) -> dict | None:
    """Fetch one L2 snapshot + compute the orderbook imbalance signal."""
    book = client.l2_book(coin)
    if not book or "levels" not in book or len(book["levels"]) < 2:
        return None
    bids = book["levels"][0][:20]
    asks = book["levels"][1][:20]
    if not bids or not asks:
        return None
    bid_depth = sum(float(l["px"]) * float(l["sz"]) for l in bids[:5])
    ask_depth = sum(float(l["px"]) * float(l["sz"]) for l in asks[:5])
    total = bid_depth + ask_depth
    imbalance = (bid_depth - ask_depth) / total if total > 0 else 0.0
    best_bid = float(bids[0]["px"])
    best_ask = float(asks[0]["px"])
    mid = (best_bid + best_ask) / 2
    spread_bps = (best_ask - best_bid) / mid * 10000 if mid > 0 else 0
    return {
        "t": int(time.time() * 1000),
        "coin": coin,
        "mid": round(mid, 6),
        "spread_bps": round(spread_bps, 2),
        "imbalance": round(imbalance, 4),
        "bids": [[float(l["px"]), float(l["sz"])] for l in bids],
        "asks": [[float(l["px"]), float(l["sz"])] for l in asks],
    }


def _append(path: str, record: dict) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")


async def accumulate_l2(coin: str, interval_s: float = 1.0) -> None:
    """Poll l2_book at interval_s and store snapshots. Runs forever."""
    client = HLClient()
    path = _l2_path(coin)
    count = 0
    logger.info("L2 accumulator started for %s (interval=%.1fs, path=%s)", coin, interval_s, path)
    while True:
        try:
            snap = snapshot_l2(client, coin)
            if snap:
                _append(path, snap)
                count += 1
                if count % 300 == 0:
                    logger.info("L2 %s: %d snapshots (%.1f min)", coin, count, count * interval_s / 60)
        except Exception as exc:
            logger.warning("L2 snapshot error for %s: %s", coin, str(exc)[:80])
        await asyncio.sleep(interval_s)


async def accumulate_trades(coin: str) -> None:
    """Subscribe to HL WebSocket trades and store each event. Auto-reconnects."""
    path = _trades_path(coin)
    sub = {"method": "subscribe", "subscription": {"type": "trades", "coin": coin}}
    count = 0
    logger.info("Trade accumulator started for %s (path=%s)", coin, path)
    while True:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.ws_connect(HL_WS_URL) as ws:
                    await ws.send_json(sub)
                    async for msg in ws:
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            data = json.loads(msg.data)
                            if data.get("channel") == "trades":
                                for trade in data.get("data", []):
                                    trade["t"] = int(time.time() * 1000)
                                    _append(path, trade)
                                    count += 1
                                    if count % 100 == 0:
                                        logger.info("Trades %s: %d events", coin, count)
                        elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                            break
        except Exception as exc:
            logger.warning("Trade WS error for %s: %s — reconnecting in 5s", coin, str(exc)[:80])
        await asyncio.sleep(5)


async def run_accumulator(coins: List[str], interval_s: float = 1.0) -> None:
    """Run L2 polling + trade WebSocket for all coins concurrently."""
    tasks = []
    for coin in coins:
        tasks.append(asyncio.create_task(accumulate_l2(coin, interval_s)))
        tasks.append(asyncio.create_task(accumulate_trades(coin)))
    await asyncio.gather(*tasks)


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    coin_arg = sys.argv[1] if len(sys.argv) > 1 else "SOL"
    coins = [c.strip().upper() for c in coin_arg.split(",")]
    interval = float(sys.argv[2]) if len(sys.argv) > 2 else 1.0
    print(f"Starting L2+trade accumulator for {coins} (interval={interval}s)")
    asyncio.run(run_accumulator(coins, interval))
