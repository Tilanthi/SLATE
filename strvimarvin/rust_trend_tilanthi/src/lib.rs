pub mod backtest;
pub mod dashboard;
pub mod data;
pub mod engine;
pub mod indicators;
pub mod market;
#[cfg(feature = "python-ext")]
pub mod python_api;
pub mod wfo;

pub use backtest::{BacktestConfig, BacktestResult, EquityPoint, run_backtest};
pub use market::{Bar, Symbol};
