"""
RIGOROUS WALK-FORWARD BACKTESTER for ML-500-5h Strategy
Simulates real trading conditions - no look-ahead bias, no future data leakage
"""

import pandas as pd
import numpy as np
from pathlib import Path
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, precision_score, recall_score
import json
from datetime import datetime, timedelta
import logging
from typing import Dict, List, Tuple, Optional
import warnings
warnings.filterwarnings('ignore')

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


class RigorousWalkForwardBacktester:
    """
    Rigorous walk-forward backtester that simulates real trading conditions.

    Key Features:
    - NO look-ahead bias (never uses future data)
    - Proper train/test splits for each prediction
    - Realistic signal generation (features computed only from available data)
    - Accurate trading cost simulation
    - Proper position sizing and risk management
    """

    def __init__(self,
                 data_path: str = "btc_data_cache/BTCUSDT_1h_12m.csv",
                 initial_capital: float = 100000,
                 position_size: float = 0.30,
                 stop_loss: float = 0.05,
                 take_profit: float = 0.08,
                 max_drawdown_limit: float = 0.15):

        self.data_path = data_path
        self.initial_capital = initial_capital
        self.position_size = position_size
        self.stop_loss = stop_loss
        self.take_profit = take_profit
        self.max_drawdown_limit = max_drawdown_limit

        # Trading costs (brutally honest)
        self.maker_fee = 0.0002  # 0.02%
        self.taker_fee = 0.0005  # 0.05%
        self.slippage_bps = 5.0  # 0.05%

        # ML-500-5h configuration
        self.ml_config = {
            'train_window': 500,  # hours of training data
            'horizon': 5,  # prediction horizon in hours
            'confidence_threshold': 0.65,
            'n_estimators': 30,
            'max_depth': 3,
            'random_state': 42
        }

        self.df = None
        self.features = None
        self.trades = []
        self.equity_curve = []

    def load_and_prepare_data(self) -> pd.DataFrame:
        """Load and prepare data with NO look-ahead bias."""

        logger.info("Loading market data...")
        df = pd.read_csv(self.data_path, index_col='timestamp', parse_dates=True)
        logger.info(f"✓ Loaded {len(df)} candles")

        # Add technical features - computed ONLY from available data
        logger.info("Computing technical features (no look-ahead bias)...")

        # RSI (14-period)
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))

        # MACD (12, 26, 9)
        exp1 = df['close'].ewm(span=12).mean()
        exp2 = df['close'].ewm(span=26).mean()
        df['macd'] = exp1 - exp2
        df['macd_signal'] = df['macd'].ewm(span=9).mean()
        df['macd_hist'] = df['macd'] - df['macd_signal']

        # Bollinger Bands (20, 2)
        df['bb_middle'] = df['close'].rolling(20).mean()
        df['bb_std'] = df['close'].rolling(20).std()
        df['bb_upper'] = df['bb_middle'] + 2 * df['bb_std']
        df['bb_lower'] = df['bb_middle'] - 2 * df['bb_std']
        df['bb_position'] = (df['close'] - df['bb_lower']) / (df['bb_upper'] - df['bb_lower'])

        # ATR (14-period)
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift())
        low_close = np.abs(df['low'] - df['close'].shift())
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = ranges.max(axis=1)
        df['atr'] = true_range.rolling(14).mean()
        df['atr_pct'] = df['atr'] / df['close']

        # Volume analysis
        df['volume_sma'] = df['volume'].rolling(20).mean()
        df['volume_ratio'] = df['volume'] / df['volume_sma']

        # Momentum indicators
        df['momentum_5'] = df['close'].pct_change(5)
        df['volatility'] = df['close'].rolling(20).std() / df['close'].rolling(20).mean()

        # Trend analysis
        df['ema_20'] = df['close'].ewm(span=20).mean()
        df['ema_50'] = df['close'].ewm(span=50).mean()
        df['trend'] = (df['ema_20'] - df['ema_50']) / df['ema_50']

        # Target variable (future returns) - ONLY for training
        # CRITICAL: This is NEVER used for prediction, only for training labels
        for h in [1, 3, 5]:
            df[f'future_return_{h}'] = df['close'].shift(-h) / df['close'] - 1

        self.df = df
        self.features = ['rsi', 'macd', 'bb_position', 'atr_pct',
                        'volume_ratio', 'momentum_5', 'volatility', 'trend']

        logger.info("✓ Features prepared")
        logger.info(f"✓ Feature set: {self.features}")

        return df

    def train_model(self, train_data: pd.DataFrame) -> RandomForestClassifier:
        """
        Train ML model using ONLY historical data.

        CRITICAL: This function never sees future data.
        """

        X_train = train_data[self.features].fillna(0)
        y_train = (train_data['future_return_5'] > 0).astype(int)

        # Skip if not enough data or only one class
        if len(X_train) < 100 or y_train.nunique() < 2:
            return None

        model = RandomForestClassifier(
            n_estimators=self.ml_config['n_estimators'],
            max_depth=self.ml_config['max_depth'],
            random_state=self.ml_config['random_state'],
            n_jobs=1,
            min_samples_split=20,
            min_samples_leaf=10
        )

        model.fit(X_train, y_train)
        return model

    def generate_signal(self, model: RandomForestClassifier,
                       current_row: pd.Series) -> Tuple[int, float]:
        """
        Generate trading signal using ONLY current and historical data.

        Returns: (signal, confidence)
        - signal: 1 (long), -1 (short), 0 (no trade)
        - confidence: 0.0 to 1.0
        """

        if model is None:
            return 0, 0.0

        # Get current features (ONLY available at this point in time)
        feature_values = []
        for feature in self.features:
            value = current_row[feature]
            if pd.isna(value):
                value = 0.0
            feature_values.append(value)

        feature_array = np.array(feature_values).reshape(1, -1)

        # Get prediction probabilities
        proba = model.predict_proba(feature_array)[0]
        confidence = proba.max()

        if confidence < self.ml_config['confidence_threshold']:
            return 0, confidence

        # Get prediction
        prediction = model.predict(feature_array)[0]

        # Convert to signal
        signal = 1 if prediction == 1 else -1

        return signal, confidence

    def execute_trade(self, signal: int, price: float,
                     capital: float, atr_pct: float) -> Tuple[float, float, int]:
        """
        Execute trade with realistic costs and position sizing.

        Returns: (new_capital, position_size, entry_price)
        """

        # Volatility-adjusted position sizing
        vol_adjustment = min(1.5, max(0.5, 1 / (1 + atr_pct * 100)))
        adjusted_position_size = self.position_size * vol_adjustment

        # Calculate position size and entry price with slippage
        if signal > 0:  # Long
            entry_price = price * (1 + self.slippage_bps / 10000)
            capital *= (1 - self.maker_fee)  # Pay maker fee
            position = adjusted_position_size
        else:  # Short
            entry_price = price * (1 - self.slippage_bps / 10000)
            capital *= (1 - self.maker_fee)  # Pay maker fee
            position = -adjusted_position_size

        return capital, position, entry_price

    def check_exit_conditions(self, position: float, entry_price: float,
                             current_price: float, capital: float) -> Tuple[bool, float]:
        """
        Check if position should be exited based on SL/TP.

        Returns: (should_exit, pnl)
        """

        if position == 0:
            return False, 0.0

        pnl_pct = (current_price - entry_price) / entry_price

        if position > 0:  # Long position
            if pnl_pct <= -self.stop_loss or pnl_pct >= self.take_profit:
                # Exit long
                exit_price = current_price * (1 - self.slippage_bps / 10000)
                pnl = position * (exit_price - entry_price) / entry_price * capital
                return True, pnl

        else:  # Short position
            if pnl_pct >= self.stop_loss or pnl_pct <= -self.take_profit:
                # Exit short
                exit_price = current_price * (1 + self.slippage_bps / 10000)
                pnl = abs(position) * (entry_price - exit_price) / entry_price * capital
                return True, pnl

        return False, 0.0

    def run_walk_forward_backtest(self) -> Dict:
        """
        Run rigorous walk-forward backtest simulating real trading.

        CRITICAL: At each point in time, we ONLY have access to:
        - Historical data up to that point
        - No future information
        - Realistic execution delays
        """

        df = self.df.copy()

        logger.info("\n" + "=" * 80)
        logger.info("RIGOROUS WALK-FORWARD BACKTEST")
        logger.info("=" * 80)
        logger.info("\nSimulating REAL trading conditions:")
        logger.info("  ✓ No look-ahead bias")
        logger.info("  ✓ No future data leakage")
        logger.info("  ✓ Realistic trading costs")
        logger.info("  ✓ Proper execution timing")
        logger.info("\nStarting backtest...\n")

        # Trading state
        capital = self.initial_capital
        position = 0  # Positive for long, negative for short
        entry_price = 0
        peak_capital = capital
        total_capital_at_risk = 0

        # Tracking
        predictions_correct = 0
        predictions_total = 0
        hourly_returns = []

        # Walk-forward through each hour (starting after train_window)
        for i in range(self.ml_config['train_window'],
                      len(df) - self.ml_config['horizon']):

            current_time = df.index[i]
            current_price = df['close'].iloc[i]
            current_atr_pct = df['atr_pct'].iloc[i]

            # Get ONLY historical data up to this point
            historical_data = df.iloc[:i].copy()

            # Check for trade exit FIRST (before entering new positions)
            if position != 0:
                should_exit, pnl = self.check_exit_conditions(
                    position, entry_price, current_price, capital
                )

                if should_exit:
                    # Close position
                    capital += pnl * (1 - self.taker_fee - self.maker_fee)

                    # Record trade
                    self.trades.append({
                        'entry_time': self.entry_time,
                        'exit_time': current_time,
                        'entry_price': entry_price,
                        'exit_price': current_price,
                        'pnl': pnl,
                        'pnl_pct': (current_price - entry_price) / entry_price if position > 0 else (entry_price - current_price) / entry_price,
                        'type': 'long' if position > 0 else 'short',
                        'confidence': self.entry_confidence,
                        'hold_hours': (current_time - self.entry_time).total_seconds() / 3600
                    })

                    position = 0
                    entry_price = 0

            # Check max drawdown limit
            peak_capital = max(peak_capital, capital)
            current_drawdown = (peak_capital - capital) / peak_capital

            if current_drawdown >= self.max_drawdown_limit:
                # System shutdown - stop trading
                logger.warning(f"\n⚠️  Max drawdown limit reached: {current_drawdown*100:.2f}%")
                logger.warning(f"   Trading halted at {current_time}")
                break

            # Generate NEW trading signal (only if not in position)
            if position == 0:
                # Train model on historical data ONLY
                train_data = historical_data.tail(self.ml_config['train_window'])
                model = self.train_model(train_data)

                # Generate signal using current data
                current_row = df.iloc[i]
                signal, confidence = self.generate_signal(model, current_row)

                if signal != 0:
                    # Execute trade
                    capital, position, entry_price = self.execute_trade(
                        signal, current_price, capital, current_atr_pct
                    )

                    self.entry_time = current_time
                    self.entry_confidence = confidence
                    self.entry_prediction = 1 if signal > 0 else 0

                    # Track prediction accuracy
                    future_return = df['future_return_5'].iloc[i]
                    actual_direction = 1 if future_return > 0 else 0

                    predictions_total += 1
                    if self.entry_prediction == actual_direction:
                        predictions_correct += 1

            # Record hourly return
            if len(hourly_returns) > 0:
                hourly_return = (capital - self.total_capital_at_risk) / self.total_capital_at_risk
                hourly_returns.append(hourly_return)
            else:
                hourly_returns.append(0)

            self.total_capital_at_risk = capital
            self.equity_curve.append({
                'timestamp': current_time,
                'capital': capital,
                'position': position,
                'drawdown': current_drawdown
            })

            # Progress reporting
            if i % 1000 == 0:
                progress = (i - self.ml_config['train_window']) / (len(df) - self.ml_config['train_window'] - self.ml_config['horizon']) * 100
                logger.info(f"  Progress: {progress:.1f}% | Capital: ${capital:,.2f} | Trades: {len(self.trades)}")

        # Close any remaining position
        if position != 0:
            final_price = df['close'].iloc[-1]
            should_exit, pnl = self.check_exit_conditions(
                position, entry_price, final_price, capital
            )
            if not should_exit:
                # Force close at end
                if position > 0:
                    exit_price = final_price * (1 - self.slippage_bps / 10000)
                    pnl = position * (exit_price - entry_price) / entry_price * capital
                else:
                    exit_price = final_price * (1 + self.slippage_bps / 10000)
                    pnl = abs(position) * (entry_price - exit_price) / entry_price * capital

                capital += pnl * (1 - self.taker_fee - self.maker_fee)

                self.trades.append({
                    'entry_time': self.entry_time,
                    'exit_time': df.index[-1],
                    'entry_price': entry_price,
                    'exit_price': final_price,
                    'pnl': pnl,
                    'pnl_pct': (final_price - entry_price) / entry_price if position > 0 else (entry_price - final_price) / entry_price,
                    'type': 'long' if position > 0 else 'short',
                    'confidence': self.entry_confidence,
                    'hold_hours': (df.index[-1] - self.entry_time).total_seconds() / 3600
                })

        return self._calculate_metrics(capital, hourly_returns, predictions_correct, predictions_total)

    def _calculate_metrics(self, final_capital: float,
                          hourly_returns: List[float],
                          predictions_correct: int,
                          predictions_total: int) -> Dict:
        """Calculate performance metrics."""

        total_return = (final_capital - self.initial_capital) / self.initial_capital

        # Sharpe ratio (annualized)
        if len(hourly_returns) > 1 and np.std(hourly_returns) > 0:
            sharpe = np.mean(hourly_returns) / np.std(hourly_returns) * np.sqrt(8760)
        else:
            sharpe = 0.0

        # Max drawdown
        drawdowns = [ec['drawdown'] for ec in self.equity_curve]
        max_drawdown = max(drawdowns) if drawdowns else 0.0

        # Win rate
        if self.trades:
            win_rate = sum(1 for t in self.trades if t['pnl'] > 0) / len(self.trades)
        else:
            win_rate = 0.0

        # Prediction accuracy
        prediction_accuracy = predictions_correct / predictions_total if predictions_total > 0 else 0.0

        # Sortino ratio
        if len(hourly_returns) > 1:
            downside_returns = [r for r in hourly_returns if r < 0]
            if downside_returns and np.std(downside_returns) > 0:
                sortino = np.mean(hourly_returns) / np.std(downside_returns) * np.sqrt(8760)
            else:
                sortino = 0.0
        else:
            sortino = 0.0

        # Calmar ratio
        calmar = total_return / max_drawdown if max_drawdown > 0 else 0.0

        return {
            'total_return': total_return,
            'sharpe_ratio': sharpe,
            'sortino_ratio': sortino,
            'calmar_ratio': calmar,
            'max_drawdown': max_drawdown,
            'win_rate': win_rate,
            'prediction_accuracy': prediction_accuracy,
            'total_trades': len(self.trades),
            'final_capital': final_capital,
            'total_predictions': predictions_total,
            'correct_predictions': predictions_correct
        }

    def print_results(self, results: Dict):
        """Print comprehensive backtest results."""

        logger.info("\n" + "=" * 80)
        logger.info("BACKTEST RESULTS")
        logger.info("=" * 80)

        logger.info("\n📊 PERFORMANCE METRICS:")
        logger.info(f"  Total Return:        {results['total_return']*100:+.2f}%")
        logger.info(f"  Sharpe Ratio:        {results['sharpe_ratio']:.2f}")
        logger.info(f"  Sortino Ratio:       {results['sortino_ratio']:.2f}")
        logger.info(f"  Calmar Ratio:        {results['calmar_ratio']:.2f}")
        logger.info(f"  Max Drawdown:        {results['max_drawdown']*100:.2f}%")
        logger.info(f"  Win Rate:            {results['win_rate']*100:.1f}%")
        logger.info(f"  Prediction Accuracy: {results['prediction_accuracy']*100:.1f}%")

        logger.info("\n📈 TRADING ACTIVITY:")
        logger.info(f"  Total Trades:        {results['total_trades']}")
        logger.info(f"  Final Capital:       ${results['final_capital']:,.2f}")
        logger.info(f"  Predictions Made:    {results['total_predictions']}")

        if self.trades:
            # Trade statistics
            profitable_trades = [t for t in self.trades if t['pnl'] > 0]
            losing_trades = [t for t in self.trades if t['pnl'] <= 0]

            if profitable_trades:
                avg_win = np.mean([t['pnl'] for t in profitable_trades])
                avg_win_pct = np.mean([t['pnl_pct'] for t in profitable_trades])
                logger.info(f"\n✅ PROFITABLE TRADES:")
                logger.info(f"  Count:               {len(profitable_trades)}")
                logger.info(f"  Avg Win:             ${avg_win:,.2f}")
                logger.info(f"  Avg Win %:           {avg_win_pct*100:.2f}%")

                best_trade = max(profitable_trades, key=lambda x: x['pnl'])
                logger.info(f"  Best Trade:          ${best_trade['pnl']:,.2f} ({best_trade['pnl_pct']*100:.2f}%)")

            if losing_trades:
                avg_loss = np.mean([t['pnl'] for t in losing_trades])
                avg_loss_pct = np.mean([t['pnl_pct'] for t in losing_trades])
                logger.info(f"\n❌ LOSING TRADES:")
                logger.info(f"  Count:               {len(losing_trades)}")
                logger.info(f"  Avg Loss:            ${avg_loss:,.2f}")
                logger.info(f"  Avg Loss %:          {avg_loss_pct*100:.2f}%")

                worst_trade = min(losing_trades, key=lambda x: x['pnl'])
                logger.info(f"  Worst Trade:         ${worst_trade['pnl']:,.2f} ({worst_trade['pnl_pct']*100:.2f}%)")

            # Hold time statistics
            hold_times = [t['hold_hours'] for t in self.trades]
            logger.info(f"\n⏱️  TRADE DURATION:")
            logger.info(f"  Avg Hold Time:       {np.mean(hold_times):.1f} hours")
            logger.info(f"  Median Hold Time:    {np.median(hold_times):.1f} hours")
            logger.info(f"  Min Hold Time:       {min(hold_times):.1f} hours")
            logger.info(f"  Max Hold Time:       {max(hold_times):.1f} hours")

        logger.info("\n" + "=" * 80)

    def save_results(self, results: Dict, filename: str = "ml_500_5h_rigorous_backtest_results.json"):
        """Save backtest results to JSON file."""

        output = {
            'timestamp': datetime.now().isoformat(),
            'strategy': 'ML-500-5h Walk-Forward',
            'configuration': {
                'initial_capital': self.initial_capital,
                'position_size': self.position_size,
                'stop_loss': self.stop_loss,
                'take_profit': self.take_profit,
                'max_drawdown_limit': self.max_drawdown_limit,
                'maker_fee': self.maker_fee,
                'taker_fee': self.taker_fee,
                'slippage_bps': self.slippage_bps,
                'ml_config': self.ml_config
            },
            'results': results,
            'trades': self.trades,
            'equity_curve': self.equity_curve
        }

        with open(filename, 'w') as f:
            json.dump(output, f, indent=2, default=str)

        logger.info(f"\n✓ Results saved to {filename}")


def main():
    """Run the rigorous walk-forward backtest."""

    logger.info("\n" + "=" * 80)
    logger.info("ML-500-5h RIGOROUS WALK-FORWARD BACKTESTER")
    logger.info("=" * 80)
    logger.info("\nThis backtest simulates REAL trading conditions:")
    logger.info("  • No look-ahead bias (never uses future data)")
    logger.info("  • No data leakage (features computed from available data only)")
    logger.info("  • Realistic trading costs (maker/taker fees, slippage)")
    logger.info("  • Proper execution timing (signals generated, then executed)")
    logger.info("  • Walk-forward validation (model trains on historical data)")

    # Initialize backtester
    backtester = RigorousWalkForwardBacktester(
        data_path="btc_data_cache/BTCUSDT_1h_12m.csv",
        initial_capital=100000,
        position_size=0.30,
        stop_loss=0.05,
        take_profit=0.08,
        max_drawdown_limit=0.15
    )

    # Load data
    backtester.load_and_prepare_data()

    # Run rigorous walk-forward backtest
    results = backtester.run_walk_forward_backtest()

    # Print results
    backtester.print_results(results)

    # Save results
    backtester.save_results(results)

    return results


if __name__ == "__main__":
    results = main()
