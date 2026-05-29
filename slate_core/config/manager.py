"""
Unified Configuration Management System
Centralized configuration with validation, environment-specific configs, and runtime updates
"""

import os
import json
import logging
from typing import Any, Dict, Optional, Type, TypeVar
from dataclasses import dataclass, field
from pathlib import Path
from enum import Enum
import yaml

logger = logging.getLogger(__name__)


class Environment(Enum):
    """Deployment environments."""
    DEVELOPMENT = "development"
    TESTING = "testing"
    PRODUCTION = "production"


@dataclass
class TradingConfig:
    """Trading-related configuration."""
    default_symbol: str = "BTCUSDT"
    default_quote: str = "USDT"
    default_interval: str = "1h"

    # Volume Imbalance defaults
    vi_period_default: int = 12
    vi_threshold_default: float = 0.30

    # Capital and position sizing
    default_initial_capital_usdt: float = 10000
    default_initial_capital_btc: float = 0.5
    default_lot_size_btc: float = 0.01

    # Risk management
    max_position_size: float = 0.05
    max_portfolio_heat: float = 0.15
    stop_loss_atr_multiple: float = 2.0
    take_profit_atr_multiple: float = 3.0

    # Default stop loss and take profit percentages
    default_stop_loss_pct: float = 0.02
    default_take_profit_pct: float = 0.04
    default_trailing_stop_pct: float = 0.015

    def validate(self) -> bool:
        """Validate trading configuration."""
        if self.default_initial_capital_usdt <= 0:
            raise ValueError("Initial capital must be positive")

        if not 0 < self.max_position_size <= 1:
            raise ValueError("Max position size must be between 0 and 1")

        if not 0 < self.max_portfolio_heat <= 1:
            raise ValueError("Max portfolio heat must be between 0 and 1")

        if self.vi_period_default < 1:
            raise ValueError("VI period must be positive")

        if not 0 < self.vi_threshold_default <= 1:
            raise ValueError("VI threshold must be between 0 and 1")

        return True


@dataclass
class TransactionCostConfig:
    """Transaction cost configuration."""
    maker_fee: float = 0.0002  # 0.02%
    taker_fee: float = 0.0005  # 0.05%

    # Slippage
    base_slippage_bps: int = 10
    volatility_adjusted_slippage: bool = True

    # Fill realism
    base_fill_rate: float = 0.85
    partial_fill_probability: float = 0.15
    partial_fill_min_size: float = 0.3

    def validate(self) -> bool:
        """Validate transaction cost configuration."""
        if not 0 <= self.maker_fee <= 0.01:
            raise ValueError("Maker fee must be between 0 and 1%")

        if not 0 <= self.taker_fee <= 0.01:
            raise ValueError("Taker fee must be between 0 and 1%")

        if not 0 < self.base_fill_rate <= 1:
            raise ValueError("Base fill rate must be between 0 and 1")

        if not 0 <= self.partial_fill_probability <= 1:
            raise ValueError("Partial fill probability must be between 0 and 1")

        return True


@dataclass
class ApiConfig:
    """API configuration."""
    binance_api_base: str = "https://api.binance.com"
    binance_api_klines: str = "https://api.binance.com/api/v3/klines"
    binance_futures_api_base: str = "https://fapi.binance.com"

    # Rate limiting
    default_rate_limit: int = 1200  # requests per minute
    rate_limit_burst: int = 100

    # Timeouts
    request_timeout: float = 10.0
    connection_timeout: float = 5.0

    # Retry configuration
    max_retries: int = 3
    retry_delay: float = 1.0

    def validate(self) -> bool:
        """Validate API configuration."""
        if not self.binance_api_base.startswith('https://'):
            raise ValueError("API base must use HTTPS")

        if self.request_timeout <= 0:
            raise ValueError("Request timeout must be positive")

        if self.max_retries < 0:
            raise ValueError("Max retries must be non-negative")

        return True


