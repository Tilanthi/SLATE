"""
Database Schema and Models

TimescaleDB/PostgreSQL schema for SLATE data storage.
"""

from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from decimal import Decimal
import asyncio
import logging

from sqlalchemy import (
    create_engine,
    Column,
    String,
    Float,
    Integer,
    BigInteger,
    DateTime,
    Boolean,
    Index,
    UniqueConstraint,
    Text,
)
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base, DeclarativeBase, Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID, JSONB
import uuid

logger = logging.getLogger(__name__)


# Base class for async models
class Base(DeclarativeBase):
    """Base class for all database models."""
    pass


class MarketDataMixin:
    """Mixin for market data tables."""
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    exchange: Mapped[str] = mapped_column(String(50), index=True)
    symbol: Mapped[str] = mapped_column(String(50), index=True)


# ========================================================================
# MARKET DATA TABLES
# ========================================================================

class Ticker(Base):
    """
    Ticker data table.
    Stores current ticker information.
    """
    __tablename__ = "tickers"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    exchange: Mapped[str] = mapped_column(String(50), index=True)
    symbol: Mapped[str] = mapped_column(String(50), index=True)

    # Price data
    last_price: Mapped[float] = mapped_column(Float)
    bid_price: Mapped[float] = mapped_column(Float)
    ask_price: Mapped[float] = mapped_column(Float)
    bid_size: Mapped[float] = mapped_column(Float)
    ask_size: Mapped[float] = mapped_column(Float)

    # Statistics
    volume_24h: Mapped[float] = mapped_column(Float)
    change_24h: Mapped[float] = mapped_column(Float)
    change_pct_24h: Mapped[float] = mapped_column(Float)
    high_24h: Mapped[float] = mapped_column(Float)
    low_24h: Mapped[float] = mapped_column(Float)

    # Derivatives data
    open_interest: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    funding_rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    mark_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    index_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Metadata
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )

    __table_args__ = (
        Index("ix_tickers_timestamp_symbol", "timestamp", "symbol"),
        Index("ix_tickers_exchange_symbol", "exchange", "symbol"),
    )


class Candle(Base):
    """
    OHLCV candle data table.
    Uses TimescaleDB hypertable optimization.
    """
    __tablename__ = "candles"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    exchange: Mapped[str] = mapped_column(String(50), index=True)
    symbol: Mapped[str] = mapped_column(String(50), index=True)
    timeframe: Mapped[str] = mapped_column(String(10), index=True)

    # OHLCV data
    open: Mapped[float] = mapped_column(Float)
    high: Mapped[float] = mapped_column(Float)
    low: Mapped[float] = mapped_column(Float)
    close: Mapped[float] = mapped_column(Float)
    volume: Mapped[float] = mapped_column(Float)

    # Additional data
    vwap: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    trades_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Metadata
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )

    __table_args__ = (
        UniqueConstraint("timestamp", "exchange", "symbol", "timeframe", name="uix_candle_unique"),
        Index("ix_candles_timestamp_symbol_tf", "timestamp", "symbol", "timeframe"),
    )


class Trade(Base):
    """
    Trade data table.
    Stores individual trades.
    """
    __tablename__ = "trades"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    exchange: Mapped[str] = mapped_column(String(50), index=True)
    symbol: Mapped[str] = mapped_column(String(50), index=True)

    # Trade data
    trade_id: Mapped[str] = mapped_column(String(100), index=True)
    price: Mapped[float] = mapped_column(Float)
    size: Mapped[float] = mapped_column(Float)
    side: Mapped[str] = mapped_column(String(10))  # 'buy' or 'sell'

    # Metadata
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )

    __table_args__ = (
        UniqueConstraint("exchange", "trade_id", name="uix_trade_unique"),
        Index("ix_trades_timestamp_symbol", "timestamp", "symbol"),
    )


