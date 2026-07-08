use crate::data::binance_um::{KlineStore, MS_PER_MINUTE, parse_date, preset_symbols};
use crate::engine::{
    EntryAttempt, EntryFillModel, EntryMode, ExecutionConfig, SymbolExecutionRules, Trade,
    simulate_limit_momentum_trades_with_diagnostics,
};
use crate::indicators::{
    IndicatorKind, OhlcvBar, SignalPoint, Strategy4448KamaKerParams, Timeframe, hurst_exponent,
    momentum_signals, resample_ohlcv, shannon_entropy, strategy_4448_kama_ker_signals,
};
use anyhow::{Context, Result};
use chrono::{DateTime, Duration, NaiveDate, TimeZone, Utc};
use optimizer::parameter::{FloatParam, IntParam, Parameter};
use optimizer::sampler::tpe::TpeSampler;
use optimizer::{Direction, Study};
use rayon::prelude::*;
use serde::{Deserialize, Serialize};
use std::collections::{BTreeMap, BTreeSet};
use std::fs::{self, File, OpenOptions};
use std::io::Write;
use std::path::{Path, PathBuf};
use std::time::Instant;

const RUNS_ROOT: &str = "runs/wfo";
const CHECKS_FILE: &str = "_checks.json";
const STRATEGY_OOS_RESULTS_FILE: &str = "strategy_oos_results.json";
const STRATEGY_OOS_STATUS_FILE: &str = "strategy_oos_status.json";
const STRATEGY_OOS_BLOCKS_DIR: &str = "strategy_oos";
const SIGNAL_FILL_DIAGNOSTICS_FILE: &str = "signal_fill_diagnostics.csv";
const TPE_TRIALS_FILE: &str = "tpe_trials.csv";
const FOLD_TRIALS_FILE: &str = "fold_trials.csv";
const OPTIMIZER_PROVENANCE_CSV_FILE: &str = "optimizer_provenance.csv";
const OPTIMIZER_PROVENANCE_JSONL_FILE: &str = "optimizer_provenance.jsonl";
const OOS_EQUITY_ARTIFACT_MAX_POINTS: usize = 2_400;
const FOLD_LOCAL_CANDIDATE_ID_STRIDE: usize = 1_000_000;
const MINUTES_PER_DAY: i64 = 1_440;
const INELIGIBLE_SCORE_CUTOFF: f64 = -999.0;
const MIN_SELECTABLE_SCORE: f64 = 0.0;
const DEFAULT_MIN_PROFIT_FACTOR: f64 = 1.20;
const DEFAULT_CANDIDATE_MIN_PROFIT_FACTOR: f64 = 1.20;
const DEFAULT_MIN_EDGE_T_STAT: f64 = TRADE_EDGE_CONFIDENCE_Z;
const DEFAULT_TPE_TRIALS: usize = 150;
const DEFAULT_TPE_RANDOM_STARTUP_FRACTION: f64 = 0.15;
const TPE_CANDIDATES_PER_TRIAL: usize = 64;
const TPE_SELECTION_VALIDATION_FRACTION: f64 = 0.50;
const TPE_OBJECTIVE_DISPERSION_PENALTY_WEIGHT: f64 = 0.08;
const TPE_OBJECTIVE_OVERFIT_GAP_PENALTY_WEIGHT: f64 = 0.35;
const TPE_BREADTH_REFERENCE_FRACTION: f64 = 0.28;
const TPE_BREADTH_RANK_WEIGHT: f64 = 20.0;
const TPE_OBJECTIVE_RANK_WEIGHT: f64 = 0.08;
const TPE_PAIRED_COUNT_OBJECTIVE_WEIGHT: f64 = 35.0;
const TPE_IS_CONSENSUS_OFFSET_DAYS: usize = 7;
const DEFAULT_TPE_IS_CONSENSUS_MIN_PASSING_WINDOWS: usize = 5;
const TPE_IS_CONSENSUS_MEAN_RANK_WEIGHT: f64 = 0.20;
const TPE_IS_CONSENSUS_DISPERSION_RANK_WEIGHT: f64 = 0.10;
const FOLD_LOCAL_OBJECTIVE_WARMUP_DAYS: i64 = 30;
const PROFIT_FACTOR_SCORE_WEIGHT: f64 = 1.50;
const PER_TRADE_EDGE_SCORE_WEIGHT: f64 = 0.45;
const TPE_MIN_SELECTION_SCORE: f64 = 6.0;
const TRADE_EDGE_CONFIDENCE_Z: f64 = 0.0;
const WEEKLY_CONSISTENCY_SCORE_WEIGHT: f64 = 0.35;
const DRAWDOWN_TO_RETURN_PENALTY_WEIGHT: f64 = 0.35;
const TRADE_FREQUENCY_PENALTY_WEIGHT: f64 = 18.0;
const MIN_FILL_RATE_SCORE_PCT: f64 = 2.0;
const MIN_EXIT_STOP_ATR_MULTIPLE: f64 = 0.50;
const MAX_EXIT_STOP_ATR_MULTIPLE: f64 = 5.0;
const MIN_EXIT_TARGET_ATR_MULTIPLE: f64 = 0.50;
const MAX_EXIT_TARGET_ATR_MULTIPLE: f64 = 12.0;
const MAX_EXIT_TARGET_STOP_RATIO: f64 = 4.0;
const BAD_EXIT_GEOMETRY_REJECTION: &str = "bad_exit_geometry";
const MIN_CANDIDATE_ENTRY_DAY_PCT: f64 = 25.0;
const MIN_CANDIDATE_ENTRY_WEEK_PCT: f64 = 100.0;
const MAX_CANDIDATE_NO_ENTRY_GAP_DAYS: usize = 6;
const DEFAULT_ACCOUNT_BALANCE: f64 = 10_000.0;
const FEE_EDGE_BUFFER_MULTIPLIER: f64 = 2.0;
const TPE_MIN_LOOKBACK_BARS: usize = 4;
const TPE_MAX_LOOKBACK_BARS: usize = 240;
const TPE_MIN_ATR_BARS: usize = 20;
const TPE_MAX_ATR_BARS: usize = 200;
const TPE_ATR_STEP_BARS: usize = 5;
const TPE_MAX_TIME_STOP_BARS: usize = 288;
const TPE_MAX_ENTRY_ATR_MULTIPLE: f64 = 1.50;
const TPE_MIN_TARGET_ATR_MULTIPLE: f64 = 0.75;
const SOFT_SCORE_MIN: f64 = INELIGIBLE_SCORE_CUTOFF + 1.0;
const TRADE_COUNT_SOFT_PENALTY_WEIGHT: f64 = 80.0;
const PROFIT_FACTOR_SOFT_PENALTY_WEIGHT: f64 = 60.0;
const NET_RETURN_SOFT_PENALTY_WEIGHT: f64 = 8.0;
const AVG_EDGE_SOFT_PENALTY_WEIGHT: f64 = 20.0;
const EDGE_CONFIDENCE_SOFT_PENALTY_WEIGHT: f64 = 15.0;
const FILL_RATE_SOFT_PENALTY_WEIGHT: f64 = 30.0;
const ENTRY_DAY_SOFT_PENALTY_WEIGHT: f64 = 20.0;
const ENTRY_WEEK_SOFT_PENALTY_WEIGHT: f64 = 20.0;
const NO_ENTRY_GAP_SOFT_PENALTY_WEIGHT: f64 = 10.0;
const STRATEGY_4448_SOURCE_KAMA1_ER: usize = 30;
const STRATEGY_4448_SOURCE_KAMA1_SHORT: usize = 45;
const STRATEGY_4448_SOURCE_KAMA1_LONG: usize = 19;
const STRATEGY_4448_SOURCE_KAMA2_ER: usize = 37;
const STRATEGY_4448_SOURCE_KAMA2_SHORT: usize = 46;
const STRATEGY_4448_SOURCE_KAMA2_LONG: usize = 15;
const STRATEGY_4448_SOURCE_COUNT_BARS: usize = 9;
const MIN_SIGNAL_BARS_PER_CLOSED_TRADE: f64 = 180.0;
const MAX_SIGNAL_BARS_PER_CLOSED_TRADE: f64 = 8.0;
const ABSOLUTE_MIN_TRADES_PER_SCORE_WINDOW: f64 = 5.0;
const MIN_CANDIDATE_OOS_TRADES: usize = 500;
const SYMBOL_PAUSE_LOSS_TRIGGER_PCT: f64 = -12.0;
const SYMBOL_PAUSE_FOLDS: usize = 4;
const EHLERS_INDICATORS: [IndicatorKind; 6] = [
    IndicatorKind::EhlersDecycler,
    IndicatorKind::SuperSmoother,
    IndicatorKind::EhlersRoofing,
    IndicatorKind::CyberCycle,
    IndicatorKind::EvenBetterSineWave,
    IndicatorKind::MamaFama,
];
const SUSPICIOUS_SHORTLIST_SET: &str = "suspicious-shortlist";
const CALIBRATION_AUDIT_SET: &str = "calibration-audit";
const PORTFOLIO_CANDIDATES_SET: &str = "portfolio-candidates";
const LOW_TURNOVER_EXTRA_SET: &str = "low-turnover-extra";
const SECOND_PASS_PORTFOLIO_SET: &str = "second-pass-portfolio";
const ROBUST_PORTFOLIO_SET: &str = "robust-portfolio";
const GOAL_SEARCH_SET: &str = "goal-search";
const HIGH_TRADE_GOAL_SET: &str = "high-trade-goal";
const HIGH_TRADE_REFINE_SET: &str = "high-trade-refine";
const PORTFOLIO_REFINE_SET: &str = "portfolio-refine";
const QUALITY_HUNT_SET: &str = "quality-hunt";
const Q3_DIVERSIFIERS_SET: &str = "q3-diversifiers";
const BEST_COMBO_CONFIRM_SET: &str = "best-combo-confirm";
const FRAMA_5M_CONFIRM_SET: &str = "frama-5m-confirm";
const STRATEGY_336_KAMA_TPO_SET: &str = "strategy-336";
const STRATEGY_3635_KAMA_TPO_SET: &str = "strategy-3635";
const STRATEGY_3938_KAMA_TPO_SET: &str = "strategy-3938";
const STRATEGY_4448_KAMA_KER_SET: &str = "strategy-4448";
const STRATEGY_33X_SQX_SET: &str = "strategy-33x-sqx";
const ELEGANT_5M_SET: &str = "elegant-5m";
const ELEGANT_5M_ENTRY50_SET: &str = "elegant-5m-entry50";
const ELEGANT_5M_ENTRY50_GATED_SET: &str = "elegant-5m-entry50-gated";
const ELEGANT_5M_ENTRY50_UNGATED_SET: &str = "elegant-5m-entry50-ungated";
const ELEGANT_5M_HYBRID_SET: &str = "elegant-5m-hybrid";
const SUSPICIOUS_SHORTLIST: [(IndicatorKind, Timeframe); 17] = [
    (IndicatorKind::Reflex, Timeframe::M3),
    (IndicatorKind::Reflex, Timeframe::M5),
    (IndicatorKind::Reflex, Timeframe::M15),
    (IndicatorKind::Alma, Timeframe::M3),
    (IndicatorKind::Alma, Timeframe::M5),
    (IndicatorKind::Alma, Timeframe::M15),
    (IndicatorKind::Frama, Timeframe::M3),
    (IndicatorKind::Frama, Timeframe::M5),
    (IndicatorKind::Frama, Timeframe::M15),
    (IndicatorKind::Frama, Timeframe::M30),
    (IndicatorKind::ConnorsRsi, Timeframe::M3),
    (IndicatorKind::ConnorsRsi, Timeframe::M5),
    (IndicatorKind::ConnorsRsi, Timeframe::M15),
    (IndicatorKind::ConnorsRsi, Timeframe::M30),
    (IndicatorKind::DonchianBreakout, Timeframe::M3),
    (IndicatorKind::DonchianBreakout, Timeframe::M5),
    (IndicatorKind::DonchianBreakout, Timeframe::M15),
];
const CALIBRATION_AUDIT: [(IndicatorKind, Timeframe); 19] = [
    (IndicatorKind::SuperSmoother, Timeframe::M5),
    (IndicatorKind::SuperSmoother, Timeframe::M15),
    (IndicatorKind::SuperSmoother, Timeframe::M30),
    (IndicatorKind::EhlersRoofing, Timeframe::M1),
    (IndicatorKind::EhlersRoofing, Timeframe::M3),
    (IndicatorKind::EhlersRoofing, Timeframe::M5),
    (IndicatorKind::CenterOfGravity, Timeframe::M1),
    (IndicatorKind::CenterOfGravity, Timeframe::M3),
    (IndicatorKind::CenterOfGravity, Timeframe::M30),
    (IndicatorKind::EvenBetterSineWave, Timeframe::M1),
    (IndicatorKind::EvenBetterSineWave, Timeframe::M3),
    (IndicatorKind::TrendFlex, Timeframe::M1),
    (IndicatorKind::Reflex, Timeframe::M3),
    (IndicatorKind::Reflex, Timeframe::M5),
    (IndicatorKind::Alma, Timeframe::M5),
    (IndicatorKind::Kama, Timeframe::M5),
    (IndicatorKind::Kama, Timeframe::M15),
    (IndicatorKind::TillsonT3, Timeframe::M1),
    (IndicatorKind::TillsonT3, Timeframe::M3),
];
const PORTFOLIO_CANDIDATES: [(IndicatorKind, Timeframe); 5] = [
    (IndicatorKind::SuperSmoother, Timeframe::M15),
    (IndicatorKind::VolatilityAdjustedMomentum, Timeframe::H1),
    (IndicatorKind::StochasticMomentumIndex, Timeframe::M15),
    (IndicatorKind::TrendFlex, Timeframe::H1),
    (IndicatorKind::EhlersDecycler, Timeframe::M30),
];
const LOW_TURNOVER_EXTRA: [(IndicatorKind, Timeframe); 5] = [
    (IndicatorKind::Kama, Timeframe::H1),
    (IndicatorKind::ElegantOscillator, Timeframe::H1),
    (IndicatorKind::VolatilityAdjustedMomentum, Timeframe::M15),
    (IndicatorKind::Frama, Timeframe::M30),
    (IndicatorKind::EvenBetterSineWave, Timeframe::H1),
];
const SECOND_PASS_PORTFOLIO: [(IndicatorKind, Timeframe); 18] = [
    (IndicatorKind::ConnorsRsi, Timeframe::M1),
    (IndicatorKind::ConnorsRsi, Timeframe::M5),
    (IndicatorKind::ConnorsRsi, Timeframe::M15),
    (IndicatorKind::ConnorsRsi, Timeframe::M30),
    (IndicatorKind::VolatilityAdjustedMomentum, Timeframe::M15),
    (IndicatorKind::VolatilityAdjustedMomentum, Timeframe::M30),
    (IndicatorKind::VolatilityAdjustedMomentum, Timeframe::H1),
    (IndicatorKind::DonchianBreakout, Timeframe::M15),
    (IndicatorKind::DonchianBreakout, Timeframe::M30),
    (IndicatorKind::DonchianBreakout, Timeframe::H1),
    (IndicatorKind::Cmo, Timeframe::M15),
    (IndicatorKind::Cmo, Timeframe::M30),
    (IndicatorKind::CyberCycle, Timeframe::M15),
    (IndicatorKind::CyberCycle, Timeframe::M30),
    (IndicatorKind::EhlersDecycler, Timeframe::M30),
    (IndicatorKind::StochasticMomentumIndex, Timeframe::M15),
    (IndicatorKind::StochasticMomentumIndex, Timeframe::M30),
    (IndicatorKind::TrendFlex, Timeframe::H1),
];
const ROBUST_PORTFOLIO: [(IndicatorKind, Timeframe); 16] = [
    (IndicatorKind::TillsonT3, Timeframe::M15),
    (IndicatorKind::DonchianBreakout, Timeframe::M3),
    (IndicatorKind::DonchianBreakout, Timeframe::M15),
    (IndicatorKind::DonchianBreakout, Timeframe::M30),
    (IndicatorKind::DonchianBreakout, Timeframe::H1),
    (IndicatorKind::SuperSmoother, Timeframe::M5),
    (IndicatorKind::SuperSmoother, Timeframe::M15),
    (IndicatorKind::ZeroLagHaTema, Timeframe::M15),
    (IndicatorKind::EhlersRoofing, Timeframe::M30),
    (IndicatorKind::VolatilityAdjustedMomentum, Timeframe::M5),
    (IndicatorKind::VolatilityAdjustedMomentum, Timeframe::M15),
    (IndicatorKind::VolatilityAdjustedMomentum, Timeframe::M30),
    (IndicatorKind::VolatilityAdjustedMomentum, Timeframe::H1),
    (IndicatorKind::Vortex, Timeframe::H1),
    (IndicatorKind::Frama, Timeframe::H1),
    (IndicatorKind::TrendFlex, Timeframe::M15),
];
const GOAL_SEARCH: [(IndicatorKind, Timeframe); 19] = [
    (IndicatorKind::SuperSmoother, Timeframe::M5),
    (IndicatorKind::SuperSmoother, Timeframe::M15),
    (IndicatorKind::CyberCycle, Timeframe::M15),
    (IndicatorKind::CyberCycle, Timeframe::M30),
    (IndicatorKind::Frama, Timeframe::M5),
    (IndicatorKind::Frama, Timeframe::M15),
    (IndicatorKind::Frama, Timeframe::M30),
    (IndicatorKind::Frama, Timeframe::H1),
    (IndicatorKind::Alma, Timeframe::M5),
    (IndicatorKind::Alma, Timeframe::M15),
    (IndicatorKind::Reflex, Timeframe::M5),
    (IndicatorKind::Reflex, Timeframe::M15),
    (IndicatorKind::ConnorsRsi, Timeframe::M5),
    (IndicatorKind::ConnorsRsi, Timeframe::M15),
    (IndicatorKind::ConnorsRsi, Timeframe::M30),
    (IndicatorKind::DonchianBreakout, Timeframe::M3),
    (IndicatorKind::DonchianBreakout, Timeframe::M15),
    (IndicatorKind::DonchianBreakout, Timeframe::H1),
    (IndicatorKind::VolatilityAdjustedMomentum, Timeframe::M30),
];
const HIGH_TRADE_GOAL: [(IndicatorKind, Timeframe); 27] = [
    (IndicatorKind::SuperSmoother, Timeframe::M5),
    (IndicatorKind::SuperSmoother, Timeframe::M15),
    (IndicatorKind::CyberCycle, Timeframe::M5),
    (IndicatorKind::CyberCycle, Timeframe::M15),
    (IndicatorKind::Frama, Timeframe::M5),
    (IndicatorKind::Frama, Timeframe::M15),
    (IndicatorKind::Alma, Timeframe::M5),
    (IndicatorKind::Alma, Timeframe::M15),
    (IndicatorKind::Reflex, Timeframe::M5),
    (IndicatorKind::Reflex, Timeframe::M15),
    (IndicatorKind::ConnorsRsi, Timeframe::M5),
    (IndicatorKind::ConnorsRsi, Timeframe::M15),
    (IndicatorKind::RelativeVigorIndex, Timeframe::M5),
    (IndicatorKind::RelativeVigorIndex, Timeframe::M15),
    (IndicatorKind::VolatilityAdjustedMomentum, Timeframe::M5),
    (IndicatorKind::VolatilityAdjustedMomentum, Timeframe::M15),
    (IndicatorKind::VolatilityAdjustedMomentum, Timeframe::M30),
    (IndicatorKind::Cmo, Timeframe::M5),
    (IndicatorKind::Cmo, Timeframe::M15),
    (IndicatorKind::Roc, Timeframe::M5),
    (IndicatorKind::Roc, Timeframe::M15),
    (IndicatorKind::ZeroLagHaTema, Timeframe::M5),
    (IndicatorKind::ZeroLagHaTema, Timeframe::M15),
    (IndicatorKind::TrendFlex, Timeframe::M5),
    (IndicatorKind::TrendFlex, Timeframe::M15),
    (IndicatorKind::DonchianBreakout, Timeframe::M5),
    (IndicatorKind::DonchianBreakout, Timeframe::M15),
];
const HIGH_TRADE_REFINE: [(IndicatorKind, Timeframe); 8] = [
    (IndicatorKind::Alma, Timeframe::M5),
    (IndicatorKind::TrendFlex, Timeframe::M5),
    (IndicatorKind::Frama, Timeframe::M5),
    (IndicatorKind::ZeroLagHaTema, Timeframe::M5),
    (IndicatorKind::Roc, Timeframe::M5),
    (IndicatorKind::ConnorsRsi, Timeframe::M5),
    (IndicatorKind::Reflex, Timeframe::M5),
    (IndicatorKind::Cmo, Timeframe::M5),
];
const PORTFOLIO_REFINE: [(IndicatorKind, Timeframe); 9] = [
    (IndicatorKind::TrendFlex, Timeframe::M5),
    (IndicatorKind::ZeroLagHaTema, Timeframe::M5),
    (IndicatorKind::Alma, Timeframe::M5),
    (IndicatorKind::Frama, Timeframe::M5),
    (IndicatorKind::Frama, Timeframe::M15),
    (IndicatorKind::Roc, Timeframe::M5),
    (IndicatorKind::Cmo, Timeframe::M5),
    (IndicatorKind::VolatilityAdjustedMomentum, Timeframe::M30),
    (IndicatorKind::SuperSmoother, Timeframe::M15),
];
const QUALITY_HUNT: [(IndicatorKind, Timeframe); 13] = [
    (IndicatorKind::EhlersRoofing, Timeframe::M5),
    (IndicatorKind::Kama, Timeframe::M5),
    (IndicatorKind::CenterOfGravity, Timeframe::M15),
    (IndicatorKind::SuperSmoother, Timeframe::M15),
    (IndicatorKind::TillsonT3, Timeframe::M15),
    (IndicatorKind::DonchianBreakout, Timeframe::M5),
    (IndicatorKind::DonchianBreakout, Timeframe::M15),
    (IndicatorKind::TrendFlex, Timeframe::M5),
    (IndicatorKind::Alma, Timeframe::M5),
    (IndicatorKind::Frama, Timeframe::M15),
    (IndicatorKind::ZeroLagHaTema, Timeframe::M5),
    (IndicatorKind::Roc, Timeframe::M5),
    (IndicatorKind::VolatilityAdjustedMomentum, Timeframe::M30),
];
const Q3_DIVERSIFIERS: [(IndicatorKind, Timeframe); 8] = [
    (IndicatorKind::CyberCycle, Timeframe::M3),
    (IndicatorKind::ZeroLagHaTema, Timeframe::M3),
    (IndicatorKind::InverseFisherTransform, Timeframe::M5),
    (IndicatorKind::Cmo, Timeframe::M15),
    (IndicatorKind::CenterOfGravity, Timeframe::M15),
    (IndicatorKind::EhlersRoofing, Timeframe::M30),
    (IndicatorKind::Alma, Timeframe::M30),
    (IndicatorKind::DonchianBreakout, Timeframe::M30),
];
const BEST_COMBO_CONFIRM: [(IndicatorKind, Timeframe); 3] = [
    (IndicatorKind::TrendFlex, Timeframe::M5),
    (IndicatorKind::InverseFisherTransform, Timeframe::M5),
    (IndicatorKind::DonchianBreakout, Timeframe::M30),
];
const FRAMA_5M_CONFIRM: [(IndicatorKind, Timeframe); 1] = [(IndicatorKind::Frama, Timeframe::M5)];
const STRATEGY_336_KAMA_TPO: [(IndicatorKind, Timeframe); 1] =
    [(IndicatorKind::Strategy336KamaTpo, Timeframe::M5)];
const STRATEGY_3635_KAMA_TPO: [(IndicatorKind, Timeframe); 1] =
    [(IndicatorKind::Strategy3635KamaTpo, Timeframe::M5)];
const STRATEGY_3938_KAMA_TPO: [(IndicatorKind, Timeframe); 1] =
    [(IndicatorKind::Strategy3938KamaTpo, Timeframe::M5)];
const STRATEGY_4448_KAMA_KER: [(IndicatorKind, Timeframe); 1] =
    [(IndicatorKind::Strategy4448KamaKer, Timeframe::M5)];
const STRATEGY_33X_SQX: [(IndicatorKind, Timeframe); 3] = [
    (IndicatorKind::Strategy336KamaTpo, Timeframe::M5),
    (IndicatorKind::Strategy3635KamaTpo, Timeframe::M5),
    (IndicatorKind::Strategy3938KamaTpo, Timeframe::M5),
];

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum GridSize {
    Smoke,
    Wide,
    Wide200,
    Tpe,
    Probe,
    Deep,
}

impl GridSize {
    pub fn parse(value: &str) -> Result<Self> {
        match value {
            "smoke" => Ok(Self::Smoke),
            "wide" => Ok(Self::Wide),
            "wide200" => Ok(Self::Wide200),
            "tpe" | "tpe150" => Ok(Self::Tpe),
            "probe" => Ok(Self::Probe),
            "deep" => Ok(Self::Deep),
            other => {
                anyhow::bail!(
                    "unknown WFO grid {other}; supported: smoke, wide, wide200, tpe, probe, deep"
                )
            }
        }
    }

    pub fn as_str(self) -> &'static str {
        match self {
            Self::Smoke => "smoke",
            Self::Wide => "wide",
            Self::Wide200 => "wide200",
            Self::Tpe => "tpe",
            Self::Probe => "probe",
            Self::Deep => "deep",
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WfoConfig {
    pub run_id: String,
    pub grid: GridSize,
    #[serde(default = "missing_optimizer_mode_is_research_only")]
    pub optimizer_mode: OptimizerMode,
    pub preset: String,
    #[serde(default)]
    pub symbols: Vec<String>,
    #[serde(default)]
    pub indicator_group: Option<String>,
    #[serde(default)]
    pub strategy_set: Option<String>,
    pub start: NaiveDate,
    pub end: NaiveDate,
    pub is_weeks: i64,
    pub oos_weeks: i64,
    pub step_weeks: i64,
    #[serde(default)]
    pub is_days: Option<i64>,
    #[serde(default)]
    pub oos_days: Option<i64>,
    #[serde(default)]
    pub step_days: Option<i64>,
    #[serde(default)]
    pub gap_weeks: i64,
    #[serde(default)]
    pub gap_days: Option<i64>,
    #[serde(default)]
    pub start_offset_days: i64,
    #[serde(default)]
    pub fold_start_index: usize,
    #[serde(default)]
    pub fold_limit: Option<usize>,
    pub fixed_notional: f64,
    #[serde(default = "default_account_balance")]
    pub account_balance: f64,
    pub fees_bps: f64,
    #[serde(default = "default_min_profit_factor")]
    pub min_profit_factor: f64,
    #[serde(default = "default_candidate_min_profit_factor")]
    pub candidate_min_profit_factor: f64,
    #[serde(default = "default_tpe_trials")]
    pub tpe_trials: usize,
    #[serde(default = "default_tpe_random_startup_fraction")]
    pub tpe_random_startup_fraction: f64,
    #[serde(default)]
    pub tpe_seed: Option<u64>,
    #[serde(default = "default_tpe_is_consensus_min_passing_windows")]
    pub tpe_is_consensus_min_passing_windows: usize,
}

impl WfoConfig {
    pub fn new(grid: GridSize) -> Self {
        let mut config = Self {
            run_id: format!(
                "{}-p{}-{}",
                Utc::now().format("%Y%m%dT%H%M%SZ"),
                std::process::id(),
                grid.as_str()
            ),
            grid,
            optimizer_mode: OptimizerMode::PointInTimeFoldLocal,
            preset: "binance-um-top7-2025".to_string(),
            symbols: Vec::new(),
            indicator_group: None,
            strategy_set: None,
            start: NaiveDate::from_ymd_opt(2025, 1, 1).expect("valid default start"),
            end: NaiveDate::from_ymd_opt(2026, 1, 1).expect("valid default end"),
            is_weeks: 4,
            oos_weeks: 1,
            step_weeks: 1,
            is_days: None,
            oos_days: None,
            step_days: None,
            gap_weeks: 0,
            gap_days: None,
            start_offset_days: 0,
            fold_start_index: 0,
            fold_limit: None,
            fixed_notional: 1_000.0,
            account_balance: DEFAULT_ACCOUNT_BALANCE,
            fees_bps: 0.0,
            min_profit_factor: DEFAULT_MIN_PROFIT_FACTOR,
            candidate_min_profit_factor: DEFAULT_CANDIDATE_MIN_PROFIT_FACTOR,
            tpe_trials: DEFAULT_TPE_TRIALS,
            tpe_random_startup_fraction: DEFAULT_TPE_RANDOM_STARTUP_FRACTION,
            tpe_seed: None,
            tpe_is_consensus_min_passing_windows: DEFAULT_TPE_IS_CONSENSUS_MIN_PASSING_WINDOWS,
        };
        if grid == GridSize::Tpe {
            config.is_weeks = 2;
        }
        config
    }

    fn effective_is_days(&self) -> i64 {
        self.is_days.unwrap_or(self.is_weeks * 7)
    }

    fn effective_oos_days(&self) -> i64 {
        self.oos_days.unwrap_or(self.oos_weeks * 7)
    }

    fn effective_step_days(&self) -> i64 {
        self.step_days.unwrap_or(self.step_weeks * 7)
    }

    fn effective_gap_days(&self) -> i64 {
        self.gap_days.unwrap_or(self.gap_weeks * 7)
    }
}

pub fn run_fill_model_experiment(options: FillModelExperimentOptions) -> Result<PathBuf> {
    if options.fold_limit == 0 {
        anyhow::bail!("fill-model experiment requires --fold-limit greater than zero");
    }

    let source_run_dirs = fill_model_source_run_dirs(&options.package_dir)?;
    let run_id = format!(
        "{}-p{}-fill-model-experiment",
        Utc::now().format("%Y%m%dT%H%M%SZ"),
        std::process::id()
    );
    let run_dir = PathBuf::from(RUNS_ROOT).join(run_id);
    fs::create_dir_all(&run_dir)?;
    write_json(
        run_dir.join("experiment_config.json"),
        &FillModelExperimentConfig {
            package_dir: options.package_dir.display().to_string(),
            fold_start_index: options.fold_start_index,
            fold_limit: options.fold_limit,
            offsets: options.offsets.clone(),
            current_fill_model: entry_fill_model_label(EntryFillModel::ImmediateOhlcTouch),
            experimental_fill_model: entry_fill_model_label(EntryFillModel::TriggerThenRetrace),
            notes: vec![
                "Production/default simulations are left unchanged.",
                "Experimental model requires a trigger breach first, no same-bar fill, then a later reverse breach through the resting fill price.",
                "This command replays selected OOS candidates only; it does not rerun Optuna.",
            ],
        },
    )?;
    append_event(
        &run_dir,
        "plan",
        "two-step trigger-then-retrace fill side experiment initialized",
    )?;

    let offset_filter = options.offsets.iter().copied().collect::<BTreeSet<_>>();
    let store = KlineStore::from_env()?;
    let mut comparison_rows = Vec::new();
    let mut source_rows = Vec::new();
    let mut trade_rows = Vec::new();
    let mut summary_trades =
        BTreeMap::<(String, Option<i64>, Option<usize>, String), Vec<Trade>>::new();
    let mut summary_selection_counts =
        BTreeMap::<(String, Option<i64>, Option<usize>, String), usize>::new();
    let mut summary_fixed_notional: Option<f64> = None;

    for source_run_dir in source_run_dirs {
        let source_run_id = source_run_dir
            .file_name()
            .and_then(|value| value.to_str())
            .with_context(|| format!("invalid source run path {}", source_run_dir.display()))?
            .to_string();
        let config = read_json::<WfoConfig>(source_run_dir.join("config.json"))
            .with_context(|| format!("read source config for {source_run_id}"))?;
        if !offset_filter.is_empty() && !offset_filter.contains(&config.start_offset_days) {
            continue;
        }
        if let Some(existing) = summary_fixed_notional {
            if (existing - config.fixed_notional).abs() > f64::EPSILON {
                anyhow::bail!(
                    "fill-model experiment does not yet support mixed fixed_notional values: {existing} and {}",
                    config.fixed_notional
                );
            }
        } else {
            summary_fixed_notional = Some(config.fixed_notional);
        }

        let selected_folds = selected_fold_range(
            read_csv::<Fold>(source_run_dir.join("folds.csv"))
                .with_context(|| format!("read folds for {source_run_id}"))?,
            options.fold_start_index,
            Some(options.fold_limit),
        );
        if selected_folds.is_empty() {
            continue;
        }
        let fold_by_index = selected_folds
            .iter()
            .map(|fold| (fold.index, *fold))
            .collect::<BTreeMap<_, _>>();
        let selected_fold_indices = fold_by_index.keys().copied().collect::<BTreeSet<_>>();

        let provenance_rows = read_csv::<OptimizerProvenanceRow>(
            source_run_dir.join(OPTIMIZER_PROVENANCE_CSV_FILE),
        )
        .with_context(|| format!("read optimizer provenance for {source_run_id}"))?
        .into_iter()
        .filter(|row| {
            row.selection_status == "selected" && selected_fold_indices.contains(&row.fold_index)
        })
        .collect::<Vec<_>>();
        if provenance_rows.is_empty() {
            source_rows.push(FillModelExperimentSourceRow {
                source_run_id,
                offset_days: config.start_offset_days,
                fold_indices: selected_fold_indices
                    .iter()
                    .map(|index| index.to_string())
                    .collect::<Vec<_>>()
                    .join("|"),
                selected_rows: 0,
            });
            continue;
        }

        let candidates = read_csv::<Candidate>(source_run_dir.join("candidates.csv"))
            .with_context(|| format!("read candidates for {source_run_id}"))?;
        let candidate_by_id = candidates
            .into_iter()
            .map(|candidate| (candidate.id, candidate))
            .collect::<BTreeMap<_, _>>();
        let symbols = provenance_rows
            .iter()
            .map(|row| row.symbol.clone())
            .collect::<BTreeSet<_>>();
        let mut bars_by_symbol = BTreeMap::<String, Vec<OhlcvBar>>::new();
        for symbol in symbols {
            let rows = store
                .load_range(&symbol, config.start, config.end)
                .with_context(|| format!("load market data for {symbol} in {source_run_id}"))?
                .iter()
                .map(OhlcvBar::from)
                .collect::<Vec<_>>();
            if rows.is_empty() {
                anyhow::bail!("no market data for {symbol} in {source_run_id}");
            }
            bars_by_symbol.insert(symbol, rows);
        }

        let mut simulation_cache = SimulationCache::default();
        let mut candidate_trade_cache = BTreeMap::<(String, usize, String), Vec<Trade>>::new();

        source_rows.push(FillModelExperimentSourceRow {
            source_run_id: source_run_id.clone(),
            offset_days: config.start_offset_days,
            fold_indices: selected_fold_indices
                .iter()
                .map(|index| index.to_string())
                .collect::<Vec<_>>()
                .join("|"),
            selected_rows: provenance_rows.len(),
        });

        for provenance in provenance_rows {
            let fold = fold_by_index.get(&provenance.fold_index).with_context(|| {
                format!(
                    "missing fold {} in selected fold map for {source_run_id}",
                    provenance.fold_index
                )
            })?;
            let candidate = candidate_by_id
                .get(&provenance.selected_candidate_id)
                .with_context(|| {
                    format!(
                        "missing candidate {} for {} {} fold {}",
                        provenance.selected_candidate_id,
                        source_run_id,
                        provenance.symbol,
                        provenance.fold_index
                    )
                })?;
            let bars = bars_by_symbol.get(&provenance.symbol).with_context(|| {
                format!("missing loaded bars for {} in {source_run_id}", provenance.symbol)
            })?;

            let current_all_trades = fill_model_candidate_trades(
                &mut candidate_trade_cache,
                &mut simulation_cache,
                &config,
                &selected_folds,
                &provenance.symbol,
                bars,
                candidate,
                EntryFillModel::ImmediateOhlcTouch,
            )?;
            let experimental_all_trades = fill_model_candidate_trades(
                &mut candidate_trade_cache,
                &mut simulation_cache,
                &config,
                &selected_folds,
                &provenance.symbol,
                bars,
                candidate,
                EntryFillModel::TriggerThenRetrace,
            )?;
            let current_oos_trades = oos_trades_for_fold(&current_all_trades, fold);
            let experimental_oos_trades = oos_trades_for_fold(&experimental_all_trades, fold);
            let current_metrics =
                fill_model_experiment_metrics(&current_oos_trades, config.fixed_notional);
            let experimental_metrics =
                fill_model_experiment_metrics(&experimental_oos_trades, config.fixed_notional);
            let current_label =
                entry_fill_model_label(EntryFillModel::ImmediateOhlcTouch).to_string();
            let experimental_label =
                entry_fill_model_label(EntryFillModel::TriggerThenRetrace).to_string();

            comparison_rows.push(FillModelExperimentComparisonRow {
                source_run_id: source_run_id.clone(),
                offset_days: config.start_offset_days,
                fold_index: fold.index,
                oos_start: utc_date_string(fold.oos_start_ms),
                oos_end: utc_date_string(fold.oos_end_ms),
                symbol: provenance.symbol.clone(),
                candidate_id: candidate.id,
                indicator: candidate.indicator.as_str().to_string(),
                timeframe: candidate.timeframe.as_str().to_string(),
                entry_mode: entry_mode_label(candidate.entry_mode).to_string(),
                signal_polarity: candidate.signal_polarity,
                params_signature: provenance.params_signature.clone(),
                provenance_oos_pnl: provenance.oos_total_pnl,
                provenance_oos_trades: provenance.oos_trades,
                provenance_oos_profit_factor: provenance.oos_profit_factor,
                current_oos_pnl: current_metrics.total_pnl,
                current_oos_trades: current_metrics.trades,
                current_oos_profit_factor: current_metrics.profit_factor,
                current_oos_max_drawdown_pct: current_metrics.max_drawdown_pct,
                current_minus_provenance_pnl: current_metrics.total_pnl
                    - provenance.oos_total_pnl,
                experimental_oos_pnl: experimental_metrics.total_pnl,
                experimental_oos_trades: experimental_metrics.trades,
                experimental_oos_profit_factor: experimental_metrics.profit_factor,
                experimental_oos_max_drawdown_pct: experimental_metrics.max_drawdown_pct,
                experimental_minus_current_pnl: experimental_metrics.total_pnl
                    - current_metrics.total_pnl,
                experimental_minus_current_trades: experimental_metrics.trades as isize
                    - current_metrics.trades as isize,
            });

            append_fill_model_trade_rows(
                &mut trade_rows,
                &current_label,
                &source_run_id,
                config.start_offset_days,
                fold.index,
                candidate.id,
                &current_oos_trades,
            );
            append_fill_model_trade_rows(
                &mut trade_rows,
                &experimental_label,
                &source_run_id,
                config.start_offset_days,
                fold.index,
                candidate.id,
                &experimental_oos_trades,
            );
            add_fill_model_summary_trades(
                &mut summary_trades,
                &mut summary_selection_counts,
                &current_label,
                config.start_offset_days,
                fold.index,
                &current_oos_trades,
            );
            add_fill_model_summary_trades(
                &mut summary_trades,
                &mut summary_selection_counts,
                &experimental_label,
                config.start_offset_days,
                fold.index,
                &experimental_oos_trades,
            );
        }
    }

    let summary_rows = fill_model_summary_rows(
        summary_trades,
        summary_selection_counts,
        summary_fixed_notional.unwrap_or(1_000.0),
    );
    write_csv(run_dir.join("source_runs.csv"), &source_rows)?;
    write_csv(run_dir.join("comparison.csv"), &comparison_rows)?;
    write_csv(run_dir.join("summary.csv"), &summary_rows)?;
    write_csv(run_dir.join("oos_trades.csv"), &trade_rows)?;
    append_event(
        &run_dir,
        "complete",
        &format!(
            "fill model experiment complete: {} comparison rows",
            comparison_rows.len()
        ),
    )?;
    Ok(run_dir)
}

fn fill_model_source_run_dirs(package_dir: &Path) -> Result<Vec<PathBuf>> {
    if package_dir.join("config.json").is_file() {
        return Ok(vec![package_dir.to_path_buf()]);
    }

    let root = if package_dir.join("source_runs").is_dir() {
        package_dir.join("source_runs")
    } else {
        package_dir.to_path_buf()
    };
    let mut dirs = fs::read_dir(&root)
        .with_context(|| format!("read source run directory {}", root.display()))?
        .filter_map(|entry| entry.ok().map(|entry| entry.path()))
        .filter(|path| {
            path.is_dir()
                && path.join("config.json").is_file()
                && path.join(OPTIMIZER_PROVENANCE_CSV_FILE).is_file()
        })
        .collect::<Vec<_>>();
    dirs.sort();
    if dirs.is_empty() {
        anyhow::bail!(
            "no source runs with config.json and {} found under {}",
            OPTIMIZER_PROVENANCE_CSV_FILE,
            root.display()
        );
    }
    Ok(dirs)
}

fn fill_model_candidate_trades(
    trade_cache: &mut BTreeMap<(String, usize, String), Vec<Trade>>,
    simulation_cache: &mut SimulationCache,
    config: &WfoConfig,
    folds: &[Fold],
    symbol: &str,
    bars: &[OhlcvBar],
    candidate: &Candidate,
    fill_model: EntryFillModel,
) -> Result<Vec<Trade>> {
    let fill_model_label = entry_fill_model_label(fill_model).to_string();
    let key = (symbol.to_string(), candidate.id, fill_model_label);
    if let Some(trades) = trade_cache.get(&key) {
        return Ok(trades.clone());
    }

    let mut prepared =
        prepare_candidate_simulation(symbol, bars, candidate, config, simulation_cache)?;
    prepared.execution.entry_fill_model = fill_model;
    let result = simulate_prepared_candidate(bars, &prepared, folds);
    let trades = result.trades;
    trade_cache.insert(key, trades.clone());
    Ok(trades)
}

fn fill_model_experiment_metrics(
    trades: &[Trade],
    fixed_notional: f64,
) -> FillModelExperimentMetrics {
    let stats = closed_trade_stats(trades, fixed_notional);
    FillModelExperimentMetrics {
        total_pnl: trades.iter().map(|trade| trade.pnl).sum(),
        net_return_pct: stats.net_return_pct,
        max_drawdown_pct: stats.max_drawdown_pct,
        profit_factor: stats.profit_factor,
        trades: stats.trades,
    }
}

fn append_fill_model_trade_rows(
    rows: &mut Vec<FillModelExperimentTradeRow>,
    fill_model: &str,
    source_run_id: &str,
    offset_days: i64,
    fold_index: usize,
    candidate_id: usize,
    trades: &[Trade],
) {
    rows.extend(trades.iter().map(|trade| FillModelExperimentTradeRow {
        fill_model: fill_model.to_string(),
        source_run_id: source_run_id.to_string(),
        offset_days,
        fold_index,
        symbol: trade.symbol.clone(),
        candidate_id,
        entry_time_ms: trade.entry_time_ms,
        exit_time_ms: trade.exit_time_ms,
        side: format!("{:?}", trade.side),
        entry_price: trade.entry_price,
        exit_price: trade.exit_price,
        quantity: trade.quantity,
        pnl: trade.pnl,
        return_pct: trade.return_pct,
        exit_reason: trade.exit_reason.clone(),
    }));
}

fn add_fill_model_summary_trades(
    summary_trades: &mut BTreeMap<(String, Option<i64>, Option<usize>, String), Vec<Trade>>,
    summary_selection_counts: &mut BTreeMap<(String, Option<i64>, Option<usize>, String), usize>,
    fill_model: &str,
    offset_days: i64,
    fold_index: usize,
    trades: &[Trade],
) {
    for key in [
        (
            "overall".to_string(),
            None,
            None,
            fill_model.to_string(),
        ),
        (
            "offset".to_string(),
            Some(offset_days),
            None,
            fill_model.to_string(),
        ),
        (
            "fold".to_string(),
            Some(offset_days),
            Some(fold_index),
            fill_model.to_string(),
        ),
    ] {
        *summary_selection_counts.entry(key.clone()).or_default() += 1;
        summary_trades
            .entry(key)
            .or_default()
            .extend(trades.iter().cloned());
    }
}

fn fill_model_summary_rows(
    summary_trades: BTreeMap<(String, Option<i64>, Option<usize>, String), Vec<Trade>>,
    summary_selection_counts: BTreeMap<(String, Option<i64>, Option<usize>, String), usize>,
    fixed_notional: f64,
) -> Vec<FillModelExperimentSummaryRow> {
    summary_trades
        .into_iter()
        .map(|((scope, offset_days, fold_index, fill_model), trades)| {
            let selections = summary_selection_counts
                .get(&(scope.clone(), offset_days, fold_index, fill_model.clone()))
                .copied()
                .unwrap_or_default();
            let stats =
                fill_model_experiment_metrics(&trades, fixed_notional * selections.max(1) as f64);
            FillModelExperimentSummaryRow {
                selections,
                scope,
                offset_days,
                fold_index,
                fill_model,
                trades: stats.trades,
                total_pnl: stats.total_pnl,
                net_return_pct: stats.net_return_pct,
                profit_factor: stats.profit_factor,
                max_drawdown_pct: stats.max_drawdown_pct,
            }
        })
        .collect()
}

fn entry_fill_model_label(fill_model: EntryFillModel) -> &'static str {
    match fill_model {
        EntryFillModel::ImmediateOhlcTouch => "immediate_ohlc_touch",
        EntryFillModel::TriggerThenRetrace => "trigger_then_retrace",
    }
}

fn entry_mode_label(entry_mode: EntryMode) -> &'static str {
    match entry_mode {
        EntryMode::Pullback => "pullback",
        EntryMode::Breakout => "breakout",
    }
}

#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct WfoRunOptions {
    pub symbols: Vec<String>,
    pub indicator_group: Option<String>,
    pub strategy_set: Option<String>,
    pub optimizer_mode: Option<OptimizerMode>,
    pub resume_run_id: Option<String>,
    pub min_profit_factor: Option<f64>,
    pub candidate_min_profit_factor: Option<f64>,
    pub account_balance: Option<f64>,
    pub fees_bps: Option<f64>,
    pub tpe_trials: Option<usize>,
    pub tpe_random_startup_fraction: Option<f64>,
    pub tpe_seed: Option<u64>,
    pub tpe_is_consensus_min_passing_windows: Option<usize>,
    pub is_weeks: Option<i64>,
    pub is_days: Option<i64>,
    pub oos_weeks: Option<i64>,
    pub oos_days: Option<i64>,
    pub step_weeks: Option<i64>,
    pub step_days: Option<i64>,
    pub gap_weeks: Option<i64>,
    pub gap_days: Option<i64>,
    pub start_offset_days: Option<i64>,
    pub fold_start_index: Option<usize>,
    pub fold_limit: Option<usize>,
    pub start_date: Option<String>,
    pub end_date: Option<String>,
}

#[derive(Debug, Clone)]
pub struct SpaceScanOptions {
    pub strategy_set: String,
    pub symbols: Vec<String>,
    pub fold_index: usize,
    pub start_offset_days: i64,
    pub trials: usize,
    pub is_weeks: i64,
    pub oos_weeks: i64,
    pub step_weeks: i64,
    pub gap_weeks: i64,
}

#[derive(Debug, Clone)]
pub struct DailyOffsetEnsembleOptions {
    pub name: String,
    pub offset_runs: Vec<DailyOffsetRunSpec>,
    pub account_balance: f64,
}

#[derive(Debug, Clone)]
pub struct DailyOffsetRunSpec {
    pub offset_days: i64,
    pub run_id: String,
}

#[derive(Debug, Clone)]
pub struct FillModelExperimentOptions {
    pub package_dir: PathBuf,
    pub fold_start_index: usize,
    pub fold_limit: usize,
    pub offsets: Vec<i64>,
}

#[derive(Debug, Clone, Serialize)]
struct FillModelExperimentConfig {
    package_dir: String,
    fold_start_index: usize,
    fold_limit: usize,
    offsets: Vec<i64>,
    current_fill_model: &'static str,
    experimental_fill_model: &'static str,
    notes: Vec<&'static str>,
}

#[derive(Debug, Clone, Serialize)]
struct FillModelExperimentSourceRow {
    source_run_id: String,
    offset_days: i64,
    fold_indices: String,
    selected_rows: usize,
}

#[derive(Debug, Clone, Serialize)]
struct FillModelExperimentComparisonRow {
    source_run_id: String,
    offset_days: i64,
    fold_index: usize,
    oos_start: String,
    oos_end: String,
    symbol: String,
    candidate_id: usize,
    indicator: String,
    timeframe: String,
    entry_mode: String,
    signal_polarity: i8,
    params_signature: String,
    provenance_oos_pnl: f64,
    provenance_oos_trades: usize,
    provenance_oos_profit_factor: f64,
    current_oos_pnl: f64,
    current_oos_trades: usize,
    current_oos_profit_factor: f64,
    current_oos_max_drawdown_pct: f64,
    current_minus_provenance_pnl: f64,
    experimental_oos_pnl: f64,
    experimental_oos_trades: usize,
    experimental_oos_profit_factor: f64,
    experimental_oos_max_drawdown_pct: f64,
    experimental_minus_current_pnl: f64,
    experimental_minus_current_trades: isize,
}

#[derive(Debug, Clone, Serialize)]
struct FillModelExperimentSummaryRow {
    scope: String,
    offset_days: Option<i64>,
    fold_index: Option<usize>,
    fill_model: String,
    selections: usize,
    trades: usize,
    total_pnl: f64,
    net_return_pct: f64,
    profit_factor: f64,
    max_drawdown_pct: f64,
}

#[derive(Debug, Clone, Serialize)]
struct FillModelExperimentTradeRow {
    fill_model: String,
    source_run_id: String,
    offset_days: i64,
    fold_index: usize,
    symbol: String,
    candidate_id: usize,
    entry_time_ms: i64,
    exit_time_ms: i64,
    side: String,
    entry_price: f64,
    exit_price: f64,
    quantity: f64,
    pnl: f64,
    return_pct: f64,
    exit_reason: String,
}

#[derive(Debug, Clone, Copy)]
struct FillModelExperimentMetrics {
    total_pnl: f64,
    net_return_pct: f64,
    max_drawdown_pct: f64,
    profit_factor: f64,
    trades: usize,
}

fn default_min_profit_factor() -> f64 {
    DEFAULT_MIN_PROFIT_FACTOR
}

fn default_candidate_min_profit_factor() -> f64 {
    DEFAULT_CANDIDATE_MIN_PROFIT_FACTOR
}

fn default_account_balance() -> f64 {
    DEFAULT_ACCOUNT_BALANCE
}

fn default_tpe_is_consensus_min_passing_windows() -> usize {
    DEFAULT_TPE_IS_CONSENSUS_MIN_PASSING_WINDOWS
}

fn default_min_edge_t_stat() -> f64 {
    DEFAULT_MIN_EDGE_T_STAT
}

fn default_tpe_trials() -> usize {
    DEFAULT_TPE_TRIALS
}

fn default_tpe_random_startup_fraction() -> f64 {
    DEFAULT_TPE_RANDOM_STARTUP_FRACTION
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum RunPhase {
    Planning,
    LoadingData,
    Simulating,
    WritingArtifacts,
    Complete,
    Failed,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum OptimizerMode {
    PointInTimeFoldLocal,
    RetrospectiveGlobalResearchOnly,
}

impl OptimizerMode {
    pub fn as_str(self) -> &'static str {
        match self {
            Self::PointInTimeFoldLocal => "point_in_time_fold_local",
            Self::RetrospectiveGlobalResearchOnly => "retrospective_global_research_only",
        }
    }
}

impl std::fmt::Display for OptimizerMode {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.write_str(self.as_str())
    }
}

impl std::str::FromStr for OptimizerMode {
    type Err = anyhow::Error;

    fn from_str(value: &str) -> std::result::Result<Self, Self::Err> {
        match value.trim().to_ascii_lowercase().as_str() {
            "point_in_time_fold_local" | "point-in-time-fold-local" | "pit" | "fold-local" => {
                Ok(Self::PointInTimeFoldLocal)
            }
            "retrospective_global_research_only"
            | "retrospective-global-research-only"
            | "global"
            | "research-only" => Ok(Self::RetrospectiveGlobalResearchOnly),
            other => anyhow::bail!(
                "unknown optimizer mode {other}; supported: point_in_time_fold_local, retrospective_global_research_only"
            ),
        }
    }
}

fn missing_optimizer_mode_is_research_only() -> OptimizerMode {
    OptimizerMode::RetrospectiveGlobalResearchOnly
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RunStatus {
    pub run_id: String,
    pub phase: RunPhase,
    pub progress_pct: f64,
    pub message: String,
    pub active_symbol: Option<String>,
    pub active_indicator: Option<String>,
    pub active_timeframe: Option<String>,
    #[serde(default)]
    pub active_offset_days: Option<i64>,
    #[serde(default)]
    pub active_fold_index: Option<usize>,
    #[serde(default)]
    pub active_fold_count: Option<usize>,
    #[serde(default)]
    pub optimizer_mode: Option<String>,
    pub eta_seconds: Option<u64>,
    pub latest_test_state: String,
    pub updated_at: DateTime<Utc>,
}

#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize)]
pub struct Fold {
    pub index: usize,
    pub is_start_ms: i64,
    pub is_end_ms: i64,
    pub oos_start_ms: i64,
    pub oos_end_ms: i64,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Candidate {
    pub id: usize,
    pub indicator: IndicatorKind,
    pub timeframe: Timeframe,
    #[serde(default = "default_signal_polarity")]
    pub signal_polarity: i8,
    #[serde(default)]
    pub entry_mode: EntryMode,
    pub lookback: usize,
    pub atr_period: usize,
    pub entry_atr_multiple: f64,
    pub stop_atr_multiple: f64,
    pub target_atr_multiple: f64,
    pub time_stop_bars: Option<usize>,
    #[serde(default)]
    pub hurst_min: Option<f64>,
    #[serde(default)]
    pub hurst_max: Option<f64>,
    #[serde(default)]
    pub shannon_max: Option<f64>,
    #[serde(default = "default_strategy_4448_kama1_er")]
    pub strategy_4448_kama1_er: usize,
    #[serde(default = "default_strategy_4448_kama1_short")]
    pub strategy_4448_kama1_short: usize,
    #[serde(default = "default_strategy_4448_kama1_long")]
    pub strategy_4448_kama1_long: usize,
    #[serde(default = "default_strategy_4448_kama2_er")]
    pub strategy_4448_kama2_er: usize,
    #[serde(default = "default_strategy_4448_kama2_short")]
    pub strategy_4448_kama2_short: usize,
    #[serde(default = "default_strategy_4448_kama2_long")]
    pub strategy_4448_kama2_long: usize,
    #[serde(default = "default_strategy_4448_count_bars")]
    pub strategy_4448_count_bars: usize,
}

fn default_signal_polarity() -> i8 {
    1
}

fn default_strategy_4448_kama1_er() -> usize {
    STRATEGY_4448_SOURCE_KAMA1_ER
}

fn default_strategy_4448_kama1_short() -> usize {
    STRATEGY_4448_SOURCE_KAMA1_SHORT
}

fn default_strategy_4448_kama1_long() -> usize {
    STRATEGY_4448_SOURCE_KAMA1_LONG
}

fn default_strategy_4448_kama2_er() -> usize {
    STRATEGY_4448_SOURCE_KAMA2_ER
}

fn default_strategy_4448_kama2_short() -> usize {
    STRATEGY_4448_SOURCE_KAMA2_SHORT
}

fn default_strategy_4448_kama2_long() -> usize {
    STRATEGY_4448_SOURCE_KAMA2_LONG
}

fn default_strategy_4448_count_bars() -> usize {
    STRATEGY_4448_SOURCE_COUNT_BARS
}

impl Default for Candidate {
    fn default() -> Self {
        Self {
            id: 0,
            indicator: IndicatorKind::Roc,
            timeframe: Timeframe::M5,
            signal_polarity: default_signal_polarity(),
            entry_mode: EntryMode::Pullback,
            lookback: 12,
            atr_period: 14,
            entry_atr_multiple: 0.5,
            stop_atr_multiple: 1.5,
            target_atr_multiple: 3.0,
            time_stop_bars: Some(24),
            hurst_min: None,
            hurst_max: None,
            shannon_max: None,
            strategy_4448_kama1_er: STRATEGY_4448_SOURCE_KAMA1_ER,
            strategy_4448_kama1_short: STRATEGY_4448_SOURCE_KAMA1_SHORT,
            strategy_4448_kama1_long: STRATEGY_4448_SOURCE_KAMA1_LONG,
            strategy_4448_kama2_er: STRATEGY_4448_SOURCE_KAMA2_ER,
            strategy_4448_kama2_short: STRATEGY_4448_SOURCE_KAMA2_SHORT,
            strategy_4448_kama2_long: STRATEGY_4448_SOURCE_KAMA2_LONG,
            strategy_4448_count_bars: STRATEGY_4448_SOURCE_COUNT_BARS,
        }
    }
}

impl Candidate {
    fn strategy_4448_params(&self) -> Strategy4448KamaKerParams {
        Strategy4448KamaKerParams {
            kama1_er: self.strategy_4448_kama1_er,
            kama1_short: self.strategy_4448_kama1_short,
            kama1_long: self.strategy_4448_kama1_long,
            ker_period: self.lookback,
            kama2_er: self.strategy_4448_kama2_er,
            kama2_short: self.strategy_4448_kama2_short,
            kama2_long: self.strategy_4448_kama2_long,
            count_bars: self.strategy_4448_count_bars,
            atr_period: self.atr_period,
        }
    }

    fn signal_cache_key(&self) -> String {
        if self.indicator == IndicatorKind::Strategy4448KamaKer {
            format!(
                "{}:{}:{}:{}:{}:{}:{}:{}:{}",
                self.lookback,
                self.atr_period,
                self.strategy_4448_kama1_er,
                self.strategy_4448_kama1_short,
                self.strategy_4448_kama1_long,
                self.strategy_4448_kama2_er,
                self.strategy_4448_kama2_short,
                self.strategy_4448_kama2_long,
                self.strategy_4448_count_bars
            )
        } else {
            format!("{}:{}", self.lookback, self.atr_period)
        }
    }
}

fn exit_geometry_rejection_reason(candidate: &Candidate) -> Option<&'static str> {
    let stop = candidate.stop_atr_multiple;
    let target = candidate.target_atr_multiple;
    if !stop.is_finite()
        || !target.is_finite()
        || !(MIN_EXIT_STOP_ATR_MULTIPLE..=MAX_EXIT_STOP_ATR_MULTIPLE).contains(&stop)
        || !(MIN_EXIT_TARGET_ATR_MULTIPLE..=MAX_EXIT_TARGET_ATR_MULTIPLE).contains(&target)
        || target / stop.max(f64::EPSILON) > MAX_EXIT_TARGET_STOP_RATIO
    {
        Some(BAD_EXIT_GEOMETRY_REJECTION)
    } else {
        None
    }
}

#[derive(Debug, Clone, Copy)]
struct RegimeGateProfile {
    hurst_min: Option<f64>,
    hurst_max: Option<f64>,
    shannon_max: Option<f64>,
}

impl RegimeGateProfile {
    const fn none() -> Self {
        Self {
            hurst_min: None,
            hurst_max: None,
            shannon_max: None,
        }
    }

    const fn trend_low_entropy() -> Self {
        Self {
            hurst_min: Some(0.52),
            hurst_max: None,
            shannon_max: Some(0.85),
        }
    }

    const fn strict_trend_low_entropy() -> Self {
        Self {
            hurst_min: Some(0.58),
            hurst_max: None,
            shannon_max: Some(0.75),
        }
    }
}

#[derive(Debug, Clone, Copy)]
struct ExitProfile {
    stop_atr_multiple: f64,
    target_atr_multiple: f64,
    time_stop_bars: Option<usize>,
    gate: RegimeGateProfile,
}

impl ExitProfile {
    const fn new(
        stop_atr_multiple: f64,
        target_atr_multiple: f64,
        time_stop_bars: Option<usize>,
        gate: RegimeGateProfile,
    ) -> Self {
        Self {
            stop_atr_multiple,
            target_atr_multiple,
            time_stop_bars,
            gate,
        }
    }
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct CandidateScore {
    pub candidate_id: usize,
    pub symbol: String,
    pub fold_index: usize,
    pub net_return_pct: f64,
    pub max_drawdown_pct: f64,
    pub weekly_profit_fraction: f64,
    #[serde(default)]
    pub profit_factor: f64,
    #[serde(default = "default_min_profit_factor")]
    pub min_profit_factor: f64,
    #[serde(default)]
    pub average_trade_return_pct: f64,
    #[serde(default)]
    pub min_average_trade_return_pct: f64,
    #[serde(default)]
    pub trade_return_stddev_pct: f64,
    #[serde(default)]
    pub edge_t_stat: f64,
    #[serde(default = "default_min_edge_t_stat")]
    pub min_edge_t_stat: f64,
    #[serde(default)]
    pub entry_attempts: usize,
    #[serde(default)]
    pub filled_entries: usize,
    #[serde(default)]
    pub fill_rate_pct: f64,
    #[serde(default = "default_min_fill_rate_score_pct")]
    pub min_fill_rate_pct: f64,
    #[serde(default)]
    pub entry_day_pct: f64,
    #[serde(default = "default_min_candidate_entry_day_pct")]
    pub min_entry_day_pct: f64,
    #[serde(default)]
    pub entry_week_pct: f64,
    #[serde(default = "default_min_candidate_entry_week_pct")]
    pub min_entry_week_pct: f64,
    #[serde(default)]
    pub longest_no_entry_gap_days: usize,
    #[serde(default = "default_max_candidate_no_entry_gap_days")]
    pub max_no_entry_gap_days: usize,
    pub trades: usize,
    #[serde(default)]
    pub min_trades: usize,
    #[serde(default)]
    pub max_trades: usize,
    #[serde(default)]
    pub trade_fit: String,
    #[serde(default)]
    pub quality_fit: String,
    pub score: f64,
}

fn default_min_fill_rate_score_pct() -> f64 {
    MIN_FILL_RATE_SCORE_PCT
}

fn default_min_candidate_entry_day_pct() -> f64 {
    MIN_CANDIDATE_ENTRY_DAY_PCT
}

fn default_min_candidate_entry_week_pct() -> f64 {
    MIN_CANDIDATE_ENTRY_WEEK_PCT
}

fn default_max_candidate_no_entry_gap_days() -> usize {
    MAX_CANDIDATE_NO_ENTRY_GAP_DAYS
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct RunSummary {
    pub run_id: String,
    pub grid: GridSize,
    pub folds: usize,
    pub candidates: usize,
    pub trades: usize,
    #[serde(default)]
    pub fixed_notional: f64,
    #[serde(default = "default_account_balance")]
    pub account_balance: f64,
    #[serde(default)]
    pub total_pnl: f64,
    pub net_return_pct: f64,
    pub max_drawdown_pct: f64,
    pub sharpe: f64,
    pub sortino: f64,
    pub weekly_consistency: f64,
    pub average_trade: f64,
    pub exposure_pct: f64,
    #[serde(default)]
    pub average_exposure_notional: f64,
    #[serde(default)]
    pub average_long_exposure_notional: f64,
    #[serde(default)]
    pub average_short_exposure_notional: f64,
    #[serde(default)]
    pub average_net_exposure_notional: f64,
    #[serde(default)]
    pub max_exposure_notional: f64,
    #[serde(default)]
    pub max_long_exposure_notional: f64,
    #[serde(default)]
    pub max_short_exposure_notional: f64,
    #[serde(default)]
    pub max_abs_net_exposure_notional: f64,
    #[serde(default)]
    pub max_concurrent_positions: usize,
    #[serde(default)]
    pub max_concurrent_long_positions: usize,
    #[serde(default)]
    pub max_concurrent_short_positions: usize,
    #[serde(default)]
    pub long_exposure_pct: f64,
    #[serde(default)]
    pub short_exposure_pct: f64,
    #[serde(default)]
    pub longest_stagnation_minutes: i64,
    #[serde(default)]
    pub longest_stagnation_days: f64,
    #[serde(default)]
    pub return_to_drawdown_ratio: f64,
    #[serde(default)]
    pub smoothness_score: f64,
    pub best_indicator: String,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct AccountEquitySample {
    pub timestamp_ms: i64,
    pub realized_pnl: f64,
    pub unrealized_pnl: f64,
    pub equity: f64,
    pub drawdown: f64,
    pub drawdown_pct: f64,
    pub open_positions: usize,
    pub long_positions: usize,
    pub short_positions: usize,
    pub exposure_notional: f64,
    pub long_exposure_notional: f64,
    pub short_exposure_notional: f64,
    pub net_exposure_notional: f64,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct StagnationPeriod {
    pub peak_time_ms: i64,
    pub start_time_ms: i64,
    pub recovery_time_ms: Option<i64>,
    pub duration_minutes: i64,
    pub recovered: bool,
    pub peak_equity: f64,
    pub trough_equity: f64,
    pub max_drawdown: f64,
    pub max_drawdown_pct: f64,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct AccountCurveStats {
    pub samples: usize,
    pub total_pnl: f64,
    pub net_return_pct: f64,
    pub max_drawdown: f64,
    pub max_drawdown_pct: f64,
    pub exposure_pct: f64,
    pub long_exposure_pct: f64,
    pub short_exposure_pct: f64,
    pub average_exposure_notional: f64,
    pub average_long_exposure_notional: f64,
    pub average_short_exposure_notional: f64,
    pub average_net_exposure_notional: f64,
    pub max_exposure_notional: f64,
    pub max_long_exposure_notional: f64,
    pub max_short_exposure_notional: f64,
    pub max_abs_net_exposure_notional: f64,
    pub max_concurrent_positions: usize,
    pub max_concurrent_long_positions: usize,
    pub max_concurrent_short_positions: usize,
    pub longest_stagnation_minutes: i64,
    #[serde(default)]
    pub longest_stagnation_days: f64,
    #[serde(default)]
    pub return_to_drawdown_ratio: f64,
    #[serde(default)]
    pub smoothness_score: f64,
}

#[derive(Debug, Clone)]
struct AccountArtifacts {
    equity: Vec<AccountEquitySample>,
    stagnation: Vec<StagnationPeriod>,
    stats: AccountCurveStats,
}

#[derive(Debug, Clone)]
struct ManagedRunArtifacts {
    summary: RunSummary,
    trades: Vec<Trade>,
    account_artifacts: AccountArtifacts,
}

#[derive(Debug, Clone)]
struct PrimaryArtifactSelection {
    trades: Vec<Trade>,
    scores: Vec<CandidateScore>,
    best_indicator: String,
    best_fold_trades: Option<Vec<Trade>>,
    best_fold_scores: Option<Vec<CandidateScore>>,
    risk_managed_trades: Option<Vec<Trade>>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DashboardPlan {
    pub config: WfoConfig,
    pub folds: Vec<Fold>,
    pub candidate_count: usize,
    pub practical_indicators: Vec<String>,
    pub regime_gates: Vec<String>,
    pub not_applicable_v1: Vec<String>,
    pub implementation_status: Vec<IndicatorImplementationRow>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct IndicatorImplementationRow {
    pub indicator: String,
    pub family: String,
    pub implementation_status: String,
    pub runnable: bool,
    pub grid_candidates: usize,
    pub note: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RunListItem {
    pub run_id: String,
    pub path: String,
    pub status: Option<RunStatus>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct StrategyRow {
    pub indicator: String,
    pub timeframe: String,
    #[serde(default = "unknown_implementation_status")]
    pub implementation_status: String,
    #[serde(default)]
    pub implementation_note: String,
    #[serde(default)]
    pub runnable: bool,
    pub parameter_candidates: usize,
    pub status: String,
    pub progress_pct: f64,
    #[serde(default)]
    pub progress_label: String,
    pub folds_scored: usize,
    pub best_score: f64,
    pub net_return_pct: f64,
    pub max_drawdown_pct: f64,
    pub trades: usize,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct StrategyOosBlock {
    pub indicator: String,
    pub timeframe: String,
    pub status: String,
    pub progress_pct: f64,
    pub progress_label: String,
    pub parameter_candidates: usize,
    pub portfolio: Option<StrategyOosMetrics>,
    #[serde(default)]
    pub candidate_gate: StrategyCandidateGate,
    pub symbols: Vec<StrategyOosSymbolResult>,
    #[serde(default)]
    pub risk_managed_portfolio: Option<StrategyOosMetrics>,
    #[serde(default)]
    pub risk_managed_symbols: Vec<StrategyOosSymbolResult>,
    #[serde(default)]
    pub risk_overlay: Option<StrategyRiskOverlay>,
    #[serde(default)]
    pub selected_candidates: Vec<StrategyOosSelection>,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct StrategyCandidateGate {
    pub min_oos_trades: usize,
    pub min_profit_factor: f64,
    #[serde(default)]
    pub min_entry_day_pct: f64,
    #[serde(default)]
    pub min_entry_week_pct: f64,
    #[serde(default)]
    pub max_no_entry_gap_days: usize,
    pub pass_min_trades: bool,
    pub pass_net_positive: bool,
    pub pass_profit_factor: bool,
    #[serde(default)]
    pub pass_entry_days: bool,
    #[serde(default)]
    pub pass_entry_weeks: bool,
    #[serde(default)]
    pub pass_no_entry_gap: bool,
    #[serde(default)]
    pub pass_symbol_participation: bool,
    pub pass_candidate: bool,
    pub status: String,
    pub reason: String,
}

impl Default for StrategyCandidateGate {
    fn default() -> Self {
        Self {
            min_oos_trades: MIN_CANDIDATE_OOS_TRADES,
            min_profit_factor: DEFAULT_CANDIDATE_MIN_PROFIT_FACTOR,
            min_entry_day_pct: MIN_CANDIDATE_ENTRY_DAY_PCT,
            min_entry_week_pct: MIN_CANDIDATE_ENTRY_WEEK_PCT,
            max_no_entry_gap_days: MAX_CANDIDATE_NO_ENTRY_GAP_DAYS,
            pass_min_trades: false,
            pass_net_positive: false,
            pass_profit_factor: false,
            pass_entry_days: false,
            pass_entry_weeks: false,
            pass_no_entry_gap: false,
            pass_symbol_participation: false,
            pass_candidate: false,
            status: "pending".to_string(),
            reason: "OOS result pending".to_string(),
        }
    }
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct StrategyRiskOverlay {
    pub loss_trigger_pct: f64,
    pub pause_folds: usize,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct StrategyOosMetrics {
    pub net_return_pct: f64,
    pub total_pnl: f64,
    pub max_drawdown_pct: f64,
    pub trades: usize,
    #[serde(default)]
    pub total_oos_days: usize,
    #[serde(default)]
    pub entry_days: usize,
    #[serde(default)]
    pub no_entry_days: usize,
    #[serde(default)]
    pub entry_day_pct: f64,
    #[serde(default)]
    pub total_oos_weeks: usize,
    #[serde(default)]
    pub entry_weeks: usize,
    #[serde(default)]
    pub no_entry_weeks: usize,
    #[serde(default)]
    pub entry_week_pct: f64,
    #[serde(default)]
    pub longest_no_entry_gap_days: usize,
    pub win_rate: f64,
    pub profit_factor: f64,
    pub sharpe: f64,
    pub equity_curve: Vec<StrategyCurvePoint>,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct StrategyOosSymbolResult {
    pub symbol: String,
    pub metrics: StrategyOosMetrics,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct StrategyOosSelection {
    pub symbol: String,
    pub fold_index: usize,
    pub candidate_id: usize,
    pub candidate: Option<Candidate>,
    pub score: CandidateScore,
    pub oos_trades: usize,
    pub oos_total_pnl: f64,
    pub oos_net_return_pct: f64,
}

#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize)]
pub struct StrategyCurvePoint {
    pub timestamp_ms: i64,
    pub equity: f64,
}

fn unknown_implementation_status() -> String {
    "unknown".to_string()
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RunHistoryRow {
    pub run_id: String,
    pub phase: String,
    pub progress_pct: f64,
    pub grid: Option<String>,
    #[serde(default)]
    pub optimizer_mode: Option<String>,
    pub folds: Option<usize>,
    pub candidates: Option<usize>,
    pub trades: Option<usize>,
    pub net_return_pct: Option<f64>,
    pub max_drawdown_pct: Option<f64>,
    pub sharpe: Option<f64>,
    pub updated_at: Option<DateTime<Utc>>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ArtifactRow {
    pub name: String,
    pub path: String,
    pub bytes: u64,
    pub rows: Option<usize>,
    pub modified_at: Option<DateTime<Utc>>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FoldResultRow {
    pub fold_index: usize,
    pub symbol: String,
    pub candidate_id: usize,
    pub score: f64,
    pub net_return_pct: f64,
    pub max_drawdown_pct: f64,
    pub trades: usize,
    pub min_trades: usize,
    pub max_trades: usize,
    pub trade_fit: String,
    pub profit_factor: f64,
    pub min_profit_factor: f64,
    pub average_trade_return_pct: f64,
    pub min_average_trade_return_pct: f64,
    pub quality_fit: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CheckRow {
    pub name: String,
    pub status: String,
    pub command: String,
    pub details: String,
    pub finished_at: DateTime<Utc>,
}

pub fn run_wfo(grid: GridSize) -> Result<PathBuf> {
    run_wfo_with_options(grid, WfoRunOptions::default())
}

pub fn run_wfo_with_options(grid: GridSize, options: WfoRunOptions) -> Result<PathBuf> {
    let WfoRunOptions {
        symbols,
        indicator_group,
        strategy_set,
        optimizer_mode,
        resume_run_id,
        min_profit_factor,
        candidate_min_profit_factor,
        account_balance,
        fees_bps,
        tpe_trials,
        tpe_random_startup_fraction,
        tpe_seed,
        tpe_is_consensus_min_passing_windows,
        is_weeks,
        is_days,
        oos_weeks,
        oos_days,
        step_weeks,
        step_days,
        gap_weeks,
        gap_days,
        start_offset_days,
        fold_start_index,
        fold_limit,
        start_date,
        end_date,
    } = options;
    if let Some(value) = min_profit_factor {
        validate_min_profit_factor(value)?;
    }
    if let Some(value) = candidate_min_profit_factor {
        validate_min_profit_factor(value)?;
    }
    if let Some(value) = account_balance {
        validate_account_balance(value)?;
    }
    if let Some(value) = fees_bps {
        validate_fees_bps(value)?;
    }
    if let Some(value) = tpe_trials {
        validate_tpe_trials(value)?;
    }
    if let Some(value) = tpe_random_startup_fraction {
        validate_tpe_random_startup_fraction(value)?;
    }
    if let Some(value) = tpe_is_consensus_min_passing_windows {
        validate_tpe_is_consensus_min_passing_windows(value)?;
    }
    if let Some(value) = is_weeks {
        validate_week_count("is_weeks", value)?;
    }
    if let Some(value) = is_days {
        validate_day_count("is_days", value)?;
    }
    if let Some(value) = oos_weeks {
        validate_week_count("oos_weeks", value)?;
    }
    if let Some(value) = oos_days {
        validate_day_count("oos_days", value)?;
    }
    if let Some(value) = step_weeks {
        validate_week_count("step_weeks", value)?;
    }
    if let Some(value) = step_days {
        validate_day_count("step_days", value)?;
    }
    if let Some(value) = gap_weeks {
        validate_gap_weeks(value)?;
    }
    if let Some(value) = gap_days {
        validate_gap_days(value)?;
    }
    if let Some(value) = start_offset_days {
        validate_start_offset_days(value)?;
    }
    let requested_symbols = normalize_symbols(symbols);
    let requested_indicator_group = normalize_indicator_group(indicator_group);
    let requested_strategy_set = normalize_strategy_set(strategy_set);
    validate_indicator_group(requested_indicator_group.as_deref())?;
    validate_strategy_set(requested_strategy_set.as_deref())?;
    validate_grid_scope(
        grid,
        requested_indicator_group.as_deref(),
        requested_strategy_set.as_deref(),
    )?;

    let resume_run_id = resume_run_id
        .map(|run_id| run_id.trim().to_string())
        .filter(|run_id| !run_id.is_empty());
    let resume_mode = resume_run_id.is_some();
    let (config, run_dir) = if let Some(run_id) = resume_run_id {
        let run_dir = PathBuf::from(RUNS_ROOT).join(&run_id);
        if !run_dir.exists() {
            anyhow::bail!("cannot resume missing WFO run {run_id}");
        }
        let config_path = run_dir.join("config.json");
        let config = read_json::<WfoConfig>(config_path)
            .with_context(|| format!("resume WFO run {run_id}"))?;
        if !requested_symbols.is_empty() && requested_symbols != config.symbols {
            anyhow::bail!(
                "resume run {run_id} has symbols {:?}; requested {:?}",
                config.symbols,
                requested_symbols
            );
        }
        if requested_indicator_group.is_some()
            && requested_indicator_group != config.indicator_group
        {
            anyhow::bail!(
                "resume run {run_id} has indicator_group {:?}; requested {:?}",
                config.indicator_group,
                requested_indicator_group
            );
        }
        if requested_strategy_set.is_some() && requested_strategy_set != config.strategy_set {
            anyhow::bail!(
                "resume run {run_id} has strategy_set {:?}; requested {:?}",
                config.strategy_set,
                requested_strategy_set
            );
        }
        if let Some(requested_optimizer_mode) = optimizer_mode
            && requested_optimizer_mode != config.optimizer_mode
        {
            anyhow::bail!(
                "resume run {run_id} has optimizer_mode {}; requested {}",
                config.optimizer_mode,
                requested_optimizer_mode
            );
        }
        if let Some(requested_fees_bps) = fees_bps
            && (requested_fees_bps - config.fees_bps).abs() > f64::EPSILON
        {
            anyhow::bail!(
                "resume run {run_id} has fees_bps {}; requested {}",
                config.fees_bps,
                requested_fees_bps
            );
        }
        if let Some(requested_candidate_min_profit_factor) = candidate_min_profit_factor
            && (requested_candidate_min_profit_factor - config.candidate_min_profit_factor).abs()
                > f64::EPSILON
        {
            anyhow::bail!(
                "resume run {run_id} has candidate_min_profit_factor {}; requested {}",
                config.candidate_min_profit_factor,
                requested_candidate_min_profit_factor
            );
        }
        if tpe_seed.is_some() && tpe_seed != config.tpe_seed {
            anyhow::bail!(
                "resume run {run_id} has tpe_seed {:?}; requested {:?}",
                config.tpe_seed,
                tpe_seed
            );
        }
        if let Some(requested_is_weeks) = is_weeks
            && requested_is_weeks != config.is_weeks
        {
            anyhow::bail!(
                "resume run {run_id} has is_weeks {}; requested {}",
                config.is_weeks,
                requested_is_weeks
            );
        }
        if let Some(requested_is_days) = is_days
            && Some(requested_is_days) != config.is_days
        {
            anyhow::bail!(
                "resume run {run_id} has is_days {:?}; requested {}",
                config.is_days,
                requested_is_days
            );
        }
        if let Some(requested_oos_weeks) = oos_weeks
            && requested_oos_weeks != config.oos_weeks
        {
            anyhow::bail!(
                "resume run {run_id} has oos_weeks {}; requested {}",
                config.oos_weeks,
                requested_oos_weeks
            );
        }
        if let Some(requested_oos_days) = oos_days
            && Some(requested_oos_days) != config.oos_days
        {
            anyhow::bail!(
                "resume run {run_id} has oos_days {:?}; requested {}",
                config.oos_days,
                requested_oos_days
            );
        }
        if let Some(requested_step_weeks) = step_weeks
            && requested_step_weeks != config.step_weeks
        {
            anyhow::bail!(
                "resume run {run_id} has step_weeks {}; requested {}",
                config.step_weeks,
                requested_step_weeks
            );
        }
        if let Some(requested_step_days) = step_days
            && Some(requested_step_days) != config.step_days
        {
            anyhow::bail!(
                "resume run {run_id} has step_days {:?}; requested {}",
                config.step_days,
                requested_step_days
            );
        }
        if let Some(requested_gap_weeks) = gap_weeks
            && requested_gap_weeks != config.gap_weeks
        {
            anyhow::bail!(
                "resume run {run_id} has gap_weeks {}; requested {}",
                config.gap_weeks,
                requested_gap_weeks
            );
        }
        if let Some(requested_gap_days) = gap_days
            && Some(requested_gap_days) != config.gap_days
        {
            anyhow::bail!(
                "resume run {run_id} has gap_days {:?}; requested {}",
                config.gap_days,
                requested_gap_days
            );
        }
        if let Some(requested_start_offset_days) = start_offset_days
            && requested_start_offset_days != config.start_offset_days
        {
            anyhow::bail!(
                "resume run {run_id} has start_offset_days {}; requested {}",
                config.start_offset_days,
                requested_start_offset_days
            );
        }
        migrate_strategy_oos_results_to_blocks(&run_dir)?;
        write_status(
            &run_dir,
            &status(&config.run_id, RunPhase::Planning, 1.0, "resuming"),
        )?;
        append_event(
            &run_dir,
            "resume",
            "WFO run resumed from existing artifacts",
        )?;
        (config, run_dir)
    } else {
        let mut config = WfoConfig::new(grid);
        config.symbols = requested_symbols;
        config.indicator_group = requested_indicator_group;
        config.strategy_set = requested_strategy_set;
        if let Some(value) = optimizer_mode {
            config.optimizer_mode = value;
        }
        if let Some(value) = min_profit_factor {
            config.min_profit_factor = value;
        }
        if let Some(value) = candidate_min_profit_factor {
            config.candidate_min_profit_factor = value;
        }
        if let Some(value) = account_balance {
            config.account_balance = value;
        }
        if let Some(value) = fees_bps {
            config.fees_bps = value;
        }
        if let Some(value) = tpe_trials {
            config.tpe_trials = value;
        }
        if let Some(value) = tpe_random_startup_fraction {
            config.tpe_random_startup_fraction = value;
        }
        if let Some(value) = is_weeks {
            config.is_weeks = value;
        }
        if let Some(value) = is_days {
            config.is_days = Some(value);
        }
        if let Some(value) = oos_weeks {
            config.oos_weeks = value;
        }
        if let Some(value) = oos_days {
            config.oos_days = Some(value);
        }
        if let Some(value) = step_weeks {
            config.step_weeks = value;
        }
        if let Some(value) = step_days {
            config.step_days = Some(value);
        }
        if let Some(value) = gap_weeks {
            config.gap_weeks = value;
        }
        if let Some(value) = gap_days {
            config.gap_days = Some(value);
        }
        if let Some(value) = start_offset_days {
            config.start_offset_days = value;
        }
        if let Some(value) = fold_start_index {
            config.fold_start_index = value;
        }
        if let Some(value) = fold_limit {
            config.fold_limit = Some(value);
        }
        if let Some(value) = start_date {
            config.start = parse_date(&value)?;
        }
        if let Some(value) = end_date {
            config.end = parse_date(&value)?;
        }
        config.tpe_seed = tpe_seed;
        if let Some(value) = tpe_is_consensus_min_passing_windows {
            config.tpe_is_consensus_min_passing_windows = value;
        }
        validate_indicator_group(config.indicator_group.as_deref())?;
        validate_strategy_set(config.strategy_set.as_deref())?;
        validate_tpe_config(&config)?;
        validate_grid_scope(
            config.grid,
            config.indicator_group.as_deref(),
            config.strategy_set.as_deref(),
        )?;
        let run_dir = PathBuf::from(RUNS_ROOT).join(&config.run_id);
        fs::create_dir_all(&run_dir)?;
        write_json(run_dir.join("config.json"), &config)?;
        write_status(
            &run_dir,
            &status(&config.run_id, RunPhase::Planning, 1.0, "planned"),
        )?;
        append_event(&run_dir, "plan", "WFO run initialized")?;
        (config, run_dir)
    };
    validate_indicator_group(config.indicator_group.as_deref())?;
    validate_strategy_set(config.strategy_set.as_deref())?;
    validate_min_profit_factor(config.min_profit_factor)?;
    validate_min_profit_factor(config.candidate_min_profit_factor)?;
    validate_fees_bps(config.fees_bps)?;
    validate_tpe_config(&config)?;
    validate_grid_scope(
        config.grid,
        config.indicator_group.as_deref(),
        config.strategy_set.as_deref(),
    )?;

    let folds_path = run_dir.join("folds.csv");
    let folds = if resume_mode && folds_path.exists() {
        read_csv::<Fold>(folds_path)?
    } else {
        let folds = selected_fold_range(
            generate_folds_days(
                date_ms(config.start)? + Duration::days(config.start_offset_days).num_milliseconds(),
                date_ms(config.end)?,
                config.effective_is_days(),
                config.effective_oos_days(),
                config.effective_step_days(),
                config.effective_gap_days(),
            ),
            config.fold_start_index,
            config.fold_limit,
        );
        write_csv(run_dir.join("folds.csv"), &folds)?;
        folds
    };
    let candidates_path = run_dir.join("candidates.csv");
    let mut candidates = if resume_mode && candidates_path.exists() {
        read_csv::<Candidate>(candidates_path)?
    } else {
        let candidates = candidate_grid_for_config(&config)?;
        write_csv(run_dir.join("candidates.csv"), &candidates)?;
        candidates
    };
    if !resume_mode || !run_dir.join("plan.json").exists() {
        write_plan(&run_dir, &config, &folds, &candidates)?;
    }
    if !resume_mode || !run_dir.join("implementation_status.json").exists() {
        write_json(
            run_dir.join("implementation_status.json"),
            &implementation_rows(&candidates),
        )?;
    }
    if !resume_mode {
        write_csv::<CandidateScore>(run_dir.join("best_by_indicator.csv"), &[])?;
    }
    let progress_path = run_dir.join("strategy_progress.json");
    let mut strategy_progress = if resume_mode && progress_path.exists() {
        read_json::<Vec<StrategyRow>>(progress_path)?
    } else {
        initial_strategy_progress(&candidates)
    };
    merge_strategy_progress_rows(&mut strategy_progress, &candidates);
    normalize_resumed_strategy_progress(&mut strategy_progress, resume_mode);
    write_strategy_progress(&run_dir, &strategy_progress)?;
    write_strategy_oos_placeholders(&run_dir, &strategy_progress)?;

    write_status(
        &run_dir,
        &status(
            &config.run_id,
            RunPhase::LoadingData,
            8.0,
            "loading symbols",
        ),
    )?;
    let symbols = if !config.symbols.is_empty() {
        config.symbols.clone()
    } else {
        match preset_symbols(&config.preset) {
            Ok(symbols) if config.grid != GridSize::Smoke => symbols,
            _ => vec!["SYNTHUSDT".to_string()],
        }
    };
    let store = KlineStore::from_env()?;
    let mut data = Vec::new();
    for symbol in &symbols {
        let rows = store
            .load_range(symbol, config.start, config.end)
            .unwrap_or_default()
            .iter()
            .map(OhlcvBar::from)
            .collect::<Vec<_>>();
        if rows.is_empty() {
            data.push((
                symbol.clone(),
                synthetic_market(
                    symbol,
                    date_ms(config.start)?,
                    synthetic_row_count(&config)?,
                ),
            ));
            append_event(
                &run_dir,
                "data",
                &format!("{symbol}: using synthetic fallback market"),
            )?;
        } else {
            append_event(
                &run_dir,
                "data",
                &format!("{symbol}: loaded {} one-minute bars", rows.len()),
            )?;
            data.push((symbol.clone(), rows));
        }
    }
    let close_by_symbol = close_lookup(&data);

    write_status(
        &run_dir,
        &status(
            &config.run_id,
            RunPhase::Simulating,
            15.0,
            "simulating candidates",
        ),
    )?;
    append_event(
        &run_dir,
        "simulate",
        &format!("{} symbols, {} candidates", data.len(), candidates.len()),
    )?;
    let strategy_totals = strategy_totals(
        &candidates,
        &symbols,
        config.strategy_set.as_deref(),
        config.grid,
    );
    let total_work = strategy_totals.values().sum::<usize>().max(1);
    let mut progress_counts =
        initial_strategy_counts_from_rows(&candidates, &strategy_progress, &strategy_totals);
    let mut completed_work = progress_counts.values().sum::<usize>();
    let progress_every = match config.grid {
        GridSize::Smoke => 1,
        GridSize::Wide => 12,
        GridSize::Wide200 => 50,
        GridSize::Tpe => 5,
        GridSize::Probe => 50,
        GridSize::Deep => 60,
    };
    let mut best_by_fold: BTreeMap<usize, FoldSelection> = BTreeMap::new();
    let mut strategy_oos_by_symbol_fold: BTreeMap<(String, String, String, usize), FoldSelection> =
        BTreeMap::new();
    let mut signal_fill_diagnostics = SignalFillDiagnosticsMap::new();
    let candidate_groups = strategy_candidate_groups(&candidates, &strategy_progress);
    let started = Instant::now();

    for (active_strategy_key, group_candidates) in candidate_groups {
        let row_total = strategy_totals
            .get(&active_strategy_key)
            .copied()
            .unwrap_or(1);
        mark_strategy_row_running(&mut strategy_progress, &active_strategy_key);
        append_event(
            &run_dir,
            "strategy",
            &format!(
                "{} {}: starting {} symbol-candidates",
                active_strategy_key.0, active_strategy_key.1, row_total
            ),
        )?;
        write_strategy_progress(&run_dir, &strategy_progress)?;
        write_strategy_oos_status_snapshot(&run_dir, &strategy_progress)?;

        if config.grid == GridSize::Tpe {
            run_tpe_strategy(
                &run_dir,
                &config,
                &folds,
                &data,
                &mut candidates,
                &mut strategy_progress,
                &active_strategy_key,
                &group_candidates,
                &strategy_totals,
                &mut progress_counts,
                &mut completed_work,
                total_work,
                progress_every,
                started,
                &mut best_by_fold,
                &mut strategy_oos_by_symbol_fold,
                &mut signal_fill_diagnostics,
                &close_by_symbol,
            )?;
            write_csv(run_dir.join("candidates.csv"), &candidates)?;
            write_signal_fill_diagnostics(&run_dir, &signal_fill_diagnostics)?;
            let strategy_oos_context = StrategyOosContext::new(
                &config,
                &folds,
                &data,
                &candidates,
                &strategy_progress,
                &strategy_oos_by_symbol_fold,
                &close_by_symbol,
            )?;
            write_completed_strategy_oos_snapshot(
                &run_dir,
                &active_strategy_key,
                &strategy_oos_context,
            )?;
            append_event(
                &run_dir,
                "strategy",
                &format!(
                    "{} {}: complete",
                    active_strategy_key.0, active_strategy_key.1
                ),
            )?;
            continue;
        }

        for (symbol, bars) in &data {
            let symbol_candidates = group_candidates
                .iter()
                .filter(|candidate| {
                    candidate_allowed_for_symbol(config.strategy_set.as_deref(), symbol, candidate)
                })
                .collect::<Vec<_>>();
            if symbol_candidates.is_empty() {
                append_event(
                    &run_dir,
                    "symbol",
                    &format!(
                        "{symbol}: skipped {} {} because no candidates are eligible for this strategy set",
                        active_strategy_key.0, active_strategy_key.1
                    ),
                )?;
                continue;
            }
            append_event(
                &run_dir,
                "symbol",
                &format!(
                    "{symbol}: starting {} {} {} candidates",
                    active_strategy_key.0,
                    active_strategy_key.1,
                    symbol_candidates.len()
                ),
            )?;
            let mut symbol_cache = SimulationCache::default();
            let mut prepared_work = Vec::with_capacity(symbol_candidates.len());
            for candidate in symbol_candidates {
                prepared_work.push(prepare_candidate_simulation(
                    symbol,
                    bars,
                    candidate,
                    &config,
                    &mut symbol_cache,
                )?);
            }

            let block_results = prepared_work
                .par_iter()
                .map(|prepared| simulate_prepared_candidate(bars, prepared, &folds))
                .collect::<Vec<_>>();

            for result in block_results {
                let candidate = &result.candidate;
                let mut candidate_scores = Vec::with_capacity(folds.len());
                for (fold_pos, fold) in folds.iter().enumerate() {
                    let fold_trades = selection_trades_for_fold(&result.trades, &config, fold);
                    let fold_diagnostics = result
                        .fold_diagnostics
                        .get(fold_pos)
                        .cloned()
                        .unwrap_or_default();
                    let score = score_trades_with_diagnostics(
                        result.symbol.as_str(),
                        &result.candidate,
                        fold.index,
                        fold,
                        &fold_trades,
                        &config,
                        &fold_diagnostics,
                    );
                    accumulate_signal_fill_diagnostics(
                        &mut signal_fill_diagnostics,
                        candidate,
                        result.symbol.as_str(),
                        fold.index,
                        &fold_diagnostics,
                        &score,
                    );
                    let selection_evaluation = fold_selection_evaluation(
                        &config,
                        result.symbol.as_str(),
                        candidate,
                        fold,
                        &result.trades,
                        &score,
                        &score,
                    );
                    let strategy_oos_key = (
                        candidate.indicator.as_str().to_string(),
                        candidate.timeframe.as_str().to_string(),
                        result.symbol.clone(),
                        fold.index,
                    );
                    if let Some(selection) = strict_fold_selection(
                        &selection_evaluation,
                        candidate.indicator,
                        oos_trades_for_fold(&result.trades, fold),
                    ) {
                        insert_strategy_fold_selection(
                            &mut strategy_oos_by_symbol_fold,
                            strategy_oos_key,
                            selection.clone(),
                        );
                        let replace = best_by_fold
                            .get(&score.fold_index)
                            .map(|current| selection.rank_score > current.rank_score)
                            .unwrap_or(true);
                        if replace {
                            best_by_fold.insert(score.fold_index, selection);
                        }
                    }
                    candidate_scores.push(selection_evaluation.objective_score);
                }

                let candidate_key = strategy_key(candidate);
                *progress_counts.entry(candidate_key.clone()).or_default() += 1;
                let row_completed = progress_counts
                    .get(&candidate_key)
                    .copied()
                    .unwrap_or_default();
                let candidate_score = mean_score(&candidate_scores);
                update_strategy_row(
                    &mut strategy_progress,
                    &candidate_key,
                    candidate_score,
                    &candidate_scores,
                    result.trades.len(),
                    row_completed,
                    row_total,
                );
                completed_work += 1;
                if row_completed % progress_every == 0
                    || row_completed == row_total
                    || completed_work == total_work
                {
                    let elapsed_seconds = started.elapsed().as_secs().max(1);
                    let eta_seconds = ((total_work - completed_work) as u64 * elapsed_seconds)
                        / completed_work.max(1) as u64;
                    let progress_pct = 15.0 + 75.0 * completed_work as f64 / total_work as f64;
                    write_status(
                        &run_dir,
                        &status_with_active(
                            &config.run_id,
                            RunPhase::Simulating,
                            progress_pct,
                            &format!("simulated {completed_work}/{total_work} symbol-candidates"),
                            ActiveStatus {
                                symbol: Some(result.symbol.as_str()),
                                indicator: Some(candidate.indicator.as_str()),
                                timeframe: Some(candidate.timeframe.as_str()),
                                eta_seconds: Some(eta_seconds),
                                ..ActiveStatus::default()
                            },
                        ),
                    )?;
                    write_strategy_progress(&run_dir, &strategy_progress)?;
                    write_strategy_oos_status_snapshot(&run_dir, &strategy_progress)?;
                    let fold_scores = best_by_fold
                        .values()
                        .map(|selection| selection.score.clone())
                        .collect::<Vec<_>>();
                    write_csv(run_dir.join("best_by_indicator.csv"), &fold_scores)?;
                    append_event(
                        &run_dir,
                        "progress",
                        &format!(
                            "{completed_work}/{total_work}: {} {} {} row {row_completed}/{row_total}",
                            result.symbol,
                            candidate.indicator.as_str(),
                            candidate.timeframe.as_str()
                        ),
                    )?;
                }
            }
        }

        let strategy_oos_context = StrategyOosContext::new(
            &config,
            &folds,
            &data,
            &candidates,
            &strategy_progress,
            &strategy_oos_by_symbol_fold,
            &close_by_symbol,
        )?;
        write_completed_strategy_oos_snapshot(
            &run_dir,
            &active_strategy_key,
            &strategy_oos_context,
        )?;
        write_signal_fill_diagnostics(&run_dir, &signal_fill_diagnostics)?;
        append_event(
            &run_dir,
            "strategy",
            &format!(
                "{} {}: complete",
                active_strategy_key.0, active_strategy_key.1
            ),
        )?;
    }

    write_strategy_progress(&run_dir, &strategy_progress)?;
    write_strategy_oos_status_snapshot(&run_dir, &strategy_progress)?;
    write_status(
        &run_dir,
        &status(
            &config.run_id,
            RunPhase::WritingArtifacts,
            90.0,
            "writing artifacts",
        ),
    )?;
    if resume_mode {
        let strategy_oos_results = read_strategy_oos_results(Some(&config.run_id))?;
        write_json(
            run_dir.join(STRATEGY_OOS_RESULTS_FILE),
            &strategy_oos_results,
        )?;
        let summary = summarize_from_strategy_oos_blocks(
            &config,
            folds.len(),
            candidates.len(),
            &strategy_oos_results,
        );
        write_resume_artifacts(&run_dir, &summary, &folds, &candidates)?;
        append_event(&run_dir, "complete", "WFO run complete after resume")?;
        write_status(
            &run_dir,
            &status(&config.run_id, RunPhase::Complete, 100.0, "complete"),
        )?;
        return Ok(run_dir);
    }
    let strategy_oos_results = build_strategy_oos_results(
        &config,
        &folds,
        &data,
        &candidates,
        &strategy_progress,
        &strategy_oos_by_symbol_fold,
        &close_by_symbol,
    )?;
    let data_symbols = data
        .iter()
        .map(|(symbol, _)| symbol.clone())
        .collect::<Vec<_>>();
    let artifact_selection = primary_artifact_selection(
        &strategy_progress,
        &data_symbols,
        &strategy_oos_by_symbol_fold,
        &best_by_fold,
        config.fixed_notional,
    );
    let account_artifacts =
        build_account_artifacts(&config, &folds, &artifact_selection.trades, &data)?;
    let risk_managed_artifacts =
        if let Some(risk_managed_trades) = artifact_selection.risk_managed_trades.clone() {
            let account_artifacts =
                build_account_artifacts(&config, &folds, &risk_managed_trades, &data)?;
            let summary = summarize(
                &config,
                folds.len(),
                candidates.len(),
                &risk_managed_trades,
                &account_artifacts.stats,
                &format!("{} risk-managed", artifact_selection.best_indicator),
            );
            Some(ManagedRunArtifacts {
                summary,
                trades: risk_managed_trades,
                account_artifacts,
            })
        } else {
            None
        };
    let summary = summarize(
        &config,
        folds.len(),
        candidates.len(),
        &artifact_selection.trades,
        &account_artifacts.stats,
        &artifact_selection.best_indicator,
    );
    write_json(
        run_dir.join(STRATEGY_OOS_RESULTS_FILE),
        &strategy_oos_results,
    )?;
    write_artifacts(
        &run_dir,
        &summary,
        &folds,
        &candidates,
        &artifact_selection.scores,
        &artifact_selection.trades,
        &account_artifacts,
        artifact_selection.best_fold_scores.as_deref(),
        artifact_selection.best_fold_trades.as_deref(),
        risk_managed_artifacts.as_ref(),
    )?;
    append_event(&run_dir, "complete", "WFO run complete")?;
    write_status(
        &run_dir,
        &status(&config.run_id, RunPhase::Complete, 100.0, "complete"),
    )?;
    Ok(run_dir)
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct OptunaStrategyGroup {
    pub indicator: String,
    pub timeframe: String,
    pub trials: usize,
    pub folds: usize,
    pub completed: usize,
    pub status: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct OptunaBatchTrial {
    pub trial_index: usize,
    #[serde(default)]
    pub params: serde_json::Value,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct OptunaTrialResult {
    pub trial_index: usize,
    #[serde(default)]
    pub fold_index: Option<usize>,
    pub candidate_id: usize,
    pub indicator: String,
    pub timeframe: String,
    pub objective_score: f64,
    pub best_objective_score: f64,
    pub best_candidate_id: usize,
    pub training_mean_score: f64,
    pub validation_mean_score: f64,
    pub training_q25_score: f64,
    pub training_median_score: f64,
    pub validation_q25_score: f64,
    pub validation_median_score: f64,
    pub validation_score_stddev: f64,
    pub training_eligible_fraction: f64,
    pub validation_eligible_fraction: f64,
    pub validation_net_positive_fraction: f64,
    pub validation_trade_fit_fraction: f64,
    pub validation_quality_fit_fraction: f64,
    pub validation_median_profit_factor: f64,
    #[serde(default)]
    pub training_nonnegative_score_fraction: f64,
    #[serde(default)]
    pub validation_nonnegative_score_fraction: f64,
    #[serde(default)]
    pub average_trade_penalty: f64,
    #[serde(default)]
    pub average_profit_factor_penalty: f64,
    #[serde(default)]
    pub average_net_penalty: f64,
    #[serde(default)]
    pub average_fill_penalty: f64,
    #[serde(default)]
    pub average_participation_penalty: f64,
    #[serde(default)]
    pub base_objective_component: f64,
    #[serde(default)]
    pub consistency_bonus: f64,
    #[serde(default)]
    pub paired_bonus: f64,
    pub paired_selection_fraction: f64,
    pub paired_selection_count: usize,
    pub train_gap_penalty: f64,
    pub dispersion_penalty: f64,
    pub training_scores: usize,
    pub validation_scores: usize,
    pub trial_trade_count: usize,
    pub validation_trades: usize,
    pub validation_profit_factor: f64,
    pub validation_net_return_pct: f64,
    pub validation_max_drawdown_pct: f64,
    #[serde(default)]
    pub max_timestamp_seen: i64,
    pub constraints: Vec<f64>,
    pub params_signature: String,
    pub candidate: Candidate,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FoldTrialTraceRow {
    pub optimizer_mode: String,
    pub offset_days: i64,
    pub fold_index: usize,
    pub indicator: String,
    pub timeframe: String,
    pub study_name: String,
    pub seed: u64,
    pub trial_index: usize,
    pub candidate_id: usize,
    pub objective_score: f64,
    pub selected: bool,
    pub constraint_0: f64,
    pub params_signature: String,
    pub max_timestamp_seen: i64,
    pub validation_trades: usize,
    pub validation_profit_factor: f64,
    pub validation_net_return_pct: f64,
    pub validation_max_drawdown_pct: f64,
    pub training_scores: usize,
    pub validation_scores: usize,
    pub lookback: usize,
    pub atr_period: usize,
    pub entry_atr_multiple: f64,
    pub stop_atr_multiple: f64,
    pub target_atr_multiple: f64,
    pub time_stop_bars: Option<usize>,
    pub strategy_4448_kama1_er: usize,
    pub strategy_4448_kama1_short: usize,
    pub strategy_4448_kama1_long: usize,
    pub strategy_4448_kama2_er: usize,
    pub strategy_4448_kama2_short: usize,
    pub strategy_4448_kama2_long: usize,
    pub strategy_4448_count_bars: usize,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct OptimizerProvenanceRow {
    pub optimizer_mode: String,
    pub offset_days: i64,
    pub fold_index: usize,
    pub strategy: String,
    pub timeframe: String,
    pub symbol: String,
    pub study_name: String,
    pub seed: u64,
    pub trials_requested: usize,
    pub trials_completed: usize,
    pub optimizer_scope_start: i64,
    pub optimizer_scope_end: i64,
    pub max_timestamp_seen: i64,
    pub selected_candidate_id: usize,
    pub params_signature: String,
    pub is_score: f64,
    pub is_profit_factor: f64,
    pub is_trades: usize,
    pub is_max_drawdown_pct: f64,
    pub oos_total_pnl: f64,
    pub oos_net_return_pct: f64,
    pub oos_profit_factor: f64,
    pub oos_trades: usize,
    pub oos_max_drawdown_pct: f64,
    pub selection_status: String,
    pub selection_reason: String,
}

#[derive(Debug, Clone, Default)]
struct FoldStudyProgress {
    study_name: String,
    seed: u64,
    trials_requested: usize,
    trials_completed: usize,
    max_timestamp_seen: i64,
}

#[derive(Debug)]
pub struct OptunaWfoEvaluator {
    config: WfoConfig,
    run_dir: PathBuf,
    folds: Vec<Fold>,
    data: Vec<(String, Vec<OhlcvBar>)>,
    candidates: Vec<Candidate>,
    strategy_progress: Vec<StrategyRow>,
    strategy_totals: BTreeMap<(String, String), usize>,
    progress_counts: BTreeMap<(String, String), usize>,
    completed_work: usize,
    total_work: usize,
    progress_every: usize,
    started: Instant,
    best_by_fold: BTreeMap<usize, FoldSelection>,
    strategy_oos_by_symbol_fold: BTreeMap<(String, String, String, usize), FoldSelection>,
    signal_fill_diagnostics: SignalFillDiagnosticsMap,
    close_by_symbol: BTreeMap<String, BTreeMap<i64, f64>>,
    symbol_caches_by_strategy: BTreeMap<(String, String), Vec<SimulationCache>>,
    fold_symbol_caches_by_strategy: BTreeMap<FoldStudyKey, Vec<SimulationCache>>,
    best_trial_by_strategy: BTreeMap<(String, String), TpeTrialEvaluation>,
    best_trial_by_strategy_fold: BTreeMap<FoldStudyKey, TpeTrialEvaluation>,
    staged_strategy_oos_by_fold: BTreeMap<FoldStudyKey, FoldSelectionMap>,
    staged_best_by_fold: BTreeMap<FoldStudyKey, BTreeMap<usize, FoldSelection>>,
    staged_candidates_by_id: BTreeMap<usize, Candidate>,
    fold_study_progress: BTreeMap<FoldStudyKey, FoldStudyProgress>,
    tpe_trial_trace: Vec<TpeTrialTraceRow>,
    fold_trial_trace: Vec<FoldTrialTraceRow>,
    optimizer_provenance: Vec<OptimizerProvenanceRow>,
}

impl OptunaWfoEvaluator {
    pub fn new(options: WfoRunOptions) -> Result<Self> {
        if options.resume_run_id.is_some() {
            anyhow::bail!("Optuna WFO does not support resume_run_id yet");
        }
        let requested_symbols = normalize_symbols(options.symbols.clone());
        let requested_indicator_group = normalize_indicator_group(options.indicator_group.clone());
        let requested_strategy_set = normalize_strategy_set(options.strategy_set.clone());
        let requested_optimizer_mode = options.optimizer_mode;
        validate_indicator_group(requested_indicator_group.as_deref())?;
        validate_strategy_set(requested_strategy_set.as_deref())?;
        validate_grid_scope(
            GridSize::Tpe,
            requested_indicator_group.as_deref(),
            requested_strategy_set.as_deref(),
        )?;
        if let Some(value) = options.min_profit_factor {
            validate_min_profit_factor(value)?;
        }
        if let Some(value) = options.candidate_min_profit_factor {
            validate_min_profit_factor(value)?;
        }
        if let Some(value) = options.account_balance {
            validate_account_balance(value)?;
        }
        if let Some(value) = options.fees_bps {
            validate_fees_bps(value)?;
        }
        if let Some(value) = options.tpe_trials {
            validate_tpe_trials(value)?;
        }
        if let Some(value) = options.tpe_random_startup_fraction {
            validate_tpe_random_startup_fraction(value)?;
        }
        if let Some(value) = options.tpe_is_consensus_min_passing_windows {
            validate_tpe_is_consensus_min_passing_windows(value)?;
        }
        if let Some(value) = options.is_weeks {
            validate_week_count("is_weeks", value)?;
        }
        if let Some(value) = options.is_days {
            validate_day_count("is_days", value)?;
        }
        if let Some(value) = options.oos_weeks {
            validate_week_count("oos_weeks", value)?;
        }
        if let Some(value) = options.oos_days {
            validate_day_count("oos_days", value)?;
        }
        if let Some(value) = options.step_weeks {
            validate_week_count("step_weeks", value)?;
        }
        if let Some(value) = options.step_days {
            validate_day_count("step_days", value)?;
        }
        if let Some(value) = options.gap_weeks {
            validate_gap_weeks(value)?;
        }
        if let Some(value) = options.gap_days {
            validate_gap_days(value)?;
        }
        if let Some(value) = options.start_offset_days {
            validate_start_offset_days(value)?;
        }

        let mut config = WfoConfig::new(GridSize::Tpe);
        config.symbols = requested_symbols;
        config.indicator_group = requested_indicator_group;
        config.strategy_set = requested_strategy_set;
        if let Some(value) = requested_optimizer_mode {
            config.optimizer_mode = value;
        }
        if let Some(value) = options.min_profit_factor {
            config.min_profit_factor = value;
        }
        if let Some(value) = options.candidate_min_profit_factor {
            config.candidate_min_profit_factor = value;
        }
        if let Some(value) = options.account_balance {
            config.account_balance = value;
        }
        if let Some(value) = options.fees_bps {
            config.fees_bps = value;
        }
        if let Some(value) = options.tpe_trials {
            config.tpe_trials = value;
        }
        if let Some(value) = options.tpe_random_startup_fraction {
            config.tpe_random_startup_fraction = value;
        }
        if let Some(value) = options.tpe_seed {
            config.tpe_seed = Some(value);
        }
        if let Some(value) = options.tpe_is_consensus_min_passing_windows {
            config.tpe_is_consensus_min_passing_windows = value;
        }
        if let Some(value) = options.is_weeks {
            config.is_weeks = value;
        }
        if let Some(value) = options.is_days {
            config.is_days = Some(value);
        }
        if let Some(value) = options.oos_weeks {
            config.oos_weeks = value;
        }
        if let Some(value) = options.oos_days {
            config.oos_days = Some(value);
        }
        if let Some(value) = options.step_weeks {
            config.step_weeks = value;
        }
        if let Some(value) = options.step_days {
            config.step_days = Some(value);
        }
        if let Some(value) = options.gap_weeks {
            config.gap_weeks = value;
        }
        if let Some(value) = options.gap_days {
            config.gap_days = Some(value);
        }
        if let Some(value) = options.start_offset_days {
            config.start_offset_days = value;
        }
        if let Some(value) = options.fold_start_index {
            config.fold_start_index = value;
        }
        if let Some(value) = options.fold_limit {
            config.fold_limit = Some(value);
        }
        if let Some(ref value) = options.start_date {
            config.start = parse_date(value)?;
        }
        if let Some(ref value) = options.end_date {
            config.end = parse_date(value)?;
        }
        validate_tpe_config(&config)?;

        let run_dir = PathBuf::from(RUNS_ROOT).join(&config.run_id);
        fs::create_dir_all(&run_dir)?;
        write_json(run_dir.join("config.json"), &config)?;
        write_status(
            &run_dir,
            &status(&config.run_id, RunPhase::Planning, 1.0, "planned"),
        )?;
        append_event(&run_dir, "plan", "Optuna WFO run initialized")?;

        let folds = selected_fold_range(
            generate_folds_days(
                date_ms(config.start)? + Duration::days(config.start_offset_days).num_milliseconds(),
                date_ms(config.end)?,
                config.effective_is_days(),
                config.effective_oos_days(),
                config.effective_step_days(),
                config.effective_gap_days(),
            ),
            config.fold_start_index,
            config.fold_limit,
        );
        write_csv(run_dir.join("folds.csv"), &folds)?;
        let candidates = candidate_grid_for_config(&config)?;
        write_csv(run_dir.join("candidates.csv"), &candidates)?;
        write_plan(&run_dir, &config, &folds, &candidates)?;
        write_json(
            run_dir.join("implementation_status.json"),
            &implementation_rows(&candidates),
        )?;
        write_csv::<CandidateScore>(run_dir.join("best_by_indicator.csv"), &[])?;
        write_csv::<TpeTrialTraceRow>(run_dir.join(TPE_TRIALS_FILE), &[])?;
        write_csv::<FoldTrialTraceRow>(run_dir.join(FOLD_TRIALS_FILE), &[])?;
        write_csv::<OptimizerProvenanceRow>(run_dir.join(OPTIMIZER_PROVENANCE_CSV_FILE), &[])?;
        write_optimizer_provenance_jsonl(&run_dir, &[])?;

        let strategy_progress = initial_strategy_progress(&candidates);
        write_strategy_progress(&run_dir, &strategy_progress)?;
        write_strategy_oos_placeholders(&run_dir, &strategy_progress)?;
        write_status(
            &run_dir,
            &status(
                &config.run_id,
                RunPhase::LoadingData,
                8.0,
                "loading symbols",
            ),
        )?;
        let symbols = if !config.symbols.is_empty() {
            config.symbols.clone()
        } else {
            match preset_symbols(&config.preset) {
                Ok(symbols) => symbols,
                _ => vec!["SYNTHUSDT".to_string()],
            }
        };
        let store = KlineStore::from_env()?;
        let mut data = Vec::new();
        for symbol in &symbols {
            let rows = store
                .load_range(symbol, config.start, config.end)
                .unwrap_or_default()
                .iter()
                .map(OhlcvBar::from)
                .collect::<Vec<_>>();
            if rows.is_empty() {
                data.push((
                    symbol.clone(),
                    synthetic_market(
                        symbol,
                        date_ms(config.start)?,
                        synthetic_row_count(&config)?,
                    ),
                ));
                append_event(
                    &run_dir,
                    "data",
                    &format!("{symbol}: using synthetic fallback market"),
                )?;
            } else {
                append_event(
                    &run_dir,
                    "data",
                    &format!("{symbol}: loaded {} one-minute bars", rows.len()),
                )?;
                data.push((symbol.clone(), rows));
            }
        }
        let close_by_symbol = close_lookup(&data);
        write_status(
            &run_dir,
            &status(
                &config.run_id,
                RunPhase::Simulating,
                15.0,
                "waiting for Optuna trials",
            ),
        )?;
        append_event(
            &run_dir,
            "simulate",
            &format!(
                "{} symbols, {} Optuna templates",
                data.len(),
                candidates.len()
            ),
        )?;
        let mut strategy_totals = strategy_totals(
            &candidates,
            &symbols,
            config.strategy_set.as_deref(),
            config.grid,
        );
        if config.optimizer_mode == OptimizerMode::PointInTimeFoldLocal {
            for total in strategy_totals.values_mut() {
                *total *= folds.len().max(1);
            }
        }
        let progress_counts =
            initial_strategy_counts_from_rows(&candidates, &strategy_progress, &strategy_totals);
        let completed_work = progress_counts.values().sum::<usize>();
        let total_work = strategy_totals.values().sum::<usize>().max(1);
        Ok(Self {
            config,
            run_dir,
            folds,
            data,
            candidates,
            strategy_progress,
            strategy_totals,
            progress_counts,
            completed_work,
            total_work,
            progress_every: 1,
            started: Instant::now(),
            best_by_fold: BTreeMap::new(),
            strategy_oos_by_symbol_fold: BTreeMap::new(),
            signal_fill_diagnostics: SignalFillDiagnosticsMap::new(),
            close_by_symbol,
            symbol_caches_by_strategy: BTreeMap::new(),
            fold_symbol_caches_by_strategy: BTreeMap::new(),
            best_trial_by_strategy: BTreeMap::new(),
            best_trial_by_strategy_fold: BTreeMap::new(),
            staged_strategy_oos_by_fold: BTreeMap::new(),
            staged_best_by_fold: BTreeMap::new(),
            staged_candidates_by_id: BTreeMap::new(),
            fold_study_progress: BTreeMap::new(),
            tpe_trial_trace: Vec::new(),
            fold_trial_trace: Vec::new(),
            optimizer_provenance: Vec::new(),
        })
    }

    pub fn run_id(&self) -> &str {
        &self.config.run_id
    }

    pub fn run_dir(&self) -> &Path {
        &self.run_dir
    }

    pub fn config(&self) -> &WfoConfig {
        &self.config
    }

    pub fn folds(&self) -> &[Fold] {
        &self.folds
    }

    pub fn groups(&self) -> Vec<OptunaStrategyGroup> {
        self.strategy_progress
            .iter()
            .filter(|row| row.runnable && row.parameter_candidates > 0)
            .map(|row| {
                let key = (row.indicator.clone(), row.timeframe.clone());
                OptunaStrategyGroup {
                    indicator: row.indicator.clone(),
                    timeframe: row.timeframe.clone(),
                    trials: row.parameter_candidates,
                    folds: self.folds.len(),
                    completed: self.progress_counts.get(&key).copied().unwrap_or_default(),
                    status: row.status.clone(),
                }
            })
            .collect()
    }

    pub fn start_group(&mut self, indicator: &str, timeframe: &str) -> Result<()> {
        let key = (indicator.to_string(), timeframe.to_string());
        if !self.strategy_totals.contains_key(&key) {
            anyhow::bail!("unknown Optuna strategy group {indicator} {timeframe}");
        }
        mark_strategy_row_running(&mut self.strategy_progress, &key);
        append_event(
            &self.run_dir,
            "strategy",
            &format!(
                "{} {}: starting {} Optuna trials",
                key.0,
                key.1,
                self.strategy_totals.get(&key).copied().unwrap_or_default()
            ),
        )?;
        write_strategy_progress(&self.run_dir, &self.strategy_progress)?;
        write_strategy_oos_status_snapshot(&self.run_dir, &self.strategy_progress)?;
        Ok(())
    }

    pub fn start_fold_group(
        &mut self,
        indicator: &str,
        timeframe: &str,
        fold_index: usize,
        study_name: &str,
        seed: u64,
        trials_requested: usize,
    ) -> Result<()> {
        if self.config.optimizer_mode != OptimizerMode::PointInTimeFoldLocal {
            anyhow::bail!(
                "start_fold_group requires optimizer_mode {}; current mode is {}",
                OptimizerMode::PointInTimeFoldLocal,
                self.config.optimizer_mode
            );
        }
        let key = (indicator.to_string(), timeframe.to_string());
        if !self.strategy_totals.contains_key(&key) {
            anyhow::bail!("unknown Optuna strategy group {indicator} {timeframe}");
        }
        let fold = self
            .folds
            .iter()
            .find(|fold| fold.index == fold_index)
            .with_context(|| format!("unknown fold_index {fold_index}"))?;
        let progress_key = (key.0.clone(), key.1.clone(), fold.index);
        self.fold_study_progress.insert(
            progress_key.clone(),
            FoldStudyProgress {
                study_name: study_name.to_string(),
                seed,
                trials_requested,
                trials_completed: 0,
                max_timestamp_seen: 0,
            },
        );
        self.staged_strategy_oos_by_fold
            .entry(progress_key.clone())
            .or_default()
            .clear();
        self.staged_best_by_fold
            .entry(progress_key.clone())
            .or_default()
            .clear();
        write_status(
            &self.run_dir,
            &status_with_active(
                &self.config.run_id,
                RunPhase::Simulating,
                15.0 + 75.0 * self.completed_work as f64 / self.total_work as f64,
                &format!(
                    "{} {} fold {}: starting point-in-time study",
                    key.0, key.1, fold.index
                ),
                ActiveStatus {
                    indicator: Some(&key.0),
                    timeframe: Some(&key.1),
                    offset_days: Some(self.config.start_offset_days),
                    fold_index: Some(fold.index),
                    fold_count: Some(self.folds.len()),
                    optimizer_mode: Some(self.config.optimizer_mode),
                    ..ActiveStatus::default()
                },
            ),
        )?;
        append_event(
            &self.run_dir,
            "fold",
            &format!(
                "{} {} fold {}: study {study_name} seed {seed} requested {trials_requested} trials",
                key.0, key.1, fold.index
            ),
        )?;
        Ok(())
    }

    pub fn evaluate_fold_batch_json(
        &mut self,
        indicator: &str,
        timeframe: &str,
        fold_index: usize,
        batch_json: &str,
    ) -> Result<Vec<OptunaTrialResult>> {
        let batch = serde_json::from_str::<Vec<OptunaBatchTrial>>(batch_json)
            .with_context(|| "parse Optuna fold batch JSON")?;
        self.evaluate_fold_batch(indicator, timeframe, fold_index, &batch)
    }

    pub fn evaluate_fold_batch(
        &mut self,
        indicator: &str,
        timeframe: &str,
        fold_index: usize,
        batch: &[OptunaBatchTrial],
    ) -> Result<Vec<OptunaTrialResult>> {
        if self.config.optimizer_mode != OptimizerMode::PointInTimeFoldLocal {
            anyhow::bail!(
                "evaluate_fold_batch requires optimizer_mode {}; current mode is {}",
                OptimizerMode::PointInTimeFoldLocal,
                self.config.optimizer_mode
            );
        }
        let fold_pos = self
            .folds
            .iter()
            .position(|fold| fold.index == fold_index)
            .with_context(|| format!("unknown fold_index {fold_index}"))?;
        let fold = self.folds[fold_pos];
        let key = (indicator.to_string(), timeframe.to_string());
        let fold_key = (key.0.clone(), key.1.clone(), fold.index);
        let group_candidates = self
            .candidates
            .iter()
            .filter(|candidate| strategy_key(candidate) == key)
            .cloned()
            .collect::<Vec<_>>();
        if group_candidates.is_empty() {
            anyhow::bail!("unknown Optuna strategy group {indicator} {timeframe}");
        }
        let mut symbol_caches = self
            .fold_symbol_caches_by_strategy
            .remove(&fold_key)
            .unwrap_or_else(|| {
                self.data
                    .iter()
                    .map(|_| SimulationCache::default())
                    .collect::<Vec<_>>()
            });
        let mut results = Vec::with_capacity(batch.len());
        for item in batch {
            let template_index = item.trial_index.saturating_sub(1);
            let Some(template) = group_candidates.get(template_index) else {
                anyhow::bail!(
                    "{} {} fold {} trial_index {} exceeds configured trial count {}",
                    indicator,
                    timeframe,
                    fold.index,
                    item.trial_index,
                    group_candidates.len()
                );
            };
            let mut candidate = optuna_candidate_from_params(template, &item.params)?;
            candidate.id = fold_local_candidate_id(template.id, fold.index);

            let mut trial_scores = Vec::new();
            let mut training_scores = Vec::new();
            let mut trial_trade_count = 0usize;
            let mut pending_strategy_selections = Vec::new();
            let mut pending_best_selections = Vec::new();
            let mut max_timestamp_seen = 0i64;
            let objective_start_ms = fold_local_objective_start_ms(&self.config, &fold, &candidate)?;
            let trial_results = self
                .data
                .par_iter()
                .zip(symbol_caches.par_iter_mut())
                .map(
                    |((symbol, bars), cache)| -> Result<Option<(SimulationResult, i64)>> {
                        if !candidate_allowed_for_symbol(
                            self.config.strategy_set.as_deref(),
                            symbol,
                            &candidate,
                        ) {
                            return Ok(None);
                        }
                        let objective_bars =
                            bars_between_timestamps(bars, objective_start_ms, fold.is_end_ms);
                        let symbol_max_timestamp_seen = max_bar_timestamp_seen(&objective_bars);
                        ensure_optimizer_boundary(symbol_max_timestamp_seen, &fold)?;
                        let prepared = prepare_candidate_simulation(
                            symbol,
                            &objective_bars,
                            &candidate,
                            &self.config,
                            cache,
                        )?;
                        Ok(Some((
                            simulate_prepared_candidate(&objective_bars, &prepared, &[fold]),
                            symbol_max_timestamp_seen,
                        )))
                    },
                )
                .collect::<Result<Vec<_>>>()?
                .into_iter()
                .flatten()
                .collect::<Vec<_>>();
            for (result, symbol_max_timestamp_seen) in trial_results {
                max_timestamp_seen = max_timestamp_seen.max(symbol_max_timestamp_seen);
                trial_trade_count += result.trades.len();
                let training_trades = training_trades_for_fold(&result.trades, &self.config, &fold);
                let (training_start_ms, training_end_ms) = training_window(&self.config, &fold);
                let training_score = score_trades_in_window(
                    result.symbol.as_str(),
                    &result.candidate,
                    fold.index,
                    &training_trades,
                    &self.config,
                    training_start_ms,
                    training_end_ms,
                );
                let fold_trades = selection_trades_for_fold(&result.trades, &self.config, &fold);
                let fold_diagnostics = result.fold_diagnostics.first().cloned().unwrap_or_default();
                let score = score_trades_with_diagnostics(
                    result.symbol.as_str(),
                    &result.candidate,
                    fold.index,
                    &fold,
                    &fold_trades,
                    &self.config,
                    &fold_diagnostics,
                );
                accumulate_signal_fill_diagnostics(
                    &mut self.signal_fill_diagnostics,
                    &candidate,
                    result.symbol.as_str(),
                    fold.index,
                    &fold_diagnostics,
                    &score,
                );
                let selection_evaluation = fold_selection_evaluation(
                    &self.config,
                    result.symbol.as_str(),
                    &candidate,
                    &fold,
                    &result.trades,
                    &training_score,
                    &score,
                );
                let strategy_oos_key = (
                    candidate.indicator.as_str().to_string(),
                    candidate.timeframe.as_str().to_string(),
                    result.symbol.clone(),
                    fold.index,
                );
                if let Some(selection) =
                    strict_fold_selection(&selection_evaluation, candidate.indicator, Vec::new())
                {
                    pending_best_selections.push((
                        selection_evaluation.objective_score.fold_index,
                        selection.clone(),
                    ));
                    pending_strategy_selections.push((strategy_oos_key, selection));
                    self.staged_candidates_by_id
                        .insert(candidate.id, candidate.clone());
                }
                training_scores.push(training_score);
                trial_scores.push(selection_evaluation.objective_score);
            }
            ensure_optimizer_boundary(max_timestamp_seen, &fold)?;

            let objective = tpe_objective_breakdown(&training_scores, &trial_scores);
            let candidate_score = objective.objective_score;
            let rank_adjustment =
                tpe_candidate_rank_adjustment(&self.config, &candidate, &objective);
            let staged_strategy = self
                .staged_strategy_oos_by_fold
                .entry(fold_key.clone())
                .or_default();
            for (selection_key, selection) in pending_strategy_selections {
                insert_strategy_fold_selection(
                    staged_strategy,
                    selection_key,
                    adjusted_fold_selection(selection, rank_adjustment),
                );
            }
            let staged_best = self
                .staged_best_by_fold
                .entry(fold_key.clone())
                .or_default();
            for (staged_fold_index, selection) in pending_best_selections {
                insert_best_fold_selection(
                    staged_best,
                    staged_fold_index,
                    adjusted_fold_selection(selection, rank_adjustment),
                );
            }
            let best_entry = self
                .best_trial_by_strategy_fold
                .entry(fold_key.clone())
                .or_insert_with(|| TpeTrialEvaluation {
                    candidate: candidate.clone(),
                    mean_score: candidate_score,
                });
            if candidate_score > best_entry.mean_score {
                *best_entry = TpeTrialEvaluation {
                    candidate: candidate.clone(),
                    mean_score: candidate_score,
                };
            }
            let best = best_entry.clone();
            let candidate_key = strategy_key(&candidate);
            *self
                .progress_counts
                .entry(candidate_key.clone())
                .or_default() += 1;
            let row_completed = self
                .progress_counts
                .get(&candidate_key)
                .copied()
                .unwrap_or_default();
            self.completed_work += 1;
            let row_total = self
                .strategy_totals
                .get(&candidate_key)
                .copied()
                .unwrap_or(group_candidates.len() * self.folds.len().max(1))
                .max(1);
            update_strategy_row(
                &mut self.strategy_progress,
                &candidate_key,
                candidate_score,
                &trial_scores,
                trial_trade_count,
                row_completed,
                row_total,
            );

            let validation_trades = trial_scores.iter().map(|score| score.trades).sum::<usize>();
            let validation_profit_factor = mean_nonzero(
                trial_scores
                    .iter()
                    .map(|score| score.profit_factor)
                    .collect::<Vec<_>>()
                    .as_slice(),
            );
            let validation_net_return_pct = trial_scores
                .iter()
                .map(|score| score.net_return_pct)
                .sum::<f64>();
            let validation_max_drawdown_pct = trial_scores
                .iter()
                .map(|score| score.max_drawdown_pct)
                .fold(0.0, f64::max);
            let constraints = optuna_constraints(&objective, self.config.min_profit_factor);
            let params_signature = candidate_param_signature(&candidate);
            let (study_name, study_seed) = {
                let progress = self
                    .fold_study_progress
                    .entry(fold_key.clone())
                    .or_default();
                progress.trials_completed += 1;
                progress.max_timestamp_seen = progress.max_timestamp_seen.max(max_timestamp_seen);
                (progress.study_name.clone(), progress.seed)
            };
            self.fold_trial_trace.push(FoldTrialTraceRow {
                optimizer_mode: self.config.optimizer_mode.as_str().to_string(),
                offset_days: self.config.start_offset_days,
                fold_index: fold.index,
                indicator: candidate.indicator.as_str().to_string(),
                timeframe: candidate.timeframe.as_str().to_string(),
                study_name,
                seed: study_seed,
                trial_index: item.trial_index,
                candidate_id: candidate.id,
                objective_score: candidate_score,
                selected: false,
                constraint_0: constraints.first().copied().unwrap_or(0.0),
                params_signature: params_signature.clone(),
                max_timestamp_seen,
                validation_trades,
                validation_profit_factor,
                validation_net_return_pct,
                validation_max_drawdown_pct,
                training_scores: training_scores.len(),
                validation_scores: trial_scores.len(),
                lookback: candidate.lookback,
                atr_period: candidate.atr_period,
                entry_atr_multiple: candidate.entry_atr_multiple,
                stop_atr_multiple: candidate.stop_atr_multiple,
                target_atr_multiple: candidate.target_atr_multiple,
                time_stop_bars: candidate.time_stop_bars,
                strategy_4448_kama1_er: candidate.strategy_4448_kama1_er,
                strategy_4448_kama1_short: candidate.strategy_4448_kama1_short,
                strategy_4448_kama1_long: candidate.strategy_4448_kama1_long,
                strategy_4448_kama2_er: candidate.strategy_4448_kama2_er,
                strategy_4448_kama2_short: candidate.strategy_4448_kama2_short,
                strategy_4448_kama2_long: candidate.strategy_4448_kama2_long,
                strategy_4448_count_bars: candidate.strategy_4448_count_bars,
            });
            self.tpe_trial_trace.push(TpeTrialTraceRow {
                trial_index: row_completed,
                fold_index: Some(fold.index),
                candidate_id: candidate.id,
                indicator: candidate.indicator.as_str().to_string(),
                timeframe: candidate.timeframe.as_str().to_string(),
                objective_score: candidate_score,
                best_objective_score: best.mean_score,
                best_candidate_id: best.candidate.id,
                training_mean_score: objective.training_mean_score,
                validation_mean_score: objective.validation_mean_score,
                training_q25_score: objective.training_q25_score,
                training_median_score: objective.training_median_score,
                validation_q25_score: objective.validation_q25_score,
                validation_median_score: objective.validation_median_score,
                validation_score_stddev: objective.validation_score_stddev,
                training_eligible_fraction: objective.training_eligible_fraction,
                validation_eligible_fraction: objective.validation_eligible_fraction,
                validation_net_positive_fraction: objective.validation_net_positive_fraction,
                validation_trade_fit_fraction: objective.validation_trade_fit_fraction,
                validation_quality_fit_fraction: objective.validation_quality_fit_fraction,
                validation_median_profit_factor: objective.validation_median_profit_factor,
                training_nonnegative_score_fraction: objective.training_nonnegative_score_fraction,
                validation_nonnegative_score_fraction: objective
                    .validation_nonnegative_score_fraction,
                average_trade_penalty: objective.average_trade_penalty,
                average_profit_factor_penalty: objective.average_profit_factor_penalty,
                average_net_penalty: objective.average_net_penalty,
                average_fill_penalty: objective.average_fill_penalty,
                average_participation_penalty: objective.average_participation_penalty,
                base_objective_component: objective.base_objective_component,
                consistency_bonus: objective.consistency_bonus,
                paired_bonus: objective.paired_bonus,
                paired_selection_fraction: objective.paired_selection_fraction,
                paired_selection_count: objective.paired_selection_count,
                train_gap_penalty: objective.train_gap_penalty,
                dispersion_penalty: objective.dispersion_penalty,
                training_scores: training_scores.len(),
                validation_scores: trial_scores.len(),
                trial_trade_count,
                lookback: candidate.lookback,
                atr_period: candidate.atr_period,
                entry_atr_multiple: candidate.entry_atr_multiple,
                stop_atr_multiple: candidate.stop_atr_multiple,
                target_atr_multiple: candidate.target_atr_multiple,
                time_stop_bars: candidate.time_stop_bars,
                strategy_4448_kama1_er: candidate.strategy_4448_kama1_er,
                strategy_4448_kama1_short: candidate.strategy_4448_kama1_short,
                strategy_4448_kama1_long: candidate.strategy_4448_kama1_long,
                strategy_4448_kama2_er: candidate.strategy_4448_kama2_er,
                strategy_4448_kama2_short: candidate.strategy_4448_kama2_short,
                strategy_4448_kama2_long: candidate.strategy_4448_kama2_long,
                strategy_4448_count_bars: candidate.strategy_4448_count_bars,
            });
            results.push(OptunaTrialResult {
                trial_index: item.trial_index,
                fold_index: Some(fold.index),
                candidate_id: candidate.id,
                indicator: candidate.indicator.as_str().to_string(),
                timeframe: candidate.timeframe.as_str().to_string(),
                objective_score: candidate_score,
                best_objective_score: best.mean_score,
                best_candidate_id: best.candidate.id,
                training_mean_score: objective.training_mean_score,
                validation_mean_score: objective.validation_mean_score,
                training_q25_score: objective.training_q25_score,
                training_median_score: objective.training_median_score,
                validation_q25_score: objective.validation_q25_score,
                validation_median_score: objective.validation_median_score,
                validation_score_stddev: objective.validation_score_stddev,
                training_eligible_fraction: objective.training_eligible_fraction,
                validation_eligible_fraction: objective.validation_eligible_fraction,
                validation_net_positive_fraction: objective.validation_net_positive_fraction,
                validation_trade_fit_fraction: objective.validation_trade_fit_fraction,
                validation_quality_fit_fraction: objective.validation_quality_fit_fraction,
                validation_median_profit_factor: objective.validation_median_profit_factor,
                training_nonnegative_score_fraction: objective.training_nonnegative_score_fraction,
                validation_nonnegative_score_fraction: objective
                    .validation_nonnegative_score_fraction,
                average_trade_penalty: objective.average_trade_penalty,
                average_profit_factor_penalty: objective.average_profit_factor_penalty,
                average_net_penalty: objective.average_net_penalty,
                average_fill_penalty: objective.average_fill_penalty,
                average_participation_penalty: objective.average_participation_penalty,
                base_objective_component: objective.base_objective_component,
                consistency_bonus: objective.consistency_bonus,
                paired_bonus: objective.paired_bonus,
                paired_selection_fraction: objective.paired_selection_fraction,
                paired_selection_count: objective.paired_selection_count,
                train_gap_penalty: objective.train_gap_penalty,
                dispersion_penalty: objective.dispersion_penalty,
                training_scores: training_scores.len(),
                validation_scores: trial_scores.len(),
                trial_trade_count,
                validation_trades,
                validation_profit_factor,
                validation_net_return_pct,
                validation_max_drawdown_pct,
                max_timestamp_seen,
                constraints,
                params_signature,
                candidate,
            });

            if row_completed % self.progress_every == 0
                || row_completed == row_total
                || self.completed_work == self.total_work
            {
                self.write_progress(&candidate_key, row_completed, Some(fold.index))?;
            }
        }
        self.fold_symbol_caches_by_strategy
            .insert(fold_key, symbol_caches);
        Ok(results)
    }

    pub fn complete_fold_group(
        &mut self,
        indicator: &str,
        timeframe: &str,
        fold_index: usize,
    ) -> Result<()> {
        if self.config.optimizer_mode != OptimizerMode::PointInTimeFoldLocal {
            anyhow::bail!(
                "complete_fold_group requires optimizer_mode {}; current mode is {}",
                OptimizerMode::PointInTimeFoldLocal,
                self.config.optimizer_mode
            );
        }
        let fold = self
            .folds
            .iter()
            .find(|fold| fold.index == fold_index)
            .copied()
            .with_context(|| format!("unknown fold_index {fold_index}"))?;
        let fold_key = (indicator.to_string(), timeframe.to_string(), fold.index);
        let progress = self
            .fold_study_progress
            .get(&fold_key)
            .cloned()
            .unwrap_or_default();
        ensure_optimizer_boundary(progress.max_timestamp_seen, &fold)?;
        let staged_strategy = self
            .staged_strategy_oos_by_fold
            .remove(&fold_key)
            .unwrap_or_default();
        let staged_best = self
            .staged_best_by_fold
            .remove(&fold_key)
            .unwrap_or_default();
        let mut committed_by_key: BTreeMap<(String, String, String, usize), FoldSelection> =
            BTreeMap::new();
        for (selection_key, mut selection) in staged_strategy {
            let Some(candidate) = self
                .staged_candidates_by_id
                .get(&selection.score.candidate_id)
                .cloned()
            else {
                continue;
            };
            let Some((symbol, bars)) = self
                .data
                .iter()
                .find(|(symbol, _)| symbol == &selection_key.2)
            else {
                continue;
            };
            let mut cache = SimulationCache::default();
            let prepared =
                prepare_candidate_simulation(symbol, bars, &candidate, &self.config, &mut cache)?;
            let result = simulate_prepared_candidate(bars, &prepared, &[fold]);
            selection.trades = oos_trades_for_fold(&result.trades, &fold);
            insert_strategy_fold_selection(
                &mut self.strategy_oos_by_symbol_fold,
                selection_key.clone(),
                selection.clone(),
            );
            committed_by_key.insert(selection_key.clone(), selection.clone());
            upsert_candidate(&mut self.candidates, candidate.clone());
            self.mark_fold_trial_selected(fold.index, candidate.id);
            let provenance_row = self.optimizer_provenance_row(
                &fold,
                &selection_key,
                &selection,
                &candidate,
                &progress,
            );
            self.optimizer_provenance.push(provenance_row);
        }
        for (staged_fold_index, staged_selection) in staged_best {
            if let Some((_, committed)) =
                committed_by_key
                    .iter()
                    .find(|((_, _, _, key_fold_index), selection)| {
                        *key_fold_index == staged_fold_index
                            && selection.score.candidate_id == staged_selection.score.candidate_id
                    })
            {
                insert_best_fold_selection(
                    &mut self.best_by_fold,
                    staged_fold_index,
                    committed.clone(),
                );
            }
        }
        self.fold_symbol_caches_by_strategy.remove(&fold_key);
        self.write_committed_optimizer_artifacts()?;
        append_event(
            &self.run_dir,
            "fold",
            &format!(
                "{} {} fold {}: committed {} selected symbol folds",
                indicator,
                timeframe,
                fold.index,
                committed_by_key.len()
            ),
        )?;
        Ok(())
    }

    pub fn evaluate_batch_json(
        &mut self,
        indicator: &str,
        timeframe: &str,
        batch_json: &str,
    ) -> Result<Vec<OptunaTrialResult>> {
        let batch = serde_json::from_str::<Vec<OptunaBatchTrial>>(batch_json)
            .with_context(|| "parse Optuna batch JSON")?;
        self.evaluate_batch(indicator, timeframe, &batch)
    }

    pub fn evaluate_batch(
        &mut self,
        indicator: &str,
        timeframe: &str,
        batch: &[OptunaBatchTrial],
    ) -> Result<Vec<OptunaTrialResult>> {
        let key = (indicator.to_string(), timeframe.to_string());
        let group_candidates = self
            .candidates
            .iter()
            .filter(|candidate| strategy_key(candidate) == key)
            .cloned()
            .collect::<Vec<_>>();
        if group_candidates.is_empty() {
            anyhow::bail!("unknown Optuna strategy group {indicator} {timeframe}");
        }
        let mut symbol_caches = self
            .symbol_caches_by_strategy
            .remove(&key)
            .unwrap_or_else(|| {
                self.data
                    .iter()
                    .map(|_| SimulationCache::default())
                    .collect::<Vec<_>>()
            });
        let mut results = Vec::with_capacity(batch.len());
        for item in batch {
            let template_index = item.trial_index.saturating_sub(1);
            let Some(template) = group_candidates.get(template_index) else {
                anyhow::bail!(
                    "{} {} trial_index {} exceeds configured trial count {}",
                    indicator,
                    timeframe,
                    item.trial_index,
                    group_candidates.len()
                );
            };
            let candidate = optuna_candidate_from_params(template, &item.params)?;
            if let Some(slot) = self
                .candidates
                .iter_mut()
                .find(|slot| slot.id == candidate.id)
            {
                *slot = candidate.clone();
            }

            let mut trial_scores = Vec::new();
            let mut training_scores = Vec::new();
            let mut trial_trade_count = 0usize;
            let mut pending_strategy_selections = Vec::new();
            let mut pending_best_selections = Vec::new();
            let trial_results = self
                .data
                .par_iter()
                .zip(symbol_caches.par_iter_mut())
                .map(
                    |((symbol, bars), cache)| -> Result<Option<SimulationResult>> {
                        if !candidate_allowed_for_symbol(
                            self.config.strategy_set.as_deref(),
                            symbol,
                            &candidate,
                        ) {
                            return Ok(None);
                        }
                        let prepared = prepare_candidate_simulation(
                            symbol,
                            bars,
                            &candidate,
                            &self.config,
                            cache,
                        )?;
                        Ok(Some(simulate_prepared_candidate(
                            bars,
                            &prepared,
                            &self.folds,
                        )))
                    },
                )
                .collect::<Result<Vec<_>>>()?
                .into_iter()
                .flatten()
                .collect::<Vec<_>>();
            for result in trial_results {
                trial_trade_count += result.trades.len();
                for (fold_pos, fold) in self.folds.iter().enumerate() {
                    let training_trades =
                        training_trades_for_fold(&result.trades, &self.config, fold);
                    let (training_start_ms, training_end_ms) = training_window(&self.config, fold);
                    let training_score = score_trades_in_window(
                        result.symbol.as_str(),
                        &result.candidate,
                        fold.index,
                        &training_trades,
                        &self.config,
                        training_start_ms,
                        training_end_ms,
                    );
                    let fold_trades = selection_trades_for_fold(&result.trades, &self.config, fold);
                    let fold_diagnostics = result
                        .fold_diagnostics
                        .get(fold_pos)
                        .cloned()
                        .unwrap_or_default();
                    let score = score_trades_with_diagnostics(
                        result.symbol.as_str(),
                        &result.candidate,
                        fold.index,
                        fold,
                        &fold_trades,
                        &self.config,
                        &fold_diagnostics,
                    );
                    accumulate_signal_fill_diagnostics(
                        &mut self.signal_fill_diagnostics,
                        &candidate,
                        result.symbol.as_str(),
                        fold.index,
                        &fold_diagnostics,
                        &score,
                    );
                    let selection_evaluation = fold_selection_evaluation(
                        &self.config,
                        result.symbol.as_str(),
                        &candidate,
                        fold,
                        &result.trades,
                        &training_score,
                        &score,
                    );
                    let strategy_oos_key = (
                        candidate.indicator.as_str().to_string(),
                        candidate.timeframe.as_str().to_string(),
                        result.symbol.clone(),
                        fold.index,
                    );
                    if let Some(selection) = strict_fold_selection(
                        &selection_evaluation,
                        candidate.indicator,
                        oos_trades_for_fold(&result.trades, fold),
                    ) {
                        pending_best_selections.push((
                            selection_evaluation.objective_score.fold_index,
                            selection.clone(),
                        ));
                        pending_strategy_selections.push((strategy_oos_key, selection));
                    }
                    training_scores.push(training_score);
                    trial_scores.push(selection_evaluation.objective_score);
                }
            }

            let objective = tpe_objective_breakdown(&training_scores, &trial_scores);
            let candidate_score = objective.objective_score;
            let rank_adjustment =
                tpe_candidate_rank_adjustment(&self.config, &candidate, &objective);
            for (key, selection) in pending_strategy_selections {
                insert_strategy_fold_selection(
                    &mut self.strategy_oos_by_symbol_fold,
                    key,
                    adjusted_fold_selection(selection, rank_adjustment),
                );
            }
            for (fold_index, selection) in pending_best_selections {
                insert_best_fold_selection(
                    &mut self.best_by_fold,
                    fold_index,
                    adjusted_fold_selection(selection, rank_adjustment),
                );
            }
            let best_entry = self
                .best_trial_by_strategy
                .entry(key.clone())
                .or_insert_with(|| TpeTrialEvaluation {
                    candidate: candidate.clone(),
                    mean_score: candidate_score,
                });
            if candidate_score > best_entry.mean_score {
                *best_entry = TpeTrialEvaluation {
                    candidate: candidate.clone(),
                    mean_score: candidate_score,
                };
            }
            let best = best_entry.clone();
            let candidate_key = strategy_key(&candidate);
            *self
                .progress_counts
                .entry(candidate_key.clone())
                .or_default() += 1;
            let row_completed = self
                .progress_counts
                .get(&candidate_key)
                .copied()
                .unwrap_or_default();
            self.completed_work += 1;
            update_strategy_row(
                &mut self.strategy_progress,
                &candidate_key,
                candidate_score,
                &trial_scores,
                trial_trade_count,
                row_completed,
                self.strategy_totals
                    .get(&candidate_key)
                    .copied()
                    .unwrap_or(group_candidates.len())
                    .max(1),
            );

            let validation_trades = trial_scores.iter().map(|score| score.trades).sum::<usize>();
            let validation_profit_factor = mean_nonzero(
                trial_scores
                    .iter()
                    .map(|score| score.profit_factor)
                    .collect::<Vec<_>>()
                    .as_slice(),
            );
            let validation_net_return_pct = trial_scores
                .iter()
                .map(|score| score.net_return_pct)
                .sum::<f64>();
            let validation_max_drawdown_pct = trial_scores
                .iter()
                .map(|score| score.max_drawdown_pct)
                .fold(0.0, f64::max);
            let constraints = optuna_constraints(&objective, self.config.min_profit_factor);
            self.tpe_trial_trace.push(TpeTrialTraceRow {
                trial_index: row_completed,
                fold_index: None,
                candidate_id: candidate.id,
                indicator: candidate.indicator.as_str().to_string(),
                timeframe: candidate.timeframe.as_str().to_string(),
                objective_score: candidate_score,
                best_objective_score: best.mean_score,
                best_candidate_id: best.candidate.id,
                training_mean_score: objective.training_mean_score,
                validation_mean_score: objective.validation_mean_score,
                training_q25_score: objective.training_q25_score,
                training_median_score: objective.training_median_score,
                validation_q25_score: objective.validation_q25_score,
                validation_median_score: objective.validation_median_score,
                validation_score_stddev: objective.validation_score_stddev,
                training_eligible_fraction: objective.training_eligible_fraction,
                validation_eligible_fraction: objective.validation_eligible_fraction,
                validation_net_positive_fraction: objective.validation_net_positive_fraction,
                validation_trade_fit_fraction: objective.validation_trade_fit_fraction,
                validation_quality_fit_fraction: objective.validation_quality_fit_fraction,
                validation_median_profit_factor: objective.validation_median_profit_factor,
                training_nonnegative_score_fraction: objective.training_nonnegative_score_fraction,
                validation_nonnegative_score_fraction: objective
                    .validation_nonnegative_score_fraction,
                average_trade_penalty: objective.average_trade_penalty,
                average_profit_factor_penalty: objective.average_profit_factor_penalty,
                average_net_penalty: objective.average_net_penalty,
                average_fill_penalty: objective.average_fill_penalty,
                average_participation_penalty: objective.average_participation_penalty,
                base_objective_component: objective.base_objective_component,
                consistency_bonus: objective.consistency_bonus,
                paired_bonus: objective.paired_bonus,
                paired_selection_fraction: objective.paired_selection_fraction,
                paired_selection_count: objective.paired_selection_count,
                train_gap_penalty: objective.train_gap_penalty,
                dispersion_penalty: objective.dispersion_penalty,
                training_scores: training_scores.len(),
                validation_scores: trial_scores.len(),
                trial_trade_count,
                lookback: candidate.lookback,
                atr_period: candidate.atr_period,
                entry_atr_multiple: candidate.entry_atr_multiple,
                stop_atr_multiple: candidate.stop_atr_multiple,
                target_atr_multiple: candidate.target_atr_multiple,
                time_stop_bars: candidate.time_stop_bars,
                strategy_4448_kama1_er: candidate.strategy_4448_kama1_er,
                strategy_4448_kama1_short: candidate.strategy_4448_kama1_short,
                strategy_4448_kama1_long: candidate.strategy_4448_kama1_long,
                strategy_4448_kama2_er: candidate.strategy_4448_kama2_er,
                strategy_4448_kama2_short: candidate.strategy_4448_kama2_short,
                strategy_4448_kama2_long: candidate.strategy_4448_kama2_long,
                strategy_4448_count_bars: candidate.strategy_4448_count_bars,
            });
            results.push(OptunaTrialResult {
                trial_index: row_completed,
                fold_index: None,
                candidate_id: candidate.id,
                indicator: candidate.indicator.as_str().to_string(),
                timeframe: candidate.timeframe.as_str().to_string(),
                objective_score: candidate_score,
                best_objective_score: best.mean_score,
                best_candidate_id: best.candidate.id,
                training_mean_score: objective.training_mean_score,
                validation_mean_score: objective.validation_mean_score,
                training_q25_score: objective.training_q25_score,
                training_median_score: objective.training_median_score,
                validation_q25_score: objective.validation_q25_score,
                validation_median_score: objective.validation_median_score,
                validation_score_stddev: objective.validation_score_stddev,
                training_eligible_fraction: objective.training_eligible_fraction,
                validation_eligible_fraction: objective.validation_eligible_fraction,
                validation_net_positive_fraction: objective.validation_net_positive_fraction,
                validation_trade_fit_fraction: objective.validation_trade_fit_fraction,
                validation_quality_fit_fraction: objective.validation_quality_fit_fraction,
                validation_median_profit_factor: objective.validation_median_profit_factor,
                training_nonnegative_score_fraction: objective.training_nonnegative_score_fraction,
                validation_nonnegative_score_fraction: objective
                    .validation_nonnegative_score_fraction,
                average_trade_penalty: objective.average_trade_penalty,
                average_profit_factor_penalty: objective.average_profit_factor_penalty,
                average_net_penalty: objective.average_net_penalty,
                average_fill_penalty: objective.average_fill_penalty,
                average_participation_penalty: objective.average_participation_penalty,
                base_objective_component: objective.base_objective_component,
                consistency_bonus: objective.consistency_bonus,
                paired_bonus: objective.paired_bonus,
                paired_selection_fraction: objective.paired_selection_fraction,
                paired_selection_count: objective.paired_selection_count,
                train_gap_penalty: objective.train_gap_penalty,
                dispersion_penalty: objective.dispersion_penalty,
                training_scores: training_scores.len(),
                validation_scores: trial_scores.len(),
                trial_trade_count,
                validation_trades,
                validation_profit_factor,
                validation_net_return_pct,
                validation_max_drawdown_pct,
                max_timestamp_seen: self
                    .data
                    .iter()
                    .filter_map(|(_, bars)| bars.last().map(|bar| bar.open_time_ms))
                    .max()
                    .unwrap_or(0),
                constraints,
                params_signature: candidate_param_signature(&candidate),
                candidate,
            });

            if row_completed % self.progress_every == 0
                || row_completed
                    == self
                        .strategy_totals
                        .get(&candidate_key)
                        .copied()
                        .unwrap_or(group_candidates.len())
                || self.completed_work == self.total_work
            {
                self.write_progress(&candidate_key, row_completed, None)?;
            }
        }
        self.symbol_caches_by_strategy.insert(key, symbol_caches);
        Ok(results)
    }

    pub fn complete_group(&mut self, indicator: &str, timeframe: &str) -> Result<()> {
        let key = (indicator.to_string(), timeframe.to_string());
        if let Some(total) = self.strategy_totals.get(&key).copied() {
            self.progress_counts.insert(key.clone(), total);
        }
        if let Some(row) = self
            .strategy_progress
            .iter_mut()
            .find(|row| row.indicator == key.0 && row.timeframe == key.1)
        {
            row.status = "complete".to_string();
            row.progress_pct = 100.0;
            row.progress_label = format!(
                "{}/{} trials",
                row.parameter_candidates, row.parameter_candidates
            );
        }
        write_csv(self.run_dir.join("candidates.csv"), &self.candidates)?;
        write_csv(self.run_dir.join(TPE_TRIALS_FILE), &self.tpe_trial_trace)?;
        write_csv(self.run_dir.join(FOLD_TRIALS_FILE), &self.fold_trial_trace)?;
        write_csv(
            self.run_dir.join(OPTIMIZER_PROVENANCE_CSV_FILE),
            &self.optimizer_provenance,
        )?;
        write_optimizer_provenance_jsonl(&self.run_dir, &self.optimizer_provenance)?;
        write_signal_fill_diagnostics(&self.run_dir, &self.signal_fill_diagnostics)?;
        let strategy_oos_context = StrategyOosContext::new(
            &self.config,
            &self.folds,
            &self.data,
            &self.candidates,
            &self.strategy_progress,
            &self.strategy_oos_by_symbol_fold,
            &self.close_by_symbol,
        )?;
        write_completed_strategy_oos_snapshot(&self.run_dir, &key, &strategy_oos_context)?;
        write_strategy_progress(&self.run_dir, &self.strategy_progress)?;
        append_event(
            &self.run_dir,
            "strategy",
            &format!("{} {}: complete", key.0, key.1),
        )?;
        Ok(())
    }

    pub fn finalize(&mut self) -> Result<PathBuf> {
        write_strategy_progress(&self.run_dir, &self.strategy_progress)?;
        write_strategy_oos_status_snapshot(&self.run_dir, &self.strategy_progress)?;
        write_status(
            &self.run_dir,
            &status(
                &self.config.run_id,
                RunPhase::WritingArtifacts,
                90.0,
                "writing artifacts",
            ),
        )?;
        let strategy_oos_results = build_strategy_oos_results(
            &self.config,
            &self.folds,
            &self.data,
            &self.candidates,
            &self.strategy_progress,
            &self.strategy_oos_by_symbol_fold,
            &self.close_by_symbol,
        )?;
        let data_symbols = self
            .data
            .iter()
            .map(|(symbol, _)| symbol.clone())
            .collect::<Vec<_>>();
        let artifact_selection = primary_artifact_selection(
            &self.strategy_progress,
            &data_symbols,
            &self.strategy_oos_by_symbol_fold,
            &self.best_by_fold,
            self.config.fixed_notional,
        );
        let account_artifacts = build_account_artifacts(
            &self.config,
            &self.folds,
            &artifact_selection.trades,
            &self.data,
        )?;
        let risk_managed_artifacts =
            if let Some(risk_managed_trades) = artifact_selection.risk_managed_trades.clone() {
                let account_artifacts = build_account_artifacts(
                    &self.config,
                    &self.folds,
                    &risk_managed_trades,
                    &self.data,
                )?;
                let summary = summarize(
                    &self.config,
                    self.folds.len(),
                    self.candidates.len(),
                    &risk_managed_trades,
                    &account_artifacts.stats,
                    &format!("{} risk-managed", artifact_selection.best_indicator),
                );
                Some(ManagedRunArtifacts {
                    summary,
                    trades: risk_managed_trades,
                    account_artifacts,
                })
            } else {
                None
            };
        let summary = summarize(
            &self.config,
            self.folds.len(),
            self.candidates.len(),
            &artifact_selection.trades,
            &account_artifacts.stats,
            &artifact_selection.best_indicator,
        );
        write_json(
            self.run_dir.join(STRATEGY_OOS_RESULTS_FILE),
            &strategy_oos_results,
        )?;
        write_csv(self.run_dir.join(TPE_TRIALS_FILE), &self.tpe_trial_trace)?;
        write_csv(self.run_dir.join(FOLD_TRIALS_FILE), &self.fold_trial_trace)?;
        write_csv(
            self.run_dir.join(OPTIMIZER_PROVENANCE_CSV_FILE),
            &self.optimizer_provenance,
        )?;
        write_optimizer_provenance_jsonl(&self.run_dir, &self.optimizer_provenance)?;
        write_artifacts(
            &self.run_dir,
            &summary,
            &self.folds,
            &self.candidates,
            &artifact_selection.scores,
            &artifact_selection.trades,
            &account_artifacts,
            artifact_selection.best_fold_scores.as_deref(),
            artifact_selection.best_fold_trades.as_deref(),
            risk_managed_artifacts.as_ref(),
        )?;
        append_event(&self.run_dir, "complete", "Optuna WFO run complete")?;
        write_status(
            &self.run_dir,
            &status_with_active(
                &self.config.run_id,
                RunPhase::Complete,
                100.0,
                "complete",
                ActiveStatus {
                    offset_days: Some(self.config.start_offset_days),
                    fold_count: Some(self.folds.len()),
                    optimizer_mode: Some(self.config.optimizer_mode),
                    ..ActiveStatus::default()
                },
            ),
        )?;
        Ok(self.run_dir.clone())
    }

    fn mark_fold_trial_selected(&mut self, fold_index: usize, candidate_id: usize) {
        for row in &mut self.fold_trial_trace {
            if row.fold_index == fold_index && row.candidate_id == candidate_id {
                row.selected = true;
            }
        }
    }

    fn optimizer_provenance_row(
        &self,
        fold: &Fold,
        selection_key: &(String, String, String, usize),
        selection: &FoldSelection,
        candidate: &Candidate,
        progress: &FoldStudyProgress,
    ) -> OptimizerProvenanceRow {
        let oos_refs = selection.trades.iter().collect::<Vec<_>>();
        let oos_score = score_trades_in_window(
            &selection_key.2,
            candidate,
            fold.index,
            &oos_refs,
            &self.config,
            fold.oos_start_ms,
            fold.oos_end_ms,
        );
        let oos_total_pnl = selection.trades.iter().map(|trade| trade.pnl).sum::<f64>();
        OptimizerProvenanceRow {
            optimizer_mode: self.config.optimizer_mode.as_str().to_string(),
            offset_days: self.config.start_offset_days,
            fold_index: fold.index,
            strategy: selection_key.0.clone(),
            timeframe: selection_key.1.clone(),
            symbol: selection_key.2.clone(),
            study_name: progress.study_name.clone(),
            seed: progress.seed,
            trials_requested: progress.trials_requested,
            trials_completed: progress.trials_completed,
            optimizer_scope_start: fold_optimizer_scored_start_ms(&self.config, fold),
            optimizer_scope_end: fold.is_end_ms,
            max_timestamp_seen: progress.max_timestamp_seen,
            selected_candidate_id: selection.score.candidate_id,
            params_signature: candidate_param_signature(candidate),
            is_score: selection.score.score,
            is_profit_factor: selection.score.profit_factor,
            is_trades: selection.score.trades,
            is_max_drawdown_pct: selection.score.max_drawdown_pct,
            oos_total_pnl,
            oos_net_return_pct: oos_score.net_return_pct,
            oos_profit_factor: oos_score.profit_factor,
            oos_trades: selection.trades.len(),
            oos_max_drawdown_pct: oos_score.max_drawdown_pct,
            selection_status: "selected".to_string(),
            selection_reason: "passed fold-local IS selection criteria".to_string(),
        }
    }

    fn write_committed_optimizer_artifacts(&self) -> Result<()> {
        write_csv(self.run_dir.join(TPE_TRIALS_FILE), &self.tpe_trial_trace)?;
        write_csv(self.run_dir.join(FOLD_TRIALS_FILE), &self.fold_trial_trace)?;
        write_csv(
            self.run_dir.join(OPTIMIZER_PROVENANCE_CSV_FILE),
            &self.optimizer_provenance,
        )?;
        write_optimizer_provenance_jsonl(&self.run_dir, &self.optimizer_provenance)?;
        let fold_scores = self
            .best_by_fold
            .values()
            .map(|selection| selection.score.clone())
            .collect::<Vec<_>>();
        write_csv(self.run_dir.join("best_by_indicator.csv"), &fold_scores)?;
        write_csv(self.run_dir.join("candidates.csv"), &self.candidates)?;
        if !self.best_by_fold.is_empty() {
            let mut live_oos_trades = self
                .best_by_fold
                .values()
                .flat_map(|selection| selection.trades.clone())
                .collect::<Vec<_>>();
            live_oos_trades.sort_by_key(|trade| trade.exit_time_ms);
            let account_artifacts =
                build_account_artifacts(&self.config, &self.folds, &live_oos_trades, &self.data)?;
            let sampled_equity =
                downsample_equity(&account_artifacts.equity, OOS_EQUITY_ARTIFACT_MAX_POINTS);
            write_csv(self.run_dir.join("oos_equity.csv"), &sampled_equity)?;
            write_csv(self.run_dir.join("oos_trades.csv"), &live_oos_trades)?;
        }
        Ok(())
    }

    fn write_progress(
        &self,
        candidate_key: &(String, String),
        row_completed: usize,
        active_fold_index: Option<usize>,
    ) -> Result<()> {
        let elapsed_seconds = self.started.elapsed().as_secs().max(1);
        let remaining = self.total_work.saturating_sub(self.completed_work);
        let eta_seconds = (remaining as u64 * elapsed_seconds) / self.completed_work.max(1) as u64;
        let progress_pct = 15.0 + 75.0 * self.completed_work as f64 / self.total_work as f64;
        write_status(
            &self.run_dir,
            &status_with_active(
                &self.config.run_id,
                RunPhase::Simulating,
                progress_pct,
                &format!(
                    "sampled {}/{} Optuna trials",
                    self.completed_work, self.total_work
                ),
                ActiveStatus {
                    symbol: None,
                    indicator: Some(candidate_key.0.as_str()),
                    timeframe: Some(candidate_key.1.as_str()),
                    offset_days: Some(self.config.start_offset_days),
                    fold_index: active_fold_index,
                    fold_count: Some(self.folds.len()),
                    optimizer_mode: Some(self.config.optimizer_mode),
                    eta_seconds: Some(eta_seconds),
                },
            ),
        )?;
        write_strategy_progress(&self.run_dir, &self.strategy_progress)?;
        write_strategy_oos_status_snapshot(&self.run_dir, &self.strategy_progress)?;
        write_csv(self.run_dir.join(TPE_TRIALS_FILE), &self.tpe_trial_trace)?;
        write_csv(self.run_dir.join(FOLD_TRIALS_FILE), &self.fold_trial_trace)?;
        let fold_scores = self
            .best_by_fold
            .values()
            .map(|selection| selection.score.clone())
            .collect::<Vec<_>>();
        write_csv(self.run_dir.join("best_by_indicator.csv"), &fold_scores)?;
        write_csv(self.run_dir.join("candidates.csv"), &self.candidates)?;
        if !self.best_by_fold.is_empty() {
            let mut live_oos_trades = self
                .best_by_fold
                .values()
                .flat_map(|selection| selection.trades.clone())
                .collect::<Vec<_>>();
            live_oos_trades.sort_by_key(|trade| trade.exit_time_ms);
            if let Ok(account_artifacts) =
                build_account_artifacts(&self.config, &self.folds, &live_oos_trades, &self.data)
            {
                let sampled_equity =
                    downsample_equity(&account_artifacts.equity, OOS_EQUITY_ARTIFACT_MAX_POINTS);
                let _ = write_csv(self.run_dir.join("oos_equity.csv"), &sampled_equity);
                let _ = write_csv(self.run_dir.join("oos_trades.csv"), &live_oos_trades);
            }
        }
        append_event(
            &self.run_dir,
            "progress",
            &format!(
                "{}/{}: {} {} Optuna trial {}/{}",
                self.completed_work,
                self.total_work,
                candidate_key.0,
                candidate_key.1,
                row_completed,
                self.strategy_totals
                    .get(candidate_key)
                    .copied()
                    .unwrap_or_default()
            ),
        )?;
        Ok(())
    }
}

fn optuna_candidate_from_params(
    template: &Candidate,
    params: &serde_json::Value,
) -> Result<Candidate> {
    if matches!(
        template.indicator,
        IndicatorKind::Strategy336KamaTpo
            | IndicatorKind::Strategy3635KamaTpo
            | IndicatorKind::Strategy3938KamaTpo
    ) {
        return Ok(source_sqx_kama_tpo_candidate(template));
    }
    if template.indicator == IndicatorKind::Strategy4448KamaKer {
        let kama1_short = optuna_usize(params, "strategy_4448_kama1_short", 45)?.clamp(2, 120);
        let kama1_long = optuna_usize(params, "strategy_4448_kama1_long", 19)?.clamp(2, 160);
        let (kama1_short, kama1_long) = ordered_period_pair(kama1_short, kama1_long, 2, 160);
        let kama2_short = optuna_usize(params, "strategy_4448_kama2_short", 46)?.clamp(2, 30);
        let kama2_long = optuna_usize(params, "strategy_4448_kama2_long", 15)?.clamp(2, 160);
        let (kama2_short, kama2_long) = ordered_period_pair(kama2_short, kama2_long, 2, 160);
        return Ok(Candidate {
            id: template.id,
            indicator: template.indicator,
            timeframe: template.timeframe,
            signal_polarity: 1,
            entry_mode: EntryMode::Pullback,
            lookback: optuna_usize(params, "strategy_4448_lookback", 47)?.clamp(5, 120),
            atr_period: round_to_step(
                optuna_usize(params, "strategy_4448_atr_period", 80)?.clamp(20, 200),
                5,
            ),
            entry_atr_multiple: 0.0,
            stop_atr_multiple: optuna_f64(params, "strategy_4448_stop_atr_multiple", 2.6)?
                .clamp(MIN_EXIT_STOP_ATR_MULTIPLE, MAX_EXIT_STOP_ATR_MULTIPLE),
            target_atr_multiple: optuna_f64(params, "strategy_4448_target_atr_multiple", 7.7)?
                .clamp(2.0, MAX_EXIT_TARGET_ATR_MULTIPLE)
                .min(
                    optuna_f64(params, "strategy_4448_stop_atr_multiple", 2.6)?
                        .clamp(MIN_EXIT_STOP_ATR_MULTIPLE, MAX_EXIT_STOP_ATR_MULTIPLE)
                        * MAX_EXIT_TARGET_STOP_RATIO,
                ),
            time_stop_bars: Some(28),
            hurst_min: None,
            hurst_max: None,
            shannon_max: None,
            strategy_4448_kama1_er: optuna_usize(params, "strategy_4448_kama1_er", 30)?
                .clamp(5, 120),
            strategy_4448_kama1_short: kama1_short,
            strategy_4448_kama1_long: kama1_long,
            strategy_4448_kama2_er: optuna_usize(params, "strategy_4448_kama2_er", 37)?
                .clamp(5, 60),
            strategy_4448_kama2_short: kama2_short.min(30),
            strategy_4448_kama2_long: kama2_long,
            strategy_4448_count_bars: optuna_usize(params, "strategy_4448_count_bars", 9)?
                .clamp(3, 15),
        });
    }
    let signal_polarity_value = optuna_i64(params, "signal_polarity", 1)?;
    let signal_polarity = if signal_polarity_value <= 0 { -1 } else { 1 };
    let entry_mode = match optuna_string(params, "entry_mode").as_deref() {
        Some("breakout") => EntryMode::Breakout,
        Some("pullback") | None => EntryMode::Pullback,
        Some(other) => anyhow::bail!("unknown entry_mode {other}; supported: pullback, breakout"),
    };
    let lookback = if params.get("lookback_bars").is_some() {
        optuna_usize(params, "lookback_bars", template.lookback)?
            .clamp(TPE_MIN_LOOKBACK_BARS, TPE_MAX_LOOKBACK_BARS)
    } else {
        minutes_to_timeframe_bars_capped(
            optuna_i64(
                params,
                "lookback_minutes",
                template.lookback as i64 * template.timeframe.minutes(),
            )?,
            template.timeframe,
            TPE_MIN_LOOKBACK_BARS,
            TPE_MAX_LOOKBACK_BARS,
        )
    };
    let atr_period = if params.get("atr_bars").is_some() {
        round_to_step(
            optuna_usize(params, "atr_bars", template.atr_period)?
                .clamp(TPE_MIN_ATR_BARS, TPE_MAX_ATR_BARS),
            TPE_ATR_STEP_BARS,
        )
    } else {
        round_to_step(
            minutes_to_timeframe_bars_capped(
                optuna_i64(
                    params,
                    "atr_minutes",
                    template.atr_period as i64 * template.timeframe.minutes(),
                )?,
                template.timeframe,
                TPE_MIN_ATR_BARS,
                TPE_MAX_ATR_BARS,
            ),
            TPE_ATR_STEP_BARS,
        )
    };
    let hurst_min_value = optuna_f64(params, "hurst_min", -0.25)?.clamp(-0.25, 0.65);
    let mut hurst_max_value = optuna_f64(params, "hurst_max", 1.25)?.clamp(0.45, 1.25);
    if hurst_min_value > 0.0 && hurst_max_value <= hurst_min_value {
        hurst_max_value = (hurst_min_value + 0.05).min(1.0);
    }
    let shannon_max_value = optuna_f64(params, "shannon_max", 1.25)?.clamp(0.75, 1.25);
    let time_stop_bars = if params.get("time_stop_bars").is_some() {
        optuna_usize(params, "time_stop_bars", 24)?.clamp(0, TPE_MAX_TIME_STOP_BARS)
    } else {
        let time_stop_minutes = optuna_i64(
            params,
            "time_stop_minutes",
            24 * template.timeframe.minutes(),
        )?;
        if time_stop_minutes > 0 {
            minutes_to_timeframe_bars(time_stop_minutes, template.timeframe, 1)
                .clamp(1, TPE_MAX_TIME_STOP_BARS)
        } else {
            0
        }
    };
    let stop_atr_multiple = optuna_f64(params, "stop_atr_multiple", 1.5)?
        .clamp(MIN_EXIT_STOP_ATR_MULTIPLE, MAX_EXIT_STOP_ATR_MULTIPLE);
    Ok(Candidate {
        id: template.id,
        indicator: template.indicator,
        timeframe: template.timeframe,
        signal_polarity,
        entry_mode,
        lookback,
        atr_period,
        entry_atr_multiple: optuna_f64(params, "entry_atr_multiple", 0.5)?
            .clamp(0.0, TPE_MAX_ENTRY_ATR_MULTIPLE),
        stop_atr_multiple,
        target_atr_multiple: optuna_f64(params, "target_atr_multiple", 3.0)?
            .clamp(TPE_MIN_TARGET_ATR_MULTIPLE, MAX_EXIT_TARGET_ATR_MULTIPLE)
            .min(stop_atr_multiple * MAX_EXIT_TARGET_STOP_RATIO),
        time_stop_bars: (time_stop_bars > 0).then_some(time_stop_bars),
        hurst_min: (hurst_min_value >= 0.20).then_some(hurst_min_value),
        hurst_max: (hurst_max_value <= 0.95).then_some(hurst_max_value),
        shannon_max: (shannon_max_value <= 0.98).then_some(shannon_max_value),
        ..Candidate::default()
    })
}

fn ordered_period_pair(
    left: usize,
    right: usize,
    min_period: usize,
    max_period: usize,
) -> (usize, usize) {
    let upper_fast = max_period.saturating_sub(1).max(min_period);
    let mut fast = left.min(right).clamp(min_period, upper_fast);
    let mut slow = left.max(right).clamp(min_period + 1, max_period);
    if slow <= fast {
        slow = (fast + 1).min(max_period);
        if slow <= fast {
            fast = slow.saturating_sub(1).max(min_period);
        }
    }
    (fast, slow)
}

fn optuna_constraints(_objective: &TpeObjectiveBreakdown, _min_profit_factor: f64) -> Vec<f64> {
    vec![0.0]
}

fn optuna_i64(params: &serde_json::Value, key: &str, default: i64) -> Result<i64> {
    match params.get(key) {
        None | Some(serde_json::Value::Null) => Ok(default),
        Some(value) => value
            .as_i64()
            .or_else(|| value.as_u64().and_then(|value| i64::try_from(value).ok()))
            .or_else(|| value.as_f64().map(|value| value.round() as i64))
            .or_else(|| value.as_str().and_then(|value| value.parse::<i64>().ok()))
            .with_context(|| format!("Optuna param {key} must be an integer")),
    }
}

fn optuna_usize(params: &serde_json::Value, key: &str, default: usize) -> Result<usize> {
    let value = optuna_i64(params, key, default as i64)?;
    usize::try_from(value).with_context(|| format!("Optuna param {key} must be non-negative"))
}

fn optuna_f64(params: &serde_json::Value, key: &str, default: f64) -> Result<f64> {
    match params.get(key) {
        None | Some(serde_json::Value::Null) => Ok(default),
        Some(value) => value
            .as_f64()
            .or_else(|| value.as_i64().map(|value| value as f64))
            .or_else(|| value.as_u64().map(|value| value as f64))
            .or_else(|| value.as_str().and_then(|value| value.parse::<f64>().ok()))
            .filter(|value| value.is_finite())
            .with_context(|| format!("Optuna param {key} must be a finite number")),
    }
}

fn optuna_string(params: &serde_json::Value, key: &str) -> Option<String> {
    params
        .get(key)
        .and_then(|value| value.as_str())
        .map(|value| value.trim().to_lowercase())
        .filter(|value| !value.is_empty())
}

fn round_to_step(value: usize, step: usize) -> usize {
    if step == 0 {
        return value;
    }
    ((value + step / 2) / step) * step
}

fn mean_nonzero(values: &[f64]) -> f64 {
    let filtered = values
        .iter()
        .copied()
        .filter(|value| value.is_finite() && *value > 0.0)
        .collect::<Vec<_>>();
    if filtered.is_empty() {
        0.0
    } else {
        filtered.iter().sum::<f64>() / filtered.len() as f64
    }
}

fn candidate_param_signature(candidate: &Candidate) -> String {
    format!(
        "{}|{}|{}|{}|{}|{:.6}|{:.6}|{:.6}|{:?}|{:?}|{:?}|{:?}|{}|{}|{}|{}|{}|{}|{}|{}",
        candidate.indicator.as_str(),
        candidate.timeframe.as_str(),
        candidate.signal_polarity,
        match candidate.entry_mode {
            EntryMode::Pullback => "pullback",
            EntryMode::Breakout => "breakout",
        },
        candidate.lookback,
        candidate.entry_atr_multiple,
        candidate.stop_atr_multiple,
        candidate.target_atr_multiple,
        candidate.time_stop_bars,
        candidate.hurst_min,
        candidate.hurst_max,
        candidate.shannon_max,
        candidate.atr_period,
        candidate.strategy_4448_kama1_er,
        candidate.strategy_4448_kama1_short,
        candidate.strategy_4448_kama1_long,
        candidate.strategy_4448_kama2_er,
        candidate.strategy_4448_kama2_short,
        candidate.strategy_4448_kama2_long,
        candidate.strategy_4448_count_bars,
    )
}

fn fold_local_candidate_id(template_id: usize, fold_index: usize) -> usize {
    (fold_index + 1)
        .saturating_mul(FOLD_LOCAL_CANDIDATE_ID_STRIDE)
        .saturating_add(template_id)
}

fn upsert_candidate(candidates: &mut Vec<Candidate>, candidate: Candidate) {
    if let Some(slot) = candidates.iter_mut().find(|slot| slot.id == candidate.id) {
        *slot = candidate;
    } else {
        candidates.push(candidate);
    }
}

#[cfg(test)]
fn bars_before_timestamp(bars: &[OhlcvBar], end_ms: i64) -> &[OhlcvBar] {
    let end = bars.partition_point(|bar| bar.open_time_ms < end_ms);
    &bars[..end]
}

fn bars_between_timestamps(bars: &[OhlcvBar], start_ms: i64, end_ms: i64) -> &[OhlcvBar] {
    let start = bars.partition_point(|bar| bar.open_time_ms < start_ms);
    let end = bars.partition_point(|bar| bar.open_time_ms < end_ms);
    &bars[start..end.max(start)]
}

fn max_bar_timestamp_seen(bars: &[OhlcvBar]) -> i64 {
    bars.last().map(|bar| bar.open_time_ms).unwrap_or(0)
}

fn fold_optimizer_scored_start_ms(config: &WfoConfig, fold: &Fold) -> i64 {
    if config.grid != GridSize::Tpe {
        return fold.is_start_ms;
    }
    let is_duration_ms = fold.is_end_ms - fold.is_start_ms;
    let consensus_offset_ms =
        Duration::days((TPE_IS_CONSENSUS_OFFSET_DAYS.saturating_sub(1)) as i64)
            .num_milliseconds();
    fold.is_end_ms - is_duration_ms - consensus_offset_ms
}

fn fold_local_objective_start_ms(
    config: &WfoConfig,
    fold: &Fold,
    candidate: &Candidate,
) -> Result<i64> {
    let scored_start_ms = fold_optimizer_scored_start_ms(config, fold);
    let timeframe_minutes = candidate.timeframe.minutes().max(1) as usize;
    let indicator_bars = candidate
        .lookback
        .max(candidate.atr_period)
        .max(candidate.strategy_4448_kama1_er)
        .max(candidate.strategy_4448_kama1_short)
        .max(candidate.strategy_4448_kama1_long)
        .max(candidate.strategy_4448_kama2_er)
        .max(candidate.strategy_4448_kama2_short)
        .max(candidate.strategy_4448_kama2_long)
        .max(candidate.strategy_4448_count_bars)
        .max(8);
    let indicator_warmup_minutes = indicator_bars.saturating_mul(timeframe_minutes);
    let order_state_warmup_minutes = entry_order_valid_bars(candidate)
        .saturating_add(execution_time_stop_bars(candidate).unwrap_or(0))
        .saturating_add(timeframe_minutes);
    let warmup_minutes = (FOLD_LOCAL_OBJECTIVE_WARMUP_DAYS * MINUTES_PER_DAY)
        .max(indicator_warmup_minutes.saturating_add(order_state_warmup_minutes) as i64);
    let config_start_ms = date_ms(config.start)?;
    Ok((scored_start_ms - warmup_minutes * MS_PER_MINUTE).max(config_start_ms))
}

fn ensure_optimizer_boundary(max_timestamp_seen: i64, fold: &Fold) -> Result<()> {
    if max_timestamp_seen > fold.is_end_ms {
        anyhow::bail!(
            "point-in-time optimizer boundary violation: max_timestamp_seen {} exceeds fold {} is_end_ms {}",
            max_timestamp_seen,
            fold.index,
            fold.is_end_ms
        );
    }
    Ok(())
}

fn write_optimizer_provenance_jsonl(run_dir: &Path, rows: &[OptimizerProvenanceRow]) -> Result<()> {
    let path = run_dir.join(OPTIMIZER_PROVENANCE_JSONL_FILE);
    let tmp = path.with_extension(format!("tmp.{}", std::process::id()));
    let mut file = File::create(&tmp).with_context(|| format!("create {}", tmp.display()))?;
    for row in rows {
        serde_json::to_writer(&mut file, row)?;
        writeln!(file)?;
    }
    file.sync_all()?;
    fs::rename(tmp, path)?;
    Ok(())
}

fn optimizer_provenance_boundary_passes(run_dir: &Path) -> Result<bool> {
    let path = run_dir.join(OPTIMIZER_PROVENANCE_CSV_FILE);
    if !path.exists() {
        return Ok(false);
    }
    let rows = read_csv::<OptimizerProvenanceRow>(path)?;
    Ok(rows
        .iter()
        .all(|row| row.max_timestamp_seen <= row.optimizer_scope_end))
}

pub fn verify_wfo() -> Result<PathBuf> {
    run_wfo(GridSize::Smoke)
}

pub fn current_status() -> Result<Option<RunStatus>> {
    let Some(run) = latest_run_dir()? else {
        return Ok(None);
    };
    read_json(run.join("status.json")).map(Some)
}

pub fn list_runs() -> Result<Vec<RunListItem>> {
    let root = PathBuf::from(RUNS_ROOT);
    if !root.exists() {
        return Ok(Vec::new());
    }
    let mut runs = Vec::new();
    for entry in fs::read_dir(root)? {
        let entry = entry?;
        if !entry.file_type()?.is_dir() {
            continue;
        }
        let path = entry.path();
        let status = read_json(path.join("status.json")).ok();
        runs.push(RunListItem {
            run_id: entry.file_name().to_string_lossy().to_string(),
            path: path.display().to_string(),
            status,
        });
    }
    runs.sort_by(|a, b| b.run_id.cmp(&a.run_id));
    Ok(runs)
}

pub fn run_history() -> Result<Vec<RunHistoryRow>> {
    let runs = list_runs()?;
    let mut rows = Vec::with_capacity(runs.len());
    for run in runs {
        let summary = read_summary(&run.run_id).ok();
        let run_path = PathBuf::from(&run.path);
        let config = read_json::<WfoConfig>(run_path.join("config.json")).ok();
        let candidate_count = read_csv::<Candidate>(run_path.join("candidates.csv"))
            .ok()
            .map(|rows| rows.len());
        rows.push(RunHistoryRow {
            run_id: run.run_id,
            phase: run
                .status
                .as_ref()
                .map(|status| format!("{:?}", status.phase))
                .unwrap_or_else(|| "unknown".to_string()),
            progress_pct: run
                .status
                .as_ref()
                .map(|status| status.progress_pct)
                .unwrap_or(0.0),
            grid: summary
                .as_ref()
                .map(|summary| format!("{:?}", summary.grid))
                .or_else(|| config.as_ref().map(|config| format!("{:?}", config.grid))),
            optimizer_mode: config
                .as_ref()
                .map(|config| config.optimizer_mode.as_str().to_string()),
            folds: summary.as_ref().map(|summary| summary.folds),
            candidates: summary
                .as_ref()
                .map(|summary| summary.candidates)
                .or(candidate_count),
            trades: summary.as_ref().map(|summary| summary.trades),
            net_return_pct: summary.as_ref().map(|summary| summary.net_return_pct),
            max_drawdown_pct: summary.as_ref().map(|summary| summary.max_drawdown_pct),
            sharpe: summary.as_ref().map(|summary| summary.sharpe),
            updated_at: run.status.map(|status| status.updated_at),
        });
    }
    Ok(rows)
}

pub fn read_summary(run_id: &str) -> Result<RunSummary> {
    read_json(PathBuf::from(RUNS_ROOT).join(run_id).join("summary.json"))
}

pub fn write_run_summary_page(run_id: &str) -> Result<PathBuf> {
    let run_dir = PathBuf::from(RUNS_ROOT).join(run_id);
    let summary = read_summary(run_id)?;
    let artifacts = read_artifacts(run_id).unwrap_or_default();
    write_run_summary_page_at(&run_dir, &summary, &artifacts)
}

pub fn read_artifacts(run_id: &str) -> Result<Vec<ArtifactRow>> {
    let run_dir = PathBuf::from(RUNS_ROOT).join(run_id);
    let mut rows = Vec::new();
    if !run_dir.exists() {
        return Ok(rows);
    }
    for entry in fs::read_dir(&run_dir)? {
        let entry = entry?;
        let metadata = entry.metadata()?;
        if !metadata.is_file() {
            continue;
        }
        let path = entry.path();
        let name = entry.file_name().to_string_lossy().to_string();
        rows.push(ArtifactRow {
            rows: artifact_row_count(&path),
            name,
            path: path.display().to_string(),
            bytes: metadata.len(),
            modified_at: metadata.modified().ok().map(DateTime::<Utc>::from),
        });
    }
    rows.sort_by(|a, b| a.name.cmp(&b.name));
    Ok(rows)
}

pub fn read_fold_results(run_id: &str) -> Result<Vec<FoldResultRow>> {
    let run_dir = PathBuf::from(RUNS_ROOT).join(run_id);
    let scores =
        read_csv::<CandidateScore>(run_dir.join("best_by_indicator.csv")).unwrap_or_default();
    let mut best_by_fold: BTreeMap<usize, FoldResultRow> = BTreeMap::new();
    for score in scores {
        let row = FoldResultRow {
            fold_index: score.fold_index,
            symbol: score.symbol,
            candidate_id: score.candidate_id,
            score: score.score,
            net_return_pct: score.net_return_pct,
            max_drawdown_pct: score.max_drawdown_pct,
            trades: score.trades,
            min_trades: score.min_trades,
            max_trades: score.max_trades,
            trade_fit: score.trade_fit,
            profit_factor: score.profit_factor,
            min_profit_factor: score.min_profit_factor,
            average_trade_return_pct: score.average_trade_return_pct,
            min_average_trade_return_pct: score.min_average_trade_return_pct,
            quality_fit: score.quality_fit,
        };
        let replace = best_by_fold
            .get(&row.fold_index)
            .map(|current| row.score > current.score)
            .unwrap_or(true);
        if replace {
            best_by_fold.insert(row.fold_index, row);
        }
    }
    Ok(best_by_fold.into_values().collect())
}

pub fn read_recent_trades(run_id: &str, limit: usize) -> Result<Vec<Trade>> {
    let mut trades =
        read_csv::<Trade>(PathBuf::from(RUNS_ROOT).join(run_id).join("oos_trades.csv"))
            .unwrap_or_default();
    trades.sort_by_key(|trade| trade.exit_time_ms);
    if trades.len() > limit {
        trades = trades.split_off(trades.len() - limit);
    }
    Ok(trades)
}

pub fn read_equity_tail(run_id: &str, limit: usize) -> Result<Vec<AccountEquitySample>> {
    let mut equity = read_csv::<AccountEquitySample>(
        PathBuf::from(RUNS_ROOT).join(run_id).join("oos_equity.csv"),
    )
    .unwrap_or_default();
    equity.sort_by_key(|sample| sample.timestamp_ms);
    if equity.len() > limit {
        equity = equity.split_off(equity.len() - limit);
    }
    Ok(equity)
}

pub fn read_events(run_id: &str, tail: usize) -> Result<Vec<serde_json::Value>> {
    let path = PathBuf::from(RUNS_ROOT).join(run_id).join("events.jsonl");
    let text = fs::read_to_string(path).unwrap_or_default();
    let mut values: Vec<_> = text
        .lines()
        .filter_map(|line| serde_json::from_str::<serde_json::Value>(line).ok())
        .collect();
    if values.len() > tail {
        values = values.split_off(values.len() - tail);
    }
    Ok(values)
}

pub fn read_checks() -> Result<Vec<CheckRow>> {
    let path = PathBuf::from(RUNS_ROOT).join(CHECKS_FILE);
    if !path.exists() {
        return Ok(default_checks());
    }
    let mut checks = read_json::<Vec<CheckRow>>(path)?;
    checks.sort_by(|a, b| a.name.cmp(&b.name));
    Ok(checks)
}

pub fn record_check(name: &str, status: &str, command: &str, details: &str) -> Result<()> {
    fs::create_dir_all(RUNS_ROOT)?;
    let path = PathBuf::from(RUNS_ROOT).join(CHECKS_FILE);
    let mut checks = read_checks().unwrap_or_else(|_| default_checks());
    checks.retain(|check| check.name != name);
    checks.push(CheckRow {
        name: name.to_string(),
        status: status.to_string(),
        command: command.to_string(),
        details: details.to_string(),
        finished_at: Utc::now(),
    });
    checks.sort_by(|a, b| a.name.cmp(&b.name));
    write_json(path, &checks)
}

pub fn strategy_rows(run_id: Option<&str>) -> Result<Vec<StrategyRow>> {
    let run_id = match run_id {
        Some(run_id) => Some(run_id.to_string()),
        None => current_status()?.map(|status| status.run_id),
    };
    if let Some(run_id) = &run_id {
        let progress_path = PathBuf::from(RUNS_ROOT)
            .join(run_id)
            .join("strategy_progress.json");
        if progress_path.exists() {
            let mut rows = read_json::<Vec<StrategyRow>>(progress_path)?;
            rows.sort_by_key(|row| {
                (
                    indicator_rank(&row.indicator),
                    timeframe_rank(&row.timeframe),
                )
            });
            return Ok(rows);
        }
    }
    let candidates = candidate_grid(GridSize::Wide);
    let mut rows = BTreeMap::new();
    for indicator in IndicatorKind::CATALOG {
        let timeframes: &[Timeframe] = if indicator.is_runnable_strategy() {
            &Timeframe::ALL
        } else {
            &[]
        };
        if timeframes.is_empty() {
            rows.insert(
                (indicator.as_str().to_string(), "n/a".to_string()),
                StrategyRow {
                    indicator: indicator.as_str().to_string(),
                    timeframe: "n/a".to_string(),
                    implementation_status: indicator.implementation_status().to_string(),
                    implementation_note: indicator.implementation_note().to_string(),
                    runnable: false,
                    parameter_candidates: 0,
                    status: indicator.implementation_status().to_string(),
                    progress_pct: 0.0,
                    progress_label: "not runnable".to_string(),
                    folds_scored: 0,
                    best_score: 0.0,
                    net_return_pct: 0.0,
                    max_drawdown_pct: 0.0,
                    trades: 0,
                },
            );
            continue;
        }
        for timeframe in Timeframe::ALL {
            rows.insert(
                (
                    indicator.as_str().to_string(),
                    timeframe.as_str().to_string(),
                ),
                StrategyRow {
                    indicator: indicator.as_str().to_string(),
                    timeframe: timeframe.as_str().to_string(),
                    implementation_status: indicator.implementation_status().to_string(),
                    implementation_note: indicator.implementation_note().to_string(),
                    runnable: true,
                    parameter_candidates: candidates
                        .iter()
                        .filter(|candidate| {
                            candidate.indicator == indicator && candidate.timeframe == timeframe
                        })
                        .count(),
                    status: "pending".to_string(),
                    progress_pct: 0.0,
                    progress_label: String::new(),
                    folds_scored: 0,
                    best_score: 0.0,
                    net_return_pct: 0.0,
                    max_drawdown_pct: 0.0,
                    trades: 0,
                },
            );
        }
    }

    if let Some(run_id) = run_id {
        let run_dir = PathBuf::from(RUNS_ROOT).join(run_id);
        let run_candidates =
            read_csv::<Candidate>(run_dir.join("candidates.csv")).unwrap_or_default();
        let scores =
            read_csv::<CandidateScore>(run_dir.join("best_by_indicator.csv")).unwrap_or_default();
        let mut candidate_lookup = BTreeMap::new();
        for candidate in run_candidates {
            candidate_lookup.insert(candidate.id, candidate);
        }
        let total_folds = scores
            .iter()
            .map(|score| score.fold_index)
            .max()
            .map(|idx| idx + 1)
            .unwrap_or(0)
            .max(1);
        for score in scores {
            let Some(candidate) = candidate_lookup.get(&score.candidate_id) else {
                continue;
            };
            let key = (
                candidate.indicator.as_str().to_string(),
                candidate.timeframe.as_str().to_string(),
            );
            let row = rows.entry(key).or_insert_with(|| StrategyRow {
                indicator: candidate.indicator.as_str().to_string(),
                timeframe: candidate.timeframe.as_str().to_string(),
                implementation_status: candidate.indicator.implementation_status().to_string(),
                implementation_note: candidate.indicator.implementation_note().to_string(),
                runnable: candidate.indicator.is_runnable_strategy(),
                parameter_candidates: 0,
                status: "pending".to_string(),
                progress_pct: 0.0,
                progress_label: String::new(),
                folds_scored: 0,
                best_score: 0.0,
                net_return_pct: 0.0,
                max_drawdown_pct: 0.0,
                trades: 0,
            });
            row.status = "complete".to_string();
            row.folds_scored += 1;
            row.progress_pct = (row.folds_scored as f64 / total_folds as f64 * 100.0).min(100.0);
            if score.score >= row.best_score || row.trades == 0 {
                row.best_score = score.score;
                row.net_return_pct = score.net_return_pct;
                row.max_drawdown_pct = score.max_drawdown_pct;
            }
            row.trades += score.trades;
        }
    }

    let mut rows: Vec<_> = rows.into_values().collect();
    rows.sort_by_key(|row| {
        (
            indicator_rank(&row.indicator),
            timeframe_rank(&row.timeframe),
        )
    });
    Ok(rows)
}

pub fn read_strategy_oos_results(run_id: Option<&str>) -> Result<Vec<StrategyOosBlock>> {
    let resolved_run_id = match run_id {
        Some(run_id) => Some(run_id.to_string()),
        None => current_status()?.map(|status| status.run_id),
    };
    if let Some(run_id) = &resolved_run_id {
        let run_dir = PathBuf::from(RUNS_ROOT).join(run_id);
        let block_map = read_strategy_oos_block_map(&run_dir)?;
        if !block_map.is_empty() {
            let rows = strategy_rows(Some(run_id))?;
            let min_profit_factor =
                run_candidate_min_profit_factor(&PathBuf::from(RUNS_ROOT).join(run_id));
            return Ok(merge_strategy_oos_blocks_with_progress(
                rows,
                block_map,
                min_profit_factor,
            ));
        }

        let path = run_dir.join(STRATEGY_OOS_RESULTS_FILE);
        if path.exists() {
            let mut blocks = read_json::<Vec<StrategyOosBlock>>(path)?;
            let progress_path = run_dir.join("strategy_progress.json");
            if progress_path.exists() {
                let rows = read_json::<Vec<StrategyRow>>(progress_path)?;
                let block_map = blocks
                    .drain(..)
                    .map(|block| ((block.indicator.clone(), block.timeframe.clone()), block))
                    .collect::<BTreeMap<_, _>>();
                let min_profit_factor = run_candidate_min_profit_factor(&run_dir);
                return Ok(merge_strategy_oos_blocks_with_progress(
                    rows,
                    block_map,
                    min_profit_factor,
                ));
            }
            let min_profit_factor = run_candidate_min_profit_factor(&run_dir);
            for block in &mut blocks {
                refresh_strategy_candidate_gate(block, min_profit_factor);
            }
            blocks.sort_by_key(|row| {
                (
                    indicator_rank(&row.indicator),
                    timeframe_rank(&row.timeframe),
                )
            });
            return Ok(blocks);
        }
    }
    let rows = strategy_rows(resolved_run_id.as_deref())?;
    Ok(strategy_oos_placeholders(&rows))
}

#[derive(Debug, Clone, Serialize)]
pub struct StrategyDiagnosticsReport {
    pub run_id: String,
    pub indicator: String,
    pub timeframe: String,
    pub candidates: usize,
    pub symbols: usize,
    pub folds: usize,
    pub fold_evaluations: usize,
    pub selected_symbol_folds: usize,
    pub selected_coverage_pct: f64,
    pub trade_band_min: usize,
    pub trade_band_max: usize,
    pub counts: DiagnosticCounts,
    pub trades_per_fold: DiagnosticDistribution,
    pub profit_factor_when_trade_count_ok: DiagnosticDistribution,
    pub portfolio: Option<DiagnosticOosMetrics>,
    pub by_symbol: Vec<SymbolDiagnosticsReport>,
    pub top_selected_candidates: Vec<SelectedCandidateDiagnostics>,
}

#[derive(Debug, Clone, Default, Serialize)]
pub struct DiagnosticCounts {
    pub zero_trades: usize,
    pub too_sparse: usize,
    pub too_active: usize,
    pub bad_exit_geometry: usize,
    pub low_profit_factor: usize,
    pub low_average_trade_edge: usize,
    pub low_edge_confidence: usize,
    pub low_fill_rate: usize,
    pub low_participation: usize,
    pub eligible_nonpositive_net: usize,
    pub eligible_positive_net: usize,
    pub eligible_total: usize,
}

#[derive(Debug, Clone, Default, Serialize)]
pub struct DiagnosticDistribution {
    pub mean: f64,
    pub p50: f64,
    pub p90: f64,
    pub max: f64,
}

#[derive(Debug, Clone, Serialize)]
pub struct SymbolDiagnosticsReport {
    pub symbol: String,
    pub fold_evaluations: usize,
    pub selected_symbol_folds: usize,
    pub selected_coverage_pct: f64,
    pub counts: DiagnosticCounts,
    pub trades_per_fold: DiagnosticDistribution,
    pub profit_factor_when_trade_count_ok: DiagnosticDistribution,
    pub oos: Option<DiagnosticOosMetrics>,
}

#[derive(Debug, Clone, Serialize)]
pub struct SelectedCandidateDiagnostics {
    pub candidate_id: usize,
    pub selections: usize,
    pub candidate: Option<Candidate>,
}

#[derive(Debug, Clone, Serialize)]
pub struct DiagnosticOosMetrics {
    pub net_return_pct: f64,
    pub max_drawdown_pct: f64,
    pub trades: usize,
    pub win_rate: f64,
    pub profit_factor: f64,
    pub sharpe: f64,
}

#[derive(Debug, Clone, Serialize)]
pub struct StressValidationReport {
    pub run_id: String,
    pub generated_at: DateTime<Utc>,
    pub min_profit_factor: f64,
    pub min_candidate_oos_trades: usize,
    pub targets: usize,
    pub scenarios: Vec<StressScenarioReport>,
    pub circuit_breakers: Vec<CircuitBreakerScenarioReport>,
    pub blocks: Vec<StressValidationBlock>,
    pub circuit_blocks: Vec<StressCircuitValidationBlock>,
}

#[derive(Debug, Clone, Serialize)]
pub struct StressScenarioReport {
    pub name: String,
    pub fees_bps: f64,
    pub breach_ticks: u32,
}

#[derive(Debug, Clone, Serialize)]
pub struct StressValidationBlock {
    pub indicator: String,
    pub timeframe: String,
    pub scenario: String,
    pub fees_bps: f64,
    pub breach_ticks: u32,
    pub original: Option<DiagnosticOosMetrics>,
    pub metrics: StrategyOosMetrics,
    pub symbols: Vec<StrategyOosSymbolResult>,
}

#[derive(Debug, Clone, Serialize)]
pub struct CircuitBreakerScenarioReport {
    pub name: String,
    pub loss_trigger_pct: f64,
    pub pause_folds: usize,
}

#[derive(Debug, Clone, Serialize)]
pub struct StressCircuitValidationBlock {
    pub indicator: String,
    pub timeframe: String,
    pub stress_scenario: String,
    pub circuit_scenario: String,
    pub fees_bps: f64,
    pub breach_ticks: u32,
    pub loss_trigger_pct: f64,
    pub pause_folds: usize,
    pub metrics: StrategyOosMetrics,
    pub symbols: Vec<StrategyOosSymbolResult>,
}

#[derive(Debug, Clone, Serialize)]
struct StressValidationCsvRow {
    indicator: String,
    timeframe: String,
    scenario: String,
    fees_bps: f64,
    breach_ticks: u32,
    original_net_return_pct: f64,
    original_max_drawdown_pct: f64,
    original_profit_factor: f64,
    original_trades: usize,
    net_return_pct: f64,
    max_drawdown_pct: f64,
    profit_factor: f64,
    trades: usize,
    win_rate: f64,
    sharpe: f64,
    net_retention_pct: f64,
    pass_net_positive: bool,
    pass_profit_factor: bool,
    min_candidate_oos_trades: usize,
    pass_min_trades: bool,
    pass_candidate: bool,
}

#[derive(Debug, Clone, Serialize)]
struct StressValidationSymbolCsvRow {
    indicator: String,
    timeframe: String,
    scenario: String,
    symbol: String,
    net_return_pct: f64,
    max_drawdown_pct: f64,
    profit_factor: f64,
    trades: usize,
    win_rate: f64,
    sharpe: f64,
}

#[derive(Debug, Clone, Serialize)]
struct StressCircuitValidationCsvRow {
    indicator: String,
    timeframe: String,
    stress_scenario: String,
    circuit_scenario: String,
    fees_bps: f64,
    breach_ticks: u32,
    loss_trigger_pct: f64,
    pause_folds: usize,
    net_return_pct: f64,
    max_drawdown_pct: f64,
    profit_factor: f64,
    trades: usize,
    win_rate: f64,
    sharpe: f64,
}

#[derive(Debug, Clone, Serialize)]
struct StressCircuitValidationSymbolCsvRow {
    indicator: String,
    timeframe: String,
    stress_scenario: String,
    circuit_scenario: String,
    symbol: String,
    net_return_pct: f64,
    max_drawdown_pct: f64,
    profit_factor: f64,
    trades: usize,
    win_rate: f64,
    sharpe: f64,
}

#[derive(Debug, Clone, Serialize)]
pub struct EquityControlValidationReport {
    pub run_id: String,
    pub generated_at: DateTime<Utc>,
    pub selector_symbols: Vec<String>,
    pub report_symbols: Vec<String>,
    pub blocks: Vec<EquityControlValidationBlock>,
}

#[derive(Debug, Clone, Serialize)]
pub struct EquityControlValidationBlock {
    pub indicator: String,
    pub timeframe: String,
    pub selector_base: StrategyOosMetrics,
    pub selector_controlled: StrategyOosMetrics,
    pub symbols: Vec<EquityControlSymbolResult>,
}

#[derive(Debug, Clone, Serialize)]
pub struct EquityControlSymbolResult {
    pub symbol: String,
    pub base: StrategyOosMetrics,
    pub controlled: StrategyOosMetrics,
    pub trades_retention_pct: f64,
}

#[derive(Debug, Clone, Serialize)]
struct EquityControlSymbolCsvRow {
    indicator: String,
    timeframe: String,
    selector_symbols: String,
    symbol: String,
    base_net_return_pct: f64,
    base_max_drawdown_pct: f64,
    base_profit_factor: f64,
    base_trades: usize,
    controlled_net_return_pct: f64,
    controlled_max_drawdown_pct: f64,
    controlled_profit_factor: f64,
    controlled_trades: usize,
    net_delta_pct: f64,
    drawdown_delta_pct: f64,
    profit_factor_delta: f64,
    trades_retention_pct: f64,
}

#[derive(Debug, Clone, Serialize)]
struct EquityControlFoldCsvRow {
    indicator: String,
    timeframe: String,
    fold_index: usize,
    oos_start_ms: i64,
    oos_end_ms: i64,
    ma_period: usize,
    buffer_pct: f64,
    below_ma_multiplier: f64,
    trade_during_warmup: bool,
    selector_is_base_net_return_pct: f64,
    selector_is_base_max_drawdown_pct: f64,
    selector_is_base_profit_factor: f64,
    selector_is_base_trades: usize,
    selector_is_controlled_net_return_pct: f64,
    selector_is_controlled_max_drawdown_pct: f64,
    selector_is_controlled_profit_factor: f64,
    selector_is_controlled_trades: usize,
    selector_oos_base_net_return_pct: f64,
    selector_oos_base_max_drawdown_pct: f64,
    selector_oos_base_profit_factor: f64,
    selector_oos_base_trades: usize,
    selector_oos_controlled_net_return_pct: f64,
    selector_oos_controlled_max_drawdown_pct: f64,
    selector_oos_controlled_profit_factor: f64,
    selector_oos_controlled_trades: usize,
}

#[derive(Debug, Clone, Copy)]
struct StressScenario {
    name: &'static str,
    fees_bps: f64,
    breach_ticks: u32,
}

#[derive(Debug, Clone, Copy)]
struct EquityControlParams {
    ma_period: usize,
    buffer_pct: f64,
    below_ma_multiplier: f64,
    trade_during_warmup: bool,
}

#[derive(Debug, Clone)]
struct EquityControlFoldReplay {
    is_base_trades: Vec<Trade>,
    is_controlled_trades: Vec<Trade>,
    oos_base_trades: Vec<Trade>,
    oos_controlled_trades: Vec<Trade>,
}

#[derive(Debug, Clone, Copy)]
struct ClosedTradeStats {
    net_return_pct: f64,
    max_drawdown_pct: f64,
    profit_factor: f64,
    trades: usize,
}

#[derive(Debug, Clone, Copy)]
struct CircuitBreakerScenario {
    name: &'static str,
    loss_trigger_pct: f64,
    pause_folds: usize,
}

struct SymbolDiagnosticsOutput {
    report: SymbolDiagnosticsReport,
    trades_per_fold: Vec<f64>,
    profit_factors_when_trade_count_ok: Vec<f64>,
}

#[derive(Debug, Clone, Serialize)]
pub struct PortfolioComboReport {
    pub generated_at: DateTime<Utc>,
    pub components: Vec<PortfolioComboComponentReport>,
    pub portfolio: StrategyOosMetrics,
    pub portfolio_per_allocated_notional: StrategyOosMetrics,
    pub risk_managed_portfolio: Option<StrategyOosMetrics>,
    pub risk_managed_portfolio_per_allocated_notional: Option<StrategyOosMetrics>,
    pub periods: Vec<PortfolioComboPeriodReport>,
    pub risk_managed_periods: Vec<PortfolioComboPeriodReport>,
    pub component_return_correlation: Option<f64>,
    pub fixed_notional: f64,
    pub allocated_notional: f64,
    pub start_ms: i64,
    pub end_ms: i64,
}

#[derive(Debug, Clone, Serialize)]
pub struct PortfolioComboComponentReport {
    pub run_id: String,
    pub indicator: String,
    pub timeframe: String,
    pub metrics: StrategyOosMetrics,
    pub original_metrics: Option<StrategyOosMetrics>,
    pub risk_managed_metrics: Option<StrategyOosMetrics>,
}

#[derive(Debug, Clone, Serialize)]
pub struct PortfolioComboPeriodReport {
    pub label: String,
    pub start_ms: i64,
    pub end_ms: i64,
    pub metrics: StrategyOosMetrics,
}

#[derive(Debug, Clone)]
struct PortfolioComboComponentSpec {
    run_id: String,
    indicator: IndicatorKind,
    timeframe: Timeframe,
}

#[derive(Debug, Clone, Serialize)]
struct DailyOffsetEnsembleSummary {
    name: String,
    generated_at: DateTime<Utc>,
    offset_count: usize,
    account_balance_per_offset: f64,
    pass_status: String,
    pass_reason: String,
    provenance_validation_status: String,
    starting_balance: f64,
    final_balance: f64,
    total_pnl: f64,
    net_return_pct: f64,
    max_drawdown: f64,
    max_drawdown_pct: f64,
    trades: usize,
    win_rate: f64,
    profit_factor: f64,
    average_trade: f64,
    exposure_pct: f64,
    long_exposure_pct: f64,
    short_exposure_pct: f64,
    average_exposure_notional: f64,
    average_long_exposure_notional: f64,
    average_short_exposure_notional: f64,
    average_net_exposure_notional: f64,
    max_exposure_notional: f64,
    max_long_exposure_notional: f64,
    max_short_exposure_notional: f64,
    max_abs_net_exposure_notional: f64,
    max_concurrent_positions: usize,
    max_concurrent_long_positions: usize,
    max_concurrent_short_positions: usize,
    no_entry_days: usize,
    longest_no_entry_gap_days: usize,
    longest_stagnation_minutes: i64,
    longest_stagnation_days: f64,
    stagnation_periods: usize,
    return_to_drawdown_ratio: f64,
    smoothness_score: f64,
    top_stagnation_periods: Vec<StagnationPeriod>,
    oct10_pnl: f64,
    oct10_trades: usize,
    runs: Vec<DailyOffsetEnsembleRunSummaryRow>,
}

#[derive(Debug, Clone, Serialize)]
struct DailyOffsetEnsembleRunSummaryRow {
    offset_days: i64,
    run_id: String,
    total_pnl: f64,
    net_return_pct: f64,
    max_drawdown_pct: f64,
    trades: usize,
    profit_factor: f64,
    ensemble_status: String,
    ensemble_reason: String,
    source_gate_status: String,
    source_gate_reason: String,
    optimizer_mode: String,
    provenance_validation_status: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
struct DailyOffsetEnsembleEquityRow {
    timestamp_ms: i64,
    balance: f64,
    pnl: f64,
    #[serde(default)]
    drawdown: f64,
    #[serde(default)]
    drawdown_pct: f64,
    #[serde(default)]
    open_positions: usize,
    #[serde(default)]
    long_positions: usize,
    #[serde(default)]
    short_positions: usize,
    #[serde(default)]
    exposure_notional: f64,
    #[serde(default)]
    long_exposure_notional: f64,
    #[serde(default)]
    short_exposure_notional: f64,
    #[serde(default)]
    net_exposure_notional: f64,
}

pub fn write_daily_offset_ensemble_rollup(options: DailyOffsetEnsembleOptions) -> Result<PathBuf> {
    if options.offset_runs.is_empty() {
        anyhow::bail!("daily offset ensemble requires at least one offset run");
    }
    validate_account_balance(options.account_balance)?;

    let mut runs = options.offset_runs.clone();
    runs.sort_by_key(|run| run.offset_days);
    let mut seen_offsets = BTreeSet::new();
    for run in &runs {
        if !seen_offsets.insert(run.offset_days) {
            anyhow::bail!("duplicate daily-offset run for offset {}", run.offset_days);
        }
    }

    let mut run_summaries = Vec::new();
    let mut equity_by_offset = BTreeMap::<i64, Vec<AccountEquitySample>>::new();
    let mut trades_by_offset = BTreeMap::<i64, Vec<Trade>>::new();
    let mut reference_config: Option<WfoConfig> = None;
    let mut all_sources_point_in_time = true;
    for run in &runs {
        let run_dir = PathBuf::from(RUNS_ROOT).join(&run.run_id);
        if !run_dir.exists() {
            anyhow::bail!("missing WFO run directory {}", run_dir.display());
        }
        let config = read_json::<WfoConfig>(run_dir.join("config.json"))?;
        if config.start_offset_days != run.offset_days {
            anyhow::bail!(
                "run {} has start_offset_days {}; expected {}",
                run.run_id,
                config.start_offset_days,
                run.offset_days
            );
        }
        if let Some(reference) = &reference_config {
            if config.preset != reference.preset
                || config.start != reference.start
                || config.end != reference.end
                || config.grid != reference.grid
                || config.strategy_set != reference.strategy_set
                || config.indicator_group != reference.indicator_group
                || config.symbols != reference.symbols
                || config.tpe_trials != reference.tpe_trials
                || config.is_weeks != reference.is_weeks
                || config.oos_weeks != reference.oos_weeks
                || config.step_weeks != reference.step_weeks
                || config.is_days != reference.is_days
                || config.oos_days != reference.oos_days
                || config.step_days != reference.step_days
                || config.gap_weeks != reference.gap_weeks
                || config.gap_days != reference.gap_days
                || (config.fixed_notional - reference.fixed_notional).abs() > f64::EPSILON
                || (config.account_balance - reference.account_balance).abs() > f64::EPSILON
                || (config.fees_bps - reference.fees_bps).abs() > f64::EPSILON
            {
                anyhow::bail!(
                    "run {} is not compatible with the first ensemble run",
                    run.run_id
                );
            }
        } else {
            reference_config = Some(config.clone());
        }
        all_sources_point_in_time &= config.optimizer_mode == OptimizerMode::PointInTimeFoldLocal
            && optimizer_provenance_boundary_passes(&run_dir).unwrap_or(false);

        let summary = read_json::<RunSummary>(run_dir.join("summary.json"))?;
        let blocks = read_strategy_oos_results(Some(&run.run_id))?;
        let best_block = blocks
            .iter()
            .filter_map(|block| block.portfolio.as_ref().map(|metrics| (block, metrics)))
            .max_by(|left, right| left.1.total_pnl.total_cmp(&right.1.total_pnl));
        let (profit_factor, source_gate_status, source_gate_reason) = best_block
            .map(|(block, metrics)| {
                (
                    metrics.profit_factor,
                    block.candidate_gate.status.clone(),
                    block.candidate_gate.reason.clone(),
                )
            })
            .unwrap_or_else(|| {
                (
                    0.0,
                    "rejected".to_string(),
                    "no strategy OOS block with portfolio metrics".to_string(),
                )
            });
        let (ensemble_status, ensemble_reason) = daily_offset_component_gate(
            summary.total_pnl,
            profit_factor,
            summary.trades,
            config.candidate_min_profit_factor,
        );

        run_summaries.push(DailyOffsetEnsembleRunSummaryRow {
            offset_days: run.offset_days,
            run_id: run.run_id.clone(),
            total_pnl: summary.total_pnl,
            net_return_pct: summary.net_return_pct,
            max_drawdown_pct: summary.max_drawdown_pct,
            trades: summary.trades,
            profit_factor,
            ensemble_status,
            ensemble_reason,
            source_gate_status,
            source_gate_reason,
            optimizer_mode: config.optimizer_mode.as_str().to_string(),
            provenance_validation_status: if config.optimizer_mode
                == OptimizerMode::PointInTimeFoldLocal
                && optimizer_provenance_boundary_passes(&run_dir).unwrap_or(false)
            {
                "PASS point-in-time optimizer boundary".to_string()
            } else {
                "RESEARCH ONLY".to_string()
            },
        });

        let equity =
            read_csv::<AccountEquitySample>(run_dir.join("oos_equity.csv")).unwrap_or_default();
        equity_by_offset.insert(run.offset_days, equity);
        let trades = read_csv::<Trade>(run_dir.join("oos_trades.csv")).unwrap_or_default();
        trades_by_offset.insert(run.offset_days, trades);
    }

    let all_timestamps = equity_by_offset
        .values()
        .flat_map(|points| points.iter().map(|sample| sample.timestamp_ms))
        .collect::<BTreeSet<_>>()
        .into_iter()
        .collect::<Vec<_>>();
    if all_timestamps.is_empty() {
        anyhow::bail!("daily offset ensemble has no equity samples");
    }

    let zero_sample = AccountEquitySample {
        timestamp_ms: 0,
        realized_pnl: 0.0,
        unrealized_pnl: 0.0,
        equity: 0.0,
        drawdown: 0.0,
        drawdown_pct: 0.0,
        open_positions: 0,
        long_positions: 0,
        short_positions: 0,
        exposure_notional: 0.0,
        long_exposure_notional: 0.0,
        short_exposure_notional: 0.0,
        net_exposure_notional: 0.0,
    };
    let starting_balance = options.account_balance * runs.len() as f64;
    let mut last_sample_by_offset = BTreeMap::<i64, AccountEquitySample>::new();
    let mut index_by_offset = BTreeMap::<i64, usize>::new();
    for run in &runs {
        last_sample_by_offset.insert(run.offset_days, zero_sample.clone());
        index_by_offset.insert(run.offset_days, 0);
    }

    let mut rollup_rows = Vec::with_capacity(all_timestamps.len());
    let mut component_rows = BTreeMap::<i64, Vec<DailyOffsetEnsembleEquityRow>>::new();
    let mut peak_balance = starting_balance;
    for timestamp_ms in all_timestamps {
        let mut total_balance = 0.0;
        let mut total_pnl = 0.0;
        let mut open_positions = 0usize;
        let mut long_positions = 0usize;
        let mut short_positions = 0usize;
        let mut exposure_notional = 0.0;
        let mut long_exposure_notional = 0.0;
        let mut short_exposure_notional = 0.0;
        let mut net_exposure_notional = 0.0;
        for run in &runs {
            let points = equity_by_offset
                .get(&run.offset_days)
                .expect("offset was initialized");
            let mut index = *index_by_offset
                .get(&run.offset_days)
                .expect("offset index was initialized");
            while index < points.len() && points[index].timestamp_ms <= timestamp_ms {
                last_sample_by_offset.insert(run.offset_days, points[index].clone());
                index += 1;
            }
            index_by_offset.insert(run.offset_days, index);
            let sample = last_sample_by_offset
                .get(&run.offset_days)
                .expect("offset sample was initialized");
            let pnl = sample.equity;
            let balance = options.account_balance + pnl;
            total_balance += balance;
            total_pnl += pnl;
            open_positions += sample.open_positions;
            long_positions += sample.long_positions;
            short_positions += sample.short_positions;
            exposure_notional += sample.exposure_notional;
            long_exposure_notional += sample.long_exposure_notional;
            short_exposure_notional += sample.short_exposure_notional;
            net_exposure_notional += sample.net_exposure_notional;
            component_rows
                .entry(run.offset_days)
                .or_default()
                .push(DailyOffsetEnsembleEquityRow {
                    timestamp_ms,
                    balance,
                    pnl,
                    drawdown: sample.drawdown,
                    drawdown_pct: sample.drawdown_pct,
                    open_positions: sample.open_positions,
                    long_positions: sample.long_positions,
                    short_positions: sample.short_positions,
                    exposure_notional: sample.exposure_notional,
                    long_exposure_notional: sample.long_exposure_notional,
                    short_exposure_notional: sample.short_exposure_notional,
                    net_exposure_notional: sample.net_exposure_notional,
                });
        }
        peak_balance = f64::max(peak_balance, total_balance);
        let drawdown = peak_balance - total_balance;
        rollup_rows.push(DailyOffsetEnsembleEquityRow {
            timestamp_ms,
            balance: total_balance,
            pnl: total_pnl,
            drawdown,
            drawdown_pct: drawdown / starting_balance.max(1.0) * 100.0,
            open_positions,
            long_positions,
            short_positions,
            exposure_notional,
            long_exposure_notional,
            short_exposure_notional,
            net_exposure_notional,
        });
    }

    let final_balance = rollup_rows
        .last()
        .map(|row| row.balance)
        .unwrap_or(starting_balance);
    let total_pnl = final_balance - starting_balance;
    let net_return_pct = total_pnl / starting_balance.max(1.0) * 100.0;
    let max_drawdown = balance_max_drawdown(rollup_rows.iter().map(|row| row.balance));
    let max_drawdown_pct = max_drawdown / starting_balance.max(1.0) * 100.0;
    let rollup_account_equity = rollup_rows
        .iter()
        .map(|row| AccountEquitySample {
            timestamp_ms: row.timestamp_ms,
            realized_pnl: row.pnl,
            unrealized_pnl: 0.0,
            equity: row.pnl,
            drawdown: row.drawdown,
            drawdown_pct: row.drawdown_pct,
            open_positions: row.open_positions,
            long_positions: row.long_positions,
            short_positions: row.short_positions,
            exposure_notional: row.exposure_notional,
            long_exposure_notional: row.long_exposure_notional,
            short_exposure_notional: row.short_exposure_notional,
            net_exposure_notional: row.net_exposure_notional,
        })
        .collect::<Vec<_>>();
    let stagnation = stagnation_periods(&rollup_account_equity, starting_balance);
    let longest_stagnation_minutes = stagnation
        .iter()
        .map(|period| period.duration_minutes)
        .max()
        .unwrap_or(0);
    let longest_stagnation_days = longest_stagnation_minutes as f64 / MINUTES_PER_DAY as f64;
    let return_to_drawdown_ratio =
        compute_return_to_drawdown_ratio(net_return_pct, max_drawdown_pct);
    let smoothness_score =
        equity_smoothness_score(return_to_drawdown_ratio, longest_stagnation_days);
    let top_stagnation_periods = top_stagnation_periods(&stagnation, 10);
    let all_trades = trades_by_offset
        .values()
        .flat_map(|trades| trades.iter())
        .collect::<Vec<_>>();
    let trades = all_trades.len();
    let gross_win = all_trades
        .iter()
        .filter(|trade| trade.pnl > 0.0)
        .map(|trade| trade.pnl)
        .sum::<f64>();
    let gross_loss = all_trades
        .iter()
        .filter(|trade| trade.pnl < 0.0)
        .map(|trade| trade.pnl.abs())
        .sum::<f64>();
    let profit_factor = if gross_loss > 0.0 {
        gross_win / gross_loss
    } else if gross_win > 0.0 {
        f64::INFINITY
    } else {
        0.0
    };
    let win_rate = if trades > 0 {
        all_trades.iter().filter(|trade| trade.pnl > 0.0).count() as f64 / trades as f64 * 100.0
    } else {
        0.0
    };
    let average_trade = if trades > 0 {
        all_trades.iter().map(|trade| trade.pnl).sum::<f64>() / trades as f64
    } else {
        0.0
    };
    let samples = rollup_rows.len().max(1) as f64;
    let exposed_samples = rollup_rows
        .iter()
        .filter(|row| row.exposure_notional > 0.0)
        .count();
    let long_exposed_samples = rollup_rows
        .iter()
        .filter(|row| row.long_exposure_notional > 0.0)
        .count();
    let short_exposed_samples = rollup_rows
        .iter()
        .filter(|row| row.short_exposure_notional > 0.0)
        .count();
    let average_exposure_notional = rollup_rows
        .iter()
        .map(|row| row.exposure_notional)
        .sum::<f64>()
        / samples;
    let average_long_exposure_notional = rollup_rows
        .iter()
        .map(|row| row.long_exposure_notional)
        .sum::<f64>()
        / samples;
    let average_short_exposure_notional = rollup_rows
        .iter()
        .map(|row| row.short_exposure_notional)
        .sum::<f64>()
        / samples;
    let average_net_exposure_notional = rollup_rows
        .iter()
        .map(|row| row.net_exposure_notional)
        .sum::<f64>()
        / samples;
    let max_exposure_notional = rollup_rows
        .iter()
        .map(|row| row.exposure_notional)
        .fold(0.0, f64::max);
    let max_long_exposure_notional = rollup_rows
        .iter()
        .map(|row| row.long_exposure_notional)
        .fold(0.0, f64::max);
    let max_short_exposure_notional = rollup_rows
        .iter()
        .map(|row| row.short_exposure_notional)
        .fold(0.0, f64::max);
    let max_abs_net_exposure_notional = rollup_rows
        .iter()
        .map(|row| row.net_exposure_notional.abs())
        .fold(0.0, f64::max);
    let max_concurrent_positions = rollup_rows
        .iter()
        .map(|row| row.open_positions)
        .max()
        .unwrap_or(0);
    let max_concurrent_long_positions = rollup_rows
        .iter()
        .map(|row| row.long_positions)
        .max()
        .unwrap_or(0);
    let max_concurrent_short_positions = rollup_rows
        .iter()
        .map(|row| row.short_positions)
        .max()
        .unwrap_or(0);
    let (no_entry_days, longest_no_entry_gap_days) =
        daily_offset_no_entry_stats(&rollup_rows, &all_trades);
    let ensemble_min_profit_factor = reference_config
        .as_ref()
        .map(|config| config.candidate_min_profit_factor)
        .unwrap_or(DEFAULT_CANDIDATE_MIN_PROFIT_FACTOR);
    let (pass_status, pass_reason) = daily_offset_ensemble_gate(
        runs.len(),
        total_pnl,
        profit_factor,
        trades,
        longest_no_entry_gap_days,
        ensemble_min_profit_factor,
    );
    let provenance_validation_status = if all_sources_point_in_time {
        "PASS point-in-time optimizer boundary".to_string()
    } else {
        "RESEARCH ONLY".to_string()
    };
    let oct10_start_ms = Utc
        .with_ymd_and_hms(2025, 10, 10, 0, 0, 0)
        .single()
        .expect("valid Oct 10 start")
        .timestamp_millis();
    let oct10_end_ms = Utc
        .with_ymd_and_hms(2025, 10, 11, 0, 0, 0)
        .single()
        .expect("valid Oct 10 end")
        .timestamp_millis();
    let oct10_trades = trades_by_offset
        .values()
        .flat_map(|trades| trades.iter())
        .filter(|trade| trade_fully_inside_window(trade, oct10_start_ms, oct10_end_ms))
        .collect::<Vec<_>>();
    let oct10_pnl = oct10_trades.iter().map(|trade| trade.pnl).sum::<f64>();

    let slug = sanitize_strategy_file_part(&options.name);
    let last_run_id = runs
        .last()
        .map(|run| run.run_id.as_str())
        .unwrap_or("unknown");
    let out_dir = PathBuf::from(RUNS_ROOT).join(format!("{slug}_{last_run_id}_daily_offset"));
    fs::create_dir_all(&out_dir)?;
    write_csv(out_dir.join("rollup_equity.csv"), &rollup_rows)?;
    for (offset_days, rows) in &component_rows {
        write_csv(
            out_dir.join(format!("offset_{offset_days}_equity.csv")),
            rows,
        )?;
    }
    write_csv(out_dir.join("rollup_summary.csv"), &run_summaries)?;

    let summary = DailyOffsetEnsembleSummary {
        name: options.name.clone(),
        generated_at: Utc::now(),
        offset_count: runs.len(),
        account_balance_per_offset: options.account_balance,
        pass_status,
        pass_reason,
        provenance_validation_status,
        starting_balance,
        final_balance,
        total_pnl,
        net_return_pct,
        max_drawdown,
        max_drawdown_pct,
        trades,
        win_rate,
        profit_factor,
        average_trade,
        exposure_pct: exposed_samples as f64 / samples * 100.0,
        long_exposure_pct: long_exposed_samples as f64 / samples * 100.0,
        short_exposure_pct: short_exposed_samples as f64 / samples * 100.0,
        average_exposure_notional,
        average_long_exposure_notional,
        average_short_exposure_notional,
        average_net_exposure_notional,
        max_exposure_notional,
        max_long_exposure_notional,
        max_short_exposure_notional,
        max_abs_net_exposure_notional,
        max_concurrent_positions,
        max_concurrent_long_positions,
        max_concurrent_short_positions,
        no_entry_days,
        longest_no_entry_gap_days,
        longest_stagnation_minutes,
        longest_stagnation_days,
        stagnation_periods: stagnation.len(),
        return_to_drawdown_ratio,
        smoothness_score,
        top_stagnation_periods,
        oct10_pnl,
        oct10_trades: oct10_trades.len(),
        runs: run_summaries,
    };
    write_json(out_dir.join("rollup_summary.json"), &summary)?;
    write_daily_offset_ensemble_html(
        out_dir.join("rollup_equity.html"),
        &summary,
        &rollup_rows,
        &component_rows,
        &runs,
    )?;
    write_daily_offset_ensemble_html(
        out_dir.join("quant_report.html"),
        &summary,
        &rollup_rows,
        &component_rows,
        &runs,
    )?;
    let _ = std::process::Command::new("python3")
        .arg("generate_institutional_quant_report.py")
        .arg(&out_dir)
        .status();
    Ok(out_dir.join("rollup_equity.html"))
}

fn balance_max_drawdown(balances: impl Iterator<Item = f64>) -> f64 {
    let mut peak = f64::NEG_INFINITY;
    let mut max_drawdown = 0.0;
    for balance in balances {
        if balance > peak {
            peak = balance;
        }
        max_drawdown = f64::max(max_drawdown, peak - balance);
    }
    max_drawdown
}

fn daily_offset_no_entry_stats(
    rows: &[DailyOffsetEnsembleEquityRow],
    trades: &[&Trade],
) -> (usize, usize) {
    let Some(first) = rows.first() else {
        return (0, 0);
    };
    let Some(last) = rows.last() else {
        return (0, 0);
    };
    let day_ms = MINUTES_PER_DAY * MS_PER_MINUTE;
    let start_day = first.timestamp_ms.div_euclid(day_ms);
    let end_day = last.timestamp_ms.div_euclid(day_ms);
    if end_day < start_day {
        return (0, 0);
    }
    let entry_days = trades
        .iter()
        .map(|trade| trade.entry_time_ms.div_euclid(day_ms))
        .collect::<BTreeSet<_>>();
    let mut no_entry_days = 0usize;
    let mut longest_gap = 0usize;
    let mut current_gap = 0usize;
    for day in start_day..=end_day {
        if entry_days.contains(&day) {
            current_gap = 0;
        } else {
            no_entry_days += 1;
            current_gap += 1;
            longest_gap = longest_gap.max(current_gap);
        }
    }
    (no_entry_days, longest_gap)
}

fn top_stagnation_periods(periods: &[StagnationPeriod], limit: usize) -> Vec<StagnationPeriod> {
    let mut out = periods.to_vec();
    out.sort_by(|left, right| {
        right
            .duration_minutes
            .cmp(&left.duration_minutes)
            .then_with(|| right.max_drawdown.total_cmp(&left.max_drawdown))
    });
    out.truncate(limit);
    out
}

fn daily_offset_component_gate(
    total_pnl: f64,
    profit_factor: f64,
    trades: usize,
    min_profit_factor: f64,
) -> (String, String) {
    let mut failures = Vec::new();
    if total_pnl <= 0.0 {
        failures.push("non-positive OOS PnL".to_string());
    }
    if profit_factor < min_profit_factor {
        failures.push(format!(
            "PF {:.3} < {:.3}",
            profit_factor, min_profit_factor
        ));
    }
    if trades < MIN_CANDIDATE_OOS_TRADES {
        failures.push(format!(
            "{trades} trades < {} minimum",
            MIN_CANDIDATE_OOS_TRADES
        ));
    }
    if failures.is_empty() {
        (
            "pass".to_string(),
            format!(
                "positive OOS PnL, PF {:.3} >= {:.3}, and {trades} trades >= {}",
                profit_factor, min_profit_factor, MIN_CANDIDATE_OOS_TRADES
            ),
        )
    } else {
        ("fail".to_string(), failures.join("; "))
    }
}

fn daily_offset_ensemble_gate(
    offset_count: usize,
    total_pnl: f64,
    profit_factor: f64,
    trades: usize,
    longest_no_entry_gap_days: usize,
    min_profit_factor: f64,
) -> (String, String) {
    let mut failures = Vec::new();
    if offset_count != TPE_IS_CONSENSUS_OFFSET_DAYS {
        failures.push(format!(
            "{offset_count} offsets != {} required stacked accounts",
            TPE_IS_CONSENSUS_OFFSET_DAYS
        ));
    }
    if total_pnl <= 0.0 {
        failures.push("non-positive stacked OOS PnL".to_string());
    }
    if profit_factor < min_profit_factor {
        failures.push(format!(
            "stacked PF {:.3} < {:.3}",
            profit_factor, min_profit_factor
        ));
    }
    if trades < MIN_CANDIDATE_OOS_TRADES {
        failures.push(format!(
            "stacked {trades} trades < {} minimum",
            MIN_CANDIDATE_OOS_TRADES
        ));
    }
    if longest_no_entry_gap_days > MAX_CANDIDATE_NO_ENTRY_GAP_DAYS {
        failures.push(format!(
            "stacked max no-entry gap {longest_no_entry_gap_days}d > {}d",
            MAX_CANDIDATE_NO_ENTRY_GAP_DAYS
        ));
    }
    if failures.is_empty() {
        (
            "pass".to_string(),
            format!(
                "{} offsets, positive stacked OOS PnL, PF {:.3} >= {:.3}, {trades} trades, and max no-entry gap {longest_no_entry_gap_days}d <= {}d",
                offset_count, profit_factor, min_profit_factor, MAX_CANDIDATE_NO_ENTRY_GAP_DAYS
            ),
        )
    } else {
        ("fail".to_string(), failures.join("; "))
    }
}

fn write_daily_offset_ensemble_html(
    path: PathBuf,
    summary: &DailyOffsetEnsembleSummary,
    rollup_rows: &[DailyOffsetEnsembleEquityRow],
    component_rows: &BTreeMap<i64, Vec<DailyOffsetEnsembleEquityRow>>,
    runs: &[DailyOffsetRunSpec],
) -> Result<()> {
    let rollup_points = rollup_rows
        .iter()
        .map(|row| (row.timestamp_ms, row.balance))
        .collect::<Vec<_>>();
    let drawdown_points = rollup_rows
        .iter()
        .map(|row| (row.timestamp_ms, -row.drawdown_pct))
        .collect::<Vec<_>>();
    let exposure_points = rollup_rows
        .iter()
        .map(|row| (row.timestamp_ms, row.exposure_notional))
        .collect::<Vec<_>>();
    let stagnation_rows = if summary.top_stagnation_periods.is_empty() {
        "<tr><td colspan=\"7\" class=\"note\">No stagnation periods detected.</td></tr>".to_string()
    } else {
        summary
            .top_stagnation_periods
            .iter()
            .enumerate()
            .map(|(index, period)| {
                let recovery = period
                    .recovery_time_ms
                    .map(format_ms_utc)
                    .unwrap_or_else(|| "unrecovered".to_string());
                format!(
                    "<tr><td class=\"num\">{}</td><td>{}</td><td>{}</td><td>{}</td><td class=\"num\">{:.2}</td><td class=\"num\">${:.2}</td><td class=\"num\">{:.2}%</td></tr>",
                    index + 1,
                    html_escape(&format_ms_utc(period.peak_time_ms)),
                    html_escape(&format_ms_utc(period.start_time_ms)),
                    html_escape(&recovery),
                    period.duration_minutes as f64 / MINUTES_PER_DAY as f64,
                    period.max_drawdown,
                    period.max_drawdown_pct
                )
            })
            .collect::<Vec<_>>()
            .join("")
    };
    let rollup_color = if summary.total_pnl >= 0.0 {
        "#4da3ff"
    } else {
        "#ef4444"
    };
    let run_rows = summary
        .runs
        .iter()
        .map(|run| {
            format!(
                "<tr><td>{:+}d</td><td><code>{}</code></td><td class=\"num {}\">${:.2}</td><td class=\"num {}\">{:+.2}%</td><td class=\"num\">{:.2}%</td><td class=\"num\">{}</td><td class=\"num\">{:.3}</td><td><span class=\"badge {}\" title=\"{}\">{}</span></td><td><span class=\"badge {}\" title=\"{}\">{}</span></td></tr>",
                run.offset_days,
                html_escape(&run.run_id),
                pct_class(run.total_pnl),
                run.total_pnl,
                pct_class(run.net_return_pct),
                run.net_return_pct,
                run.max_drawdown_pct,
                run.trades,
                run.profit_factor,
                if run.ensemble_status == "pass" {
                    "ok"
                } else {
                    "bad"
                },
                html_escape(&run.ensemble_reason),
                html_escape(&run.ensemble_status),
                if run.provenance_validation_status.starts_with("PASS") {
                    "ok"
                } else {
                    "bad"
                },
                html_escape(&run.optimizer_mode),
                html_escape(&run.provenance_validation_status)
            )
        })
        .collect::<Vec<_>>()
        .join("");
    let curve_cards = runs
        .iter()
        .filter_map(|run| {
            let rows = component_rows.get(&run.offset_days)?;
            let run_summary = summary
                .runs
                .iter()
                .find(|candidate| candidate.offset_days == run.offset_days)?;
            let points = rows
                .iter()
                .map(|row| (row.timestamp_ms, row.balance))
                .collect::<Vec<_>>();
            let color = if run_summary.total_pnl >= 0.0 {
                "#3fbf6f"
            } else {
                "#8b949e"
            };
            Some(format!(
                "<section class=\"offset-card\"><div class=\"offset-head\"><div><b>Offset {:+}d</b><span>{}</span></div><div class=\"num {}\">${:.2}</div></div>{}</section>",
                run.offset_days,
                html_escape(&run.run_id),
                pct_class(run_summary.total_pnl),
                run_summary.total_pnl,
                daily_offset_svg_curve(&points, color, 720, 150)
            ))
        })
        .collect::<Vec<_>>()
        .join("");
    let html = format!(
        r#"<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<style>
:root{{color-scheme:dark;--bg:#0b1012;--panel:#11181b;--line:#26343a;--text:#e5edf0;--muted:#95a3aa;--green:#4ade80;--red:#fb7185;--blue:#4da3ff}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--text);font:13px/1.35 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}}
main{{max-width:1180px;margin:0 auto;padding:18px}}h1{{margin:0 0 4px;font-size:20px;letter-spacing:0}}.sub{{color:var(--muted);margin-bottom:14px}}
.metrics{{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:8px;margin:12px 0}}.metric{{background:var(--panel);border:1px solid var(--line);border-radius:6px;padding:10px}}
.metric span{{display:block;color:var(--muted);font-size:11px;text-transform:uppercase;font-weight:700}}.metric b{{display:block;margin-top:4px;font-size:17px}}.pos{{color:var(--green)}}.neg{{color:var(--red)}}.num{{text-align:right;font-variant-numeric:tabular-nums}}
.panel{{background:var(--panel);border:1px solid var(--line);border-radius:6px;padding:12px;margin:12px 0}}.curve{{width:100%;height:220px;display:block}}.chart-grid{{display:grid;grid-template-columns:2fr 1fr 1fr;gap:10px}}.grid{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}}
.offset-card{{background:var(--panel);border:1px solid var(--line);border-radius:6px;padding:10px}}.offset-head{{display:flex;justify-content:space-between;gap:12px;align-items:baseline;margin-bottom:8px}}.offset-head span{{display:block;color:var(--muted);font-size:11px}}.offset-card .curve{{height:150px}}
table{{width:100%;border-collapse:collapse;margin-top:6px}}th,td{{padding:7px 8px;border-bottom:1px solid var(--line);white-space:nowrap}}th{{color:var(--muted);text-align:left;font-size:11px;text-transform:uppercase}}.badge{{display:inline-block;padding:2px 7px;border-radius:999px;font-size:11px;font-weight:700}}.badge.ok{{background:#12351f;color:#86efac}}.badge.bad{{background:#3a2026;color:#fda4af}}code{{color:#cbd5e1;font-size:11px}}.note{{color:var(--muted);font-size:12px;margin-top:8px}}
@media(max-width:900px){{.metrics{{grid-template-columns:repeat(2,minmax(0,1fr))}}.grid,.chart-grid{{grid-template-columns:1fr}}th,td{{white-space:normal}}}}
</style></head><body><main>
<h1>{title}</h1><div class="sub">Named WFO type: {offset_count} independent daily-offset accounts, each using internal IS consensus offsets, stitched only after each run completes. Generated {generated_at}.</div>
<section class="metrics">
<div class="metric"><span>Ensemble Gate</span><b class="{pass_class}" title="{pass_reason}">{pass_status}</b></div><div class="metric"><span>Start Balance</span><b>${starting:.2}</b></div><div class="metric"><span>Capital Model</span><b>{offset_count} x ${per_offset:.0}</b></div><div class="metric"><span>Final Balance</span><b>${final_balance:.2}</b></div><div class="metric"><span>Net PnL</span><b class="{pnl_class}">${pnl:.2}</b></div><div class="metric"><span>Net Return</span><b class="{return_class}">{net_return:+.2}%</b></div>
<div class="metric"><span>Max DD</span><b>${max_dd:.2} / {max_dd_pct:.2}%</b></div>
<div class="metric"><span>Trades</span><b>{trades}</b></div><div class="metric"><span>Win Rate</span><b>{win_rate:.2}%</b></div><div class="metric"><span>Profit Factor</span><b>{profit_factor:.3}</b></div><div class="metric"><span>Avg Trade</span><b>${average_trade:.2}</b></div><div class="metric"><span>Exposure</span><b>{exposure_pct:.2}%</b></div><div class="metric"><span>Long / Short</span><b>{long_exposure_pct:.2}% / {short_exposure_pct:.2}%</b></div>
<div class="metric"><span>Avg Gross Exposure</span><b>${average_exposure:.0}</b></div><div class="metric"><span>Max Gross Exposure</span><b>${max_exposure:.0}</b></div><div class="metric"><span>Max Net Exposure</span><b>${max_net_exposure:.0}</b></div><div class="metric"><span>Max Positions</span><b>{max_positions}</b></div><div class="metric"><span>No-Entry Days</span><b>{no_entry_days}</b></div><div class="metric"><span>Max No-Entry Gap</span><b>{max_no_entry_gap}d</b></div>
<div class="metric"><span>Return / DD</span><b>{return_to_drawdown:.2}</b></div><div class="metric"><span>Smoothness</span><b>{smoothness_score:.2}</b></div><div class="metric"><span>Longest Stagnation</span><b>{stagnation_days:.2}d</b></div><div class="metric"><span>Stagnation Periods</span><b>{stagnation_periods}</b></div><div class="metric"><span>Stagnation Minutes</span><b>{stagnation_minutes}</b></div><div class="metric"><span>Provenance</span><b class="{provenance_class}">{provenance_status}</b></div>
</section>
<section class="chart-grid"><div class="panel"><h2 style="margin:0 0 8px;font-size:15px">Combined Portfolio Equity</h2>{rollup_svg}<div class="note">Oct 10, 2025 crash-window check: {oct10_trades} trades, ${oct10_pnl:.2} PnL across all offsets.</div></div><div class="panel"><h2 style="margin:0 0 8px;font-size:15px">Drawdown</h2>{drawdown_svg}</div><div class="panel"><h2 style="margin:0 0 8px;font-size:15px">Gross Exposure</h2>{exposure_svg}</div></section>
<section class="panel"><h2 style="margin:0 0 8px;font-size:15px">Top Stagnation Periods</h2><table><thead><tr><th class="num">#</th><th>Peak</th><th>Started</th><th>Recovered</th><th class="num">Days</th><th class="num">Max DD</th><th class="num">Max DD %</th></tr></thead><tbody>{stagnation_rows}</tbody></table></section>
<section class="panel"><h2 style="margin:0 0 8px;font-size:15px">Offset Runs</h2><table><thead><tr><th>Offset</th><th>Run</th><th class="num">PnL</th><th class="num">Net</th><th class="num">DD</th><th class="num">Trades</th><th class="num">PF</th><th>Ensemble Gate</th><th>Provenance</th></tr></thead><tbody>{run_rows}</tbody></table></section>
<section class="grid">{curve_cards}</section>
</main></body></html>"#,
        title = html_escape(&summary.name),
        offset_count = summary.offset_count,
        generated_at = summary.generated_at.format("%Y-%m-%d %H:%M UTC"),
        pass_class = if summary.pass_status == "pass" {
            "pos"
        } else {
            "neg"
        },
        pass_status = html_escape(&summary.pass_status),
        pass_reason = html_escape(&summary.pass_reason),
        starting = summary.starting_balance,
        per_offset = summary.account_balance_per_offset,
        final_balance = summary.final_balance,
        pnl_class = pct_class(summary.total_pnl),
        pnl = summary.total_pnl,
        return_class = pct_class(summary.net_return_pct),
        net_return = summary.net_return_pct,
        max_dd = summary.max_drawdown,
        max_dd_pct = summary.max_drawdown_pct,
        trades = summary.trades,
        win_rate = summary.win_rate,
        profit_factor = summary.profit_factor,
        average_trade = summary.average_trade,
        exposure_pct = summary.exposure_pct,
        long_exposure_pct = summary.long_exposure_pct,
        short_exposure_pct = summary.short_exposure_pct,
        average_exposure = summary.average_exposure_notional,
        max_exposure = summary.max_exposure_notional,
        max_net_exposure = summary.max_abs_net_exposure_notional,
        max_positions = summary.max_concurrent_positions,
        no_entry_days = summary.no_entry_days,
        max_no_entry_gap = summary.longest_no_entry_gap_days,
        return_to_drawdown = summary.return_to_drawdown_ratio,
        smoothness_score = summary.smoothness_score,
        stagnation_days = summary.longest_stagnation_days,
        stagnation_periods = summary.stagnation_periods,
        stagnation_minutes = summary.longest_stagnation_minutes,
        provenance_class = if summary.provenance_validation_status.starts_with("PASS") {
            "pos"
        } else {
            "neg"
        },
        provenance_status = html_escape(&summary.provenance_validation_status),
        rollup_svg = daily_offset_svg_curve(&rollup_points, rollup_color, 760, 170),
        drawdown_svg = daily_offset_svg_curve(&drawdown_points, "#fb7185", 360, 170),
        exposure_svg = daily_offset_svg_curve(&exposure_points, "#a78bfa", 360, 170),
        stagnation_rows = stagnation_rows,
        oct10_trades = summary.oct10_trades,
        oct10_pnl = summary.oct10_pnl,
        run_rows = run_rows,
        curve_cards = curve_cards,
    );
    fs::write(path.clone(), html)?;
    Ok(())
}

fn daily_offset_svg_curve(
    points: &[(i64, f64)],
    color: &str,
    width: usize,
    height: usize,
) -> String {
    let path = daily_offset_svg_path(points, width as f64, height as f64);
    format!(
        "<svg viewBox=\"0 0 {width} {height}\" preserveAspectRatio=\"none\" class=\"curve\"><rect x=\"0\" y=\"0\" width=\"{width}\" height=\"{height}\" rx=\"6\" fill=\"#0f1518\"/><path d=\"{}\" fill=\"none\" stroke=\"{}\" stroke-width=\"2.2\" vector-effect=\"non-scaling-stroke\"/></svg>",
        html_escape(&path),
        color
    )
}

fn daily_offset_svg_path(points: &[(i64, f64)], width: f64, height: f64) -> String {
    if points.is_empty() {
        return String::new();
    }
    let min_x = points
        .iter()
        .map(|(timestamp_ms, _)| *timestamp_ms)
        .min()
        .unwrap_or(0);
    let max_x = points
        .iter()
        .map(|(timestamp_ms, _)| *timestamp_ms)
        .max()
        .unwrap_or(min_x);
    let min_y = points
        .iter()
        .map(|(_, value)| *value)
        .fold(f64::INFINITY, f64::min);
    let mut max_y = points
        .iter()
        .map(|(_, value)| *value)
        .fold(f64::NEG_INFINITY, f64::max);
    let min_y = if min_y.is_finite() { min_y } else { 0.0 };
    if !max_y.is_finite() || (max_y - min_y).abs() < f64::EPSILON {
        max_y = min_y + 1.0;
    }
    let pad = 10.0;
    let x_span = (max_x - min_x).max(1) as f64;
    let y_span = (max_y - min_y).max(1e-9);
    points
        .iter()
        .enumerate()
        .map(|(index, (timestamp_ms, value))| {
            let x = pad + (*timestamp_ms - min_x) as f64 / x_span * (width - pad * 2.0);
            let y = height - pad - (*value - min_y) / y_span * (height - pad * 2.0);
            let command = if index == 0 { "M" } else { "L" };
            format!("{command}{x:.2},{y:.2}")
        })
        .collect::<Vec<_>>()
        .join(" ")
}

pub fn combine_strategy_components(component_specs: &[String]) -> Result<PathBuf> {
    if component_specs.len() < 2 {
        anyhow::bail!("portfolio combo requires at least two components");
    }
    let specs = component_specs
        .iter()
        .map(|value| parse_combo_component_spec(value))
        .collect::<Result<Vec<_>>>()?;
    let first_run_dir = PathBuf::from(RUNS_ROOT).join(&specs[0].run_id);
    let first_config = read_json::<WfoConfig>(first_run_dir.join("config.json"))?;
    let first_folds = read_csv::<Fold>(first_run_dir.join("folds.csv"))?;
    let first_data = load_wfo_data(&first_config)?;
    let close_by_symbol = close_lookup(&first_data);
    let start_ms = first_folds
        .first()
        .map(|fold| fold.oos_start_ms)
        .unwrap_or(date_ms(first_config.start)?);
    let end_ms = first_folds
        .last()
        .map(|fold| fold.oos_end_ms)
        .unwrap_or(date_ms(first_config.end)?);

    let mut component_reports = Vec::new();
    let mut combined_trades = Vec::new();
    let mut combined_risk_managed_trades = Vec::new();
    let mut used_risk_overlay = false;
    for spec in &specs {
        let run_dir = PathBuf::from(RUNS_ROOT).join(&spec.run_id);
        let config = read_json::<WfoConfig>(run_dir.join("config.json"))?;
        if config.preset != first_config.preset
            || config.start != first_config.start
            || config.end != first_config.end
            || (config.fixed_notional - first_config.fixed_notional).abs() > f64::EPSILON
        {
            anyhow::bail!(
                "component {} has incompatible preset/date/notional config",
                spec.run_id
            );
        }
        let folds = read_csv::<Fold>(run_dir.join("folds.csv"))?;
        if folds != first_folds {
            anyhow::bail!("component {} has incompatible fold schedule", spec.run_id);
        }
        let blocks = read_strategy_oos_results(Some(&spec.run_id))?;
        let block = blocks
            .iter()
            .find(|block| {
                block.indicator == spec.indicator.as_str()
                    && block.timeframe == spec.timeframe.as_str()
            })
            .with_context(|| {
                format!(
                    "missing strategy block {}:{}:{}",
                    spec.run_id,
                    spec.indicator.as_str(),
                    spec.timeframe.as_str()
                )
            })?;
        if block.status != "complete" {
            anyhow::bail!(
                "{}:{}:{} is not complete",
                spec.run_id,
                spec.indicator.as_str(),
                spec.timeframe.as_str()
            );
        }
        let data = load_wfo_data(&config)?;
        let component_close_by_symbol = close_lookup(&data);
        let scenario = [StressScenario {
            name: "baseline_replay",
            fees_bps: config.fees_bps,
            breach_ticks: 1,
        }];
        let mut replay = stress_replay_block_all_scenarios(
            block,
            &scenario,
            &config,
            &folds,
            &data,
            (start_ms, end_ms),
            &component_close_by_symbol,
        )?;
        let replay = replay.remove(0);
        combined_trades.extend(
            replay
                .fold_trades
                .iter()
                .flat_map(|fold| fold.trades.clone()),
        );
        let risk_managed_replay = block.risk_overlay.as_ref().map(|overlay| {
            used_risk_overlay = true;
            apply_circuit_breaker_to_replay(
                &replay,
                &CircuitBreakerScenario {
                    name: "saved_overlay",
                    loss_trigger_pct: overlay.loss_trigger_pct,
                    pause_folds: overlay.pause_folds,
                },
                config.fixed_notional,
                (start_ms, end_ms),
                &component_close_by_symbol,
            )
        });
        let risk_source = risk_managed_replay.as_ref().unwrap_or(&replay);
        combined_risk_managed_trades.extend(
            risk_source
                .fold_trades
                .iter()
                .flat_map(|fold| fold.trades.clone()),
        );
        component_reports.push(PortfolioComboComponentReport {
            run_id: spec.run_id.clone(),
            indicator: spec.indicator.as_str().to_string(),
            timeframe: spec.timeframe.as_str().to_string(),
            metrics: replay.metrics.clone(),
            original_metrics: block.portfolio.clone(),
            risk_managed_metrics: risk_managed_replay.map(|replay| replay.metrics),
        });
    }

    combined_trades.sort_by_key(|trade| trade.exit_time_ms);
    combined_risk_managed_trades.sort_by_key(|trade| trade.exit_time_ms);
    let component_metrics = component_reports
        .iter()
        .map(|component| component.metrics.clone())
        .collect::<Vec<_>>();
    let allocated_notional = first_config.fixed_notional * specs.len() as f64;
    let portfolio = strategy_oos_metrics(
        &combined_trades,
        first_config.fixed_notional,
        start_ms,
        end_ms,
        &close_by_symbol,
    );
    let portfolio_per_allocated_notional = strategy_oos_metrics(
        &combined_trades,
        allocated_notional,
        start_ms,
        end_ms,
        &close_by_symbol,
    );
    let risk_managed_portfolio = used_risk_overlay.then(|| {
        strategy_oos_metrics(
            &combined_risk_managed_trades,
            first_config.fixed_notional,
            start_ms,
            end_ms,
            &close_by_symbol,
        )
    });
    let risk_managed_portfolio_per_allocated_notional = used_risk_overlay.then(|| {
        strategy_oos_metrics(
            &combined_risk_managed_trades,
            allocated_notional,
            start_ms,
            end_ms,
            &close_by_symbol,
        )
    });
    let periods = portfolio_combo_periods(
        &combined_trades,
        allocated_notional,
        start_ms,
        end_ms,
        &close_by_symbol,
    );
    let risk_managed_periods = if used_risk_overlay {
        portfolio_combo_periods(
            &combined_risk_managed_trades,
            allocated_notional,
            start_ms,
            end_ms,
            &close_by_symbol,
        )
    } else {
        Vec::new()
    };
    let report = PortfolioComboReport {
        generated_at: Utc::now(),
        components: component_reports,
        portfolio,
        portfolio_per_allocated_notional,
        risk_managed_portfolio,
        risk_managed_portfolio_per_allocated_notional,
        periods,
        risk_managed_periods,
        component_return_correlation: component_equity_return_correlation(&component_metrics),
        fixed_notional: first_config.fixed_notional,
        allocated_notional,
        start_ms,
        end_ms,
    };
    let combo_dir = PathBuf::from(RUNS_ROOT).join("portfolio_combos");
    fs::create_dir_all(&combo_dir)?;
    let component_slug = specs
        .iter()
        .map(|spec| {
            format!(
                "{}_{}_{}",
                spec.run_id,
                spec.indicator.as_str(),
                spec.timeframe.as_str()
            )
        })
        .collect::<Vec<_>>()
        .join("__");
    let filename = format!(
        "{}-{}.json",
        Utc::now().format("%Y%m%dT%H%M%SZ"),
        sanitize_strategy_file_part(&component_slug)
    );
    let path = combo_dir.join(filename);
    write_json(path.clone(), &report)?;
    Ok(path)
}

fn parse_combo_component_spec(value: &str) -> Result<PortfolioComboComponentSpec> {
    let parts = value.split(':').collect::<Vec<_>>();
    if parts.len() != 3 {
        anyhow::bail!("invalid combo component {value}; use run_id:indicator:timeframe");
    }
    Ok(PortfolioComboComponentSpec {
        run_id: parts[0].to_string(),
        indicator: parse_indicator_kind(parts[1])?,
        timeframe: parse_timeframe_kind(parts[2])?,
    })
}

fn portfolio_combo_periods(
    trades: &[Trade],
    fixed_notional: f64,
    start_ms: i64,
    end_ms: i64,
    close_by_symbol: &BTreeMap<String, BTreeMap<i64, f64>>,
) -> Vec<PortfolioComboPeriodReport> {
    let span = (end_ms - start_ms).max(1);
    (0..4)
        .map(|index| {
            let period_start = start_ms + span * index / 4;
            let period_end = if index == 3 {
                end_ms
            } else {
                start_ms + span * (index + 1) / 4
            };
            let period_trades = trades
                .iter()
                .filter(|trade| trade_fully_inside_window(trade, period_start, period_end))
                .cloned()
                .collect::<Vec<_>>();
            PortfolioComboPeriodReport {
                label: format!("Q{}", index + 1),
                start_ms: period_start,
                end_ms: period_end,
                metrics: strategy_oos_metrics(
                    &period_trades,
                    fixed_notional,
                    period_start,
                    period_end,
                    close_by_symbol,
                ),
            }
        })
        .collect()
}

#[derive(Debug, Clone, Deserialize)]
struct OffsetStitchManifestRow {
    window: String,
    offset_days: i64,
    run_id: String,
    path: String,
}

#[derive(Debug, Clone, Serialize)]
struct OosPrefixDecayCsvRow {
    window: String,
    bucket: String,
    prefix_days: usize,
    pnl: f64,
    net_return_pct: f64,
    profit_factor: f64,
    trades: usize,
    win_rate: f64,
    pnl_per_day: f64,
    share_of_full_week_pnl_pct: f64,
    exact_day_pnl: f64,
    exact_day_trades: usize,
}

#[derive(Debug, Clone, Default)]
struct OosPrefixBucket {
    pnl: f64,
    gross_win: f64,
    gross_loss: f64,
    trades: usize,
    wins: usize,
}

impl OosPrefixBucket {
    fn add_trade(&mut self, trade: &Trade) {
        self.pnl += trade.pnl;
        if trade.pnl > 0.0 {
            self.gross_win += trade.pnl;
            self.wins += 1;
        } else if trade.pnl < 0.0 {
            self.gross_loss += trade.pnl.abs();
        }
        self.trades += 1;
    }

    fn add_bucket(&mut self, other: &Self) {
        self.pnl += other.pnl;
        self.gross_win += other.gross_win;
        self.gross_loss += other.gross_loss;
        self.trades += other.trades;
        self.wins += other.wins;
    }

    fn profit_factor(&self) -> f64 {
        if self.gross_loss > 0.0 {
            self.gross_win / self.gross_loss
        } else if self.gross_win > 0.0 {
            999.0
        } else {
            0.0
        }
    }

    fn win_rate(&self) -> f64 {
        if self.trades == 0 {
            0.0
        } else {
            self.wins as f64 / self.trades as f64 * 100.0
        }
    }
}

#[derive(Debug, Clone, Serialize)]
struct IsDailyProfitScanRow {
    run_id: String,
    symbol: String,
    scan_offset_days: i64,
    candidate_id: usize,
    fold_index: usize,
    is_start_date: String,
    is_end_date: String,
    is_days: usize,
    profitable_days: usize,
    losing_days: usize,
    flat_days: usize,
    trades: usize,
    pnl: f64,
    net_return_pct: f64,
    profit_factor: f64,
    max_drawdown_pct: f64,
    worst_day_pnl: f64,
    best_day_pnl: f64,
    oos_trades: usize,
    oos_pnl: f64,
    oos_net_return_pct: f64,
    oos_profit_factor: f64,
    oos_max_drawdown_pct: f64,
    oos_positive: bool,
    oos_day1_trades: usize,
    oos_day1_pnl: f64,
    oos_day1_net_return_pct: f64,
    oos_day1_profit_factor: f64,
    oos_day1_positive: bool,
    day_pnls: String,
    day_trades: String,
}

#[derive(Debug, Clone, Serialize)]
struct IsDailyProfitScanSummary {
    run_id: String,
    generated_at: DateTime<Utc>,
    elapsed_seconds: f64,
    symbols: Vec<String>,
    scan_offset_days: Vec<i64>,
    candidates: usize,
    folds: usize,
    evaluated_windows: usize,
    is_days: usize,
    min_profitable_days: usize,
    perfect_windows: usize,
    perfect_candidates: usize,
    perfect_folds: usize,
    max_profitable_days: usize,
    profitable_day_distribution: BTreeMap<usize, usize>,
    top_rows_written: usize,
}

fn generate_config_folds_for_offset(config: &WfoConfig, offset_days: i64) -> Result<Vec<Fold>> {
    let start_ms = date_ms(config.start)? + Duration::days(offset_days).num_milliseconds();
    let end_ms = date_ms(config.end)?;
    Ok(generate_folds_days(
        start_ms,
        end_ms,
        config.effective_is_days(),
        config.effective_oos_days(),
        config.effective_step_days(),
        config.effective_gap_days(),
    ))
}

pub fn scan_is_daily_profit(
    run_id: &str,
    scan_offset_days: &[i64],
    min_profitable_days: usize,
    top_rows: usize,
) -> Result<PathBuf> {
    let started = Instant::now();
    let run_dir = PathBuf::from(RUNS_ROOT).join(run_id);
    if !run_dir.exists() {
        anyhow::bail!("missing WFO run {run_id}");
    }
    let config = read_json::<WfoConfig>(run_dir.join("config.json"))?;
    let folds = read_csv::<Fold>(run_dir.join("folds.csv"))?;
    let candidates = read_csv::<Candidate>(run_dir.join("candidates.csv"))?;
    if folds.is_empty() {
        anyhow::bail!("{run_id} has no folds");
    }
    if candidates.is_empty() {
        anyhow::bail!("{run_id} has no candidates");
    }
    let scan_schedules = if scan_offset_days.is_empty() {
        vec![(config.start_offset_days, folds.clone())]
    } else {
        scan_offset_days
            .iter()
            .copied()
            .map(|offset| Ok((offset, generate_config_folds_for_offset(&config, offset)?)))
            .collect::<Result<Vec<_>>>()?
    };
    if scan_schedules.iter().all(|(_, folds)| folds.is_empty()) {
        anyhow::bail!("{run_id} has no scan folds");
    }

    let data = load_wfo_data(&config)?;
    let day_ms = Duration::days(1).num_milliseconds();
    let expected_is_days = scan_schedules
        .iter()
        .flat_map(|(_, folds)| folds)
        .map(|fold| ((fold.is_end_ms - fold.is_start_ms) / day_ms).max(0) as usize)
        .max()
        .unwrap_or_default();
    let mut distribution = BTreeMap::<usize, usize>::new();
    let mut perfect_rows = Vec::new();
    let mut top_rows_buffer = Vec::new();
    let mut evaluated_windows = 0usize;
    let mut max_profitable_days = 0usize;

    for (symbol, bars) in &data {
        let symbol_candidates = candidates
            .iter()
            .filter(|candidate| {
                candidate_allowed_for_symbol(config.strategy_set.as_deref(), symbol, candidate)
            })
            .collect::<Vec<_>>();
        if symbol_candidates.is_empty() {
            continue;
        }
        let mut cache = SimulationCache::default();
        for (candidate_pos, candidate) in symbol_candidates.iter().enumerate() {
            let prepared =
                prepare_candidate_simulation(symbol, bars, candidate, &config, &mut cache)?;
            let result = simulate_prepared_candidate(bars, &prepared, &folds);
            for (scan_offset, scan_folds) in &scan_schedules {
                for fold in scan_folds {
                    let row = is_daily_profit_scan_row(
                        run_id,
                        symbol,
                        *scan_offset,
                        &result.candidate,
                        fold,
                        &result.trades,
                        config.fixed_notional,
                        day_ms,
                    );
                    evaluated_windows += 1;
                    max_profitable_days = max_profitable_days.max(row.profitable_days);
                    *distribution.entry(row.profitable_days).or_default() += 1;
                    if row.profitable_days >= min_profitable_days {
                        perfect_rows.push(row.clone());
                    }
                    top_rows_buffer.push(row);
                }
            }
            if (candidate_pos + 1) % 100 == 0 || candidate_pos + 1 == symbol_candidates.len() {
                eprintln!(
                    "{run_id} {symbol}: scanned {}/{} candidates",
                    candidate_pos + 1,
                    symbol_candidates.len()
                );
            }
        }
    }

    top_rows_buffer.sort_by(|left, right| {
        right
            .profitable_days
            .cmp(&left.profitable_days)
            .then_with(|| right.pnl.total_cmp(&left.pnl))
            .then_with(|| left.scan_offset_days.cmp(&right.scan_offset_days))
            .then_with(|| left.candidate_id.cmp(&right.candidate_id))
            .then_with(|| left.fold_index.cmp(&right.fold_index))
    });
    if top_rows_buffer.len() > top_rows {
        top_rows_buffer.truncate(top_rows);
    }

    let perfect_candidates = perfect_rows
        .iter()
        .map(|row| (row.symbol.clone(), row.candidate_id))
        .collect::<std::collections::BTreeSet<_>>()
        .len();
    let perfect_folds = perfect_rows
        .iter()
        .map(|row| (row.scan_offset_days, row.fold_index))
        .collect::<std::collections::BTreeSet<_>>()
        .len();
    let summary = IsDailyProfitScanSummary {
        run_id: run_id.to_string(),
        generated_at: Utc::now(),
        elapsed_seconds: started.elapsed().as_secs_f64(),
        symbols: data.iter().map(|(symbol, _)| symbol.clone()).collect(),
        scan_offset_days: scan_schedules.iter().map(|(offset, _)| *offset).collect(),
        candidates: candidates.len(),
        folds: scan_schedules.iter().map(|(_, folds)| folds.len()).sum(),
        evaluated_windows,
        is_days: expected_is_days,
        min_profitable_days,
        perfect_windows: perfect_rows.len(),
        perfect_candidates,
        perfect_folds,
        max_profitable_days,
        profitable_day_distribution: distribution,
        top_rows_written: top_rows_buffer.len(),
    };
    write_json(run_dir.join("is_daily_profit_scan_summary.json"), &summary)?;
    write_csv(run_dir.join("is_daily_profit_hits.csv"), &perfect_rows)?;
    write_csv(run_dir.join("is_daily_profit_top.csv"), &top_rows_buffer)?;
    Ok(run_dir.join("is_daily_profit_scan_summary.json"))
}

#[allow(clippy::too_many_arguments)]
fn is_daily_profit_scan_row(
    run_id: &str,
    symbol: &str,
    scan_offset_days: i64,
    candidate: &Candidate,
    fold: &Fold,
    trades: &[Trade],
    fixed_notional: f64,
    day_ms: i64,
) -> IsDailyProfitScanRow {
    let is_days = ((fold.is_end_ms - fold.is_start_ms) / day_ms).max(0) as usize;
    let mut day_pnls = vec![0.0; is_days];
    let mut day_trades = vec![0usize; is_days];
    let is_trades = trades_for_window(trades, fold.is_start_ms, fold.is_end_ms);
    let oos_trades = trades_for_window(trades, fold.oos_start_ms, fold.oos_end_ms);
    let oos_day1_trades = trades_for_window(
        trades,
        fold.oos_start_ms,
        (fold.oos_start_ms + day_ms).min(fold.oos_end_ms),
    );
    for trade in &is_trades {
        let day_index = ((trade.exit_time_ms - fold.is_start_ms) / day_ms) as usize;
        if day_index < is_days {
            day_pnls[day_index] += trade.pnl;
            day_trades[day_index] += 1;
        }
    }
    let profitable_days = day_pnls.iter().filter(|pnl| **pnl > 0.0).count();
    let losing_days = day_pnls.iter().filter(|pnl| **pnl < 0.0).count();
    let flat_days = is_days.saturating_sub(profitable_days + losing_days);
    let pnl = day_pnls.iter().sum::<f64>();
    let oos_pnl = oos_trades.iter().map(|trade| trade.pnl).sum::<f64>();
    let oos_day1_pnl = oos_day1_trades.iter().map(|trade| trade.pnl).sum::<f64>();
    IsDailyProfitScanRow {
        run_id: run_id.to_string(),
        symbol: symbol.to_string(),
        scan_offset_days,
        candidate_id: candidate.id,
        fold_index: fold.index,
        is_start_date: utc_date_string(fold.is_start_ms),
        is_end_date: utc_date_string(fold.is_end_ms - 1),
        is_days,
        profitable_days,
        losing_days,
        flat_days,
        trades: is_trades.len(),
        pnl,
        net_return_pct: pnl / fixed_notional.max(1.0) * 100.0,
        profit_factor: profit_factor_from_trade_refs(&is_trades),
        max_drawdown_pct: max_drawdown_pct_from_trade_refs(&is_trades),
        worst_day_pnl: day_pnls.iter().copied().fold(0.0, f64::min),
        best_day_pnl: day_pnls.iter().copied().fold(0.0, f64::max),
        oos_trades: oos_trades.len(),
        oos_pnl,
        oos_net_return_pct: oos_pnl / fixed_notional.max(1.0) * 100.0,
        oos_profit_factor: profit_factor_from_trade_refs(&oos_trades),
        oos_max_drawdown_pct: max_drawdown_pct_from_trade_refs(&oos_trades),
        oos_positive: oos_pnl > 0.0,
        oos_day1_trades: oos_day1_trades.len(),
        oos_day1_pnl,
        oos_day1_net_return_pct: oos_day1_pnl / fixed_notional.max(1.0) * 100.0,
        oos_day1_profit_factor: profit_factor_from_trade_refs(&oos_day1_trades),
        oos_day1_positive: oos_day1_pnl > 0.0,
        day_pnls: day_pnls
            .iter()
            .map(|value| format!("{value:.4}"))
            .collect::<Vec<_>>()
            .join("|"),
        day_trades: day_trades
            .iter()
            .map(|value| value.to_string())
            .collect::<Vec<_>>()
            .join("|"),
    }
}

fn utc_date_string(timestamp_ms: i64) -> String {
    Utc.timestamp_millis_opt(timestamp_ms)
        .single()
        .map(|dt| dt.date_naive().to_string())
        .unwrap_or_else(|| timestamp_ms.to_string())
}

pub fn write_oos_prefix_decay_report(manifest: &str) -> Result<PathBuf> {
    let manifest_path = PathBuf::from(manifest);
    let output_dir = manifest_path
        .parent()
        .map(Path::to_path_buf)
        .unwrap_or_else(|| PathBuf::from("."));
    let manifest_rows = read_csv::<OffsetStitchManifestRow>(manifest_path.clone())
        .with_context(|| format!("read {}", manifest_path.display()))?;
    if manifest_rows.is_empty() {
        anyhow::bail!("manifest {} has no runs", manifest_path.display());
    }

    let day_ms = Duration::days(1).num_milliseconds();
    let mut daily: BTreeMap<(String, String), Vec<OosPrefixBucket>> = BTreeMap::new();
    let mut run_checks = Vec::<String>::new();

    for manifest_row in &manifest_rows {
        let run_dir = PathBuf::from(&manifest_row.path);
        let config = read_json::<WfoConfig>(run_dir.join("config.json"))?;
        let folds = read_csv::<Fold>(run_dir.join("folds.csv"))?;
        let candidates = read_csv::<Candidate>(run_dir.join("candidates.csv"))?;
        let candidates_by_id = candidates
            .into_iter()
            .map(|candidate| (candidate.id, candidate))
            .collect::<BTreeMap<_, _>>();
        let block = read_json::<StrategyOosBlock>(
            run_dir
                .join(STRATEGY_OOS_BLOCKS_DIR)
                .join("strategy_4448_kama_ker__5m.json"),
        )?;
        let data = load_wfo_data(&config)?;
        let bars_by_symbol = data
            .iter()
            .map(|(symbol, bars)| (symbol.as_str(), bars.as_slice()))
            .collect::<BTreeMap<_, _>>();
        let mut symbol_caches = BTreeMap::<String, SimulationCache>::new();
        let mut simulation_cache = BTreeMap::<(String, usize), Vec<Trade>>::new();
        let mut reconstructed_pnl = 0.0;
        let mut reconstructed_trades = 0usize;

        for selection in &block.selected_candidates {
            let fold = folds
                .iter()
                .find(|fold| fold.index == selection.fold_index)
                .with_context(|| {
                    format!(
                        "{} missing fold {}",
                        manifest_row.run_id, selection.fold_index
                    )
                })?;
            let candidate = selection
                .candidate
                .clone()
                .or_else(|| candidates_by_id.get(&selection.candidate_id).cloned())
                .with_context(|| {
                    format!(
                        "{} missing selected candidate {}",
                        manifest_row.run_id, selection.candidate_id
                    )
                })?;
            let symbol = selection.symbol.as_str();
            let all_trades = if let Some(trades) =
                simulation_cache.get(&(selection.symbol.clone(), candidate.id))
            {
                trades.clone()
            } else {
                let bars = bars_by_symbol.get(symbol).copied().with_context(|| {
                    format!("{} missing loaded data for {symbol}", manifest_row.run_id)
                })?;
                let cache = symbol_caches.entry(selection.symbol.clone()).or_default();
                let prepared =
                    prepare_candidate_simulation(symbol, bars, &candidate, &config, cache)?;
                let result = simulate_prepared_candidate(bars, &prepared, &folds);
                let trades = result.trades;
                simulation_cache.insert((selection.symbol.clone(), candidate.id), trades.clone());
                trades
            };
            for trade in all_trades.iter().filter(|trade| {
                trade_fully_inside_window(trade, fold.oos_start_ms, fold.oos_end_ms)
            }) {
                let day = ((trade.exit_time_ms - fold.oos_start_ms) / day_ms) as usize + 1;
                if !(1..=7).contains(&day) {
                    continue;
                }
                let symbol_key = selection
                    .symbol
                    .strip_suffix("USDT")
                    .unwrap_or(&selection.symbol)
                    .to_string();
                for bucket in ["Combined".to_string(), symbol_key] {
                    let entry = daily
                        .entry((manifest_row.window.clone(), bucket))
                        .or_insert_with(|| vec![OosPrefixBucket::default(); 8]);
                    entry[day].add_trade(trade);
                }
                reconstructed_pnl += trade.pnl;
                reconstructed_trades += 1;
            }
        }

        if let Some(portfolio) = &block.portfolio {
            run_checks.push(format!(
                "{} offset {:+}: reconstructed {} trades / {:.2} pnl; artifact {} trades / {:.2} pnl",
                manifest_row.run_id,
                manifest_row.offset_days,
                reconstructed_trades,
                reconstructed_pnl,
                portfolio.trades,
                portfolio.total_pnl
            ));
        }
    }

    let mut rows = Vec::new();
    for ((window, bucket), exact_days) in &daily {
        let mut full_week = OosPrefixBucket::default();
        for exact in exact_days.iter().skip(1).take(7) {
            full_week.add_bucket(exact);
        }
        let mut cumulative = OosPrefixBucket::default();
        for (prefix_days, exact_day) in exact_days.iter().enumerate().take(8).skip(1) {
            cumulative.add_bucket(exact_day);
            rows.push(OosPrefixDecayCsvRow {
                window: window.clone(),
                bucket: bucket.clone(),
                prefix_days,
                pnl: cumulative.pnl,
                net_return_pct: cumulative.pnl / 7_000.0 * 100.0,
                profit_factor: cumulative.profit_factor(),
                trades: cumulative.trades,
                win_rate: cumulative.win_rate(),
                pnl_per_day: cumulative.pnl / prefix_days as f64,
                share_of_full_week_pnl_pct: if full_week.pnl.abs() > 1e-9 {
                    cumulative.pnl / full_week.pnl * 100.0
                } else {
                    0.0
                },
                exact_day_pnl: exact_day.pnl,
                exact_day_trades: exact_day.trades,
            });
        }
    }

    let csv_path = output_dir.join("oos_prefix_decay.csv");
    write_csv(csv_path, &rows)?;
    let html_path = output_dir.join("oos_prefix_decay.html");
    fs::write(&html_path, oos_prefix_decay_html(&rows, &run_checks))?;
    Ok(html_path)
}

fn oos_prefix_decay_html(rows: &[OosPrefixDecayCsvRow], run_checks: &[String]) -> String {
    let mut by_window = BTreeMap::<String, Vec<&OosPrefixDecayCsvRow>>::new();
    for row in rows {
        by_window.entry(row.window.clone()).or_default().push(row);
    }
    let mut sections = String::new();
    for (window, window_rows) in by_window {
        let mut by_bucket = BTreeMap::<String, Vec<&OosPrefixDecayCsvRow>>::new();
        for row in window_rows {
            by_bucket.entry(row.bucket.clone()).or_default().push(row);
        }
        sections.push_str(&format!("<section><h2>{}</h2>", html_escape(&window)));
        sections.push_str("<table><thead><tr><th>Bucket</th>");
        for day in 1..=7 {
            sections.push_str(&format!("<th>1-{day} days</th>"));
        }
        sections.push_str("</tr></thead><tbody>");
        for bucket in ["Combined", "BTC", "SUI", "SOL", "ETH"] {
            if let Some(bucket_rows) = by_bucket.get(bucket) {
                sections.push_str(&format!("<tr><th>{}</th>", html_escape(bucket)));
                for row in bucket_rows {
                    sections.push_str(&format!(
                        "<td><b class=\"{}\">{:+.2}%</b><span>pnl {:+.2}</span><span>PF {:.3}</span><span>{} trades</span><span>day pnl {:+.2}</span></td>",
                        pct_class(row.net_return_pct),
                        row.net_return_pct,
                        row.pnl,
                        row.profit_factor,
                        row.trades,
                        row.exact_day_pnl
                    ));
                }
                sections.push_str("</tr>");
            }
        }
        sections.push_str("</tbody></table></section>");
    }
    let checks = run_checks
        .iter()
        .map(|check| format!("<li>{}</li>", html_escape(check)))
        .collect::<String>();
    format!(
        r#"<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>OOS Prefix Decay</title>
<style>
body{{margin:0;padding:16px;background:#0c1113;color:#e6eef0;font:12px/1.35 -apple-system,BlinkMacSystemFont,Segoe UI,sans-serif}}
h1{{font-size:18px;margin:0 0 12px}} h2{{font-size:14px;margin:18px 0 8px}}
table{{border-collapse:collapse;width:100%;table-layout:fixed;margin-bottom:18px;background:#12191c;border:1px solid #263238}}
th,td{{border-bottom:1px solid #263238;border-right:1px solid #263238;padding:7px;vertical-align:top;overflow:hidden}}
th{{color:#aebdc2;text-align:left;width:86px}} td span{{display:block;color:#8ea0a6;font-size:10px;margin-top:2px}}
.pos{{color:#52d985}} .neg{{color:#ff737b}} .note{{color:#8ea0a6;margin-bottom:12px}} ul{{color:#8ea0a6;font-size:11px}}
</style></head><body>
<h1>OOS Prefix Decay</h1>
<div class="note">Each cell is cumulative from OOS day 1 through the shown day. "day pnl" is the incremental PnL added by the final day in that prefix. Net return denominator is $7,000 stitched capital per window.</div>
{sections}
<h2>Reconstruction Checks</h2><ul>{checks}</ul>
</body></html>"#
    )
}

fn component_equity_return_correlation(metrics: &[StrategyOosMetrics]) -> Option<f64> {
    if metrics.len() != 2 {
        return None;
    }
    let times = metrics
        .iter()
        .flat_map(|metrics| metrics.equity_curve.iter().map(|point| point.timestamp_ms))
        .collect::<std::collections::BTreeSet<_>>()
        .into_iter()
        .collect::<Vec<_>>();
    if times.len() < 3 {
        return None;
    }
    let left = equity_step_returns(&metrics[0].equity_curve, &times);
    let right = equity_step_returns(&metrics[1].equity_curve, &times);
    pearson_correlation(&left, &right)
}

fn equity_step_returns(curve: &[StrategyCurvePoint], times: &[i64]) -> Vec<f64> {
    let mut values = Vec::with_capacity(times.len());
    let mut index = 0usize;
    let mut current = 0.0;
    for time in times {
        while index < curve.len() && curve[index].timestamp_ms <= *time {
            current = curve[index].equity;
            index += 1;
        }
        values.push(current);
    }
    values
        .windows(2)
        .map(|window| window[1] - window[0])
        .collect()
}

fn pearson_correlation(left: &[f64], right: &[f64]) -> Option<f64> {
    if left.len() != right.len() || left.len() < 2 {
        return None;
    }
    let left_mean = left.iter().sum::<f64>() / left.len() as f64;
    let right_mean = right.iter().sum::<f64>() / right.len() as f64;
    let mut numerator = 0.0;
    let mut left_var = 0.0;
    let mut right_var = 0.0;
    for (left_value, right_value) in left.iter().zip(right) {
        let left_delta = left_value - left_mean;
        let right_delta = right_value - right_mean;
        numerator += left_delta * right_delta;
        left_var += left_delta * left_delta;
        right_var += right_delta * right_delta;
    }
    let denominator = (left_var * right_var).sqrt();
    (denominator > 0.0).then_some(numerator / denominator)
}

pub fn stress_validate_run(
    run_id: &str,
    requested_pairs: &[String],
    min_profit_factor: f64,
) -> Result<PathBuf> {
    validate_min_profit_factor(min_profit_factor)?;
    let run_dir = PathBuf::from(RUNS_ROOT).join(run_id);
    if !run_dir.exists() {
        anyhow::bail!("missing WFO run {run_id}");
    }

    let config = read_json::<WfoConfig>(run_dir.join("config.json"))?;
    let folds = read_csv::<Fold>(run_dir.join("folds.csv"))?;
    let block_map = read_strategy_oos_block_map(&run_dir)?;
    let target_blocks = stress_target_blocks(&block_map, requested_pairs, min_profit_factor)?;
    if target_blocks.is_empty() {
        anyhow::bail!("no completed positive strategy OOS blocks met PF >= {min_profit_factor}");
    }

    let data = load_wfo_data(&config)?;
    let close_by_symbol = close_lookup(&data);
    let scenarios = stress_scenarios(config.fees_bps);
    let circuit_scenarios = circuit_breaker_scenarios();
    let start_ms = folds
        .first()
        .map(|fold| fold.oos_start_ms)
        .unwrap_or(date_ms(config.start)?);
    let end_ms = folds
        .last()
        .map(|fold| fold.oos_end_ms)
        .unwrap_or(date_ms(config.end)?);

    let mut report_blocks = Vec::new();
    let mut circuit_report_blocks = Vec::new();
    let mut csv_rows = Vec::new();
    let mut symbol_rows = Vec::new();
    let mut circuit_csv_rows = Vec::new();
    let mut circuit_symbol_rows = Vec::new();
    for block in &target_blocks {
        let original = block.portfolio.as_ref().map(diagnostic_oos_metrics);
        eprintln!(
            "stress replay {} {} ({} selected symbol-folds)",
            block.indicator,
            block.timeframe,
            block.selected_candidates.len()
        );
        let replays = stress_replay_block_all_scenarios(
            block,
            &scenarios,
            &config,
            &folds,
            &data,
            (start_ms, end_ms),
            &close_by_symbol,
        )?;
        for (scenario, replay) in scenarios.iter().zip(replays) {
            let metrics = replay.metrics.clone();
            let original_net = original
                .as_ref()
                .map(|metrics| metrics.net_return_pct)
                .unwrap_or(0.0);
            let original_dd = original
                .as_ref()
                .map(|metrics| metrics.max_drawdown_pct)
                .unwrap_or(0.0);
            let original_pf = original
                .as_ref()
                .map(|metrics| metrics.profit_factor)
                .unwrap_or(0.0);
            let original_trades = original.as_ref().map(|metrics| metrics.trades).unwrap_or(0);
            let pass_net_positive = metrics.net_return_pct > 0.0;
            let pass_profit_factor = metrics.profit_factor >= min_profit_factor;
            let pass_min_trades = metrics.trades >= MIN_CANDIDATE_OOS_TRADES;
            csv_rows.push(StressValidationCsvRow {
                indicator: block.indicator.clone(),
                timeframe: block.timeframe.clone(),
                scenario: scenario.name.to_string(),
                fees_bps: scenario.fees_bps,
                breach_ticks: scenario.breach_ticks,
                original_net_return_pct: original_net,
                original_max_drawdown_pct: original_dd,
                original_profit_factor: original_pf,
                original_trades,
                net_return_pct: metrics.net_return_pct,
                max_drawdown_pct: metrics.max_drawdown_pct,
                profit_factor: metrics.profit_factor,
                trades: metrics.trades,
                win_rate: metrics.win_rate,
                sharpe: metrics.sharpe,
                net_retention_pct: if original_net.abs() > f64::EPSILON {
                    metrics.net_return_pct / original_net * 100.0
                } else {
                    0.0
                },
                pass_net_positive,
                pass_profit_factor,
                min_candidate_oos_trades: MIN_CANDIDATE_OOS_TRADES,
                pass_min_trades,
                pass_candidate: pass_net_positive && pass_profit_factor && pass_min_trades,
            });
            for symbol in &replay.symbols {
                symbol_rows.push(StressValidationSymbolCsvRow {
                    indicator: block.indicator.clone(),
                    timeframe: block.timeframe.clone(),
                    scenario: scenario.name.to_string(),
                    symbol: symbol.symbol.clone(),
                    net_return_pct: symbol.metrics.net_return_pct,
                    max_drawdown_pct: symbol.metrics.max_drawdown_pct,
                    profit_factor: symbol.metrics.profit_factor,
                    trades: symbol.metrics.trades,
                    win_rate: symbol.metrics.win_rate,
                    sharpe: symbol.metrics.sharpe,
                });
            }
            report_blocks.push(StressValidationBlock {
                indicator: block.indicator.clone(),
                timeframe: block.timeframe.clone(),
                scenario: scenario.name.to_string(),
                fees_bps: scenario.fees_bps,
                breach_ticks: scenario.breach_ticks,
                original: original.clone(),
                metrics,
                symbols: replay.symbols.clone(),
            });
            for circuit in &circuit_scenarios {
                let circuit_replay = apply_circuit_breaker_to_replay(
                    &replay,
                    circuit,
                    config.fixed_notional,
                    (start_ms, end_ms),
                    &close_by_symbol,
                );
                circuit_csv_rows.push(StressCircuitValidationCsvRow {
                    indicator: block.indicator.clone(),
                    timeframe: block.timeframe.clone(),
                    stress_scenario: scenario.name.to_string(),
                    circuit_scenario: circuit.name.to_string(),
                    fees_bps: scenario.fees_bps,
                    breach_ticks: scenario.breach_ticks,
                    loss_trigger_pct: circuit.loss_trigger_pct,
                    pause_folds: circuit.pause_folds,
                    net_return_pct: circuit_replay.metrics.net_return_pct,
                    max_drawdown_pct: circuit_replay.metrics.max_drawdown_pct,
                    profit_factor: circuit_replay.metrics.profit_factor,
                    trades: circuit_replay.metrics.trades,
                    win_rate: circuit_replay.metrics.win_rate,
                    sharpe: circuit_replay.metrics.sharpe,
                });
                for symbol in &circuit_replay.symbols {
                    circuit_symbol_rows.push(StressCircuitValidationSymbolCsvRow {
                        indicator: block.indicator.clone(),
                        timeframe: block.timeframe.clone(),
                        stress_scenario: scenario.name.to_string(),
                        circuit_scenario: circuit.name.to_string(),
                        symbol: symbol.symbol.clone(),
                        net_return_pct: symbol.metrics.net_return_pct,
                        max_drawdown_pct: symbol.metrics.max_drawdown_pct,
                        profit_factor: symbol.metrics.profit_factor,
                        trades: symbol.metrics.trades,
                        win_rate: symbol.metrics.win_rate,
                        sharpe: symbol.metrics.sharpe,
                    });
                }
                circuit_report_blocks.push(StressCircuitValidationBlock {
                    indicator: block.indicator.clone(),
                    timeframe: block.timeframe.clone(),
                    stress_scenario: scenario.name.to_string(),
                    circuit_scenario: circuit.name.to_string(),
                    fees_bps: scenario.fees_bps,
                    breach_ticks: scenario.breach_ticks,
                    loss_trigger_pct: circuit.loss_trigger_pct,
                    pause_folds: circuit.pause_folds,
                    metrics: circuit_replay.metrics,
                    symbols: circuit_replay.symbols,
                });
            }
        }
    }

    write_csv(run_dir.join("selected_oos_stress.csv"), &csv_rows)?;
    write_csv(
        run_dir.join("selected_oos_stress_by_symbol.csv"),
        &symbol_rows,
    )?;
    write_csv(run_dir.join("selected_oos_circuit.csv"), &circuit_csv_rows)?;
    write_csv(
        run_dir.join("selected_oos_circuit_by_symbol.csv"),
        &circuit_symbol_rows,
    )?;
    let report = StressValidationReport {
        run_id: config.run_id.clone(),
        generated_at: Utc::now(),
        min_profit_factor,
        min_candidate_oos_trades: MIN_CANDIDATE_OOS_TRADES,
        targets: target_blocks.len(),
        scenarios: scenarios
            .iter()
            .map(|scenario| StressScenarioReport {
                name: scenario.name.to_string(),
                fees_bps: scenario.fees_bps,
                breach_ticks: scenario.breach_ticks,
            })
            .collect(),
        circuit_breakers: circuit_scenarios
            .iter()
            .map(|scenario| CircuitBreakerScenarioReport {
                name: scenario.name.to_string(),
                loss_trigger_pct: scenario.loss_trigger_pct,
                pause_folds: scenario.pause_folds,
            })
            .collect(),
        blocks: report_blocks,
        circuit_blocks: circuit_report_blocks,
    };
    let report_path = run_dir.join("selected_oos_stress.json");
    write_json(report_path.clone(), &report)?;
    Ok(report_path)
}

pub fn equity_control_validate_run(
    run_id: &str,
    requested_pairs: &[String],
    select_symbols: &[String],
    report_symbols: &[String],
) -> Result<PathBuf> {
    if requested_pairs.is_empty() {
        anyhow::bail!("provide at least one --pairs item like strategy_4448_kama_ker:5m");
    }
    let selector_symbols = normalize_symbols(select_symbols.to_vec());
    if selector_symbols.is_empty() {
        anyhow::bail!("provide --select-symbols, for example BTCUSDT,SUIUSDT");
    }
    let report_symbols = {
        let requested = normalize_symbols(report_symbols.to_vec());
        if requested.is_empty() {
            selector_symbols.clone()
        } else {
            requested
        }
    };
    let mut load_symbols = selector_symbols.clone();
    for symbol in &report_symbols {
        if !load_symbols.contains(symbol) {
            load_symbols.push(symbol.clone());
        }
    }

    let run_dir = PathBuf::from(RUNS_ROOT).join(run_id);
    if !run_dir.exists() {
        anyhow::bail!("missing WFO run {run_id}");
    }
    let config = read_json::<WfoConfig>(run_dir.join("config.json"))?;
    let folds = read_csv::<Fold>(run_dir.join("folds.csv"))?;
    let block_map = read_strategy_oos_block_map(&run_dir)?;
    let target_blocks = requested_pairs
        .iter()
        .map(|pair| {
            let (indicator, timeframe) = parse_diagnostic_pair(pair)?;
            let key = (
                indicator.as_str().to_string(),
                timeframe.as_str().to_string(),
            );
            block_map
                .get(&key)
                .cloned()
                .with_context(|| format!("missing strategy OOS block for {pair}"))
        })
        .collect::<Result<Vec<_>>>()?;
    let all_data = load_wfo_data(&config)?;
    let data = all_data
        .into_iter()
        .filter(|(symbol, _)| load_symbols.contains(symbol))
        .collect::<Vec<_>>();
    for symbol in &load_symbols {
        if !data.iter().any(|(loaded, _)| loaded == symbol) {
            anyhow::bail!("missing data for {symbol}");
        }
    }
    let close_by_symbol = close_lookup(&data);
    let start_ms = folds
        .first()
        .map(|fold| fold.oos_start_ms)
        .unwrap_or(date_ms(config.start)?);
    let end_ms = folds
        .last()
        .map(|fold| fold.oos_end_ms)
        .unwrap_or(date_ms(config.end)?);

    let params_grid = equity_control_params_grid();
    let mut report_blocks = Vec::new();
    let mut symbol_csv_rows = Vec::new();
    let mut fold_csv_rows = Vec::new();

    for block in &target_blocks {
        eprintln!(
            "equity-control replay {} {} using selector symbols {}",
            block.indicator,
            block.timeframe,
            selector_symbols.join(",")
        );
        let trade_cache = equity_control_trade_cache(block, &config, &folds, &data)?;
        let mut selected_params_by_fold = BTreeMap::<usize, EquityControlParams>::new();

        for fold in &folds {
            let mut best: Option<(f64, EquityControlParams, ClosedTradeStats, ClosedTradeStats)> =
                None;
            for params in &params_grid {
                let mut is_base = Vec::new();
                let mut is_controlled = Vec::new();
                for symbol in &selector_symbols {
                    if let Some(selection) = selection_for_symbol_fold(block, symbol, fold.index)
                        && let Some(trades) =
                            trade_cache.get(&(symbol.clone(), selection.candidate_id))
                    {
                        let replay = equity_control_replay_fold(
                            trades,
                            fold,
                            *params,
                            config.fixed_notional,
                        );
                        is_base.extend(replay.is_base_trades);
                        is_controlled.extend(replay.is_controlled_trades);
                    }
                }
                let base_stats = closed_trade_stats(&is_base, config.fixed_notional);
                let controlled_stats = closed_trade_stats(&is_controlled, config.fixed_notional);
                let score = equity_control_selection_score(controlled_stats, base_stats);
                if best
                    .as_ref()
                    .is_none_or(|(best_score, _, _, _)| score > *best_score)
                {
                    best = Some((score, *params, base_stats, controlled_stats));
                }
            }
            let (_, selected_params, is_base_stats, is_controlled_stats) =
                best.with_context(|| {
                    format!("no equity-control params scored for fold {}", fold.index)
                })?;
            selected_params_by_fold.insert(fold.index, selected_params);

            let (selector_oos_base, selector_oos_controlled) =
                equity_control_fold_trades_for_symbols(
                    block,
                    &trade_cache,
                    fold,
                    &selector_symbols,
                    selected_params,
                    config.fixed_notional,
                );
            let oos_base_stats = closed_trade_stats(&selector_oos_base, config.fixed_notional);
            let oos_controlled_stats =
                closed_trade_stats(&selector_oos_controlled, config.fixed_notional);
            fold_csv_rows.push(EquityControlFoldCsvRow {
                indicator: block.indicator.clone(),
                timeframe: block.timeframe.clone(),
                fold_index: fold.index,
                oos_start_ms: fold.oos_start_ms,
                oos_end_ms: fold.oos_end_ms,
                ma_period: selected_params.ma_period,
                buffer_pct: selected_params.buffer_pct,
                below_ma_multiplier: selected_params.below_ma_multiplier,
                trade_during_warmup: selected_params.trade_during_warmup,
                selector_is_base_net_return_pct: is_base_stats.net_return_pct,
                selector_is_base_max_drawdown_pct: is_base_stats.max_drawdown_pct,
                selector_is_base_profit_factor: is_base_stats.profit_factor,
                selector_is_base_trades: is_base_stats.trades,
                selector_is_controlled_net_return_pct: is_controlled_stats.net_return_pct,
                selector_is_controlled_max_drawdown_pct: is_controlled_stats.max_drawdown_pct,
                selector_is_controlled_profit_factor: is_controlled_stats.profit_factor,
                selector_is_controlled_trades: is_controlled_stats.trades,
                selector_oos_base_net_return_pct: oos_base_stats.net_return_pct,
                selector_oos_base_max_drawdown_pct: oos_base_stats.max_drawdown_pct,
                selector_oos_base_profit_factor: oos_base_stats.profit_factor,
                selector_oos_base_trades: oos_base_stats.trades,
                selector_oos_controlled_net_return_pct: oos_controlled_stats.net_return_pct,
                selector_oos_controlled_max_drawdown_pct: oos_controlled_stats.max_drawdown_pct,
                selector_oos_controlled_profit_factor: oos_controlled_stats.profit_factor,
                selector_oos_controlled_trades: oos_controlled_stats.trades,
            });
        }

        let mut selector_base_trades = Vec::new();
        let mut selector_controlled_trades = Vec::new();
        let mut symbol_results = Vec::new();
        for symbol in &report_symbols {
            let mut base_trades = Vec::new();
            let mut controlled_trades = Vec::new();
            for fold in &folds {
                if let Some(params) = selected_params_by_fold.get(&fold.index).copied()
                    && let Some(selection) = selection_for_symbol_fold(block, symbol, fold.index)
                    && let Some(trades) = trade_cache.get(&(symbol.clone(), selection.candidate_id))
                {
                    let replay =
                        equity_control_replay_fold(trades, fold, params, config.fixed_notional);
                    base_trades.extend(replay.oos_base_trades);
                    controlled_trades.extend(replay.oos_controlled_trades);
                }
            }
            base_trades.sort_by_key(|trade| trade.exit_time_ms);
            controlled_trades.sort_by_key(|trade| trade.exit_time_ms);
            if selector_symbols.contains(symbol) {
                selector_base_trades.extend(base_trades.clone());
                selector_controlled_trades.extend(controlled_trades.clone());
            }
            let base = strategy_oos_metrics(
                &base_trades,
                config.fixed_notional,
                start_ms,
                end_ms,
                &close_by_symbol,
            );
            let controlled = strategy_oos_metrics(
                &controlled_trades,
                config.fixed_notional,
                start_ms,
                end_ms,
                &close_by_symbol,
            );
            let trades_retention_pct = pct(controlled.trades, base.trades);
            symbol_csv_rows.push(EquityControlSymbolCsvRow {
                indicator: block.indicator.clone(),
                timeframe: block.timeframe.clone(),
                selector_symbols: selector_symbols.join(","),
                symbol: symbol.clone(),
                base_net_return_pct: base.net_return_pct,
                base_max_drawdown_pct: base.max_drawdown_pct,
                base_profit_factor: base.profit_factor,
                base_trades: base.trades,
                controlled_net_return_pct: controlled.net_return_pct,
                controlled_max_drawdown_pct: controlled.max_drawdown_pct,
                controlled_profit_factor: controlled.profit_factor,
                controlled_trades: controlled.trades,
                net_delta_pct: controlled.net_return_pct - base.net_return_pct,
                drawdown_delta_pct: controlled.max_drawdown_pct - base.max_drawdown_pct,
                profit_factor_delta: controlled.profit_factor - base.profit_factor,
                trades_retention_pct,
            });
            symbol_results.push(EquityControlSymbolResult {
                symbol: symbol.clone(),
                base,
                controlled,
                trades_retention_pct,
            });
        }
        selector_base_trades.sort_by_key(|trade| trade.exit_time_ms);
        selector_controlled_trades.sort_by_key(|trade| trade.exit_time_ms);
        report_blocks.push(EquityControlValidationBlock {
            indicator: block.indicator.clone(),
            timeframe: block.timeframe.clone(),
            selector_base: strategy_oos_metrics(
                &selector_base_trades,
                config.fixed_notional,
                start_ms,
                end_ms,
                &close_by_symbol,
            ),
            selector_controlled: strategy_oos_metrics(
                &selector_controlled_trades,
                config.fixed_notional,
                start_ms,
                end_ms,
                &close_by_symbol,
            ),
            symbols: symbol_results,
        });
    }

    write_csv(
        run_dir.join("selected_oos_ecc_by_symbol.csv"),
        &symbol_csv_rows,
    )?;
    write_csv(run_dir.join("selected_oos_ecc_folds.csv"), &fold_csv_rows)?;
    let report = EquityControlValidationReport {
        run_id: config.run_id.clone(),
        generated_at: Utc::now(),
        selector_symbols,
        report_symbols,
        blocks: report_blocks,
    };
    let report_path = run_dir.join("selected_oos_ecc.json");
    write_json(report_path.clone(), &report)?;
    Ok(report_path)
}

fn stress_scenarios(base_fees_bps: f64) -> Vec<StressScenario> {
    vec![
        StressScenario {
            name: "baseline_replay",
            fees_bps: base_fees_bps,
            breach_ticks: 1,
        },
        StressScenario {
            name: "fees_5bps",
            fees_bps: 5.0,
            breach_ticks: 1,
        },
        StressScenario {
            name: "fees_10bps",
            fees_bps: 10.0,
            breach_ticks: 1,
        },
        StressScenario {
            name: "breach_2ticks",
            fees_bps: base_fees_bps,
            breach_ticks: 2,
        },
        StressScenario {
            name: "breach_3ticks",
            fees_bps: base_fees_bps,
            breach_ticks: 3,
        },
    ]
}

fn circuit_breaker_scenarios() -> Vec<CircuitBreakerScenario> {
    vec![
        CircuitBreakerScenario {
            name: "loss3_pause2",
            loss_trigger_pct: -3.0,
            pause_folds: 2,
        },
        CircuitBreakerScenario {
            name: "loss5_pause2",
            loss_trigger_pct: -5.0,
            pause_folds: 2,
        },
        CircuitBreakerScenario {
            name: "loss8_pause2",
            loss_trigger_pct: -8.0,
            pause_folds: 2,
        },
        CircuitBreakerScenario {
            name: "loss5_pause4",
            loss_trigger_pct: -5.0,
            pause_folds: 4,
        },
    ]
}

fn equity_control_params_grid() -> Vec<EquityControlParams> {
    let ma_periods = [5usize, 8, 13, 20, 34, 55, 89, 144];
    let buffers = [0.0, 0.25, 0.50, 1.0];
    let below_ma_multipliers = [0.0, 0.5, 1.0, 1.5, 2.0];
    let warmup_modes = [true, false];
    let mut out = Vec::new();
    for ma_period in ma_periods {
        for buffer_pct in buffers {
            for below_ma_multiplier in below_ma_multipliers {
                for trade_during_warmup in warmup_modes {
                    out.push(EquityControlParams {
                        ma_period,
                        buffer_pct,
                        below_ma_multiplier,
                        trade_during_warmup,
                    });
                }
            }
        }
    }
    out
}

fn equity_control_trade_cache(
    block: &StrategyOosBlock,
    config: &WfoConfig,
    folds: &[Fold],
    data: &[(String, Vec<OhlcvBar>)],
) -> Result<BTreeMap<(String, usize), Vec<Trade>>> {
    let mut cache = BTreeMap::new();
    let mut simulation_cache = SimulationCache::default();
    for (symbol, bars) in data {
        for selection in block
            .selected_candidates
            .iter()
            .filter(|selection| selection.symbol == *symbol)
        {
            let key = (symbol.clone(), selection.candidate_id);
            if cache.contains_key(&key) {
                continue;
            }
            let candidate = selection.candidate.as_ref().with_context(|| {
                format!(
                    "{} {} {symbol} fold {} selected candidate {} is missing parameters",
                    block.indicator, block.timeframe, selection.fold_index, selection.candidate_id
                )
            })?;
            let mut prepared = prepare_candidate_simulation(
                symbol,
                bars,
                candidate,
                config,
                &mut simulation_cache,
            )?;
            prepared.execution.fee_rate = config.fees_bps / 10_000.0;
            prepared.execution.breach_ticks = 1;
            let result = simulate_prepared_candidate(bars, &prepared, folds);
            cache.insert(key, result.trades);
        }
    }
    Ok(cache)
}

fn selection_for_symbol_fold<'a>(
    block: &'a StrategyOosBlock,
    symbol: &str,
    fold_index: usize,
) -> Option<&'a StrategyOosSelection> {
    block
        .selected_candidates
        .iter()
        .find(|selection| selection.symbol == symbol && selection.fold_index == fold_index)
}

fn equity_control_fold_trades_for_symbols(
    block: &StrategyOosBlock,
    trade_cache: &BTreeMap<(String, usize), Vec<Trade>>,
    fold: &Fold,
    symbols: &[String],
    params: EquityControlParams,
    fixed_notional: f64,
) -> (Vec<Trade>, Vec<Trade>) {
    let mut base = Vec::new();
    let mut controlled = Vec::new();
    for symbol in symbols {
        if let Some(selection) = selection_for_symbol_fold(block, symbol, fold.index)
            && let Some(trades) = trade_cache.get(&(symbol.clone(), selection.candidate_id))
        {
            let replay = equity_control_replay_fold(trades, fold, params, fixed_notional);
            base.extend(replay.oos_base_trades);
            controlled.extend(replay.oos_controlled_trades);
        }
    }
    base.sort_by_key(|trade| trade.exit_time_ms);
    controlled.sort_by_key(|trade| trade.exit_time_ms);
    (base, controlled)
}

fn equity_control_replay_fold(
    trades: &[Trade],
    fold: &Fold,
    params: EquityControlParams,
    fixed_notional: f64,
) -> EquityControlFoldReplay {
    let mut ordered = trades
        .iter()
        .filter(|trade| trade_fully_inside_window(trade, fold.is_start_ms, fold.oos_end_ms))
        .cloned()
        .collect::<Vec<_>>();
    ordered.sort_by_key(|trade| (trade.entry_time_ms, trade.exit_time_ms));

    let mut shadow_equity = 0.0;
    let mut shadow_balances = Vec::<f64>::new();
    let mut replay = EquityControlFoldReplay {
        is_base_trades: Vec::new(),
        is_controlled_trades: Vec::new(),
        oos_base_trades: Vec::new(),
        oos_controlled_trades: Vec::new(),
    };

    for trade in ordered {
        let in_is = trade_fully_inside_window(&trade, fold.is_start_ms, fold.is_end_ms);
        let in_oos = trade_fully_inside_window(&trade, fold.oos_start_ms, fold.oos_end_ms);
        if !in_is && !in_oos {
            continue;
        }
        let live_multiplier = equity_control_trade_multiplier(
            shadow_equity,
            &shadow_balances,
            params,
            fixed_notional,
        );
        if in_is {
            replay.is_base_trades.push(trade.clone());
            if live_multiplier > 0.0 {
                replay
                    .is_controlled_trades
                    .push(scale_trade(&trade, live_multiplier));
            }
        } else if in_oos {
            replay.oos_base_trades.push(trade.clone());
            if live_multiplier > 0.0 {
                replay
                    .oos_controlled_trades
                    .push(scale_trade(&trade, live_multiplier));
            }
        }
        shadow_equity += trade.pnl;
        shadow_balances.push(shadow_equity);
    }
    replay
}

fn equity_control_trade_multiplier(
    shadow_equity: f64,
    shadow_balances: &[f64],
    params: EquityControlParams,
    fixed_notional: f64,
) -> f64 {
    if shadow_balances.len() < params.ma_period {
        return if params.trade_during_warmup { 1.0 } else { 0.0 };
    }
    let start = shadow_balances.len() - params.ma_period;
    let average = shadow_balances[start..].iter().sum::<f64>() / params.ma_period as f64;
    let buffer = fixed_notional.max(1.0) * params.buffer_pct / 100.0;
    if shadow_equity > average + buffer {
        1.0
    } else {
        params.below_ma_multiplier
    }
}

fn scale_trade(trade: &Trade, multiplier: f64) -> Trade {
    let mut scaled = trade.clone();
    scaled.quantity *= multiplier;
    scaled.pnl *= multiplier;
    scaled.return_pct *= multiplier;
    scaled
}

fn closed_trade_stats(trades: &[Trade], fixed_notional: f64) -> ClosedTradeStats {
    let mut ordered = trades.to_vec();
    ordered.sort_by_key(|trade| trade.exit_time_ms);
    let mut equity = 0.0;
    let mut peak = 0.0;
    let mut max_drawdown = 0.0;
    let mut winning_pnl = 0.0;
    let mut losing_pnl = 0.0;
    for trade in &ordered {
        if trade.pnl > 0.0 {
            winning_pnl += trade.pnl;
        } else if trade.pnl < 0.0 {
            losing_pnl += trade.pnl.abs();
        }
        equity += trade.pnl;
        if equity > peak {
            peak = equity;
        }
        let drawdown = peak - equity;
        if drawdown > max_drawdown {
            max_drawdown = drawdown;
        }
    }
    ClosedTradeStats {
        net_return_pct: equity / fixed_notional.max(1.0) * 100.0,
        max_drawdown_pct: max_drawdown / fixed_notional.max(1.0) * 100.0,
        profit_factor: if losing_pnl > 0.0 {
            winning_pnl / losing_pnl
        } else if winning_pnl > 0.0 {
            999.0
        } else {
            0.0
        },
        trades: ordered.len(),
    }
}

fn equity_control_selection_score(controlled: ClosedTradeStats, base: ClosedTradeStats) -> f64 {
    if base.trades == 0 || controlled.trades < (base.trades / 4).max(4) {
        return -1_500.0;
    }
    if controlled.net_return_pct <= 0.0 || controlled.profit_factor < 1.0 {
        return -1_200.0 - controlled.net_return_pct.abs();
    }
    let drawdown_score = controlled.net_return_pct / controlled.max_drawdown_pct.max(0.5);
    let pf_score = controlled.profit_factor.max(0.01).ln().clamp(-1.0, 1.5) * 0.35;
    let activity_score = (controlled.trades as f64 + 1.0).ln() * 0.03;
    let retention = if base.net_return_pct > 0.0 {
        (controlled.net_return_pct / base.net_return_pct).clamp(0.0, 2.0)
    } else {
        1.0
    };
    drawdown_score + pf_score + activity_score + 0.15 * retention
}

fn stress_target_blocks(
    block_map: &BTreeMap<(String, String), StrategyOosBlock>,
    requested_pairs: &[String],
    min_profit_factor: f64,
) -> Result<Vec<StrategyOosBlock>> {
    let mut blocks = if requested_pairs.is_empty() {
        block_map
            .values()
            .filter(|block| block.status == "complete")
            .filter(|block| {
                block.portfolio.as_ref().is_some_and(|metrics| {
                    candidate_acceptance(metrics, &block.symbols, min_profit_factor)
                })
            })
            .cloned()
            .collect::<Vec<_>>()
    } else {
        requested_pairs
            .iter()
            .map(|pair| {
                let (indicator, timeframe) = parse_diagnostic_pair(pair)?;
                let key = (
                    indicator.as_str().to_string(),
                    timeframe.as_str().to_string(),
                );
                block_map
                    .get(&key)
                    .cloned()
                    .with_context(|| format!("missing strategy OOS block for {pair}"))
            })
            .collect::<Result<Vec<_>>>()?
    };
    let rejected = blocks
        .iter()
        .filter_map(|block| match block.portfolio.as_ref() {
            Some(metrics) if candidate_acceptance(metrics, &block.symbols, min_profit_factor) => {
                None
            }
            Some(metrics) => Some(format!(
                "{} {} has {} OOS trades, {:.2}% net, PF {:.3}, {:.2}% active weeks, {:.2}% entry days, {}d max idle gap; candidate gate requires >= {} trades, positive net, PF >= {:.3}, active weeks >= {:.1}%, entry days >= {:.1}%, max idle gap <= {}d, and every symbol passing the same participation floor",
                block.indicator,
                block.timeframe,
                metrics.trades,
                metrics.net_return_pct,
                metrics.profit_factor,
                metrics.entry_week_pct,
                metrics.entry_day_pct,
                metrics.longest_no_entry_gap_days,
                MIN_CANDIDATE_OOS_TRADES,
                min_profit_factor,
                MIN_CANDIDATE_ENTRY_WEEK_PCT,
                MIN_CANDIDATE_ENTRY_DAY_PCT,
                MAX_CANDIDATE_NO_ENTRY_GAP_DAYS
            )),
            None => Some(format!(
                "{} {} has no completed portfolio metrics",
                block.indicator, block.timeframe
            )),
        })
        .collect::<Vec<_>>();
    if !rejected.is_empty() {
        anyhow::bail!("{}", rejected.join("; "));
    }
    blocks.sort_by_key(|block| {
        (
            indicator_rank(&block.indicator),
            timeframe_rank(&block.timeframe),
        )
    });
    Ok(blocks)
}

fn candidate_acceptance(
    metrics: &StrategyOosMetrics,
    symbols: &[StrategyOosSymbolResult],
    min_profit_factor: f64,
) -> bool {
    metrics.trades >= MIN_CANDIDATE_OOS_TRADES
        && metrics.net_return_pct > 0.0
        && metrics.profit_factor >= min_profit_factor
        && metrics.entry_day_pct >= MIN_CANDIDATE_ENTRY_DAY_PCT
        && metrics.entry_week_pct >= MIN_CANDIDATE_ENTRY_WEEK_PCT
        && metrics.longest_no_entry_gap_days <= MAX_CANDIDATE_NO_ENTRY_GAP_DAYS
        && symbols.iter().all(|symbol| {
            symbol.metrics.entry_day_pct >= MIN_CANDIDATE_ENTRY_DAY_PCT
                && symbol.metrics.entry_week_pct >= MIN_CANDIDATE_ENTRY_WEEK_PCT
                && symbol.metrics.longest_no_entry_gap_days <= MAX_CANDIDATE_NO_ENTRY_GAP_DAYS
        })
}

fn refresh_strategy_candidate_gate(block: &mut StrategyOosBlock, min_profit_factor: f64) {
    block.candidate_gate =
        strategy_candidate_gate(block.portfolio.as_ref(), &block.symbols, min_profit_factor);
}

fn strategy_candidate_gate(
    metrics: Option<&StrategyOosMetrics>,
    symbols: &[StrategyOosSymbolResult],
    min_profit_factor: f64,
) -> StrategyCandidateGate {
    let Some(metrics) = metrics else {
        return StrategyCandidateGate {
            min_profit_factor,
            ..StrategyCandidateGate::default()
        };
    };
    let pass_min_trades = metrics.trades >= MIN_CANDIDATE_OOS_TRADES;
    let pass_net_positive = metrics.net_return_pct > 0.0;
    let pass_profit_factor = metrics.profit_factor >= min_profit_factor;
    let pass_entry_days = metrics.entry_day_pct >= MIN_CANDIDATE_ENTRY_DAY_PCT;
    let pass_entry_weeks = metrics.entry_week_pct >= MIN_CANDIDATE_ENTRY_WEEK_PCT;
    let pass_no_entry_gap = metrics.longest_no_entry_gap_days <= MAX_CANDIDATE_NO_ENTRY_GAP_DAYS;
    let symbol_failures = strategy_symbol_participation_failures(symbols);
    let pass_symbol_participation = symbol_failures.is_empty();
    let pass_candidate = pass_min_trades
        && pass_net_positive
        && pass_profit_factor
        && pass_entry_days
        && pass_entry_weeks
        && pass_no_entry_gap
        && pass_symbol_participation;
    let mut reasons = Vec::new();
    if !pass_min_trades {
        reasons.push(format!(
            "{} OOS trades < {} minimum",
            metrics.trades, MIN_CANDIDATE_OOS_TRADES
        ));
    }
    if !pass_net_positive {
        reasons.push(format!("OOS net {:.2}% <= 0", metrics.net_return_pct));
    }
    if !pass_profit_factor {
        reasons.push(format!(
            "PF {:.3} < {:.3} minimum",
            metrics.profit_factor, min_profit_factor
        ));
    }
    if !pass_entry_days {
        reasons.push(format!(
            "portfolio entry days {:.2}% < {:.2}% minimum ({} no-entry days / {} OOS days)",
            metrics.entry_day_pct,
            MIN_CANDIDATE_ENTRY_DAY_PCT,
            metrics.no_entry_days,
            metrics.total_oos_days
        ));
    }
    if !pass_entry_weeks {
        reasons.push(format!(
            "portfolio active weeks {:.2}% < {:.2}% minimum ({} / {})",
            metrics.entry_week_pct,
            MIN_CANDIDATE_ENTRY_WEEK_PCT,
            metrics.entry_weeks,
            metrics.total_oos_weeks
        ));
    }
    if !pass_no_entry_gap {
        reasons.push(format!(
            "portfolio max no-entry gap {}d > {}d",
            metrics.longest_no_entry_gap_days, MAX_CANDIDATE_NO_ENTRY_GAP_DAYS
        ));
    }
    if !pass_symbol_participation {
        reasons.push(format!(
            "symbol participation failed: {}",
            symbol_failures.join("; ")
        ));
    }
    StrategyCandidateGate {
        min_oos_trades: MIN_CANDIDATE_OOS_TRADES,
        min_profit_factor,
        min_entry_day_pct: MIN_CANDIDATE_ENTRY_DAY_PCT,
        min_entry_week_pct: MIN_CANDIDATE_ENTRY_WEEK_PCT,
        max_no_entry_gap_days: MAX_CANDIDATE_NO_ENTRY_GAP_DAYS,
        pass_min_trades,
        pass_net_positive,
        pass_profit_factor,
        pass_entry_days,
        pass_entry_weeks,
        pass_no_entry_gap,
        pass_symbol_participation,
        pass_candidate,
        status: if pass_candidate {
            "accepted".to_string()
        } else {
            "rejected".to_string()
        },
        reason: if pass_candidate {
            format!(
                "accepted: {} OOS trades, positive net, PF >= {:.3}, active weeks >= {:.1}%, entry days >= {:.1}%, max no-entry gap <= {}d, all symbols pass participation",
                metrics.trades,
                min_profit_factor,
                MIN_CANDIDATE_ENTRY_WEEK_PCT,
                MIN_CANDIDATE_ENTRY_DAY_PCT,
                MAX_CANDIDATE_NO_ENTRY_GAP_DAYS
            )
        } else {
            reasons.join("; ")
        },
    }
}

fn strategy_symbol_participation_failures(symbols: &[StrategyOosSymbolResult]) -> Vec<String> {
    symbols
        .iter()
        .filter(|symbol| {
            symbol.metrics.entry_day_pct < MIN_CANDIDATE_ENTRY_DAY_PCT
                || symbol.metrics.entry_week_pct < MIN_CANDIDATE_ENTRY_WEEK_PCT
                || symbol.metrics.longest_no_entry_gap_days > MAX_CANDIDATE_NO_ENTRY_GAP_DAYS
        })
        .map(|symbol| {
            format!(
                "{} entry_days {:.2}% active_weeks {:.2}% max_gap {}d",
                symbol.symbol,
                symbol.metrics.entry_day_pct,
                symbol.metrics.entry_week_pct,
                symbol.metrics.longest_no_entry_gap_days
            )
        })
        .collect()
}

fn load_wfo_data(config: &WfoConfig) -> Result<Vec<(String, Vec<OhlcvBar>)>> {
    let symbols = if !config.symbols.is_empty() {
        config.symbols.clone()
    } else {
        preset_symbols(&config.preset)?
    };
    let store = KlineStore::from_env()?;
    let mut data = Vec::new();
    for symbol in &symbols {
        let rows = store
            .load_range(symbol, config.start, config.end)
            .unwrap_or_default()
            .iter()
            .map(OhlcvBar::from)
            .collect::<Vec<_>>();
        if rows.is_empty() {
            data.push((
                symbol.clone(),
                synthetic_market(symbol, date_ms(config.start)?, synthetic_row_count(config)?),
            ));
        } else {
            data.push((symbol.clone(), rows));
        }
    }
    Ok(data)
}

struct StressReplayBlock {
    metrics: StrategyOosMetrics,
    symbols: Vec<StrategyOosSymbolResult>,
    fold_trades: Vec<StressFoldTrades>,
}

#[derive(Debug, Clone)]
struct StressFoldTrades {
    symbol: String,
    fold_index: usize,
    trades: Vec<Trade>,
}

fn stress_replay_block_all_scenarios(
    block: &StrategyOosBlock,
    scenarios: &[StressScenario],
    config: &WfoConfig,
    folds: &[Fold],
    data: &[(String, Vec<OhlcvBar>)],
    oos_window_ms: (i64, i64),
    close_by_symbol: &BTreeMap<String, BTreeMap<i64, f64>>,
) -> Result<Vec<StressReplayBlock>> {
    let mut portfolio_trades = vec![Vec::<Trade>::new(); scenarios.len()];
    let mut symbol_results = vec![Vec::<StrategyOosSymbolResult>::new(); scenarios.len()];
    let mut fold_trades_by_scenario = vec![Vec::<StressFoldTrades>::new(); scenarios.len()];
    for (symbol, bars) in data {
        let selections = block
            .selected_candidates
            .iter()
            .filter(|selection| selection.symbol == *symbol)
            .collect::<Vec<_>>();
        let mut symbol_trades = vec![Vec::<Trade>::new(); scenarios.len()];
        if !selections.is_empty() {
            let mut simulation_cache = SimulationCache::default();
            let mut trade_cache = BTreeMap::<(usize, usize), Vec<Trade>>::new();
            for selection in selections {
                if !trade_cache.contains_key(&(selection.candidate_id, 0)) {
                    let candidate = selection.candidate.as_ref().with_context(|| {
                        format!(
                            "{} {} {symbol} fold {} selected candidate {} is missing parameters",
                            block.indicator,
                            block.timeframe,
                            selection.fold_index,
                            selection.candidate_id
                        )
                    })?;
                    let mut prepared = prepare_candidate_simulation(
                        symbol,
                        bars,
                        candidate,
                        config,
                        &mut simulation_cache,
                    )?;
                    for (scenario_index, scenario) in scenarios.iter().enumerate() {
                        prepared.execution.fee_rate = scenario.fees_bps / 10_000.0;
                        prepared.execution.breach_ticks = scenario.breach_ticks;
                        let result = simulate_prepared_candidate(bars, &prepared, folds);
                        trade_cache.insert((selection.candidate_id, scenario_index), result.trades);
                    }
                }
                let fold = folds
                    .iter()
                    .find(|fold| fold.index == selection.fold_index)
                    .with_context(|| {
                        format!(
                            "{} {} {symbol}: missing fold {}",
                            block.indicator, block.timeframe, selection.fold_index
                        )
                    })?;
                for (scenario_index, scenario_trades) in symbol_trades.iter_mut().enumerate() {
                    if let Some(trades) = trade_cache.get(&(selection.candidate_id, scenario_index))
                    {
                        let selected_trades = trades
                            .iter()
                            .filter(|trade| {
                                trade_fully_inside_window(trade, fold.oos_start_ms, fold.oos_end_ms)
                            })
                            .cloned()
                            .collect::<Vec<_>>();
                        scenario_trades.extend(selected_trades.clone());
                        fold_trades_by_scenario[scenario_index].push(StressFoldTrades {
                            symbol: symbol.clone(),
                            fold_index: fold.index,
                            trades: selected_trades,
                        });
                    }
                }
            }
        }
        for scenario_index in 0..scenarios.len() {
            symbol_trades[scenario_index].sort_by_key(|trade| trade.exit_time_ms);
            portfolio_trades[scenario_index].extend(symbol_trades[scenario_index].clone());
            symbol_results[scenario_index].push(StrategyOosSymbolResult {
                symbol: symbol.clone(),
                metrics: strategy_oos_metrics(
                    &symbol_trades[scenario_index],
                    config.fixed_notional,
                    oos_window_ms.0,
                    oos_window_ms.1,
                    close_by_symbol,
                ),
            });
        }
    }
    Ok(portfolio_trades
        .into_iter()
        .zip(symbol_results)
        .zip(fold_trades_by_scenario)
        .map(|((mut trades, mut symbols), mut fold_trades)| {
            trades.sort_by_key(|trade| trade.exit_time_ms);
            symbols.sort_by(|left, right| left.symbol.cmp(&right.symbol));
            fold_trades.sort_by(|left, right| {
                left.symbol
                    .cmp(&right.symbol)
                    .then(left.fold_index.cmp(&right.fold_index))
            });
            StressReplayBlock {
                metrics: strategy_oos_metrics(
                    &trades,
                    config.fixed_notional,
                    oos_window_ms.0,
                    oos_window_ms.1,
                    close_by_symbol,
                ),
                symbols,
                fold_trades,
            }
        })
        .collect())
}

fn apply_circuit_breaker_to_replay(
    replay: &StressReplayBlock,
    circuit: &CircuitBreakerScenario,
    fixed_notional: f64,
    oos_window_ms: (i64, i64),
    close_by_symbol: &BTreeMap<String, BTreeMap<i64, f64>>,
) -> StressReplayBlock {
    let mut by_symbol = BTreeMap::<String, Vec<&StressFoldTrades>>::new();
    for fold in &replay.fold_trades {
        by_symbol.entry(fold.symbol.clone()).or_default().push(fold);
    }

    let mut portfolio_trades = Vec::new();
    let mut symbol_results = Vec::new();
    let mut kept_folds = Vec::new();
    for symbol in replay.symbols.iter().map(|row| row.symbol.clone()) {
        let mut paused_until_fold = 0usize;
        let mut symbol_trades = Vec::new();
        if let Some(folds) = by_symbol.get_mut(&symbol) {
            folds.sort_by_key(|fold| fold.fold_index);
            for fold in folds.iter().copied() {
                if fold.fold_index < paused_until_fold {
                    continue;
                }
                let fold_pnl = fold.trades.iter().map(|trade| trade.pnl).sum::<f64>();
                let fold_net_return_pct = fold_pnl / fixed_notional.max(1.0) * 100.0;
                symbol_trades.extend(fold.trades.clone());
                kept_folds.push(fold.clone());
                if !fold.trades.is_empty() && fold_net_return_pct <= circuit.loss_trigger_pct {
                    paused_until_fold = fold.fold_index + 1 + circuit.pause_folds;
                }
            }
        }
        symbol_trades.sort_by_key(|trade| trade.exit_time_ms);
        portfolio_trades.extend(symbol_trades.clone());
        symbol_results.push(StrategyOosSymbolResult {
            symbol,
            metrics: strategy_oos_metrics(
                &symbol_trades,
                fixed_notional,
                oos_window_ms.0,
                oos_window_ms.1,
                close_by_symbol,
            ),
        });
    }
    portfolio_trades.sort_by_key(|trade| trade.exit_time_ms);
    symbol_results.sort_by(|left, right| left.symbol.cmp(&right.symbol));
    kept_folds.sort_by(|left, right| {
        left.symbol
            .cmp(&right.symbol)
            .then(left.fold_index.cmp(&right.fold_index))
    });
    StressReplayBlock {
        metrics: strategy_oos_metrics(
            &portfolio_trades,
            fixed_notional,
            oos_window_ms.0,
            oos_window_ms.1,
            close_by_symbol,
        ),
        symbols: symbol_results,
        fold_trades: kept_folds,
    }
}

pub fn diagnose_run_strategies(
    run_id: &str,
    requested_pairs: &[String],
) -> Result<Vec<StrategyDiagnosticsReport>> {
    if requested_pairs.is_empty() {
        anyhow::bail!("provide at least one --pairs item like super_smoother:15m");
    }
    let run_dir = PathBuf::from(RUNS_ROOT).join(run_id);
    if !run_dir.exists() {
        anyhow::bail!("missing WFO run {run_id}");
    }
    let config = read_json::<WfoConfig>(run_dir.join("config.json"))?;
    let folds = read_csv::<Fold>(run_dir.join("folds.csv"))?;
    let candidates = read_csv::<Candidate>(run_dir.join("candidates.csv"))?;
    let pairs = requested_pairs
        .iter()
        .map(|pair| parse_diagnostic_pair(pair))
        .collect::<Result<Vec<_>>>()?;
    let symbols = if !config.symbols.is_empty() {
        config.symbols.clone()
    } else {
        preset_symbols(&config.preset)?
    };
    let store = KlineStore::from_env()?;
    let mut data = Vec::new();
    for symbol in &symbols {
        let rows = store
            .load_range(symbol, config.start, config.end)
            .unwrap_or_default()
            .iter()
            .map(OhlcvBar::from)
            .collect::<Vec<_>>();
        if rows.is_empty() {
            data.push((
                symbol.clone(),
                synthetic_market(
                    symbol,
                    date_ms(config.start)?,
                    synthetic_row_count(&config)?,
                ),
            ));
        } else {
            data.push((symbol.clone(), rows));
        }
    }

    pairs
        .into_iter()
        .map(|(indicator, timeframe)| {
            diagnose_strategy_pair(
                &run_dir,
                &config,
                &folds,
                &candidates,
                &data,
                indicator,
                timeframe,
            )
        })
        .collect()
}

fn diagnose_strategy_pair(
    run_dir: &Path,
    config: &WfoConfig,
    folds: &[Fold],
    all_candidates: &[Candidate],
    data: &[(String, Vec<OhlcvBar>)],
    indicator: IndicatorKind,
    timeframe: Timeframe,
) -> Result<StrategyDiagnosticsReport> {
    let candidates = all_candidates
        .iter()
        .filter(|candidate| candidate.indicator == indicator && candidate.timeframe == timeframe)
        .cloned()
        .collect::<Vec<_>>();
    if candidates.is_empty() {
        anyhow::bail!(
            "run {} has no candidates for {} {}",
            config.run_id,
            indicator.as_str(),
            timeframe.as_str()
        );
    }

    let block = read_strategy_block_if_exists(run_dir, indicator, timeframe)?;
    let selected_by_symbol = selected_counts_by_symbol(block.as_ref());
    let selected_candidates = top_selected_candidate_counts(block.as_ref());
    let oos_by_symbol = block
        .as_ref()
        .map(|block| {
            block
                .symbols
                .iter()
                .map(|row| (row.symbol.clone(), diagnostic_oos_metrics(&row.metrics)))
                .collect::<BTreeMap<_, _>>()
        })
        .unwrap_or_default();
    let symbol_outputs = data
        .par_iter()
        .map(|(symbol, bars)| {
            diagnose_strategy_symbol(
                config,
                folds,
                &candidates,
                symbol,
                bars,
                selected_by_symbol.get(symbol).copied().unwrap_or_default(),
                oos_by_symbol.get(symbol).cloned(),
            )
        })
        .collect::<Result<Vec<_>>>()?;

    let mut counts = DiagnosticCounts::default();
    let mut trades = Vec::new();
    let mut pfs = Vec::new();
    let mut symbol_reports = Vec::new();
    for output in symbol_outputs {
        merge_diagnostic_counts(&mut counts, &output.report.counts);
        trades.extend(output.trades_per_fold);
        pfs.extend(output.profit_factors_when_trade_count_ok);
        symbol_reports.push(output.report);
    }
    let selected_symbol_folds = symbol_reports
        .iter()
        .map(|report| report.selected_symbol_folds)
        .sum::<usize>();
    let symbol_fold_slots = data.len() * folds.len();
    let (trade_band_min, trade_band_max) = folds
        .first()
        .map(|fold| trade_count_band(timeframe, fold))
        .unwrap_or_default();

    Ok(StrategyDiagnosticsReport {
        run_id: config.run_id.clone(),
        indicator: indicator.as_str().to_string(),
        timeframe: timeframe.as_str().to_string(),
        candidates: candidates.len(),
        symbols: data.len(),
        folds: folds.len(),
        fold_evaluations: candidates.len() * data.len() * folds.len(),
        selected_symbol_folds,
        selected_coverage_pct: pct(selected_symbol_folds, symbol_fold_slots),
        trade_band_min,
        trade_band_max,
        counts,
        trades_per_fold: distribution_from_values(&trades),
        profit_factor_when_trade_count_ok: distribution_from_values(&pfs),
        portfolio: block
            .as_ref()
            .and_then(|block| block.portfolio.as_ref().map(diagnostic_oos_metrics)),
        by_symbol: symbol_reports,
        top_selected_candidates: selected_candidates,
    })
}

fn diagnose_strategy_symbol(
    config: &WfoConfig,
    folds: &[Fold],
    candidates: &[Candidate],
    symbol: &str,
    bars: &[OhlcvBar],
    selected_symbol_folds: usize,
    oos: Option<DiagnosticOosMetrics>,
) -> Result<SymbolDiagnosticsOutput> {
    let mut cache = SimulationCache::default();
    let mut counts = DiagnosticCounts::default();
    let mut trades_per_fold = Vec::with_capacity(candidates.len() * folds.len());
    let mut profit_factors = Vec::new();
    for candidate in candidates {
        if !candidate_allowed_for_symbol(config.strategy_set.as_deref(), symbol, candidate) {
            continue;
        }
        let prepared = prepare_candidate_simulation(symbol, bars, candidate, config, &mut cache)?;
        let result = simulate_prepared_candidate(bars, &prepared, folds);
        for (fold_pos, fold) in folds.iter().enumerate() {
            let fold_trades = selection_trades_for_fold(&result.trades, config, fold);
            let fold_diagnostics = result
                .fold_diagnostics
                .get(fold_pos)
                .cloned()
                .unwrap_or_default();
            let score = score_trades_with_diagnostics(
                result.symbol.as_str(),
                &result.candidate,
                fold.index,
                fold,
                &fold_trades,
                config,
                &fold_diagnostics,
            );
            classify_score(&score, &mut counts);
            trades_per_fold.push(score.trades as f64);
            if score.trades >= score.min_trades && score.trades <= score.max_trades {
                profit_factors.push(score.profit_factor.min(999.0));
            }
        }
    }
    let fold_evaluations = trades_per_fold.len();
    let report = SymbolDiagnosticsReport {
        symbol: symbol.to_string(),
        fold_evaluations,
        selected_symbol_folds,
        selected_coverage_pct: pct(selected_symbol_folds, folds.len()),
        counts,
        trades_per_fold: distribution_from_values(&trades_per_fold),
        profit_factor_when_trade_count_ok: distribution_from_values(&profit_factors),
        oos,
    };
    Ok(SymbolDiagnosticsOutput {
        report,
        trades_per_fold,
        profit_factors_when_trade_count_ok: profit_factors,
    })
}

fn diagnostic_oos_metrics(metrics: &StrategyOosMetrics) -> DiagnosticOosMetrics {
    DiagnosticOosMetrics {
        net_return_pct: metrics.net_return_pct,
        max_drawdown_pct: metrics.max_drawdown_pct,
        trades: metrics.trades,
        win_rate: metrics.win_rate,
        profit_factor: metrics.profit_factor,
        sharpe: metrics.sharpe,
    }
}

fn classify_score(score: &CandidateScore, counts: &mut DiagnosticCounts) {
    if score.trades == 0 {
        counts.zero_trades += 1;
    }
    if score.trades < score.min_trades {
        counts.too_sparse += 1;
    } else if score.trades > score.max_trades {
        counts.too_active += 1;
    } else if score.quality_fit == BAD_EXIT_GEOMETRY_REJECTION {
        counts.bad_exit_geometry += 1;
    } else if score.profit_factor < score.min_profit_factor {
        counts.low_profit_factor += 1;
    } else if score.average_trade_return_pct < score.min_average_trade_return_pct {
        counts.low_average_trade_edge += 1;
    } else if score.edge_t_stat < score.min_edge_t_stat {
        counts.low_edge_confidence += 1;
    } else if score.entry_attempts >= score.min_trades.max(25)
        && score.fill_rate_pct < score.min_fill_rate_pct
    {
        counts.low_fill_rate += 1;
    } else if candidate_score_has_low_participation(score) {
        counts.low_participation += 1;
    } else if score.net_return_pct <= 0.0 {
        counts.eligible_nonpositive_net += 1;
        counts.eligible_total += 1;
    } else {
        counts.eligible_positive_net += 1;
        counts.eligible_total += 1;
    }
}

fn parse_diagnostic_pair(pair: &str) -> Result<(IndicatorKind, Timeframe)> {
    let normalized = pair.trim();
    let (indicator, timeframe) = normalized
        .split_once(':')
        .or_else(|| normalized.split_once("__"))
        .with_context(|| format!("invalid pair {pair}; use indicator:timeframe"))?;
    Ok((
        parse_indicator_kind(indicator)?,
        parse_timeframe_kind(timeframe)?,
    ))
}

fn parse_indicator_kind(value: &str) -> Result<IndicatorKind> {
    let normalized = value.trim().to_lowercase();
    IndicatorKind::CATALOG
        .into_iter()
        .find(|indicator| indicator.as_str() == normalized)
        .with_context(|| format!("unknown indicator {value}"))
}

fn parse_timeframe_kind(value: &str) -> Result<Timeframe> {
    let normalized = value.trim().to_lowercase();
    Timeframe::ALL
        .into_iter()
        .find(|timeframe| timeframe.as_str() == normalized)
        .with_context(|| format!("unknown timeframe {value}"))
}

fn read_strategy_block_if_exists(
    run_dir: &Path,
    indicator: IndicatorKind,
    timeframe: Timeframe,
) -> Result<Option<StrategyOosBlock>> {
    let path = run_dir.join(STRATEGY_OOS_BLOCKS_DIR).join(format!(
        "{}__{}.json",
        indicator.as_str(),
        timeframe.as_str()
    ));
    if path.exists() {
        read_json(path).map(Some)
    } else {
        Ok(None)
    }
}

fn selected_counts_by_symbol(block: Option<&StrategyOosBlock>) -> BTreeMap<String, usize> {
    let mut out = BTreeMap::new();
    if let Some(block) = block {
        for selection in &block.selected_candidates {
            *out.entry(selection.symbol.clone()).or_default() += 1;
        }
    }
    out
}

fn top_selected_candidate_counts(
    block: Option<&StrategyOosBlock>,
) -> Vec<SelectedCandidateDiagnostics> {
    let mut counts = BTreeMap::<usize, (usize, Option<Candidate>)>::new();
    if let Some(block) = block {
        for selection in &block.selected_candidates {
            let entry = counts
                .entry(selection.candidate_id)
                .or_insert_with(|| (0, selection.candidate.clone()));
            entry.0 += 1;
            if entry.1.is_none() {
                entry.1 = selection.candidate.clone();
            }
        }
    }
    let mut out = counts
        .into_iter()
        .map(
            |(candidate_id, (selections, candidate))| SelectedCandidateDiagnostics {
                candidate_id,
                selections,
                candidate,
            },
        )
        .collect::<Vec<_>>();
    out.sort_by_key(|row| std::cmp::Reverse(row.selections));
    out.truncate(5);
    out
}

fn merge_diagnostic_counts(total: &mut DiagnosticCounts, next: &DiagnosticCounts) {
    total.zero_trades += next.zero_trades;
    total.too_sparse += next.too_sparse;
    total.too_active += next.too_active;
    total.bad_exit_geometry += next.bad_exit_geometry;
    total.low_profit_factor += next.low_profit_factor;
    total.low_average_trade_edge += next.low_average_trade_edge;
    total.low_edge_confidence += next.low_edge_confidence;
    total.low_fill_rate += next.low_fill_rate;
    total.low_participation += next.low_participation;
    total.eligible_nonpositive_net += next.eligible_nonpositive_net;
    total.eligible_positive_net += next.eligible_positive_net;
    total.eligible_total += next.eligible_total;
}

fn distribution_from_values(values: &[f64]) -> DiagnosticDistribution {
    if values.is_empty() {
        return DiagnosticDistribution::default();
    }
    let mut sorted = values.to_vec();
    sorted.sort_by(|a, b| a.total_cmp(b));
    DiagnosticDistribution {
        mean: values.iter().sum::<f64>() / values.len() as f64,
        p50: percentile_sorted(&sorted, 0.50),
        p90: percentile_sorted(&sorted, 0.90),
        max: *sorted.last().unwrap_or(&0.0),
    }
}

fn percentile_sorted(sorted: &[f64], percentile: f64) -> f64 {
    if sorted.is_empty() {
        return 0.0;
    }
    let idx = ((sorted.len() - 1) as f64 * percentile)
        .round()
        .clamp(0.0, (sorted.len() - 1) as f64) as usize;
    sorted[idx]
}

fn pct(numerator: usize, denominator: usize) -> f64 {
    if denominator == 0 {
        0.0
    } else {
        numerator as f64 / denominator as f64 * 100.0
    }
}

fn merge_strategy_oos_blocks_with_progress(
    mut rows: Vec<StrategyRow>,
    mut blocks: BTreeMap<(String, String), StrategyOosBlock>,
    min_profit_factor: f64,
) -> Vec<StrategyOosBlock> {
    rows.sort_by_key(|row| {
        (
            indicator_rank(&row.indicator),
            timeframe_rank(&row.timeframe),
        )
    });
    rows.into_iter()
        .filter(|row| row.runnable && row.parameter_candidates > 0)
        .map(|row| {
            let key = (row.indicator.clone(), row.timeframe.clone());
            let mut block = blocks.remove(&key).unwrap_or_else(|| StrategyOosBlock {
                indicator: row.indicator.clone(),
                timeframe: row.timeframe.clone(),
                status: row.status.clone(),
                progress_pct: row.progress_pct,
                progress_label: row.progress_label.clone(),
                parameter_candidates: row.parameter_candidates,
                portfolio: None,
                candidate_gate: strategy_candidate_gate(None, &[], min_profit_factor),
                symbols: Vec::new(),
                risk_managed_portfolio: None,
                risk_managed_symbols: Vec::new(),
                risk_overlay: None,
                selected_candidates: Vec::new(),
            });
            block.status = row.status.clone();
            block.progress_pct = row.progress_pct;
            block.progress_label = row.progress_label.clone();
            block.parameter_candidates = row.parameter_candidates;
            if row.status != "complete" {
                block.portfolio = None;
                block.symbols.clear();
            }
            refresh_strategy_candidate_gate(&mut block, min_profit_factor);
            block
        })
        .collect()
}

fn run_candidate_min_profit_factor(run_dir: &Path) -> f64 {
    read_json::<WfoConfig>(run_dir.join("config.json"))
        .map(|config| config.candidate_min_profit_factor)
        .unwrap_or(DEFAULT_CANDIDATE_MIN_PROFIT_FACTOR)
}

fn read_strategy_oos_block_map(
    run_dir: &Path,
) -> Result<BTreeMap<(String, String), StrategyOosBlock>> {
    let block_dir = run_dir.join(STRATEGY_OOS_BLOCKS_DIR);
    if !block_dir.exists() {
        return Ok(BTreeMap::new());
    }
    let mut out = BTreeMap::new();
    for entry in
        fs::read_dir(&block_dir).with_context(|| format!("read {}", block_dir.display()))?
    {
        let path = entry?.path();
        if path.extension().and_then(|value| value.to_str()) != Some("json") {
            continue;
        }
        let block = read_json::<StrategyOosBlock>(path)?;
        out.insert((block.indicator.clone(), block.timeframe.clone()), block);
    }
    Ok(out)
}

fn migrate_strategy_oos_results_to_blocks(run_dir: &Path) -> Result<()> {
    let path = run_dir.join(STRATEGY_OOS_RESULTS_FILE);
    if !path.exists() {
        return Ok(());
    }
    let blocks = read_json::<Vec<StrategyOosBlock>>(path)?;
    if blocks.is_empty() {
        return Ok(());
    }
    fs::create_dir_all(run_dir.join(STRATEGY_OOS_BLOCKS_DIR))?;
    for block in blocks {
        if block.portfolio.is_none() && block.symbols.is_empty() {
            continue;
        }
        let path = strategy_oos_block_path(run_dir, &block.indicator, &block.timeframe);
        if !path.exists() {
            write_json(path, &block)?;
        }
    }
    Ok(())
}

fn strategy_oos_block_path(run_dir: &Path, indicator: &str, timeframe: &str) -> PathBuf {
    run_dir.join(STRATEGY_OOS_BLOCKS_DIR).join(format!(
        "{}__{}.json",
        sanitize_strategy_file_part(indicator),
        sanitize_strategy_file_part(timeframe)
    ))
}

fn sanitize_strategy_file_part(value: &str) -> String {
    value
        .chars()
        .map(|ch| {
            if ch.is_ascii_alphanumeric() || ch == '_' || ch == '-' {
                ch
            } else {
                '_'
            }
        })
        .collect()
}

pub fn default_plan() -> DashboardPlan {
    let config = WfoConfig::new(GridSize::Wide);
    let folds = generate_folds(
        date_ms(config.start).unwrap_or(0),
        date_ms(config.end).unwrap_or(0),
        config.is_weeks,
        config.oos_weeks,
        config.step_weeks,
        config.gap_weeks,
    );
    DashboardPlan {
        candidate_count: candidate_grid(config.grid).len(),
        config,
        folds,
        practical_indicators: IndicatorKind::IMPLEMENTED_DIRECT_OHLC
            .iter()
            .map(|kind| kind.as_str().to_string())
            .collect(),
        regime_gates: IndicatorKind::REGIME_GATES
            .iter()
            .map(|kind| kind.as_str().to_string())
            .collect(),
        not_applicable_v1: IndicatorKind::NOT_APPLICABLE_V1
            .iter()
            .map(|kind| kind.as_str().to_string())
            .collect(),
        implementation_status: implementation_rows(&candidate_grid(GridSize::Wide)),
    }
}

fn implementation_rows(candidates: &[Candidate]) -> Vec<IndicatorImplementationRow> {
    IndicatorKind::CATALOG
        .iter()
        .map(|kind| IndicatorImplementationRow {
            indicator: kind.as_str().to_string(),
            family: kind.family().to_string(),
            implementation_status: kind.implementation_status().to_string(),
            runnable: kind.is_runnable_strategy(),
            grid_candidates: candidates
                .iter()
                .filter(|candidate| candidate.indicator == *kind)
                .count(),
            note: kind.implementation_note().to_string(),
        })
        .collect()
}

pub fn generate_folds(
    start_ms: i64,
    end_ms: i64,
    is_weeks: i64,
    oos_weeks: i64,
    step_weeks: i64,
    gap_weeks: i64,
) -> Vec<Fold> {
    generate_folds_days(
        start_ms,
        end_ms,
        is_weeks * 7,
        oos_weeks * 7,
        step_weeks * 7,
        gap_weeks * 7,
    )
}

pub fn generate_folds_days(
    start_ms: i64,
    end_ms: i64,
    is_days: i64,
    oos_days: i64,
    step_days: i64,
    gap_days: i64,
) -> Vec<Fold> {
    let day = Duration::days(1).num_milliseconds();
    let is = is_days * day;
    let oos = oos_days * day;
    let step = step_days * day;
    let gap = gap_days * day;
    let mut folds = Vec::new();
    let mut is_start = start_ms;
    while is_start + is + gap + oos <= end_ms {
        let is_end = is_start + is;
        let oos_start = is_end + gap;
        folds.push(Fold {
            index: folds.len(),
            is_start_ms: is_start,
            is_end_ms: is_end,
            oos_start_ms: oos_start,
            oos_end_ms: oos_start + oos,
        });
        is_start += step;
    }
    folds
}

fn selected_fold_range(
    folds: Vec<Fold>,
    fold_start_index: usize,
    fold_limit: Option<usize>,
) -> Vec<Fold> {
    folds
        .into_iter()
        .filter(|fold| fold.index >= fold_start_index)
        .take(fold_limit.unwrap_or(usize::MAX))
        .collect()
}

pub fn score_candidate(input: CandidateScoreInput) -> f64 {
    let CandidateScoreInput {
        net_return_pct,
        max_drawdown_pct,
        weekly_profit_fraction,
        profit_factor,
        trades,
        trade_band,
        min_profit_factor,
        average_trade_return_pct,
        min_average_trade_return_pct,
        ..
    } = input;
    let (min_trades, max_trades) = trade_band;
    let return_drawdown_score = net_return_pct / max_drawdown_pct.max(0.5);
    let profit_factor_bonus = ((profit_factor / min_profit_factor.max(1.0)).ln()).clamp(0.0, 1.25)
        * PROFIT_FACTOR_SCORE_WEIGHT;
    let edge_unit = min_average_trade_return_pct.max(0.05);
    let per_trade_edge_bonus =
        ((average_trade_return_pct - min_average_trade_return_pct) / edge_unit).clamp(0.0, 4.0)
            * PER_TRADE_EDGE_SCORE_WEIGHT;
    let drawdown_to_return_penalty = ((max_drawdown_pct / net_return_pct.max(0.5)) - 1.0)
        .clamp(0.0, 5.0)
        * DRAWDOWN_TO_RETURN_PENALTY_WEIGHT;
    let trade_penalty = trade_frequency_penalty(trades, min_trades, max_trades);
    let soft_penalties = score_input_soft_penalties(&input);
    (return_drawdown_score
        + WEEKLY_CONSISTENCY_SCORE_WEIGHT * weekly_profit_fraction
        + profit_factor_bonus
        + per_trade_edge_bonus
        - drawdown_to_return_penalty
        - trade_penalty
        - soft_penalties)
        .clamp(SOFT_SCORE_MIN, 10_000.0)
}

fn score_input_soft_penalties(input: &CandidateScoreInput) -> f64 {
    trade_count_soft_penalty(input.trades, input.trade_band.0, input.trade_band.1)
        + profit_factor_soft_penalty(input.profit_factor, input.min_profit_factor)
        + net_return_soft_penalty(input.net_return_pct, input.max_drawdown_pct)
        + average_edge_soft_penalty(
            input.average_trade_return_pct,
            input.min_average_trade_return_pct,
        )
        + edge_confidence_soft_penalty(
            edge_t_stat(
                input.average_trade_return_pct,
                input.trade_return_stddev_pct,
                input.trades,
            ),
            input.min_edge_t_stat,
        )
        + fill_rate_soft_penalty(
            input.entry_attempts,
            input.trade_band.0,
            input.fill_rate_pct,
            input.min_fill_rate_pct,
        )
        + participation_soft_penalty(
            input.entry_day_pct,
            input.min_entry_day_pct,
            input.entry_week_pct,
            input.min_entry_week_pct,
            input.longest_no_entry_gap_days,
            input.max_no_entry_gap_days,
        )
}

fn score_soft_penalties(score: &CandidateScore) -> ScorePenaltyBreakdown {
    ScorePenaltyBreakdown {
        trade: trade_count_soft_penalty(score.trades, score.min_trades, score.max_trades),
        profit_factor: profit_factor_soft_penalty(score.profit_factor, score.min_profit_factor),
        net: net_return_soft_penalty(score.net_return_pct, score.max_drawdown_pct),
        fill: fill_rate_soft_penalty(
            score.entry_attempts,
            score.min_trades,
            score.fill_rate_pct,
            score.min_fill_rate_pct,
        ),
        participation: participation_soft_penalty(
            score.entry_day_pct,
            score.min_entry_day_pct,
            score.entry_week_pct,
            score.min_entry_week_pct,
            score.longest_no_entry_gap_days,
            score.max_no_entry_gap_days,
        ),
    }
}

#[derive(Debug, Clone, Copy, Default)]
struct ScorePenaltyBreakdown {
    trade: f64,
    profit_factor: f64,
    net: f64,
    fill: f64,
    participation: f64,
}

fn trade_count_soft_penalty(trades: usize, min_trades: usize, max_trades: usize) -> f64 {
    if trades < min_trades {
        let shortfall = (min_trades - trades) as f64 / min_trades.max(1) as f64;
        shortfall * shortfall * TRADE_COUNT_SOFT_PENALTY_WEIGHT
    } else if trades > max_trades {
        let excess = (trades - max_trades) as f64 / max_trades.max(1) as f64;
        excess * excess * TRADE_COUNT_SOFT_PENALTY_WEIGHT
    } else {
        0.0
    }
}

fn profit_factor_soft_penalty(profit_factor: f64, min_profit_factor: f64) -> f64 {
    if profit_factor >= min_profit_factor {
        0.0
    } else {
        let shortfall = (min_profit_factor - profit_factor).max(0.0) / min_profit_factor.max(1.0);
        shortfall * shortfall * PROFIT_FACTOR_SOFT_PENALTY_WEIGHT
    }
}

fn net_return_soft_penalty(net_return_pct: f64, max_drawdown_pct: f64) -> f64 {
    if net_return_pct > 0.0 {
        0.0
    } else {
        NET_RETURN_SOFT_PENALTY_WEIGHT
            + net_return_pct.abs() / max_drawdown_pct.max(0.5) * NET_RETURN_SOFT_PENALTY_WEIGHT
    }
}

fn average_edge_soft_penalty(
    average_trade_return_pct: f64,
    min_average_trade_return_pct: f64,
) -> f64 {
    if average_trade_return_pct >= min_average_trade_return_pct {
        0.0
    } else {
        let unit = min_average_trade_return_pct.max(0.05);
        let shortfall = (min_average_trade_return_pct - average_trade_return_pct).max(0.0) / unit;
        shortfall * shortfall * AVG_EDGE_SOFT_PENALTY_WEIGHT
    }
}

fn edge_confidence_soft_penalty(edge_t_stat: f64, min_edge_t_stat: f64) -> f64 {
    if edge_t_stat >= min_edge_t_stat {
        0.0
    } else {
        let shortfall = (min_edge_t_stat - edge_t_stat).max(0.0);
        shortfall * shortfall * EDGE_CONFIDENCE_SOFT_PENALTY_WEIGHT
    }
}

fn fill_rate_soft_penalty(
    entry_attempts: usize,
    min_trades: usize,
    fill_rate_pct: f64,
    min_fill_rate_pct: f64,
) -> f64 {
    if entry_attempts < min_trades.max(25) || fill_rate_pct >= min_fill_rate_pct {
        0.0
    } else {
        let shortfall = (min_fill_rate_pct - fill_rate_pct).max(0.0) / min_fill_rate_pct.max(0.1);
        shortfall * shortfall * FILL_RATE_SOFT_PENALTY_WEIGHT
    }
}

fn participation_soft_penalty(
    entry_day_pct: f64,
    min_entry_day_pct: f64,
    entry_week_pct: f64,
    min_entry_week_pct: f64,
    longest_no_entry_gap_days: usize,
    max_no_entry_gap_days: usize,
) -> f64 {
    let entry_day_shortfall =
        ((min_entry_day_pct - entry_day_pct).max(0.0) / min_entry_day_pct.max(1.0)).powi(2)
            * ENTRY_DAY_SOFT_PENALTY_WEIGHT;
    let entry_week_shortfall =
        ((min_entry_week_pct - entry_week_pct).max(0.0) / min_entry_week_pct.max(1.0)).powi(2)
            * ENTRY_WEEK_SOFT_PENALTY_WEIGHT;
    let gap_excess = if longest_no_entry_gap_days > max_no_entry_gap_days {
        let excess = (longest_no_entry_gap_days - max_no_entry_gap_days) as f64
            / max_no_entry_gap_days.max(1) as f64;
        excess * excess * NO_ENTRY_GAP_SOFT_PENALTY_WEIGHT
    } else {
        0.0
    };
    entry_day_shortfall + entry_week_shortfall + gap_excess
}

fn candidate_score_has_low_fill(score: &CandidateScore) -> bool {
    score.entry_attempts >= score.min_trades.max(25)
        && score.fill_rate_pct < score.min_fill_rate_pct
}

fn candidate_score_has_low_participation(score: &CandidateScore) -> bool {
    score.entry_day_pct < score.min_entry_day_pct
        || score.entry_week_pct < score.min_entry_week_pct
        || score.longest_no_entry_gap_days > score.max_no_entry_gap_days
}

fn candidate_score_is_selectable(score: &CandidateScore, min_score: f64) -> bool {
    score.score >= min_score
        && score.trade_fit == "ok"
        && score.quality_fit == "ok"
        && !candidate_score_has_low_fill(score)
        && !candidate_score_has_low_participation(score)
}

#[derive(Debug, Clone, Copy)]
pub struct CandidateScoreInput {
    net_return_pct: f64,
    max_drawdown_pct: f64,
    weekly_profit_fraction: f64,
    profit_factor: f64,
    trades: usize,
    trade_band: (usize, usize),
    min_profit_factor: f64,
    average_trade_return_pct: f64,
    min_average_trade_return_pct: f64,
    trade_return_stddev_pct: f64,
    min_edge_t_stat: f64,
    entry_attempts: usize,
    fill_rate_pct: f64,
    min_fill_rate_pct: f64,
    entry_day_pct: f64,
    min_entry_day_pct: f64,
    entry_week_pct: f64,
    min_entry_week_pct: f64,
    longest_no_entry_gap_days: usize,
    max_no_entry_gap_days: usize,
}

fn edge_t_stat(average_trade_return_pct: f64, trade_return_stddev_pct: f64, trades: usize) -> f64 {
    if trades < 2 {
        return if average_trade_return_pct > 0.0 {
            999.0
        } else {
            0.0
        };
    }
    if trade_return_stddev_pct <= f64::EPSILON {
        return if average_trade_return_pct > 0.0 {
            999.0
        } else {
            0.0
        };
    }
    average_trade_return_pct / (trade_return_stddev_pct / (trades as f64).sqrt())
}

fn trade_frequency_penalty(trades: usize, min_trades: usize, max_trades: usize) -> f64 {
    let min_trades = min_trades.max(1) as f64;
    let max_trades = max_trades.max(min_trades as usize) as f64;
    let target = (min_trades * max_trades).sqrt();
    let ratio = (trades as f64 + 1.0) / (target + 1.0);
    let log_distance = ratio.ln().abs();
    log_distance * log_distance * TRADE_FREQUENCY_PENALTY_WEIGHT
}

pub fn long_only_excess_score(long_only_return_pct: f64, buy_hold_return_pct: f64) -> f64 {
    long_only_return_pct - buy_hold_return_pct
}

fn selection_window(config: &WfoConfig, fold: &Fold) -> (i64, i64) {
    if config.grid != GridSize::Tpe {
        return (fold.is_start_ms, fold.is_end_ms);
    }
    let is_duration_ms = fold.is_end_ms - fold.is_start_ms;
    if is_duration_ms <= 0 {
        return (fold.is_start_ms, fold.is_end_ms);
    }
    let validation_ms = (is_duration_ms as f64 * TPE_SELECTION_VALIDATION_FRACTION)
        .round()
        .max(MS_PER_MINUTE as f64) as i64;
    (
        (fold.is_end_ms - validation_ms).max(fold.is_start_ms),
        fold.is_end_ms,
    )
}

fn training_window(config: &WfoConfig, fold: &Fold) -> (i64, i64) {
    if config.grid != GridSize::Tpe {
        return (fold.is_start_ms, fold.is_end_ms);
    }
    let (validation_start_ms, _) = selection_window(config, fold);
    (fold.is_start_ms, validation_start_ms.max(fold.is_start_ms))
}

fn trades_for_window(trades: &[Trade], start_ms: i64, end_ms: i64) -> Vec<&Trade> {
    trades
        .iter()
        .filter(|trade| trade_fully_inside_window(trade, start_ms, end_ms))
        .collect()
}

fn trade_fully_inside_window(trade: &Trade, start_ms: i64, end_ms: i64) -> bool {
    trade.entry_time_ms >= start_ms
        && trade.entry_time_ms < end_ms
        && trade.exit_time_ms >= start_ms
        && trade.exit_time_ms < end_ms
}

fn training_trades_for_fold<'a>(
    trades: &'a [Trade],
    config: &WfoConfig,
    fold: &Fold,
) -> Vec<&'a Trade> {
    let (training_start_ms, training_end_ms) = training_window(config, fold);
    trades_for_window(trades, training_start_ms, training_end_ms)
}

fn selection_trades_for_fold<'a>(
    trades: &'a [Trade],
    config: &WfoConfig,
    fold: &Fold,
) -> Vec<&'a Trade> {
    let (selection_start_ms, selection_end_ms) = selection_window(config, fold);
    trades_for_window(trades, selection_start_ms, selection_end_ms)
}

fn paired_generalization_rank_score(training_score: f64, selection_score: f64) -> f64 {
    let conservative = training_score.min(selection_score);
    let mean = (training_score + selection_score) * 0.5;
    let gap_penalty = (training_score - selection_score).abs() * 0.15;
    conservative + mean * 0.25 - gap_penalty
}

fn fold_selection_rank_score(
    config: &WfoConfig,
    training_score: &CandidateScore,
    selection_score: &CandidateScore,
) -> Option<f64> {
    if !candidate_score_is_selectable(selection_score, MIN_SELECTABLE_SCORE) {
        return None;
    }
    if config.grid != GridSize::Tpe {
        return Some(selection_score.score);
    }
    if !candidate_score_is_selectable(selection_score, TPE_MIN_SELECTION_SCORE) {
        return None;
    }
    if !candidate_score_is_selectable(training_score, MIN_SELECTABLE_SCORE) {
        return None;
    }
    Some(paired_generalization_rank_score(
        training_score.score,
        selection_score.score,
    ))
}

fn fold_selection_evaluation(
    config: &WfoConfig,
    symbol: &str,
    candidate: &Candidate,
    fold: &Fold,
    all_trades: &[Trade],
    training_score: &CandidateScore,
    selection_score: &CandidateScore,
) -> FoldSelectionEvaluation {
    if should_stitch_fixed_source_strategy_oos(candidate) {
        return FoldSelectionEvaluation {
            rank_score: Some(selection_score.score),
            objective_score: selection_score.clone(),
        };
    }
    if config.grid != GridSize::Tpe {
        return FoldSelectionEvaluation {
            rank_score: fold_selection_rank_score(config, training_score, selection_score),
            objective_score: selection_score.clone(),
        };
    }

    let Some(base_rank) = fold_selection_rank_score(config, training_score, selection_score) else {
        return FoldSelectionEvaluation {
            rank_score: None,
            objective_score: selection_score.clone(),
        };
    };
    tpe_is_offset_consensus_selection(
        config,
        symbol,
        candidate,
        fold,
        all_trades,
        selection_score,
        base_rank,
    )
}

fn strict_fold_selection(
    evaluation: &FoldSelectionEvaluation,
    indicator: IndicatorKind,
    trades: Vec<Trade>,
) -> Option<FoldSelection> {
    evaluation.rank_score.map(|rank_score| FoldSelection {
        score: evaluation.objective_score.clone(),
        rank_score,
        indicator,
        trades,
    })
}

fn oos_trades_for_fold(trades: &[Trade], fold: &Fold) -> Vec<Trade> {
    trades
        .iter()
        .filter(|trade| trade_fully_inside_window(trade, fold.oos_start_ms, fold.oos_end_ms))
        .cloned()
        .collect()
}

fn tpe_is_offset_consensus_selection(
    config: &WfoConfig,
    symbol: &str,
    candidate: &Candidate,
    fold: &Fold,
    all_trades: &[Trade],
    fallback_score: &CandidateScore,
    base_rank: f64,
) -> FoldSelectionEvaluation {
    let is_duration_ms = fold.is_end_ms - fold.is_start_ms;
    let config_start_ms = match date_ms(config.start) {
        Ok(value) => value,
        Err(_) => {
            let mut score = fallback_score.clone();
            score.score = INELIGIBLE_SCORE_CUTOFF - 700.0;
            return FoldSelectionEvaluation {
                rank_score: None,
                objective_score: score,
            };
        }
    };
    if is_duration_ms <= 0 {
        let mut score = fallback_score.clone();
        score.score = INELIGIBLE_SCORE_CUTOFF - 700.0;
        return FoldSelectionEvaluation {
            rank_score: None,
            objective_score: score,
        };
    }

    let mut consensus_scores = Vec::with_capacity(TPE_IS_CONSENSUS_OFFSET_DAYS);
    for offset_day in 0..TPE_IS_CONSENSUS_OFFSET_DAYS {
        let offset_ms = Duration::days(offset_day as i64).num_milliseconds();
        let end_ms = fold.is_end_ms - offset_ms;
        let start_ms = end_ms - is_duration_ms;
        if start_ms < config_start_ms {
            let mut score = fallback_score.clone();
            score.score = INELIGIBLE_SCORE_CUTOFF - 700.0;
            return FoldSelectionEvaluation {
                rank_score: None,
                objective_score: score,
            };
        }
        let window_trades = trades_for_window(all_trades, start_ms, end_ms);
        consensus_scores.push(score_trades_in_window(
            symbol,
            candidate,
            fold.index,
            &window_trades,
            config,
            start_ms,
            end_ms,
        ));
    }

    let passing_scores = consensus_scores
        .iter()
        .filter(|score| candidate_score_is_selectable(score, TPE_MIN_SELECTION_SCORE))
        .cloned()
        .collect::<Vec<_>>();
    let passing_count = passing_scores.len();
    let score_source = if passing_scores.is_empty() {
        &consensus_scores
    } else {
        &passing_scores
    };
    let mut objective_score = score_source
        .iter()
        .min_by(|left, right| left.score.total_cmp(&right.score))
        .cloned()
        .unwrap_or_else(|| fallback_score.clone());
    let values = score_source
        .iter()
        .map(|score| score.score)
        .collect::<Vec<_>>();
    let lower_tail_score = percentile(&values, 0.25);
    let mean_score = values.iter().sum::<f64>() / values.len().max(1) as f64;
    let dispersion = sample_stddev(&values);
    let missed_window_penalty = (TPE_IS_CONSENSUS_OFFSET_DAYS - passing_count) as f64;
    let consensus_rank = lower_tail_score + mean_score * TPE_IS_CONSENSUS_MEAN_RANK_WEIGHT
        - dispersion * TPE_IS_CONSENSUS_DISPERSION_RANK_WEIGHT;
    objective_score.score = consensus_rank - missed_window_penalty;

    let enough_windows_pass = passing_count >= config.tpe_is_consensus_min_passing_windows;
    FoldSelectionEvaluation {
        rank_score: enough_windows_pass.then_some(base_rank.min(objective_score.score)),
        objective_score,
    }
}

fn tpe_candidate_rank_adjustment(
    config: &WfoConfig,
    candidate: &Candidate,
    objective: &TpeObjectiveBreakdown,
) -> f64 {
    if config.grid != GridSize::Tpe || should_stitch_fixed_source_strategy_oos(candidate) {
        return 0.0;
    }
    let breadth = objective
        .training_eligible_fraction
        .min(objective.validation_eligible_fraction);
    let breadth_adjustment = (breadth - TPE_BREADTH_REFERENCE_FRACTION) * TPE_BREADTH_RANK_WEIGHT;
    let objective_adjustment = objective.objective_score.max(0.0) * TPE_OBJECTIVE_RANK_WEIGHT;
    breadth_adjustment + objective_adjustment
}

fn adjusted_fold_selection(mut selection: FoldSelection, rank_adjustment: f64) -> FoldSelection {
    selection.rank_score += rank_adjustment;
    selection
}

fn insert_strategy_fold_selection(
    selections: &mut BTreeMap<(String, String, String, usize), FoldSelection>,
    key: (String, String, String, usize),
    selection: FoldSelection,
) {
    let replace = selections
        .get(&key)
        .map(|current| selection.rank_score > current.rank_score)
        .unwrap_or(true);
    if replace {
        selections.insert(key, selection);
    }
}

fn insert_best_fold_selection(
    selections: &mut BTreeMap<usize, FoldSelection>,
    fold_index: usize,
    selection: FoldSelection,
) {
    let replace = selections
        .get(&fold_index)
        .map(|current| selection.rank_score > current.rank_score)
        .unwrap_or(true);
    if replace {
        selections.insert(fold_index, selection);
    }
}

struct SimulationResult {
    symbol: String,
    candidate: Candidate,
    trades: Vec<Trade>,
    fold_diagnostics: Vec<CandidateSignalFillFoldDiagnostics>,
}

#[derive(Debug, Clone, Default)]
struct CandidateSignalFillFoldDiagnostics {
    fold_index: usize,
    raw_signal_bars: usize,
    gated_signal_bars: usize,
    entry_attempts: usize,
    filled_entries: usize,
    closed_trades: usize,
}

#[derive(Debug, Clone, Default)]
struct SignalFillDiagnosticsAccumulator {
    candidates_evaluated: usize,
    raw_signal_bars: usize,
    gated_signal_bars: usize,
    entry_attempts: usize,
    filled_entries: usize,
    closed_trades: usize,
    too_sparse: usize,
    too_active: usize,
    bad_exit_geometry: usize,
    low_profit_factor: usize,
    low_average_trade_edge: usize,
    low_edge_confidence: usize,
    low_fill_rate: usize,
    low_participation: usize,
    eligible_nonpositive_net: usize,
    eligible_positive_net: usize,
}

type SignalFillDiagnosticsMap =
    BTreeMap<(String, String, String, usize), SignalFillDiagnosticsAccumulator>;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SignalFillDiagnosticsRow {
    pub indicator: String,
    pub timeframe: String,
    pub symbol: String,
    pub fold_index: usize,
    pub candidates_evaluated: usize,
    pub raw_signal_bars: usize,
    pub gated_signal_bars: usize,
    pub entry_attempts: usize,
    pub filled_entries: usize,
    pub closed_trades: usize,
    pub raw_signal_bars_per_candidate: f64,
    pub gated_signal_bars_per_candidate: f64,
    pub entry_attempts_per_candidate: f64,
    pub fill_rate_pct: f64,
    pub closed_trades_per_candidate: f64,
    pub too_sparse: usize,
    pub too_active: usize,
    #[serde(default)]
    pub bad_exit_geometry: usize,
    pub low_profit_factor: usize,
    pub low_average_trade_edge: usize,
    #[serde(default)]
    pub low_edge_confidence: usize,
    #[serde(default)]
    pub low_fill_rate: usize,
    #[serde(default)]
    pub low_participation: usize,
    pub eligible_nonpositive_net: usize,
    pub eligible_positive_net: usize,
    pub eligible_total: usize,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SpaceScanMetricRow {
    pub candidate_id: usize,
    pub symbol: String,
    pub fold_index: usize,
    pub window: String,
    pub window_start_ms: i64,
    pub window_end_ms: i64,
    pub net_return_pct: f64,
    pub max_drawdown_pct: f64,
    pub profit_factor: f64,
    pub average_trade_return_pct: f64,
    pub trades: usize,
    pub min_trades: usize,
    pub max_trades: usize,
    pub score: f64,
    pub rejection_reason: String,
    pub raw_signal_bars: usize,
    pub gated_signal_bars: usize,
    pub entry_attempts: usize,
    pub filled_entries: usize,
    pub fill_rate_pct: f64,
    pub closed_trades: usize,
    pub lookback: usize,
    pub atr_period: usize,
    pub stop_atr_multiple: f64,
    pub target_atr_multiple: f64,
    pub strategy_4448_kama1_er: usize,
    pub strategy_4448_kama1_short: usize,
    pub strategy_4448_kama1_long: usize,
    pub strategy_4448_kama2_er: usize,
    pub strategy_4448_kama2_short: usize,
    pub strategy_4448_kama2_long: usize,
    pub strategy_4448_count_bars: usize,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SpaceScanRejectionSummaryRow {
    pub symbol: String,
    pub window: String,
    pub rejection_reason: String,
    pub candidates: usize,
    pub candidates_pct: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SpaceScanParamBinSummaryRow {
    pub parameter: String,
    pub bin: String,
    pub window: String,
    pub candidates: usize,
    pub selectable: usize,
    pub selectable_pct: f64,
    pub low_fill_rate: usize,
    pub low_fill_rate_pct: f64,
    pub average_score: f64,
    pub average_net_return_pct: f64,
    pub average_trades: f64,
    pub average_fill_rate_pct: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SpaceScanTopCandidateRow {
    pub rank: usize,
    pub candidate_id: usize,
    pub selectable_symbols: usize,
    pub base_pass_symbols: usize,
    pub selection_score_avg: f64,
    pub selection_net_return_avg_pct: f64,
    pub selection_profit_factor_avg: f64,
    pub selection_trades_total: usize,
    pub selection_fill_rate_avg_pct: f64,
    pub oos_net_return_total_pct: f64,
    pub oos_profit_factor_avg: f64,
    pub oos_trades_total: usize,
    pub lookback: usize,
    pub atr_period: usize,
    pub stop_atr_multiple: f64,
    pub target_atr_multiple: f64,
    pub strategy_4448_kama1_er: usize,
    pub strategy_4448_kama1_short: usize,
    pub strategy_4448_kama1_long: usize,
    pub strategy_4448_kama2_er: usize,
    pub strategy_4448_kama2_short: usize,
    pub strategy_4448_kama2_long: usize,
    pub strategy_4448_count_bars: usize,
}

#[derive(Debug, Clone)]
struct TpeTrialEvaluation {
    candidate: Candidate,
    mean_score: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TpeTrialTraceRow {
    pub trial_index: usize,
    #[serde(default)]
    pub fold_index: Option<usize>,
    pub candidate_id: usize,
    pub indicator: String,
    pub timeframe: String,
    pub objective_score: f64,
    pub best_objective_score: f64,
    pub best_candidate_id: usize,
    pub training_mean_score: f64,
    pub validation_mean_score: f64,
    pub training_q25_score: f64,
    pub training_median_score: f64,
    pub validation_q25_score: f64,
    pub validation_median_score: f64,
    pub validation_score_stddev: f64,
    pub training_eligible_fraction: f64,
    pub validation_eligible_fraction: f64,
    pub validation_net_positive_fraction: f64,
    pub validation_trade_fit_fraction: f64,
    pub validation_quality_fit_fraction: f64,
    pub validation_median_profit_factor: f64,
    #[serde(default)]
    pub training_nonnegative_score_fraction: f64,
    #[serde(default)]
    pub validation_nonnegative_score_fraction: f64,
    #[serde(default)]
    pub average_trade_penalty: f64,
    #[serde(default)]
    pub average_profit_factor_penalty: f64,
    #[serde(default)]
    pub average_net_penalty: f64,
    #[serde(default)]
    pub average_fill_penalty: f64,
    #[serde(default)]
    pub average_participation_penalty: f64,
    #[serde(default)]
    pub base_objective_component: f64,
    #[serde(default)]
    pub consistency_bonus: f64,
    #[serde(default)]
    pub paired_bonus: f64,
    pub paired_selection_fraction: f64,
    pub paired_selection_count: usize,
    pub train_gap_penalty: f64,
    pub dispersion_penalty: f64,
    pub training_scores: usize,
    pub validation_scores: usize,
    pub trial_trade_count: usize,
    pub lookback: usize,
    pub atr_period: usize,
    pub entry_atr_multiple: f64,
    pub stop_atr_multiple: f64,
    pub target_atr_multiple: f64,
    pub time_stop_bars: Option<usize>,
    pub strategy_4448_kama1_er: usize,
    pub strategy_4448_kama1_short: usize,
    pub strategy_4448_kama1_long: usize,
    pub strategy_4448_kama2_er: usize,
    pub strategy_4448_kama2_short: usize,
    pub strategy_4448_kama2_long: usize,
    pub strategy_4448_count_bars: usize,
}

#[derive(Debug, Clone, Copy)]
struct TpeObjectiveBreakdown {
    objective_score: f64,
    training_mean_score: f64,
    validation_mean_score: f64,
    training_q25_score: f64,
    training_median_score: f64,
    validation_q25_score: f64,
    validation_median_score: f64,
    validation_score_stddev: f64,
    training_eligible_fraction: f64,
    validation_eligible_fraction: f64,
    validation_net_positive_fraction: f64,
    validation_trade_fit_fraction: f64,
    validation_quality_fit_fraction: f64,
    validation_median_profit_factor: f64,
    training_nonnegative_score_fraction: f64,
    validation_nonnegative_score_fraction: f64,
    average_trade_penalty: f64,
    average_profit_factor_penalty: f64,
    average_net_penalty: f64,
    average_fill_penalty: f64,
    average_participation_penalty: f64,
    base_objective_component: f64,
    consistency_bonus: f64,
    paired_bonus: f64,
    paired_selection_fraction: f64,
    paired_selection_count: usize,
    train_gap_penalty: f64,
    dispersion_penalty: f64,
}

#[derive(Debug, Clone)]
struct FoldSelection {
    score: CandidateScore,
    rank_score: f64,
    indicator: IndicatorKind,
    trades: Vec<Trade>,
}

type FoldStudyKey = (String, String, usize);
type StrategyFoldSelectionKey = (String, String, String, usize);
type FoldSelectionMap = BTreeMap<StrategyFoldSelectionKey, FoldSelection>;

#[derive(Debug, Clone)]
struct FoldSelectionEvaluation {
    rank_score: Option<f64>,
    objective_score: CandidateScore,
}

#[derive(Debug, Default)]
struct SimulationCache {
    tf_bars: BTreeMap<(String, String), Vec<OhlcvBar>>,
    signals: BTreeMap<(String, String, String, String), Vec<SignalPoint>>,
    regimes: BTreeMap<(String, String, usize), CachedRegime>,
}

#[derive(Debug, Clone)]
struct CachedRegime {
    entropy: Vec<f64>,
    hurst: Vec<f64>,
}

#[derive(Debug, Clone)]
struct PreparedSimulation {
    symbol: String,
    candidate: Candidate,
    raw_signals_1m: Vec<SignalPoint>,
    signals_1m: Vec<SignalPoint>,
    execution: ExecutionConfig,
}

#[derive(Debug, Clone)]
struct TpeSearchSpace {
    signal_polarity: IntParam,
    entry_mode: IntParam,
    lookback_bars: IntParam,
    atr_bars: IntParam,
    entry_atr_multiple: FloatParam,
    stop_atr_multiple: FloatParam,
    target_atr_multiple: FloatParam,
    time_stop_bars: IntParam,
    hurst_min: FloatParam,
    hurst_max: FloatParam,
    shannon_max: FloatParam,
    strategy_4448_lookback: IntParam,
    strategy_4448_atr_period: IntParam,
    strategy_4448_stop_atr_multiple: FloatParam,
    strategy_4448_target_atr_multiple: FloatParam,
    strategy_4448_kama1_er: IntParam,
    strategy_4448_kama1_short: IntParam,
    strategy_4448_kama1_long: IntParam,
    strategy_4448_kama2_er: IntParam,
    strategy_4448_kama2_short: IntParam,
    strategy_4448_kama2_long: IntParam,
    strategy_4448_count_bars: IntParam,
}

impl TpeSearchSpace {
    fn new() -> Self {
        Self {
            signal_polarity: IntParam::new(0, 1).name("signal_polarity"),
            entry_mode: IntParam::new(0, 1).name("entry_mode"),
            lookback_bars: IntParam::new(
                TPE_MIN_LOOKBACK_BARS as i64,
                TPE_MAX_LOOKBACK_BARS as i64,
            )
            .step(1)
            .name("lookback_bars"),
            atr_bars: IntParam::new(TPE_MIN_ATR_BARS as i64, TPE_MAX_ATR_BARS as i64)
                .step(TPE_ATR_STEP_BARS as i64)
                .name("atr_bars"),
            entry_atr_multiple: FloatParam::new(0.0, TPE_MAX_ENTRY_ATR_MULTIPLE)
                .name("entry_atr_multiple"),
            stop_atr_multiple: FloatParam::new(
                MIN_EXIT_STOP_ATR_MULTIPLE,
                MAX_EXIT_STOP_ATR_MULTIPLE,
            )
            .name("stop_atr_multiple"),
            target_atr_multiple: FloatParam::new(
                TPE_MIN_TARGET_ATR_MULTIPLE,
                MAX_EXIT_TARGET_ATR_MULTIPLE,
            )
            .name("target_atr_multiple"),
            time_stop_bars: IntParam::new(0, TPE_MAX_TIME_STOP_BARS as i64)
                .step(1)
                .name("time_stop_bars"),
            hurst_min: FloatParam::new(-0.25, 0.65).name("hurst_min"),
            hurst_max: FloatParam::new(0.45, 1.25).name("hurst_max"),
            shannon_max: FloatParam::new(0.75, 1.25).name("shannon_max"),
            strategy_4448_lookback: IntParam::new(5, 120).step(1).name("strategy_4448_lookback"),
            strategy_4448_atr_period: IntParam::new(20, 200)
                .step(5)
                .name("strategy_4448_atr_period"),
            strategy_4448_stop_atr_multiple: FloatParam::new(
                MIN_EXIT_STOP_ATR_MULTIPLE,
                MAX_EXIT_STOP_ATR_MULTIPLE,
            )
            .name("strategy_4448_stop_atr_multiple"),
            strategy_4448_target_atr_multiple: FloatParam::new(2.0, MAX_EXIT_TARGET_ATR_MULTIPLE)
                .name("strategy_4448_target_atr_multiple"),
            strategy_4448_kama1_er: IntParam::new(5, 120).step(1).name("strategy_4448_kama1_er"),
            strategy_4448_kama1_short: IntParam::new(2, 120)
                .step(1)
                .name("strategy_4448_kama1_short"),
            strategy_4448_kama1_long: IntParam::new(2, 160)
                .step(1)
                .name("strategy_4448_kama1_long"),
            strategy_4448_kama2_er: IntParam::new(5, 60).step(1).name("strategy_4448_kama2_er"),
            strategy_4448_kama2_short: IntParam::new(2, 30)
                .step(1)
                .name("strategy_4448_kama2_short"),
            strategy_4448_kama2_long: IntParam::new(2, 160)
                .step(1)
                .name("strategy_4448_kama2_long"),
            strategy_4448_count_bars: IntParam::new(3, 15)
                .step(1)
                .name("strategy_4448_count_bars"),
        }
    }

    fn suggest(&self, trial: &mut optimizer::Trial, template: &Candidate) -> Result<Candidate> {
        if matches!(
            template.indicator,
            IndicatorKind::Strategy336KamaTpo
                | IndicatorKind::Strategy3635KamaTpo
                | IndicatorKind::Strategy3938KamaTpo
        ) {
            return self.suggest_sqx_kama_tpo(trial, template);
        }
        if template.indicator == IndicatorKind::Strategy4448KamaKer {
            return self.suggest_strategy_4448_kama_ker(trial, template);
        }
        let signal_polarity = if self.signal_polarity.suggest(trial)? == 0 {
            -1
        } else {
            1
        };
        let entry_mode = if self.entry_mode.suggest(trial)? == 0 {
            EntryMode::Pullback
        } else {
            EntryMode::Breakout
        };
        let lookback = usize::try_from(self.lookback_bars.suggest(trial)?)?
            .clamp(TPE_MIN_LOOKBACK_BARS, TPE_MAX_LOOKBACK_BARS);
        let atr_period = round_to_step(
            usize::try_from(self.atr_bars.suggest(trial)?)?
                .clamp(TPE_MIN_ATR_BARS, TPE_MAX_ATR_BARS),
            TPE_ATR_STEP_BARS,
        );
        let entry_atr_multiple = self
            .entry_atr_multiple
            .suggest(trial)?
            .clamp(0.0, TPE_MAX_ENTRY_ATR_MULTIPLE);
        let stop_atr_multiple = self
            .stop_atr_multiple
            .suggest(trial)?
            .clamp(MIN_EXIT_STOP_ATR_MULTIPLE, MAX_EXIT_STOP_ATR_MULTIPLE);
        let target_atr_multiple = self
            .target_atr_multiple
            .suggest(trial)?
            .clamp(TPE_MIN_TARGET_ATR_MULTIPLE, MAX_EXIT_TARGET_ATR_MULTIPLE)
            .min(stop_atr_multiple * MAX_EXIT_TARGET_STOP_RATIO);
        let time_stop_bars = match self.time_stop_bars.suggest(trial)? {
            value if value <= 0 => None,
            value => Some(usize::try_from(value)?.clamp(1, TPE_MAX_TIME_STOP_BARS)),
        };
        let hurst_min_value = self.hurst_min.suggest(trial)?.clamp(-0.25, 0.65);
        let mut hurst_max_value = self.hurst_max.suggest(trial)?.clamp(0.45, 1.25);
        if hurst_min_value > 0.0 && hurst_max_value <= hurst_min_value {
            hurst_max_value = (hurst_min_value + 0.05).min(1.0);
        }
        let shannon_max_value = self.shannon_max.suggest(trial)?.clamp(0.75, 1.25);

        Ok(Candidate {
            id: template.id,
            indicator: template.indicator,
            timeframe: template.timeframe,
            signal_polarity,
            entry_mode,
            lookback,
            atr_period,
            entry_atr_multiple,
            stop_atr_multiple,
            target_atr_multiple,
            time_stop_bars,
            hurst_min: (hurst_min_value >= 0.20).then_some(hurst_min_value),
            hurst_max: (hurst_max_value <= 0.95).then_some(hurst_max_value),
            shannon_max: (shannon_max_value <= 0.98).then_some(shannon_max_value),
            ..Candidate::default()
        })
    }

    fn suggest_sqx_kama_tpo(
        &self,
        _trial: &mut optimizer::Trial,
        template: &Candidate,
    ) -> Result<Candidate> {
        Ok(source_sqx_kama_tpo_candidate(template))
    }

    fn suggest_strategy_4448_kama_ker(
        &self,
        trial: &mut optimizer::Trial,
        template: &Candidate,
    ) -> Result<Candidate> {
        let lookback = self.strategy_4448_lookback.suggest(trial)? as usize;
        let atr_period = self.strategy_4448_atr_period.suggest(trial)? as usize;
        let stop_atr_multiple = self.strategy_4448_stop_atr_multiple.suggest(trial)?;
        let target_atr_multiple = self
            .strategy_4448_target_atr_multiple
            .suggest(trial)?
            .min(stop_atr_multiple * MAX_EXIT_TARGET_STOP_RATIO);
        let strategy_4448_kama1_er = self.strategy_4448_kama1_er.suggest(trial)? as usize;
        let strategy_4448_kama1_short_raw = self.strategy_4448_kama1_short.suggest(trial)? as usize;
        let strategy_4448_kama1_long_raw = self.strategy_4448_kama1_long.suggest(trial)? as usize;
        let (strategy_4448_kama1_short, strategy_4448_kama1_long) = ordered_period_pair(
            strategy_4448_kama1_short_raw,
            strategy_4448_kama1_long_raw,
            2,
            160,
        );
        let strategy_4448_kama2_er = self.strategy_4448_kama2_er.suggest(trial)? as usize;
        let strategy_4448_kama2_short_raw = self.strategy_4448_kama2_short.suggest(trial)? as usize;
        let strategy_4448_kama2_long_raw = self.strategy_4448_kama2_long.suggest(trial)? as usize;
        let (strategy_4448_kama2_short, strategy_4448_kama2_long) = ordered_period_pair(
            strategy_4448_kama2_short_raw,
            strategy_4448_kama2_long_raw,
            2,
            160,
        );
        let strategy_4448_count_bars = self.strategy_4448_count_bars.suggest(trial)? as usize;

        Ok(Candidate {
            id: template.id,
            indicator: template.indicator,
            timeframe: template.timeframe,
            signal_polarity: 1,
            entry_mode: EntryMode::Pullback,
            lookback,
            atr_period,
            entry_atr_multiple: 0.0,
            stop_atr_multiple,
            target_atr_multiple,
            time_stop_bars: Some(28),
            hurst_min: None,
            hurst_max: None,
            shannon_max: None,
            strategy_4448_kama1_er,
            strategy_4448_kama1_short,
            strategy_4448_kama1_long,
            strategy_4448_kama2_er,
            strategy_4448_kama2_short: strategy_4448_kama2_short.min(30),
            strategy_4448_kama2_long,
            strategy_4448_count_bars,
        })
    }
}

fn source_sqx_kama_tpo_candidate(template: &Candidate) -> Candidate {
    let source_stop = match template.indicator {
        IndicatorKind::Strategy3635KamaTpo | IndicatorKind::Strategy3938KamaTpo => 2.9,
        _ => 3.2,
    };
    Candidate {
        id: template.id,
        indicator: template.indicator,
        timeframe: template.timeframe,
        signal_polarity: 1,
        entry_mode: EntryMode::Pullback,
        lookback: 40,
        atr_period: 80,
        entry_atr_multiple: 0.0,
        stop_atr_multiple: source_stop,
        target_atr_multiple: 7.1,
        time_stop_bars: Some(28),
        hurst_min: None,
        hurst_max: None,
        shannon_max: None,
        ..Candidate::default()
    }
}

#[cfg(test)]
fn source_strategy_4448_kama_ker_candidate(template: &Candidate) -> Candidate {
    Candidate {
        id: template.id,
        indicator: template.indicator,
        timeframe: template.timeframe,
        signal_polarity: 1,
        entry_mode: EntryMode::Pullback,
        lookback: 47,
        atr_period: 80,
        entry_atr_multiple: 0.0,
        stop_atr_multiple: 2.6,
        target_atr_multiple: 7.7,
        time_stop_bars: Some(28),
        hurst_min: None,
        hurst_max: None,
        shannon_max: None,
        ..Candidate::default()
    }
}

fn should_stitch_fixed_source_strategy_oos(candidate: &Candidate) -> bool {
    let sqx_kama_tpo = matches!(
        candidate.indicator,
        IndicatorKind::Strategy336KamaTpo
            | IndicatorKind::Strategy3635KamaTpo
            | IndicatorKind::Strategy3938KamaTpo
    ) && candidate.lookback == 40
        && candidate.atr_period == 80
        && candidate.entry_atr_multiple == 0.0
        && candidate.target_atr_multiple == 7.1
        && candidate.time_stop_bars == Some(28);
    let strategy_4448 = candidate.indicator == IndicatorKind::Strategy4448KamaKer
        && candidate.lookback == 47
        && candidate.atr_period == 80
        && candidate.entry_atr_multiple == 0.0
        && candidate.stop_atr_multiple == 2.6
        && candidate.target_atr_multiple == 7.7
        && candidate.time_stop_bars == Some(28)
        && candidate.strategy_4448_kama1_er == STRATEGY_4448_SOURCE_KAMA1_ER
        && candidate.strategy_4448_kama1_short == STRATEGY_4448_SOURCE_KAMA1_SHORT
        && candidate.strategy_4448_kama1_long == STRATEGY_4448_SOURCE_KAMA1_LONG
        && candidate.strategy_4448_kama2_er == STRATEGY_4448_SOURCE_KAMA2_ER
        && candidate.strategy_4448_kama2_short == STRATEGY_4448_SOURCE_KAMA2_SHORT
        && candidate.strategy_4448_kama2_long == STRATEGY_4448_SOURCE_KAMA2_LONG
        && candidate.strategy_4448_count_bars == STRATEGY_4448_SOURCE_COUNT_BARS;
    sqx_kama_tpo || strategy_4448
}

fn stable_seed(parts: &[&str]) -> u64 {
    let mut hash = 0xcbf29ce484222325_u64;
    for part in parts {
        for byte in part.as_bytes() {
            hash ^= u64::from(*byte);
            hash = hash.wrapping_mul(0x100000001b3);
        }
        hash ^= 0xff;
        hash = hash.wrapping_mul(0x100000001b3);
    }
    hash
}

fn prepare_candidate_simulation(
    symbol: &str,
    bars_1m: &[OhlcvBar],
    candidate: &Candidate,
    config: &WfoConfig,
    cache: &mut SimulationCache,
) -> Result<PreparedSimulation> {
    let rules = SymbolExecutionRules::for_symbol(symbol).with_context(|| {
        format!("missing pinned Binance USD-M execution filters for symbol {symbol}")
    })?;
    let timeframe_key = (symbol.to_string(), candidate.timeframe.as_str().to_string());
    if !cache.tf_bars.contains_key(&timeframe_key) {
        cache
            .tf_bars
            .insert(timeframe_key.clone(), resample_ohlcv(bars_1m, candidate.timeframe));
    }
    let tf_bars = cache
        .tf_bars
        .get(&timeframe_key)
        .with_context(|| "missing cached timeframe bars")?;
    let signal_key = (
        symbol.to_string(),
        candidate.indicator.as_str().to_string(),
        candidate.timeframe.as_str().to_string(),
        candidate.signal_cache_key(),
    );
    let mut tf_signals = if let Some(signals) = cache.signals.get(&signal_key) {
        signals.clone()
    } else {
        let signals = {
            if candidate.indicator == IndicatorKind::Strategy4448KamaKer {
                strategy_4448_kama_ker_signals(&tf_bars, candidate.strategy_4448_params())
            } else {
                momentum_signals(
                    &tf_bars,
                    candidate.indicator,
                    candidate.lookback,
                    candidate.atr_period,
                )
            }
        };
        cache.signals.insert(signal_key, signals.clone());
        signals
    };
    apply_signal_polarity(&mut tf_signals, candidate.signal_polarity);
    let raw_signals_1m = expand_signals(bars_1m, &tf_signals, candidate.timeframe);
    let regime_key = (
        symbol.to_string(),
        candidate.timeframe.as_str().to_string(),
        candidate.lookback.max(8),
    );
    if !cache.regimes.contains_key(&regime_key) {
        cache.regimes.insert(regime_key.clone(), CachedRegime {
            entropy: shannon_entropy(&tf_bars, candidate.lookback.max(8)),
            hurst: hurst_exponent(&tf_bars, candidate.lookback.max(8)),
        });
    }
    let regime = cache
        .regimes
        .get(&regime_key)
        .with_context(|| "missing cached regime series")?;
    for ((signal, entropy), hurst) in tf_signals
        .iter_mut()
        .zip(regime.entropy.iter())
        .zip(regime.hurst.iter())
    {
        if candidate
            .shannon_max
            .is_some_and(|max_entropy| *entropy > max_entropy)
            || candidate
                .hurst_min
                .is_some_and(|min_hurst| *hurst < min_hurst)
            || candidate
                .hurst_max
                .is_some_and(|max_hurst| *hurst > max_hurst)
        {
            signal.direction = 0;
        }
    }
    let signals_1m = expand_signals(bars_1m, &tf_signals, candidate.timeframe);
    let execution = ExecutionConfig {
        fixed_notional: config.fixed_notional,
        entry_mode: candidate.entry_mode,
        entry_fill_model: crate::engine::EntryFillModel::ImmediateOhlcTouch,
        entry_atr_multiple: candidate.entry_atr_multiple,
        stop_atr_multiple: candidate.stop_atr_multiple,
        target_atr_multiple: candidate.target_atr_multiple,
        time_stop_bars: execution_time_stop_bars(candidate),
        entry_order_valid_bars: entry_order_valid_bars(candidate),
        fee_rate: config.fees_bps / 10_000.0,
        breach_ticks: 1,
        symbol_rules: rules,
    };
    Ok(PreparedSimulation {
        symbol: symbol.to_string(),
        candidate: candidate.clone(),
        raw_signals_1m,
        signals_1m,
        execution,
    })
}

fn apply_signal_polarity(signals: &mut [SignalPoint], polarity: i8) {
    if polarity >= 0 {
        return;
    }
    for signal in signals {
        signal.direction = -signal.direction;
    }
}

fn simulate_prepared_candidate(
    bars_1m: &[OhlcvBar],
    prepared: &PreparedSimulation,
    folds: &[Fold],
) -> SimulationResult {
    let (trades, execution_diagnostics) = simulate_limit_momentum_trades_with_diagnostics(
        &prepared.symbol,
        bars_1m,
        &prepared.signals_1m,
        prepared.execution,
    );
    let fold_diagnostics = signal_fill_fold_diagnostics_for_folds(
        &prepared.raw_signals_1m,
        &prepared.signals_1m,
        &execution_diagnostics.entry_attempts,
        &trades,
        folds,
    );
    SimulationResult {
        symbol: prepared.symbol.clone(),
        candidate: prepared.candidate.clone(),
        trades,
        fold_diagnostics,
    }
}

fn signal_fill_fold_diagnostics_for_folds(
    raw_signals: &[SignalPoint],
    gated_signals: &[SignalPoint],
    entry_attempts: &[EntryAttempt],
    trades: &[Trade],
    folds: &[Fold],
) -> Vec<CandidateSignalFillFoldDiagnostics> {
    let raw_signal_times = EventTimes::from_signal_bars(raw_signals);
    let gated_signal_times = EventTimes::from_signal_bars(gated_signals);
    let entry_attempt_times = EventTimes::from_attempts(entry_attempts, false);
    let filled_entry_times = EventTimes::from_attempts(entry_attempts, true);
    let closed_trade_times = EventTimes::from_trades(trades);

    folds
        .iter()
        .map(|fold| CandidateSignalFillFoldDiagnostics {
            fold_index: fold.index,
            raw_signal_bars: raw_signal_times.count(fold.is_start_ms, fold.is_end_ms),
            gated_signal_bars: gated_signal_times.count(fold.is_start_ms, fold.is_end_ms),
            entry_attempts: entry_attempt_times.count(fold.is_start_ms, fold.is_end_ms),
            filled_entries: filled_entry_times.count(fold.is_start_ms, fold.is_end_ms),
            closed_trades: closed_trade_times.count(fold.is_start_ms, fold.is_end_ms),
        })
        .collect()
}

fn signal_fill_window_diagnostics(
    raw_signals: &[SignalPoint],
    gated_signals: &[SignalPoint],
    entry_attempts: &[EntryAttempt],
    trades: &[Trade],
    start_ms: i64,
    end_ms: i64,
) -> CandidateSignalFillFoldDiagnostics {
    let raw_signal_times = EventTimes::from_signal_bars(raw_signals);
    let gated_signal_times = EventTimes::from_signal_bars(gated_signals);
    let entry_attempt_times = EventTimes::from_attempts(entry_attempts, false);
    let filled_entry_times = EventTimes::from_attempts(entry_attempts, true);
    let closed_trade_times = EventTimes::from_trades(trades);

    CandidateSignalFillFoldDiagnostics {
        fold_index: 0,
        raw_signal_bars: raw_signal_times.count(start_ms, end_ms),
        gated_signal_bars: gated_signal_times.count(start_ms, end_ms),
        entry_attempts: entry_attempt_times.count(start_ms, end_ms),
        filled_entries: filled_entry_times.count(start_ms, end_ms),
        closed_trades: closed_trade_times.count(start_ms, end_ms),
    }
}

struct EventTimes {
    timestamps_ms: Vec<i64>,
}

impl EventTimes {
    fn from_signal_bars(signals: &[SignalPoint]) -> Self {
        Self {
            timestamps_ms: signals
                .iter()
                .filter(|signal| signal.direction != 0)
                .map(|signal| signal.timestamp_ms)
                .collect(),
        }
    }

    fn from_attempts(entry_attempts: &[EntryAttempt], accepted_only: bool) -> Self {
        Self {
            timestamps_ms: entry_attempts
                .iter()
                .filter(|attempt| !accepted_only || attempt.accepted)
                .map(|attempt| attempt.timestamp_ms)
                .collect(),
        }
    }

    fn from_trades(trades: &[Trade]) -> Self {
        Self {
            timestamps_ms: trades.iter().map(|trade| trade.exit_time_ms).collect(),
        }
    }

    fn count(&self, start_ms: i64, end_ms: i64) -> usize {
        let start = self
            .timestamps_ms
            .partition_point(|timestamp_ms| *timestamp_ms < start_ms);
        let end = self
            .timestamps_ms
            .partition_point(|timestamp_ms| *timestamp_ms < end_ms);
        end.saturating_sub(start)
    }
}

fn accumulate_signal_fill_diagnostics(
    out: &mut SignalFillDiagnosticsMap,
    candidate: &Candidate,
    symbol: &str,
    fold_index: usize,
    diagnostics: &CandidateSignalFillFoldDiagnostics,
    score: &CandidateScore,
) {
    debug_assert_eq!(diagnostics.fold_index, fold_index);
    let key = (
        candidate.indicator.as_str().to_string(),
        candidate.timeframe.as_str().to_string(),
        symbol.to_string(),
        fold_index,
    );
    let row = out.entry(key).or_default();
    row.candidates_evaluated += 1;
    row.raw_signal_bars += diagnostics.raw_signal_bars;
    row.gated_signal_bars += diagnostics.gated_signal_bars;
    row.entry_attempts += diagnostics.entry_attempts;
    row.filled_entries += diagnostics.filled_entries;
    row.closed_trades += diagnostics.closed_trades;
    if score.trades < score.min_trades {
        row.too_sparse += 1;
    } else if score.trades > score.max_trades {
        row.too_active += 1;
    } else if score.quality_fit == BAD_EXIT_GEOMETRY_REJECTION {
        row.bad_exit_geometry += 1;
    } else if score.profit_factor < score.min_profit_factor {
        row.low_profit_factor += 1;
    } else if score.average_trade_return_pct < score.min_average_trade_return_pct {
        row.low_average_trade_edge += 1;
    } else if score.edge_t_stat < score.min_edge_t_stat {
        row.low_edge_confidence += 1;
    } else if score.entry_attempts >= score.min_trades.max(25)
        && score.fill_rate_pct < score.min_fill_rate_pct
    {
        row.low_fill_rate += 1;
    } else if candidate_score_has_low_participation(score) {
        row.low_participation += 1;
    } else if score.net_return_pct <= 0.0 {
        row.eligible_nonpositive_net += 1;
    } else {
        row.eligible_positive_net += 1;
    }
}

fn write_signal_fill_diagnostics(
    run_dir: &Path,
    diagnostics: &SignalFillDiagnosticsMap,
) -> Result<()> {
    let rows = diagnostics
        .iter()
        .map(
            |((indicator, timeframe, symbol, fold_index), row)| SignalFillDiagnosticsRow {
                indicator: indicator.clone(),
                timeframe: timeframe.clone(),
                symbol: symbol.clone(),
                fold_index: *fold_index,
                candidates_evaluated: row.candidates_evaluated,
                raw_signal_bars: row.raw_signal_bars,
                gated_signal_bars: row.gated_signal_bars,
                entry_attempts: row.entry_attempts,
                filled_entries: row.filled_entries,
                closed_trades: row.closed_trades,
                raw_signal_bars_per_candidate: per_candidate(
                    row.raw_signal_bars,
                    row.candidates_evaluated,
                ),
                gated_signal_bars_per_candidate: per_candidate(
                    row.gated_signal_bars,
                    row.candidates_evaluated,
                ),
                entry_attempts_per_candidate: per_candidate(
                    row.entry_attempts,
                    row.candidates_evaluated,
                ),
                fill_rate_pct: pct(row.filled_entries, row.entry_attempts),
                closed_trades_per_candidate: per_candidate(
                    row.closed_trades,
                    row.candidates_evaluated,
                ),
                too_sparse: row.too_sparse,
                too_active: row.too_active,
                bad_exit_geometry: row.bad_exit_geometry,
                low_profit_factor: row.low_profit_factor,
                low_average_trade_edge: row.low_average_trade_edge,
                low_edge_confidence: row.low_edge_confidence,
                low_fill_rate: row.low_fill_rate,
                low_participation: row.low_participation,
                eligible_nonpositive_net: row.eligible_nonpositive_net,
                eligible_positive_net: row.eligible_positive_net,
                eligible_total: row.eligible_nonpositive_net + row.eligible_positive_net,
            },
        )
        .collect::<Vec<_>>();
    write_csv(run_dir.join(SIGNAL_FILL_DIAGNOSTICS_FILE), &rows)
}

fn per_candidate(total: usize, candidates: usize) -> f64 {
    if candidates == 0 {
        0.0
    } else {
        total as f64 / candidates as f64
    }
}

pub fn run_strategy_space_scan(options: SpaceScanOptions) -> Result<PathBuf> {
    let SpaceScanOptions {
        strategy_set,
        symbols,
        fold_index,
        start_offset_days,
        trials,
        is_weeks,
        oos_weeks,
        step_weeks,
        gap_weeks,
    } = options;
    let strategy_set = normalize_strategy_set(Some(strategy_set))
        .unwrap_or_else(|| STRATEGY_4448_KAMA_KER_SET.to_string());
    if strategy_set != STRATEGY_4448_KAMA_KER_SET {
        anyhow::bail!("space-scan currently supports only {STRATEGY_4448_KAMA_KER_SET}");
    }
    validate_tpe_trials(trials)?;
    validate_week_count("is_weeks", is_weeks)?;
    validate_week_count("oos_weeks", oos_weeks)?;
    validate_week_count("step_weeks", step_weeks)?;
    validate_gap_weeks(gap_weeks)?;
    validate_start_offset_days(start_offset_days)?;

    let symbols = {
        let normalized = normalize_symbols(symbols);
        if normalized.is_empty() {
            vec![
                "BTCUSDT".to_string(),
                "ETHUSDT".to_string(),
                "SOLUSDT".to_string(),
                "XRPUSDT".to_string(),
                "SUIUSDT".to_string(),
            ]
        } else {
            normalized
        }
    };
    let mut config = WfoConfig::new(GridSize::Tpe);
    config.run_id = format!("{}-space-scan", Utc::now().format("%Y%m%dT%H%M%SZ"));
    config.symbols = symbols.clone();
    config.strategy_set = Some(strategy_set);
    config.start_offset_days = start_offset_days;
    config.is_weeks = is_weeks;
    config.oos_weeks = oos_weeks;
    config.step_weeks = step_weeks;
    config.gap_weeks = gap_weeks;
    config.tpe_trials = trials;
    config.tpe_random_startup_fraction = 0.0;

    let run_dir = PathBuf::from(RUNS_ROOT).join(format!("space_scan_{}", config.run_id));
    fs::create_dir_all(&run_dir)?;
    write_json(run_dir.join("config.json"), &config)?;
    write_status(
        &run_dir,
        &status(
            &config.run_id,
            RunPhase::Planning,
            1.0,
            "space scan initialized",
        ),
    )?;
    append_event(
        &run_dir,
        "plan",
        &format!(
            "Strategy 4.4.48 space scan: fold {fold_index}, offset {start_offset_days}, {trials} trials"
        ),
    )?;

    let folds = generate_folds_days(
        date_ms(config.start)? + Duration::days(config.start_offset_days).num_milliseconds(),
        date_ms(config.end)?,
        config.effective_is_days(),
        config.effective_oos_days(),
        config.effective_step_days(),
        config.effective_gap_days(),
    );
    let fold = folds
        .get(fold_index)
        .copied()
        .with_context(|| format!("fold_index {fold_index} outside {} folds", folds.len()))?;
    write_csv(run_dir.join("folds.csv"), &folds)?;

    let candidates = strategy_4448_space_scan_candidates(trials);
    write_csv(run_dir.join("candidates.csv"), &candidates)?;

    write_status(
        &run_dir,
        &status(
            &config.run_id,
            RunPhase::LoadingData,
            5.0,
            "loading scan symbols",
        ),
    )?;
    let store = KlineStore::from_env()?;
    let mut data = Vec::new();
    for symbol in &symbols {
        let mut rows = store
            .load_range(symbol, config.start, config.end)
            .unwrap_or_default()
            .iter()
            .map(OhlcvBar::from)
            .filter(|row| {
                row.open_time_ms >= fold.is_start_ms && row.open_time_ms < fold.oos_end_ms
            })
            .collect::<Vec<_>>();
        if rows.is_empty() {
            rows = synthetic_market(
                symbol,
                date_ms(config.start)?,
                ((fold.oos_end_ms - fold.is_start_ms) / MS_PER_MINUTE).max(1) as usize,
            );
            append_event(
                &run_dir,
                "data",
                &format!("{symbol}: using synthetic fallback market"),
            )?;
        } else {
            append_event(
                &run_dir,
                "data",
                &format!(
                    "{symbol}: loaded {} one-minute bars for scan window",
                    rows.len()
                ),
            )?;
        }
        data.push((symbol.clone(), rows));
    }

    write_status(
        &run_dir,
        &status(
            &config.run_id,
            RunPhase::Simulating,
            10.0,
            "running stratified space scan",
        ),
    )?;
    let mut metric_rows = Vec::with_capacity(candidates.len() * data.len() * 3);
    let mut symbol_caches = data
        .iter()
        .map(|_| SimulationCache::default())
        .collect::<Vec<_>>();
    let started = Instant::now();
    let total_work = candidates.len().max(1);
    for (candidate_index, candidate) in candidates.iter().enumerate() {
        for ((symbol, bars), cache) in data.iter().zip(symbol_caches.iter_mut()) {
            let rules = SymbolExecutionRules::for_symbol(symbol)
                .with_context(|| format!("missing execution rules for {symbol}"))?;
            let prepared = prepare_candidate_simulation(symbol, bars, candidate, &config, cache)?;
            let (trades, execution_diagnostics) = simulate_limit_momentum_trades_with_diagnostics(
                symbol,
                bars,
                &prepared.signals_1m,
                ExecutionConfig {
                    symbol_rules: rules,
                    ..prepared.execution
                },
            );
            metric_rows.extend(space_scan_metric_rows_for_candidate(
                candidate,
                symbol,
                fold,
                &config,
                &prepared,
                &trades,
                &execution_diagnostics.entry_attempts,
            ));
        }
        if (candidate_index + 1) % 100 == 0 || candidate_index + 1 == total_work {
            let completed = candidate_index + 1;
            let elapsed_seconds = started.elapsed().as_secs().max(1);
            let eta_seconds =
                ((total_work - completed) as u64 * elapsed_seconds) / completed.max(1) as u64;
            write_status(
                &run_dir,
                &status_with_active(
                    &config.run_id,
                    RunPhase::Simulating,
                    10.0 + 80.0 * completed as f64 / total_work as f64,
                    &format!("space scan {completed}/{total_work} candidates"),
                    ActiveStatus {
                        symbol: None,
                        indicator: Some(IndicatorKind::Strategy4448KamaKer.as_str()),
                        timeframe: Some(Timeframe::M5.as_str()),
                        eta_seconds: Some(eta_seconds),
                        ..ActiveStatus::default()
                    },
                ),
            )?;
        }
    }

    write_status(
        &run_dir,
        &status(
            &config.run_id,
            RunPhase::WritingArtifacts,
            92.0,
            "writing scan artifacts",
        ),
    )?;
    let rejection_summary = space_scan_rejection_summary(&metric_rows);
    let param_summary = space_scan_param_bin_summary(&metric_rows);
    let top_candidates = space_scan_top_candidates(&metric_rows, &candidates, 100);
    write_csv(run_dir.join("candidate_metrics.csv"), &metric_rows)?;
    write_csv(run_dir.join("rejection_summary.csv"), &rejection_summary)?;
    write_csv(run_dir.join("param_bin_summary.csv"), &param_summary)?;
    write_csv(run_dir.join("top_candidates.csv"), &top_candidates)?;
    fs::write(
        run_dir.join("search_space_pulse.html"),
        space_scan_html(
            &config,
            fold,
            &rejection_summary,
            &param_summary,
            &top_candidates,
        ),
    )?;
    write_status(
        &run_dir,
        &status(
            &config.run_id,
            RunPhase::Complete,
            100.0,
            "space scan complete",
        ),
    )?;
    append_event(&run_dir, "complete", "Strategy 4.4.48 space scan complete")?;
    Ok(run_dir)
}

fn strategy_4448_space_scan_candidates(trials: usize) -> Vec<Candidate> {
    const LOOKBACKS: &[usize] = &[
        5, 8, 10, 12, 15, 20, 30, 45, 60, 90, 120, 180, 240, 360, 540, 720,
    ];
    const ATR_PERIODS: &[usize] = &[
        5, 10, 15, 20, 30, 45, 60, 90, 120, 160, 200, 300, 450, 600, 720,
    ];
    const STOPS: &[f64] = &[0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 4.0, 5.0, 7.5, 8.0];
    const TARGETS: &[f64] = &[1.0, 1.5, 2.0, 3.0, 4.0, 5.0, 7.5, 10.0, 12.0];
    const ER_PERIODS: &[usize] = &[5, 8, 10, 12, 15, 20, 30, 45, 60, 90, 120, 160, 200, 240];
    const KAMA_PERIODS: &[usize] = &[2, 3, 5, 8, 13, 20, 30, 45, 60, 80, 100, 120, 140, 160];
    const COUNTS: &[usize] = &[3, 5, 7, 9, 12, 15, 18, 21, 25, 30];
    let mut candidates = Vec::with_capacity(trials);
    for i in 0..trials {
        candidates.push(Candidate {
            id: i,
            indicator: IndicatorKind::Strategy4448KamaKer,
            timeframe: Timeframe::M5,
            signal_polarity: 1,
            entry_mode: EntryMode::Pullback,
            lookback: stratified_value(LOOKBACKS, i, 5, 3),
            atr_period: stratified_value(ATR_PERIODS, i, 7, 5),
            entry_atr_multiple: 0.0,
            stop_atr_multiple: stratified_value(STOPS, i, 5, 7),
            target_atr_multiple: stratified_value(TARGETS, i, 7, 11),
            time_stop_bars: Some(28),
            hurst_min: None,
            hurst_max: None,
            shannon_max: None,
            strategy_4448_kama1_er: stratified_value(ER_PERIODS, i, 5, 3),
            strategy_4448_kama1_short: stratified_value(KAMA_PERIODS, i, 9, 5),
            strategy_4448_kama1_long: stratified_value(KAMA_PERIODS, i, 11, 7),
            strategy_4448_kama2_er: stratified_value(ER_PERIODS, i, 13, 9),
            strategy_4448_kama2_short: stratified_value(KAMA_PERIODS, i, 15, 11),
            strategy_4448_kama2_long: stratified_value(KAMA_PERIODS, i, 17, 13),
            strategy_4448_count_bars: stratified_value(COUNTS, i, 7, 3),
        });
    }
    candidates
}

fn stratified_value<T: Copy>(values: &[T], index: usize, step: usize, cycle_step: usize) -> T {
    let len = values.len();
    let cycle = index / len;
    values[(index * step + cycle * cycle_step) % len]
}

fn space_scan_metric_rows_for_candidate(
    candidate: &Candidate,
    symbol: &str,
    fold: Fold,
    config: &WfoConfig,
    prepared: &PreparedSimulation,
    trades: &[Trade],
    entry_attempts: &[EntryAttempt],
) -> Vec<SpaceScanMetricRow> {
    let (training_start_ms, training_end_ms) = training_window(config, &fold);
    let (selection_start_ms, selection_end_ms) = selection_window(config, &fold);
    [
        ("training", training_start_ms, training_end_ms),
        ("selection", selection_start_ms, selection_end_ms),
        ("oos", fold.oos_start_ms, fold.oos_end_ms),
    ]
    .into_iter()
    .map(|(window, start_ms, end_ms)| {
        let window_trades = trades_for_window(trades, start_ms, end_ms);
        let score = score_trades_in_window(
            symbol,
            candidate,
            fold.index,
            &window_trades,
            config,
            start_ms,
            end_ms,
        );
        let diagnostics = signal_fill_window_diagnostics(
            &prepared.raw_signals_1m,
            &prepared.signals_1m,
            entry_attempts,
            trades,
            start_ms,
            end_ms,
        );
        let fill_rate_pct = fill_rate_pct(&diagnostics);
        SpaceScanMetricRow {
            candidate_id: candidate.id,
            symbol: symbol.to_string(),
            fold_index: fold.index,
            window: window.to_string(),
            window_start_ms: start_ms,
            window_end_ms: end_ms,
            net_return_pct: score.net_return_pct,
            max_drawdown_pct: score.max_drawdown_pct,
            profit_factor: score.profit_factor,
            average_trade_return_pct: score.average_trade_return_pct,
            trades: score.trades,
            min_trades: score.min_trades,
            max_trades: score.max_trades,
            score: score.score,
            rejection_reason: space_scan_rejection_reason(&score, &diagnostics),
            raw_signal_bars: diagnostics.raw_signal_bars,
            gated_signal_bars: diagnostics.gated_signal_bars,
            entry_attempts: diagnostics.entry_attempts,
            filled_entries: diagnostics.filled_entries,
            fill_rate_pct,
            closed_trades: diagnostics.closed_trades,
            lookback: candidate.lookback,
            atr_period: candidate.atr_period,
            stop_atr_multiple: candidate.stop_atr_multiple,
            target_atr_multiple: candidate.target_atr_multiple,
            strategy_4448_kama1_er: candidate.strategy_4448_kama1_er,
            strategy_4448_kama1_short: candidate.strategy_4448_kama1_short,
            strategy_4448_kama1_long: candidate.strategy_4448_kama1_long,
            strategy_4448_kama2_er: candidate.strategy_4448_kama2_er,
            strategy_4448_kama2_short: candidate.strategy_4448_kama2_short,
            strategy_4448_kama2_long: candidate.strategy_4448_kama2_long,
            strategy_4448_count_bars: candidate.strategy_4448_count_bars,
        }
    })
    .collect()
}

fn fill_rate_pct(diagnostics: &CandidateSignalFillFoldDiagnostics) -> f64 {
    if diagnostics.entry_attempts == 0 {
        0.0
    } else {
        diagnostics.filled_entries as f64 / diagnostics.entry_attempts as f64 * 100.0
    }
}

fn low_fill_rate(entry_attempts: usize, fill_rate_pct: f64) -> bool {
    entry_attempts >= 25 && fill_rate_pct < 2.0
}

fn space_scan_rejection_reason(
    score: &CandidateScore,
    diagnostics: &CandidateSignalFillFoldDiagnostics,
) -> String {
    if score.trades < score.min_trades {
        "too_sparse".to_string()
    } else if score.trades > score.max_trades {
        "too_active".to_string()
    } else if score.quality_fit == BAD_EXIT_GEOMETRY_REJECTION {
        BAD_EXIT_GEOMETRY_REJECTION.to_string()
    } else if score.profit_factor < score.min_profit_factor {
        "low_profit_factor".to_string()
    } else if score.average_trade_return_pct < score.min_average_trade_return_pct {
        "low_average_trade_edge".to_string()
    } else if score.edge_t_stat < score.min_edge_t_stat {
        "low_edge_confidence".to_string()
    } else if score.net_return_pct <= 0.0 {
        "nonpositive_net".to_string()
    } else if low_fill_rate(diagnostics.entry_attempts, fill_rate_pct(diagnostics)) {
        "low_fill_rate".to_string()
    } else if candidate_score_has_low_participation(score) {
        "low_participation".to_string()
    } else if score.score < MIN_SELECTABLE_SCORE {
        "negative_final_score".to_string()
    } else {
        "selectable".to_string()
    }
}

fn space_scan_rejection_summary(rows: &[SpaceScanMetricRow]) -> Vec<SpaceScanRejectionSummaryRow> {
    let mut totals = BTreeMap::<(String, String), usize>::new();
    let mut counts = BTreeMap::<(String, String, String), usize>::new();
    for row in rows {
        *totals
            .entry((row.symbol.clone(), row.window.clone()))
            .or_default() += 1;
        *counts
            .entry((
                row.symbol.clone(),
                row.window.clone(),
                row.rejection_reason.clone(),
            ))
            .or_default() += 1;
    }
    counts
        .into_iter()
        .map(|((symbol, window, rejection_reason), candidates)| {
            let total = totals
                .get(&(symbol.clone(), window.clone()))
                .copied()
                .unwrap_or(candidates)
                .max(1);
            SpaceScanRejectionSummaryRow {
                symbol,
                window,
                rejection_reason,
                candidates,
                candidates_pct: candidates as f64 / total as f64 * 100.0,
            }
        })
        .collect()
}

#[derive(Debug, Default)]
struct SpaceScanParamBinAccumulator {
    candidates: usize,
    selectable: usize,
    low_fill_rate: usize,
    score_sum: f64,
    net_sum: f64,
    trades_sum: usize,
    fill_rate_sum: f64,
}

fn space_scan_param_bin_summary(rows: &[SpaceScanMetricRow]) -> Vec<SpaceScanParamBinSummaryRow> {
    let mut accumulators =
        BTreeMap::<(String, String, String), SpaceScanParamBinAccumulator>::new();
    for row in rows.iter().filter(|row| row.window == "selection") {
        for (parameter, bin) in space_scan_param_bins(row) {
            let acc = accumulators
                .entry((parameter, bin, row.window.clone()))
                .or_default();
            acc.candidates += 1;
            if row.score >= MIN_SELECTABLE_SCORE && row.rejection_reason == "selectable" {
                acc.selectable += 1;
            }
            if row.rejection_reason == "low_fill_rate" {
                acc.low_fill_rate += 1;
            }
            acc.score_sum += row.score;
            acc.net_sum += row.net_return_pct;
            acc.trades_sum += row.trades;
            acc.fill_rate_sum += row.fill_rate_pct;
        }
    }
    accumulators
        .into_iter()
        .map(|((parameter, bin, window), acc)| {
            let candidates = acc.candidates.max(1);
            SpaceScanParamBinSummaryRow {
                parameter,
                bin,
                window,
                candidates: acc.candidates,
                selectable: acc.selectable,
                selectable_pct: acc.selectable as f64 / candidates as f64 * 100.0,
                low_fill_rate: acc.low_fill_rate,
                low_fill_rate_pct: acc.low_fill_rate as f64 / candidates as f64 * 100.0,
                average_score: acc.score_sum / candidates as f64,
                average_net_return_pct: acc.net_sum / candidates as f64,
                average_trades: acc.trades_sum as f64 / candidates as f64,
                average_fill_rate_pct: acc.fill_rate_sum / candidates as f64,
            }
        })
        .collect()
}

fn space_scan_param_bins(row: &SpaceScanMetricRow) -> Vec<(String, String)> {
    vec![
        ("lookback".to_string(), row.lookback.to_string()),
        ("atr_period".to_string(), row.atr_period.to_string()),
        (
            "stop_atr_multiple".to_string(),
            format!("{:.2}", row.stop_atr_multiple),
        ),
        (
            "target_atr_multiple".to_string(),
            format!("{:.2}", row.target_atr_multiple),
        ),
        (
            "kama1_er".to_string(),
            row.strategy_4448_kama1_er.to_string(),
        ),
        (
            "kama1_short".to_string(),
            row.strategy_4448_kama1_short.to_string(),
        ),
        (
            "kama1_long".to_string(),
            row.strategy_4448_kama1_long.to_string(),
        ),
        (
            "kama2_er".to_string(),
            row.strategy_4448_kama2_er.to_string(),
        ),
        (
            "kama2_short".to_string(),
            row.strategy_4448_kama2_short.to_string(),
        ),
        (
            "kama2_long".to_string(),
            row.strategy_4448_kama2_long.to_string(),
        ),
        (
            "count_bars".to_string(),
            row.strategy_4448_count_bars.to_string(),
        ),
    ]
}

#[derive(Debug, Default)]
struct SpaceScanTopAccumulator {
    candidate: Option<Candidate>,
    selectable_symbols: usize,
    base_pass_symbols: usize,
    selection_symbols: usize,
    selection_score_sum: f64,
    selection_net_sum: f64,
    selection_profit_factor_sum: f64,
    selection_trades_total: usize,
    selection_fill_rate_sum: f64,
    oos_symbols: usize,
    oos_net_sum: f64,
    oos_profit_factor_sum: f64,
    oos_trades_total: usize,
}

fn space_scan_top_candidates(
    rows: &[SpaceScanMetricRow],
    candidates: &[Candidate],
    limit: usize,
) -> Vec<SpaceScanTopCandidateRow> {
    let candidates_by_id = candidates
        .iter()
        .map(|candidate| (candidate.id, candidate.clone()))
        .collect::<BTreeMap<_, _>>();
    let mut by_candidate = BTreeMap::<usize, SpaceScanTopAccumulator>::new();
    for row in rows {
        let acc = by_candidate.entry(row.candidate_id).or_default();
        acc.candidate = candidates_by_id.get(&row.candidate_id).cloned();
        if row.window == "selection" {
            acc.selection_symbols += 1;
            acc.selection_score_sum += row.score;
            acc.selection_net_sum += row.net_return_pct;
            acc.selection_profit_factor_sum += row.profit_factor;
            acc.selection_trades_total += row.trades;
            acc.selection_fill_rate_sum += row.fill_rate_pct;
            if row.rejection_reason == "selectable" {
                acc.selectable_symbols += 1;
            }
            if !matches!(
                row.rejection_reason.as_str(),
                "too_sparse"
                    | "too_active"
                    | "bad_exit_geometry"
                    | "low_profit_factor"
                    | "low_average_trade_edge"
                    | "low_edge_confidence"
                    | "nonpositive_net"
            ) {
                acc.base_pass_symbols += 1;
            }
        } else if row.window == "oos" {
            acc.oos_symbols += 1;
            acc.oos_net_sum += row.net_return_pct;
            acc.oos_profit_factor_sum += row.profit_factor;
            acc.oos_trades_total += row.trades;
        }
    }
    let mut rows = by_candidate
        .into_iter()
        .filter_map(|(candidate_id, acc)| {
            let candidate = acc.candidate?;
            let selection_symbols = acc.selection_symbols.max(1);
            let oos_symbols = acc.oos_symbols.max(1);
            Some(SpaceScanTopCandidateRow {
                rank: 0,
                candidate_id,
                selectable_symbols: acc.selectable_symbols,
                base_pass_symbols: acc.base_pass_symbols,
                selection_score_avg: acc.selection_score_sum / selection_symbols as f64,
                selection_net_return_avg_pct: acc.selection_net_sum / selection_symbols as f64,
                selection_profit_factor_avg: acc.selection_profit_factor_sum
                    / selection_symbols as f64,
                selection_trades_total: acc.selection_trades_total,
                selection_fill_rate_avg_pct: acc.selection_fill_rate_sum / selection_symbols as f64,
                oos_net_return_total_pct: acc.oos_net_sum,
                oos_profit_factor_avg: acc.oos_profit_factor_sum / oos_symbols as f64,
                oos_trades_total: acc.oos_trades_total,
                lookback: candidate.lookback,
                atr_period: candidate.atr_period,
                stop_atr_multiple: candidate.stop_atr_multiple,
                target_atr_multiple: candidate.target_atr_multiple,
                strategy_4448_kama1_er: candidate.strategy_4448_kama1_er,
                strategy_4448_kama1_short: candidate.strategy_4448_kama1_short,
                strategy_4448_kama1_long: candidate.strategy_4448_kama1_long,
                strategy_4448_kama2_er: candidate.strategy_4448_kama2_er,
                strategy_4448_kama2_short: candidate.strategy_4448_kama2_short,
                strategy_4448_kama2_long: candidate.strategy_4448_kama2_long,
                strategy_4448_count_bars: candidate.strategy_4448_count_bars,
            })
        })
        .collect::<Vec<_>>();
    rows.sort_by(|left, right| {
        right
            .selectable_symbols
            .cmp(&left.selectable_symbols)
            .then_with(|| right.base_pass_symbols.cmp(&left.base_pass_symbols))
            .then_with(|| {
                right
                    .selection_score_avg
                    .partial_cmp(&left.selection_score_avg)
                    .unwrap_or(std::cmp::Ordering::Equal)
            })
    });
    rows.truncate(limit);
    for (index, row) in rows.iter_mut().enumerate() {
        row.rank = index + 1;
    }
    rows
}

fn space_scan_html(
    config: &WfoConfig,
    fold: Fold,
    rejection_summary: &[SpaceScanRejectionSummaryRow],
    param_summary: &[SpaceScanParamBinSummaryRow],
    top_candidates: &[SpaceScanTopCandidateRow],
) -> String {
    let selection_rejections = rejection_summary
        .iter()
        .filter(|row| row.window == "selection")
        .map(|row| {
            format!(
                "<tr><td>{}</td><td>{}</td><td class=\"num\">{}</td><td class=\"num\">{:.1}%</td></tr>",
                html_escape(&row.symbol),
                html_escape(&row.rejection_reason),
                row.candidates,
                row.candidates_pct
            )
        })
        .collect::<String>();
    let param_rows = param_summary
        .iter()
        .filter(|row| row.window == "selection")
        .map(|row| {
            format!(
                "<tr><td>{}</td><td>{}</td><td class=\"num\">{}</td><td class=\"num\">{:.1}%</td><td class=\"num\">{:.1}%</td><td class=\"num\">{:.2}</td><td class=\"num\">{:.2}%</td><td class=\"num\">{:.1}</td><td class=\"num\">{:.2}%</td></tr>",
                html_escape(&row.parameter),
                html_escape(&row.bin),
                row.candidates,
                row.selectable_pct,
                row.low_fill_rate_pct,
                row.average_score,
                row.average_net_return_pct,
                row.average_trades,
                row.average_fill_rate_pct
            )
        })
        .collect::<String>();
    let top_rows = top_candidates
        .iter()
        .take(30)
        .map(|row| {
            format!(
                "<tr><td class=\"num\">{}</td><td class=\"num\">{}</td><td class=\"num\">{}</td><td class=\"num\">{}</td><td class=\"num\">{:.2}</td><td class=\"num\">{:.2}%</td><td class=\"num\">{:.2}</td><td class=\"num\">{}</td><td class=\"num\">{:.2}%</td><td class=\"num\">{:.2}%</td><td class=\"num\">{}</td><td class=\"params\">lb={} atr={} stop={:.2} tgt={:.2} k1={}/{}/{} k2={}/{}/{} count={}</td></tr>",
                row.rank,
                row.candidate_id,
                row.selectable_symbols,
                row.base_pass_symbols,
                row.selection_score_avg,
                row.selection_net_return_avg_pct,
                row.selection_profit_factor_avg,
                row.selection_trades_total,
                row.selection_fill_rate_avg_pct,
                row.oos_net_return_total_pct,
                row.oos_trades_total,
                row.lookback,
                row.atr_period,
                row.stop_atr_multiple,
                row.target_atr_multiple,
                row.strategy_4448_kama1_er,
                row.strategy_4448_kama1_short,
                row.strategy_4448_kama1_long,
                row.strategy_4448_kama2_er,
                row.strategy_4448_kama2_short,
                row.strategy_4448_kama2_long,
                row.strategy_4448_count_bars
            )
        })
        .collect::<String>();
    format!(
        r#"<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Strategy 4.4.48 Search Space Pulse</title>
<style>
:root{{color-scheme:dark;background:#0d1114;color:#dce4ea;font-family:Inter,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}}
body{{margin:0;padding:18px;background:#0d1114}}h1{{font-size:18px;margin:0 0 6px}}h2{{font-size:14px;margin:22px 0 8px;color:#f2f6f8}}.muted{{color:#92a0aa;font-size:12px}}
.grid{{display:grid;grid-template-columns:repeat(4,minmax(150px,1fr));gap:8px;margin:14px 0}}.stat{{border:1px solid #243039;background:#12181d;padding:10px;border-radius:6px}}.stat b{{display:block;font-size:12px;color:#92a0aa}}.stat span{{font-size:16px}}
table{{width:100%;border-collapse:collapse;font-size:12px;background:#11171b;border:1px solid #27323a}}th,td{{border-bottom:1px solid #27323a;padding:6px 8px;text-align:left;white-space:nowrap}}th{{position:sticky;top:0;background:#172027;color:#aebbc4}}.num{{text-align:right;font-variant-numeric:tabular-nums}}.params{{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:11px}}.wrap{{overflow:auto;max-height:520px;border:1px solid #27323a}}a{{color:#7db4ff}}
</style></head><body>
<h1>Strategy 4.4.48 Search Space Pulse</h1>
<div class="muted">Run {} · fold {} · offset {} days · selection {} to {} · OOS {} to {}</div>
<div class="grid">
<div class="stat"><b>Symbols</b><span>{}</span></div>
<div class="stat"><b>Trials</b><span>{}</span></div>
<div class="stat"><b>IS / OOS</b><span>{}w / {}w</span></div>
<div class="stat"><b>Candidate Metrics</b><span>candidate_metrics.csv</span></div>
</div>
<h2>Top Candidates</h2><div class="wrap"><table><tr><th>Rank</th><th>Candidate</th><th>Selectable Symbols</th><th>Base Pass Symbols</th><th>Sel Score</th><th>Sel Net</th><th>Sel PF</th><th>Sel Trades</th><th>Sel Fill</th><th>OOS Net Sum</th><th>OOS Trades</th><th>Params</th></tr>{top_rows}</table></div>
<h2>Selection Rejections</h2><div class="wrap"><table><tr><th>Symbol</th><th>Reason</th><th>Candidates</th><th>Share</th></tr>{selection_rejections}</table></div>
<h2>Parameter Bins, Selection Window</h2><div class="wrap"><table><tr><th>Parameter</th><th>Bin</th><th>Candidates</th><th>Selectable</th><th>Low Fill</th><th>Avg Score</th><th>Avg Net</th><th>Avg Trades</th><th>Avg Fill</th></tr>{param_rows}</table></div>
</body></html>"#,
        html_escape(&config.run_id),
        fold.index,
        config.start_offset_days,
        html_escape(&format_ms_utc(fold.is_start_ms)),
        html_escape(&format_ms_utc(fold.is_end_ms)),
        html_escape(&format_ms_utc(fold.oos_start_ms)),
        html_escape(&format_ms_utc(fold.oos_end_ms)),
        html_escape(&config.symbols.join(", ")),
        config.tpe_trials,
        config.is_weeks,
        config.oos_weeks,
    )
}

fn format_ms_utc(timestamp_ms: i64) -> String {
    Utc.timestamp_millis_opt(timestamp_ms)
        .single()
        .map(|dt| dt.format("%Y-%m-%d %H:%M UTC").to_string())
        .unwrap_or_else(|| timestamp_ms.to_string())
}

#[allow(clippy::too_many_arguments)]
fn run_tpe_strategy(
    run_dir: &Path,
    config: &WfoConfig,
    folds: &[Fold],
    data: &[(String, Vec<OhlcvBar>)],
    candidates: &mut [Candidate],
    strategy_progress: &mut [StrategyRow],
    active_strategy_key: &(String, String),
    group_candidates: &[Candidate],
    strategy_totals: &BTreeMap<(String, String), usize>,
    progress_counts: &mut BTreeMap<(String, String), usize>,
    completed_work: &mut usize,
    total_work: usize,
    progress_every: usize,
    started: Instant,
    best_by_fold: &mut BTreeMap<usize, FoldSelection>,
    strategy_oos_by_symbol_fold: &mut BTreeMap<(String, String, String, usize), FoldSelection>,
    signal_fill_diagnostics: &mut SignalFillDiagnosticsMap,
    close_by_symbol: &BTreeMap<String, BTreeMap<i64, f64>>,
) -> Result<()> {
    let row_total = strategy_totals
        .get(active_strategy_key)
        .copied()
        .unwrap_or(group_candidates.len())
        .max(1);
    let startup_trials = ((config.tpe_trials as f64 * config.tpe_random_startup_fraction).ceil()
        as usize)
        .clamp(1, config.tpe_trials.max(1));
    let tpe_seed_part = config
        .tpe_seed
        .map_or_else(|| config.run_id.clone(), |seed| seed.to_string());
    let sampler = TpeSampler::builder()
        .n_startup_trials(startup_trials)
        .n_ei_candidates(TPE_CANDIDATES_PER_TRIAL)
        .seed(stable_seed(&[
            &tpe_seed_part,
            active_strategy_key.0.as_str(),
            active_strategy_key.1.as_str(),
        ]))
        .build()?;
    let study: Study<f64> = Study::with_sampler(Direction::Maximize, sampler);
    let search_message = if active_strategy_key.0 == IndicatorKind::Strategy4448KamaKer.as_str() {
        format!(
            "{} {}: Strategy 4.4.48 TPE ranges KER/lookback 5-120 bars, ATR 20-200 bars step 5, KAMA1 ER 5-120, KAMA1 short 2-120, KAMA1 long 2-160, KAMA2 ER 5-60, KAMA2 short 2-30, KAMA2 long 2-160, count 3-15 bars, stop ATR {:.2}-{:.2}, target ATR 2.00-{:.2}, target/stop <= {:.1}R, fixed 28-bar time stop, random startup {:.0}%, low-fill gate {:.1}%",
            active_strategy_key.0,
            active_strategy_key.1,
            MIN_EXIT_STOP_ATR_MULTIPLE,
            MAX_EXIT_STOP_ATR_MULTIPLE,
            MAX_EXIT_TARGET_ATR_MULTIPLE,
            MAX_EXIT_TARGET_STOP_RATIO,
            config.tpe_random_startup_fraction * 100.0,
            MIN_FILL_RATE_SCORE_PCT
        )
    } else if active_strategy_key.0.starts_with("strategy_3") {
        format!(
            "{} {}: SQX KAMA/TPO fixed-source strategy; WFO selection uses source params, candidate gate PF {:.2}, low-fill gate {:.1}%",
            active_strategy_key.0,
            active_strategy_key.1,
            config.min_profit_factor,
            MIN_FILL_RATE_SCORE_PCT
        )
    } else {
        format!(
            "{} {}: TPE search ranges lookback {}-{} signal bars, ATR {}-{} signal bars step {}, entry ATR 0.00-{:.2}, stop ATR {:.2}-{:.2}, target ATR {:.2}-{:.2}, target/stop <= {:.1}R, time stop 0-{} signal bars",
            active_strategy_key.0,
            active_strategy_key.1,
            TPE_MIN_LOOKBACK_BARS,
            TPE_MAX_LOOKBACK_BARS,
            TPE_MIN_ATR_BARS,
            TPE_MAX_ATR_BARS,
            TPE_ATR_STEP_BARS,
            TPE_MAX_ENTRY_ATR_MULTIPLE,
            MIN_EXIT_STOP_ATR_MULTIPLE,
            MAX_EXIT_STOP_ATR_MULTIPLE,
            TPE_MIN_TARGET_ATR_MULTIPLE,
            MAX_EXIT_TARGET_ATR_MULTIPLE,
            MAX_EXIT_TARGET_STOP_RATIO,
            TPE_MAX_TIME_STOP_BARS
        )
    };
    let search_space = TpeSearchSpace::new();
    append_event(run_dir, "search", &search_message)?;
    let mut symbol_caches = data
        .iter()
        .map(|_| SimulationCache::default())
        .collect::<Vec<_>>();
    let mut best_trial: Option<TpeTrialEvaluation> = None;
    let mut tpe_trial_trace = Vec::with_capacity(group_candidates.len());

    for template in group_candidates {
        let mut trial = study.ask();
        let candidate = search_space.suggest(&mut trial, template)?;
        if let Some(slot) = candidates.iter_mut().find(|slot| slot.id == candidate.id) {
            *slot = candidate.clone();
        }

        let mut trial_scores = Vec::new();
        let mut training_scores = Vec::new();
        let mut trial_trade_count = 0usize;
        let mut pending_strategy_selections = Vec::new();
        let mut pending_best_selections = Vec::new();
        let trial_results = data
            .par_iter()
            .zip(symbol_caches.par_iter_mut())
            .map(
                |((symbol, bars), cache)| -> Result<Option<SimulationResult>> {
                    if !candidate_allowed_for_symbol(
                        config.strategy_set.as_deref(),
                        symbol,
                        &candidate,
                    ) {
                        return Ok(None);
                    }
                    let prepared =
                        prepare_candidate_simulation(symbol, bars, &candidate, config, cache)?;
                    Ok(Some(simulate_prepared_candidate(bars, &prepared, folds)))
                },
            )
            .collect::<Result<Vec<_>>>()?
            .into_iter()
            .flatten()
            .collect::<Vec<_>>();
        for result in trial_results {
            trial_trade_count += result.trades.len();
            for (fold_pos, fold) in folds.iter().enumerate() {
                let training_trades = training_trades_for_fold(&result.trades, config, fold);
                let (training_start_ms, training_end_ms) = training_window(config, fold);
                let training_score = score_trades_in_window(
                    result.symbol.as_str(),
                    &result.candidate,
                    fold.index,
                    &training_trades,
                    config,
                    training_start_ms,
                    training_end_ms,
                );
                let fold_trades = selection_trades_for_fold(&result.trades, config, fold);
                let fold_diagnostics = result
                    .fold_diagnostics
                    .get(fold_pos)
                    .cloned()
                    .unwrap_or_default();
                let score = score_trades_with_diagnostics(
                    result.symbol.as_str(),
                    &result.candidate,
                    fold.index,
                    fold,
                    &fold_trades,
                    config,
                    &fold_diagnostics,
                );
                accumulate_signal_fill_diagnostics(
                    signal_fill_diagnostics,
                    &candidate,
                    result.symbol.as_str(),
                    fold.index,
                    &fold_diagnostics,
                    &score,
                );
                let selection_evaluation = fold_selection_evaluation(
                    config,
                    result.symbol.as_str(),
                    &candidate,
                    fold,
                    &result.trades,
                    &training_score,
                    &score,
                );
                let strategy_oos_key = (
                    candidate.indicator.as_str().to_string(),
                    candidate.timeframe.as_str().to_string(),
                    result.symbol.clone(),
                    fold.index,
                );
                if let Some(selection) = strict_fold_selection(
                    &selection_evaluation,
                    candidate.indicator,
                    oos_trades_for_fold(&result.trades, fold),
                ) {
                    pending_best_selections.push((
                        selection_evaluation.objective_score.fold_index,
                        selection.clone(),
                    ));
                    pending_strategy_selections.push((strategy_oos_key, selection));
                }
                training_scores.push(training_score);
                trial_scores.push(selection_evaluation.objective_score);
            }
        }

        let objective = tpe_objective_breakdown(&training_scores, &trial_scores);
        let candidate_score = objective.objective_score;
        let rank_adjustment = tpe_candidate_rank_adjustment(config, &candidate, &objective);
        for (key, selection) in pending_strategy_selections {
            insert_strategy_fold_selection(
                strategy_oos_by_symbol_fold,
                key,
                adjusted_fold_selection(selection, rank_adjustment),
            );
        }
        for (fold_index, selection) in pending_best_selections {
            insert_best_fold_selection(
                best_by_fold,
                fold_index,
                adjusted_fold_selection(selection, rank_adjustment),
            );
        }
        study.tell(trial, Ok::<f64, &'static str>(candidate_score));
        if best_trial
            .as_ref()
            .map(|best| candidate_score > best.mean_score)
            .unwrap_or(true)
        {
            best_trial = Some(TpeTrialEvaluation {
                candidate: candidate.clone(),
                mean_score: candidate_score,
            });
        }
        let best = best_trial
            .as_ref()
            .expect("best trial is set after scoring");

        let candidate_key = strategy_key(&candidate);
        *progress_counts.entry(candidate_key.clone()).or_default() += 1;
        let row_completed = progress_counts
            .get(&candidate_key)
            .copied()
            .unwrap_or_default();
        tpe_trial_trace.push(TpeTrialTraceRow {
            trial_index: row_completed,
            fold_index: None,
            candidate_id: candidate.id,
            indicator: candidate.indicator.as_str().to_string(),
            timeframe: candidate.timeframe.as_str().to_string(),
            objective_score: candidate_score,
            best_objective_score: best.mean_score,
            best_candidate_id: best.candidate.id,
            training_mean_score: objective.training_mean_score,
            validation_mean_score: objective.validation_mean_score,
            training_q25_score: objective.training_q25_score,
            training_median_score: objective.training_median_score,
            validation_q25_score: objective.validation_q25_score,
            validation_median_score: objective.validation_median_score,
            validation_score_stddev: objective.validation_score_stddev,
            training_eligible_fraction: objective.training_eligible_fraction,
            validation_eligible_fraction: objective.validation_eligible_fraction,
            validation_net_positive_fraction: objective.validation_net_positive_fraction,
            validation_trade_fit_fraction: objective.validation_trade_fit_fraction,
            validation_quality_fit_fraction: objective.validation_quality_fit_fraction,
            validation_median_profit_factor: objective.validation_median_profit_factor,
            training_nonnegative_score_fraction: objective.training_nonnegative_score_fraction,
            validation_nonnegative_score_fraction: objective.validation_nonnegative_score_fraction,
            average_trade_penalty: objective.average_trade_penalty,
            average_profit_factor_penalty: objective.average_profit_factor_penalty,
            average_net_penalty: objective.average_net_penalty,
            average_fill_penalty: objective.average_fill_penalty,
            average_participation_penalty: objective.average_participation_penalty,
            base_objective_component: objective.base_objective_component,
            consistency_bonus: objective.consistency_bonus,
            paired_bonus: objective.paired_bonus,
            paired_selection_fraction: objective.paired_selection_fraction,
            paired_selection_count: objective.paired_selection_count,
            train_gap_penalty: objective.train_gap_penalty,
            dispersion_penalty: objective.dispersion_penalty,
            training_scores: training_scores.len(),
            validation_scores: trial_scores.len(),
            trial_trade_count,
            lookback: candidate.lookback,
            atr_period: candidate.atr_period,
            entry_atr_multiple: candidate.entry_atr_multiple,
            stop_atr_multiple: candidate.stop_atr_multiple,
            target_atr_multiple: candidate.target_atr_multiple,
            time_stop_bars: candidate.time_stop_bars,
            strategy_4448_kama1_er: candidate.strategy_4448_kama1_er,
            strategy_4448_kama1_short: candidate.strategy_4448_kama1_short,
            strategy_4448_kama1_long: candidate.strategy_4448_kama1_long,
            strategy_4448_kama2_er: candidate.strategy_4448_kama2_er,
            strategy_4448_kama2_short: candidate.strategy_4448_kama2_short,
            strategy_4448_kama2_long: candidate.strategy_4448_kama2_long,
            strategy_4448_count_bars: candidate.strategy_4448_count_bars,
        });
        update_strategy_row(
            strategy_progress,
            &candidate_key,
            candidate_score,
            &trial_scores,
            trial_trade_count,
            row_completed,
            row_total,
        );
        *completed_work += 1;
        if row_completed % progress_every == 0
            || row_completed == row_total
            || *completed_work == total_work
        {
            let elapsed_seconds = started.elapsed().as_secs().max(1);
            let eta_seconds = ((total_work - *completed_work) as u64 * elapsed_seconds)
                / (*completed_work).max(1) as u64;
            let progress_pct = 15.0 + 75.0 * *completed_work as f64 / total_work as f64;
            write_status(
                run_dir,
                &status_with_active(
                    &config.run_id,
                    RunPhase::Simulating,
                    progress_pct,
                    &format!("sampled {}/{total_work} TPE trials", *completed_work),
                    ActiveStatus {
                        symbol: None,
                        indicator: Some(candidate.indicator.as_str()),
                        timeframe: Some(candidate.timeframe.as_str()),
                        eta_seconds: Some(eta_seconds),
                        ..ActiveStatus::default()
                    },
                ),
            )?;
            write_strategy_progress(run_dir, strategy_progress)?;
            write_strategy_oos_status_snapshot(run_dir, strategy_progress)?;
            write_csv(run_dir.join(TPE_TRIALS_FILE), &tpe_trial_trace)?;
            let fold_scores = best_by_fold
                .values()
                .map(|selection| selection.score.clone())
                .collect::<Vec<_>>();
            write_csv(run_dir.join("best_by_indicator.csv"), &fold_scores)?;
            write_csv(run_dir.join("candidates.csv"), candidates)?;
            append_event(
                run_dir,
                "progress",
                &format!(
                    "{}/{}: {} {} TPE trial {row_completed}/{row_total}",
                    *completed_work,
                    total_work,
                    candidate.indicator.as_str(),
                    candidate.timeframe.as_str()
                ),
            )?;
        }
    }

    if let Some(best) = best_trial {
        write_csv(run_dir.join(TPE_TRIALS_FILE), &tpe_trial_trace)?;
        append_event(
            run_dir,
            "tpe",
            &format!(
                "{} {}: best sampled candidate {} score {:.3}",
                active_strategy_key.0, active_strategy_key.1, best.candidate.id, best.mean_score
            ),
        )?;
    }
    let _ = close_by_symbol;
    Ok(())
}

fn execution_time_stop_bars(candidate: &Candidate) -> Option<usize> {
    candidate
        .time_stop_bars
        .map(|bars| bars.saturating_mul(candidate.timeframe.minutes() as usize))
}

fn entry_order_valid_bars(candidate: &Candidate) -> usize {
    if matches!(
        candidate.indicator,
        IndicatorKind::Strategy336KamaTpo
            | IndicatorKind::Strategy3635KamaTpo
            | IndicatorKind::Strategy3938KamaTpo
    ) {
        199usize.saturating_mul(candidate.timeframe.minutes() as usize)
    } else if candidate.indicator == IndicatorKind::Strategy4448KamaKer {
        3usize.saturating_mul(candidate.timeframe.minutes() as usize)
    } else {
        1
    }
}

fn minutes_to_timeframe_bars(minutes: i64, timeframe: Timeframe, min_bars: usize) -> usize {
    let timeframe_minutes = timeframe.minutes().max(1) as usize;
    let minutes = minutes.max(1) as usize;
    minutes.div_ceil(timeframe_minutes).max(min_bars)
}

fn minutes_to_timeframe_bars_capped(
    minutes: i64,
    timeframe: Timeframe,
    min_bars: usize,
    max_bars: usize,
) -> usize {
    minutes_to_timeframe_bars(minutes, timeframe, min_bars).min(max_bars.max(min_bars))
}

fn expand_signals(
    bars_1m: &[OhlcvBar],
    tf_signals: &[crate::indicators::SignalPoint],
    timeframe: Timeframe,
) -> Vec<crate::indicators::SignalPoint> {
    let availability_delay_ms = (timeframe.minutes() - 1).max(0) * MS_PER_MINUTE;
    let mut by_time = BTreeMap::new();
    for signal in tf_signals {
        by_time.insert(signal.timestamp_ms + availability_delay_ms, *signal);
    }
    let mut current = crate::indicators::SignalPoint {
        timestamp_ms: 0,
        direction: 0,
        strength: 0.0,
        atr: 0.0,
        entry_reference: None,
    };
    bars_1m
        .iter()
        .map(|bar| {
            if let Some(signal) = by_time.get(&bar.open_time_ms) {
                current = *signal;
            }
            crate::indicators::SignalPoint {
                timestamp_ms: bar.open_time_ms,
                ..current
            }
        })
        .collect()
}

fn validate_indicator_group(group: Option<&str>) -> Result<()> {
    match group {
        None | Some("ehlers") => Ok(()),
        Some(other) => anyhow::bail!("unknown indicator group {other}; supported: ehlers"),
    }
}

fn validate_strategy_set(strategy_set: Option<&str>) -> Result<()> {
    match strategy_set {
        None
        | Some(SUSPICIOUS_SHORTLIST_SET)
        | Some(CALIBRATION_AUDIT_SET)
        | Some(PORTFOLIO_CANDIDATES_SET)
        | Some(LOW_TURNOVER_EXTRA_SET)
        | Some(SECOND_PASS_PORTFOLIO_SET)
        | Some(ROBUST_PORTFOLIO_SET)
        | Some(GOAL_SEARCH_SET)
        | Some(HIGH_TRADE_GOAL_SET)
        | Some(HIGH_TRADE_REFINE_SET)
        | Some(PORTFOLIO_REFINE_SET)
        | Some(QUALITY_HUNT_SET)
        | Some(Q3_DIVERSIFIERS_SET)
        | Some(BEST_COMBO_CONFIRM_SET)
        | Some(FRAMA_5M_CONFIRM_SET)
        | Some(STRATEGY_336_KAMA_TPO_SET)
        | Some(STRATEGY_3635_KAMA_TPO_SET)
        | Some(STRATEGY_3938_KAMA_TPO_SET)
        | Some(STRATEGY_4448_KAMA_KER_SET)
        | Some(STRATEGY_33X_SQX_SET)
        | Some(ELEGANT_5M_SET)
        | Some(ELEGANT_5M_ENTRY50_SET)
        | Some(ELEGANT_5M_ENTRY50_GATED_SET)
        | Some(ELEGANT_5M_ENTRY50_UNGATED_SET)
        | Some(ELEGANT_5M_HYBRID_SET) => Ok(()),
        Some(other) => {
            anyhow::bail!(
                "unknown strategy set {other}; supported: {SUSPICIOUS_SHORTLIST_SET}, {CALIBRATION_AUDIT_SET}, {PORTFOLIO_CANDIDATES_SET}, {LOW_TURNOVER_EXTRA_SET}, {SECOND_PASS_PORTFOLIO_SET}, {ROBUST_PORTFOLIO_SET}, {GOAL_SEARCH_SET}, {HIGH_TRADE_GOAL_SET}, {HIGH_TRADE_REFINE_SET}, {PORTFOLIO_REFINE_SET}, {QUALITY_HUNT_SET}, {Q3_DIVERSIFIERS_SET}, {BEST_COMBO_CONFIRM_SET}, {FRAMA_5M_CONFIRM_SET}, {STRATEGY_336_KAMA_TPO_SET}, {STRATEGY_3635_KAMA_TPO_SET}, {STRATEGY_3938_KAMA_TPO_SET}, {STRATEGY_4448_KAMA_KER_SET}, {STRATEGY_33X_SQX_SET}, {ELEGANT_5M_SET}, {ELEGANT_5M_ENTRY50_SET}, {ELEGANT_5M_ENTRY50_GATED_SET}, {ELEGANT_5M_ENTRY50_UNGATED_SET}, {ELEGANT_5M_HYBRID_SET}"
            )
        }
    }
}

fn validate_grid_scope(
    grid: GridSize,
    indicator_group: Option<&str>,
    strategy_set: Option<&str>,
) -> Result<()> {
    if grid == GridSize::Probe && indicator_group.is_none() && strategy_set.is_none() {
        anyhow::bail!("probe grid requires --indicator-group or --strategy-set")
    }
    Ok(())
}

fn validate_min_profit_factor(value: f64) -> Result<()> {
    if !value.is_finite() || value < 0.0 {
        anyhow::bail!("min_profit_factor must be a finite non-negative number");
    }
    Ok(())
}

fn validate_account_balance(value: f64) -> Result<()> {
    if !value.is_finite() || value <= 0.0 {
        anyhow::bail!("account_balance must be a finite positive number");
    }
    Ok(())
}

fn validate_fees_bps(value: f64) -> Result<()> {
    if !value.is_finite() || value < 0.0 {
        anyhow::bail!("fees_bps must be a finite non-negative number");
    }
    Ok(())
}

fn validate_tpe_config(config: &WfoConfig) -> Result<()> {
    validate_tpe_trials(config.tpe_trials)?;
    validate_tpe_random_startup_fraction(config.tpe_random_startup_fraction)?;
    validate_tpe_is_consensus_min_passing_windows(config.tpe_is_consensus_min_passing_windows)?;
    validate_week_count("is_weeks", config.is_weeks)?;
    validate_week_count("oos_weeks", config.oos_weeks)?;
    validate_week_count("step_weeks", config.step_weeks)?;
    if let Some(value) = config.is_days {
        validate_day_count("is_days", value)?;
    }
    if let Some(value) = config.oos_days {
        validate_day_count("oos_days", value)?;
    }
    if let Some(value) = config.step_days {
        validate_day_count("step_days", value)?;
    }
    validate_gap_weeks(config.gap_weeks)?;
    if let Some(value) = config.gap_days {
        validate_gap_days(value)?;
    }
    validate_start_offset_days(config.start_offset_days)?;
    Ok(())
}

fn validate_tpe_trials(value: usize) -> Result<()> {
    if value == 0 {
        anyhow::bail!("tpe trials must be greater than zero");
    }
    Ok(())
}

fn validate_tpe_random_startup_fraction(value: f64) -> Result<()> {
    if !value.is_finite() || !(0.0..=1.0).contains(&value) {
        anyhow::bail!("tpe random startup fraction must be between 0.0 and 1.0");
    }
    Ok(())
}

fn validate_tpe_is_consensus_min_passing_windows(value: usize) -> Result<()> {
    if !(1..=TPE_IS_CONSENSUS_OFFSET_DAYS).contains(&value) {
        anyhow::bail!(
            "tpe consensus min passing windows must be between 1 and {}",
            TPE_IS_CONSENSUS_OFFSET_DAYS
        );
    }
    Ok(())
}

fn validate_week_count(name: &str, value: i64) -> Result<()> {
    if value <= 0 {
        anyhow::bail!("{name} must be greater than zero");
    }
    Ok(())
}

fn validate_day_count(name: &str, value: i64) -> Result<()> {
    if !(1..=365).contains(&value) {
        anyhow::bail!("{name} must be between 1 and 365");
    }
    Ok(())
}

fn validate_gap_weeks(value: i64) -> Result<()> {
    if !(0..=8).contains(&value) {
        anyhow::bail!("gap_weeks must be between 0 and 8");
    }
    Ok(())
}

fn validate_gap_days(value: i64) -> Result<()> {
    if !(0..=365).contains(&value) {
        anyhow::bail!("gap_days must be between 0 and 365");
    }
    Ok(())
}

fn validate_start_offset_days(value: i64) -> Result<()> {
    if !(-30..=30).contains(&value) {
        anyhow::bail!("start_offset_days must be between -30 and 30");
    }
    Ok(())
}

fn normalize_symbols(symbols: Vec<String>) -> Vec<String> {
    symbols
        .into_iter()
        .map(|symbol| symbol.trim().to_uppercase())
        .filter(|symbol| !symbol.is_empty())
        .collect()
}

fn normalize_indicator_group(group: Option<String>) -> Option<String> {
    group
        .map(|group| group.trim().to_lowercase())
        .filter(|group| !group.is_empty())
}

fn normalize_strategy_set(strategy_set: Option<String>) -> Option<String> {
    strategy_set
        .map(|strategy_set| strategy_set.trim().to_lowercase())
        .filter(|strategy_set| !strategy_set.is_empty())
}

#[cfg(test)]
fn candidate_grid_for_group(
    grid: GridSize,
    indicator_group: Option<&str>,
) -> Result<Vec<Candidate>> {
    candidate_grid_for_group_with_trials(grid, indicator_group, DEFAULT_TPE_TRIALS)
}

fn candidate_grid_for_group_with_trials(
    grid: GridSize,
    indicator_group: Option<&str>,
    tpe_trials: usize,
) -> Result<Vec<Candidate>> {
    let candidates = candidate_grid_with_trials(grid, tpe_trials);
    match indicator_group {
        None => Ok(candidates),
        Some("ehlers") => Ok(candidates
            .into_iter()
            .filter(|candidate| EHLERS_INDICATORS.contains(&candidate.indicator))
            .collect()),
        Some(other) => anyhow::bail!("unknown indicator group {other}; supported: ehlers"),
    }
}

fn candidate_grid_for_config(config: &WfoConfig) -> Result<Vec<Candidate>> {
    candidate_grid_for_filters_with_trials(
        config.grid,
        config.indicator_group.as_deref(),
        config.strategy_set.as_deref(),
        config.tpe_trials,
    )
}

#[cfg(test)]
fn candidate_grid_for_filters(
    grid: GridSize,
    indicator_group: Option<&str>,
    strategy_set: Option<&str>,
) -> Result<Vec<Candidate>> {
    candidate_grid_for_filters_with_trials(grid, indicator_group, strategy_set, DEFAULT_TPE_TRIALS)
}

fn candidate_grid_for_filters_with_trials(
    grid: GridSize,
    indicator_group: Option<&str>,
    strategy_set: Option<&str>,
    tpe_trials: usize,
) -> Result<Vec<Candidate>> {
    let mut candidates = candidate_grid_for_group_with_trials(grid, indicator_group, tpe_trials)?;
    match strategy_set {
        None => {}
        Some(SUSPICIOUS_SHORTLIST_SET) => {
            candidates.retain(|candidate| {
                SUSPICIOUS_SHORTLIST.contains(&(candidate.indicator, candidate.timeframe))
            });
        }
        Some(CALIBRATION_AUDIT_SET) => {
            candidates.retain(|candidate| {
                CALIBRATION_AUDIT.contains(&(candidate.indicator, candidate.timeframe))
            });
        }
        Some(PORTFOLIO_CANDIDATES_SET) => {
            candidates.retain(|candidate| {
                PORTFOLIO_CANDIDATES.contains(&(candidate.indicator, candidate.timeframe))
            });
        }
        Some(LOW_TURNOVER_EXTRA_SET) => {
            candidates.retain(|candidate| {
                LOW_TURNOVER_EXTRA.contains(&(candidate.indicator, candidate.timeframe))
            });
        }
        Some(SECOND_PASS_PORTFOLIO_SET) => {
            candidates.retain(|candidate| {
                SECOND_PASS_PORTFOLIO.contains(&(candidate.indicator, candidate.timeframe))
            });
        }
        Some(ROBUST_PORTFOLIO_SET) => {
            candidates.retain(|candidate| {
                ROBUST_PORTFOLIO.contains(&(candidate.indicator, candidate.timeframe))
            });
        }
        Some(GOAL_SEARCH_SET) => {
            candidates.retain(|candidate| {
                GOAL_SEARCH.contains(&(candidate.indicator, candidate.timeframe))
            });
        }
        Some(HIGH_TRADE_GOAL_SET) => {
            candidates.retain(|candidate| {
                HIGH_TRADE_GOAL.contains(&(candidate.indicator, candidate.timeframe))
            });
        }
        Some(HIGH_TRADE_REFINE_SET) => {
            candidates.retain(|candidate| {
                HIGH_TRADE_REFINE.contains(&(candidate.indicator, candidate.timeframe))
            });
        }
        Some(PORTFOLIO_REFINE_SET) => {
            candidates.retain(|candidate| {
                PORTFOLIO_REFINE.contains(&(candidate.indicator, candidate.timeframe))
            });
        }
        Some(QUALITY_HUNT_SET) => {
            candidates.retain(|candidate| {
                QUALITY_HUNT.contains(&(candidate.indicator, candidate.timeframe))
            });
        }
        Some(Q3_DIVERSIFIERS_SET) => {
            candidates.retain(|candidate| {
                Q3_DIVERSIFIERS.contains(&(candidate.indicator, candidate.timeframe))
            });
        }
        Some(BEST_COMBO_CONFIRM_SET) => {
            candidates.retain(|candidate| {
                BEST_COMBO_CONFIRM.contains(&(candidate.indicator, candidate.timeframe))
            });
        }
        Some(FRAMA_5M_CONFIRM_SET) => {
            candidates.retain(|candidate| {
                FRAMA_5M_CONFIRM.contains(&(candidate.indicator, candidate.timeframe))
            });
        }
        Some(STRATEGY_336_KAMA_TPO_SET) => {
            candidates.retain(|candidate| {
                STRATEGY_336_KAMA_TPO.contains(&(candidate.indicator, candidate.timeframe))
            });
        }
        Some(STRATEGY_3635_KAMA_TPO_SET) => {
            candidates.retain(|candidate| {
                STRATEGY_3635_KAMA_TPO.contains(&(candidate.indicator, candidate.timeframe))
            });
        }
        Some(STRATEGY_3938_KAMA_TPO_SET) => {
            candidates.retain(|candidate| {
                STRATEGY_3938_KAMA_TPO.contains(&(candidate.indicator, candidate.timeframe))
            });
        }
        Some(STRATEGY_4448_KAMA_KER_SET) => {
            candidates.retain(|candidate| {
                STRATEGY_4448_KAMA_KER.contains(&(candidate.indicator, candidate.timeframe))
            });
        }
        Some(STRATEGY_33X_SQX_SET) => {
            candidates.retain(|candidate| {
                STRATEGY_33X_SQX.contains(&(candidate.indicator, candidate.timeframe))
            });
        }
        Some(ELEGANT_5M_SET) => {
            candidates.retain(|candidate| {
                candidate.indicator == IndicatorKind::ElegantOscillator
                    && candidate.timeframe == Timeframe::M5
            });
        }
        Some(ELEGANT_5M_ENTRY50_SET) => {
            candidates.retain(is_elegant_5m_entry50_candidate);
        }
        Some(ELEGANT_5M_ENTRY50_GATED_SET) => {
            candidates.retain(is_elegant_5m_entry50_gated_candidate);
        }
        Some(ELEGANT_5M_ENTRY50_UNGATED_SET) => {
            candidates.retain(is_elegant_5m_entry50_ungated_candidate);
        }
        Some(ELEGANT_5M_HYBRID_SET) => {
            candidates.retain(is_elegant_5m_entry50_candidate);
        }
        Some(other) => {
            anyhow::bail!(
                "unknown strategy set {other}; supported: {SUSPICIOUS_SHORTLIST_SET}, {CALIBRATION_AUDIT_SET}, {PORTFOLIO_CANDIDATES_SET}, {LOW_TURNOVER_EXTRA_SET}, {SECOND_PASS_PORTFOLIO_SET}, {ROBUST_PORTFOLIO_SET}, {GOAL_SEARCH_SET}, {HIGH_TRADE_GOAL_SET}, {HIGH_TRADE_REFINE_SET}, {PORTFOLIO_REFINE_SET}, {QUALITY_HUNT_SET}, {Q3_DIVERSIFIERS_SET}, {BEST_COMBO_CONFIRM_SET}, {FRAMA_5M_CONFIRM_SET}, {STRATEGY_336_KAMA_TPO_SET}, {STRATEGY_3635_KAMA_TPO_SET}, {STRATEGY_3938_KAMA_TPO_SET}, {STRATEGY_4448_KAMA_KER_SET}, {STRATEGY_33X_SQX_SET}, {ELEGANT_5M_SET}, {ELEGANT_5M_ENTRY50_SET}, {ELEGANT_5M_ENTRY50_GATED_SET}, {ELEGANT_5M_ENTRY50_UNGATED_SET}, {ELEGANT_5M_HYBRID_SET}"
            )
        }
    }
    Ok(candidates)
}

fn is_elegant_5m_entry50_candidate(candidate: &Candidate) -> bool {
    candidate.indicator == IndicatorKind::ElegantOscillator
        && candidate.timeframe == Timeframe::M5
        && candidate.entry_atr_multiple == 0.5
}

fn is_elegant_5m_entry50_gated_candidate(candidate: &Candidate) -> bool {
    is_elegant_5m_entry50_candidate(candidate)
        && candidate.stop_atr_multiple == 2.0
        && candidate.target_atr_multiple == 5.0
        && candidate.time_stop_bars == Some(24)
        && candidate.hurst_min == Some(0.52)
        && candidate.shannon_max == Some(0.85)
}

fn is_elegant_5m_entry50_ungated_candidate(candidate: &Candidate) -> bool {
    is_elegant_5m_entry50_candidate(candidate)
        && candidate.stop_atr_multiple == 1.5
        && candidate.target_atr_multiple == 3.0
        && candidate.time_stop_bars == Some(24)
        && candidate.hurst_min.is_none()
        && candidate.shannon_max.is_none()
}

fn candidate_allowed_for_symbol(
    strategy_set: Option<&str>,
    symbol: &str,
    candidate: &Candidate,
) -> bool {
    if strategy_set != Some(ELEGANT_5M_HYBRID_SET) {
        return true;
    }
    match symbol.trim().to_uppercase().as_str() {
        "BNBUSDT" | "DOGEUSDT" | "XRPUSDT" => is_elegant_5m_entry50_gated_candidate(candidate),
        _ => true,
    }
}

fn candidate_grid(grid: GridSize) -> Vec<Candidate> {
    candidate_grid_with_trials(grid, DEFAULT_TPE_TRIALS)
}

fn candidate_grid_with_trials(grid: GridSize, tpe_trials: usize) -> Vec<Candidate> {
    if grid == GridSize::Wide200 {
        return candidate_grid_wide200();
    }
    if grid == GridSize::Tpe {
        return candidate_grid_tpe_templates(tpe_trials);
    }
    if grid == GridSize::Probe {
        return candidate_grid_probe();
    }
    let indicators: &[IndicatorKind] = match grid {
        GridSize::Smoke => &[
            IndicatorKind::Roc,
            IndicatorKind::DonchianBreakout,
            IndicatorKind::Kama,
            IndicatorKind::EhlersRoofing,
        ],
        GridSize::Wide | GridSize::Deep => &IndicatorKind::IMPLEMENTED_DIRECT_OHLC,
        GridSize::Wide200 => unreachable!("wide200 is handled by candidate_grid_wide200"),
        GridSize::Tpe => unreachable!("tpe is handled by candidate_grid_tpe_templates"),
        GridSize::Probe => unreachable!("probe is handled by candidate_grid_probe"),
    };
    let timeframes: &[Timeframe] = match grid {
        GridSize::Smoke => &[Timeframe::M5],
        GridSize::Wide | GridSize::Deep => &Timeframe::ALL,
        GridSize::Wide200 => unreachable!("wide200 is handled by candidate_grid_wide200"),
        GridSize::Tpe => unreachable!("tpe is handled by candidate_grid_tpe_templates"),
        GridSize::Probe => unreachable!("probe is handled by candidate_grid_probe"),
    };
    let lookbacks: &[usize] = match grid {
        GridSize::Smoke => &[12],
        GridSize::Wide => &[12],
        GridSize::Deep => &[6, 8, 12, 24, 48],
        GridSize::Wide200 => unreachable!("wide200 is handled by candidate_grid_wide200"),
        GridSize::Tpe => unreachable!("tpe is handled by candidate_grid_tpe_templates"),
        GridSize::Probe => unreachable!("probe is handled by candidate_grid_probe"),
    };
    let atr_periods: &[usize] = match grid {
        GridSize::Smoke => &[14],
        GridSize::Wide | GridSize::Deep => &[14, 28, 56],
        GridSize::Wide200 => unreachable!("wide200 is handled by candidate_grid_wide200"),
        GridSize::Tpe => unreachable!("tpe is handled by candidate_grid_tpe_templates"),
        GridSize::Probe => unreachable!("probe is handled by candidate_grid_probe"),
    };
    let entries: &[f64] = match grid {
        GridSize::Smoke => &[0.5],
        GridSize::Wide => &[0.5],
        GridSize::Deep => &[0.25, 0.5, 1.0],
        GridSize::Wide200 => unreachable!("wide200 is handled by candidate_grid_wide200"),
        GridSize::Tpe => unreachable!("tpe is handled by candidate_grid_tpe_templates"),
        GridSize::Probe => unreachable!("probe is handled by candidate_grid_probe"),
    };
    let stops: &[f64] = match grid {
        GridSize::Smoke => &[1.5],
        GridSize::Wide => &[1.5, 2.0],
        GridSize::Deep => &[1.0, 1.5, 2.0, 3.0],
        GridSize::Wide200 => unreachable!("wide200 is handled by candidate_grid_wide200"),
        GridSize::Tpe => unreachable!("tpe is handled by candidate_grid_tpe_templates"),
        GridSize::Probe => unreachable!("probe is handled by candidate_grid_probe"),
    };
    let targets: &[f64] = match grid {
        GridSize::Smoke => &[2.0],
        GridSize::Wide => &[2.0, 3.0, 5.0],
        GridSize::Deep => &[1.0, 1.5, 2.0, 3.0, 5.0],
        GridSize::Wide200 => unreachable!("wide200 is handled by candidate_grid_wide200"),
        GridSize::Tpe => unreachable!("tpe is handled by candidate_grid_tpe_templates"),
        GridSize::Probe => unreachable!("probe is handled by candidate_grid_probe"),
    };
    let time_stops: &[Option<usize>] = match grid {
        GridSize::Smoke => &[Some(24)],
        GridSize::Wide => &[Some(24)],
        GridSize::Deep => &[None, Some(6), Some(24)],
        GridSize::Wide200 => unreachable!("wide200 is handled by candidate_grid_wide200"),
        GridSize::Tpe => unreachable!("tpe is handled by candidate_grid_tpe_templates"),
        GridSize::Probe => unreachable!("probe is handled by candidate_grid_probe"),
    };
    let gate_profiles: &[RegimeGateProfile] = match grid {
        GridSize::Smoke => &[RegimeGateProfile::none()],
        GridSize::Wide => &[
            RegimeGateProfile::none(),
            RegimeGateProfile::trend_low_entropy(),
        ],
        GridSize::Deep => &[
            RegimeGateProfile::none(),
            RegimeGateProfile::trend_low_entropy(),
            RegimeGateProfile::strict_trend_low_entropy(),
        ],
        GridSize::Wide200 => unreachable!("wide200 is handled by candidate_grid_wide200"),
        GridSize::Tpe => unreachable!("tpe is handled by candidate_grid_tpe_templates"),
        GridSize::Probe => unreachable!("probe is handled by candidate_grid_probe"),
    };

    let mut out = Vec::new();
    for indicator in indicators {
        for timeframe in timeframes {
            for lookback in lookbacks {
                for atr_period in atr_periods {
                    for entry in entries {
                        for stop in stops {
                            for target in targets {
                                for time_stop in time_stops {
                                    for gate in gate_profiles {
                                        out.push(Candidate {
                                            id: out.len(),
                                            indicator: *indicator,
                                            timeframe: *timeframe,
                                            signal_polarity: 1,
                                            entry_mode: EntryMode::Pullback,
                                            lookback: *lookback,
                                            atr_period: *atr_period,
                                            entry_atr_multiple: *entry,
                                            stop_atr_multiple: *stop,
                                            target_atr_multiple: *target,
                                            time_stop_bars: *time_stop,
                                            hurst_min: gate.hurst_min,
                                            hurst_max: gate.hurst_max,
                                            shannon_max: gate.shannon_max,
                                            ..Candidate::default()
                                        });
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
    out
}

fn candidate_grid_tpe_templates(trials: usize) -> Vec<Candidate> {
    let mut out = Vec::new();
    for indicator in IndicatorKind::IMPLEMENTED_DIRECT_OHLC {
        for timeframe in Timeframe::ALL {
            for _ in 0..trials {
                out.push(Candidate {
                    id: out.len(),
                    indicator,
                    timeframe,
                    signal_polarity: 1,
                    entry_mode: EntryMode::Pullback,
                    lookback: 12,
                    atr_period: 14,
                    entry_atr_multiple: 0.5,
                    stop_atr_multiple: 1.5,
                    target_atr_multiple: 3.0,
                    time_stop_bars: Some(24),
                    hurst_min: None,
                    hurst_max: None,
                    shannon_max: None,
                    ..Candidate::default()
                });
            }
        }
    }
    out
}

fn candidate_grid_probe() -> Vec<Candidate> {
    let lookbacks = [4, 5, 6, 8, 10, 12, 14, 16, 18, 21, 24, 30, 36];
    let atr_periods = [7, 10, 14, 21, 28, 42, 56];
    let entries = [0.25, 0.5, 0.75, 1.0];
    let profiles = [
        ExitProfile::new(1.0, 1.5, Some(6), RegimeGateProfile::none()),
        ExitProfile::new(1.25, 2.0, Some(12), RegimeGateProfile::none()),
        ExitProfile::new(1.5, 3.0, Some(24), RegimeGateProfile::none()),
        ExitProfile::new(2.0, 4.0, Some(48), RegimeGateProfile::none()),
        ExitProfile::new(2.0, 5.0, Some(24), RegimeGateProfile::trend_low_entropy()),
        ExitProfile::new(
            3.0,
            6.0,
            None,
            RegimeGateProfile::strict_trend_low_entropy(),
        ),
    ];
    let mut out = Vec::new();
    for indicator in IndicatorKind::IMPLEMENTED_DIRECT_OHLC {
        for timeframe in Timeframe::ALL {
            for lookback in lookbacks {
                for atr_period in atr_periods {
                    for entry in entries {
                        for profile in profiles {
                            out.push(Candidate {
                                id: out.len(),
                                indicator,
                                timeframe,
                                signal_polarity: 1,
                                entry_mode: EntryMode::Pullback,
                                lookback,
                                atr_period,
                                entry_atr_multiple: entry,
                                stop_atr_multiple: profile.stop_atr_multiple,
                                target_atr_multiple: profile.target_atr_multiple,
                                time_stop_bars: profile.time_stop_bars,
                                hurst_min: profile.gate.hurst_min,
                                hurst_max: profile.gate.hurst_max,
                                shannon_max: profile.gate.shannon_max,
                                ..Candidate::default()
                            });
                        }
                    }
                }
            }
        }
    }
    out
}

fn candidate_grid_wide200() -> Vec<Candidate> {
    let lookbacks = [6, 8, 12, 18, 24];
    let atr_periods = [10, 14, 28, 56];
    let entries = [0.25, 0.5];
    let profiles = [
        ExitProfile::new(1.0, 1.5, Some(6), RegimeGateProfile::none()),
        ExitProfile::new(1.5, 2.0, Some(12), RegimeGateProfile::none()),
        ExitProfile::new(1.5, 3.0, Some(24), RegimeGateProfile::none()),
        ExitProfile::new(2.0, 5.0, Some(24), RegimeGateProfile::trend_low_entropy()),
        ExitProfile::new(
            3.0,
            5.0,
            None,
            RegimeGateProfile::strict_trend_low_entropy(),
        ),
    ];
    let mut out = Vec::new();
    for indicator in IndicatorKind::IMPLEMENTED_DIRECT_OHLC {
        for timeframe in Timeframe::ALL {
            for lookback in lookbacks {
                for atr_period in atr_periods {
                    for entry in entries {
                        for profile in profiles {
                            out.push(Candidate {
                                id: out.len(),
                                indicator,
                                timeframe,
                                signal_polarity: 1,
                                entry_mode: EntryMode::Pullback,
                                lookback,
                                atr_period,
                                entry_atr_multiple: entry,
                                stop_atr_multiple: profile.stop_atr_multiple,
                                target_atr_multiple: profile.target_atr_multiple,
                                time_stop_bars: profile.time_stop_bars,
                                hurst_min: profile.gate.hurst_min,
                                hurst_max: profile.gate.hurst_max,
                                shannon_max: profile.gate.shannon_max,
                                ..Candidate::default()
                            });
                        }
                    }
                }
            }
        }
    }
    out
}

fn score_trades_with_diagnostics(
    symbol: &str,
    candidate: &Candidate,
    fold_index: usize,
    fold: &Fold,
    trades: &[&Trade],
    config: &WfoConfig,
    diagnostics: &CandidateSignalFillFoldDiagnostics,
) -> CandidateScore {
    let (selection_start_ms, selection_end_ms) = selection_window(config, fold);
    score_trades_in_window_with_diagnostics(
        symbol,
        candidate,
        fold_index,
        trades,
        config,
        selection_start_ms,
        selection_end_ms,
        Some(diagnostics),
    )
}

fn score_trades_in_window(
    symbol: &str,
    candidate: &Candidate,
    fold_index: usize,
    trades: &[&Trade],
    config: &WfoConfig,
    window_start_ms: i64,
    window_end_ms: i64,
) -> CandidateScore {
    score_trades_in_window_with_diagnostics(
        symbol,
        candidate,
        fold_index,
        trades,
        config,
        window_start_ms,
        window_end_ms,
        None,
    )
}

#[allow(clippy::too_many_arguments)]
fn score_trades_in_window_with_diagnostics(
    symbol: &str,
    candidate: &Candidate,
    fold_index: usize,
    trades: &[&Trade],
    config: &WfoConfig,
    window_start_ms: i64,
    window_end_ms: i64,
    diagnostics: Option<&CandidateSignalFillFoldDiagnostics>,
) -> CandidateScore {
    let pnl: f64 = trades.iter().map(|trade| trade.pnl).sum();
    let net_return_pct = pnl / config.fixed_notional.max(1.0) * 100.0;
    let average_trade_return_pct = if trades.is_empty() {
        0.0
    } else {
        net_return_pct / trades.len() as f64
    };
    let min_average_trade_return_pct = min_average_trade_return_pct(config.fees_bps);
    let trade_return_stddev_pct = trade_return_stddev_pct(trades);
    let edge_t_stat = edge_t_stat(
        average_trade_return_pct,
        trade_return_stddev_pct,
        trades.len(),
    );
    let max_drawdown_pct = max_drawdown_pct_from_trade_refs(trades);
    let weekly_profit_fraction = weekly_profit_fraction(trades);
    let profit_factor = profit_factor_from_trade_refs(trades);
    let participation = entry_participation_from_trade_refs(trades, window_start_ms, window_end_ms);
    let (min_trades, max_trades) =
        trade_count_band_for_window(candidate.timeframe, window_start_ms, window_end_ms);
    let entry_attempts = diagnostics
        .map(|diagnostics| diagnostics.entry_attempts)
        .unwrap_or_default();
    let filled_entries = diagnostics
        .map(|diagnostics| diagnostics.filled_entries)
        .unwrap_or_default();
    let fill_rate_pct = diagnostics.map(fill_rate_pct).unwrap_or_default();
    let trade_fit = trade_fit_label(trades.len(), min_trades, max_trades);
    let exit_geometry_rejection = exit_geometry_rejection_reason(candidate);
    let quality_fit = exit_geometry_rejection
        .map(str::to_string)
        .unwrap_or_else(|| {
            quality_fit_label(
                net_return_pct,
                profit_factor,
                config.min_profit_factor,
                average_trade_return_pct,
                min_average_trade_return_pct,
                edge_t_stat,
                DEFAULT_MIN_EDGE_T_STAT,
            )
        });
    let mut score = score_candidate(CandidateScoreInput {
        net_return_pct,
        max_drawdown_pct,
        weekly_profit_fraction,
        profit_factor,
        trades: trades.len(),
        trade_band: (min_trades, max_trades),
        min_profit_factor: config.min_profit_factor,
        average_trade_return_pct,
        min_average_trade_return_pct,
        trade_return_stddev_pct,
        min_edge_t_stat: DEFAULT_MIN_EDGE_T_STAT,
        entry_attempts,
        fill_rate_pct,
        min_fill_rate_pct: MIN_FILL_RATE_SCORE_PCT,
        entry_day_pct: participation.entry_day_pct,
        min_entry_day_pct: MIN_CANDIDATE_ENTRY_DAY_PCT,
        entry_week_pct: participation.entry_week_pct,
        min_entry_week_pct: MIN_CANDIDATE_ENTRY_WEEK_PCT,
        longest_no_entry_gap_days: participation.longest_no_entry_gap_days,
        max_no_entry_gap_days: MAX_CANDIDATE_NO_ENTRY_GAP_DAYS,
    });
    if exit_geometry_rejection.is_some() {
        score = INELIGIBLE_SCORE_CUTOFF - 900.0;
    }
    CandidateScore {
        candidate_id: candidate.id,
        symbol: symbol.to_string(),
        fold_index,
        net_return_pct,
        max_drawdown_pct,
        weekly_profit_fraction,
        profit_factor,
        min_profit_factor: config.min_profit_factor,
        average_trade_return_pct,
        min_average_trade_return_pct,
        trade_return_stddev_pct,
        edge_t_stat,
        min_edge_t_stat: DEFAULT_MIN_EDGE_T_STAT,
        entry_attempts,
        filled_entries,
        fill_rate_pct,
        min_fill_rate_pct: MIN_FILL_RATE_SCORE_PCT,
        entry_day_pct: participation.entry_day_pct,
        min_entry_day_pct: MIN_CANDIDATE_ENTRY_DAY_PCT,
        entry_week_pct: participation.entry_week_pct,
        min_entry_week_pct: MIN_CANDIDATE_ENTRY_WEEK_PCT,
        longest_no_entry_gap_days: participation.longest_no_entry_gap_days,
        max_no_entry_gap_days: MAX_CANDIDATE_NO_ENTRY_GAP_DAYS,
        trades: trades.len(),
        min_trades,
        max_trades,
        trade_fit,
        quality_fit,
        score,
    }
}

fn min_average_trade_return_pct(fees_bps: f64) -> f64 {
    if fees_bps <= 0.0 {
        0.0
    } else {
        fees_bps * 2.0 * FEE_EDGE_BUFFER_MULTIPLIER / 100.0
    }
}

fn trade_count_band(timeframe: Timeframe, fold: &Fold) -> (usize, usize) {
    trade_count_band_for_window(timeframe, fold.is_start_ms, fold.is_end_ms)
}

fn trade_count_band_for_window(timeframe: Timeframe, start_ms: i64, end_ms: i64) -> (usize, usize) {
    let duration_minutes = ((end_ms - start_ms) / MS_PER_MINUTE).max(1) as usize;
    let signal_bars = (duration_minutes / timeframe.minutes() as usize).max(1);
    let min_trades = (signal_bars as f64 / MIN_SIGNAL_BARS_PER_CLOSED_TRADE)
        .ceil()
        .max(ABSOLUTE_MIN_TRADES_PER_SCORE_WINDOW) as usize;
    let max_trades = (signal_bars as f64 / MAX_SIGNAL_BARS_PER_CLOSED_TRADE)
        .floor()
        .max(min_trades as f64) as usize;
    (min_trades, max_trades)
}

fn trade_fit_label(trades: usize, min_trades: usize, max_trades: usize) -> String {
    if trades < min_trades {
        "too_sparse".to_string()
    } else if trades > max_trades {
        "too_active".to_string()
    } else {
        "ok".to_string()
    }
}

fn quality_fit_label(
    net_return_pct: f64,
    profit_factor: f64,
    min_profit_factor: f64,
    average_trade_return_pct: f64,
    min_average_trade_return_pct: f64,
    edge_t_stat: f64,
    min_edge_t_stat: f64,
) -> String {
    if profit_factor < min_profit_factor {
        "low_profit_factor".to_string()
    } else if net_return_pct <= 0.0 {
        "nonpositive_net".to_string()
    } else if average_trade_return_pct < min_average_trade_return_pct {
        "low_average_trade_edge".to_string()
    } else if edge_t_stat < min_edge_t_stat {
        "low_edge_confidence".to_string()
    } else {
        "ok".to_string()
    }
}

fn profit_factor_from_trade_refs(trades: &[&Trade]) -> f64 {
    let winning_pnl = trades
        .iter()
        .filter(|trade| trade.pnl > 0.0)
        .map(|trade| trade.pnl)
        .sum::<f64>();
    let losing_pnl = trades
        .iter()
        .filter(|trade| trade.pnl < 0.0)
        .map(|trade| trade.pnl.abs())
        .sum::<f64>();
    if losing_pnl > 0.0 {
        winning_pnl / losing_pnl
    } else if winning_pnl > 0.0 {
        999.0
    } else {
        0.0
    }
}

fn trade_return_stddev_pct(trades: &[&Trade]) -> f64 {
    if trades.len() < 2 {
        return 0.0;
    }
    let mean = trades.iter().map(|trade| trade.return_pct).sum::<f64>() / trades.len() as f64;
    let variance = trades
        .iter()
        .map(|trade| {
            let delta = trade.return_pct - mean;
            delta * delta
        })
        .sum::<f64>()
        / (trades.len() - 1) as f64;
    variance.sqrt()
}

fn weekly_profit_fraction(trades: &[&Trade]) -> f64 {
    if trades.is_empty() {
        return 0.0;
    }
    let week_ms = Duration::weeks(1).num_milliseconds();
    let mut weeks: BTreeMap<i64, f64> = BTreeMap::new();
    for trade in trades {
        *weeks
            .entry(trade.exit_time_ms.div_euclid(week_ms))
            .or_default() += trade.pnl;
    }
    weeks.values().filter(|pnl| **pnl > 0.0).count() as f64 / weeks.len().max(1) as f64
}

fn summarize(
    config: &WfoConfig,
    folds: usize,
    candidates: usize,
    trades: &[Trade],
    account_stats: &AccountCurveStats,
    best_indicator: &str,
) -> RunSummary {
    let pnl: f64 = trades.iter().map(|trade| trade.pnl).sum();
    let returns: Vec<f64> = trades
        .iter()
        .map(|trade| trade.return_pct / 100.0)
        .collect();
    RunSummary {
        run_id: config.run_id.clone(),
        grid: config.grid,
        folds,
        candidates,
        trades: trades.len(),
        fixed_notional: config.fixed_notional,
        account_balance: config.account_balance,
        total_pnl: pnl,
        net_return_pct: pnl / config.account_balance.max(1.0) * 100.0,
        max_drawdown_pct: account_stats.max_drawdown_pct,
        sharpe: sharpe(&returns, false),
        sortino: sharpe(&returns, true),
        weekly_consistency: weekly_consistency(trades),
        average_trade: if trades.is_empty() {
            0.0
        } else {
            pnl / trades.len() as f64
        },
        exposure_pct: account_stats.exposure_pct,
        average_exposure_notional: account_stats.average_exposure_notional,
        average_long_exposure_notional: account_stats.average_long_exposure_notional,
        average_short_exposure_notional: account_stats.average_short_exposure_notional,
        average_net_exposure_notional: account_stats.average_net_exposure_notional,
        max_exposure_notional: account_stats.max_exposure_notional,
        max_long_exposure_notional: account_stats.max_long_exposure_notional,
        max_short_exposure_notional: account_stats.max_short_exposure_notional,
        max_abs_net_exposure_notional: account_stats.max_abs_net_exposure_notional,
        max_concurrent_positions: account_stats.max_concurrent_positions,
        max_concurrent_long_positions: account_stats.max_concurrent_long_positions,
        max_concurrent_short_positions: account_stats.max_concurrent_short_positions,
        long_exposure_pct: account_stats.long_exposure_pct,
        short_exposure_pct: account_stats.short_exposure_pct,
        longest_stagnation_minutes: account_stats.longest_stagnation_minutes,
        longest_stagnation_days: account_stats.longest_stagnation_days,
        return_to_drawdown_ratio: account_stats.return_to_drawdown_ratio,
        smoothness_score: account_stats.smoothness_score,
        best_indicator: best_indicator.to_string(),
    }
}

fn summarize_from_strategy_oos_blocks(
    config: &WfoConfig,
    folds: usize,
    candidates: usize,
    blocks: &[StrategyOosBlock],
) -> RunSummary {
    let best = blocks
        .iter()
        .filter_map(|block| block.portfolio.as_ref().map(|portfolio| (block, portfolio)))
        .filter(|(block, portfolio)| {
            candidate_acceptance(
                portfolio,
                &block.symbols,
                config.candidate_min_profit_factor,
            )
        })
        .max_by(|left, right| left.1.net_return_pct.total_cmp(&right.1.net_return_pct));
    let (best_indicator, portfolio) = best
        .map(|(block, portfolio)| {
            (
                format!("{} {}", block.indicator, block.timeframe),
                Some(portfolio),
            )
        })
        .unwrap_or_else(|| ("none".to_string(), None));
    let total_pnl = portfolio
        .map(|metrics| metrics.total_pnl)
        .unwrap_or_default();
    let trades = portfolio.map(|metrics| metrics.trades).unwrap_or_default();
    RunSummary {
        run_id: config.run_id.clone(),
        grid: config.grid,
        folds,
        candidates,
        trades,
        fixed_notional: config.fixed_notional,
        account_balance: config.account_balance,
        total_pnl,
        net_return_pct: portfolio
            .map(|metrics| metrics.net_return_pct)
            .unwrap_or_default(),
        max_drawdown_pct: portfolio
            .map(|metrics| metrics.max_drawdown_pct)
            .unwrap_or_default(),
        sharpe: portfolio.map(|metrics| metrics.sharpe).unwrap_or_default(),
        sortino: 0.0,
        weekly_consistency: 0.0,
        average_trade: if trades == 0 {
            0.0
        } else {
            total_pnl / trades as f64
        },
        exposure_pct: 0.0,
        average_exposure_notional: 0.0,
        average_long_exposure_notional: 0.0,
        average_short_exposure_notional: 0.0,
        average_net_exposure_notional: 0.0,
        max_exposure_notional: 0.0,
        max_long_exposure_notional: 0.0,
        max_short_exposure_notional: 0.0,
        max_abs_net_exposure_notional: 0.0,
        max_concurrent_positions: 0,
        max_concurrent_long_positions: 0,
        max_concurrent_short_positions: 0,
        long_exposure_pct: 0.0,
        short_exposure_pct: 0.0,
        longest_stagnation_minutes: 0,
        longest_stagnation_days: 0.0,
        return_to_drawdown_ratio: 0.0,
        smoothness_score: 0.0,
        best_indicator,
    }
}

#[allow(clippy::too_many_arguments)]
fn write_artifacts(
    run_dir: &Path,
    summary: &RunSummary,
    folds: &[Fold],
    candidates: &[Candidate],
    scores: &[CandidateScore],
    trades: &[Trade],
    account_artifacts: &AccountArtifacts,
    best_fold_scores: Option<&[CandidateScore]>,
    best_fold_trades: Option<&[Trade]>,
    risk_managed_artifacts: Option<&ManagedRunArtifacts>,
) -> Result<()> {
    write_json(run_dir.join("summary.json"), summary)?;
    write_summary_csv(run_dir.join("summary.csv"), summary)?;
    write_csv(run_dir.join("folds.csv"), folds)?;
    write_csv(run_dir.join("candidates.csv"), candidates)?;
    write_csv(run_dir.join("oos_trades.csv"), trades)?;
    if let Some(best_fold_scores) = best_fold_scores {
        write_csv(run_dir.join("oos_best_fold_scores.csv"), best_fold_scores)?;
    }
    if let Some(best_fold_trades) = best_fold_trades {
        write_csv(run_dir.join("oos_best_fold_trades.csv"), best_fold_trades)?;
    }
    let sampled_equity =
        downsample_equity(&account_artifacts.equity, OOS_EQUITY_ARTIFACT_MAX_POINTS);
    write_csv(run_dir.join("oos_equity.csv"), &sampled_equity)?;
    write_csv(
        run_dir.join("oos_stagnation.csv"),
        &account_artifacts.stagnation,
    )?;
    write_json(
        run_dir.join("oos_curve_stats.json"),
        &account_artifacts.stats,
    )?;
    write_equity_plot_html(
        run_dir.join("oos_equity_plot.html"),
        summary,
        &account_artifacts.equity,
        &account_artifacts.stagnation,
    )?;
    if let Some(managed) = risk_managed_artifacts {
        write_json(
            run_dir.join("oos_risk_managed_summary.json"),
            &managed.summary,
        )?;
        write_summary_csv(
            run_dir.join("oos_risk_managed_summary.csv"),
            &managed.summary,
        )?;
        write_csv(run_dir.join("oos_risk_managed_trades.csv"), &managed.trades)?;
        let sampled_managed_equity = downsample_equity(
            &managed.account_artifacts.equity,
            OOS_EQUITY_ARTIFACT_MAX_POINTS,
        );
        write_csv(
            run_dir.join("oos_risk_managed_equity.csv"),
            &sampled_managed_equity,
        )?;
        write_csv(
            run_dir.join("oos_risk_managed_stagnation.csv"),
            &managed.account_artifacts.stagnation,
        )?;
        write_json(
            run_dir.join("oos_risk_managed_curve_stats.json"),
            &managed.account_artifacts.stats,
        )?;
        write_equity_plot_html(
            run_dir.join("oos_risk_managed_equity_plot.html"),
            &managed.summary,
            &managed.account_artifacts.equity,
            &managed.account_artifacts.stagnation,
        )?;
    }
    write_csv(run_dir.join("best_by_indicator.csv"), scores)?;
    let artifacts = read_artifacts(
        run_dir
            .file_name()
            .and_then(|value| value.to_str())
            .unwrap_or_default(),
    )
    .unwrap_or_default();
    write_run_summary_page_at(run_dir, summary, &artifacts)?;
    Ok(())
}

fn write_resume_artifacts(
    run_dir: &Path,
    summary: &RunSummary,
    folds: &[Fold],
    candidates: &[Candidate],
) -> Result<()> {
    write_json(run_dir.join("summary.json"), summary)?;
    write_summary_csv(run_dir.join("summary.csv"), summary)?;
    write_csv(run_dir.join("folds.csv"), folds)?;
    write_csv(run_dir.join("candidates.csv"), candidates)?;
    let artifacts = read_artifacts(
        run_dir
            .file_name()
            .and_then(|value| value.to_str())
            .unwrap_or_default(),
    )
    .unwrap_or_default();
    write_run_summary_page_at(run_dir, summary, &artifacts)?;
    Ok(())
}

fn write_plan(
    run_dir: &Path,
    config: &WfoConfig,
    folds: &[Fold],
    candidates: &[Candidate],
) -> Result<()> {
    let mut plan = default_plan();
    plan.config = config.clone();
    plan.folds = folds.to_vec();
    plan.candidate_count = candidates.len();
    plan.implementation_status = implementation_rows(candidates);
    write_json(run_dir.join("plan.json"), &plan)
}

fn write_summary_csv(path: PathBuf, summary: &RunSummary) -> Result<()> {
    let mut writer = csv::Writer::from_path(path)?;
    writer.serialize(summary)?;
    writer.flush()?;
    Ok(())
}

fn write_csv<T: Serialize>(path: PathBuf, rows: &[T]) -> Result<()> {
    let mut writer = csv::Writer::from_path(path)?;
    for row in rows {
        writer.serialize(row)?;
    }
    writer.flush()?;
    Ok(())
}

fn close_lookup(data: &[(String, Vec<OhlcvBar>)]) -> BTreeMap<String, BTreeMap<i64, f64>> {
    data.iter()
        .map(|(symbol, rows)| {
            (
                symbol.clone(),
                rows.iter()
                    .map(|row| (row.open_time_ms, row.close))
                    .collect::<BTreeMap<_, _>>(),
            )
        })
        .collect()
}

fn build_account_artifacts(
    config: &WfoConfig,
    folds: &[Fold],
    trades: &[Trade],
    data: &[(String, Vec<OhlcvBar>)],
) -> Result<AccountArtifacts> {
    let start_ms = folds
        .first()
        .map(|fold| fold.oos_start_ms)
        .unwrap_or(date_ms(config.start)?);
    let end_ms = folds
        .last()
        .map(|fold| fold.oos_end_ms)
        .unwrap_or(date_ms(config.end)?);
    let close_by_symbol = close_lookup(data);

    let mut by_entry = trades.to_vec();
    by_entry.sort_by_key(|trade| trade.entry_time_ms);
    let mut by_exit = trades.to_vec();
    by_exit.sort_by_key(|trade| trade.exit_time_ms);

    let mut entry_idx = 0usize;
    let mut exit_idx = 0usize;
    let mut active: Vec<Trade> = Vec::new();
    let mut realized_pnl = 0.0;
    let mut peak = 0.0;
    let mut equity = Vec::new();
    let mut exposed_samples = 0usize;
    let mut long_exposed_samples = 0usize;
    let mut short_exposed_samples = 0usize;
    let mut exposure_sum = 0.0;
    let mut long_exposure_sum = 0.0;
    let mut short_exposure_sum = 0.0;
    let mut net_exposure_sum = 0.0;
    let mut max_exposure_notional = 0.0;
    let mut max_long_exposure_notional = 0.0;
    let mut max_short_exposure_notional = 0.0;
    let mut max_abs_net_exposure_notional = 0.0;
    let mut max_concurrent_positions = 0usize;
    let mut max_concurrent_long_positions = 0usize;
    let mut max_concurrent_short_positions = 0usize;
    let mut ts = start_ms;

    while ts < end_ms {
        while entry_idx < by_entry.len() && by_entry[entry_idx].entry_time_ms <= ts {
            if by_entry[entry_idx].exit_time_ms > ts {
                active.push(by_entry[entry_idx].clone());
            }
            entry_idx += 1;
        }
        while exit_idx < by_exit.len() && by_exit[exit_idx].exit_time_ms <= ts {
            realized_pnl += by_exit[exit_idx].pnl;
            if let Some(index) = active.iter().position(|trade| *trade == by_exit[exit_idx]) {
                active.remove(index);
            }
            exit_idx += 1;
        }

        let unrealized_pnl = active
            .iter()
            .map(|trade| mark_to_market(trade, ts, &close_by_symbol))
            .sum::<f64>();
        let account_equity = realized_pnl + unrealized_pnl;
        peak = f64::max(peak, account_equity);
        let drawdown = peak - account_equity;
        let long_positions = active
            .iter()
            .filter(|trade| trade.side == crate::engine::TradeSide::Long)
            .count();
        let short_positions = active.len().saturating_sub(long_positions);
        let exposure_notional = active.len() as f64 * config.fixed_notional;
        let long_exposure_notional = long_positions as f64 * config.fixed_notional;
        let short_exposure_notional = short_positions as f64 * config.fixed_notional;
        let net_exposure_notional = long_exposure_notional - short_exposure_notional;
        if !active.is_empty() {
            exposed_samples += 1;
        }
        if long_positions > 0 {
            long_exposed_samples += 1;
        }
        if short_positions > 0 {
            short_exposed_samples += 1;
        }
        exposure_sum += exposure_notional;
        long_exposure_sum += long_exposure_notional;
        short_exposure_sum += short_exposure_notional;
        net_exposure_sum += net_exposure_notional;
        max_exposure_notional = f64::max(max_exposure_notional, exposure_notional);
        max_long_exposure_notional = f64::max(max_long_exposure_notional, long_exposure_notional);
        max_short_exposure_notional =
            f64::max(max_short_exposure_notional, short_exposure_notional);
        max_abs_net_exposure_notional =
            f64::max(max_abs_net_exposure_notional, net_exposure_notional.abs());
        max_concurrent_positions = max_concurrent_positions.max(active.len());
        max_concurrent_long_positions = max_concurrent_long_positions.max(long_positions);
        max_concurrent_short_positions = max_concurrent_short_positions.max(short_positions);
        equity.push(AccountEquitySample {
            timestamp_ms: ts,
            realized_pnl,
            unrealized_pnl,
            equity: account_equity,
            drawdown,
            drawdown_pct: drawdown / config.account_balance.max(1.0) * 100.0,
            open_positions: active.len(),
            long_positions,
            short_positions,
            exposure_notional,
            long_exposure_notional,
            short_exposure_notional,
            net_exposure_notional,
        });
        ts += MS_PER_MINUTE;
    }

    let stagnation = stagnation_periods(&equity, config.account_balance);
    let total_pnl = trades.iter().map(|trade| trade.pnl).sum::<f64>();
    let max_drawdown = equity
        .iter()
        .map(|sample| sample.drawdown)
        .fold(0.0, f64::max);
    let max_drawdown_pct = equity
        .iter()
        .map(|sample| sample.drawdown_pct)
        .fold(0.0, f64::max);
    let net_return_pct = total_pnl / config.account_balance.max(1.0) * 100.0;
    let longest_stagnation_minutes = stagnation
        .iter()
        .map(|period| period.duration_minutes)
        .max()
        .unwrap_or(0);
    let longest_stagnation_days = longest_stagnation_minutes as f64 / MINUTES_PER_DAY as f64;
    let return_to_drawdown_ratio =
        compute_return_to_drawdown_ratio(net_return_pct, max_drawdown_pct);
    let smoothness_score =
        equity_smoothness_score(return_to_drawdown_ratio, longest_stagnation_days);
    let samples = equity.len().max(1);
    let stats = AccountCurveStats {
        samples: equity.len(),
        total_pnl,
        net_return_pct,
        max_drawdown,
        max_drawdown_pct,
        exposure_pct: exposed_samples as f64 / samples as f64 * 100.0,
        long_exposure_pct: long_exposed_samples as f64 / samples as f64 * 100.0,
        short_exposure_pct: short_exposed_samples as f64 / samples as f64 * 100.0,
        average_exposure_notional: exposure_sum / samples as f64,
        average_long_exposure_notional: long_exposure_sum / samples as f64,
        average_short_exposure_notional: short_exposure_sum / samples as f64,
        average_net_exposure_notional: net_exposure_sum / samples as f64,
        max_exposure_notional,
        max_long_exposure_notional,
        max_short_exposure_notional,
        max_abs_net_exposure_notional,
        max_concurrent_positions,
        max_concurrent_long_positions,
        max_concurrent_short_positions,
        longest_stagnation_minutes,
        longest_stagnation_days,
        return_to_drawdown_ratio,
        smoothness_score,
    };

    Ok(AccountArtifacts {
        equity,
        stagnation,
        stats,
    })
}

fn compute_return_to_drawdown_ratio(net_return_pct: f64, max_drawdown_pct: f64) -> f64 {
    if max_drawdown_pct > 0.0 {
        net_return_pct / max_drawdown_pct
    } else {
        net_return_pct.max(0.0)
    }
}

fn equity_smoothness_score(return_to_drawdown_ratio: f64, longest_stagnation_days: f64) -> f64 {
    return_to_drawdown_ratio / (1.0 + longest_stagnation_days.max(0.0) / 30.0)
}

fn mark_to_market(
    trade: &Trade,
    timestamp_ms: i64,
    close_by_symbol: &BTreeMap<String, BTreeMap<i64, f64>>,
) -> f64 {
    let close = close_by_symbol
        .get(&trade.symbol)
        .and_then(|rows| {
            rows.range(..=timestamp_ms)
                .next_back()
                .map(|(_, close)| *close)
        })
        .unwrap_or(trade.entry_price);
    let close = SymbolExecutionRules::for_symbol(&trade.symbol)
        .unwrap_or_else(SymbolExecutionRules::synthetic)
        .round_price_nearest(close);
    match trade.side {
        crate::engine::TradeSide::Long => (close - trade.entry_price) * trade.quantity,
        crate::engine::TradeSide::Short => (trade.entry_price - close) * trade.quantity,
    }
}

fn stagnation_periods(
    equity: &[AccountEquitySample],
    account_balance: f64,
) -> Vec<StagnationPeriod> {
    let Some(first) = equity.first() else {
        return Vec::new();
    };
    let mut periods = Vec::new();
    let mut peak_equity = 0.0;
    let mut peak_time_ms = first.timestamp_ms;
    let mut active: Option<(i64, i64, f64, f64)> = None;

    for sample in equity {
        if sample.equity >= peak_equity {
            if let Some((start_time_ms, period_peak_time_ms, period_peak, trough_equity)) =
                active.take()
            {
                let max_drawdown = period_peak - trough_equity;
                periods.push(StagnationPeriod {
                    peak_time_ms: period_peak_time_ms,
                    start_time_ms,
                    recovery_time_ms: Some(sample.timestamp_ms),
                    duration_minutes: (sample.timestamp_ms - start_time_ms) / MS_PER_MINUTE,
                    recovered: true,
                    peak_equity: period_peak,
                    trough_equity,
                    max_drawdown,
                    max_drawdown_pct: max_drawdown / account_balance.max(1.0) * 100.0,
                });
            }
            peak_equity = sample.equity;
            peak_time_ms = sample.timestamp_ms;
        } else if let Some((_, _, _, trough_equity)) = active.as_mut() {
            *trough_equity = f64::min(*trough_equity, sample.equity);
        } else {
            active = Some((
                sample.timestamp_ms,
                peak_time_ms,
                peak_equity,
                sample.equity,
            ));
        }
    }

    if let (Some(last), Some((start_time_ms, period_peak_time_ms, period_peak, trough_equity))) =
        (equity.last(), active)
    {
        let max_drawdown = period_peak - trough_equity;
        periods.push(StagnationPeriod {
            peak_time_ms: period_peak_time_ms,
            start_time_ms,
            recovery_time_ms: None,
            duration_minutes: (last.timestamp_ms - start_time_ms) / MS_PER_MINUTE,
            recovered: false,
            peak_equity: period_peak,
            trough_equity,
            max_drawdown,
            max_drawdown_pct: max_drawdown / account_balance.max(1.0) * 100.0,
        });
    }

    periods
}

fn write_equity_plot_html(
    path: PathBuf,
    summary: &RunSummary,
    equity: &[AccountEquitySample],
    stagnation: &[StagnationPeriod],
) -> Result<()> {
    let points = downsample_equity(equity, 2_400)
        .into_iter()
        .map(|sample| {
            serde_json::json!({
                "t": sample.timestamp_ms,
                "equity": sample.equity,
                "realized": sample.realized_pnl,
                "drawdown": sample.drawdown,
                "drawdownPct": sample.drawdown_pct,
                "exposure": sample.exposure_notional,
                "longExposure": sample.long_exposure_notional,
                "shortExposure": sample.short_exposure_notional,
                "netExposure": sample.net_exposure_notional,
                "open": sample.open_positions,
                "longOpen": sample.long_positions,
                "shortOpen": sample.short_positions,
            })
        })
        .collect::<Vec<_>>();
    let worst_stagnation = stagnation
        .iter()
        .max_by_key(|period| period.duration_minutes)
        .cloned();
    let data_json = serde_json::to_string(&points)?;
    let stagnation_json = serde_json::to_string(&worst_stagnation)?;
    let title = html_escape(&summary.run_id);
    let html = format!(
        r#"<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>WFO OOS Equity {title}</title>
  <style>
    :root {{ color-scheme: dark; --bg:#0f1214; --panel:#171d20; --line:#334047; --text:#eef4f6; --muted:#aebbc1; --green:#58c792; --blue:#79a8ff; --red:#e06c6c; --gold:#d9b760; }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; font:12px/1.4 system-ui,-apple-system,Segoe UI,sans-serif; background:var(--bg); color:var(--text); }}
    header {{ padding:12px 16px; border-bottom:1px solid var(--line); background:#111619; }}
    h1 {{ margin:0; font-size:16px; }}
    main {{ padding:14px 16px; display:grid; gap:12px; }}
    .grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(145px,1fr)); gap:8px; }}
    .card {{ background:var(--panel); border:1px solid var(--line); border-radius:6px; padding:9px 10px; }}
    .label {{ color:var(--muted); text-transform:uppercase; font-size:10px; font-weight:750; }}
    .value {{ font-size:17px; font-weight:760; margin-top:4px; font-variant-numeric:tabular-nums; }}
    canvas {{ width:100%; height:310px; display:block; background:#0b0f11; border:1px solid var(--line); border-radius:6px; }}
    table {{ width:100%; border-collapse:collapse; background:var(--panel); border:1px solid var(--line); border-radius:6px; overflow:hidden; }}
    th,td {{ padding:6px 8px; border-bottom:1px solid var(--line); text-align:left; font-variant-numeric:tabular-nums; }}
    th {{ color:var(--muted); background:#1b2327; }}
  </style>
</head>
<body>
  <header><h1>WFO OOS Equity - {title}</h1></header>
  <main>
    <div class="grid">
      <div class="card"><div class="label">Total PnL</div><div class="value">${total_pnl:.2}</div></div>
      <div class="card"><div class="label">Net Return</div><div class="value">{net_return:.2}%</div></div>
      <div class="card"><div class="label">Max DD</div><div class="value">{max_dd:.2}%</div></div>
      <div class="card"><div class="label">Exposure</div><div class="value">{exposure:.2}%</div></div>
      <div class="card"><div class="label">Long / Short Exposure</div><div class="value">{long_exposure:.2}% / {short_exposure:.2}%</div></div>
      <div class="card"><div class="label">Avg Net Exposure</div><div class="value">${avg_net_exposure:.0}</div></div>
      <div class="card"><div class="label">Longest Stagnation</div><div class="value">{stagnation_minutes} min</div></div>
      <div class="card"><div class="label">Return / DD</div><div class="value">{return_to_drawdown:.2}</div></div>
      <div class="card"><div class="label">Smoothness Score</div><div class="value">{smoothness_score:.2}</div></div>
      <div class="card"><div class="label">Trades</div><div class="value">{trades}</div></div>
    </div>
    <canvas id="equity"></canvas>
    <canvas id="risk"></canvas>
    <table id="stats"></table>
  </main>
  <script>
    const points = {data_json};
    const worstStagnation = {stagnation_json};
    const fmt = new Intl.NumberFormat(undefined, {{ maximumFractionDigits: 2 }});
    function fitCanvas(canvas) {{
      const ratio = window.devicePixelRatio || 1;
      const rect = canvas.getBoundingClientRect();
      canvas.width = Math.max(1, Math.floor(rect.width * ratio));
      canvas.height = Math.max(1, Math.floor(rect.height * ratio));
      return canvas.getContext('2d');
    }}
    function drawLine(canvas, series, color, label, minValue, maxValue) {{
      const ctx = fitCanvas(canvas);
      const w = canvas.width, h = canvas.height, pad = 34 * (window.devicePixelRatio || 1);
      ctx.clearRect(0,0,w,h);
      ctx.strokeStyle = '#334047'; ctx.lineWidth = 1;
      ctx.beginPath(); ctx.moveTo(pad, h - pad); ctx.lineTo(w - 8, h - pad); ctx.lineTo(w - 8, 10); ctx.stroke();
      const min = minValue ?? Math.min(...series);
      const max = maxValue ?? Math.max(...series);
      const span = Math.max(1e-9, max - min);
      ctx.strokeStyle = color; ctx.lineWidth = 2 * (window.devicePixelRatio || 1); ctx.beginPath();
      series.forEach((v, i) => {{
        const x = pad + i / Math.max(1, series.length - 1) * (w - pad - 12);
        const y = 10 + (max - v) / span * (h - pad - 18);
        if(i === 0) ctx.moveTo(x,y); else ctx.lineTo(x,y);
      }});
      ctx.stroke();
      ctx.fillStyle = '#eef4f6'; ctx.font = `${{12 * (window.devicePixelRatio || 1)}}px system-ui`;
      ctx.fillText(label, pad, 18 * (window.devicePixelRatio || 1));
      ctx.fillStyle = '#aebbc1';
      ctx.fillText(fmt.format(max), 4, 18 * (window.devicePixelRatio || 1));
      ctx.fillText(fmt.format(min), 4, h - pad);
    }}
    function render() {{
      if(!points.length) return;
      drawLine(document.getElementById('equity'), points.map(p => p.equity), '#58c792', 'MTM equity');
      drawLine(document.getElementById('risk'), points.map(p => -p.drawdownPct), '#e06c6c', 'Drawdown %', -Math.max(...points.map(p => p.drawdownPct)), 0);
      const first = new Date(points[0].t).toISOString().slice(0,10);
      const last = new Date(points[points.length - 1].t).toISOString().slice(0,10);
      document.getElementById('stats').innerHTML = `
        <tr><th>Range</th><td>${{first}} to ${{last}}</td></tr>
        <tr><th>Samples Rendered</th><td>${{points.length}}</td></tr>
        <tr><th>Worst Stagnation</th><td>${{worstStagnation ? fmt.format(worstStagnation.duration_minutes) + ' minutes' : '-'}}</td></tr>
        <tr><th>Longest Stagnation Days</th><td>{stagnation_days:.2}</td></tr>
        <tr><th>Return / Drawdown</th><td>{return_to_drawdown:.3}</td></tr>
        <tr><th>Smoothness Score</th><td>{smoothness_score:.3}</td></tr>
        <tr><th>Worst Stagnation Recovered</th><td>${{worstStagnation ? worstStagnation.recovered : '-'}}</td></tr>
        <tr><th>Max Long / Short Exposure</th><td>${{fmt.format({max_long_exposure})}} / ${{fmt.format({max_short_exposure})}}</td></tr>
        <tr><th>Max Abs Net Exposure</th><td>${{fmt.format({max_abs_net_exposure})}}</td></tr>
      `;
    }}
    window.addEventListener('resize', render);
    render();
  </script>
</body>
</html>
"#,
        total_pnl = summary.total_pnl,
        net_return = summary.net_return_pct,
        max_dd = summary.max_drawdown_pct,
        exposure = summary.exposure_pct,
        long_exposure = summary.long_exposure_pct,
        short_exposure = summary.short_exposure_pct,
        avg_net_exposure = summary.average_net_exposure_notional,
        max_long_exposure = summary.max_long_exposure_notional,
        max_short_exposure = summary.max_short_exposure_notional,
        max_abs_net_exposure = summary.max_abs_net_exposure_notional,
        stagnation_minutes = summary.longest_stagnation_minutes,
        stagnation_days = summary.longest_stagnation_days,
        return_to_drawdown = summary.return_to_drawdown_ratio,
        smoothness_score = summary.smoothness_score,
        trades = summary.trades,
    );
    fs::write(path, html)?;
    Ok(())
}

fn write_run_summary_page_at(
    run_dir: &Path,
    summary: &RunSummary,
    artifacts: &[ArtifactRow],
) -> Result<PathBuf> {
    let path = run_dir.join("summary.html");
    let mut oos_blocks = read_strategy_oos_block_map(run_dir)?
        .into_values()
        .collect::<Vec<_>>();
    if oos_blocks.is_empty() {
        let legacy_path = run_dir.join(STRATEGY_OOS_RESULTS_FILE);
        if legacy_path.exists() {
            oos_blocks = read_json::<Vec<StrategyOosBlock>>(legacy_path)?;
        }
    }
    let min_profit_factor = run_candidate_min_profit_factor(run_dir);
    for block in &mut oos_blocks {
        refresh_strategy_candidate_gate(block, min_profit_factor);
    }
    oos_blocks.sort_by(|left, right| {
        right
            .candidate_gate
            .pass_candidate
            .cmp(&left.candidate_gate.pass_candidate)
            .then_with(|| {
                let left_net = left
                    .portfolio
                    .as_ref()
                    .map(|metrics| metrics.net_return_pct)
                    .unwrap_or(f64::NEG_INFINITY);
                let right_net = right
                    .portfolio
                    .as_ref()
                    .map(|metrics| metrics.net_return_pct)
                    .unwrap_or(f64::NEG_INFINITY);
                right_net.total_cmp(&left_net)
            })
            .then_with(|| indicator_rank(&left.indicator).cmp(&indicator_rank(&right.indicator)))
            .then_with(|| timeframe_rank(&left.timeframe).cmp(&timeframe_rank(&right.timeframe)))
    });
    let accepted_blocks = oos_blocks
        .iter()
        .filter(|block| block.candidate_gate.pass_candidate)
        .count();
    let accepted_best_indicator = oos_blocks
        .iter()
        .filter(|block| block.candidate_gate.pass_candidate)
        .max_by(|left, right| {
            let left_net = left
                .portfolio
                .as_ref()
                .map(|metrics| metrics.net_return_pct)
                .unwrap_or(f64::NEG_INFINITY);
            let right_net = right
                .portfolio
                .as_ref()
                .map(|metrics| metrics.net_return_pct)
                .unwrap_or(f64::NEG_INFINITY);
            left_net.total_cmp(&right_net)
        })
        .map(|block| format!("{} {}", block.indicator, block.timeframe))
        .unwrap_or_else(|| "none accepted".to_string());
    let mut curve_links = artifacts
        .iter()
        .filter(|artifact| artifact.name.ends_with("_plot.html"))
        .map(|artifact| artifact.name.clone())
        .collect::<Vec<_>>();
    if curve_links.is_empty() && run_dir.join("oos_equity_plot.html").exists() {
        curve_links.push("oos_equity_plot.html".to_string());
    }
    curve_links.sort();
    curve_links.dedup();

    let mut html = String::new();
    html.push_str("<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">");
    html.push_str("<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">");
    html.push_str(&format!(
        "<title>WFO Summary {}</title>",
        html_escape(&summary.run_id)
    ));
    html.push_str(
        r#"<style>
:root{color-scheme:dark;--bg:#0f1214;--panel:#171d20;--panel2:#111719;--line:#334047;--text:#eef4f6;--muted:#aebbc1;--green:#58c792;--red:#e06c6c;--blue:#64a8ff;--gray:#99a3a8}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:12px/1.4 system-ui,-apple-system,Segoe UI,sans-serif}
header{padding:12px 16px;border-bottom:1px solid var(--line);background:#111619;position:sticky;top:0;z-index:2}
h1{margin:0;font-size:17px}.muted{color:var(--muted)}main{padding:14px 16px;display:grid;gap:12px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:8px}.card{background:var(--panel);border:1px solid var(--line);border-radius:6px;padding:9px 10px}
.label{color:var(--muted);font-size:10px;text-transform:uppercase;font-weight:760}.value{font-size:17px;font-weight:760;margin-top:4px;font-variant-numeric:tabular-nums}
.toolbar{display:flex;gap:8px;flex-wrap:wrap}.plot-btn{border:1px solid var(--line);background:#1b2327;color:var(--text);border-radius:6px;padding:7px 10px;cursor:pointer;font-weight:720}
.plot-btn:hover{border-color:var(--green)}.table-wrap{border:1px solid var(--line);border-radius:6px;overflow:auto;background:var(--panel)}
table{width:100%;border-collapse:collapse;min-width:1180px}th,td{padding:6px 8px;border-bottom:1px solid var(--line);text-align:left;font-variant-numeric:tabular-nums;vertical-align:middle}
th{color:var(--muted);position:sticky;top:0;background:#1b2327}.num{text-align:right}.pos{color:var(--green)}.neg{color:var(--red)}
.portfolio-row{background:var(--panel2)}.symbols-cell{padding:0 8px 10px 42px;background:#101518}.symbols{min-width:900px;border-left:1px solid var(--line);border-right:1px solid var(--line)}
.symbols th{position:static;background:#172025}.spark{display:block;width:260px;height:72px}.wide-spark{display:block;width:380px;height:96px}.pill{display:inline-block;border:1px solid var(--line);border-radius:999px;padding:2px 7px;color:var(--muted);font-size:10px;font-weight:760}
.spark,.wide-spark{cursor:zoom-in;border:1px solid transparent;border-radius:5px}.spark:hover,.wide-spark:hover{border-color:var(--blue)}
.chart-wrap{display:inline-block;min-width:280px}.spark-hint{display:block;color:var(--muted);font-size:10px;margin-top:2px}
.modal{display:none;position:fixed;inset:0;background:rgba(0,0,0,.72);z-index:10;padding:22px}.modal.open{display:grid;grid-template-rows:auto 1fr;gap:8px}
.modal-head{display:flex;justify-content:space-between;gap:10px;align-items:center}.modal iframe{width:100%;height:100%;border:1px solid var(--line);border-radius:6px;background:#0b0f11}
.close{border:1px solid var(--line);background:#1b2327;color:var(--text);border-radius:6px;padding:7px 10px;cursor:pointer}
.chart-modal{display:none;position:fixed;inset:0;background:rgba(0,0,0,.78);z-index:11;padding:22px}.chart-modal.open{display:grid;grid-template-rows:auto 1fr;gap:10px}
.chart-panel{background:#0b0f11;border:1px solid var(--line);border-radius:6px;padding:12px;min-height:0;display:grid;grid-template-rows:1fr auto;gap:8px}
.chart-panel canvas{width:100%;height:100%;display:block;min-height:540px}.chart-meta{display:flex;gap:14px;flex-wrap:wrap;color:var(--muted);font-variant-numeric:tabular-nums}
</style></head><body>"#,
    );
    html.push_str(&format!(
        "<header><h1>WFO OOS Summary - {}</h1><div class=\"muted\">All strategy/timeframe rows below are stitched out-of-sample portfolio results. Click any inline equity curve to enlarge it with the peak-to-trough drawdown window shaded.</div></header><main>",
        html_escape(&summary.run_id)
    ));
    html.push_str("<div class=\"grid\">");
    for (label, value, class_name) in [
        (
            "Stitched OOS Net",
            format!("{:.2}%", summary.net_return_pct),
            if summary.net_return_pct >= 0.0 {
                "pos"
            } else {
                "neg"
            },
        ),
        (
            "Stitched OOS PnL",
            format!("${:.2}", summary.total_pnl),
            if summary.total_pnl >= 0.0 {
                "pos"
            } else {
                "neg"
            },
        ),
        ("Max DD", format!("{:.2}%", summary.max_drawdown_pct), "neg"),
        ("Trades", summary.trades.to_string(), ""),
        ("Exposure", format!("{:.2}%", summary.exposure_pct), ""),
        (
            "Long / Short",
            format!(
                "{:.2}% / {:.2}%",
                summary.long_exposure_pct, summary.short_exposure_pct
            ),
            "",
        ),
        (
            "Avg Net Exposure",
            format!("${:.0}", summary.average_net_exposure_notional),
            "",
        ),
        (
            "Longest Stagnation",
            format!("{} min", summary.longest_stagnation_minutes),
            "",
        ),
        (
            "Accepted Blocks",
            format!("{} / {}", accepted_blocks, oos_blocks.len()),
            if accepted_blocks > 0 { "pos" } else { "neg" },
        ),
        (
            "Accepted Best",
            accepted_best_indicator.clone(),
            if accepted_blocks > 0 { "pos" } else { "neg" },
        ),
    ] {
        html.push_str(&format!(
            "<div class=\"card\"><div class=\"label\">{}</div><div class=\"value {}\">{}</div></div>",
            html_escape(label),
            class_name,
            html_escape(&value)
        ));
    }
    html.push_str("</div>");

    html.push_str("<section><h2>OOS Equity Artifacts</h2><div class=\"toolbar\">");
    if curve_links.is_empty() {
        html.push_str("<span class=\"muted\">No plot artifacts found.</span>");
    } else {
        for link in &curve_links {
            html.push_str(&format!(
                "<button class=\"plot-btn\" data-src=\"{}\">{}</button>",
                html_escape(link),
                html_escape(link)
            ));
        }
    }
    html.push_str("</div></section>");

    html.push_str("<section><h2>OOS Portfolio Results</h2><div class=\"table-wrap\"><table><tr><th>Rank</th><th>Strategy</th><th>TF</th><th>Status</th><th>Candidate Gate</th><th class=\"num\">Candidates</th><th class=\"num\">OOS Net</th><th class=\"num\">OOS DD</th><th class=\"num\">Trades</th><th class=\"num\">No-Entry Days</th><th class=\"num\">Active Weeks</th><th class=\"num\">Max Idle</th><th class=\"num\">Win Rate</th><th class=\"num\">PF</th><th class=\"num\">Sharpe</th><th>Portfolio OOS Equity</th><th class=\"num\">Circuit Net</th><th class=\"num\">Circuit DD</th><th class=\"num\">Circuit Trades</th><th>Circuit Equity</th></tr>");
    for (idx, block) in oos_blocks.iter().enumerate() {
        let Some(metrics) = block.portfolio.as_ref() else {
            html.push_str(&format!(
                "<tr class=\"portfolio-row\"><td class=\"num\">{}</td><td>{}</td><td>{}</td><td><span class=\"pill\">{}</span></td><td><span class=\"pill\">{}</span></td><td class=\"num\">{}</td><td colspan=\"14\" class=\"muted\">OOS result pending</td></tr>",
                idx + 1,
                html_escape(&block.indicator),
                html_escape(&block.timeframe),
                html_escape(&block.status),
                html_escape(&candidate_gate_label(&block.candidate_gate)),
                block.parameter_candidates
            ));
            continue;
        };
        let risk_metrics = block.risk_managed_portfolio.as_ref().unwrap_or(metrics);
        html.push_str(&format!(
            "<tr class=\"portfolio-row\"><td class=\"num\">{}</td><td>{}</td><td>{}</td><td><span class=\"pill\">{}</span></td><td><span class=\"pill {}\" title=\"{}\">{}</span></td><td class=\"num\">{}</td><td class=\"num {}\">{:.2}%</td><td class=\"num\">{:.2}%</td><td class=\"num\">{}</td><td class=\"num\">{}</td><td class=\"num\">{} / {}</td><td class=\"num\">{}d</td><td class=\"num\">{:.2}%</td><td class=\"num\">{:.3}</td><td class=\"num\">{:.3}</td><td>{}</td><td class=\"num {}\">{:.2}%</td><td class=\"num\">{:.2}%</td><td class=\"num\">{}</td><td>{}</td></tr>",
            idx + 1,
            html_escape(&block.indicator),
            html_escape(&block.timeframe),
            html_escape(&block.status),
            candidate_gate_class(&block.candidate_gate),
            html_escape(&block.candidate_gate.reason),
            html_escape(&candidate_gate_label(&block.candidate_gate)),
            block.parameter_candidates,
            pct_class(metrics.net_return_pct),
            metrics.net_return_pct,
            metrics.max_drawdown_pct,
            metrics.trades,
            metrics.no_entry_days,
            metrics.entry_weeks,
            metrics.total_oos_weeks,
            metrics.longest_no_entry_gap_days,
            metrics.win_rate,
            metrics.profit_factor,
            metrics.sharpe,
            spark_canvas(
                "portfolio",
                &format!("{} {} portfolio", block.indicator, block.timeframe),
                metrics.net_return_pct,
                metrics.max_drawdown_pct,
                &metrics.equity_curve,
                "wide-spark"
            ),
            pct_class(risk_metrics.net_return_pct),
            risk_metrics.net_return_pct,
            risk_metrics.max_drawdown_pct,
            risk_metrics.trades,
            spark_canvas(
                "portfolio",
                &format!("{} {} circuit portfolio", block.indicator, block.timeframe),
                risk_metrics.net_return_pct,
                risk_metrics.max_drawdown_pct,
                &risk_metrics.equity_curve,
                "wide-spark"
            )
        ));
        html.push_str("<tr><td class=\"symbols-cell\" colspan=\"20\"><table class=\"symbols\"><tr><th>Symbol</th><th class=\"num\">OOS Net</th><th class=\"num\">OOS DD</th><th class=\"num\">Trades</th><th class=\"num\">No-Entry Days</th><th class=\"num\">Active Weeks</th><th class=\"num\">Max Idle</th><th class=\"num\">Win Rate</th><th class=\"num\">PF</th><th class=\"num\">Sharpe</th><th>Symbol OOS Equity</th><th class=\"num\">Circuit Net</th><th class=\"num\">Circuit DD</th><th class=\"num\">Circuit Trades</th><th>Circuit Equity</th></tr>");
        let mut symbols = block.symbols.clone();
        symbols.sort_by(|left, right| left.symbol.cmp(&right.symbol));
        let risk_by_symbol = block
            .risk_managed_symbols
            .iter()
            .map(|symbol| (symbol.symbol.as_str(), &symbol.metrics))
            .collect::<BTreeMap<_, _>>();
        for symbol in &symbols {
            let metrics = &symbol.metrics;
            let risk_metrics = risk_by_symbol
                .get(symbol.symbol.as_str())
                .copied()
                .unwrap_or(metrics);
            html.push_str(&format!(
                "<tr><td>{}</td><td class=\"num {}\">{:.2}%</td><td class=\"num\">{:.2}%</td><td class=\"num\">{}</td><td class=\"num\">{}</td><td class=\"num\">{} / {}</td><td class=\"num\">{}d</td><td class=\"num\">{:.2}%</td><td class=\"num\">{:.3}</td><td class=\"num\">{:.3}</td><td>{}</td><td class=\"num {}\">{:.2}%</td><td class=\"num\">{:.2}%</td><td class=\"num\">{}</td><td>{}</td></tr>",
                html_escape(&symbol.symbol),
                pct_class(metrics.net_return_pct),
                metrics.net_return_pct,
                metrics.max_drawdown_pct,
                metrics.trades,
                metrics.no_entry_days,
                metrics.entry_weeks,
                metrics.total_oos_weeks,
                metrics.longest_no_entry_gap_days,
                metrics.win_rate,
                metrics.profit_factor,
                metrics.sharpe,
                spark_canvas(
                    "symbol",
                    &format!("{} {} {}", block.indicator, block.timeframe, symbol.symbol),
                    metrics.net_return_pct,
                    metrics.max_drawdown_pct,
                    &metrics.equity_curve,
                    "spark"
                )
                ,
                pct_class(risk_metrics.net_return_pct),
                risk_metrics.net_return_pct,
                risk_metrics.max_drawdown_pct,
                risk_metrics.trades,
                spark_canvas(
                    "symbol",
                    &format!("{} {} {} circuit", block.indicator, block.timeframe, symbol.symbol),
                    risk_metrics.net_return_pct,
                    risk_metrics.max_drawdown_pct,
                    &risk_metrics.equity_curve,
                    "spark"
                )
            ));
        }
        html.push_str("</table></td></tr>");
    }
    html.push_str("</table></div></section>");

    html.push_str(
        r#"</main><div class="modal" id="modal"><div class="modal-head"><strong id="modalTitle">Curve</strong><button class="close" id="close">Close</button></div><iframe id="plotFrame"></iframe></div>
<div class="chart-modal" id="chartModal"><div class="modal-head"><strong id="chartTitle">Equity Curve</strong><button class="close" id="chartClose">Close</button></div><div class="chart-panel"><canvas id="largeChart"></canvas><div class="chart-meta" id="chartMeta"></div></div></div>
<script>
const modal=document.getElementById('modal'), frame=document.getElementById('plotFrame'), title=document.getElementById('modalTitle');
document.querySelectorAll('.plot-btn').forEach(btn=>btn.onclick=()=>{title.textContent=btn.dataset.src;frame.src=btn.dataset.src;modal.classList.add('open')});
document.getElementById('close').onclick=()=>{modal.classList.remove('open');frame.src='about:blank'};
modal.addEventListener('click',e=>{if(e.target===modal){modal.classList.remove('open');frame.src='about:blank'}});
const chartModal=document.getElementById('chartModal'), chartTitle=document.getElementById('chartTitle'), chartMeta=document.getElementById('chartMeta'), largeChart=document.getElementById('largeChart');
document.getElementById('chartClose').onclick=()=>chartModal.classList.remove('open');
chartModal.addEventListener('click',e=>{if(e.target===chartModal)chartModal.classList.remove('open')});
function fitCanvas(canvas){
  const ratio=window.devicePixelRatio||1, rect=canvas.getBoundingClientRect();
  canvas.width=Math.max(1,Math.floor(rect.width*ratio));
  canvas.height=Math.max(1,Math.floor(rect.height*ratio));
  return {ctx:canvas.getContext('2d'), ratio};
}
function ddWindow(values){
  let peak=values[0], peakIdx=0, maxDd=0, maxPeakIdx=0, maxTroughIdx=0;
  values.forEach((value,i)=>{
    if(value>peak){peak=value;peakIdx=i}
    const dd=peak-value;
    if(dd>maxDd){maxDd=dd;maxPeakIdx=peakIdx;maxTroughIdx=i}
  });
  return {maxDd,maxPeakIdx,maxTroughIdx};
}
function drawSpark(canvas){
  const values=(canvas.dataset.points||'').split(',').map(Number).filter(Number.isFinite);
  const {ctx}=fitCanvas(canvas), w=canvas.width, h=canvas.height;
  ctx.clearRect(0,0,w,h);
  if(values.length<2)return;
  const min=Math.min(...values), max=Math.max(...values), pad=3, span=Math.max(1e-9,max-min);
  const net=Number(canvas.dataset.net)||0;
  const kind=canvas.dataset.kind;
  const dd=ddWindow(values);
  if(dd.maxTroughIdx>dd.maxPeakIdx){
    const x1=pad+(w-pad*2)*dd.maxPeakIdx/(values.length-1);
    const x2=pad+(w-pad*2)*dd.maxTroughIdx/(values.length-1);
    ctx.fillStyle='rgba(224,108,108,.12)';
    ctx.fillRect(x1,pad,Math.max(2,x2-x1),h-pad*2);
  }
  ctx.lineWidth=Math.max(1.25,1.5*(window.devicePixelRatio||1));
  ctx.strokeStyle=kind==='portfolio' ? (net>=0 ? '#64a8ff' : '#e06c6c') : (net>=0 ? '#58c792' : '#99a3a8');
  ctx.beginPath();
  values.forEach((value,i)=>{
    const x=pad+(w-pad*2)*i/(values.length-1);
    const y=h-pad-(h-pad*2)*(value-min)/span;
    if(i===0)ctx.moveTo(x,y);else ctx.lineTo(x,y);
  });
  ctx.stroke();
}
function drawLargeChart(source){
  const values=(source.dataset.points||'').split(',').map(Number).filter(Number.isFinite);
  chartTitle.textContent=source.dataset.title||'Equity Curve';
  chartModal.classList.add('open');
  requestAnimationFrame(()=>{
    const {ctx,ratio}=fitCanvas(largeChart), w=largeChart.width, h=largeChart.height;
    ctx.clearRect(0,0,w,h);
    if(values.length<2)return;
    const min=Math.min(...values), max=Math.max(...values), span=Math.max(1e-9,max-min);
    const padL=62*ratio, padR=22*ratio, padT=26*ratio, padB=44*ratio;
    const plotW=w-padL-padR, plotH=h-padT-padB;
    const xFor=i=>padL+plotW*i/(values.length-1);
    const yFor=value=>padT+plotH-(plotH*(value-min)/span);
    const net=Number(source.dataset.net)||0, reportedDd=Number(source.dataset.dd)||0, kind=source.dataset.kind;
    const color=kind==='portfolio' ? (net>=0 ? '#64a8ff' : '#e06c6c') : (net>=0 ? '#58c792' : '#99a3a8');
    const dd=ddWindow(values);
    ctx.fillStyle='#0b0f11';ctx.fillRect(0,0,w,h);
    ctx.strokeStyle='#2a343a';ctx.lineWidth=1*ratio;
    for(let g=0;g<=4;g++){
      const y=padT+plotH*g/4;ctx.beginPath();ctx.moveTo(padL,y);ctx.lineTo(w-padR,y);ctx.stroke();
    }
    if(dd.maxTroughIdx>dd.maxPeakIdx){
      const x1=xFor(dd.maxPeakIdx), x2=xFor(dd.maxTroughIdx);
      ctx.fillStyle='rgba(224,108,108,.18)';
      ctx.fillRect(x1,padT,Math.max(3*ratio,x2-x1),plotH);
      ctx.strokeStyle='rgba(224,108,108,.65)';
      ctx.setLineDash([5*ratio,4*ratio]);
      ctx.beginPath();ctx.moveTo(x1,padT);ctx.lineTo(x1,padT+plotH);ctx.moveTo(x2,padT);ctx.lineTo(x2,padT+plotH);ctx.stroke();
      ctx.setLineDash([]);
    }
    ctx.strokeStyle=color;ctx.lineWidth=2.2*ratio;ctx.beginPath();
    values.forEach((value,i)=>{const x=xFor(i), y=yFor(value); if(i===0)ctx.moveTo(x,y);else ctx.lineTo(x,y)});
    ctx.stroke();
    ctx.fillStyle='#aebbc1';ctx.font=`${12*ratio}px system-ui`;
    ctx.textAlign='right';ctx.textBaseline='middle';
    for(let g=0;g<=4;g++){
      const value=max-(span*g/4), y=padT+plotH*g/4;
      ctx.fillText(value.toFixed(2),padL-8*ratio,y);
    }
    ctx.textAlign='left';ctx.textBaseline='top';
    ctx.fillText('peak -> trough shaded red',padL,padT+plotH+12*ratio);
    chartMeta.innerHTML=`<span>Net: <strong class="${net>=0?'pos':'neg'}">${net.toFixed(2)}%</strong></span><span>Reported max DD: <strong class="neg">${reportedDd.toFixed(2)}%</strong></span><span>Rendered peak-to-trough PnL move: <strong class="neg">${dd.maxDd.toFixed(2)}</strong></span><span>Points: ${values.length}</span>`;
  });
}
document.querySelectorAll('canvas.spark,canvas.wide-spark').forEach(canvas=>{
  drawSpark(canvas);
  canvas.addEventListener('click',()=>drawLargeChart(canvas));
});
window.addEventListener('resize',()=>document.querySelectorAll('canvas.spark,canvas.wide-spark').forEach(drawSpark));
</script></body></html>"#,
    );
    fs::write(&path, html)?;
    Ok(path)
}

fn downsample_equity(
    equity: &[AccountEquitySample],
    max_points: usize,
) -> Vec<AccountEquitySample> {
    if equity.len() <= max_points {
        return equity.to_vec();
    }
    let step = (equity.len() as f64 / max_points as f64).ceil() as usize;
    let mut out = equity.iter().step_by(step).cloned().collect::<Vec<_>>();
    if let Some(last) = equity.last()
        && out.last().map(|sample| sample.timestamp_ms) != Some(last.timestamp_ms)
    {
        out.push(last.clone());
    }
    out
}

fn html_escape(value: &str) -> String {
    value
        .replace('&', "&amp;")
        .replace('<', "&lt;")
        .replace('>', "&gt;")
        .replace('"', "&quot;")
}

fn pct_class(value: f64) -> &'static str {
    if value >= 0.0 { "pos" } else { "neg" }
}

fn candidate_gate_class(gate: &StrategyCandidateGate) -> &'static str {
    if gate.pass_candidate {
        "pos"
    } else if gate.status == "pending" {
        ""
    } else {
        "neg"
    }
}

fn candidate_gate_label(gate: &StrategyCandidateGate) -> String {
    if gate.pass_candidate {
        "candidate".to_string()
    } else if gate.status == "pending" {
        "pending".to_string()
    } else {
        format!("rejected: {}", gate.reason)
    }
}

fn spark_canvas(
    kind: &str,
    title: &str,
    net_return_pct: f64,
    max_drawdown_pct: f64,
    curve: &[StrategyCurvePoint],
    class_name: &str,
) -> String {
    let points = curve
        .iter()
        .map(|point| format!("{:.6}", point.equity))
        .collect::<Vec<_>>()
        .join(",");
    format!(
        "<span class=\"chart-wrap\"><canvas class=\"{}\" width=\"380\" height=\"96\" data-kind=\"{}\" data-title=\"{}\" data-net=\"{:.6}\" data-dd=\"{:.6}\" data-points=\"{}\"></canvas><span class=\"spark-hint\">Click to enlarge</span></span>",
        html_escape(class_name),
        html_escape(kind),
        html_escape(title),
        net_return_pct,
        max_drawdown_pct,
        html_escape(&points)
    )
}

fn write_status(run_dir: &Path, status: &RunStatus) -> Result<()> {
    write_json(run_dir.join("status.json"), status)
}

fn status(run_id: &str, phase: RunPhase, progress_pct: f64, message: &str) -> RunStatus {
    status_with_active(
        run_id,
        phase,
        progress_pct,
        message,
        ActiveStatus::default(),
    )
}

#[derive(Debug, Clone, Copy, Default)]
struct ActiveStatus<'a> {
    symbol: Option<&'a str>,
    indicator: Option<&'a str>,
    timeframe: Option<&'a str>,
    offset_days: Option<i64>,
    fold_index: Option<usize>,
    fold_count: Option<usize>,
    optimizer_mode: Option<OptimizerMode>,
    eta_seconds: Option<u64>,
}

fn status_with_active(
    run_id: &str,
    phase: RunPhase,
    progress_pct: f64,
    message: &str,
    active: ActiveStatus<'_>,
) -> RunStatus {
    RunStatus {
        run_id: run_id.to_string(),
        phase,
        progress_pct,
        message: message.to_string(),
        active_symbol: active.symbol.map(str::to_string),
        active_indicator: active.indicator.map(str::to_string),
        active_timeframe: active.timeframe.map(str::to_string),
        active_offset_days: active.offset_days,
        active_fold_index: active.fold_index,
        active_fold_count: active.fold_count,
        optimizer_mode: active.optimizer_mode.map(|mode| mode.as_str().to_string()),
        eta_seconds: active.eta_seconds,
        latest_test_state: "not_run".to_string(),
        updated_at: Utc::now(),
    }
}

fn append_event(run_dir: &Path, kind: &str, message: &str) -> Result<()> {
    let mut file = OpenOptions::new()
        .create(true)
        .append(true)
        .open(run_dir.join("events.jsonl"))?;
    serde_json::to_writer(
        &mut file,
        &serde_json::json!({
            "ts": Utc::now(),
            "kind": kind,
            "message": message,
        }),
    )?;
    writeln!(file)?;
    Ok(())
}

fn write_json<T: Serialize>(path: PathBuf, value: &T) -> Result<()> {
    let ext = format!("tmp.{}", std::process::id());
    let tmp = path.with_extension(ext);
    let mut file = File::create(&tmp).with_context(|| format!("create {}", tmp.display()))?;
    serde_json::to_writer_pretty(&mut file, value)?;
    writeln!(file)?;
    file.sync_all()?;
    fs::rename(tmp, path)?;
    Ok(())
}

fn write_strategy_progress(run_dir: &Path, rows: &[StrategyRow]) -> Result<()> {
    write_json(run_dir.join("strategy_progress.json"), &rows)
}

fn write_strategy_oos_placeholders(run_dir: &Path, rows: &[StrategyRow]) -> Result<()> {
    write_json(
        run_dir.join(STRATEGY_OOS_STATUS_FILE),
        &strategy_oos_placeholders(rows),
    )
}

fn strategy_oos_placeholders(rows: &[StrategyRow]) -> Vec<StrategyOosBlock> {
    rows.iter()
        .filter(|row| row.runnable && row.parameter_candidates > 0)
        .map(|row| StrategyOosBlock {
            indicator: row.indicator.clone(),
            timeframe: row.timeframe.clone(),
            status: row.status.clone(),
            progress_pct: row.progress_pct,
            progress_label: row.progress_label.clone(),
            parameter_candidates: row.parameter_candidates,
            portfolio: None,
            candidate_gate: strategy_candidate_gate(None, &[], DEFAULT_CANDIDATE_MIN_PROFIT_FACTOR),
            symbols: Vec::new(),
            risk_managed_portfolio: None,
            risk_managed_symbols: Vec::new(),
            risk_overlay: None,
            selected_candidates: Vec::new(),
        })
        .collect()
}

fn write_strategy_oos_status_snapshot(run_dir: &Path, rows: &[StrategyRow]) -> Result<()> {
    write_json(
        run_dir.join(STRATEGY_OOS_STATUS_FILE),
        &strategy_oos_placeholders(rows),
    )
}

struct StrategyOosContext<'a> {
    config: &'a WfoConfig,
    rows: &'a [StrategyRow],
    selections: &'a BTreeMap<(String, String, String, usize), FoldSelection>,
    candidates_by_id: BTreeMap<usize, Candidate>,
    close_by_symbol: &'a BTreeMap<String, BTreeMap<i64, f64>>,
    symbols: Vec<String>,
    start_ms: i64,
    end_ms: i64,
}

impl<'a> StrategyOosContext<'a> {
    fn new(
        config: &'a WfoConfig,
        folds: &[Fold],
        data: &[(String, Vec<OhlcvBar>)],
        candidates: &[Candidate],
        rows: &'a [StrategyRow],
        selections: &'a BTreeMap<(String, String, String, usize), FoldSelection>,
        close_by_symbol: &'a BTreeMap<String, BTreeMap<i64, f64>>,
    ) -> Result<Self> {
        Ok(Self {
            config,
            rows,
            selections,
            candidates_by_id: candidates
                .iter()
                .map(|candidate| (candidate.id, candidate.clone()))
                .collect(),
            close_by_symbol,
            symbols: data
                .iter()
                .map(|(symbol, _)| symbol.clone())
                .collect::<Vec<_>>(),
            start_ms: folds
                .first()
                .map(|fold| fold.oos_start_ms)
                .unwrap_or(date_ms(config.start)?),
            end_ms: folds
                .last()
                .map(|fold| fold.oos_end_ms)
                .unwrap_or(date_ms(config.end)?),
        })
    }
}

fn write_completed_strategy_oos_snapshot(
    run_dir: &Path,
    completed_key: &(String, String),
    context: &StrategyOosContext<'_>,
) -> Result<()> {
    if let Some(row) = context
        .rows
        .iter()
        .find(|row| row.indicator == completed_key.0 && row.timeframe == completed_key.1)
    {
        fs::create_dir_all(run_dir.join(STRATEGY_OOS_BLOCKS_DIR))?;
        let block = build_strategy_oos_block(
            context.config,
            row,
            &context.symbols,
            context.selections,
            &context.candidates_by_id,
            (context.start_ms, context.end_ms),
            context.close_by_symbol,
        );
        write_json(
            strategy_oos_block_path(run_dir, &row.indicator, &row.timeframe),
            &block,
        )?;
    }
    write_strategy_oos_status_snapshot(run_dir, context.rows)
}

fn build_strategy_oos_results(
    config: &WfoConfig,
    folds: &[Fold],
    data: &[(String, Vec<OhlcvBar>)],
    candidates: &[Candidate],
    rows: &[StrategyRow],
    selections: &BTreeMap<(String, String, String, usize), FoldSelection>,
    close_by_symbol: &BTreeMap<String, BTreeMap<i64, f64>>,
) -> Result<Vec<StrategyOosBlock>> {
    let start_ms = folds
        .first()
        .map(|fold| fold.oos_start_ms)
        .unwrap_or(date_ms(config.start)?);
    let end_ms = folds
        .last()
        .map(|fold| fold.oos_end_ms)
        .unwrap_or(date_ms(config.end)?);
    let symbols = data
        .iter()
        .map(|(symbol, _)| symbol.clone())
        .collect::<Vec<_>>();
    let candidates_by_id = candidates
        .iter()
        .map(|candidate| (candidate.id, candidate.clone()))
        .collect::<BTreeMap<_, _>>();
    Ok(rows
        .iter()
        .filter(|row| row.runnable && row.parameter_candidates > 0)
        .map(|row| {
            build_strategy_oos_block(
                config,
                row,
                &symbols,
                selections,
                &candidates_by_id,
                (start_ms, end_ms),
                close_by_symbol,
            )
        })
        .collect())
}

fn build_strategy_oos_block(
    config: &WfoConfig,
    row: &StrategyRow,
    symbols: &[String],
    selections: &BTreeMap<(String, String, String, usize), FoldSelection>,
    candidates_by_id: &BTreeMap<usize, Candidate>,
    oos_window_ms: (i64, i64),
    close_by_symbol: &BTreeMap<String, BTreeMap<i64, f64>>,
) -> StrategyOosBlock {
    let mut portfolio_trades = Vec::new();
    let mut risk_managed_portfolio_trades = Vec::new();
    let mut symbol_results = Vec::new();
    let mut risk_managed_symbol_results = Vec::new();
    for symbol in symbols {
        let mut symbol_trades = selections
            .iter()
            .filter(|((indicator, timeframe, selected_symbol, _), _)| {
                indicator == &row.indicator
                    && timeframe == &row.timeframe
                    && selected_symbol == symbol
            })
            .flat_map(|(_, selection)| selection.trades.clone())
            .collect::<Vec<_>>();
        symbol_trades.sort_by_key(|trade| trade.exit_time_ms);
        portfolio_trades.extend(symbol_trades.clone());

        let mut risk_managed_symbol_trades =
            risk_managed_trades_for_symbol(row, symbol, selections, config.fixed_notional);
        risk_managed_symbol_trades.sort_by_key(|trade| trade.exit_time_ms);
        risk_managed_portfolio_trades.extend(risk_managed_symbol_trades.clone());

        symbol_results.push(StrategyOosSymbolResult {
            symbol: symbol.clone(),
            metrics: strategy_oos_metrics(
                &symbol_trades,
                config.account_balance,
                oos_window_ms.0,
                oos_window_ms.1,
                close_by_symbol,
            ),
        });
        risk_managed_symbol_results.push(StrategyOosSymbolResult {
            symbol: symbol.clone(),
            metrics: strategy_oos_metrics(
                &risk_managed_symbol_trades,
                config.account_balance,
                oos_window_ms.0,
                oos_window_ms.1,
                close_by_symbol,
            ),
        });
    }
    portfolio_trades.sort_by_key(|trade| trade.exit_time_ms);
    risk_managed_portfolio_trades.sort_by_key(|trade| trade.exit_time_ms);
    let portfolio = if row.status == "complete" {
        Some(strategy_oos_metrics(
            &portfolio_trades,
            config.account_balance,
            oos_window_ms.0,
            oos_window_ms.1,
            close_by_symbol,
        ))
    } else {
        None
    };
    let risk_managed_portfolio = if row.status == "complete" {
        Some(strategy_oos_metrics(
            &risk_managed_portfolio_trades,
            config.account_balance,
            oos_window_ms.0,
            oos_window_ms.1,
            close_by_symbol,
        ))
    } else {
        None
    };
    let selected_candidates = if row.status == "complete" {
        strategy_oos_selected_candidates(row, selections, candidates_by_id, config.fixed_notional)
    } else {
        Vec::new()
    };
    let candidate_gate = strategy_candidate_gate(
        portfolio.as_ref(),
        &symbol_results,
        config.candidate_min_profit_factor,
    );
    StrategyOosBlock {
        indicator: row.indicator.clone(),
        timeframe: row.timeframe.clone(),
        status: row.status.clone(),
        progress_pct: row.progress_pct,
        progress_label: row.progress_label.clone(),
        parameter_candidates: row.parameter_candidates,
        portfolio,
        candidate_gate,
        symbols: if row.status == "complete" {
            symbol_results
        } else {
            Vec::new()
        },
        risk_managed_portfolio,
        risk_managed_symbols: if row.status == "complete" {
            risk_managed_symbol_results
        } else {
            Vec::new()
        },
        risk_overlay: if row.status == "complete" {
            Some(StrategyRiskOverlay {
                loss_trigger_pct: SYMBOL_PAUSE_LOSS_TRIGGER_PCT,
                pause_folds: SYMBOL_PAUSE_FOLDS,
            })
        } else {
            None
        },
        selected_candidates,
    }
}

fn primary_artifact_selection(
    rows: &[StrategyRow],
    symbols: &[String],
    strategy_selections: &BTreeMap<(String, String, String, usize), FoldSelection>,
    best_by_fold: &BTreeMap<usize, FoldSelection>,
    fixed_notional: f64,
) -> PrimaryArtifactSelection {
    let best_fold_selections = best_by_fold.values().cloned().collect::<Vec<_>>();
    let mut best_fold_trades = best_fold_selections
        .iter()
        .flat_map(|selection| selection.trades.clone())
        .collect::<Vec<_>>();
    best_fold_trades.sort_by_key(|trade| trade.exit_time_ms);
    let best_fold_scores = best_fold_selections
        .iter()
        .map(|selection| selection.score.clone())
        .collect::<Vec<_>>();
    let legacy_best_indicator = best_fold_selections
        .iter()
        .max_by(|left, right| left.rank_score.total_cmp(&right.rank_score))
        .map(|selection| selection.indicator.as_str().to_string())
        .unwrap_or_else(|| "none".to_string());

    let completed_rows = rows
        .iter()
        .filter(|row| row.runnable && row.parameter_candidates > 0 && row.status == "complete")
        .collect::<Vec<_>>();
    if completed_rows.len() == 1 {
        let row = completed_rows[0];
        let mut trades = strategy_trades_for_row(row, strategy_selections);
        trades.sort_by_key(|trade| trade.exit_time_ms);
        let mut scores = strategy_scores_for_row(row, strategy_selections);
        scores.sort_by(|left, right| {
            left.symbol
                .cmp(&right.symbol)
                .then(left.fold_index.cmp(&right.fold_index))
                .then(left.candidate_id.cmp(&right.candidate_id))
        });
        let has_selection = !scores.is_empty();
        let mut risk_managed_trades =
            strategy_risk_managed_trades_for_row(row, symbols, strategy_selections, fixed_notional);
        risk_managed_trades.sort_by_key(|trade| trade.exit_time_ms);
        return PrimaryArtifactSelection {
            trades,
            scores,
            best_indicator: if has_selection {
                format!("{} {}", row.indicator, row.timeframe)
            } else {
                "none".to_string()
            },
            best_fold_trades: Some(best_fold_trades),
            best_fold_scores: Some(best_fold_scores),
            risk_managed_trades: has_selection.then_some(risk_managed_trades),
        };
    }

    PrimaryArtifactSelection {
        trades: best_fold_trades,
        scores: best_fold_scores,
        best_indicator: legacy_best_indicator,
        best_fold_trades: None,
        best_fold_scores: None,
        risk_managed_trades: None,
    }
}

fn strategy_trades_for_row(
    row: &StrategyRow,
    selections: &BTreeMap<(String, String, String, usize), FoldSelection>,
) -> Vec<Trade> {
    selections
        .iter()
        .filter(|((indicator, timeframe, _, _), _)| {
            indicator == &row.indicator && timeframe == &row.timeframe
        })
        .flat_map(|(_, selection)| selection.trades.clone())
        .collect()
}

fn strategy_scores_for_row(
    row: &StrategyRow,
    selections: &BTreeMap<(String, String, String, usize), FoldSelection>,
) -> Vec<CandidateScore> {
    selections
        .iter()
        .filter(|((indicator, timeframe, _, _), _)| {
            indicator == &row.indicator && timeframe == &row.timeframe
        })
        .map(|(_, selection)| selection.score.clone())
        .collect()
}

fn strategy_risk_managed_trades_for_row(
    row: &StrategyRow,
    symbols: &[String],
    selections: &BTreeMap<(String, String, String, usize), FoldSelection>,
    fixed_notional: f64,
) -> Vec<Trade> {
    symbols
        .iter()
        .flat_map(|symbol| risk_managed_trades_for_symbol(row, symbol, selections, fixed_notional))
        .collect()
}

fn risk_managed_trades_for_symbol(
    row: &StrategyRow,
    symbol: &str,
    selections: &BTreeMap<(String, String, String, usize), FoldSelection>,
    fixed_notional: f64,
) -> Vec<Trade> {
    let mut selected = selections
        .iter()
        .filter(|((indicator, timeframe, selected_symbol, _), _)| {
            indicator == &row.indicator && timeframe == &row.timeframe && selected_symbol == symbol
        })
        .map(|((_, _, _, fold_index), selection)| (*fold_index, selection))
        .collect::<Vec<_>>();
    selected.sort_by_key(|(fold_index, _)| *fold_index);

    let mut paused_until_fold = 0usize;
    let mut trades = Vec::new();
    for (fold_index, selection) in selected {
        if fold_index < paused_until_fold {
            continue;
        }
        let oos_total_pnl = selection.trades.iter().map(|trade| trade.pnl).sum::<f64>();
        let oos_net_return_pct = oos_total_pnl / fixed_notional.max(1.0) * 100.0;
        trades.extend(selection.trades.clone());
        if oos_net_return_pct <= SYMBOL_PAUSE_LOSS_TRIGGER_PCT {
            paused_until_fold = fold_index + 1 + SYMBOL_PAUSE_FOLDS;
        }
    }
    trades
}

fn strategy_oos_selected_candidates(
    row: &StrategyRow,
    selections: &BTreeMap<(String, String, String, usize), FoldSelection>,
    candidates_by_id: &BTreeMap<usize, Candidate>,
    fixed_notional: f64,
) -> Vec<StrategyOosSelection> {
    let mut selected = selections
        .iter()
        .filter(|((indicator, timeframe, _, _), _)| {
            indicator == &row.indicator && timeframe == &row.timeframe
        })
        .map(|((_, _, symbol, fold_index), selection)| {
            let oos_total_pnl = selection.trades.iter().map(|trade| trade.pnl).sum::<f64>();
            StrategyOosSelection {
                symbol: symbol.clone(),
                fold_index: *fold_index,
                candidate_id: selection.score.candidate_id,
                candidate: candidates_by_id.get(&selection.score.candidate_id).cloned(),
                score: selection.score.clone(),
                oos_trades: selection.trades.len(),
                oos_total_pnl,
                oos_net_return_pct: oos_total_pnl / fixed_notional.max(1.0) * 100.0,
            }
        })
        .collect::<Vec<_>>();
    selected.sort_by(|left, right| {
        left.symbol
            .cmp(&right.symbol)
            .then(left.fold_index.cmp(&right.fold_index))
    });
    selected
}

fn strategy_oos_metrics(
    trades: &[Trade],
    fixed_notional: f64,
    start_ms: i64,
    end_ms: i64,
    close_by_symbol: &BTreeMap<String, BTreeMap<i64, f64>>,
) -> StrategyOosMetrics {
    let total_pnl = trades.iter().map(|trade| trade.pnl).sum::<f64>();
    let winning_pnl = trades
        .iter()
        .filter(|trade| trade.pnl > 0.0)
        .map(|trade| trade.pnl)
        .sum::<f64>();
    let losing_pnl = trades
        .iter()
        .filter(|trade| trade.pnl < 0.0)
        .map(|trade| trade.pnl.abs())
        .sum::<f64>();
    let returns = trades
        .iter()
        .map(|trade| trade.return_pct / 100.0)
        .collect::<Vec<_>>();
    let max_drawdown_pct =
        strategy_mtm_max_drawdown_pct(trades, start_ms, end_ms, close_by_symbol, fixed_notional);
    let equity_curve = strategy_mtm_equity_curve(trades, start_ms, end_ms, close_by_symbol, 90);
    let participation = strategy_entry_participation(trades, start_ms, end_ms);
    StrategyOosMetrics {
        net_return_pct: total_pnl / fixed_notional.max(1.0) * 100.0,
        total_pnl,
        max_drawdown_pct,
        trades: trades.len(),
        total_oos_days: participation.total_days,
        entry_days: participation.entry_days,
        no_entry_days: participation.no_entry_days,
        entry_day_pct: participation.entry_day_pct,
        total_oos_weeks: participation.total_weeks,
        entry_weeks: participation.entry_weeks,
        no_entry_weeks: participation.no_entry_weeks,
        entry_week_pct: participation.entry_week_pct,
        longest_no_entry_gap_days: participation.longest_no_entry_gap_days,
        win_rate: if trades.is_empty() {
            0.0
        } else {
            trades.iter().filter(|trade| trade.pnl > 0.0).count() as f64 / trades.len() as f64
                * 100.0
        },
        profit_factor: if losing_pnl > 0.0 {
            winning_pnl / losing_pnl
        } else if winning_pnl > 0.0 {
            999.0
        } else {
            0.0
        },
        sharpe: sharpe(&returns, false),
        equity_curve,
    }
}

#[derive(Debug, Clone, Copy, Default)]
struct StrategyEntryParticipation {
    total_days: usize,
    entry_days: usize,
    no_entry_days: usize,
    entry_day_pct: f64,
    total_weeks: usize,
    entry_weeks: usize,
    no_entry_weeks: usize,
    entry_week_pct: f64,
    longest_no_entry_gap_days: usize,
}

fn strategy_mtm_max_drawdown_pct(
    trades: &[Trade],
    start_ms: i64,
    end_ms: i64,
    close_by_symbol: &BTreeMap<String, BTreeMap<i64, f64>>,
    denominator: f64,
) -> f64 {
    let mut by_entry = trades.to_vec();
    by_entry.sort_by_key(|trade| trade.entry_time_ms);
    let mut by_exit = trades.to_vec();
    by_exit.sort_by_key(|trade| trade.exit_time_ms);
    let mut entry_idx = 0usize;
    let mut exit_idx = 0usize;
    let mut active = Vec::new();
    let mut realized_pnl = 0.0;
    let mut peak = 0.0;
    let mut max_drawdown: f64 = 0.0;
    let mut ts = start_ms;
    while ts <= end_ms {
        while entry_idx < by_entry.len() && by_entry[entry_idx].entry_time_ms <= ts {
            if by_entry[entry_idx].exit_time_ms > ts {
                active.push(by_entry[entry_idx].clone());
            }
            entry_idx += 1;
        }
        while exit_idx < by_exit.len() && by_exit[exit_idx].exit_time_ms <= ts {
            realized_pnl += by_exit[exit_idx].pnl;
            if let Some(index) = active.iter().position(|trade| *trade == by_exit[exit_idx]) {
                active.remove(index);
            }
            exit_idx += 1;
        }
        let unrealized_pnl = active
            .iter()
            .map(|trade| mark_to_market(trade, ts, close_by_symbol))
            .sum::<f64>();
        let equity = realized_pnl + unrealized_pnl;
        peak = f64::max(peak, equity);
        max_drawdown = f64::max(max_drawdown, peak - equity);
        ts = ts.saturating_add(MS_PER_MINUTE);
    }
    max_drawdown / denominator.max(1.0) * 100.0
}

fn strategy_entry_participation(
    trades: &[Trade],
    start_ms: i64,
    end_ms: i64,
) -> StrategyEntryParticipation {
    entry_participation(trades.iter(), start_ms, end_ms)
}

fn entry_participation_from_trade_refs(
    trades: &[&Trade],
    start_ms: i64,
    end_ms: i64,
) -> StrategyEntryParticipation {
    entry_participation(trades.iter().copied(), start_ms, end_ms)
}

fn entry_participation<'a>(
    trades: impl IntoIterator<Item = &'a Trade>,
    start_ms: i64,
    end_ms: i64,
) -> StrategyEntryParticipation {
    if end_ms <= start_ms {
        return StrategyEntryParticipation::default();
    }
    let total_days = ((end_ms - start_ms) as f64 / Duration::days(1).num_milliseconds() as f64)
        .ceil()
        .max(1.0) as usize;
    let total_weeks = ((end_ms - start_ms) as f64 / Duration::weeks(1).num_milliseconds() as f64)
        .ceil()
        .max(1.0) as usize;
    let mut entry_days = BTreeSet::new();
    let mut entry_weeks = BTreeSet::new();
    for trade in trades {
        if trade.entry_time_ms < start_ms || trade.entry_time_ms >= end_ms {
            continue;
        }
        let day_index = ((trade.entry_time_ms - start_ms) / Duration::days(1).num_milliseconds())
            .clamp(0, total_days.saturating_sub(1) as i64) as usize;
        let week_index = ((trade.entry_time_ms - start_ms) / Duration::weeks(1).num_milliseconds())
            .clamp(0, total_weeks.saturating_sub(1) as i64) as usize;
        entry_days.insert(day_index);
        entry_weeks.insert(week_index);
    }
    let mut longest_gap = 0usize;
    let mut current_gap = 0usize;
    for day_index in 0..total_days {
        if entry_days.contains(&day_index) {
            longest_gap = longest_gap.max(current_gap);
            current_gap = 0;
        } else {
            current_gap += 1;
        }
    }
    longest_gap = longest_gap.max(current_gap);
    let entry_days_count = entry_days.len();
    let entry_weeks_count = entry_weeks.len();
    StrategyEntryParticipation {
        total_days,
        entry_days: entry_days_count,
        no_entry_days: total_days.saturating_sub(entry_days_count),
        entry_day_pct: entry_days_count as f64 / total_days as f64 * 100.0,
        total_weeks,
        entry_weeks: entry_weeks_count,
        no_entry_weeks: total_weeks.saturating_sub(entry_weeks_count),
        entry_week_pct: entry_weeks_count as f64 / total_weeks as f64 * 100.0,
        longest_no_entry_gap_days: longest_gap,
    }
}

fn strategy_mtm_equity_curve(
    trades: &[Trade],
    start_ms: i64,
    end_ms: i64,
    close_by_symbol: &BTreeMap<String, BTreeMap<i64, f64>>,
    max_points: usize,
) -> Vec<StrategyCurvePoint> {
    let mut by_entry = trades.to_vec();
    by_entry.sort_by_key(|trade| trade.entry_time_ms);
    let mut by_exit = trades.to_vec();
    by_exit.sort_by_key(|trade| trade.exit_time_ms);
    let span_minutes = ((end_ms - start_ms) / MS_PER_MINUTE).max(1) as usize;
    let target_points = max_points.max(2);
    let step_minutes = (span_minutes as f64 / (target_points - 1) as f64)
        .ceil()
        .max(1.0) as i64;
    let step_ms = step_minutes * MS_PER_MINUTE;
    let mut entry_idx = 0usize;
    let mut exit_idx = 0usize;
    let mut active = Vec::new();
    let mut realized_pnl = 0.0;
    let mut points = Vec::with_capacity(target_points + 1);
    let mut ts = start_ms;
    while ts <= end_ms {
        while entry_idx < by_entry.len() && by_entry[entry_idx].entry_time_ms <= ts {
            if by_entry[entry_idx].exit_time_ms > ts {
                active.push(by_entry[entry_idx].clone());
            }
            entry_idx += 1;
        }
        while exit_idx < by_exit.len() && by_exit[exit_idx].exit_time_ms <= ts {
            realized_pnl += by_exit[exit_idx].pnl;
            if let Some(index) = active.iter().position(|trade| *trade == by_exit[exit_idx]) {
                active.remove(index);
            }
            exit_idx += 1;
        }
        let unrealized_pnl = active
            .iter()
            .map(|trade| mark_to_market(trade, ts, close_by_symbol))
            .sum::<f64>();
        points.push(StrategyCurvePoint {
            timestamp_ms: ts,
            equity: realized_pnl + unrealized_pnl,
        });
        ts = ts.saturating_add(step_ms);
        if ts > end_ms && points.last().map(|point| point.timestamp_ms) != Some(end_ms) {
            ts = end_ms;
        }
    }
    points
}

fn read_json<T: for<'de> Deserialize<'de>>(path: PathBuf) -> Result<T> {
    let file = File::open(&path).with_context(|| format!("open {}", path.display()))?;
    Ok(serde_json::from_reader(file)?)
}

fn initial_strategy_progress(candidates: &[Candidate]) -> Vec<StrategyRow> {
    let mut counts: BTreeMap<(String, String), usize> = BTreeMap::new();
    for candidate in candidates {
        *counts.entry(strategy_key(candidate)).or_default() += 1;
    }
    let mut rows = Vec::new();
    for indicator in IndicatorKind::CATALOG {
        if !indicator.is_runnable_strategy() {
            rows.push(StrategyRow {
                indicator: indicator.as_str().to_string(),
                timeframe: "n/a".to_string(),
                implementation_status: indicator.implementation_status().to_string(),
                implementation_note: indicator.implementation_note().to_string(),
                runnable: false,
                parameter_candidates: 0,
                status: indicator.implementation_status().to_string(),
                progress_pct: 0.0,
                progress_label: "not runnable".to_string(),
                folds_scored: 0,
                best_score: 0.0,
                net_return_pct: 0.0,
                max_drawdown_pct: 0.0,
                trades: 0,
            });
            continue;
        }
        for timeframe in Timeframe::ALL {
            let key = (
                indicator.as_str().to_string(),
                timeframe.as_str().to_string(),
            );
            let parameter_candidates = counts.get(&key).copied().unwrap_or_default();
            rows.push(StrategyRow {
                indicator: key.0,
                timeframe: key.1,
                implementation_status: indicator.implementation_status().to_string(),
                implementation_note: indicator.implementation_note().to_string(),
                runnable: true,
                parameter_candidates,
                status: if parameter_candidates > 0 {
                    "pending".to_string()
                } else {
                    "not_in_grid".to_string()
                },
                progress_pct: 0.0,
                progress_label: String::new(),
                folds_scored: 0,
                best_score: 0.0,
                net_return_pct: 0.0,
                max_drawdown_pct: 0.0,
                trades: 0,
            });
        }
    }
    rows.sort_by_key(|row| {
        (
            indicator_rank(&row.indicator),
            timeframe_rank(&row.timeframe),
        )
    });
    rows
}

fn initial_strategy_counts(candidates: &[Candidate]) -> BTreeMap<(String, String), usize> {
    let mut out = BTreeMap::new();
    for candidate in candidates {
        out.entry(strategy_key(candidate)).or_insert(0);
    }
    out
}

fn initial_strategy_counts_from_rows(
    candidates: &[Candidate],
    rows: &[StrategyRow],
    totals: &BTreeMap<(String, String), usize>,
) -> BTreeMap<(String, String), usize> {
    let mut out = initial_strategy_counts(candidates);
    for row in rows.iter().filter(|row| row.status == "complete") {
        let key = (row.indicator.clone(), row.timeframe.clone());
        if let Some(count) = out.get_mut(&key) {
            *count = totals.get(&key).copied().unwrap_or_default();
        }
    }
    out
}

fn merge_strategy_progress_rows(rows: &mut Vec<StrategyRow>, candidates: &[Candidate]) {
    for template in initial_strategy_progress(candidates) {
        if let Some(row) = rows
            .iter_mut()
            .find(|row| row.indicator == template.indicator && row.timeframe == template.timeframe)
        {
            row.implementation_status = template.implementation_status;
            row.implementation_note = template.implementation_note;
            row.runnable = template.runnable;
            row.parameter_candidates = template.parameter_candidates;
        } else {
            rows.push(template);
        }
    }
    rows.sort_by_key(|row| {
        (
            indicator_rank(&row.indicator),
            timeframe_rank(&row.timeframe),
        )
    });
}

fn normalize_resumed_strategy_progress(rows: &mut [StrategyRow], resume_mode: bool) {
    if !resume_mode {
        return;
    }
    for row in rows {
        if row.status == "complete" {
            row.progress_pct = 100.0;
            if row.progress_label.is_empty() {
                row.progress_label = "complete".to_string();
            }
        } else if row.runnable && row.parameter_candidates > 0 {
            row.status = "pending".to_string();
            row.progress_pct = 0.0;
            row.progress_label = "resume pending".to_string();
            row.folds_scored = 0;
            row.best_score = 0.0;
            row.net_return_pct = 0.0;
            row.max_drawdown_pct = 0.0;
            row.trades = 0;
        }
    }
}

fn strategy_candidate_groups(
    candidates: &[Candidate],
    rows: &[StrategyRow],
) -> Vec<((String, String), Vec<Candidate>)> {
    let mut by_strategy: BTreeMap<(String, String), Vec<Candidate>> = BTreeMap::new();
    for candidate in candidates {
        by_strategy
            .entry(strategy_key(candidate))
            .or_default()
            .push(candidate.clone());
    }
    rows.iter()
        .filter(|row| row.runnable && row.parameter_candidates > 0)
        .filter(|row| row.status != "complete")
        .filter_map(|row| {
            let key = (row.indicator.clone(), row.timeframe.clone());
            by_strategy.remove(&key).map(|candidates| (key, candidates))
        })
        .collect()
}

fn mark_strategy_row_running(rows: &mut [StrategyRow], key: &(String, String)) {
    let Some(row) = rows
        .iter_mut()
        .find(|row| row.indicator == key.0 && row.timeframe == key.1)
    else {
        return;
    };
    if row.status != "complete" {
        row.status = "running".to_string();
        row.progress_label = if row.parameter_candidates > 0 {
            "0/0 symbols (0 evals)".to_string()
        } else {
            "0 evals".to_string()
        };
    }
}

fn strategy_totals(
    candidates: &[Candidate],
    symbols: &[String],
    strategy_set: Option<&str>,
    grid: GridSize,
) -> BTreeMap<(String, String), usize> {
    let mut out = BTreeMap::new();
    for candidate in candidates {
        let work_units = if grid == GridSize::Tpe {
            1
        } else {
            symbols
                .iter()
                .filter(|symbol| candidate_allowed_for_symbol(strategy_set, symbol, candidate))
                .count()
        };
        *out.entry(strategy_key(candidate)).or_default() += work_units;
    }
    out
}

fn strategy_key(candidate: &Candidate) -> (String, String) {
    (
        candidate.indicator.as_str().to_string(),
        candidate.timeframe.as_str().to_string(),
    )
}

fn update_strategy_row(
    rows: &mut [StrategyRow],
    key: &(String, String),
    candidate_score: f64,
    fold_scores: &[CandidateScore],
    trade_count: usize,
    completed: usize,
    total: usize,
) {
    let Some(row) = rows
        .iter_mut()
        .find(|row| row.indicator == key.0 && row.timeframe == key.1)
    else {
        return;
    };
    row.status = if completed >= total {
        "complete".to_string()
    } else {
        "running".to_string()
    };
    row.progress_pct = (completed as f64 / total.max(1) as f64 * 100.0).min(100.0);
    row.progress_label = if total == row.parameter_candidates {
        format!("{completed}/{total} trials")
    } else if row.parameter_candidates > 0 {
        let completed_symbols = completed / row.parameter_candidates;
        let total_symbols = total / row.parameter_candidates;
        format!(
            "{}/{} symbols ({} evals)",
            completed_symbols, total_symbols, completed
        )
    } else {
        format!("{completed}/{total} evals")
    };
    row.folds_scored = fold_scores.len();
    if candidate_score >= row.best_score || row.trades == 0 {
        row.best_score = candidate_score;
        row.net_return_pct = fold_scores
            .iter()
            .map(|score| score.net_return_pct)
            .sum::<f64>()
            / fold_scores.len().max(1) as f64;
        row.max_drawdown_pct = fold_scores
            .iter()
            .map(|score| score.max_drawdown_pct)
            .fold(0.0, f64::max);
        row.trades = trade_count;
    }
}

fn mean_score(scores: &[CandidateScore]) -> f64 {
    scores.iter().map(|score| score.score).sum::<f64>() / scores.len().max(1) as f64
}

#[cfg(test)]
fn tpe_objective_score(
    training_scores: &[CandidateScore],
    validation_scores: &[CandidateScore],
) -> f64 {
    tpe_objective_breakdown(training_scores, validation_scores).objective_score
}

fn tpe_objective_breakdown(
    training_scores: &[CandidateScore],
    validation_scores: &[CandidateScore],
) -> TpeObjectiveBreakdown {
    if validation_scores.is_empty() {
        return TpeObjectiveBreakdown {
            objective_score: INELIGIBLE_SCORE_CUTOFF - 500.0,
            training_mean_score: 0.0,
            validation_mean_score: 0.0,
            training_q25_score: 0.0,
            training_median_score: 0.0,
            validation_q25_score: 0.0,
            validation_median_score: 0.0,
            validation_score_stddev: 0.0,
            training_eligible_fraction: 0.0,
            validation_eligible_fraction: 0.0,
            validation_net_positive_fraction: 0.0,
            validation_trade_fit_fraction: 0.0,
            validation_quality_fit_fraction: 0.0,
            validation_median_profit_factor: 0.0,
            training_nonnegative_score_fraction: 0.0,
            validation_nonnegative_score_fraction: 0.0,
            average_trade_penalty: 0.0,
            average_profit_factor_penalty: 0.0,
            average_net_penalty: 0.0,
            average_fill_penalty: 0.0,
            average_participation_penalty: 0.0,
            base_objective_component: 0.0,
            consistency_bonus: 0.0,
            paired_bonus: 0.0,
            paired_selection_fraction: 0.0,
            paired_selection_count: 0,
            train_gap_penalty: 0.0,
            dispersion_penalty: 0.0,
        };
    }
    let validation_mean = mean_score(validation_scores);
    let training_mean = mean_score(training_scores);
    let training_values = training_scores
        .iter()
        .map(|score| score.score)
        .collect::<Vec<_>>();
    let validation_values = validation_scores
        .iter()
        .map(|score| score.score)
        .collect::<Vec<_>>();
    let training_q25 = percentile(&training_values, 0.25);
    let training_median = percentile(&training_values, 0.50);
    let validation_q25 = percentile(&validation_values, 0.25);
    let validation_median = percentile(&validation_values, 0.50);
    let validation_stddev = sample_stddev(&validation_values);
    let validation_eligible = eligible_score_fraction(validation_scores);
    let training_eligible = eligible_score_fraction(training_scores);
    let validation_nonnegative = nonnegative_score_fraction(validation_scores);
    let training_nonnegative = nonnegative_score_fraction(training_scores);
    let validation_net_positive =
        fraction_matching(validation_scores, |score| score.net_return_pct > 0.0);
    let validation_trade_fit =
        fraction_matching(validation_scores, |score| score.trade_fit == "ok");
    let validation_quality_fit =
        fraction_matching(validation_scores, |score| score.quality_fit == "ok");
    let validation_pf_values = validation_scores
        .iter()
        .map(|score| score.profit_factor.clamp(0.0, 10.0))
        .collect::<Vec<_>>();
    let validation_median_profit_factor = percentile(&validation_pf_values, 0.50);
    let penalty_breakdown = average_score_penalties(validation_scores);
    let paired_ranks = paired_generalization_rank_scores(training_scores, validation_scores);
    let paired_fraction = paired_ranks.len() as f64 / validation_scores.len().max(1) as f64;
    let paired_mean = if paired_ranks.is_empty() {
        0.0
    } else {
        paired_ranks.iter().sum::<f64>() / paired_ranks.len() as f64
    };
    let paired_q25 = percentile(&paired_ranks, 0.25);
    let paired_median = percentile(&paired_ranks, 0.50);
    let train_gap_penalty = if training_median <= INELIGIBLE_SCORE_CUTOFF {
        (INELIGIBLE_SCORE_CUTOFF - training_median).min(500.0) * 0.05
    } else {
        (training_median - validation_median).max(0.0) * TPE_OBJECTIVE_OVERFIT_GAP_PENALTY_WEIGHT
    };
    let dispersion_penalty = validation_stddev.min(500.0) * TPE_OBJECTIVE_DISPERSION_PENALTY_WEIGHT;

    let min_profit_factor = validation_scores
        .first()
        .map(|score| score.min_profit_factor)
        .unwrap_or(DEFAULT_MIN_PROFIT_FACTOR)
        .max(1.0);
    let pf_consistency_bonus =
        ((validation_median_profit_factor / min_profit_factor).ln()).clamp(-1.0, 1.0) * 12.0;
    let paired_count_bonus =
        paired_ranks.len().saturating_sub(1) as f64 * TPE_PAIRED_COUNT_OBJECTIVE_WEIGHT;
    let paired_bonus = if paired_ranks.is_empty() {
        0.0
    } else {
        paired_fraction * 1_000.0
            + paired_count_bonus
            + paired_q25 * 8.0
            + paired_median * 5.0
            + paired_mean * 2.0
    };
    let consistency_bonus =
        10.0 * validation_net_positive + 6.0 * validation_trade_fit + 6.0 * validation_quality_fit;
    let base_objective_component = validation_q25 * 0.30
        + validation_median * 0.35
        + validation_mean * 0.20
        + training_q25 * 0.15;
    let objective_score = base_objective_component
        + paired_bonus
        + consistency_bonus
        + pf_consistency_bonus
        + validation_eligible * 60.0
        + training_eligible * 30.0
        + validation_nonnegative * 12.0
        + training_nonnegative * 6.0
        - train_gap_penalty
        - dispersion_penalty * 0.25
        - penalty_breakdown.trade * 0.20
        - penalty_breakdown.profit_factor * 0.25
        - penalty_breakdown.net * 0.15
        - penalty_breakdown.fill * 0.20
        - penalty_breakdown.participation * 0.20;
    TpeObjectiveBreakdown {
        objective_score,
        training_mean_score: training_mean,
        validation_mean_score: validation_mean,
        training_q25_score: training_q25,
        training_median_score: training_median,
        validation_q25_score: validation_q25,
        validation_median_score: validation_median,
        validation_score_stddev: validation_stddev,
        training_eligible_fraction: training_eligible,
        validation_eligible_fraction: validation_eligible,
        validation_net_positive_fraction: validation_net_positive,
        validation_trade_fit_fraction: validation_trade_fit,
        validation_quality_fit_fraction: validation_quality_fit,
        validation_median_profit_factor,
        training_nonnegative_score_fraction: training_nonnegative,
        validation_nonnegative_score_fraction: validation_nonnegative,
        average_trade_penalty: penalty_breakdown.trade,
        average_profit_factor_penalty: penalty_breakdown.profit_factor,
        average_net_penalty: penalty_breakdown.net,
        average_fill_penalty: penalty_breakdown.fill,
        average_participation_penalty: penalty_breakdown.participation,
        base_objective_component,
        consistency_bonus,
        paired_bonus,
        paired_selection_fraction: paired_fraction,
        paired_selection_count: paired_ranks.len(),
        train_gap_penalty,
        dispersion_penalty,
    }
}

fn percentile(values: &[f64], percentile: f64) -> f64 {
    let mut values = values
        .iter()
        .copied()
        .filter(|value| value.is_finite())
        .collect::<Vec<_>>();
    if values.is_empty() {
        return 0.0;
    }
    values.sort_by(f64::total_cmp);
    let position =
        (values.len().saturating_sub(1) as f64 * percentile.clamp(0.0, 1.0)).round() as usize;
    values[position.min(values.len() - 1)]
}

fn sample_stddev(values: &[f64]) -> f64 {
    let values = values
        .iter()
        .copied()
        .filter(|value| value.is_finite())
        .collect::<Vec<_>>();
    if values.len() < 2 {
        return 0.0;
    }
    let mean = values.iter().sum::<f64>() / values.len() as f64;
    let variance = values
        .iter()
        .map(|value| {
            let delta = value - mean;
            delta * delta
        })
        .sum::<f64>()
        / (values.len() - 1) as f64;
    variance.sqrt()
}

fn fraction_matching(
    scores: &[CandidateScore],
    predicate: impl Fn(&CandidateScore) -> bool,
) -> f64 {
    if scores.is_empty() {
        return 0.0;
    }
    scores.iter().filter(|score| predicate(score)).count() as f64 / scores.len() as f64
}

fn paired_generalization_rank_scores(
    training_scores: &[CandidateScore],
    validation_scores: &[CandidateScore],
) -> Vec<f64> {
    training_scores
        .iter()
        .zip(validation_scores.iter())
        .filter_map(|(training_score, validation_score)| {
            if candidate_score_is_selectable(training_score, MIN_SELECTABLE_SCORE)
                && candidate_score_is_selectable(validation_score, TPE_MIN_SELECTION_SCORE)
            {
                Some(paired_generalization_rank_score(
                    training_score.score,
                    validation_score.score,
                ))
            } else {
                None
            }
        })
        .collect()
}

fn eligible_score_fraction(scores: &[CandidateScore]) -> f64 {
    if scores.is_empty() {
        return 0.0;
    }
    scores
        .iter()
        .filter(|score| candidate_score_is_selectable(score, MIN_SELECTABLE_SCORE))
        .count() as f64
        / scores.len() as f64
}

fn nonnegative_score_fraction(scores: &[CandidateScore]) -> f64 {
    if scores.is_empty() {
        return 0.0;
    }
    scores.iter().filter(|score| score.score >= 0.0).count() as f64 / scores.len() as f64
}

fn average_score_penalties(scores: &[CandidateScore]) -> ScorePenaltyBreakdown {
    if scores.is_empty() {
        return ScorePenaltyBreakdown::default();
    }
    let mut total = ScorePenaltyBreakdown::default();
    for score in scores {
        let penalties = score_soft_penalties(score);
        total.trade += penalties.trade;
        total.profit_factor += penalties.profit_factor;
        total.net += penalties.net;
        total.fill += penalties.fill;
        total.participation += penalties.participation;
    }
    let denominator = scores.len() as f64;
    ScorePenaltyBreakdown {
        trade: total.trade / denominator,
        profit_factor: total.profit_factor / denominator,
        net: total.net / denominator,
        fill: total.fill / denominator,
        participation: total.participation / denominator,
    }
}

fn read_csv<T: for<'de> Deserialize<'de>>(path: PathBuf) -> Result<Vec<T>> {
    let mut reader = csv::Reader::from_path(path)?;
    reader
        .deserialize()
        .collect::<Result<Vec<T>, csv::Error>>()
        .map_err(Into::into)
}

fn artifact_row_count(path: &Path) -> Option<usize> {
    let extension = path.extension()?.to_string_lossy();
    match extension.as_ref() {
        "csv" => csv::Reader::from_path(path)
            .ok()
            .map(|mut reader| reader.records().count()),
        "jsonl" => fs::read_to_string(path)
            .ok()
            .map(|text| text.lines().count()),
        _ => None,
    }
}

fn default_checks() -> Vec<CheckRow> {
    ["cargo test", "clippy", "smoke WFO", "dashboard endpoints"]
        .into_iter()
        .map(|name| CheckRow {
            name: name.to_string(),
            status: "not_recorded".to_string(),
            command: String::new(),
            details: String::new(),
            finished_at: Utc::now(),
        })
        .collect()
}

fn latest_run_dir() -> Result<Option<PathBuf>> {
    let runs = list_runs()?;
    Ok(runs
        .into_iter()
        .find(|run| run.status.is_some())
        .map(|run| PathBuf::from(run.path)))
}

fn date_ms(date: NaiveDate) -> Result<i64> {
    Ok(Utc
        .from_utc_datetime(&date.and_hms_opt(0, 0, 0).context("valid midnight")?)
        .timestamp_millis())
}

fn synthetic_market(symbol: &str, start_ms: i64, rows: usize) -> Vec<OhlcvBar> {
    let phase = symbol.bytes().map(f64::from).sum::<f64>() % 37.0;
    (0..rows)
        .map(|i| {
            let t = i as f64;
            let close = 100.0 + t * 0.002 + ((t + phase) / 50.0).sin() * 2.0;
            let open = close - ((t + phase) / 17.0).sin() * 0.15;
            OhlcvBar {
                open_time_ms: start_ms + i as i64 * MS_PER_MINUTE,
                open,
                high: open.max(close) + 0.35,
                low: open.min(close) - 0.35,
                close,
                volume: 1_000.0 + (t % 200.0),
            }
        })
        .collect()
}

fn synthetic_row_count(config: &WfoConfig) -> Result<usize> {
    let start = date_ms(config.start)?;
    let end = date_ms(config.end)?;
    Ok(((end - start) / MS_PER_MINUTE).max(1) as usize)
}

fn max_drawdown_pct_from_trade_refs(trades: &[&Trade]) -> f64 {
    let notional = trades
        .first()
        .map(|trade| trade.entry_price * trade.quantity)
        .unwrap_or(1.0)
        .max(1.0);
    max_drawdown_cash_from_pnls(trades.iter().map(|trade| trade.pnl)) / notional * 100.0
}

#[cfg(test)]
fn max_drawdown_pct_from_trades(trades: &[Trade]) -> f64 {
    let notional = trades
        .first()
        .map(|trade| trade.entry_price * trade.quantity)
        .unwrap_or(1.0)
        .max(1.0);
    max_drawdown_cash_from_pnls(trades.iter().map(|trade| trade.pnl)) / notional * 100.0
}

fn max_drawdown_cash_from_pnls<I>(pnls: I) -> f64
where
    I: IntoIterator<Item = f64>,
{
    let mut equity = 0.0;
    let mut peak = 0.0;
    let mut max_dd: f64 = 0.0;
    for pnl in pnls {
        equity += pnl;
        peak = f64::max(peak, equity);
        max_dd = f64::max(max_dd, peak - equity);
    }
    max_dd
}

fn sharpe(returns: &[f64], downside_only: bool) -> f64 {
    if returns.len() < 2 {
        return 0.0;
    }
    let mean = returns.iter().sum::<f64>() / returns.len() as f64;
    let variance = returns
        .iter()
        .filter(|value| !downside_only || **value < 0.0)
        .map(|value| (value - mean).powi(2))
        .sum::<f64>()
        / returns.len() as f64;
    if variance <= 0.0 {
        0.0
    } else {
        mean / variance.sqrt()
    }
}

fn weekly_consistency(trades: &[Trade]) -> f64 {
    if trades.is_empty() {
        return 0.0;
    }
    let mut weeks: BTreeMap<i64, f64> = BTreeMap::new();
    let week_ms = Duration::weeks(1).num_milliseconds();
    for trade in trades {
        *weeks
            .entry(trade.exit_time_ms.div_euclid(week_ms))
            .or_default() += trade.pnl;
    }
    weeks.values().filter(|pnl| **pnl > 0.0).count() as f64 / weeks.len() as f64
}

fn indicator_rank(value: &str) -> usize {
    IndicatorKind::CATALOG
        .iter()
        .position(|kind| kind.as_str() == value)
        .unwrap_or(usize::MAX)
}

fn timeframe_rank(value: &str) -> usize {
    Timeframe::ALL
        .iter()
        .position(|timeframe| timeframe.as_str() == value)
        .unwrap_or(usize::MAX)
}

#[allow(dead_code)]
fn parse_config_date(value: &str) -> Result<NaiveDate> {
    parse_date(value)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn score_input() -> CandidateScoreInput {
        CandidateScoreInput {
            net_return_pct: 2.0,
            max_drawdown_pct: 1.0,
            weekly_profit_fraction: 1.0,
            profit_factor: 1.2,
            trades: 12,
            trade_band: (4, 40),
            min_profit_factor: 1.2,
            average_trade_return_pct: 0.16,
            min_average_trade_return_pct: 0.0,
            trade_return_stddev_pct: 0.25,
            min_edge_t_stat: DEFAULT_MIN_EDGE_T_STAT,
            entry_attempts: 40,
            fill_rate_pct: 10.0,
            min_fill_rate_pct: MIN_FILL_RATE_SCORE_PCT,
            entry_day_pct: 100.0,
            min_entry_day_pct: MIN_CANDIDATE_ENTRY_DAY_PCT,
            entry_week_pct: 100.0,
            min_entry_week_pct: MIN_CANDIDATE_ENTRY_WEEK_PCT,
            longest_no_entry_gap_days: 0,
            max_no_entry_gap_days: MAX_CANDIDATE_NO_ENTRY_GAP_DAYS,
        }
    }

    fn candidate_metrics(
        net_return_pct: f64,
        profit_factor: f64,
        trades: usize,
    ) -> StrategyOosMetrics {
        StrategyOosMetrics {
            net_return_pct,
            total_pnl: net_return_pct * 10.0,
            max_drawdown_pct: 5.0,
            trades,
            total_oos_days: 100,
            entry_days: 60,
            no_entry_days: 40,
            entry_day_pct: 60.0,
            total_oos_weeks: 20,
            entry_weeks: 20,
            no_entry_weeks: 0,
            entry_week_pct: 100.0,
            longest_no_entry_gap_days: 3,
            win_rate: 50.0,
            profit_factor,
            sharpe: 0.0,
            equity_curve: Vec::new(),
        }
    }

    fn candidate_score(score: f64) -> CandidateScore {
        CandidateScore {
            candidate_id: 0,
            symbol: "BTCUSDT".to_string(),
            fold_index: 0,
            net_return_pct: 1.0,
            max_drawdown_pct: 1.0,
            weekly_profit_fraction: 1.0,
            profit_factor: 1.4,
            min_profit_factor: 1.2,
            average_trade_return_pct: 0.10,
            min_average_trade_return_pct: 0.0,
            trade_return_stddev_pct: 0.20,
            edge_t_stat: 1.58,
            min_edge_t_stat: DEFAULT_MIN_EDGE_T_STAT,
            entry_attempts: 20,
            filled_entries: 10,
            fill_rate_pct: 50.0,
            min_fill_rate_pct: MIN_FILL_RATE_SCORE_PCT,
            entry_day_pct: 100.0,
            min_entry_day_pct: MIN_CANDIDATE_ENTRY_DAY_PCT,
            entry_week_pct: 100.0,
            min_entry_week_pct: MIN_CANDIDATE_ENTRY_WEEK_PCT,
            longest_no_entry_gap_days: 0,
            max_no_entry_gap_days: MAX_CANDIDATE_NO_ENTRY_GAP_DAYS,
            trades: 10,
            min_trades: 2,
            max_trades: 100,
            trade_fit: "ok".to_string(),
            quality_fit: "ok".to_string(),
            score,
        }
    }

    fn test_trade(symbol: &str, entry_time_ms: i64, pnl: f64) -> Trade {
        Trade {
            symbol: symbol.to_string(),
            entry_time_ms,
            exit_time_ms: entry_time_ms + MS_PER_MINUTE,
            side: crate::engine::TradeSide::Long,
            entry_price: 100.0,
            exit_price: 100.0 + pnl,
            quantity: 1.0,
            pnl,
            return_pct: pnl,
            exit_reason: "test".to_string(),
        }
    }

    #[test]
    fn generates_four_week_is_one_week_oos_step_folds() {
        let start = date_ms(NaiveDate::from_ymd_opt(2025, 1, 1).unwrap()).unwrap();
        let end = date_ms(NaiveDate::from_ymd_opt(2025, 2, 12).unwrap()).unwrap();
        let folds = generate_folds(start, end, 4, 1, 1, 0);

        assert_eq!(folds.len(), 2);
        assert_eq!(folds[0].is_start_ms, start);
        assert_eq!(
            folds[0].oos_start_ms - folds[0].is_start_ms,
            Duration::weeks(4).num_milliseconds()
        );
        assert_eq!(
            folds[1].is_start_ms - folds[0].is_start_ms,
            Duration::weeks(1).num_milliseconds()
        );
    }

    #[test]
    fn new_configs_are_point_in_time_but_missing_mode_is_research_only() {
        let config = WfoConfig::new(GridSize::Tpe);
        assert_eq!(config.optimizer_mode, OptimizerMode::PointInTimeFoldLocal);

        let mut value = serde_json::to_value(&config).unwrap();
        value.as_object_mut().unwrap().remove("optimizer_mode");
        let legacy = serde_json::from_value::<WfoConfig>(value).unwrap();

        assert_eq!(
            legacy.optimizer_mode,
            OptimizerMode::RetrospectiveGlobalResearchOnly
        );
    }

    #[test]
    fn fold_local_candidate_ids_are_namespaced_by_fold() {
        let template_id = 42;

        assert_eq!(
            fold_local_candidate_id(template_id, 0),
            FOLD_LOCAL_CANDIDATE_ID_STRIDE + template_id
        );
        assert_ne!(
            fold_local_candidate_id(template_id, 0),
            fold_local_candidate_id(template_id, 1)
        );
    }

    #[test]
    fn point_in_time_boundary_rejects_future_timestamps() {
        let fold = Fold {
            index: 0,
            is_start_ms: 0,
            is_end_ms: 10 * MS_PER_MINUTE,
            oos_start_ms: 10 * MS_PER_MINUTE,
            oos_end_ms: 20 * MS_PER_MINUTE,
        };
        let bars = (0..12)
            .map(|index| OhlcvBar {
                open_time_ms: index * MS_PER_MINUTE,
                open: 100.0,
                high: 101.0,
                low: 99.0,
                close: 100.0,
                volume: 1.0,
            })
            .collect::<Vec<_>>();

        let objective_bars = bars_before_timestamp(&bars, fold.is_end_ms);
        let max_seen = max_bar_timestamp_seen(&objective_bars);

        assert_eq!(objective_bars.len(), 10);
        assert!(max_seen < fold.is_end_ms);
        assert!(ensure_optimizer_boundary(max_seen, &fold).is_ok());
        assert!(ensure_optimizer_boundary(fold.oos_start_ms + MS_PER_MINUTE, &fold).is_err());
    }

    #[test]
    fn optimizer_provenance_validation_checks_boundary_rows() {
        let dir =
            std::env::temp_dir().join(format!("rust_trend_provenance_test_{}", std::process::id()));
        let _ = fs::remove_dir_all(&dir);
        fs::create_dir_all(&dir).unwrap();

        assert!(!optimizer_provenance_boundary_passes(&dir).unwrap());

        let mut row = OptimizerProvenanceRow {
            optimizer_mode: OptimizerMode::PointInTimeFoldLocal.as_str().to_string(),
            offset_days: 0,
            fold_index: 0,
            strategy: "frama".to_string(),
            timeframe: "5m".to_string(),
            symbol: "BTCUSDT".to_string(),
            study_name: "study".to_string(),
            seed: 1,
            trials_requested: 1,
            trials_completed: 1,
            optimizer_scope_start: 0,
            optimizer_scope_end: 10,
            max_timestamp_seen: 10,
            selected_candidate_id: 1,
            params_signature: "sig".to_string(),
            is_score: 1.0,
            is_profit_factor: 1.2,
            is_trades: 1,
            is_max_drawdown_pct: 0.0,
            oos_total_pnl: 0.0,
            oos_net_return_pct: 0.0,
            oos_profit_factor: 0.0,
            oos_trades: 0,
            oos_max_drawdown_pct: 0.0,
            selection_status: "selected".to_string(),
            selection_reason: "test".to_string(),
        };
        write_csv(dir.join(OPTIMIZER_PROVENANCE_CSV_FILE), &[row.clone()]).unwrap();
        assert!(optimizer_provenance_boundary_passes(&dir).unwrap());

        row.max_timestamp_seen = 11;
        write_csv(dir.join(OPTIMIZER_PROVENANCE_CSV_FILE), &[row]).unwrap();
        assert!(!optimizer_provenance_boundary_passes(&dir).unwrap());

        let _ = fs::remove_dir_all(&dir);
    }

    #[test]
    fn generate_folds_can_skip_one_week_between_is_and_oos() {
        let start = date_ms(NaiveDate::from_ymd_opt(2025, 1, 1).unwrap()).unwrap();
        let end = date_ms(NaiveDate::from_ymd_opt(2025, 2, 12).unwrap()).unwrap();
        let folds = generate_folds(start, end, 4, 1, 1, 1);

        assert_eq!(folds.len(), 1);
        assert_eq!(folds[0].is_start_ms, start);
        assert_eq!(
            folds[0].is_end_ms - folds[0].is_start_ms,
            Duration::weeks(4).num_milliseconds()
        );
        assert_eq!(
            folds[0].oos_start_ms - folds[0].is_end_ms,
            Duration::weeks(1).num_milliseconds()
        );
        assert_eq!(
            folds[0].oos_end_ms - folds[0].oos_start_ms,
            Duration::weeks(1).num_milliseconds()
        );
    }

    #[test]
    fn generate_folds_days_supports_non_week_is_windows() {
        let start = date_ms(NaiveDate::from_ymd_opt(2025, 1, 1).unwrap()).unwrap();
        let end = date_ms(NaiveDate::from_ymd_opt(2025, 2, 1).unwrap()).unwrap();
        let folds = generate_folds_days(start, end, 9, 7, 7, 0);

        assert_eq!(folds.len(), 3);
        assert_eq!(
            folds[0].is_end_ms - folds[0].is_start_ms,
            Duration::days(9).num_milliseconds()
        );
        assert_eq!(folds[0].oos_start_ms, folds[0].is_end_ms);
        assert_eq!(
            folds[0].oos_end_ms - folds[0].oos_start_ms,
            Duration::days(7).num_milliseconds()
        );
        assert_eq!(
            folds[1].is_start_ms - folds[0].is_start_ms,
            Duration::days(7).num_milliseconds()
        );
    }

    #[test]
    fn fold_trade_slices_exclude_carry_in_and_carry_out_trades() {
        let fold = Fold {
            index: 0,
            is_start_ms: 0,
            is_end_ms: 10 * MS_PER_MINUTE,
            oos_start_ms: 10 * MS_PER_MINUTE,
            oos_end_ms: 20 * MS_PER_MINUTE,
        };
        let trades = vec![
            test_trade("BTCUSDT", 9 * MS_PER_MINUTE, 1.0),
            test_trade("BTCUSDT", 10 * MS_PER_MINUTE, 2.0),
            test_trade("BTCUSDT", 19 * MS_PER_MINUTE, 3.0),
        ];

        let oos_trades = oos_trades_for_fold(&trades, &fold);
        let window_trades = trades_for_window(&trades, fold.oos_start_ms, fold.oos_end_ms);

        assert_eq!(oos_trades.len(), 1);
        assert_eq!(oos_trades[0].entry_time_ms, 10 * MS_PER_MINUTE);
        assert_eq!(window_trades.len(), 1);
        assert_eq!(window_trades[0].entry_time_ms, 10 * MS_PER_MINUTE);
    }

    #[test]
    fn strategy_4448_space_scan_grid_covers_current_extents() {
        let candidates = strategy_4448_space_scan_candidates(5_120);

        assert_eq!(candidates.len(), 5_120);
        let unique = candidates
            .iter()
            .map(|candidate| {
                format!(
                    "{}:{}:{:.2}:{:.2}:{}:{}:{}:{}:{}:{}:{}",
                    candidate.lookback,
                    candidate.atr_period,
                    candidate.stop_atr_multiple,
                    candidate.target_atr_multiple,
                    candidate.strategy_4448_kama1_er,
                    candidate.strategy_4448_kama1_short,
                    candidate.strategy_4448_kama1_long,
                    candidate.strategy_4448_kama2_er,
                    candidate.strategy_4448_kama2_short,
                    candidate.strategy_4448_kama2_long,
                    candidate.strategy_4448_count_bars
                )
            })
            .collect::<std::collections::BTreeSet<_>>();
        assert_eq!(unique.len(), candidates.len());
        assert!(candidates.iter().any(|candidate| candidate.lookback == 5));
        assert!(candidates.iter().any(|candidate| candidate.lookback == 720));
        assert!(candidates.iter().any(|candidate| candidate.atr_period == 5));
        assert!(
            candidates
                .iter()
                .any(|candidate| candidate.atr_period == 720)
        );
        assert!(
            candidates
                .iter()
                .any(|candidate| candidate.stop_atr_multiple == 0.5)
        );
        assert!(
            candidates
                .iter()
                .any(|candidate| candidate.stop_atr_multiple == 8.0)
        );
        assert!(
            candidates
                .iter()
                .any(|candidate| candidate.target_atr_multiple == 1.0)
        );
        assert!(
            candidates
                .iter()
                .any(|candidate| candidate.target_atr_multiple == 12.0)
        );
        assert!(
            candidates
                .iter()
                .any(|candidate| candidate.strategy_4448_count_bars == 3)
        );
        assert!(
            candidates
                .iter()
                .any(|candidate| candidate.strategy_4448_count_bars == 30)
        );
        assert!(candidates.iter().all(|candidate| candidate.indicator
            == IndicatorKind::Strategy4448KamaKer
            && candidate.timeframe == Timeframe::M5
            && candidate.time_stop_bars == Some(28)
            && candidate.entry_atr_multiple == 0.0));
    }

    #[test]
    fn strategy_4448_space_scan_fold_zero_matches_offset_zero_baseline() {
        let start = date_ms(NaiveDate::from_ymd_opt(2025, 1, 1).unwrap()).unwrap();
        let end = date_ms(NaiveDate::from_ymd_opt(2026, 1, 1).unwrap()).unwrap();
        let folds = generate_folds_days(start, end, 14, 7, 7, 0);
        let fold = folds[0];

        assert_eq!(fold.is_start_ms, start);
        assert_eq!(
            fold.is_end_ms - fold.is_start_ms,
            Duration::days(14).num_milliseconds()
        );
        assert_eq!(fold.oos_start_ms, fold.is_end_ms);
        assert_eq!(
            fold.oos_end_ms - fold.oos_start_ms,
            Duration::days(7).num_milliseconds()
        );
    }

    #[test]
    fn negative_score_is_not_rescued_by_trade_activity() {
        let quiet = score_candidate(CandidateScoreInput {
            net_return_pct: -2.0,
            trades: 10,
            trade_band: (2, 100),
            average_trade_return_pct: -0.2,
            ..score_input()
        });
        let active = score_candidate(CandidateScoreInput {
            net_return_pct: -2.0,
            trades: 90,
            trade_band: (2, 100),
            average_trade_return_pct: -0.02,
            ..score_input()
        });

        assert!(quiet < 0.0);
        assert!(active < 0.0);
        assert!(quiet > INELIGIBLE_SCORE_CUTOFF);
        assert!(active > INELIGIBLE_SCORE_CUTOFF);
    }

    #[test]
    fn candidate_acceptance_requires_five_hundred_oos_trades() {
        assert!(!candidate_acceptance(
            &candidate_metrics(42.0, 1.4, MIN_CANDIDATE_OOS_TRADES - 1),
            &[],
            1.2
        ));
        assert!(!candidate_acceptance(
            &candidate_metrics(-1.0, 1.4, MIN_CANDIDATE_OOS_TRADES),
            &[],
            1.2
        ));
        assert!(!candidate_acceptance(
            &candidate_metrics(42.0, 1.1, MIN_CANDIDATE_OOS_TRADES),
            &[],
            1.2
        ));
        assert!(candidate_acceptance(
            &candidate_metrics(42.0, 1.4, MIN_CANDIDATE_OOS_TRADES),
            &[],
            1.2
        ));
    }

    #[test]
    fn daily_offset_ensemble_gate_accepts_stacked_portfolio_metrics() {
        let (status, reason) = daily_offset_ensemble_gate(
            TPE_IS_CONSENSUS_OFFSET_DAYS,
            147_936.29,
            1.34,
            80_466,
            5,
            1.10,
        );

        assert_eq!(status, "pass");
        assert!(reason.contains("positive stacked OOS PnL"));

        let (status, reason) = daily_offset_ensemble_gate(
            TPE_IS_CONSENSUS_OFFSET_DAYS,
            147_936.29,
            1.34,
            80_466,
            MAX_CANDIDATE_NO_ENTRY_GAP_DAYS + 1,
            1.10,
        );

        assert_eq!(status, "fail");
        assert!(reason.contains("stacked max no-entry gap"));
    }

    #[test]
    fn strategy_candidate_gate_reports_low_oos_trade_count() {
        let metrics = candidate_metrics(42.0, 1.4, 62);
        let gate = strategy_candidate_gate(Some(&metrics), &[], 1.2);

        assert!(!gate.pass_candidate);
        assert!(!gate.pass_min_trades);
        assert_eq!(gate.min_oos_trades, MIN_CANDIDATE_OOS_TRADES);
        assert!(gate.reason.contains("62 OOS trades < 500 minimum"));
    }

    #[test]
    fn strategy_candidate_gate_rejects_clustered_oos_participation() {
        let mut metrics = candidate_metrics(73.98, 1.239, 1182);
        metrics.total_oos_days = 350;
        metrics.entry_days = 107;
        metrics.no_entry_days = 243;
        metrics.entry_day_pct = 30.57;
        metrics.total_oos_weeks = 50;
        metrics.entry_weeks = 17;
        metrics.no_entry_weeks = 33;
        metrics.entry_week_pct = 34.0;
        metrics.longest_no_entry_gap_days = 83;

        let mut btc_metrics = candidate_metrics(8.31, 1.298, 175);
        btc_metrics.total_oos_days = 350;
        btc_metrics.entry_days = 23;
        btc_metrics.no_entry_days = 327;
        btc_metrics.entry_day_pct = 6.57;
        btc_metrics.total_oos_weeks = 50;
        btc_metrics.entry_weeks = 5;
        btc_metrics.no_entry_weeks = 45;
        btc_metrics.entry_week_pct = 10.0;
        btc_metrics.longest_no_entry_gap_days = 167;
        let symbols = vec![StrategyOosSymbolResult {
            symbol: "BTCUSDT".to_string(),
            metrics: btc_metrics,
        }];

        let gate = strategy_candidate_gate(Some(&metrics), &symbols, 1.2);

        assert!(!gate.pass_candidate);
        assert!(gate.pass_min_trades);
        assert!(gate.pass_net_positive);
        assert!(gate.pass_profit_factor);
        assert!(gate.pass_entry_days);
        assert!(!gate.pass_entry_weeks);
        assert!(!gate.pass_no_entry_gap);
        assert!(!gate.pass_symbol_participation);
        assert!(
            gate.reason
                .contains("portfolio active weeks 34.00% < 100.00%")
        );
        assert!(gate.reason.contains("BTCUSDT entry_days 6.57%"));
    }

    #[test]
    fn strategy_candidate_gate_can_be_looser_than_is_profit_factor_filter() {
        let metrics = candidate_metrics(56.85, 1.224, MIN_CANDIDATE_OOS_TRADES);
        let candidate_gate = strategy_candidate_gate(Some(&metrics), &[], 1.2);
        let strict_is_gate = strategy_candidate_gate(Some(&metrics), &[], 1.5);

        assert!(candidate_gate.pass_candidate);
        assert!(!strict_is_gate.pass_candidate);
        assert!(!strict_is_gate.pass_profit_factor);
    }

    #[test]
    fn sparse_and_overactive_candidates_are_ineligible() {
        let sparse = score_candidate(CandidateScoreInput {
            net_return_pct: 20.0,
            max_drawdown_pct: 0.0,
            trades: 1,
            average_trade_return_pct: 20.0,
            ..score_input()
        });
        let ok = score_candidate(score_input());
        let overactive = score_candidate(CandidateScoreInput {
            net_return_pct: 20.0,
            max_drawdown_pct: 0.0,
            trades: 200,
            average_trade_return_pct: 0.1,
            ..score_input()
        });

        assert!(sparse < ok);
        assert!(overactive < ok);
        assert!(sparse > INELIGIBLE_SCORE_CUTOFF);
        assert!(overactive > INELIGIBLE_SCORE_CUTOFF);
        assert!(ok > 0.0);
    }

    #[test]
    fn low_profit_factor_candidates_are_ineligible() {
        let low_pf = score_candidate(CandidateScoreInput {
            net_return_pct: 20.0,
            max_drawdown_pct: 2.0,
            profit_factor: 1.19,
            average_trade_return_pct: 1.67,
            ..score_input()
        });
        let ok_pf = score_candidate(CandidateScoreInput {
            net_return_pct: 20.0,
            max_drawdown_pct: 2.0,
            profit_factor: 1.2,
            average_trade_return_pct: 1.67,
            ..score_input()
        });

        assert!(low_pf < ok_pf);
        assert!(ok_pf > 0.0);
    }

    #[test]
    fn low_fill_rate_candidates_are_ineligible_when_attempts_are_material() {
        let low_fill = score_candidate(CandidateScoreInput {
            net_return_pct: 20.0,
            max_drawdown_pct: 2.0,
            profit_factor: 1.6,
            trades: 40,
            trade_band: (12, 252),
            average_trade_return_pct: 0.5,
            entry_attempts: 300,
            fill_rate_pct: 1.0,
            ..score_input()
        });
        let healthy_fill = score_candidate(CandidateScoreInput {
            net_return_pct: 20.0,
            max_drawdown_pct: 2.0,
            profit_factor: 1.6,
            trades: 40,
            trade_band: (12, 252),
            average_trade_return_pct: 0.5,
            entry_attempts: 300,
            fill_rate_pct: 6.0,
            ..score_input()
        });

        assert!(low_fill < healthy_fill);
        assert!(healthy_fill > 0.0);
    }

    #[test]
    fn soft_failed_scores_remain_ranked_but_not_selectable() {
        let low_pf_score = score_candidate(CandidateScoreInput {
            net_return_pct: 20.0,
            max_drawdown_pct: 2.0,
            profit_factor: 1.0,
            average_trade_return_pct: 1.67,
            ..score_input()
        });
        assert!(low_pf_score > INELIGIBLE_SCORE_CUTOFF);

        let mut low_pf = candidate_score(low_pf_score);
        low_pf.quality_fit = "low_profit_factor".to_string();
        assert!(!candidate_score_is_selectable(
            &low_pf,
            MIN_SELECTABLE_SCORE
        ));

        let mut low_fill = candidate_score(12.0);
        low_fill.entry_attempts = 300;
        low_fill.fill_rate_pct = 1.0;
        assert!(!candidate_score_is_selectable(
            &low_fill,
            MIN_SELECTABLE_SCORE
        ));

        let mut low_participation = candidate_score(12.0);
        low_participation.entry_day_pct = 10.0;
        assert!(!candidate_score_is_selectable(
            &low_participation,
            MIN_SELECTABLE_SCORE
        ));
    }

    #[test]
    fn pathological_exit_geometry_is_never_selectable() {
        let config = WfoConfig::new(GridSize::Tpe);
        let window_start = date_ms(NaiveDate::from_ymd_opt(2025, 1, 1).unwrap()).unwrap();
        let window_end = window_start + Duration::weeks(2).num_milliseconds();
        let trade_values = (0..108)
            .map(|index| {
                test_trade(
                    "BNBUSDT",
                    window_start + index as i64 * 3 * 60 * MS_PER_MINUTE,
                    1.0,
                )
            })
            .collect::<Vec<_>>();
        let trade_refs = trade_values.iter().collect::<Vec<_>>();
        let valid_candidate = Candidate {
            id: 1,
            indicator: IndicatorKind::Frama,
            timeframe: Timeframe::M5,
            stop_atr_multiple: 1.5,
            target_atr_multiple: 3.0,
            ..Candidate::default()
        };
        let invalid_candidate = Candidate {
            stop_atr_multiple: 0.2,
            target_atr_multiple: 28.0,
            ..valid_candidate.clone()
        };

        let valid_score = score_trades_in_window(
            "BNBUSDT",
            &valid_candidate,
            0,
            &trade_refs,
            &config,
            window_start,
            window_end,
        );
        let invalid_score = score_trades_in_window(
            "BNBUSDT",
            &invalid_candidate,
            0,
            &trade_refs,
            &config,
            window_start,
            window_end,
        );

        assert!(valid_score.score > MIN_SELECTABLE_SCORE);
        assert_eq!(valid_score.quality_fit, "ok");
        assert!(invalid_score.score <= INELIGIBLE_SCORE_CUTOFF);
        assert_eq!(invalid_score.quality_fit, BAD_EXIT_GEOMETRY_REJECTION);
    }

    #[test]
    fn score_prefers_higher_profit_factor_after_minimum_is_met() {
        let barely_valid = score_candidate(CandidateScoreInput {
            profit_factor: 1.21,
            ..score_input()
        });
        let stronger_pf = score_candidate(CandidateScoreInput {
            profit_factor: 1.8,
            ..score_input()
        });

        assert!(stronger_pf > barely_valid + 0.4);
    }

    #[test]
    fn score_penalizes_drawdown_larger_than_return() {
        let shallow_drawdown = score_candidate(CandidateScoreInput {
            net_return_pct: 8.0,
            max_drawdown_pct: 2.0,
            profit_factor: 1.6,
            ..score_input()
        });
        let deep_drawdown = score_candidate(CandidateScoreInput {
            net_return_pct: 8.0,
            max_drawdown_pct: 16.0,
            profit_factor: 1.6,
            ..score_input()
        });

        assert!(shallow_drawdown > deep_drawdown + 3.0);
    }

    #[test]
    fn fee_buffer_requires_enough_average_trade_edge() {
        let low_edge = score_candidate(CandidateScoreInput {
            net_return_pct: 4.0,
            max_drawdown_pct: 2.0,
            profit_factor: 1.4,
            trades: 100,
            trade_band: (50, 200),
            average_trade_return_pct: 0.03,
            min_average_trade_return_pct: 0.04,
            ..score_input()
        });
        let enough_edge = score_candidate(CandidateScoreInput {
            net_return_pct: 4.0,
            max_drawdown_pct: 2.0,
            profit_factor: 1.4,
            trades: 100,
            trade_band: (50, 200),
            average_trade_return_pct: 0.08,
            min_average_trade_return_pct: 0.04,
            ..score_input()
        });

        assert!(low_edge < enough_edge);
        assert!(enough_edge > 0.0);
    }

    #[test]
    fn weak_average_trade_confidence_is_ineligible() {
        let noisy_edge = score_candidate(CandidateScoreInput {
            net_return_pct: 5.0,
            max_drawdown_pct: 2.0,
            profit_factor: 1.5,
            trades: 100,
            trade_band: (50, 200),
            average_trade_return_pct: 0.05,
            trade_return_stddev_pct: 1.0,
            min_edge_t_stat: 1.0,
            ..score_input()
        });
        let confident_edge = score_candidate(CandidateScoreInput {
            net_return_pct: 20.0,
            max_drawdown_pct: 2.0,
            profit_factor: 1.5,
            trades: 100,
            trade_band: (50, 200),
            average_trade_return_pct: 0.20,
            trade_return_stddev_pct: 1.0,
            min_edge_t_stat: 1.0,
            ..score_input()
        });

        assert!(noisy_edge < confident_edge);
        assert!(confident_edge > 0.0);
    }

    #[test]
    fn min_average_trade_edge_requires_fee_buffer() {
        assert_eq!(min_average_trade_return_pct(0.0), 0.0);
        assert_eq!(min_average_trade_return_pct(2.0), 0.08);
    }

    #[test]
    fn combo_component_spec_parses_run_indicator_and_timeframe() {
        let spec = parse_combo_component_spec("20260623T192152Z-tpe:trendflex:5m").unwrap();

        assert_eq!(spec.run_id, "20260623T192152Z-tpe");
        assert_eq!(spec.indicator, IndicatorKind::TrendFlex);
        assert_eq!(spec.timeframe, Timeframe::M5);
        assert!(parse_combo_component_spec("bad-spec").is_err());
    }

    #[test]
    fn pearson_correlation_reports_positive_and_negative_relationships() {
        let positive = pearson_correlation(&[1.0, 2.0, 3.0], &[2.0, 4.0, 6.0]).unwrap();
        let negative = pearson_correlation(&[1.0, 2.0, 3.0], &[6.0, 4.0, 2.0]).unwrap();

        assert!((positive - 1.0).abs() < 1e-9);
        assert!((negative + 1.0).abs() < 1e-9);
    }

    #[test]
    fn tpe_objective_uses_validation_with_training_stability_penalty() {
        let validation = vec![candidate_score(7.0), candidate_score(6.0)];
        let stable_training = vec![candidate_score(2.0), candidate_score(2.5)];
        let failed_training = vec![candidate_score(-1_350.0), candidate_score(-1_300.0)];

        let stable = tpe_objective_score(&stable_training, &validation);
        let unstable = tpe_objective_score(&failed_training, &validation);

        assert!(stable > unstable);
        assert!(stable > mean_score(&validation));
        assert!(unstable > INELIGIBLE_SCORE_CUTOFF);
    }

    #[test]
    fn tpe_objective_prefers_consistent_validation_over_spiky_validation() {
        let training = vec![
            candidate_score(2.0),
            candidate_score(2.0),
            candidate_score(2.0),
            candidate_score(2.0),
        ];
        let consistent_validation = vec![
            candidate_score(7.0),
            candidate_score(7.0),
            candidate_score(7.0),
            candidate_score(7.0),
        ];
        let spiky_validation = vec![
            candidate_score(30.0),
            candidate_score(30.0),
            candidate_score(-1_200.0),
            candidate_score(-1_200.0),
        ];

        let consistent = tpe_objective_score(&training, &consistent_validation);
        let spiky = tpe_objective_score(&training, &spiky_validation);

        assert!(consistent > spiky);
    }

    #[test]
    fn tpe_objective_prefers_paired_train_selection_wins() {
        let paired_training = vec![
            candidate_score(7.0),
            candidate_score(7.0),
            candidate_score(-1_200.0),
            candidate_score(-1_200.0),
        ];
        let paired_validation = vec![
            candidate_score(7.0),
            candidate_score(7.0),
            candidate_score(-1_200.0),
            candidate_score(-1_200.0),
        ];
        let validation_only_training = vec![
            candidate_score(-1_200.0),
            candidate_score(-1_200.0),
            candidate_score(7.0),
            candidate_score(7.0),
        ];
        let validation_only = vec![
            candidate_score(30.0),
            candidate_score(30.0),
            candidate_score(-1_200.0),
            candidate_score(-1_200.0),
        ];

        let paired = tpe_objective_score(&paired_training, &paired_validation);
        let validation_spike = tpe_objective_score(&validation_only_training, &validation_only);

        assert!(paired > validation_spike);
    }

    #[test]
    fn tpe_objective_ranks_candidates_without_paired_selection_wins() {
        let poor_training = vec![candidate_score(-20.0), candidate_score(-18.0)];
        let poor_validation = vec![candidate_score(-16.0), candidate_score(-15.0)];
        let better_training = vec![candidate_score(-10.0), candidate_score(-9.0)];
        let better_validation = vec![candidate_score(-8.0), candidate_score(-7.0)];

        let poor = tpe_objective_breakdown(&poor_training, &poor_validation);
        let better = tpe_objective_breakdown(&better_training, &better_validation);

        assert_eq!(poor.paired_selection_count, 0);
        assert_eq!(better.paired_selection_count, 0);
        assert!(poor.objective_score > INELIGIBLE_SCORE_CUTOFF);
        assert!(better.objective_score > poor.objective_score);
    }

    #[test]
    fn tpe_fold_selection_rank_requires_training_and_selection() {
        let tpe_config = WfoConfig::new(GridSize::Tpe);
        let wide_config = WfoConfig::new(GridSize::Wide);
        let training_fail = candidate_score(-1_200.0);
        let selection_weak = candidate_score(4.0);
        let selection_pass = candidate_score(7.0);
        let training_pass = candidate_score(2.0);

        assert_eq!(
            fold_selection_rank_score(&tpe_config, &training_fail, &selection_pass),
            None
        );
        assert_eq!(
            fold_selection_rank_score(&tpe_config, &training_pass, &selection_weak),
            None
        );
        assert!(fold_selection_rank_score(&tpe_config, &training_pass, &selection_pass).is_some());
        assert_eq!(
            fold_selection_rank_score(&wide_config, &training_fail, &selection_weak),
            Some(selection_weak.score)
        );
    }

    #[test]
    fn non_selectable_fold_does_not_create_primary_oos_selection() {
        let rejected = FoldSelectionEvaluation {
            rank_score: None,
            objective_score: candidate_score(5.0),
        };
        let selected = strict_fold_selection(
            &rejected,
            IndicatorKind::Frama,
            vec![test_trade("BTCUSDT", 1, 10.0)],
        );

        assert!(selected.is_none());
    }

    #[test]
    fn tpe_candidate_breadth_adjusts_fold_rank_without_hard_rejection() {
        let config = WfoConfig::new(GridSize::Tpe);
        let candidate = Candidate::default();
        let broad_training = vec![
            candidate_score(7.0),
            candidate_score(7.0),
            candidate_score(-1_200.0),
            candidate_score(-1_200.0),
        ];
        let broad_validation = broad_training.clone();
        let narrow_training = vec![
            candidate_score(7.0),
            candidate_score(-1_200.0),
            candidate_score(-1_200.0),
            candidate_score(-1_200.0),
        ];
        let narrow_validation = narrow_training.clone();

        let broad = tpe_objective_breakdown(&broad_training, &broad_validation);
        let narrow = tpe_objective_breakdown(&narrow_training, &narrow_validation);
        let broad_adjustment = tpe_candidate_rank_adjustment(&config, &candidate, &broad);
        let narrow_adjustment = tpe_candidate_rank_adjustment(&config, &candidate, &narrow);

        assert!(broad_adjustment > narrow_adjustment);
        assert!(broad_adjustment > 0.0);
        assert!(broad.objective_score > narrow.objective_score);
        assert!(broad.paired_selection_fraction > narrow.paired_selection_fraction);
        assert!(broad.paired_selection_count >= 2);
        assert!(narrow.paired_selection_count < 2);

        let selected = FoldSelection {
            score: candidate_score(7.0),
            rank_score: 7.0,
            indicator: IndicatorKind::Frama,
            trades: Vec::new(),
        };
        let adjusted = adjusted_fold_selection(selected, narrow_adjustment);

        assert!(adjusted.rank_score.is_finite());
    }

    #[test]
    fn tpe_candidate_objective_regularizes_fold_rank() {
        let config = WfoConfig::new(GridSize::Tpe);
        let candidate = Candidate::default();
        let weak_objective = tpe_objective_breakdown(
            &[
                candidate_score(7.0),
                candidate_score(7.0),
                candidate_score(-1_200.0),
                candidate_score(-1_200.0),
            ],
            &[
                candidate_score(7.0),
                candidate_score(7.0),
                candidate_score(-1_200.0),
                candidate_score(-1_200.0),
            ],
        );
        let strong_objective = tpe_objective_breakdown(
            &[
                candidate_score(7.0),
                candidate_score(7.0),
                candidate_score(7.0),
                candidate_score(7.0),
            ],
            &[
                candidate_score(7.0),
                candidate_score(7.0),
                candidate_score(7.0),
                candidate_score(7.0),
            ],
        );

        let weak_adjustment = tpe_candidate_rank_adjustment(&config, &candidate, &weak_objective);
        let strong_adjustment =
            tpe_candidate_rank_adjustment(&config, &candidate, &strong_objective);

        assert!(strong_adjustment > weak_adjustment + 10.0);
        assert_eq!(strong_objective.paired_selection_count, 4);
    }

    #[test]
    fn optuna_constraints_are_neutral_for_diagnostic_feasibility_metrics() {
        let training = vec![candidate_score(2.0), candidate_score(-1_200.0)];
        let validation = vec![
            candidate_score(2.0),
            candidate_score(-1_200.0),
            candidate_score(-1_200.0),
        ];
        let objective = tpe_objective_breakdown(&training, &validation);
        let constraints = optuna_constraints(&objective, DEFAULT_MIN_PROFIT_FACTOR);

        assert_eq!(constraints, vec![0.0]);
    }

    #[test]
    fn trade_count_band_allows_one_trade_per_eight_signal_bars() {
        let start = date_ms(NaiveDate::from_ymd_opt(2025, 1, 1).unwrap()).unwrap();
        let fold = generate_folds(
            start,
            start + Duration::weeks(6).num_milliseconds(),
            4,
            1,
            1,
            0,
        )
        .remove(0);

        assert_eq!(trade_count_band(Timeframe::M5, &fold), (45, 1008));
        assert_eq!(trade_count_band(Timeframe::H1, &fold), (5, 84));
    }

    #[test]
    fn tpe_selection_window_uses_trailing_half_of_is_and_training_uses_leading_half() {
        let start = date_ms(NaiveDate::from_ymd_opt(2025, 1, 1).unwrap()).unwrap();
        let fold = generate_folds(
            start,
            start + Duration::weeks(4).num_milliseconds(),
            2,
            1,
            1,
            0,
        )
        .remove(0);
        let tpe_config = WfoConfig::new(GridSize::Tpe);
        let (selection_start_ms, selection_end_ms) = selection_window(&tpe_config, &fold);
        let (training_start_ms, training_end_ms) = training_window(&tpe_config, &fold);

        assert_eq!(selection_end_ms, fold.is_end_ms);
        assert_eq!(
            selection_start_ms,
            fold.is_start_ms + Duration::weeks(1).num_milliseconds()
        );
        assert_eq!(training_start_ms, fold.is_start_ms);
        assert_eq!(training_end_ms, selection_start_ms);
        assert_eq!(
            trade_count_band_for_window(Timeframe::M5, selection_start_ms, selection_end_ms),
            (12, 252)
        );

        let wide_config = WfoConfig::new(GridSize::Wide);
        assert_eq!(
            selection_window(&wide_config, &fold),
            (fold.is_start_ms, fold.is_end_ms)
        );
    }

    #[test]
    fn tpe_fold_selection_requires_five_of_seven_past_daily_offset_is_windows() {
        let config = WfoConfig::new(GridSize::Tpe);
        let start = date_ms(NaiveDate::from_ymd_opt(2025, 1, 1).unwrap()).unwrap();
        let fold = generate_folds(
            start,
            start + Duration::weeks(8).num_milliseconds(),
            2,
            1,
            1,
            0,
        )
        .remove(1);
        let candidate = Candidate {
            id: 1,
            indicator: IndicatorKind::Strategy4448KamaKer,
            timeframe: Timeframe::M5,
            signal_polarity: 1,
            entry_mode: EntryMode::Pullback,
            lookback: 20,
            atr_period: 20,
            stop_atr_multiple: 2.0,
            target_atr_multiple: 4.0,
            time_stop_bars: Some(28),
            ..Candidate::default()
        };
        let jan2 = date_ms(NaiveDate::from_ymd_opt(2025, 1, 2).unwrap()).unwrap();
        let jan3 = date_ms(NaiveDate::from_ymd_opt(2025, 1, 3).unwrap()).unwrap();
        let jan4 = date_ms(NaiveDate::from_ymd_opt(2025, 1, 4).unwrap()).unwrap();
        let mut trades = (0..21 * 4)
            .map(|index| test_trade("BTCUSDT", jan2 + index * 6 * MS_PER_MINUTE * 60, 2.0))
            .collect::<Vec<_>>();
        let training_trades = training_trades_for_fold(&trades, &config, &fold);
        let selection_trades = selection_trades_for_fold(&trades, &config, &fold);
        let (training_start_ms, training_end_ms) = training_window(&config, &fold);
        let training_score = score_trades_in_window(
            "BTCUSDT",
            &candidate,
            fold.index,
            &training_trades,
            &config,
            training_start_ms,
            training_end_ms,
        );
        let selection_score = score_trades_with_diagnostics(
            "BTCUSDT",
            &candidate,
            fold.index,
            &fold,
            &selection_trades,
            &config,
            &CandidateSignalFillFoldDiagnostics::default(),
        );
        assert!(
            fold_selection_rank_score(&config, &training_score, &selection_score).is_some(),
            "baseline split must pass before consensus can be tested"
        );
        let stable = fold_selection_evaluation(
            &config,
            "BTCUSDT",
            &candidate,
            &fold,
            &trades,
            &training_score,
            &selection_score,
        );
        assert!(stable.rank_score.is_some());

        for index in 0..6 {
            trades.push(test_trade(
                "BTCUSDT",
                jan3 + index * 4 * MS_PER_MINUTE * 60,
                -50.0,
            ));
        }
        let two_failed_training_trades = training_trades_for_fold(&trades, &config, &fold);
        let two_failed_selection_trades = selection_trades_for_fold(&trades, &config, &fold);
        let two_failed_training_score = score_trades_in_window(
            "BTCUSDT",
            &candidate,
            fold.index,
            &two_failed_training_trades,
            &config,
            training_start_ms,
            training_end_ms,
        );
        let two_failed_selection_score = score_trades_with_diagnostics(
            "BTCUSDT",
            &candidate,
            fold.index,
            &fold,
            &two_failed_selection_trades,
            &config,
            &CandidateSignalFillFoldDiagnostics::default(),
        );
        assert!(
            fold_selection_rank_score(
                &config,
                &two_failed_training_score,
                &two_failed_selection_score
            )
            .is_some(),
            "the ordinary split still passes because the loss cluster is before it"
        );
        let two_failed_offsets = fold_selection_evaluation(
            &config,
            "BTCUSDT",
            &candidate,
            &fold,
            &trades,
            &two_failed_training_score,
            &two_failed_selection_score,
        );
        assert!(
            two_failed_offsets.rank_score.is_some(),
            "two weak daily offset windows should not veto selection"
        );

        for index in 0..6 {
            trades.push(test_trade(
                "BTCUSDT",
                jan4 + index * 4 * MS_PER_MINUTE * 60,
                -50.0,
            ));
        }
        let three_failed_training_trades = training_trades_for_fold(&trades, &config, &fold);
        let three_failed_selection_trades = selection_trades_for_fold(&trades, &config, &fold);
        let three_failed_training_score = score_trades_in_window(
            "BTCUSDT",
            &candidate,
            fold.index,
            &three_failed_training_trades,
            &config,
            training_start_ms,
            training_end_ms,
        );
        let three_failed_selection_score = score_trades_with_diagnostics(
            "BTCUSDT",
            &candidate,
            fold.index,
            &fold,
            &three_failed_selection_trades,
            &config,
            &CandidateSignalFillFoldDiagnostics::default(),
        );
        let three_failed_offsets = fold_selection_evaluation(
            &config,
            "BTCUSDT",
            &candidate,
            &fold,
            &trades,
            &three_failed_training_score,
            &three_failed_selection_score,
        );
        assert_eq!(three_failed_offsets.rank_score, None);
    }

    #[test]
    fn tpe_minute_params_are_capped_in_signal_bars() {
        assert_eq!(
            minutes_to_timeframe_bars_capped(
                4_320,
                Timeframe::M1,
                TPE_MIN_LOOKBACK_BARS,
                TPE_MAX_LOOKBACK_BARS
            ),
            TPE_MAX_LOOKBACK_BARS
        );
        assert_eq!(
            minutes_to_timeframe_bars_capped(
                10_080,
                Timeframe::H1,
                TPE_MIN_LOOKBACK_BARS,
                TPE_MAX_LOOKBACK_BARS
            ),
            168
        );
    }

    #[test]
    fn generic_tpe_search_space_uses_signal_bar_bounds() {
        let template = Candidate {
            id: 22,
            indicator: IndicatorKind::Frama,
            timeframe: Timeframe::M5,
            ..Candidate::default()
        };
        let search_space = TpeSearchSpace::new();
        let study: Study<f64> = Study::new(Direction::Maximize);

        for _ in 0..24 {
            let mut trial = study.ask();
            let candidate = search_space.suggest(&mut trial, &template).unwrap();
            assert!((TPE_MIN_LOOKBACK_BARS..=TPE_MAX_LOOKBACK_BARS).contains(&candidate.lookback));
            assert!((TPE_MIN_ATR_BARS..=TPE_MAX_ATR_BARS).contains(&candidate.atr_period));
            assert_eq!(candidate.atr_period % TPE_ATR_STEP_BARS, 0);
            assert!((0.0..=TPE_MAX_ENTRY_ATR_MULTIPLE).contains(&candidate.entry_atr_multiple));
            assert!(
                (MIN_EXIT_STOP_ATR_MULTIPLE..=MAX_EXIT_STOP_ATR_MULTIPLE)
                    .contains(&candidate.stop_atr_multiple)
            );
            assert!(
                (TPE_MIN_TARGET_ATR_MULTIPLE..=MAX_EXIT_TARGET_ATR_MULTIPLE)
                    .contains(&candidate.target_atr_multiple)
            );
            assert!(
                candidate.target_atr_multiple
                    <= candidate.stop_atr_multiple * MAX_EXIT_TARGET_STOP_RATIO
            );
            if let Some(time_stop_bars) = candidate.time_stop_bars {
                assert!((1..=TPE_MAX_TIME_STOP_BARS).contains(&time_stop_bars));
            }
            study.tell(trial, Ok::<f64, &'static str>(0.0));
        }
    }

    #[test]
    fn ehlers_indicator_group_filters_wide_grid() {
        let candidates = candidate_grid_for_group(GridSize::Wide, Some("ehlers")).unwrap();

        assert_eq!(candidates.len(), 1_296);
        assert!(
            candidates
                .iter()
                .all(|candidate| EHLERS_INDICATORS.contains(&candidate.indicator))
        );
    }

    #[test]
    fn suspicious_shortlist_filters_wide_grid_to_requested_strategy_timeframes() {
        let candidates =
            candidate_grid_for_filters(GridSize::Wide, None, Some(SUSPICIOUS_SHORTLIST_SET))
                .unwrap();
        let mut strategy_keys = Vec::new();
        for candidate in &candidates {
            let key = (candidate.indicator, candidate.timeframe);
            if !strategy_keys.contains(&key) {
                strategy_keys.push(key);
            }
        }

        assert_eq!(candidates.len(), 17 * 36);
        assert_eq!(strategy_keys.len(), 17);
        assert!(
            SUSPICIOUS_SHORTLIST
                .iter()
                .all(|key| strategy_keys.contains(key))
        );
    }

    #[test]
    fn calibration_audit_filters_to_diagnosed_strategy_timeframes() {
        let candidates =
            candidate_grid_for_filters(GridSize::Tpe, None, Some(CALIBRATION_AUDIT_SET)).unwrap();
        let mut strategy_keys = Vec::new();
        for candidate in &candidates {
            let key = (candidate.indicator, candidate.timeframe);
            if !strategy_keys.contains(&key) {
                strategy_keys.push(key);
            }
        }

        assert_eq!(
            candidates.len(),
            CALIBRATION_AUDIT.len() * DEFAULT_TPE_TRIALS
        );
        assert_eq!(strategy_keys.len(), CALIBRATION_AUDIT.len());
        assert!(
            CALIBRATION_AUDIT
                .iter()
                .all(|key| strategy_keys.contains(key))
        );
    }

    #[test]
    fn portfolio_candidates_filters_to_non_one_minute_combo_candidates() {
        let candidates =
            candidate_grid_for_filters(GridSize::Tpe, None, Some(PORTFOLIO_CANDIDATES_SET))
                .unwrap();
        let mut strategy_keys = Vec::new();
        for candidate in &candidates {
            let key = (candidate.indicator, candidate.timeframe);
            if !strategy_keys.contains(&key) {
                strategy_keys.push(key);
            }
        }

        assert_eq!(
            candidates.len(),
            PORTFOLIO_CANDIDATES.len() * DEFAULT_TPE_TRIALS
        );
        assert_eq!(strategy_keys.len(), PORTFOLIO_CANDIDATES.len());
        assert!(
            PORTFOLIO_CANDIDATES
                .iter()
                .all(|key| strategy_keys.contains(key))
        );
        assert!(
            candidates
                .iter()
                .all(|candidate| candidate.timeframe != Timeframe::M1)
        );
    }

    #[test]
    fn low_turnover_extra_filters_to_fee_relevant_non_one_minute_candidates() {
        let candidates =
            candidate_grid_for_filters(GridSize::Tpe, None, Some(LOW_TURNOVER_EXTRA_SET)).unwrap();
        let mut strategy_keys = Vec::new();
        for candidate in &candidates {
            let key = (candidate.indicator, candidate.timeframe);
            if !strategy_keys.contains(&key) {
                strategy_keys.push(key);
            }
        }

        assert_eq!(
            candidates.len(),
            LOW_TURNOVER_EXTRA.len() * DEFAULT_TPE_TRIALS
        );
        assert_eq!(strategy_keys.len(), LOW_TURNOVER_EXTRA.len());
        assert!(
            LOW_TURNOVER_EXTRA
                .iter()
                .all(|key| strategy_keys.contains(key))
        );
        assert!(
            candidates
                .iter()
                .all(|candidate| candidate.timeframe != Timeframe::M1)
        );
    }

    #[test]
    fn second_pass_portfolio_filters_to_focused_survivor_candidates() {
        let candidates =
            candidate_grid_for_filters(GridSize::Tpe, None, Some(SECOND_PASS_PORTFOLIO_SET))
                .unwrap();
        let mut strategy_keys = Vec::new();
        for candidate in &candidates {
            let key = (candidate.indicator, candidate.timeframe);
            if !strategy_keys.contains(&key) {
                strategy_keys.push(key);
            }
        }

        assert_eq!(
            candidates.len(),
            SECOND_PASS_PORTFOLIO.len() * DEFAULT_TPE_TRIALS
        );
        assert_eq!(strategy_keys.len(), SECOND_PASS_PORTFOLIO.len());
        assert!(
            SECOND_PASS_PORTFOLIO
                .iter()
                .all(|key| strategy_keys.contains(key))
        );
        assert!(
            strategy_keys.contains(&(IndicatorKind::VolatilityAdjustedMomentum, Timeframe::H1))
        );
    }

    #[test]
    fn goal_search_filters_to_current_non_one_minute_candidates() {
        let candidates =
            candidate_grid_for_filters(GridSize::Tpe, None, Some(GOAL_SEARCH_SET)).unwrap();
        let mut strategy_keys = Vec::new();
        for candidate in &candidates {
            let key = (candidate.indicator, candidate.timeframe);
            if !strategy_keys.contains(&key) {
                strategy_keys.push(key);
            }
        }

        assert_eq!(candidates.len(), GOAL_SEARCH.len() * DEFAULT_TPE_TRIALS);
        assert_eq!(strategy_keys.len(), GOAL_SEARCH.len());
        assert!(GOAL_SEARCH.iter().all(|key| strategy_keys.contains(key)));
        assert!(
            candidates
                .iter()
                .all(|candidate| candidate.timeframe != Timeframe::M1)
        );
        assert!(strategy_keys.contains(&(IndicatorKind::Frama, Timeframe::H1)));
        assert!(strategy_keys.contains(&(IndicatorKind::DonchianBreakout, Timeframe::H1)));
    }

    #[test]
    fn high_trade_goal_filters_to_mid_timeframe_candidates() {
        let candidates =
            candidate_grid_for_filters(GridSize::Tpe, None, Some(HIGH_TRADE_GOAL_SET)).unwrap();
        let mut strategy_keys = Vec::new();
        for candidate in &candidates {
            let key = (candidate.indicator, candidate.timeframe);
            if !strategy_keys.contains(&key) {
                strategy_keys.push(key);
            }
        }

        assert_eq!(candidates.len(), HIGH_TRADE_GOAL.len() * DEFAULT_TPE_TRIALS);
        assert_eq!(strategy_keys.len(), HIGH_TRADE_GOAL.len());
        assert!(
            HIGH_TRADE_GOAL
                .iter()
                .all(|key| strategy_keys.contains(key))
        );
        assert!(candidates.iter().all(|candidate| {
            matches!(
                candidate.timeframe,
                Timeframe::M5 | Timeframe::M15 | Timeframe::M30
            )
        }));
        assert!(strategy_keys.contains(&(IndicatorKind::RelativeVigorIndex, Timeframe::M15)));
        assert!(
            strategy_keys.contains(&(IndicatorKind::VolatilityAdjustedMomentum, Timeframe::M30))
        );
    }

    #[test]
    fn high_trade_refine_filters_to_five_minute_candidates() {
        let candidates =
            candidate_grid_for_filters(GridSize::Tpe, None, Some(HIGH_TRADE_REFINE_SET)).unwrap();
        let mut strategy_keys = Vec::new();
        for candidate in &candidates {
            let key = (candidate.indicator, candidate.timeframe);
            if !strategy_keys.contains(&key) {
                strategy_keys.push(key);
            }
        }

        assert_eq!(
            candidates.len(),
            HIGH_TRADE_REFINE.len() * DEFAULT_TPE_TRIALS
        );
        assert_eq!(strategy_keys.len(), HIGH_TRADE_REFINE.len());
        assert!(
            HIGH_TRADE_REFINE
                .iter()
                .all(|key| strategy_keys.contains(key))
        );
        assert!(
            candidates
                .iter()
                .all(|candidate| candidate.timeframe == Timeframe::M5)
        );
    }

    #[test]
    fn portfolio_refine_filters_to_current_candidate_leads() {
        let candidates =
            candidate_grid_for_filters(GridSize::Tpe, None, Some(PORTFOLIO_REFINE_SET)).unwrap();
        let mut strategy_keys = Vec::new();
        for candidate in &candidates {
            let key = (candidate.indicator, candidate.timeframe);
            if !strategy_keys.contains(&key) {
                strategy_keys.push(key);
            }
        }

        assert_eq!(
            candidates.len(),
            PORTFOLIO_REFINE.len() * DEFAULT_TPE_TRIALS
        );
        assert_eq!(strategy_keys.len(), PORTFOLIO_REFINE.len());
        assert!(
            PORTFOLIO_REFINE
                .iter()
                .all(|key| strategy_keys.contains(key))
        );
        assert!(strategy_keys.contains(&(IndicatorKind::TrendFlex, Timeframe::M5)));
        assert!(
            strategy_keys.contains(&(IndicatorKind::VolatilityAdjustedMomentum, Timeframe::M30))
        );
    }

    #[test]
    fn quality_hunt_filters_to_non_one_minute_quality_leads() {
        let candidates =
            candidate_grid_for_filters(GridSize::Tpe, None, Some(QUALITY_HUNT_SET)).unwrap();
        let mut strategy_keys = Vec::new();
        for candidate in &candidates {
            let key = (candidate.indicator, candidate.timeframe);
            if !strategy_keys.contains(&key) {
                strategy_keys.push(key);
            }
        }

        assert_eq!(candidates.len(), QUALITY_HUNT.len() * DEFAULT_TPE_TRIALS);
        assert_eq!(strategy_keys.len(), QUALITY_HUNT.len());
        assert!(QUALITY_HUNT.iter().all(|key| strategy_keys.contains(key)));
        assert!(
            strategy_keys
                .iter()
                .all(|(_, timeframe)| *timeframe != Timeframe::M1)
        );
        assert!(strategy_keys.contains(&(IndicatorKind::DonchianBreakout, Timeframe::M15)));
        assert!(strategy_keys.contains(&(IndicatorKind::CenterOfGravity, Timeframe::M15)));
    }

    #[test]
    fn q3_diversifiers_filter_to_high_trade_positive_q3_leads() {
        let candidates =
            candidate_grid_for_filters(GridSize::Tpe, None, Some(Q3_DIVERSIFIERS_SET)).unwrap();
        let mut strategy_keys = Vec::new();
        for candidate in &candidates {
            let key = (candidate.indicator, candidate.timeframe);
            if !strategy_keys.contains(&key) {
                strategy_keys.push(key);
            }
        }

        assert_eq!(candidates.len(), Q3_DIVERSIFIERS.len() * DEFAULT_TPE_TRIALS);
        assert_eq!(strategy_keys.len(), Q3_DIVERSIFIERS.len());
        assert!(
            Q3_DIVERSIFIERS
                .iter()
                .all(|key| strategy_keys.contains(key))
        );
        assert!(
            strategy_keys
                .iter()
                .all(|(_, timeframe)| *timeframe != Timeframe::M1)
        );
        assert!(strategy_keys.contains(&(IndicatorKind::CyberCycle, Timeframe::M3)));
        assert!(strategy_keys.contains(&(IndicatorKind::EhlersRoofing, Timeframe::M30)));
    }

    #[test]
    fn best_combo_confirm_filters_to_current_viable_components() {
        let candidates =
            candidate_grid_for_filters(GridSize::Tpe, None, Some(BEST_COMBO_CONFIRM_SET)).unwrap();
        let mut strategy_keys = Vec::new();
        for candidate in &candidates {
            let key = (candidate.indicator, candidate.timeframe);
            if !strategy_keys.contains(&key) {
                strategy_keys.push(key);
            }
        }

        assert_eq!(
            candidates.len(),
            BEST_COMBO_CONFIRM.len() * DEFAULT_TPE_TRIALS
        );
        assert_eq!(strategy_keys.len(), BEST_COMBO_CONFIRM.len());
        assert!(
            BEST_COMBO_CONFIRM
                .iter()
                .all(|key| strategy_keys.contains(key))
        );
        assert!(
            strategy_keys
                .iter()
                .all(|(_, timeframe)| *timeframe != Timeframe::M1)
        );
        assert!(strategy_keys.contains(&(IndicatorKind::TrendFlex, Timeframe::M5)));
        assert!(strategy_keys.contains(&(IndicatorKind::InverseFisherTransform, Timeframe::M5)));
        assert!(strategy_keys.contains(&(IndicatorKind::DonchianBreakout, Timeframe::M30)));
    }

    #[test]
    fn frama_5m_confirm_filters_to_single_component() {
        let candidates =
            candidate_grid_for_filters(GridSize::Tpe, None, Some(FRAMA_5M_CONFIRM_SET)).unwrap();
        let mut strategy_keys = Vec::new();
        for candidate in &candidates {
            let key = (candidate.indicator, candidate.timeframe);
            if !strategy_keys.contains(&key) {
                strategy_keys.push(key);
            }
        }

        assert_eq!(
            candidates.len(),
            FRAMA_5M_CONFIRM.len() * DEFAULT_TPE_TRIALS
        );
        assert_eq!(strategy_keys, vec![(IndicatorKind::Frama, Timeframe::M5)]);
    }

    #[test]
    fn strategy_33x_sqx_filters_to_three_independent_kama_tpo_templates() {
        let candidates =
            candidate_grid_for_filters(GridSize::Tpe, None, Some(STRATEGY_33X_SQX_SET)).unwrap();
        let mut strategy_keys = Vec::new();
        for candidate in &candidates {
            let key = (candidate.indicator, candidate.timeframe);
            if !strategy_keys.contains(&key) {
                strategy_keys.push(key);
            }
        }

        assert_eq!(
            candidates.len(),
            STRATEGY_33X_SQX.len() * DEFAULT_TPE_TRIALS
        );
        assert_eq!(strategy_keys.len(), 3);
        assert!(strategy_keys.contains(&(IndicatorKind::Strategy336KamaTpo, Timeframe::M5)));
        assert!(strategy_keys.contains(&(IndicatorKind::Strategy3635KamaTpo, Timeframe::M5)));
        assert!(strategy_keys.contains(&(IndicatorKind::Strategy3938KamaTpo, Timeframe::M5)));
    }

    #[test]
    fn strategy_4448_filters_to_single_m5_template() {
        let candidates =
            candidate_grid_for_filters(GridSize::Tpe, None, Some(STRATEGY_4448_KAMA_KER_SET))
                .unwrap();
        let mut strategy_keys = Vec::new();
        for candidate in &candidates {
            let key = (candidate.indicator, candidate.timeframe);
            if !strategy_keys.contains(&key) {
                strategy_keys.push(key);
            }
        }

        assert_eq!(candidates.len(), DEFAULT_TPE_TRIALS);
        assert_eq!(
            strategy_keys,
            vec![(IndicatorKind::Strategy4448KamaKer, Timeframe::M5)]
        );
    }

    #[test]
    fn sqx_source_candidate_uses_saved_strategy_constants() {
        let template = Candidate {
            id: 7,
            indicator: IndicatorKind::Strategy336KamaTpo,
            timeframe: Timeframe::M5,
            signal_polarity: -1,
            entry_mode: EntryMode::Breakout,
            lookback: 999,
            atr_period: 999,
            entry_atr_multiple: 9.0,
            stop_atr_multiple: 9.0,
            target_atr_multiple: 9.0,
            time_stop_bars: None,
            hurst_min: Some(0.5),
            hurst_max: Some(0.8),
            shannon_max: Some(0.9),
            ..Candidate::default()
        };

        let strategy_336 = source_sqx_kama_tpo_candidate(&template);
        assert_eq!(strategy_336.id, 7);
        assert_eq!(strategy_336.indicator, IndicatorKind::Strategy336KamaTpo);
        assert_eq!(strategy_336.timeframe, Timeframe::M5);
        assert_eq!(strategy_336.signal_polarity, 1);
        assert_eq!(strategy_336.entry_mode, EntryMode::Pullback);
        assert_eq!(strategy_336.lookback, 40);
        assert_eq!(strategy_336.atr_period, 80);
        assert_eq!(strategy_336.entry_atr_multiple, 0.0);
        assert_eq!(strategy_336.stop_atr_multiple, 3.2);
        assert_eq!(strategy_336.target_atr_multiple, 7.1);
        assert_eq!(strategy_336.time_stop_bars, Some(28));
        assert_eq!(strategy_336.hurst_min, None);
        assert_eq!(strategy_336.hurst_max, None);
        assert_eq!(strategy_336.shannon_max, None);
        assert!(should_stitch_fixed_source_strategy_oos(&strategy_336));

        let mut template_3635 = template.clone();
        template_3635.indicator = IndicatorKind::Strategy3635KamaTpo;
        assert_eq!(
            source_sqx_kama_tpo_candidate(&template_3635).stop_atr_multiple,
            2.9
        );

        let mut template_3938 = template;
        template_3938.indicator = IndicatorKind::Strategy3938KamaTpo;
        assert_eq!(
            source_sqx_kama_tpo_candidate(&template_3938).stop_atr_multiple,
            2.9
        );

        let mut mutated = strategy_336;
        mutated.entry_atr_multiple = 0.5;
        assert!(!should_stitch_fixed_source_strategy_oos(&mutated));
    }

    #[test]
    fn strategy_4448_source_candidate_uses_saved_strategy_constants() {
        let template = Candidate {
            id: 11,
            indicator: IndicatorKind::Strategy4448KamaKer,
            timeframe: Timeframe::M5,
            signal_polarity: -1,
            entry_mode: EntryMode::Breakout,
            lookback: 999,
            atr_period: 999,
            entry_atr_multiple: 9.0,
            stop_atr_multiple: 9.0,
            target_atr_multiple: 9.0,
            time_stop_bars: None,
            hurst_min: Some(0.5),
            hurst_max: Some(0.8),
            shannon_max: Some(0.9),
            ..Candidate::default()
        };

        let strategy = source_strategy_4448_kama_ker_candidate(&template);

        assert_eq!(strategy.id, 11);
        assert_eq!(strategy.indicator, IndicatorKind::Strategy4448KamaKer);
        assert_eq!(strategy.timeframe, Timeframe::M5);
        assert_eq!(strategy.signal_polarity, 1);
        assert_eq!(strategy.entry_mode, EntryMode::Pullback);
        assert_eq!(strategy.lookback, 47);
        assert_eq!(strategy.atr_period, 80);
        assert_eq!(strategy.entry_atr_multiple, 0.0);
        assert_eq!(strategy.stop_atr_multiple, 2.6);
        assert_eq!(strategy.target_atr_multiple, 7.7);
        assert_eq!(strategy.time_stop_bars, Some(28));
        assert_eq!(strategy.hurst_min, None);
        assert_eq!(strategy.hurst_max, None);
        assert_eq!(strategy.shannon_max, None);
        assert_eq!(
            strategy.strategy_4448_kama1_er,
            STRATEGY_4448_SOURCE_KAMA1_ER
        );
        assert_eq!(
            strategy.strategy_4448_kama1_short,
            STRATEGY_4448_SOURCE_KAMA1_SHORT
        );
        assert_eq!(
            strategy.strategy_4448_kama1_long,
            STRATEGY_4448_SOURCE_KAMA1_LONG
        );
        assert_eq!(
            strategy.strategy_4448_kama2_er,
            STRATEGY_4448_SOURCE_KAMA2_ER
        );
        assert_eq!(
            strategy.strategy_4448_kama2_short,
            STRATEGY_4448_SOURCE_KAMA2_SHORT
        );
        assert_eq!(
            strategy.strategy_4448_kama2_long,
            STRATEGY_4448_SOURCE_KAMA2_LONG
        );
        assert_eq!(
            strategy.strategy_4448_count_bars,
            STRATEGY_4448_SOURCE_COUNT_BARS
        );
        assert!(should_stitch_fixed_source_strategy_oos(&strategy));

        let mut mutated = strategy;
        mutated.target_atr_multiple = 7.1;
        assert!(!should_stitch_fixed_source_strategy_oos(&mutated));
    }

    #[test]
    fn strategy_4448_tpe_samples_entry_constants_and_exits() {
        let template = Candidate {
            id: 11,
            indicator: IndicatorKind::Strategy4448KamaKer,
            timeframe: Timeframe::M5,
            signal_polarity: -1,
            entry_mode: EntryMode::Breakout,
            lookback: 999,
            atr_period: 999,
            entry_atr_multiple: 9.0,
            stop_atr_multiple: 9.0,
            target_atr_multiple: 9.0,
            time_stop_bars: None,
            hurst_min: Some(0.5),
            hurst_max: Some(0.8),
            shannon_max: Some(0.9),
            ..Candidate::default()
        };
        let search_space = TpeSearchSpace::new();
        let study: Study<f64> = Study::new(Direction::Maximize);
        let mut sampled_different_parameter = false;

        for _ in 0..24 {
            let mut trial = study.ask();
            let candidate = search_space
                .suggest_strategy_4448_kama_ker(&mut trial, &template)
                .unwrap();
            assert_eq!(candidate.id, 11);
            assert_eq!(candidate.indicator, IndicatorKind::Strategy4448KamaKer);
            assert_eq!(candidate.timeframe, Timeframe::M5);
            assert_eq!(candidate.signal_polarity, 1);
            assert_eq!(candidate.entry_mode, EntryMode::Pullback);
            assert!((5..=120).contains(&candidate.lookback));
            assert_eq!(candidate.entry_atr_multiple, 0.0);
            assert_eq!(candidate.time_stop_bars, Some(28));
            assert_eq!(candidate.hurst_min, None);
            assert_eq!(candidate.hurst_max, None);
            assert_eq!(candidate.shannon_max, None);
            assert!((5..=120).contains(&candidate.strategy_4448_kama1_er));
            assert!((2..=120).contains(&candidate.strategy_4448_kama1_short));
            assert!((2..=160).contains(&candidate.strategy_4448_kama1_long));
            assert!(candidate.strategy_4448_kama1_short < candidate.strategy_4448_kama1_long);
            assert!((5..=60).contains(&candidate.strategy_4448_kama2_er));
            assert!((2..=30).contains(&candidate.strategy_4448_kama2_short));
            assert!((2..=160).contains(&candidate.strategy_4448_kama2_long));
            assert!(candidate.strategy_4448_kama2_short < candidate.strategy_4448_kama2_long);
            assert!((3..=15).contains(&candidate.strategy_4448_count_bars));
            assert!((20..=200).contains(&candidate.atr_period));
            assert_eq!(candidate.atr_period % 5, 0);
            assert!(
                (MIN_EXIT_STOP_ATR_MULTIPLE..=MAX_EXIT_STOP_ATR_MULTIPLE)
                    .contains(&candidate.stop_atr_multiple)
            );
            assert!((2.0..=MAX_EXIT_TARGET_ATR_MULTIPLE).contains(&candidate.target_atr_multiple));
            assert!(
                candidate.target_atr_multiple
                    <= candidate.stop_atr_multiple * MAX_EXIT_TARGET_STOP_RATIO
            );
            sampled_different_parameter |= candidate.lookback != 47
                || candidate.strategy_4448_kama1_er != STRATEGY_4448_SOURCE_KAMA1_ER
                || candidate.strategy_4448_kama1_short != STRATEGY_4448_SOURCE_KAMA1_SHORT
                || candidate.strategy_4448_kama1_long != STRATEGY_4448_SOURCE_KAMA1_LONG
                || candidate.strategy_4448_kama2_er != STRATEGY_4448_SOURCE_KAMA2_ER
                || candidate.strategy_4448_kama2_short != STRATEGY_4448_SOURCE_KAMA2_SHORT
                || candidate.strategy_4448_kama2_long != STRATEGY_4448_SOURCE_KAMA2_LONG
                || candidate.strategy_4448_count_bars != STRATEGY_4448_SOURCE_COUNT_BARS
                || candidate.atr_period != 80
                || (candidate.stop_atr_multiple - 2.6).abs() > 1e-9
                || (candidate.target_atr_multiple - 7.7).abs() > 1e-9;
            study.tell(trial, Ok::<f64, &'static str>(0.0));
        }

        assert!(sampled_different_parameter);
    }

    #[test]
    fn optuna_strategy_4448_params_normalize_kama_period_order() {
        let template = Candidate {
            id: 42,
            indicator: IndicatorKind::Strategy4448KamaKer,
            timeframe: Timeframe::M5,
            ..Candidate::default()
        };
        let params = serde_json::json!({
            "strategy_4448_kama1_short": 90,
            "strategy_4448_kama1_long": 12,
            "strategy_4448_kama2_short": 28,
            "strategy_4448_kama2_long": 4
        });

        let candidate = optuna_candidate_from_params(&template, &params).unwrap();

        assert_eq!(candidate.strategy_4448_kama1_short, 12);
        assert_eq!(candidate.strategy_4448_kama1_long, 90);
        assert_eq!(candidate.strategy_4448_kama2_short, 4);
        assert_eq!(candidate.strategy_4448_kama2_long, 28);
    }

    #[test]
    fn strategy_4448_param_signature_includes_count_bars() {
        let mut left = Candidate {
            indicator: IndicatorKind::Strategy4448KamaKer,
            timeframe: Timeframe::M5,
            strategy_4448_count_bars: 3,
            ..Candidate::default()
        };
        let mut right = left.clone();
        right.strategy_4448_count_bars = 15;

        assert_ne!(
            candidate_param_signature(&left),
            candidate_param_signature(&right)
        );
        left.strategy_4448_count_bars = right.strategy_4448_count_bars;
        assert_eq!(
            candidate_param_signature(&left),
            candidate_param_signature(&right)
        );
    }

    #[test]
    fn sqx_entry_orders_remain_valid_for_199_chart_bars() {
        let candidate = Candidate {
            id: 1,
            indicator: IndicatorKind::Strategy336KamaTpo,
            timeframe: Timeframe::M5,
            signal_polarity: 1,
            entry_mode: EntryMode::Pullback,
            lookback: 40,
            atr_period: 80,
            entry_atr_multiple: 0.0,
            stop_atr_multiple: 3.2,
            target_atr_multiple: 7.1,
            time_stop_bars: Some(28),
            hurst_min: None,
            hurst_max: None,
            shannon_max: None,
            ..Candidate::default()
        };

        assert_eq!(entry_order_valid_bars(&candidate), 995);
    }

    #[test]
    fn strategy_4448_entry_orders_remain_valid_for_three_chart_bars() {
        let candidate = Candidate {
            id: 1,
            indicator: IndicatorKind::Strategy4448KamaKer,
            timeframe: Timeframe::M5,
            signal_polarity: 1,
            entry_mode: EntryMode::Pullback,
            lookback: 47,
            atr_period: 80,
            entry_atr_multiple: 0.0,
            stop_atr_multiple: 2.6,
            target_atr_multiple: 7.7,
            time_stop_bars: Some(28),
            hurst_min: None,
            hurst_max: None,
            shannon_max: None,
            ..Candidate::default()
        };

        assert_eq!(entry_order_valid_bars(&candidate), 15);
    }

    #[test]
    fn elegant_5m_strategy_set_filters_probe_grid_to_one_strategy_timeframe() {
        let candidates =
            candidate_grid_for_filters(GridSize::Probe, None, Some(ELEGANT_5M_SET)).unwrap();

        assert_eq!(candidates.len(), 2_184);
        assert!(candidates.iter().all(|candidate| {
            candidate.indicator == IndicatorKind::ElegantOscillator
                && candidate.timeframe == Timeframe::M5
        }));
    }

    #[test]
    fn elegant_5m_entry50_strategy_set_filters_to_single_entry_branch() {
        let candidates =
            candidate_grid_for_filters(GridSize::Wide200, None, Some(ELEGANT_5M_ENTRY50_SET))
                .unwrap();

        assert_eq!(candidates.len(), 100);
        assert!(candidates.iter().all(|candidate| {
            candidate.indicator == IndicatorKind::ElegantOscillator
                && candidate.timeframe == Timeframe::M5
                && candidate.entry_atr_multiple == 0.5
        }));
    }

    #[test]
    fn elegant_5m_entry50_gated_strategy_set_filters_to_core_profile() {
        let candidates =
            candidate_grid_for_filters(GridSize::Wide200, None, Some(ELEGANT_5M_ENTRY50_GATED_SET))
                .unwrap();

        assert_eq!(candidates.len(), 20);
        assert!(candidates.iter().all(|candidate| {
            candidate.indicator == IndicatorKind::ElegantOscillator
                && candidate.timeframe == Timeframe::M5
                && candidate.entry_atr_multiple == 0.5
                && candidate.stop_atr_multiple == 2.0
                && candidate.target_atr_multiple == 5.0
                && candidate.time_stop_bars == Some(24)
                && candidate.hurst_min == Some(0.52)
                && candidate.shannon_max == Some(0.85)
        }));
    }

    #[test]
    fn elegant_5m_entry50_ungated_strategy_set_filters_to_fast_profile() {
        let candidates = candidate_grid_for_filters(
            GridSize::Wide200,
            None,
            Some(ELEGANT_5M_ENTRY50_UNGATED_SET),
        )
        .unwrap();

        assert_eq!(candidates.len(), 20);
        assert!(candidates.iter().all(|candidate| {
            candidate.indicator == IndicatorKind::ElegantOscillator
                && candidate.timeframe == Timeframe::M5
                && candidate.entry_atr_multiple == 0.5
                && candidate.stop_atr_multiple == 1.5
                && candidate.target_atr_multiple == 3.0
                && candidate.time_stop_bars == Some(24)
                && candidate.hurst_min.is_none()
                && candidate.shannon_max.is_none()
        }));
    }

    #[test]
    fn elegant_5m_hybrid_keeps_core_profile_for_choppy_symbols() {
        let candidates =
            candidate_grid_for_filters(GridSize::Wide200, None, Some(ELEGANT_5M_HYBRID_SET))
                .unwrap();

        assert_eq!(candidates.len(), 100);
        let doge_allowed = candidates
            .iter()
            .filter(|candidate| {
                candidate_allowed_for_symbol(Some(ELEGANT_5M_HYBRID_SET), "DOGEUSDT", candidate)
            })
            .count();
        let sol_allowed = candidates
            .iter()
            .filter(|candidate| {
                candidate_allowed_for_symbol(Some(ELEGANT_5M_HYBRID_SET), "SOLUSDT", candidate)
            })
            .count();

        assert_eq!(doge_allowed, 20);
        assert_eq!(sol_allowed, 100);
    }

    #[test]
    fn probe_grid_requires_scope() {
        assert!(validate_grid_scope(GridSize::Probe, None, None).is_err());
        assert!(validate_grid_scope(GridSize::Probe, None, Some(ELEGANT_5M_SET)).is_ok());
    }

    #[test]
    fn htf_signals_become_available_after_candle_completion() {
        let bars = (0..7)
            .map(|i| OhlcvBar {
                open_time_ms: i * MS_PER_MINUTE,
                open: 100.0,
                high: 101.0,
                low: 99.0,
                close: 100.0,
                volume: 1.0,
            })
            .collect::<Vec<_>>();
        let tf_signals = vec![SignalPoint {
            timestamp_ms: 0,
            direction: 1,
            strength: 1.0,
            atr: 1.0,
            entry_reference: None,
        }];

        let expanded = expand_signals(&bars, &tf_signals, Timeframe::M5);

        assert_eq!(
            expanded
                .iter()
                .take(4)
                .map(|signal| signal.direction)
                .collect::<Vec<_>>(),
            vec![0, 0, 0, 0]
        );
        assert_eq!(expanded[4].direction, 1);
        assert_eq!(expanded[5].direction, 1);
    }

    #[test]
    fn htf_signal_entry_reference_persists_after_candle_completion() {
        let bars = (0..7)
            .map(|i| OhlcvBar {
                open_time_ms: i * MS_PER_MINUTE,
                open: 100.0,
                high: 101.0,
                low: 99.0,
                close: 100.0,
                volume: 1.0,
            })
            .collect::<Vec<_>>();
        let tf_signals = vec![SignalPoint {
            timestamp_ms: 0,
            direction: 1,
            strength: 1.0,
            atr: 1.0,
            entry_reference: Some(99.5),
        }];

        let expanded = expand_signals(&bars, &tf_signals, Timeframe::M5);

        assert_eq!(
            expanded
                .iter()
                .map(|signal| signal.direction)
                .collect::<Vec<_>>(),
            vec![0, 0, 0, 0, 1, 1, 1]
        );
        assert_eq!(expanded[4].entry_reference, Some(99.5));
        assert_eq!(expanded[5].entry_reference, Some(99.5));
        assert_eq!(expanded[6].entry_reference, Some(99.5));
    }

    #[test]
    fn htf_signal_cannot_fill_on_the_completion_minute() {
        let bars = (0..7)
            .map(|i| OhlcvBar {
                open_time_ms: i * MS_PER_MINUTE,
                open: 100.0,
                high: if i == 4 { 105.0 } else { 100.0 },
                low: 99.0,
                close: 100.0,
                volume: 1.0,
            })
            .collect::<Vec<_>>();
        let tf_signals = vec![SignalPoint {
            timestamp_ms: 0,
            direction: 1,
            strength: 1.0,
            atr: 1.0,
            entry_reference: Some(100.0),
        }];
        let expanded = expand_signals(&bars, &tf_signals, Timeframe::M5);
        let config = ExecutionConfig {
            entry_mode: EntryMode::Breakout,
            entry_atr_multiple: 0.0,
            stop_atr_multiple: 2.0,
            target_atr_multiple: 10.0,
            time_stop_bars: Some(1),
            entry_order_valid_bars: 1,
            symbol_rules: SymbolExecutionRules::synthetic(),
            ..ExecutionConfig::default()
        };

        let (trades, _) =
            simulate_limit_momentum_trades_with_diagnostics("SYNTHUSDT", &bars, &expanded, config);

        assert!(trades.is_empty());
    }

    #[test]
    fn htf_signal_can_fill_on_the_next_minute_after_completion() {
        let bars = (0..7)
            .map(|i| OhlcvBar {
                open_time_ms: i * MS_PER_MINUTE,
                open: 100.0,
                high: if i == 5 { 105.0 } else { 100.0 },
                low: 99.0,
                close: 100.0,
                volume: 1.0,
            })
            .collect::<Vec<_>>();
        let tf_signals = vec![SignalPoint {
            timestamp_ms: 0,
            direction: 1,
            strength: 1.0,
            atr: 1.0,
            entry_reference: Some(100.0),
        }];
        let expanded = expand_signals(&bars, &tf_signals, Timeframe::M5);
        let config = ExecutionConfig {
            entry_mode: EntryMode::Breakout,
            entry_atr_multiple: 0.0,
            stop_atr_multiple: 2.0,
            target_atr_multiple: 10.0,
            time_stop_bars: Some(1),
            entry_order_valid_bars: 1,
            symbol_rules: SymbolExecutionRules::synthetic(),
            ..ExecutionConfig::default()
        };

        let (trades, _) =
            simulate_limit_momentum_trades_with_diagnostics("SYNTHUSDT", &bars, &expanded, config);

        assert_eq!(trades.len(), 1);
        assert_eq!(trades[0].entry_time_ms, 5 * MS_PER_MINUTE);
    }

    #[test]
    fn one_minute_signals_keep_existing_next_bar_timing() {
        let bars = (0..2)
            .map(|i| OhlcvBar {
                open_time_ms: i * MS_PER_MINUTE,
                open: 100.0,
                high: 101.0,
                low: 99.0,
                close: 100.0,
                volume: 1.0,
            })
            .collect::<Vec<_>>();
        let tf_signals = vec![SignalPoint {
            timestamp_ms: 0,
            direction: -1,
            strength: 1.0,
            atr: 1.0,
            entry_reference: None,
        }];

        let expanded = expand_signals(&bars, &tf_signals, Timeframe::M1);

        assert_eq!(expanded[0].direction, -1);
        assert_eq!(expanded[1].direction, -1);
    }

    #[test]
    fn signal_polarity_inverts_direction_without_changing_timing() {
        let mut signals = vec![
            SignalPoint {
                timestamp_ms: 0,
                direction: 1,
                strength: 1.0,
                atr: 1.0,
                entry_reference: None,
            },
            SignalPoint {
                timestamp_ms: MS_PER_MINUTE,
                direction: -1,
                strength: 0.5,
                atr: 2.0,
                entry_reference: None,
            },
            SignalPoint {
                timestamp_ms: 2 * MS_PER_MINUTE,
                direction: 0,
                strength: 0.0,
                atr: 1.0,
                entry_reference: None,
            },
        ];

        apply_signal_polarity(&mut signals, -1);

        assert_eq!(
            signals
                .iter()
                .map(|signal| (signal.timestamp_ms, signal.direction))
                .collect::<Vec<_>>(),
            vec![(0, -1), (MS_PER_MINUTE, 1), (2 * MS_PER_MINUTE, 0)]
        );
    }

    #[test]
    fn time_stop_bars_are_signal_timeframe_bars() {
        let mut candidate = Candidate {
            id: 0,
            indicator: IndicatorKind::EhlersDecycler,
            timeframe: Timeframe::H1,
            signal_polarity: 1,
            entry_mode: EntryMode::Pullback,
            lookback: 12,
            atr_period: 14,
            entry_atr_multiple: 0.5,
            stop_atr_multiple: 1.5,
            target_atr_multiple: 2.0,
            time_stop_bars: Some(24),
            hurst_min: None,
            hurst_max: None,
            shannon_max: None,
            ..Candidate::default()
        };

        assert_eq!(execution_time_stop_bars(&candidate), Some(1_440));
        candidate.timeframe = Timeframe::M5;
        assert_eq!(execution_time_stop_bars(&candidate), Some(120));
        candidate.time_stop_bars = None;
        assert_eq!(execution_time_stop_bars(&candidate), None);
    }

    #[test]
    fn long_only_score_is_excess_return() {
        assert_eq!(long_only_excess_score(12.0, 8.0), 4.0);
    }

    #[test]
    fn candidate_grid_excludes_not_applicable_catalog_items() {
        let candidates = candidate_grid(GridSize::Wide);

        assert!(!candidates.is_empty());
        assert!(
            candidates
                .iter()
                .all(|candidate| candidate.indicator.is_runnable_strategy())
        );
        for kind in IndicatorKind::NOT_APPLICABLE_V1 {
            assert!(
                !candidates
                    .iter()
                    .any(|candidate| candidate.indicator == kind)
            );
        }
    }

    #[test]
    fn wide_grid_sweeps_regime_gate_profiles() {
        let candidates = candidate_grid(GridSize::Wide);

        assert!(
            candidates
                .iter()
                .any(|candidate| candidate.shannon_max.is_none() && candidate.hurst_min.is_none())
        );
        assert!(
            candidates
                .iter()
                .any(|candidate| candidate.shannon_max == Some(0.85)
                    && candidate.hurst_min == Some(0.52))
        );
    }

    #[test]
    fn drawdown_is_reported_as_percent_of_fixed_notional() {
        let trades = [
            Trade {
                symbol: "BTCUSDT".to_string(),
                entry_time_ms: 0,
                exit_time_ms: 1,
                side: crate::engine::TradeSide::Long,
                entry_price: 100.0,
                exit_price: 110.0,
                quantity: 10.0,
                pnl: 100.0,
                return_pct: 10.0,
                exit_reason: "target".to_string(),
            },
            Trade {
                symbol: "BTCUSDT".to_string(),
                entry_time_ms: 2,
                exit_time_ms: 3,
                side: crate::engine::TradeSide::Long,
                entry_price: 100.0,
                exit_price: 95.0,
                quantity: 10.0,
                pnl: -50.0,
                return_pct: -5.0,
                exit_reason: "stop".to_string(),
            },
        ];
        let refs = trades.iter().collect::<Vec<_>>();

        assert_eq!(max_drawdown_pct_from_trade_refs(&refs), 5.0);
        assert_eq!(max_drawdown_pct_from_trades(&trades), 5.0);
    }

    #[test]
    fn single_strategy_primary_artifacts_use_all_symbol_fold_trades() {
        let row = StrategyRow {
            indicator: IndicatorKind::Strategy4448KamaKer.as_str().to_string(),
            timeframe: Timeframe::M5.as_str().to_string(),
            implementation_status: "implemented".to_string(),
            implementation_note: String::new(),
            runnable: true,
            parameter_candidates: 2,
            status: "complete".to_string(),
            progress_pct: 100.0,
            progress_label: "complete".to_string(),
            folds_scored: 2,
            best_score: 1.0,
            net_return_pct: 0.0,
            max_drawdown_pct: 0.0,
            trades: 0,
        };
        let mut btc_score = candidate_score(9.0);
        btc_score.symbol = "BTCUSDT".to_string();
        btc_score.fold_index = 0;
        btc_score.candidate_id = 10;
        let mut xrp_score = candidate_score(8.0);
        xrp_score.symbol = "XRPUSDT".to_string();
        xrp_score.fold_index = 0;
        xrp_score.candidate_id = 11;
        let btc_trade = test_trade("BTCUSDT", 10, 10.0);
        let xrp_trade = test_trade("XRPUSDT", 20, -4.0);
        let mut strategy_selections = BTreeMap::new();
        strategy_selections.insert(
            (
                row.indicator.clone(),
                row.timeframe.clone(),
                "BTCUSDT".to_string(),
                0,
            ),
            FoldSelection {
                score: btc_score.clone(),
                rank_score: 9.0,
                indicator: IndicatorKind::Strategy4448KamaKer,
                trades: vec![btc_trade.clone()],
            },
        );
        strategy_selections.insert(
            (
                row.indicator.clone(),
                row.timeframe.clone(),
                "XRPUSDT".to_string(),
                0,
            ),
            FoldSelection {
                score: xrp_score.clone(),
                rank_score: 8.0,
                indicator: IndicatorKind::Strategy4448KamaKer,
                trades: vec![xrp_trade.clone()],
            },
        );
        let mut best_by_fold = BTreeMap::new();
        best_by_fold.insert(
            0,
            FoldSelection {
                score: btc_score,
                rank_score: 9.0,
                indicator: IndicatorKind::Strategy4448KamaKer,
                trades: vec![btc_trade],
            },
        );

        let selected = primary_artifact_selection(
            &[row],
            &["BTCUSDT".to_string(), "XRPUSDT".to_string()],
            &strategy_selections,
            &best_by_fold,
            1_000.0,
        );

        assert_eq!(selected.trades.len(), 2);
        assert_eq!(selected.scores.len(), 2);
        assert_eq!(
            selected
                .trades
                .iter()
                .map(|trade| trade.symbol.as_str())
                .collect::<Vec<_>>(),
            vec!["BTCUSDT", "XRPUSDT"]
        );
        assert_eq!(
            selected
                .best_fold_trades
                .as_ref()
                .map(|trades| trades.len()),
            Some(1)
        );
        assert!(selected.risk_managed_trades.is_some());
    }

    #[test]
    fn single_strategy_primary_artifacts_do_not_name_best_without_selection() {
        let row = StrategyRow {
            indicator: IndicatorKind::Frama.as_str().to_string(),
            timeframe: Timeframe::M5.as_str().to_string(),
            implementation_status: "implemented".to_string(),
            implementation_note: String::new(),
            runnable: true,
            parameter_candidates: 300,
            status: "complete".to_string(),
            progress_pct: 100.0,
            progress_label: "complete".to_string(),
            folds_scored: 0,
            best_score: 0.0,
            net_return_pct: 0.0,
            max_drawdown_pct: 0.0,
            trades: 0,
        };

        let selected = primary_artifact_selection(
            &[row],
            &["BTCUSDT".to_string(), "SOLUSDT".to_string()],
            &BTreeMap::new(),
            &BTreeMap::new(),
            1_000.0,
        );

        assert!(selected.trades.is_empty());
        assert!(selected.scores.is_empty());
        assert_eq!(selected.best_indicator, "none");
        assert!(selected.risk_managed_trades.is_none());
    }

    #[test]
    fn summary_return_is_percent_of_portfolio_account_balance() {
        let config = WfoConfig::new(GridSize::Wide);
        let trades = vec![
            Trade {
                symbol: "BTCUSDT".to_string(),
                entry_time_ms: 0,
                exit_time_ms: 1,
                side: crate::engine::TradeSide::Long,
                entry_price: 100.0,
                exit_price: 110.0,
                quantity: 10.0,
                pnl: 100.0,
                return_pct: 10.0,
                exit_reason: "target".to_string(),
            },
            Trade {
                symbol: "BTCUSDT".to_string(),
                entry_time_ms: 2,
                exit_time_ms: 3,
                side: crate::engine::TradeSide::Long,
                entry_price: 100.0,
                exit_price: 95.0,
                quantity: 10.0,
                pnl: -50.0,
                return_pct: -5.0,
                exit_reason: "stop".to_string(),
            },
        ];

        let account_stats = AccountCurveStats {
            samples: 2,
            total_pnl: 50.0,
            net_return_pct: 0.5,
            max_drawdown: 50.0,
            max_drawdown_pct: 0.5,
            exposure_pct: 50.0,
            long_exposure_pct: 50.0,
            short_exposure_pct: 0.0,
            average_exposure_notional: 500.0,
            average_long_exposure_notional: 500.0,
            average_short_exposure_notional: 0.0,
            average_net_exposure_notional: 500.0,
            max_exposure_notional: 1_000.0,
            max_long_exposure_notional: 1_000.0,
            max_short_exposure_notional: 0.0,
            max_abs_net_exposure_notional: 1_000.0,
            max_concurrent_positions: 1,
            max_concurrent_long_positions: 1,
            max_concurrent_short_positions: 0,
            longest_stagnation_minutes: 60,
            longest_stagnation_days: 60.0 / 1_440.0,
            return_to_drawdown_ratio: 1.0,
            smoothness_score: 1.0 / (1.0 + (60.0 / 1_440.0) / 30.0),
        };
        let summary = summarize(&config, 1, 1, &trades, &account_stats, "test");

        assert_eq!(summary.total_pnl, 50.0);
        assert_eq!(summary.fixed_notional, 1_000.0);
        assert_eq!(summary.account_balance, 10_000.0);
        assert_eq!(summary.net_return_pct, 0.5);
        assert_eq!(summary.max_drawdown_pct, 0.5);
        assert_eq!(summary.exposure_pct, 50.0);
        assert_eq!(summary.long_exposure_pct, 50.0);
        assert_eq!(summary.short_exposure_pct, 0.0);
        assert_eq!(summary.average_net_exposure_notional, 500.0);
        assert_eq!(summary.return_to_drawdown_ratio, 1.0);
    }

    #[test]
    fn account_artifacts_mark_to_market_exposure_and_stagnation() {
        let config = WfoConfig::new(GridSize::Wide);
        let fold = Fold {
            index: 0,
            is_start_ms: 0,
            is_end_ms: 0,
            oos_start_ms: 0,
            oos_end_ms: 5 * MS_PER_MINUTE,
        };
        let data = vec![(
            "BTCUSDT".to_string(),
            vec![
                OhlcvBar {
                    open_time_ms: 0,
                    open: 100.0,
                    high: 100.0,
                    low: 100.0,
                    close: 100.0,
                    volume: 1.0,
                },
                OhlcvBar {
                    open_time_ms: MS_PER_MINUTE,
                    open: 103.0,
                    high: 103.0,
                    low: 103.0,
                    close: 103.0,
                    volume: 1.0,
                },
                OhlcvBar {
                    open_time_ms: 2 * MS_PER_MINUTE,
                    open: 102.0,
                    high: 102.0,
                    low: 102.0,
                    close: 102.0,
                    volume: 1.0,
                },
            ],
        )];
        let trades = vec![Trade {
            symbol: "BTCUSDT".to_string(),
            entry_time_ms: 0,
            exit_time_ms: 2 * MS_PER_MINUTE,
            side: crate::engine::TradeSide::Long,
            entry_price: 100.0,
            exit_price: 102.0,
            quantity: 10.0,
            pnl: 20.0,
            return_pct: 2.0,
            exit_reason: "time".to_string(),
        }];

        let artifacts = build_account_artifacts(&config, &[fold], &trades, &data).unwrap();

        assert_eq!(artifacts.equity.len(), 5);
        assert_eq!(artifacts.equity[1].unrealized_pnl, 30.0);
        assert_eq!(artifacts.equity[2].realized_pnl, 20.0);
        assert_eq!(artifacts.stats.net_return_pct, 0.2);
        assert_eq!(artifacts.stats.exposure_pct, 40.0);
        assert_eq!(artifacts.stats.long_exposure_pct, 40.0);
        assert_eq!(artifacts.stats.short_exposure_pct, 0.0);
        assert_eq!(artifacts.stats.average_net_exposure_notional, 400.0);
        assert_eq!(artifacts.stats.max_drawdown_pct, 0.1);
        assert_eq!(artifacts.stats.max_concurrent_positions, 1);
        assert_eq!(artifacts.stats.max_concurrent_long_positions, 1);
        assert_eq!(artifacts.stats.max_concurrent_short_positions, 0);
        assert_eq!(artifacts.stats.longest_stagnation_minutes, 2);
        assert!((artifacts.stats.longest_stagnation_days - (2.0 / 1_440.0)).abs() < 1e-12);
        assert!((artifacts.stats.return_to_drawdown_ratio - 2.0).abs() < 1e-12);
        assert!(
            (artifacts.stats.smoothness_score - (2.0 / (1.0 + (2.0 / 1_440.0) / 30.0))).abs()
                < 1e-12
        );
    }

    #[test]
    fn wide_grid_is_practical_all_strategy_sweep() {
        let candidates = candidate_grid(GridSize::Wide);

        assert_eq!(
            candidates.len(),
            IndicatorKind::IMPLEMENTED_DIRECT_OHLC.len() * 216
        );
        assert_eq!(
            candidates
                .iter()
                .filter(|candidate| candidate.indicator == IndicatorKind::EhlersDecycler)
                .count(),
            216
        );
    }

    #[test]
    fn wide200_grid_has_two_hundred_candidates_per_strategy_timeframe() {
        let candidates = candidate_grid(GridSize::Wide200);
        let mut counts: std::collections::HashMap<(IndicatorKind, Timeframe), usize> =
            std::collections::HashMap::new();
        for candidate in &candidates {
            *counts
                .entry((candidate.indicator, candidate.timeframe))
                .or_default() += 1;
        }

        assert_eq!(
            candidates.len(),
            IndicatorKind::IMPLEMENTED_DIRECT_OHLC.len() * 6 * 200
        );
        assert_eq!(
            counts.len(),
            IndicatorKind::IMPLEMENTED_DIRECT_OHLC.len() * 6
        );
        assert!(counts.values().all(|count| *count == 200));
    }

    #[test]
    fn tpe_grid_defaults_to_two_week_is_and_one_hundred_fifty_trials() {
        let config = WfoConfig::new(GridSize::Tpe);

        assert_eq!(config.is_weeks, 2);
        assert_eq!(config.oos_weeks, 1);
        assert_eq!(config.step_weeks, 1);
        assert_eq!(config.gap_weeks, 0);
        assert_eq!(config.candidate_min_profit_factor, 1.2);
        assert_eq!(config.tpe_trials, 150);
        assert_eq!(config.tpe_random_startup_fraction, 0.15);
        assert_eq!(config.tpe_seed, None);
    }

    #[test]
    fn tpe_grid_has_configurable_trial_templates_per_strategy_timeframe() {
        let candidates = candidate_grid_with_trials(GridSize::Tpe, 17);
        let mut counts: std::collections::HashMap<(IndicatorKind, Timeframe), usize> =
            std::collections::HashMap::new();
        for candidate in &candidates {
            *counts
                .entry((candidate.indicator, candidate.timeframe))
                .or_default() += 1;
        }

        assert_eq!(
            candidates.len(),
            IndicatorKind::IMPLEMENTED_DIRECT_OHLC.len() * 6 * 17
        );
        assert_eq!(
            counts.len(),
            IndicatorKind::IMPLEMENTED_DIRECT_OHLC.len() * 6
        );
        assert!(counts.values().all(|count| *count == 17));
    }

    /// Verifies that a point-in-time sequential live simulation (where market data is strictly
    /// truncated to rows[0..=t] at each wall-clock step t) produces signals and trades that match
    /// the full batch backtester 100% bit-for-bit, proving zero lookahead bias.
    #[test]
    fn strict_point_in_time_live_frontier_simulation_matches_backtester() {
        let bars = (0..300)
            .map(|i| {
                let price = 100.0 + (i as f64 * 0.1).sin() * 5.0 + i as f64 * 0.05;
                OhlcvBar {
                    open_time_ms: i * MS_PER_MINUTE,
                    open: price,
                    high: price + 1.5,
                    low: price - 1.5,
                    close: price + 0.2,
                    volume: 10.0,
                }
            })
            .collect::<Vec<_>>();

        let candidate = Candidate {
            id: 99999,
            indicator: IndicatorKind::Frama,
            timeframe: Timeframe::M5,
            signal_polarity: 1,
            entry_mode: EntryMode::Breakout,
            lookback: 8,
            atr_period: 14,
            entry_atr_multiple: 0.1,
            stop_atr_multiple: 1.5,
            target_atr_multiple: 3.0,
            time_stop_bars: Some(20),
            ..Candidate::default()
        };

        let config = WfoConfig::new(GridSize::Smoke);
        let mut cache = SimulationCache::default();
        let prepared =
            prepare_candidate_simulation("SYNTHUSDT", &bars, &candidate, &config, &mut cache)
                .unwrap();
        let fold = Fold {
            index: 0,
            is_start_ms: 0,
            is_end_ms: 300 * MS_PER_MINUTE,
            oos_start_ms: 0,
            oos_end_ms: 300 * MS_PER_MINUTE,
        };
        let batch_result = simulate_prepared_candidate(&bars, &prepared, &[fold]);

        let mut live_signals = Vec::new();
        for i in 0..bars.len() {
            let frontier_bars = &bars[0..=i];
            let tf_bars = resample_ohlcv(frontier_bars, candidate.timeframe);
            let tf_signals = momentum_signals(
                &tf_bars,
                candidate.indicator,
                candidate.lookback,
                candidate.atr_period,
            );
            let expanded = expand_signals(frontier_bars, &tf_signals, candidate.timeframe);
            live_signals.push(*expanded.last().unwrap());
        }

        for (i, (live_signal, prepared_signal)) in live_signals
            .iter()
            .zip(prepared.signals_1m.iter())
            .enumerate()
            .take(bars.len())
        {
            assert_eq!(
                live_signal.direction, prepared_signal.direction,
                "Signal direction mismatch at bar index {}",
                i
            );
            assert_eq!(
                live_signal.timestamp_ms, prepared_signal.timestamp_ms,
                "Timestamp mismatch at bar index {}",
                i
            );
        }

        let execution = prepared.execution;
        let (live_trades, _) = crate::engine::simulate_limit_momentum_trades_with_diagnostics(
            "SYNTHUSDT",
            &bars,
            &live_signals,
            execution,
        );

        assert_eq!(
            live_trades.len(),
            batch_result.trades.len(),
            "Trade count mismatch between live frontier and backtester"
        );
        for (lt, bt) in live_trades.iter().zip(batch_result.trades.iter()) {
            assert_eq!(lt.entry_time_ms, bt.entry_time_ms);
            assert_eq!(lt.exit_time_ms, bt.exit_time_ms);
            assert_eq!(lt.side, bt.side);
            assert!((lt.entry_price - bt.entry_price).abs() < 1e-12);
            assert!((lt.exit_price - bt.exit_price).abs() < 1e-12);
            assert!((lt.pnl - bt.pnl).abs() < 1e-12);
            assert_eq!(lt.exit_reason, bt.exit_reason);
        }
    }
}
