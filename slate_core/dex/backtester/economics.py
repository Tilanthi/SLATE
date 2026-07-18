"""Hyperliquid economics: fee schedule (maker/taker/rebate), oracle rejection,
min-notional. A fill's `fee` is notional*rate; rate<0 means a net rebate (cash IN).

Fee tiers below are VERIFIED from HL's official docs (hyperliquid.gitbook.io/
hyperliquid-docs/trading/fees, published 2026-05-08). The maker fee is POSITIVE
(a cost) at retail and steps to ZERO at >$500M 14-day volume (tier 4); negative
maker REBATES are a separate, whale-gated schedule (>0.5% of venue maker volume).
So the realistic inflection for MM viability is maker=0% at scale, NOT the rebate.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple


@dataclass
class HLFeeSchedule:
    taker: float = 0.00045        # 0.045% perp taker
    maker: float = 0.00015        # 0.015% perp maker (set <0 to model a rebate tier)
    min_notional: float = 10.0    # USD min trade size (minTradeNtl)
    oracle_tol: float = 0.15      # orders priced >15% from oracle are rejected
                                  # (exact HL threshold undocumented; approximate guard)
    slippage_bps: float = 1.0     # slippage on taker fills (book walking); 1bps is
                                  # realistic for HL SOL ($1000-5000 orders in a deep book)


# Verified perps fee tiers (base-rate column): (min_14d_volume_usd, taker, maker).
# Source: HL official docs, 2026-05-08. Maker reaches 0% at tier 4 (>=$500M).
HL_PERP_FEE_TIERS: List[Tuple[float, float, float]] = [
    (0.0,        0.00045, 0.00015),   # tier 0 (retail):   taker 0.045% / maker 0.015%
    (5_000_000,  0.00040, 0.00012),   # tier 1 (>$5M):     0.040% / 0.012%
    (25_000_000, 0.00035, 0.00008),   # tier 2 (>$25M):    0.035% / 0.008%
    (100_000_000, 0.00030, 0.00004),  # tier 3 (>$100M):   0.030% / 0.004%
    (500_000_000, 0.00028, 0.00000),  # tier 4 (>$500M):   0.028% / 0.000%  <-- maker free
    (2_000_000_000, 0.00026, 0.00000),# tier 5 (>$2B):     0.026% / 0.000%
    (7_000_000_000, 0.00024, 0.00000),# tier 6 (>$7B):     0.024% / 0.000%
]

# Verified maker REBATE tiers (override maker fee, apply on top of the volume tier):
# (min_maker_share_of_venue_14d, maker_rate). Whale-gated — requires you to be a
# significant fraction of the ENTIRE venue's maker volume. Max rebate is -0.3bps.
HL_MAKER_REBATE_TIERS: List[Tuple[float, float]] = [
    (0.005, -0.00001),   # tier 1 (>0.5% of venue maker vol): maker -0.001%
    (0.015, -0.00002),   # tier 2 (>1.5%):                    maker -0.002%
    (0.030, -0.00003),   # tier 3 (>3.0%):                    maker -0.003%
]


def hl_perp_fee_schedule(volume_14d_usd: Optional[float] = None,
                         maker_share_of_venue: Optional[float] = None,
                         base: Optional[HLFeeSchedule] = None) -> HLFeeSchedule:
    """Build an HLFeeSchedule from the verified HL perp tiers.

    `volume_14d_usd` selects the volume tier (maker steps to 0% at >=$500M).
    `maker_share_of_venue` (fraction, e.g. 0.005 = 0.5%) overrides maker with the
    rebate rate if the whale-gated rebate tier is met. Both default to None ->
    retail base (maker +0.015%), the brutally-honest default for a strategy that
    has not demonstrated the volume to qualify for a better tier.
    """
    sched = base or HLFeeSchedule()
    if volume_14d_usd is not None:
        taker, maker = HL_PERP_FEE_TIERS[0][1], HL_PERP_FEE_TIERS[0][2]
        for threshold, t, m in HL_PERP_FEE_TIERS:
            if volume_14d_usd >= threshold:
                taker, maker = t, m
        sched = HLFeeSchedule(taker=taker, maker=maker, min_notional=sched.min_notional,
                              oracle_tol=sched.oracle_tol, slippage_bps=sched.slippage_bps)
    if maker_share_of_venue is not None:
        rebate = None
        for threshold, rate in HL_MAKER_REBATE_TIERS:
            if maker_share_of_venue >= threshold:
                rebate = rate
        if rebate is not None:
            sched.maker = rebate
    return sched


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