class OrderBookSnapshot(Base):
    """
    Order book snapshot table.
    Stores full order book snapshots at intervals.
    """
    __tablename__ = "orderbook_snapshots"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    exchange: Mapped[str] = mapped_column(String(50), index=True)
    symbol: Mapped[str] = mapped_column(String(50), index=True)

    # Order book data (stored as JSONB)
    bids: Mapped[Dict[str, Any]] = mapped_column(JSONB)
    asks: Mapped[Dict[str, Any]] = mapped_column(JSONB)

    # Snapshot metadata
    depth: Mapped[int] = mapped_column(Integer)  # Number of levels
    spread: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    spread_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    mid_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Metadata
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )

    __table_args__ = (
        Index("ix_orderbook_timestamp_symbol", "timestamp", "symbol"),
    )


# ========================================================================
# TRADING TABLES (PAPER TRADING)
# ========================================================================

class PaperOrder(Base):
    """
    Paper trading orders table.
    """
    __tablename__ = "paper_orders"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )

    # Order identifiers
    order_id: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    client_order_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    strategy_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)

    # Order details
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    exchange: Mapped[str] = mapped_column(String(50))
    symbol: Mapped[str] = mapped_column(String(50), index=True)
    side: Mapped[str] = mapped_column(String(10))  # 'buy' or 'sell'
    order_type: Mapped[str] = mapped_column(String(20))  # 'market', 'limit', etc.

    # Price and quantity
    price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    stop_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    quantity: Mapped[float] = mapped_column(Float)
    filled_quantity: Mapped[float] = mapped_column(Float, default=0.0)
    remaining_quantity: Mapped[float] = mapped_column(Float)

    # Execution
    average_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(20), index=True)  # 'pending', 'open', 'filled', etc.

    # Fees
    fee: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    fee_currency: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    # Metadata
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )


class PaperPosition(Base):
    """
    Paper trading positions table.
    """
    __tablename__ = "paper_positions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    # Position identifiers
    strategy_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)

    # Position details
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    exchange: Mapped[str] = mapped_column(String(50))
    symbol: Mapped[str] = mapped_column(String(50), index=True)
    position_side: Mapped[str] = mapped_column(String(10))  # 'long' or 'short'

    # Size and price
    size: Mapped[float] = mapped_column(Float)  # Positive for long, negative for short
    entry_price: Mapped[float] = mapped_column(Float)
    mark_price: Mapped[float] = mapped_column(Float)

    # P&L
    unrealized_pnl: Mapped[float] = mapped_column(Float, default=0.0)
    realized_pnl: Mapped[float] = mapped_column(Float, default=0.0)

    # Risk
    leverage: Mapped[float] = mapped_column(Float)
    margin_type: Mapped[str] = mapped_column(String(20))  # 'cross' or 'isolated'
    liquidation_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Metadata
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )

    __table_args__ = (
        Index("ix_paper_positions_symbol", "symbol"),
        Index("ix_paper_positions_strategy", "strategy_id", "symbol"),
    )


class PaperBalance(Base):
    """
    Paper trading account balance table.
    """
    __tablename__ = "paper_balances"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)

    # Balance details
    exchange: Mapped[str] = mapped_column(String(50))
    currency: Mapped[str] = mapped_column(String(20), index=True)
    total_balance: Mapped[float] = mapped_column(Float)
    available_balance: Mapped[float] = mapped_column(Float)
    used_balance: Mapped[float] = mapped_column(Float)
    unrealized_pnl: Mapped[float] = mapped_column(Float, default=0.0)

    # Metadata
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )


class PaperTrade(Base):
    """
    Paper trading trade history table.
    """
    __tablename__ = "paper_trades"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    # Trade identifiers
    trade_id: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    order_id: Mapped[str] = mapped_column(String(100), index=True)
    strategy_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)

    # Trade details
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    exchange: Mapped[str] = mapped_column(String(50))
    symbol: Mapped[str] = mapped_column(String(50), index=True)
    side: Mapped[str] = mapped_column(String(10))
    price: Mapped[float] = mapped_column(Float)
    quantity: Mapped[float] = mapped_column(Float)

    # Execution
    fee: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    fee_currency: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    # P&L
    realized_pnl: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Metadata
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )


