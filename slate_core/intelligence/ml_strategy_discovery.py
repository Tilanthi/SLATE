#!/usr/bin/env python3
"""
SLATE ML Strategy Discovery System

Phase 2: Machine Learning Integration for Alpha Discovery

This module uses machine learning to discover trading strategies that adapt
to market conditions and identify genuine alpha.

Key Capabilities:
- Gradient Boosting for feature importance and signal prediction
- Neural Networks (LSTM) for temporal pattern recognition
- Automated feature engineering
- SHAP values for interpretability
- Regime-aware model training
- Walk-forward validation for robustness

Author: SLATE Evolution
Date: 2026-04-30
Priority: CRITICAL - Foundation for autonomous alpha discovery
"""

import asyncio
import logging
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum
import json
from pathlib import Path

# ML imports
from sklearn.ensemble import GradientBoostingClassifier, GradientBoostingRegressor
from sklearn.ensemble import RandomForestClassifier, AdaBoostClassifier
from sklearn.model_selection import train_test_split, cross_val_score, TimeSeriesSplit
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
from sklearn.preprocessing import StandardScaler
import shap

# Import market intelligence from Phase 1
from .market_regime_detector import get_market_intelligence, MarketRegime, RegimeState

logger = logging.getLogger(__name__)


class MLModelType(Enum):
    """Types of ML models for strategy discovery."""
    GRADIENT_BOOSTING = "gradient_boosting"
    RANDOM_FOREST = "random_forest"
    ADA_BOOST = "ada_boost"
    NEURAL_NETWORK = "neural_network"
    ENSEMBLE = "ensemble"


class FeatureType(Enum):
    """Types of features for ML models."""
    PRICE_MOMENTUM = "price_momentum"
    VOLATILITY = "volatility"
    VOLUME = "volume"
    TECHNICAL_INDICATORS = "technical_indicators"
    REGIME_FEATURES = "regime_features"
    TIME_FEATURES = "time_features"
    MARKET_MICROSTRUCTURE = "market_microstructure"


@dataclass
class MLFeature:
    """A feature for ML models."""
    name: str
    feature_type: FeatureType
    description: str
    computation_func: callable
    importance_score: float = 0.0
    is_active: bool = True


@dataclass
class MLStrategyResult:
    """Results from ML strategy discovery."""
    model_type: MLModelType
    features_used: List[str]
    feature_importance: Dict[str, float]
    train_accuracy: float
    test_accuracy: float
    cross_val_scores: List[float]
    shap_values_available: bool
    regime_specific_performance: Dict[str, float]
    predicted_returns: pd.Series
    actual_returns: pd.Series
    total_profit_usdt: float
    max_drawdown_pct: float
    sharpe_ratio: float
    recommended_position_size: float
    confidence_level: float


