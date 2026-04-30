"""
ENHANCED STRATEGY CLASSES
Applying ML-500-5h success principles to improve each strategy class
"""

import sqlite3
import json
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import logging
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import cross_val_score
import warnings
warnings.filterwarnings('ignore')

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


class EnhancedStrategyClasses:
    """Enhanced versions of strategy classes with ML, risk management, and optimization."""

    def __init__(self, data_path: str = "btc_data_cache/BTCUSDT_1h_12m.csv"):
        self.data_path = data_path
        self.df = None
        self.features = None
        self.maker_fee = 0.0002  # 0.02%
        self.taker_fee = 0.0005  # 0.05%
        self.slippage_bps = 5.0

        # ML-500-5h proven parameters
        self.ml_config = {
            'train_window': 500,
            'horizon': 5,
            'confidence_threshold': 0.65,
            'n_estimators': 30,
            'max_depth': 3,
            'random_state': 42
        }

    def load_data(self) -> pd.DataFrame:
        """Load and prepare data with proper features."""
        if self.df is not None:
            return self.df

        logger.info("Loading market data...")
        df = pd.read_csv(self.data_path, index_col='timestamp', parse_dates=True)
        logger.info(f"✓ Loaded {len(df)} candles")

        # Add technical features (ML-500-5h style)
        logger.info("Preparing technical features...")

        # RSI
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))

        # MACD
        exp1 = df['close'].ewm(span=12).mean()
        exp2 = df['close'].ewm(span=26).mean()
        df['macd'] = exp1 - exp2
        df['macd_signal'] = df['macd'].ewm(span=9).mean()
        df['macd_hist'] = df['macd'] - df['macd_signal']

        # Bollinger Bands
        df['bb_middle'] = df['close'].rolling(20).mean()
        df['bb_std'] = df['close'].rolling(20).std()
        df['bb_upper'] = df['bb_middle'] + 2 * df['bb_std']
        df['bb_lower'] = df['bb_middle'] - 2 * df['bb_std']
        df['bb_position'] = (df['close'] - df['bb_lower']) / (df['bb_upper'] - df['bb_lower'])

        # ATR
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift())
        low_close = np.abs(df['low'] - df['close'].shift())
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = ranges.max(axis=1)
        df['atr'] = true_range.rolling(14).mean()
        df['atr_pct'] = df['atr'] / df['close']

        # Volume
        df['volume_sma'] = df['volume'].rolling(20).mean()
        df['volume_ratio'] = df['volume'] / df['volume_sma']

        # Momentum
        df['momentum_5'] = df['close'].pct_change(5)
        df['momentum_10'] = df['close'].pct_change(10)

        # Volatility
        df['volatility'] = df['close'].rolling(20).std() / df['close'].rolling(20).mean()

        # Trend
        df['ema_20'] = df['close'].ewm(span=20).mean()
        df['ema_50'] = df['close'].ewm(span=50).mean()
        df['trend'] = (df['ema_20'] - df['ema_50']) / df['ema_50']

        # Regime detection
        df['regime_trend'] = df['trend'].rolling(50).mean()
        df['regime_volatility'] = df['volatility'].rolling(50).mean()

        # Multi-timeframe features (simulate 5m, 10m, 15m from hourly)
        for tf in [5, 10, 15]:
            df[f'ma_{tf}'] = df['close'].rolling(tf).mean()
            df[f'ma_{tf}_ratio'] = df['close'] / df[f'ma_{tf}']

        # Target variable
        for h in [1, 3, 5]:
            df[f'future_return_{h}'] = df['close'].shift(-h) / df['close'] - 1

        self.df = df
        logger.info("✓ Features prepared")

        return df

    def realistic_backtest(self, signals: pd.Series, position_size: float = 0.30,
                          stop_loss: float = 0.05, take_profit: float = 0.08,
                          max_drawdown_limit: float = 0.15) -> Dict:
        """Realistic backtest with proper risk management."""

        df = self.df.copy()
        initial_capital = 100000
        capital = initial_capital
        position = 0
        entry_price = 0
        peak_capital = initial_capital
        trades = []
        equity_curve = []

        for i in range(1, len(df)):
            current_price = df['close'].iloc[i]

            # Check stop loss / take profit
            if position != 0:
                pnl_pct = (current_price - entry_price) / entry_price
                if position > 0:  # Long
                    if pnl_pct <= -stop_loss or pnl_pct >= take_profit:
                        # Exit position
                        exit_price = current_price * (1 - self.slippage_bps / 10000)
                        pnl = position * (exit_price - entry_price) / entry_price * capital
                        capital += pnl * (1 - self.taker_fee - self.maker_fee)
                        trades.append({
                            'entry': entry_price,
                            'exit': exit_price,
                            'pnl_pct': pnl_pct,
                            'type': 'long'
                        })
                        position = 0
                        entry_price = 0

                else:  # Short
                    if pnl_pct >= stop_loss or pnl_pct <= -take_profit:
                        # Exit position
                        exit_price = current_price * (1 + self.slippage_bps / 10000)
                        pnl = abs(position) * (entry_price - exit_price) / entry_price * capital
                        capital += pnl * (1 - self.taker_fee - self.maker_fee)
                        trades.append({
                            'entry': entry_price,
                            'exit': exit_price,
                            'pnl_pct': -pnl_pct,
                            'type': 'short'
                        })
                        position = 0
                        entry_price = 0

            # Check max drawdown
            peak_capital = max(peak_capital, capital)
            current_drawdown = (peak_capital - capital) / peak_capital
            if current_drawdown >= max_drawdown_limit:
                # System shutdown - close everything
                if position != 0:
                    if position > 0:
                        exit_price = current_price * (1 - self.slippage_bps / 10000)
                        pnl = position * (exit_price - entry_price) / entry_price * capital
                        capital += pnl * (1 - self.taker_fee - self.maker_fee)
                    else:
                        exit_price = current_price * (1 + self.slippage_bps / 10000)
                        pnl = abs(position) * (entry_price - exit_price) / entry_price * capital
                        capital += pnl * (1 - self.taker_fee - self.maker_fee)
                    position = 0
                    entry_price = 0

                equity_curve.append(capital)
                continue  # Stop trading

            # Enter new position
            if position == 0 and signals.iloc[i] != 0:
                # Volatility-adjusted position sizing
                atr_pct = df['atr_pct'].iloc[i]
                vol_adjustment = min(1.5, max(0.5, 1 / (1 + atr_pct * 100)))
                adjusted_size = position_size * vol_adjustment

                if signals.iloc[i] > 0:  # Long signal
                    entry_price = current_price * (1 + self.slippage_bps / 10000)
                    position = adjusted_size
                    capital *= (1 - self.maker_fee)
                else:  # Short signal
                    entry_price = current_price * (1 - self.slippage_bps / 10000)
                    position = -adjusted_size
                    capital *= (1 - self.maker_fee)

            equity_curve.append(capital)

        # Calculate metrics
        total_return = (capital - initial_capital) / initial_capital

        # Sharpe ratio (annualized)
        returns = pd.Series(equity_curve).pct_change().dropna()
        sharpe = returns.mean() / returns.std() * np.sqrt(8760) if returns.std() > 0 else 0

        # Max drawdown
        peak = pd.Series(equity_curve).expanding(min_periods=1).max()
        drawdown = (peak - pd.Series(equity_curve)) / peak
        max_drawdown = drawdown.max()

        # Win rate
        win_rate = sum(1 for t in trades if t['pnl_pct'] > 0) / len(trades) if trades else 0

        return {
            'total_return': total_return,
            'sharpe_ratio': sharpe,
            'max_drawdown': max_drawdown,
            'win_rate': win_rate,
            'total_trades': len(trades),
            'final_capital': capital,
            'equity_curve': equity_curve,
            'trades': trades
        }

    def enhanced_multitimeframe_strategy(self) -> Dict:
        """Enhanced multi-timeframe strategy with ML and risk management."""

        logger.info("\n" + "=" * 80)
        logger.info("ENHANCED MULTI-TIMEFRAME STRATEGY")
        logger.info("=" * 80)

        df = self.load_data()

        # Multi-timeframe signals (5m, 10m, 15m, plus 1h for trend)
        df['mtf_signal'] = 0

        for i in range(500, len(df) - 5):
            # Get signals from multiple timeframes
            signals = []

            # 5-period signal (simulated 5m)
            ma5_ratio = df['ma_5_ratio'].iloc[i]
            if ma5_ratio > 1.001:
                signals.append(1)
            elif ma5_ratio < 0.999:
                signals.append(-1)

            # 10-period signal (simulated 10m)
            ma10_ratio = df['ma_10_ratio'].iloc[i]
            if ma10_ratio > 1.0015:
                signals.append(1)
            elif ma10_ratio < 0.9985:
                signals.append(-1)

            # 15-period signal (simulated 15m)
            ma15_ratio = df['ma_15_ratio'].iloc[i]
            if ma15_ratio > 1.002:
                signals.append(1)
            elif ma15_ratio < 0.998:
                signals.append(-1)

            # 1h trend context
            trend_strength = df['trend'].iloc[i]
            if abs(trend_strength) > 0.02:
                if trend_strength > 0:
                    signals.append(0.5)  # Bullish bias
                else:
                    signals.append(-0.5)  # Bearish bias

            # Combine signals with exponential weighting
            if signals:
                # Recent timeframes get more weight
                weights = np.array([0.4, 0.3, 0.2, 0.1])
                weighted_signal = sum(s * w for s, w in zip(signals, weights))

                # ML filtering
                feature_cols = ['rsi', 'macd', 'bb_position', 'atr_pct', 'volume_ratio',
                              'momentum_5', 'volatility', 'trend']

                X_train = df[feature_cols].iloc[i-500:i].fillna(0)
                y_train = (df['future_return_5'].iloc[i-500:i] > 0).astype(int)

                if y_train.nunique() > 1:
                    model = RandomForestClassifier(
                        n_estimators=self.ml_config['n_estimators'],
                        max_depth=self.ml_config['max_depth'],
                        random_state=self.ml_config['random_state'],
                        n_jobs=1
                    )
                    model.fit(X_train, y_train)

                    current_features = df[feature_cols].iloc[i:i+1].fillna(0)
                    proba = model.predict_proba(current_features)[0].max()

                    if proba > self.ml_config['confidence_threshold']:
                        prediction = model.predict(current_features)[0]
                        # Combine MTF signal with ML prediction
                        final_signal = weighted_signal * 0.6 + (1 if prediction == 1 else -1) * 0.4

                        if abs(final_signal) > 0.3:
                            df['mtf_signal'].iloc[i] = np.sign(final_signal)

        logger.info("✓ MTF+ML signals generated")

        # Backtest with enhanced risk management
        results = self.realistic_backtest(
            df['mtf_signal'],
            position_size=0.30,
            stop_loss=0.05,
            take_profit=0.08,
            max_drawdown_limit=0.15
        )

        logger.info(f"\nEnhanced Multi-Timeframe Results:")
        logger.info(f"  Return: {results['total_return']*100:+.2f}%")
        logger.info(f"  Sharpe: {results['sharpe_ratio']:.2f}")
        logger.info(f"  Max DD: {results['max_drawdown']*100:.2f}%")
        logger.info(f"  Win Rate: {results['win_rate']*100:.1f}%")
        logger.info(f"  Trades: {results['total_trades']}")

        return {
            'strategy_name': 'enhanced_multitimeframe',
            'strategy_type': 'multi_timeframe',
            'parameters': {
                'timeframes': ['5m', '10m', '15m', '1h'],
                'ml_config': self.ml_config,
                'position_size': 0.30,
                'stop_loss': 0.05,
                'take_profit': 0.08,
                'volatility_adjustment': True
            },
            'results': results
        }

    def enhanced_regime_strategy(self) -> Dict:
        """Enhanced regime switching strategy with ML confirmation."""

        logger.info("\n" + "=" * 80)
        logger.info("ENHANCED REGIME SWITCHING STRATEGY")
        logger.info("=" * 80)

        df = self.load_data()

        # Enhanced regime detection
        df['regime'] = 'unknown'
        df['regime_signal'] = 0

        for i in range(500, len(df) - 5):
            # Detect market regime
            recent_vol = df['volatility'].iloc[i-50:i].mean()
            recent_trend = df['trend'].iloc[i-50:i].mean()
            recent_momentum = df['momentum_5'].iloc[i-50:i].mean()

            # Classify regime
            if recent_vol > df['volatility'].iloc[i-500:i].quantile(0.75):
                if abs(recent_trend) > 0.01:
                    regime = 'volatile_trending'
                else:
                    regime = 'volatile_ranging'
            else:
                if abs(recent_trend) > 0.01:
                    regime = 'calm_trending'
                else:
                    regime = 'calm_ranging'

            df['regime'].iloc[i] = regime

            # ML confirmation
            feature_cols = ['rsi', 'macd', 'bb_position', 'atr_pct', 'volume_ratio',
                          'momentum_5', 'volatility', 'trend']

            X_train = df[feature_cols].iloc[i-500:i].fillna(0)
            y_train = (df['future_return_5'].iloc[i-500:i] > 0).astype(int)

            if y_train.nunique() > 1:
                model = RandomForestClassifier(
                    n_estimators=self.ml_config['n_estimators'],
                    max_depth=self.ml_config['max_depth'],
                    random_state=self.ml_config['random_state'],
                    n_jobs=1
                )
                model.fit(X_train, y_train)

                current_features = df[feature_cols].iloc[i:i+1].fillna(0)
                proba = model.predict_proba(current_features)[0].max()

                if proba > self.ml_config['confidence_threshold']:
                    prediction = model.predict(current_features)[0]

                    # Regime-weighted signal
                    if regime == 'volatile_trending':
                        # High conviction in volatile trending
                        signal_strength = 1.0 if proba > 0.75 else 0.5
                    elif regime == 'calm_trending':
                        # Moderate conviction in calm trending
                        signal_strength = 0.8 if proba > 0.70 else 0.4
                    elif regime == 'volatile_ranging':
                        # Low conviction in volatile ranging (avoid)
                        signal_strength = 0.2
                    else:  # calm_ranging
                        # Mean reversion focus
                        signal_strength = 0.5

                    df['regime_signal'].iloc[i] = (1 if prediction == 1 else -1) * signal_strength

        logger.info("✓ Regime+ML signals generated")

        # Backtest
        results = self.realistic_backtest(
            df['regime_signal'],
            position_size=0.30,
            stop_loss=0.05,
            take_profit=0.08,
            max_drawdown_limit=0.15
        )

        logger.info(f"\nEnhanced Regime Switching Results:")
        logger.info(f"  Return: {results['total_return']*100:+.2f}%")
        logger.info(f"  Sharpe: {results['sharpe_ratio']:.2f}")
        logger.info(f"  Max DD: {results['max_drawdown']*100:.2f}%")
        logger.info(f"  Win Rate: {results['win_rate']*100:.1f}%")
        logger.info(f"  Trades: {results['total_trades']}")

        return {
            'strategy_name': 'enhanced_regime_switching',
            'strategy_type': 'regime_switching',
            'parameters': {
                'regimes': ['volatile_trending', 'volatile_ranging', 'calm_trending', 'calm_ranging'],
                'ml_config': self.ml_config,
                'position_size': 0.30,
                'stop_loss': 0.05,
                'take_profit': 0.08,
                'regime_weighted_sizing': True
            },
            'results': results
        }

    def hybrid_ml_mtf_regime_strategy(self) -> Dict:
        """Hybrid strategy combining ML, multi-timeframe, and regime switching."""

        logger.info("\n" + "=" * 80)
        logger.info("HYBRID ML+MTF+REGIME STRATEGY")
        logger.info("=" * 80)

        df = self.load_data()

        # Combined signal
        df['hybrid_signal'] = 0

        for i in range(500, len(df) - 5):
            # 1. Detect regime
            recent_vol = df['volatility'].iloc[i-50:i].mean()
            recent_trend = df['trend'].iloc[i-50:i].mean()

            if recent_vol > df['volatility'].iloc[i-500:i].quantile(0.75):
                regime = 'volatile'
            else:
                regime = 'calm'

            # 2. Multi-timeframe momentum
            mtf_signals = []
            for tf in [5, 10, 15]:
                ma_ratio = df[f'ma_{tf}_ratio'].iloc[i]
                if ma_ratio > 1.001:
                    mtf_signals.append(1)
                elif ma_ratio < 0.999:
                    mtf_signals.append(-1)
                else:
                    mtf_signals.append(0)

            mtf_consensus = np.mean(mtf_signals) if mtf_signals else 0

            # 3. ML prediction
            feature_cols = ['rsi', 'macd', 'bb_position', 'atr_pct', 'volume_ratio',
                          'momentum_5', 'volatility', 'trend']

            X_train = df[feature_cols].iloc[i-500:i].fillna(0)
            y_train = (df['future_return_5'].iloc[i-500:i] > 0).astype(int)

            if y_train.nunique() > 1:
                model = RandomForestClassifier(
                    n_estimators=self.ml_config['n_estimators'],
                    max_depth=self.ml_config['max_depth'],
                    random_state=self.ml_config['random_state'],
                    n_jobs=1
                )
                model.fit(X_train, y_train)

                current_features = df[feature_cols].iloc[i:i+1].fillna(0)
                proba = model.predict_proba(current_features)[0].max()

                if proba > self.ml_config['confidence_threshold']:
                    ml_signal = 1 if model.predict(current_features)[0] == 1 else -1
                else:
                    ml_signal = 0
            else:
                ml_signal = 0
                proba = 0

            # 4. Combine signals with regime-based weighting
            if regime == 'volatile':
                # In volatile markets, rely more on ML (quick adaptation)
                ml_weight = 0.6
                mtf_weight = 0.4
                confidence_threshold = 0.70
            else:
                # In calm markets, rely more on MTF (trend following)
                ml_weight = 0.4
                mtf_weight = 0.6
                confidence_threshold = 0.65

            if proba > confidence_threshold and abs(mtf_consensus) > 0.3:
                combined_signal = ml_signal * ml_weight + mtf_consensus * mtf_weight

                # Only trade if signals align
                if abs(combined_signal) > 0.5:
                    df['hybrid_signal'].iloc[i] = np.sign(combined_signal)

        logger.info("✓ Hybrid ML+MTF+Regime signals generated")

        # Backtest
        results = self.realistic_backtest(
            df['hybrid_signal'],
            position_size=0.30,
            stop_loss=0.05,
            take_profit=0.08,
            max_drawdown_limit=0.15
        )

        logger.info(f"\nHybrid ML+MTF+Regime Results:")
        logger.info(f"  Return: {results['total_return']*100:+.2f}%")
        logger.info(f"  Sharpe: {results['sharpe_ratio']:.2f}")
        logger.info(f"  Max DD: {results['max_drawdown']*100:.2f}%")
        logger.info(f"  Win Rate: {results['win_rate']*100:.1f}%")
        logger.info(f"  Trades: {results['total_trades']}")

        return {
            'strategy_name': 'hybrid_ml_mtf_regime',
            'strategy_type': 'hybrid',
            'parameters': {
                'components': ['ml', 'multi_timeframe', 'regime_switching'],
                'ml_config': self.ml_config,
                'position_size': 0.30,
                'stop_loss': 0.05,
                'take_profit': 0.08,
                'regime_adaptive_weights': True
            },
            'results': results
        }


