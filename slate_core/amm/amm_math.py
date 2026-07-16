"""Uniswap V3 concentrated-liquidity math.

Pure functions for tick ↔ price conversion, liquidity ↔ amounts, and impermanent
loss. No I/O — safe to import anywhere. Ported from the 1tick.lp.py reference
implementation + the Uniswap V3 whitepaper formulas.
"""
from __future__ import annotations

import math

LOG_1_0001 = math.log(1.0001)


def price_to_tick(price: float) -> int:
    """Convert a price to the nearest Uniswap V3 tick."""
    if price <= 0:
        return 0
    return int(math.log(price) / LOG_1_0001)


def tick_to_price(tick: int) -> float:
    """Convert a tick to its price (1.0001^tick)."""
    return 1.0001 ** tick


def impermanent_loss(price_ratio: float) -> float:
    """Impermanent loss for a constant-product AMM position.

    IL = 2*sqrt(r)/(1+r) - 1, where r = current_price / initial_price.
    Returns a negative float (loss) or 0.0 at r=1.0. For a V3 concentrated
    position the IL is amplified by the concentration factor, but the base
    formula is the same.
    """
    if price_ratio <= 0:
        return -1.0
    return 2.0 * math.sqrt(price_ratio) / (1.0 + price_ratio) - 1.0


def amounts_for_liquidity(liquidity: float, sqrt_price: float,
                          sqrt_lo: float, sqrt_hi: float) -> tuple:
    """Given a liquidity L and price bounds [lo, hi] (as sqrt prices), compute
    the token0 and token1 amounts at the current price. Returns (amount0, amount1).

    amount0 = token deposited as the "base" (e.g. USDC in a USDC/WETH pool).
    amount1 = token deposited as the "quote" (e.g. WETH).
    """
    if sqrt_price <= sqrt_lo:
        amt0 = liquidity * (sqrt_hi - sqrt_lo) / (sqrt_lo * sqrt_hi)
        return amt0, 0.0
    elif sqrt_price < sqrt_hi:
        amt0 = liquidity * (sqrt_hi - sqrt_price) / (sqrt_price * sqrt_hi)
        amt1 = liquidity * (sqrt_price - sqrt_lo)
        return amt0, amt1
    else:
        amt1 = liquidity * (sqrt_hi - sqrt_lo)
        return 0.0, amt1


def liquidity_for_amounts(sqrt_price: float, sqrt_lo: float, sqrt_hi: float,
                         amount0: float, amount1: float) -> float:
    """Max liquidity L for the given amounts and price range."""
    if sqrt_price <= sqrt_lo:
        if sqrt_hi == sqrt_lo:
            return 0.0
        return amount0 * (sqrt_lo * sqrt_hi) / (sqrt_hi - sqrt_lo)
    elif sqrt_price < sqrt_hi:
        liq0 = amount0 * (sqrt_price * sqrt_hi) / (sqrt_hi - sqrt_price)
        liq1 = amount1 / (sqrt_price - sqrt_lo) if sqrt_price > sqrt_lo else float("inf")
        return min(liq0, liq1)
    else:
        if sqrt_hi == sqrt_lo:
            return 0.0
        return amount1 / (sqrt_hi - sqrt_lo)


def in_range(price: float, lo: float, hi: float) -> bool:
    """True if price is within the LP range [lo, hi]."""
    return lo <= price <= hi