@dataclass
class DataConfig:
    """Data configuration."""
    default_cache_dir: str = "sol_data_cache"
    default_cache_file_pattern: str = "{symbol}_{interval}_{period}.csv"
    cache_enabled: bool = True
    cache_ttl_hours: int = 24

    # Data validation
    validate_data: bool = True
    min_data_points: int = 100
    max_data_gap_hours: int = 24

    def validate(self) -> bool:
        """Validate data configuration."""
        if self.cache_ttl_hours <= 0:
            raise ValueError("Cache TTL must be positive")

        if self.min_data_points < 1:
            raise ValueError("Minimum data points must be positive")

        return True


@dataclass
class BacktestConfig:
    """Backtest configuration."""
    default_output_dir: str = "backtest_results"
    default_chart_format: str = "png"
    default_chart_dpi: int = 150

    # Parallel execution
    max_parallel_backtests: int = 4
    backtest_timeout_minutes: int = 30

    # Results storage
    save_detailed_results: bool = True
    save_trade_log: bool = True
    save_equity_curve: bool = True

    def validate(self) -> bool:
        """Validate backtest configuration."""
        if self.max_parallel_backtests < 1:
            raise ValueError("Max parallel backtests must be at least 1")

        if self.backtest_timeout_minutes <= 0:
            raise ValueError("Backtest timeout must be positive")

        return True