def main():
    """Test all enhanced strategy classes."""

    enhancer = EnhancedStrategyClasses()

    results = []

    # Test enhanced multi-timeframe
    try:
        mtf_result = enhancer.enhanced_multitimeframe_strategy()
        results.append(mtf_result)
    except Exception as e:
        logger.error(f"Enhanced MTF failed: {e}")

    # Test enhanced regime switching
    try:
        regime_result = enhancer.enhanced_regime_strategy()
        results.append(regime_result)
    except Exception as e:
        logger.error(f"Enhanced Regime failed: {e}")

    # Test hybrid strategy
    try:
        hybrid_result = enhancer.hybrid_ml_mtf_regime_strategy()
        results.append(hybrid_result)
    except Exception as e:
        logger.error(f"Hybrid strategy failed: {e}")

    # Summary
    logger.info("\n" + "=" * 80)
    logger.info("ENHANCED STRATEGY CLASSES - COMPARISON")
    logger.info("=" * 80)

    for result in results:
        r = result['results']
        logger.info(f"\n{result['strategy_name'].upper()}:")
        logger.info(f"  Return: {r['total_return']*100:+.2f}%")
        logger.info(f"  Sharpe: {r['sharpe_ratio']:.2f}")
        logger.info(f"  Max DD: {r['max_drawdown']*100:.2f}%")
        logger.info(f"  Win Rate: {r['win_rate']*100:.1f}%")
        logger.info(f"  Trades: {r['total_trades']}")

    # Save results
    output = {
        'timestamp': pd.Timestamp.now().isoformat(),
        'strategies': results,
        'summary': {
            'best_return': max(results, key=lambda x: x['results']['total_return']),
            'best_sharpe': max(results, key=lambda x: x['results']['sharpe_ratio']),
            'best_drawdown': min(results, key=lambda x: x['results']['max_drawdown'])
        }
    }

    with open('enhanced_strategy_classes_results.json', 'w') as f:
        json.dump(output, f, indent=2, default=str)

    logger.info("\n✓ Results saved to enhanced_strategy_classes_results.json")


if __name__ == "__main__":
    main()
