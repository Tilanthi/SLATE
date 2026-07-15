"""Hyperliquid economics: fee schedule (maker/taker/rebate), oracle rejection,
min-notional. From the live feeSchedule: perp taker 0.045% / maker 0.015%, with
NEGATIVE maker rates (rebates) at high maker-fraction tiers. A fill's `fee` is
notional*rate; rate<0 means a net rebate (cash IN)."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class HLFeeSchedule:
    taker: float = 0.00045        # 0.045% perp taker
    maker: float = 0.00015        # 0.015% perp maker (set <0 to model a rebate tier)
    min_notional: float = 10.0    # USD min trade size (minTradeNtl)
    oracle_tol: float = 0.15      # orders priced >15% from oracle are rejected
                                  # (exact HL threshold undocumented; approximate guard)
    slippage_bps: float = 1.0     # slippage on taker fills (book walking); 1bps is
                                  # realistic for HL SOL ($1000-5000 orders in a deep book)


def fee_for(notional: float, is_maker: bool, schedule: HLFeeSchedule) -> float:
    """Fee (positive = cost) or rebate (negative = cash in) for a fill."""
    rate = schedule.maker if is_maker else schedule.taker
    return notional * rate


def min_notional_ok(sz: float, px: float, schedule: HLFeeSchedule) -> bool:
    return sz * px >= schedule.min_notional


def oracle_ok(limit_px: float, oracle_px: float, schedule: HLFeeSchedule) -> bool:
    if not oracle_px or oracle_px <= 0:
        return True
    return abs(limit_px - oracle_px) / oracle_px <= schedule.oracle_tol