# ========================================================================
# STRATEGY TABLES
# ========================================================================

class Strategy(Base):
    """
    Strategy definitions table.
    """
    __tablename__ = "strategies"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )

    # Strategy identifiers
    strategy_id: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Strategy type
    strategy_type: Mapped[str] = mapped_column(String(50), index=True)  # 'trend_following', etc.
    subtype: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Status
    phase: Mapped[str] = mapped_column(String(50), index=True)  # 'idea', 'backtest', 'paper', 'live'
    status: Mapped[str] = mapped_column(String(20), index=True)  # 'active', 'paused', 'retired'

    # Parameters
    parameters: Mapped[Dict[str, Any]] = mapped_column(JSONB, default={})

    # Performance metrics
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    sharpe_ratio: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    max_drawdown: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    win_rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    profit_factor: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Backtest results
    backtest_start: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    backtest_end: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    backtest_trades: Mapped[int] = mapped_column(Integer, default=0)
    backtest_return: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Metadata
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )


class BacktestResult(Base):
    """
    Backtest results table.
    """
    __tablename__ = "backtest_results"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    # Identifiers
    strategy_id: Mapped[str] = mapped_column(String(100), index=True)
    backtest_id: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    symbol: Mapped[str] = mapped_column(String(50))
    exchange: Mapped[str] = mapped_column(String(50))

    # Backtest parameters
    start_date: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    end_date: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    initial_capital: Mapped[float] = mapped_column(Float)

    # Results
    final_capital: Mapped[float] = mapped_column(Float)
    total_return: Mapped[float] = mapped_column(Float)
    cagr: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    sharpe_ratio: Mapped[float] = mapped_column(Float)
    sortino_ratio: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    max_drawdown: Mapped[float] = mapped_column(Float)
    win_rate: Mapped[float] = mapped_column(Float)
    profit_factor: Mapped[float] = mapped_column(Float)

    # Trade statistics
    total_trades: Mapped[int] = mapped_column(Integer)
    winning_trades: Mapped[int] = mapped_column(Integer)
    losing_trades: Mapped[int] = mapped_column(Integer)
    avg_trade: Mapped[float] = mapped_column(Float)
    avg_win: Mapped[float] = mapped_column(Float)
    avg_loss: Mapped[float] = mapped_column(Float)
    largest_win: Mapped[float] = mapped_column(Float)
    largest_loss: Mapped[float] = mapped_column(Float)

    # Parameters used
    parameters: Mapped[Dict[str, Any]] = mapped_column(JSONB)

    # Metadata
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )


# ========================================================================
# RISK MANAGEMENT TABLES
# ========================================================================

class RiskState(Base):
    """
    Risk state history table.
    """
    __tablename__ = "risk_states"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)

    # Risk state
    state: Mapped[str] = mapped_column(String(20), index=True)  # 'nominal', 'elevated', etc.
    previous_state: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    # Risk metrics
    portfolio_value: Mapped[float] = mapped_column(Float)
    gross_exposure: Mapped[float] = mapped_column(Float)
    net_exposure: Mapped[float] = mapped_column(Float)
    max_drawdown: Mapped[float] = mapped_column(Float)
    daily_loss_pct: Mapped[float] = mapped_column(Float)

    # Trigger
    trigger_reason: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Metadata
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )


class CircuitBreakerEvent(Base):
    """
    Circuit breaker events table.
    """
    __tablename__ = "circuit_breaker_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)

    # Event details
    breaker_type: Mapped[str] = mapped_column(String(50), index=True)  # 'daily_loss', 'drawdown', etc.
    triggered: Mapped[bool] = mapped_column(Boolean, index=True)
    threshold: Mapped[float] = mapped_column(Float)
    current_value: Mapped[float] = mapped_column(Float)

    # Action taken
    action: Mapped[str] = mapped_column(String(50))  # 'pause_trading', 'reduce_exposure', etc.
    action_details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Resolution
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    resolution_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Metadata
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )


