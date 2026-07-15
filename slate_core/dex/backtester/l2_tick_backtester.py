"""Tick-level L2 backtester for orderbook-imbalance scalping.

Replays L2 snapshots (from the accumulator) event-by-event, simulating the
Cyril-style strategy: fade orderbook imbalance → maker entry → TP/SL → taker exit.
This is the microstructure backtester the bar-level pipeline can't express.

The simple version (fade static imbalance) LOSES — the real edge (per the Cyril
analysis) needs: (1) an imbalance TREND filter (rising/falling, not just level),
(2) sub-second execution (100ms order updates), (3) proper maker queue modeling,
(4) multi-coin diversification, (5) days of data not minutes. This module
provides the framework; the refinements are the evolution target.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


@dataclass
class L2TickResult:
    trades: int
    wins: int
    win_rate: float
    pnl: float
    maker_fills: int
    taker_fills: int
    per_trade: float
    equity_curve: List[float] = field(default_factory=list)


def load_l2_snapshots(path: str) -> List[dict]:
    return [json.loads(l) for l in open(path) if l.strip()]


def backtest_imbalance_scalp(
    snaps: List[dict],
    imb_threshold: float = 0.25,
    tp_bps: float = 25.0,
    sl_bps: float = 15.0,
    max_hold: int = 45,
    size: float = 1.0,
    fee_maker: float = 0.00015,
    fee_taker: float = 0.00045,
    use_trend_filter: bool = False,
    trend_window: int = 5,
) -> L2TickResult:
    """Backtest the imbalance-scalping strategy on L2 snapshots.

    Without use_trend_filter: fade any |imbalance| > threshold (simple).
    With use_trend_filter: only fade when imbalance is MOVING AWAY from 0
        (rising for shorts, falling for longs) — closer to the Cyril strategy.
    """
    position = 0
    entry_px = 0.0
    hold = 0
    cash = 0.0
    n_trades = 0
    wins = 0
    maker = 0
    taker = 0
    imb_history: List[float] = []

    for i in range(1, len(snaps)):
        mid = snaps[i]["mid"]
        imb = snaps[i]["imbalance"]
        imb_history.append(imb)
        if len(imb_history) > trend_window:
            imb_history.pop(0)

        # manage open position
        if position != 0:
            pnl_bps = (mid - entry_px) / entry_px * 10000 * position
            hold += 1
            if pnl_bps >= tp_bps or pnl_bps <= -sl_bps or hold >= max_hold:
                exit_val = (mid - entry_px) * position * size
                fee = abs(mid * size) * fee_taker
                cash += exit_val - fee
                if exit_val - fee > 0:
                    wins += 1
                position = 0
                taker += 1
                n_trades += 1
                hold = 0
                continue

        # new entry signal
        if position == 0:
            signal = 0
            if imb > imb_threshold:
                signal = -1
            elif imb < -imb_threshold:
                signal = 1

            if use_trend_filter and signal != 0 and len(imb_history) >= trend_window:
                avg_imb = sum(imb_history) / len(imb_history)
                if signal == -1 and imb < avg_imb:
                    signal = 0   # imbalance not rising → don't short
                elif signal == 1 and imb > avg_imb:
                    signal = 0   # imbalance not falling → don't long

            if signal != 0:
                entry_px = mid
                position = signal
                hold = 0
                cash -= abs(mid * size) * fee_maker
                maker += 1

    if position != 0:
        mid = snaps[-1]["mid"]
        cash += (mid - entry_px) * position * size - abs(mid * size) * fee_taker
        taker += 1
        n_trades += 1

    return L2TickResult(
        trades=n_trades, wins=wins, win_rate=wins / n_trades * 100 if n_trades else 0,
        pnl=cash, maker_fills=maker, taker_fills=taker,
        per_trade=cash / n_trades if n_trades else 0,
    )
