"""
SLATE Autonomous Trading Executor

Makes real trading decisions in paper trading mode.
Integrates with discoveries to execute autonomous trading decisions.
"""

import logging
import asyncio
from typing import Dict, List, Any, Optional
from datetime import datetime
from dataclasses import dataclass

from .config import Discovery, AutonomousConfig

try:
    from ..connectors.binance_spot import BinanceSpotConnector
    CONNECTOR_AVAILABLE = True
except ImportError:
    CONNECTOR_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class TradingDecision:
    """Autonomous trading decision."""
    decision_type: str  # "ENTER_LONG", "ENTER_SHORT", "EXIT", "HOLD"
    symbol: str
    confidence: float
    reason: str
    discovery: Discovery
    paper_execution: bool  # Always True - safety constraint
    timestamp: datetime

    def to_dict(self):
        return {
            'decision_type': self.decision_type,
            'symbol': self.symbol,
            'confidence': self.confidence,
            'reason': self.reason,
            'discovery_summary': self.discovery.answer[:100] if self.discovery else None,
            'paper_execution': self.paper_execution,
            'timestamp': self.timestamp.isoformat()
        }


class TradingExecutor:
    """
    Execute autonomous trading decisions in paper trading mode.

    SAFETY:
    - ONLY paper trading (never real money)
    - All decisions logged and reviewable
    - Transaction costs always applied
    - Position sizing risk-managed
    """

    def __init__(self, config: AutonomousConfig):
        self.config = config

        # Initialize paper trading connector
        if CONNECTOR_AVAILABLE:
            self.paper_exchange = BinanceSpotConnector()
            logger.info("Paper trading connector initialized")
        else:
            self.paper_exchange = None
            logger.warning("Binance connector not available - paper trading limited")

        self.decision_history = []
        self.paper_positions = {}

        logger.info("Trading Executor initialized in PAPER_TRADING mode")

    async def evaluate_discoveries_for_trading(self, discoveries: List[Discovery]) -> List[TradingDecision]:
        """
        Evaluate discoveries and make trading decisions.

        This is where autonomous trading decisions are made.
        Multiple discoveries are analyzed and prioritized.
        """
        decisions = []

        for discovery in discoveries:
            # Skip if not realistic edge
            if not discovery.realistic_edge:
                logger.debug(f"Skipping {discovery.symbol}: not realistic edge")
                continue

            # Skip if confidence too low
            if discovery.confidence < self.config.min_confidence_to_store:
                logger.debug(f"Skipping {discovery.symbol}: confidence {discovery.confidence:.2f} too low")
                continue

            # Skip if drawdown too high
            if discovery.max_drawdown_pct > self.config.max_drawdown_pct:
                logger.debug(f"Skipping {discovery.symbol}: drawdown {discovery.max_drawdown_pct:.1f}% too high")
                continue

            # Calculate decision score
            decision_score = self._calculate_decision_score(discovery)

            # Make trading decision
            if decision_score > 0.7:  # High confidence threshold
                decision = TradingDecision(
                    decision_type="ENTER_LONG",  # Simplified - can be enhanced
                    symbol=discovery.symbol,
                    confidence=decision_score,
                    reason=f"Profitable strategy discovered: {discovery.answer[:100]}",
                    discovery=discovery,
                    paper_execution=True,  # ALWAYS paper trading
                    timestamp=datetime.now()
                )
                decisions.append(decision)

                logger.info(f"🎯 Trading decision: {decision.decision_type} {decision.symbol}")
                logger.info(f"   Confidence: {decision.confidence:.1%}")
                logger.info(f"   Reason: {decision.reason}")

        return decisions

    def _calculate_decision_score(self, discovery: Discovery) -> float:
        """
        Calculate trading decision score from discovery metrics.

        Combines multiple factors into a single confidence score.
        """
        score = 0.0

        # Profitability after costs (40% weight)
        if discovery.profit_after_costs > 0:
            profitability_score = min(discovery.profitability_score, 1.0)
            score += profitability_score * 0.40

        # Risk-adjusted returns (25% weight)
        if discovery.sharpe_ratio > 0.5:
            sharpe_score = min(discovery.sharpe_ratio / 2.0, 1.0)
            score += sharpe_score * 0.25

        # Win rate (20% weight)
        if discovery.win_rate > 0.5:
            win_score = (discovery.win_rate - 0.5) * 2  # Scale 0.5-1.0 to 0.0-1.0
            score += win_score * 0.20

        # Discovery confidence (15% weight)
        score += discovery.confidence * 0.15

        return min(score, 1.0)  # Cap at 1.0

    async def execute_paper_trade(self, decision: TradingDecision) -> Dict[str, Any]:
        """
        Execute a trading decision in paper trading mode.

        This simulates the trade without real money.
        """
        logger.info(f"📊 Executing PAPER trade: {decision.decision_type} {decision.symbol}")

        if not self.paper_exchange:
            logger.error("Paper exchange not available - cannot execute trade")
            return {'success': False, 'error': 'no_exchange'}

        try:
            # Get current price
            ticker = await self.paper_exchange.get_ticker(decision.symbol)
            current_price = ticker.get('last_price', 0.0)

            if current_price == 0.0:
                logger.error(f"Cannot get price for {decision.symbol}")
                return {'success': False, 'error': 'no_price'}

            # Calculate position size (risk-managed)
            position_size_usdt = 100.0  # Small position for safety
            quantity = position_size_usdt / current_price

            # Apply realistic transaction costs
            entry_fee = position_size_usdt * self.config.taker_fee
            slippage_cost = position_size_usdt * (self.config.base_slippage_bps / 10000.0)
            total_cost = entry_fee + slippage_cost

            # Simulate execution
            execution_result = {
                'success': True,
                'paper_trade': True,
                'symbol': decision.symbol,
                'side': decision.decision_type,
                'quantity': quantity,
                'entry_price': current_price,
                'position_value_usdt': position_size_usdt,
                'transaction_costs_usdt': total_cost,
                'decision_confidence': decision.confidence,
                'discovery_sharpe': decision.discovery.sharpe_ratio,
                'discovery_profit': decision.discovery.profit_after_costs,
                'timestamp': datetime.now().isoformat()
            }

            logger.info(f"✅ Paper trade executed: {execution_result['symbol']} ${execution_result['position_value_usdt']:.2f}")
            logger.info(f"   Transaction costs: ${total_cost:.4f} USDT")

            # Store paper position
            self.paper_positions[decision.symbol] = {
                'entry_price': current_price,
                'quantity': quantity,
                'entry_time': datetime.now(),
                'decision': decision
            }

            # Add to decision history
            self.decision_history.append(decision)

            return execution_result

        except Exception as e:
            logger.error(f"Error executing paper trade: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}

    def get_paper_positions(self) -> Dict[str, Any]:
        """Get current paper trading positions."""
        return {
            'active_positions': len(self.paper_positions),
            'positions': {
                symbol: {
                    'entry_price': pos['entry_price'],
                    'quantity': pos['quantity'],
                    'entry_time': pos['entry_time'].isoformat()
                }
                for symbol, pos in self.paper_positions.items()
            },
            'mode': 'PAPER_TRADING_ONLY'
        }

    def get_decision_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get recent trading decisions."""
        recent_decisions = self.decision_history[-limit:]
        return [decision.to_dict() for decision in recent_decisions]

    def get_statistics(self) -> Dict[str, Any]:
        """Get trading executor statistics."""
        return {
            'total_decisions': len(self.decision_history),
            'active_positions': len(self.paper_positions),
            'mode': 'PAPER_TRADING_ONLY',
            'connector_available': CONNECTOR_AVAILABLE,
            'recent_decisions': self.get_decision_history(limit=5),
            'paper_positions': self.get_paper_positions()
        }