@dataclass
class LoggingConfig:
    """Logging configuration."""
    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    file_enabled: bool = True
    file_path: str = "slate.log"
    max_bytes: int = 10485760  # 10MB
    backup_count: int = 5

    # Console logging
    console_enabled: bool = True
    console_level: str = "INFO"

    def validate(self) -> bool:
        """Validate logging configuration."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if self.level not in valid_levels:
            raise ValueError(f"Invalid log level: {self.level}")

        if self.console_level not in valid_levels:
            raise ValueError(f"Invalid console log level: {self.console_level}")

        return True


@dataclass
class OrchestrationConfig:
    """Orchestration configuration."""
    event_bus_enabled: bool = True
    event_bus_max_queue_size: int = 10000
    service_mesh_enabled: bool = True
    health_check_interval: float = 10.0

    # Circuit breaker
    circuit_breaker_threshold: float = 0.5
    circuit_breaker_timeout: float = 60.0

    # Graceful degradation
    fallback_enabled: bool = True
    max_retry_attempts: int = 3
    retry_backoff_base: float = 2.0

    def validate(self) -> bool:
        """Validate orchestration configuration."""
        if not 0 <= self.circuit_breaker_threshold <= 1:
            raise ValueError("Circuit breaker threshold must be between 0 and 1")

        if self.health_check_interval <= 0:
            raise ValueError("Health check interval must be positive")

        return True


@dataclass
class SystemConfig:
    """Complete system configuration."""
    environment: Environment = Environment.DEVELOPMENT
    trading: TradingConfig = field(default_factory=TradingConfig)
    transaction_costs: TransactionCostConfig = field(default_factory=TransactionCostConfig)
    api: ApiConfig = field(default_factory=ApiConfig)
    data: DataConfig = field(default_factory=DataConfig)
    backtest: BacktestConfig = field(default_factory=BacktestConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    orchestration: OrchestrationConfig = field(default_factory=OrchestrationConfig)

    # Metadata
    version: str = "1.0.0"
    config_version: int = 1

    def validate(self) -> bool:
        """Validate all configuration sections."""
        self.trading.validate()
        self.transaction_costs.validate()
        self.api.validate()
        self.data.validate()
        self.backtest.validate()
        self.logging.validate()
        self.orchestration.validate()
        return True

    def to_dict(self) -> Dict:
        """Convert configuration to dictionary."""
        return {
            'environment': self.environment.value,
            'version': self.version,
            'config_version': self.config_version,
            'trading': {
                'default_symbol': self.trading.default_symbol,
                'default_interval': self.trading.default_interval,
                'vi_period_default': self.trading.vi_period_default,
                'vi_threshold_default': self.trading.vi_threshold_default,
                'default_initial_capital_usdt': self.trading.default_initial_capital_usdt,
                'max_position_size': self.trading.max_position_size,
                'max_portfolio_heat': self.trading.max_portfolio_heat,
            },
            'transaction_costs': {
                'maker_fee': self.transaction_costs.maker_fee,
                'taker_fee': self.transaction_costs.taker_fee,
                'base_slippage_bps': self.transaction_costs.base_slippage_bps,
                'base_fill_rate': self.transaction_costs.base_fill_rate,
            },
            'api': {
                'binance_api_base': self.api.binance_api_base,
                'request_timeout': self.api.request_timeout,
                'max_retries': self.api.max_retries,
            },
            'data': {
                'cache_enabled': self.data.cache_enabled,
                'cache_ttl_hours': self.data.cache_ttl_hours,
                'validate_data': self.data.validate_data,
            },
            'backtest': {
                'max_parallel_backtests': self.backtest.max_parallel_backtests,
                'save_detailed_results': self.backtest.save_detailed_results,
            },
            'orchestration': {
                'event_bus_enabled': self.orchestration.event_bus_enabled,
                'service_mesh_enabled': self.orchestration.service_mesh_enabled,
                'fallback_enabled': self.orchestration.fallback_enabled,
            }
        }


class ConfigManager:
    """
    Unified configuration manager.

    Features:
    - Load from multiple sources (file, environment, defaults)
    - Configuration validation
    - Runtime updates
    - Environment-specific overrides
    """

    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or Path("slate_config.yaml")
        self.config: Optional[SystemConfig] = None
        self._watchers: List[Callable] = []

    def load_config(
        self,
        environment: Optional[Environment] = None,
        config_file: Optional[Path] = None
    ) -> SystemConfig:
        """
        Load configuration from multiple sources.

        Priority:
        1. Environment variables
        2. Config file
        3. Default values

        Parameters:
        - environment: Deployment environment
        - config_file: Path to config file

        Returns:
        - Loaded and validated configuration
        """
        # Start with defaults
        config_dict = {}

        # Load from file if exists
        config_file = config_file or self.config_path
        if config_file.exists():
            try:
                with open(config_file, 'r') as f:
                    file_config = yaml.safe_load(f)
                    config_dict.update(file_config)
                logger.info(f"Loaded configuration from {config_file}")
            except Exception as e:
                logger.warning(f"Failed to load config file: {e}")

        # Override with environment-specific config
        if environment:
            env_config_file = config_file.parent / f"slate_config.{environment.value}.yaml"
            if env_config_file.exists():
                try:
                    with open(env_config_file, 'r') as f:
                        env_config = yaml.safe_load(f)
                        self._deep_update(config_dict, env_config)
                    logger.info(f"Loaded environment config from {env_config_file}")
                except Exception as e:
                    logger.warning(f"Failed to load environment config: {e}")

        # Override with environment variables
        env_overrides = self._load_env_overrides()
        if env_overrides:
            self._deep_update(config_dict, env_overrides)
            logger.info("Applied environment variable overrides")

        # Create config object
        self.config = self._dict_to_config(config_dict)

        # Validate
        try:
            self.config.validate()
            logger.info("Configuration validated successfully")
        except ValueError as e:
            logger.error(f"Configuration validation failed: {e}")
            raise

        return self.config

    def save_config(self, config_path: Optional[Path] = None) -> bool:
        """
        Save current configuration to file.

        Parameters:
        - config_path: Path to save config

        Returns:
        - True if saved successfully
        """
        if self.config is None:
            logger.error("No configuration to save")
            return False

        config_path = config_path or self.config_path

        try:
            with open(config_path, 'w') as f:
                yaml.dump(self.config.to_dict(), f, default_flow_style=False)
            logger.info(f"Saved configuration to {config_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to save configuration: {e}")
            return False

    def update_config(self, updates: Dict, notify: bool = True) -> bool:
        """
        Update configuration at runtime.

        Parameters:
        - updates: Configuration updates
        - notify: Notify watchers of changes

        Returns:
        - True if updated successfully
        """
        if self.config is None:
            logger.error("No configuration loaded")
            return False

        try:
            # Apply updates
            config_dict = self.config.to_dict()
            self._deep_update(config_dict, updates)

            # Recreate config object
            self.config = self._dict_to_config(config_dict)
            self.config.validate()

            logger.info("Configuration updated successfully")

            # Notify watchers
            if notify:
                for watcher in self._watchers:
                    try:
                        watcher(self.config)
                    except Exception as e:
                        logger.error(f"Config watcher error: {e}")

            return True
        except Exception as e:
            logger.error(f"Failed to update configuration: {e}")
            return False

    def watch_config(self, watcher: Callable[[SystemConfig], None]):
        """Register a configuration watcher."""
        self._watchers.append(watcher)

    def get_config(self) -> SystemConfig:
        """Get current configuration."""
        if self.config is None:
            self.config = self.load_config()
        return self.config

    def _load_env_overrides(self) -> Dict:
        """Load configuration overrides from environment variables."""
        overrides = {}

        # Trading overrides
        if 'SLATE_SYMBOL' in os.environ:
            overrides.setdefault('trading', {})['default_symbol'] = os.environ['SLATE_SYMBOL']

        if 'SLATE_INITIAL_CAPITAL' in os.environ:
            overrides.setdefault('trading', {})['default_initial_capital_usdt'] = float(os.environ['SLATE_INITIAL_CAPITAL'])

        # API overrides
        if 'SLATE_API_KEY' in os.environ:
            overrides.setdefault('api', {})['api_key'] = os.environ['SLATE_API_KEY']

        if 'SLATE_API_SECRET' in os.environ:
            overrides.setdefault('api', {})['api_secret'] = os.environ['SLATE_API_SECRET']

        # Logging overrides
        if 'SLATE_LOG_LEVEL' in os.environ:
            overrides.setdefault('logging', {})['level'] = os.environ['SLATE_LOG_LEVEL']

        return overrides

    def _dict_to_config(self, config_dict: Dict) -> SystemConfig:
        """Convert dictionary to configuration object."""
        trading_config = config_dict.get('trading', {})
        costs_config = config_dict.get('transaction_costs', {})
        api_config = config_dict.get('api', {})
        data_config = config_dict.get('data', {})
        backtest_config = config_dict.get('backtest', {})
        logging_config = config_dict.get('logging', {})
        orchestration_config = config_dict.get('orchestration', {})

        return SystemConfig(
            environment=Environment(config_dict.get('environment', 'development')),
            trading=TradingConfig(**trading_config),
            transaction_costs=TransactionCostConfig(**costs_config),
            api=ApiConfig(**api_config),
            data=DataConfig(**data_config),
            backtest=BacktestConfig(**backtest_config),
            logging=LoggingConfig(**logging_config),
            orchestration=OrchestrationConfig(**orchestration_config),
            version=config_dict.get('version', '1.0.0'),
            config_version=config_dict.get('config_version', 1)
        )

    def _deep_update(self, base_dict: Dict, updates: Dict):
        """Deep update dictionary."""
        for key, value in updates.items():
            if isinstance(value, dict) and key in base_dict and isinstance(base_dict[key], dict):
                self._deep_update(base_dict[key], value)
            else:
                base_dict[key] = value


# Global config manager instance
_global_config_manager: Optional[ConfigManager] = None


def get_config_manager() -> ConfigManager:
    """Get the global configuration manager instance."""
    global _global_config_manager
    if _global_config_manager is None:
        _global_config_manager = ConfigManager()
    return _global_config_manager


def get_config() -> SystemConfig:
    """Get the current system configuration."""
    return get_config_manager().get_config()


# Backward compatibility - export constants from existing constants.py
from .constants import *
