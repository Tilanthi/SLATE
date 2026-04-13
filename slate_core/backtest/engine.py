"""
SLATE Backtest Engine

Paper trading backtest engine for strategy validation.
NEVER executes live trades.
"""

import logging
import numpy as np
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class TradeType(Enum):
    """Trade types."""
    LONG = "long"
    SHORT = "short"
    EXIT_LONG = "exit_long"
    EXIT_SHORT = "exit_short"


@dataclass
class Trade:
    """Trade representation."""
    timestamp: datetime
    symbol: str
    trade_type: TradeType
    price: float
    size: float
    pnl: float = 0.0


@dataclass
class BacktestConfig:
    """Backtest configuration."""
    symbol: str
    timeframe: str
    start_date: str
    end_date: str
    initial_capital: float = 10000
    commission: float = 0.001  # 0.1%


@dataclass
class BacktestResult:
    """Backtest results."""
    total_return: float
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown: float
    win_rate: float
    profit_factor: float
    total_trades: int
    equity_curve: List[float] = field(default_factory=list)
    trades: List[Dict] = field(default_factory=list)


class BacktestEngine:
    """
    Paper trading backtest engine.

    Simulates strategy execution over historical data.
    NO LIVE TRADING - simulation only.
    """

    def __init__(self):
        self.capital = 10000
        self.positions: Dict[str, Dict] = {}
        self.trades: List[Trade] = []
        self.equity_curve: List[float] = []

    async def run_backtest(
        self,
        strategy_id: str,
        symbol: str,
        timeframe: str,
        start_date: str,
        end_date: str,
        initial_capital: float = 10000
    ) -> Dict:
        """
        Run backtest for a strategy.

        Simulates paper trading - NO REAL TRADES EXECUTED.
        """
        logger.info(f"[PAPER TRADING] Starting backtest for {strategy_id}")
        logger.info(f"[PAPER TRADING] Symbol: {symbol}, Period: {start_date} to {end_date}")

        # Reset state
        self.capital = initial_capital
        self.positions = {}
        self.trades = []
        self.equity_curve = [initial_capital]

        # Generate simulated price data
        candles = self._generate_candles(start_date, end_date)

        # Simulate strategy execution
        for candle in candles:
            await self._process_candle(candle, symbol)
            self.equity_curve.append(self.capital)

        # Calculate results
        result = self._calculate_results(initial_capital)

        logger.info(f"[PAPER TRADING] Backtest complete. Return: {result['total_return']:.2%}")

        return {
            "strategy_id": strategy_id,
            "symbol": symbol,
            "timeframe": timeframe,
            "period": f"{start_date} to {end_date}",
            "initial_capital": initial_capital,
            "final_capital": self.capital,
            "result": result,
            "completed_at": datetime.now().isoformat()
        }

    def _generate_candles(
        self,
        start_date: str,
        end_date: str
    ) -> List[Dict]:
        """Generate simulated candlestick data."""
        start = datetime.fromisoformat(start_date)
        end = datetime.fromisoformat(end_date)

        candles = []
        current_date = start
        base_price = 50000

        while current_date <= end:
            # Random walk price generation
            change = np.random.normal(0, 0.02)  # 2% daily volatility
            open_price = base_price * (1 + change)
            high_price = open_price * (1 + abs(np.random.normal(0, 0.01)))
            low_price = open_price * (1 - abs(np.random.normal(0, 0.01)))
            close_price = open_price * (1 + np.random.normal(0, 0.005))

            candles.append({
                "timestamp": current_date,
                "open": open_price,
                "high": high_price,
                "low": low_price,
                "close": close_price,
                "volume": np.random.uniform(100, 1000)
            })

            base_price = close_price
            current_date += timedelta(days=1)

        return candles

    async def _process_candle(self, candle: Dict, symbol: str):
        """Process a single candle (simulate strategy logic)."""
        # Simple simulated strategy
        rsi = np.random.uniform(20, 80)  # Simulated RSI

        if rsi < 30 and symbol not in self.positions:
            # Entry long signal
            size = self.capital * 0.01 / candle["close"]
            self.positions[symbol] = {
                "side": "long",
                "size": size,
                "entry_price": candle["close"],
                "timestamp": candle["timestamp"]
            }
        elif rsi > 70 and symbol in self.positions:
            # Exit signal
            await self._close_position(symbol, candle["close"], candle["timestamp"])

    async def _close_position(
        self,
        symbol: str,
        price: float,
        timestamp: datetime
    ):
        """Close a position and calculate P&L."""
        if symbol not in self.positions:
            return

        pos = self.positions[symbol]
        entry_price = pos["entry_price"]
        size = pos["size"]

        if pos["side"] == "long":
            pnl = (price - entry_price) * size
        else:
            pnl = (entry_price - price) * size

        self.capital += pnl
        self.trades.append(Trade(
            timestamp=timestamp,
            symbol=symbol,
            trade_type=TradeType.LONG,
            price=price,
            size=size,
            pnl=pnl
        ))

        del self.positions[symbol]

    def _calculate_results(self, initial_capital: float) -> Dict:
        """Calculate backtest results."""
        if not self.trades:
            return {
                "total_return": 0.0,
                "sharpe_ratio": 0.0,
                "max_drawdown": 0.0,
                "win_rate": 0.0,
                "profit_factor": 1.0,
                "total_trades": 0
            }

        # Total return
        total_return = (self.capital - initial_capital) / initial_capital

        # Win rate
        winning_trades = [t for t in self.trades if t.pnl > 0]
        losing_trades = [t for t in self.trades if t.pnl <= 0]
        win_rate = len(winning_trades) / len(self.trades) if self.trades else 0

        # Profit factor
        gross_profit = sum(t.pnl for t in winning_trades)
        gross_loss = abs(sum(t.pnl for t in losing_trades))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0

        # Max drawdown
        equity_array = np.array(self.equity_curve)
        running_max = np.maximum.accumulate(equity_array)
        drawdowns = (equity_array - running_max) / running_max
        max_drawdown = abs(min(drawdowns)) if len(drawdowns) > 0 else 0

        # Sharpe ratio (simplified)
        returns = np.diff(equity_array) / equity_array[:-1]
        sharpe = np.mean(returns) / np.std(returns) * np.sqrt(252) if np.std(returns) > 0 else 0

        return {
            "total_return": round(total_return, 4),
            "sharpe_ratio": round(sharpe, 4),
            "max_drawdown": round(max_drawdown, 4),
            "win_rate": round(win_rate, 4),
            "profit_factor": round(profit_factor, 2),
            "total_trades": len(self.trades),
            "avg_win": round(np.mean([t.pnl for t in winning_trades]), 2) if winning_trades else 0,
            "avg_loss": round(np.mean([t.pnl for t in losing_trades]), 2) if losing_trades else 0
        }
