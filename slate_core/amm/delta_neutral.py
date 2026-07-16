"""Delta-neutral LP + perp hedge combined backtester (the PDF's top recommendation).

Provide liquidity on an AMM (earn swap fees, suffer IL) + short the equivalent
perp (hedge the price exposure) = market-neutral yield.

Net PnL = LP_fees + perp_short_pnl - perp_funding - gas_both_legs

When perfectly hedged: IL ≈ 0 (the price move that hurts the LP helps the short).
Net = swap fees - perp funding costs. If perp funding is negative (shorts receive),
the yield is amplified.

For stablecoin pairs (USDC/USDT): IL is negligible, so the hedge adds cost
without much benefit — the LP alone is better. This strategy SHINES for volatile
pairs (ETH/USDC, SOL/USDC) where IL is significant and the hedge removes it.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from slate_core.amm.amm_math import impermanent_loss, in_range
from slate_core.amm.lp_backtester import LPBacktestConfig


@dataclass
class DeltaNeutralConfig:
    # LP leg
    fee_tier: float = 0.0003
    capital: float = 10000.0
    pool_daily_volume: float = 50_000_000.0   # $50M for volatile pairs (lower than stable)
    pool_tvl: float = 50_000_000.0
    range_bps: float = 200.0   # wider for volatile pairs
    # Perp hedge leg
    perp_taker_fee: float = 0.0005
    perp_funding_8h: float = 0.0001   # average funding rate (can be overridden per-bar)
    funding_interval_bars: int = 3     # 3 daily bars = 24h / 8h
    # Both legs
    gas_per_action: float = 5.0        # L2 gas
    warmup: int = 10


@dataclass
class DeltaNeutralResult:
    final_equity: float
    lp_fees: float
    lp_il: float
    perp_price_pnl: float     # PnL from the short position's price movement
    perp_funding: float        # funding paid/received on the short
    total_gas: float
    n_rebalances: int
    bars_hedged: int
    n_bars: int
    apy: float
    equity_curve: List[float] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in self.__dict__.items() if k != "equity_curve"}


def backtest_delta_neutral(
    price_df,                    # OHLCV for the volatile token (e.g., ETH)
    config: Optional[DeltaNeutralConfig] = None,
    funding_df=None,             # optional: df with 'funding' column for real rates
) -> DeltaNeutralResult:
    """Run a delta-neutral LP + perp short hedge.

    The LP provides liquidity in a range around the current price (earning fees,
    suffering IL). The perp short hedges the price exposure (gaining when price
    falls, losing when it rises — exactly offsetting the LP's IL). Funding on the
    short is a cost (if positive) or income (if negative).

    The LP is rebalanced (exit + re-enter at new price) every `rebalance_bars`
    to keep it in range. Each rebalance pays gas on both legs.
    """
    cfg = config or DeltaNeutralConfig()
    cash = cfg.capital
    entry_price = 0.0
    range_lo = 0.0
    range_hi = 0.0
    short_entry = 0.0
    position_active = False
    bars_since_rebal = 0
    rebalance_interval = 7   # rebalance weekly
    position_value = 0.0    # capital deployed in LP (cash is separate)

    lp_fees = 0.0
    lp_il_total = 0.0
    perp_price_pnl = 0.0
    perp_funding_total = 0.0
    total_gas = 0.0
    n_rebalances = 0
    bars_hedged = 0

    closes = price_df["close"].astype(float).values
    n = len(closes)
    funding_rates = None
    if funding_df is not None and "funding" in funding_df.columns:
        funding_rates = funding_df["funding"].astype(float).values

    equity_curve: List[float] = []

    for i in range(cfg.warmup, n):
        price = closes[i]

        if position_active:
            # --- LP leg: accrue fees ---
            if in_range(price, range_lo, range_hi):
                your_share = position_value / cfg.pool_tvl if cfg.pool_tvl > 0 else 0
                fee_share = cfg.pool_daily_volume * cfg.fee_tier * your_share
                lp_fees += fee_share
                cash += fee_share
                bars_hedged += 1

            # --- LP IL (unrealized) ---
            ratio = price / entry_price if entry_price > 0 else 1.0
            unrealized_il = impermanent_loss(ratio) * position_value

            # --- Perp short PnL (offsets IL) ---
            perp_unrealized = (short_entry - price) / short_entry * position_value if short_entry > 0 else 0.0

            # --- Perp funding ---
            if i % cfg.funding_interval_bars == 0:
                if funding_rates is not None and i < len(funding_rates) and funding_rates[i] != 0.0:
                    rate = funding_rates[i]
                else:
                    rate = cfg.perp_funding_8h
                # Short position: receives funding when rate > 0 (longs pay shorts)
                funding_pnl = rate * position_value
                perp_funding_total += funding_pnl
                cash += funding_pnl

            # --- Rebalance check ---
            bars_since_rebal += 1
            if bars_since_rebal >= rebalance_interval or not in_range(price, range_lo, range_hi):
                # Close both legs
                cash += position_value + unrealized_il       # withdraw LP with IL
                cash += perp_unrealized                      # close short
                lp_il_total += unrealized_il
                perp_price_pnl += perp_unrealized
                cash -= cfg.gas_per_action * 2
                total_gas += cfg.gas_per_action * 2
                # Re-enter both legs at current price
                entry_price = price
                short_entry = price
                range_lo = price * (1 - cfg.range_bps / 10000)
                range_hi = price * (1 + cfg.range_bps / 10000)
                position_value = min(cash, cfg.capital)  # redeploy
                cash -= position_value
                cash -= cfg.gas_per_action * 2
                total_gas += cfg.gas_per_action * 2
                bars_since_rebal = 0
                n_rebalances += 1

        elif not position_active:
            # Enter both legs
            entry_price = price
            short_entry = price
            range_lo = price * (1 - cfg.range_bps / 10000)
            range_hi = price * (1 + cfg.range_bps / 10000)
            position_value = cash
            cash = 0.0
            cash -= cfg.gas_per_action * 2
            total_gas += cfg.gas_per_action * 2
            position_active = True
            bars_since_rebal = 0
            n_rebalances += 1

        # Mark equity: cash + LP value (with IL) + short value
        equity = cash
        if position_active and entry_price > 0:
            ratio = price / entry_price
            equity += position_value * (1 + impermanent_loss(ratio))
            equity += position_value * (short_entry - price) / short_entry
        equity_curve.append(equity)

    # Close remaining
    if position_active and entry_price > 0:
        price = closes[-1]
        ratio = price / entry_price
        final_il = impermanent_loss(ratio) * position_value
        lp_il_total += final_il
        perp_price_pnl += (short_entry - price) / short_entry * position_value
        cash += position_value + final_il
        cash += (short_entry - price) / short_entry * position_value
        cash -= cfg.gas_per_action * 2
        total_gas += cfg.gas_per_action * 2

    final_equity = cash
    days = max(1, n - cfg.warmup)
    apy = (final_equity / cfg.capital - 1.0) * 365.0 / days

    return DeltaNeutralResult(
        final_equity=final_equity, lp_fees=lp_fees, lp_il=lp_il_total,
        perp_price_pnl=perp_price_pnl, perp_funding=perp_funding_total,
        total_gas=total_gas, n_rebalances=n_rebalances, bars_hedged=bars_hedged,
        n_bars=max(0, n - cfg.warmup), apy=apy, equity_curve=equity_curve,
    )
