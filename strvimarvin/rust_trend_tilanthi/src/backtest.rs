use crate::market::Bar;

#[derive(Debug, Clone, Copy, PartialEq)]
pub struct BacktestConfig {
    pub initial_cash: f64,
}

impl Default for BacktestConfig {
    fn default() -> Self {
        Self {
            initial_cash: 10_000.0,
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq)]
pub struct EquityPoint {
    pub timestamp_ms: i64,
    pub equity: f64,
}

#[derive(Debug, Clone, PartialEq)]
pub struct BacktestResult {
    pub starting_equity: f64,
    pub ending_equity: f64,
    pub equity_curve: Vec<EquityPoint>,
}

pub fn run_backtest(bars: &[Bar], config: BacktestConfig) -> BacktestResult {
    let equity_curve = bars
        .iter()
        .map(|bar| EquityPoint {
            timestamp_ms: bar.timestamp_ms,
            equity: config.initial_cash,
        })
        .collect();

    BacktestResult {
        starting_equity: config.initial_cash,
        ending_equity: config.initial_cash,
        equity_curve,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::market::Symbol;

    #[test]
    fn empty_backtest_preserves_initial_cash() {
        let result = run_backtest(&[], BacktestConfig::default());

        assert_eq!(result.starting_equity, 10_000.0);
        assert_eq!(result.ending_equity, 10_000.0);
        assert!(result.equity_curve.is_empty());
    }

    #[test]
    fn starter_backtest_emits_one_equity_point_per_bar() {
        let symbol = Symbol::new("BTCUSDT");
        let bars = vec![
            Bar::new(
                symbol.clone(),
                1_700_000_000_000,
                100.0,
                101.0,
                99.0,
                100.5,
                42.0,
            ),
            Bar::new(symbol, 1_700_000_060_000, 100.5, 102.0, 100.0, 101.5, 48.0),
        ];

        let result = run_backtest(
            &bars,
            BacktestConfig {
                initial_cash: 25_000.0,
            },
        );

        assert_eq!(result.starting_equity, 25_000.0);
        assert_eq!(result.ending_equity, 25_000.0);
        assert_eq!(result.equity_curve.len(), 2);
        assert_eq!(result.equity_curve[0].timestamp_ms, 1_700_000_000_000);
        assert_eq!(result.equity_curve[1].equity, 25_000.0);
    }
}
