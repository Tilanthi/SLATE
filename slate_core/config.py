"""
Configuration Module for SLATE

Provides configuration management for the SLATE trading platform.
"""

import os
from pathlib import Path
from typing import Dict, Any
from dataclasses import dataclass


@dataclass
class SlateConfig:
    """SLATE configuration."""

    # Server settings
    host: str = "0.0.0.0"
    port: int = 8788
    debug: bool = False

    # Exchange settings
    binance_api_key: str = ""
    binance_api_secret: str = ""
    binance_testnet: bool = False

    bitget_api_key: str = ""
    bitget_api_secret: str = ""
    bitget_passphrase: str = ""
    bitget_testnet: bool = False

    # Database settings
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "slate_trading"
    postgres_user: str = "slate_user"
    postgres_password: str = ""

    # Redis settings
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_password: str = ""
    redis_db: int = 0

    # Trading settings
    trading_mode: str = "paper"  # paper, live_small, live_full
    max_position_size: float = 0.1  # 10% of portfolio
    max_daily_loss_pct: float = 2.0

    # Risk management
    kelly_fraction: float = 0.25
    max_gross_exposure: float = 3.0
    max_net_exposure: float = 1.0

    # Discovery settings
    discovery_enabled: bool = True
    discovery_interval_seconds: int = 3600
    min_confidence: float = 0.7
    min_sharpe: float = 0.5
    min_win_rate: float = 0.55

    # GraphPalace settings
    graphpalace_enabled: bool = False
    graphpalace_path: str = "./palace_data"


# Global config instance
_config: SlateConfig = None


def load_config() -> SlateConfig:
    """Load configuration from environment variables."""
    global _config

    if _config is not None:
        return _config

    _config = SlateConfig(
        # Server
        host=os.getenv("SLATE_HOST", "0.0.0.0"),
        port=int(os.getenv("SLATE_PORT", "8788")),
        debug=os.getenv("SLATE_ENV", "development") == "development",

        # Exchanges
        binance_api_key=os.getenv("BINANCE_API_KEY", ""),
        binance_api_secret=os.getenv("BINANCE_API_SECRET", ""),
        binance_testnet=os.getenv("BINANCE_TESTNET", "false").lower() == "true",

        bitget_api_key=os.getenv("BITGET_API_KEY", ""),
        bitget_api_secret=os.getenv("BITGET_API_SECRET", ""),
        bitget_passphrase=os.getenv("BITGET_PASSPHRASE", ""),
        bitget_testnet=os.getenv("BITGET_TESTNET", "false").lower() == "true",

        # Database
        postgres_host=os.getenv("POSTGRES_HOST", "localhost"),
        postgres_port=int(os.getenv("POSTGRES_PORT", "5432")),
        postgres_db=os.getenv("POSTGRES_DB", "slate_trading"),
        postgres_user=os.getenv("POSTGRES_USER", "slate_user"),
        postgres_password=os.getenv("POSTGRES_PASSWORD", ""),

        # Redis
        redis_host=os.getenv("REDIS_HOST", "localhost"),
        redis_port=int(os.getenv("REDIS_PORT", "6379")),
        redis_password=os.getenv("REDIS_PASSWORD", ""),
        redis_db=int(os.getenv("REDIS_DB", "0")),

        # Trading
        trading_mode=os.getenv("SLATE_TRADING_MODE", "paper"),
        max_position_size=float(os.getenv("POSITION_MAX_PCT", "0.1")),
        max_daily_loss_pct=float(os.getenv("RISK_MAX_DAILY_LOSS_PCT", "2.0")),

        # Risk
        kelly_fraction=float(os.getenv("POSITION_KELLY_FRACTION", "0.25")),
        max_gross_exposure=float(os.getenv("RISK_MAX_GROSS_EXPOSURE", "3.0")),
        max_net_exposure=float(os.getenv("RISK_MAX_NET_EXPOSURE", "1.0")),

        # Discovery
        discovery_enabled=os.getenv("DISCOVERY_ENABLED", "true").lower() == "true",
        discovery_interval_seconds=int(os.getenv("DISCOVERY_INTERVAL_SECONDS", "3600")),
        min_confidence=float(os.getenv("DISCOVERY_MIN_CONFIDENCE", "0.7")),
        min_sharpe=float(os.getenv("DISCOVERY_MIN_SHARPE", "0.5")),
        min_win_rate=float(os.getenv("DISCOVERY_MIN_WIN_RATE", "0.55")),

        # GraphPalace
        graphpalace_enabled=os.getenv("GRAPHPALACE_ENABLED", "false").lower() == "true",
        graphpalace_path=os.getenv("GRAPHPALACE_PATH", "./palace_data"),
    )

    return _config


def get_config() -> SlateConfig:
    """Get the current configuration instance."""
    if _config is None:
        return load_config()
    return _config


def reload_config() -> SlateConfig:
    """Reload configuration from environment variables."""
    global _config
    _config = None
    return load_config()