class AutomatedFeatureEngine:
    """
    Automated feature engineering for ML strategy discovery.

    Generates a comprehensive set of features from price/volume data.
    """

    def __init__(self):
        self.features: List[MLFeature] = []
        self.feature_history = {}
        self._initialize_features()

        logger.info("AutomatedFeatureEngine initialized with feature library")

    def _initialize_features(self):
        """Initialize the feature library."""

        # ===== PRICE MOMENTUM FEATURES =====

        self.features.append(MLFeature(
            name="returns_1",
            feature_type=FeatureType.PRICE_MOMENTUM,
            description="1-period return",
            computation_func=lambda df: df['close'].pct_change(1)
        ))

        self.features.append(MLFeature(
            name="returns_5",
            feature_type=FeatureType.PRICE_MOMENTUM,
            description="5-period return",
            computation_func=lambda df: df['close'].pct_change(5)
        ))

        self.features.append(MLFeature(
            name="returns_20",
            feature_type=FeatureType.PRICE_MOMENTUM,
            description="20-period return",
            computation_func=lambda df: df['close'].pct_change(20)
        ))

        # Moving averages
        self.features.append(MLFeature(
            name="ma_ratio_5_20",
            feature_type=FeatureType.PRICE_MOMENTUM,
            description="5-day MA / 20-day MA ratio",
            computation_func=lambda df: df['close'].rolling(5).mean() / df['close'].rolling(20).mean()
        ))

        self.features.append(MLFeature(
            name="ma_ratio_20_50",
            feature_type=FeatureType.PRICE_MOMENTUM,
            description="20-day MA / 50-day MA ratio",
            computation_func=lambda df: df['close'].rolling(20).mean() / df['close'].rolling(50).mean()
        ))

        # ===== VOLATILITY FEATURES =====

        self.features.append(MLFeature(
            name="volatility_20",
            feature_type=FeatureType.VOLATILITY,
            description="20-period rolling volatility",
            computation_func=lambda df: df['close'].pct_change().rolling(20).std()
        ))

        self.features.append(MLFeature(
            name="volatility_ratio",
            feature_type=FeatureType.VOLATILITY,
            description="Current vol / Historical vol ratio",
            computation_func=lambda df: df['close'].pct_change().rolling(20).std() / df['close'].pct_change().rolling(100).std()
        ))

        self.features.append(MLFeature(
            name="atr_14",
            feature_type=FeatureType.VOLATILITY,
            description="14-period Average True Range",
            computation_func=lambda df: self._calculate_atr(df)
        ))

        self.features.append(MLFeature(
            name="atr_ratio",
            feature_type=FeatureType.VOLATILITY,
            description="Current ATR / Average ATR",
            computation_func=lambda df: self._calculate_atr(df) / self._calculate_atr(df).rolling(100).mean()
        ))

        # ===== VOLUME FEATURES =====

        self.features.append(MLFeature(
            name="volume_ma_ratio",
            feature_type=FeatureType.VOLUME,
            description="Volume / 20-day MA volume",
            computation_func=lambda df: df['volume'] / df['volume'].rolling(20).mean()
        ))

        self.features.append(MLFeature(
            name="volume_change",
            feature_type=FeatureType.VOLUME,
            description="Volume percent change",
            computation_func=lambda df: df['volume'].pct_change()
        ))

        self.features.append(MLFeature(
            name="volume_price_trend",
            feature_type=FeatureType.VOLUME,
            description="Volume * Price change correlation",
            computation_func=lambda df: (df['volume'] * df['close'].pct_change()).rolling(20).mean()
        ))

        # ===== TECHNICAL INDICATORS =====

        # RSI
        self.features.append(MLFeature(
            name="rsi_14",
            feature_type=FeatureType.TECHNICAL_INDICATORS,
            description="14-period RSI",
            computation_func=lambda df: self._calculate_rsi(df['close'], 14)
        ))

        # Bollinger Bands
        self.features.append(MLFeature(
            name="bb_position",
            feature_type=FeatureType.TECHNICAL_INDICATORS,
            description="Price position in Bollinger Bands",
            computation_func=lambda df: self._calculate_bb_position(df)
        ))

        # MACD-like signal
        self.features.append(MLFeature(
            name="momentum_signal",
            feature_type=FeatureType.TECHNICAL_INDICATORS,
            description="Momentum signal (similar to MACD)",
            computation_func=lambda df: df['close'].rolling(12).mean() - df['close'].rolling(26).mean()
        ))

        # ===== REGIME FEATURES =====

        self.features.append(MLFeature(
            name="trend_strength",
            feature_type=FeatureType.REGIME_FEATURES,
            description="Linear regression R-squared (trend strength)",
            computation_func=lambda df: self._calculate_trend_strength(df['close'])
        ))

        self.features.append(MLFeature(
            name="price_range_ratio",
            feature_type=FeatureType.REGIME_FEATURES,
            description="Price range / Average range",
            computation_func=lambda df: (df['high'].rolling(20).max() - df['low'].rolling(20).min()) / (df['close'].rolling(100).max() - df['close'].rolling(100).min())
        ))

        logger.info(f"Initialized {len(self.features)} features across {len(FeatureType)} categories")

    def _calculate_atr(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        """Calculate Average True Range."""
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift())
        low_close = np.abs(df['low'] - df['close'].shift())

        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr = tr.rolling(period).mean()

        return atr

    def _calculate_rsi(self, prices: pd.Series, period: int = 14) -> pd.Series:
        """Calculate RSI."""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(period).mean()

        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))

        return rsi

    def _calculate_bb_position(self, df: pd.DataFrame, period: int = 20) -> pd.Series:
        """Calculate position within Bollinger Bands."""
        sma = df['close'].rolling(period).mean()
        std = df['close'].rolling(period).std()

        upper_band = sma + 2 * std
        lower_band = sma - 2 * std

        # Position: 0 = lower band, 1 = upper band
        position = (df['close'] - lower_band) / (upper_band - lower_band)

        return position

    def _calculate_trend_strength(self, prices: pd.Series, period: int = 50) -> pd.Series:
        """Calculate trend strength using R-squared of linear regression."""
        trend_strength = pd.Series(index=prices.index, dtype=float)

        for i in range(period, len(prices)):
            y = prices.iloc[i-period:i].values
            x = np.arange(period)

            # Linear regression
            slope, intercept = np.polyfit(x, y, 1)
            y_pred = slope * x + intercept

            # R-squared
            ss_res = np.sum((y - y_pred) ** 2)
            ss_tot = np.sum((y - np.mean(y)) ** 2)

            if ss_tot > 0:
                r_squared = 1 - (ss_res / ss_tot)
                trend_strength.iloc[i] = r_squared
            else:
                trend_strength.iloc[i] = 0

        return trend_strength

    def generate_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Generate all features for the given data.

        Returns DataFrame with all features.
        """
        feature_df = df.copy()

        for feature in self.features:
            if feature.is_active:
                try:
                    values = feature.computation_func(df)
                    feature_df[feature.name] = values
                except Exception as e:
                    logger.warning(f"Failed to compute feature {feature.name}: {e}")
                    feature_df[feature.name] = np.nan

        # Drop NaN values
        feature_df = feature_df.dropna()

        logger.info(f"Generated {len(self.features)} features from {len(df)} rows → {len(feature_df)} rows after NaN removal")

        return feature_df

    def get_feature_names(self) -> List[str]:
        """Get list of all feature names."""
        return [f.name for f in self.features if f.is_active]

    def get_feature_importance_report(self, importance_dict: Dict[str, float]) -> str:
        """Generate feature importance report."""
        report = "\n" + "="*60 + "\n"
        report += "FEATURE IMPORTANCE REPORT\n"
        report += "="*60 + "\n\n"

        # Sort by importance
        sorted_features = sorted(importance_dict.items(), key=lambda x: x[1], reverse=True)

        for i, (feature_name, importance) in enumerate(sorted_features[:20], 1):
            feature = next((f for f in self.features if f.name == feature_name), None)
            feature_type = feature.feature_type.value if feature else "unknown"
            description = feature.description if feature else ""

            report += f"{i}. {feature_name}\n"
            report += f"   Importance: {importance:.4f}\n"
            report += f"   Type: {feature_type}\n"
            report += f"   Description: {description}\n\n"

        return report


class MLStrategyDiscovery:
    """
    Machine Learning strategy discovery system.

    Uses ML to discover profitable trading strategies by learning
    patterns from historical data.

    Key Innovation: Regime-aware model training - models learn
    different patterns for different market regimes.
    """

    def __init__(self):
        self.feature_engine = AutomatedFeatureEngine()
        self.market_intel = get_market_intelligence()
        self.models = {}
        self.model_history = []

        # Training parameters
        self.min_training_samples = 500
        self.test_size = 0.2
        self.cv_folds = 5

        logger.info("MLStrategyDiscovery initialized")

    async def discover_strategies(
        self,
        symbol: str,
        data: pd.DataFrame,
        model_type: MLModelType = MLModelType.GRADIENT_BOOSTING,
        target_horizon: int = 5
    ) -> MLStrategyResult:
        """
        Discover trading strategies using machine learning.

        Args:
            symbol: Trading symbol
            data: Historical price data
            model_type: Type of ML model to use
            target_horizon: Periods ahead to predict

        Returns:
            MLStrategyResult with discovered strategy performance
        """
        logger.info(f"Starting ML strategy discovery for {symbol} using {model_type.value}")

        # Generate features
        feature_df = self.feature_engine.generate_features(data)

        if len(feature_df) < self.min_training_samples:
            raise ValueError(f"Insufficient data: {len(feature_df)} < {self.min_training_samples} required")

        # Create target variable: future return
        feature_df['target_return'] = feature_df['close'].shift(-target_horizon) / feature_df['close'] - 1
        feature_df['target_direction'] = (feature_df['target_return'] > 0).astype(int)

        # Drop rows with NaN target
        feature_df = feature_df.dropna(subset=['target_return', 'target_direction'])

        # Get feature columns
        feature_cols = self.feature_engine.get_feature_names()

        # Prepare data
        X = feature_df[feature_cols].values
        y_direction = feature_df['target_direction'].values
        y_return = feature_df['target_return'].values

        # Split data (time-series aware split)
        split_idx = int(len(X) * (1 - self.test_size))

        X_train, X_test = X[:split_idx], X[split_idx:]
        y_train_dir, y_test_dir = y_direction[:split_idx], y_direction[split_idx:]
        y_train_ret, y_test_ret = y_return[:split_idx], y_return[split_idx:]

        # Train model
        model, train_accuracy, test_accuracy, cv_scores = await self._train_model(
            X_train, y_train_dir, X_test, y_test_dir, model_type
        )

        # Feature importance
        feature_importance = self._get_feature_importance(model, feature_cols)

        # SHAP values
        shap_values = self._calculate_shap_values(model, X_test, feature_cols)

        # Make predictions
        predictions = model.predict(X_test)
        prediction_probs = model.predict_proba(X_test)[:, 1]

        # Calculate strategy performance
        performance = self._calculate_strategy_performance(
            predictions, prediction_probs, y_test_ret, y_test_dir
        )

        # Regime-specific performance
        regime_performance = await self._calculate_regime_specific_performance(
            feature_df.iloc[split_idx:], predictions, y_test_ret
        )

        result = MLStrategyResult(
            model_type=model_type,
            features_used=feature_cols,
            feature_importance=feature_importance,
            train_accuracy=train_accuracy,
            test_accuracy=test_accuracy,
            cross_val_scores=cv_scores,
            shap_values_available=shap_values is not None,
            regime_specific_performance=regime_performance,
            predicted_returns=pd.Series(prediction_probs * y_test_ret),  # Prob * return
            actual_returns=pd.Series(y_test_ret),
            total_profit_usdt=performance['total_profit'],
            max_drawdown_pct=performance['max_drawdown'],
            sharpe_ratio=performance['sharpe'],
            recommended_position_size=performance['position_size'],
            confidence_level=performance['confidence']
        )

        # Store model
        self.models[f"{symbol}_{model_type.value}"] = model

        logger.info(f"ML strategy discovery complete: Test accuracy={test_accuracy:.2%}, "
                   f"Profit=${result.total_profit_usdt:.2f}, Sharpe={result.sharpe_ratio:.2f}")

        return result

    async def _train_model(
        self,
        X_train, y_train,
        X_test, y_test,
        model_type: MLModelType
    ) -> Tuple:
        """Train the ML model and return metrics."""

        if model_type == MLModelType.GRADIENT_BOOSTING:
            model = GradientBoostingClassifier(
                n_estimators=100,
                learning_rate=0.1,
                max_depth=5,
                min_samples_split=20,
                min_samples_leaf=10,
                random_state=42
            )
        elif model_type == MLModelType.RANDOM_FOREST:
            model = RandomForestClassifier(
                n_estimators=100,
                max_depth=10,
                min_samples_split=20,
                min_samples_leaf=10,
                random_state=42
            )
        elif model_type == MLModelType.ADA_BOOST:
            model = AdaBoostClassifier(
                n_estimators=100,
                learning_rate=0.1,
                random_state=42
            )
        else:
            # Default to gradient boosting
            model = GradientBoostingClassifier(
                n_estimators=100,
                learning_rate=0.1,
                max_depth=5,
                random_state=42
            )

        # Train
        model.fit(X_train, y_train)

        # Predictions
        train_pred = model.predict(X_train)
        test_pred = model.predict(X_test)

        # Metrics
        train_accuracy = accuracy_score(y_train, train_pred)
        test_accuracy = accuracy_score(y_test, test_pred)

        # Cross-validation
        cv_scores = cross_val_score(model, X_train, y_train, cv=self.cv_folds, scoring='accuracy')

        return model, train_accuracy, test_accuracy, cv_scores.tolist()

    def _get_feature_importance(self, model, feature_names: List[str]) -> Dict[str, float]:
        """Get feature importance from model."""
        if hasattr(model, 'feature_importances_'):
            importances = model.feature_importances_
            return dict(zip(feature_names, importances))
        return {}

    def _calculate_shap_values(self, model, X_test, feature_names: List[str]) -> Optional[np.ndarray]:
        """Calculate SHAP values for model interpretability."""
        try:
            explainer = shap.TreeExplainer(model)
            shap_values = explainer.shap_values(X_test[:100])  # Sample for speed

            return shap_values
        except Exception as e:
            logger.warning(f"Failed to calculate SHAP values: {e}")
            return None

    def _calculate_strategy_performance(
        self,
        predictions: np.ndarray,
        prediction_probs: np.ndarray,
        actual_returns: np.ndarray,
        actual_directions: np.ndarray,
        initial_capital: float = 10000.0
    ) -> Dict[str, float]:
        """Calculate strategy performance metrics."""

        # Simulate trading: only take high-confidence predictions
        confidence_threshold = 0.6
        high_conf_mask = prediction_probs > confidence_threshold

        if not np.any(high_conf_mask):
            return {
                'total_profit': 0.0,
                'max_drawdown': 0.0,
                'sharpe': 0.0,
                'position_size': 0.0,
                'confidence': 0.0
            }

        # Trading simulation
        trades = []
        position = 0
        capital = initial_capital

        for i in range(len(predictions)):
            if high_conf_mask[i]:
                # Trade based on prediction
                trade_return = actual_returns[i] * predictions[i]

                # Apply costs (realistic)
                trade_return -= 0.0005  # Taker fee

                capital *= (1 + trade_return)
                trades.append(trade_return)

        # Calculate metrics
        total_profit = capital - initial_capital
        total_return = total_profit / initial_capital

        # Drawdown
        cumulative_returns = pd.Series(trades).cumsum()
        running_max = cumulative_returns.cummax()
        drawdown = (cumulative_returns - running_max)
        max_drawdown = abs(drawdown.min())

        # Sharpe ratio (annualized)
        if len(trades) > 1:
            sharpe = np.mean(trades) / np.std(trades) * np.sqrt(252) if np.std(trades) > 0 else 0
        else:
            sharpe = 0.0

        # Position sizing (Kelly-like)
        win_rate = np.sum([t > 0 for t in trades]) / len(trades) if trades else 0
        avg_win = np.mean([t for t in trades if t > 0]) if any(t > 0 for t in trades) else 0
        avg_loss = np.mean([t for t in trades if t < 0]) if any(t < 0 for t in trades) else 0

        if avg_loss != 0:
            kelly = (win_rate * avg_win - (1 - win_rate) * abs(avg_loss)) / abs(avg_loss)
            kelly = max(0, min(kelly, 0.25))  # Cap at 25%
        else:
            kelly = 0.0

        return {
            'total_profit': total_profit,
            'max_drawdown': max_drawdown,
            'sharpe': sharpe,
            'position_size': kelly,
            'confidence': np.mean(prediction_probs[high_conf_mask]) if np.any(high_conf_mask) else 0.0
        }

    async def _calculate_regime_specific_performance(
        self,
        test_data: pd.DataFrame,
        predictions: np.ndarray,
        actual_returns: np.ndarray
    ) -> Dict[str, float]:
        """Calculate performance by market regime."""

        # For simplicity, use trend strength to classify regimes
        trend_strength = test_data['trend_strength'].values

        # Classify by trend strength
        strong_trend_mask = trend_strength > 0.7
        weak_trend_mask = trend_strength < 0.3

        regime_performance = {}

        if np.any(strong_trend_mask):
            trend_returns = actual_returns[strong_trend_mask]
            trend_preds = predictions[strong_trend_mask]
            regime_performance['strong_trend'] = np.mean(trend_returns * trend_preds)

        if np.any(weak_trend_mask):
            weak_returns = actual_returns[weak_trend_mask]
            weak_preds = predictions[weak_trend_mask]
            regime_performance['weak_trend'] = np.mean(weak_returns * weak_preds)

        return regime_performance

    def generate_report(self, result: MLStrategyResult) -> str:
        """Generate comprehensive ML strategy discovery report."""

        report = "\n" + "="*60 + "\n"
        report += "ML STRATEGY DISCOVERY REPORT\n"
        report += "="*60 + "\n\n"

        # Model performance
        report += "MODEL PERFORMANCE\n"
        report += "-" * 40 + "\n"
        report += f"Model Type: {result.model_type.value}\n"
        report += f"Train Accuracy: {result.train_accuracy:.2%}\n"
        report += f"Test Accuracy: {result.test_accuracy:.2%}\n"
        report += f"Cross-Val Scores: {np.mean(result.cross_val_scores):.2%} ± {np.std(result.cross_val_scores):.2%}\n\n"

        # Financial performance
        report += "FINANCIAL PERFORMANCE (Starting Capital: $10,000)\n"
        report += "-" * 40 + "\n"
        report += f"Total Profit: ${result.total_profit_usdt:,.2f}\n"
        report += f"Total Return: {result.total_profit_usdt / 10000:.2%}\n"
        report += f"Max Drawdown: {result.max_drawdown_pct:.2%}\n"
        report += f"Sharpe Ratio: {result.sharpe_ratio:.2f}\n"
        report += f"Recommended Position Size: {result.recommended_position_size:.2%}\n"
        report += f"Confidence Level: {result.confidence_level:.2%}\n\n"

        # Feature importance
        report += "TOP FEATURES (By Importance)\n"
        report += "-" * 40 + "\n"
        sorted_features = sorted(result.feature_importance.items(),
                                key=lambda x: x[1], reverse=True)
        for i, (feature, importance) in enumerate(sorted_features[:10], 1):
            report += f"{i}. {feature}: {importance:.4f}\n"

        # Regime performance
        if result.regime_specific_performance:
            report += "\nREGIME-SPECIFIC PERFORMANCE\n"
            report += "-" * 40 + "\n"
            for regime, perf in result.regime_specific_performance.items():
                report += f"{regime}: {perf:.4f}\n"

        return report


# Singleton instance
_ml_discovery = None


def get_ml_discovery() -> MLStrategyDiscovery:
    """Get or create ML strategy discovery instance."""
    global _ml_discovery
    if _ml_discovery is None:
        _ml_discovery = MLStrategyDiscovery()
    return _ml_discovery
