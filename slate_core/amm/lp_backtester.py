"""LP (Liquidity Provider) backtester for Uniswap V3 concentrated positions.

Simulates providing liquidity in a price range, accruing swap fees proportional
to pool volume × your in-range share, and suffering impermanent loss when the
price ratio moves from entry. The "strategy" is an `lp_fn(state) -> LPAction`
that decides when to enter / exit / hold.

Honest v1 simplifications (documented):
- Pool volume estimated from token price volatility (vol-scaled proxy), not real
  swap volume (which needs a subgraph/indexer). The APY numbers are indicative.
- No compounding (fees accrue linearly, not reinvested).
- Flat gas cost per enter/exit ($5 on L2; $0 on Hyperliquid EVM).
- In-range share assumes a small position vs total TVL (price impact negligible).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from slate_core.amm.amm_math import (
    amounts_for_liquidity, impermanent_loss, in_range, liquidity_for_amounts,
)

LPFn = Callable[..., Optional[Tuple[str, float]]]


@dataclass
class LPBacktestConfig:
    fee_tier: float = 0.0003          # 0.03% per swap (Uniswap V3 stable pair tier)
    gas_per_action: float = 5.0       # $5 L2 gas per enter/exit (negligible on HL EVM)
    capital: float = 10000.0          # initial USDC to deploy
    pool_daily_volume: float = 100_000_000.0  # $100M daily volume (realistic for USDC/USDT)
    pool_tvl: float = 100_000_000.0   # $100M total liquidity in the pool
    warmup: int = 10


@dataclass
class LPBacktestResult:
    final_equity: float
    total_fees_earned: float
    total_il: float
    total_gas: float
    n_rebalances: int
    bars_in_range: int
    n_bars: int
    apy: float
    equity_curve: List[float] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in self.__dict__.items() if k != "equity_curve"}


class LPBacktester:
    """Simulates an LP position managed by an `lp_fn`."""

    def __init__(self, config: LPBacktestConfig = None):
        self.config = config or LPBacktestConfig()

    def backtest(self, lp_fn: LPFn, df) -> LPBacktestResult:
        cfg = self.config
        cash = cfg.capital
        position_active = False
        entry_price = 0.0
        range_lo = 0.0
        range_hi = 0.0
        position_value = 0.0  # deployed capital (for fee-share calc)

        total_fees = 0.0
        total_il = 0.0
        total_gas = 0.0
        n_rebalances = 0
        bars_in = 0
        equity_curve: List[float] = []

        closes = df["close"].astype(float).values
        n = len(closes)

        for i in range(cfg.warmup, n):
            price = closes[i]

            # accrue fees if LP is active and in range
            if position_active and in_range(price, range_lo, range_hi):
                # Your share of pool fees = pool_volume × fee_tier × (your_capital / pool_tvl)
                your_share = min(1.0, position_value / cfg.pool_tvl) if cfg.pool_tvl > 0 else 0
                fee_share = cfg.pool_daily_volume * cfg.fee_tier * your_share
                total_fees += fee_share
                cash += fee_share
                bars_in += 1

            # compute unrealized IL if LP active
            unrealized_il = 0.0
            if position_active and entry_price > 0:
                ratio = price / entry_price
                unrealized_il = impermanent_loss(ratio) * position_value

            # call lp_fn for action
            try:
                result = lp_fn(df.iloc[i])
            except Exception:
                result = None

            action = "HOLD"
            range_bps = 50.0
            if isinstance(result, dict):
                action = result.get("action", "HOLD")
                range_bps = float(result.get("range_bps", 50.0))
            elif isinstance(result, (list, tuple)) and len(result) >= 1:
                action = result[0]
                if len(result) >= 2:
                    range_bps = float(result[1])

            # apply action
            if action == "EXIT" and position_active:
                cash += position_value + unrealized_il  # withdraw with IL
                total_il += unrealized_il
                cash -= cfg.gas_per_action
                total_gas += cfg.gas_per_action
                position_active = False
                position_value = 0.0
                n_rebalances += 1

            elif action == "ENTER" and not position_active:
                range_bps = max(1.0, min(range_bps, 10000.0))
                range_lo = price * (1.0 - range_bps / 10000.0)
                range_hi = price * (1.0 + range_bps / 10000.0)
                entry_price = price
                position_value = cash  # deploy all available capital
                cash = 0.0             # capital is now in the LP position
                cash -= cfg.gas_per_action
                total_gas += cfg.gas_per_action
                position_active = True
                n_rebalances += 1

            # mark equity (cash + LP position value with unrealized IL)
            unrealized = 0.0
            if position_active and entry_price > 0:
                ratio = price / entry_price
                unrealized = position_value * impermanent_loss(ratio)
            equity = cash + position_value + unrealized
            equity_curve.append(equity)

        # close remaining position
        if position_active and entry_price > 0:
            price = closes[-1]
            ratio = price / entry_price
            final_il = impermanent_loss(ratio) * position_value
            total_il += final_il
            cash += position_value + final_il
            cash -= cfg.gas_per_action
            total_gas += cfg.gas_per_action

        final_equity = cash
        days = max(1, n - cfg.warmup)
        apy = (final_equity / cfg.capital - 1.0) * 365.0 / days

        return LPBacktestResult(
            final_equity=final_equity, total_fees_earned=total_fees,
            total_il=total_il, total_gas=total_gas, n_rebalances=n_rebalances,
            bars_in_range=bars_in, n_bars=max(0, n - cfg.warmup),
            apy=apy, equity_curve=equity_curve,
        )