# ========================================================================
# ANALYTICS TABLES
# ========================================================================

class PortfolioSnapshot(Base):
    """
    Portfolio snapshot table for analytics.
    """
    __tablename__ = "portfolio_snapshots"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)

    # Portfolio value
    total_value: Mapped[float] = mapped_column(Float)
    cash_balance: Mapped[float] = mapped_column(Float)
    positions_value: Mapped[float] = mapped_column(Float)
    unrealized_pnl: Mapped[float] = mapped_column(Float)

    # Exposure
    gross_exposure: Mapped[float] = mapped_column(Float)
    net_exposure: Mapped[float] = mapped_column(Float)
    long_exposure: Mapped[float] = mapped_column(Float)
    short_exposure: Mapped[float] = mapped_column(Float)

    # Risk metrics
    max_drawdown: Mapped[float] = mapped_column(Float)
    daily_return: Mapped[float] = mapped_column(Float)

    # Positions count
    total_positions: Mapped[int] = mapped_column(Integer)
    long_positions: Mapped[int] = mapped_column(Integer)
    short_positions: Mapped[int] = mapped_column(Integer)

    # Metadata
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )


class SignalEvent(Base):
    """
    Signal events table.
    """
    __tablename__ = "signal_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)

    # Signal details
    signal_type: Mapped[str] = mapped_column(String(50), index=True)  # 'statistical', 'causal', etc.
    symbol: Mapped[str] = mapped_column(String(50), index=True)
    exchange: Mapped[str] = mapped_column(String(50))

    # Signal data
    signal_value: Mapped[float] = mapped_column(Float)
    confidence: Mapped[float] = mapped_column(Float)
    direction: Mapped[str] = mapped_column(String(10))  # 'long', 'short', 'neutral'

    # Source
    source_strategy: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    parameters: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)

    # Metadata
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )


# ========================================================================
# DATABASE MANAGER
# ========================================================================

class DatabaseManager:
    """
    Database manager for SLATE.
    """

    def __init__(self, database_url: str):
        """
        Initialize database manager.

        Args:
            database_url: Database connection URL
        """
        self.database_url = database_url
        self.engine = None
        self.session_factory = None

    async def connect(self) -> None:
        """Connect to database."""
        self.engine = create_async_engine(
            self.database_url,
            echo=False,
            pool_size=20,
            max_overflow=10,
        )

        self.session_factory = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

        logger.info("Connected to database")

    async def disconnect(self) -> None:
        """Disconnect from database."""
        if self.engine:
            await self.engine.dispose()
            logger.info("Disconnected from database")

    async def create_tables(self) -> None:
        """Create all tables."""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Created database tables")

    async def drop_tables(self) -> None:
        """Drop all tables (use with caution)."""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        logger.warning("Dropped database tables")

    def get_session(self) -> AsyncSession:
        """
        Get a database session.

        Returns:
            AsyncSession
        """
        return self.session_factory()

    async def create_hypertables(self) -> None:
        """
        Create TimescaleDB hypertables for time-series data.
        """
        async with self.engine.begin() as conn:
            # Create hypertables for time-series tables
            time_series_tables = [
                "candles",
                "trades",
                "tickers",
                "portfolio_snapshots",
                "risk_states",
            ]

            for table in time_series_tables:
                try:
                    await conn.execute(
                        f"SELECT create_hypertable('{table}', 'timestamp', if_not_exists => TRUE);"
                    )
                except Exception as e:
                    logger.warning(f"Failed to create hypertable for {table}: {e}")

        logger.info("Created TimescaleDB hypertables")
