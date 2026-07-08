use anyhow::{Context, Result};
use clap::{Parser, Subcommand};
use rust_trend::data::binance_um::{KlineStore, parse_date, preset_symbols};
use rust_trend::wfo::{
    DailyOffsetEnsembleOptions, DailyOffsetRunSpec, FillModelExperimentOptions, GridSize,
    OptimizerMode, WfoRunOptions,
};
use rust_trend::{BacktestConfig, run_backtest};
use std::path::PathBuf;
use std::process::Command as ProcessCommand;

#[derive(Debug, Parser)]
#[command(name = "rust_trend")]
#[command(about = "Trend backtester research tools")]
struct Cli {
    #[command(subcommand)]
    command: Option<Command>,
}

#[derive(Debug, Subcommand)]
#[allow(clippy::large_enum_variant)]
enum Command {
    Data {
        #[command(subcommand)]
        command: DataCommand,
    },
    Wfo {
        #[command(subcommand)]
        command: WfoCommand,
    },
    Dashboard {
        #[command(subcommand)]
        command: DashboardCommand,
    },
}

#[derive(Debug, Subcommand)]
enum DataCommand {
    Sync {
        #[arg(long, default_value = "binance-um-top7-2025")]
        preset: String,
        #[arg(long, default_value = "2025-01-01")]
        start: String,
        #[arg(long, default_value = "2026-01-01")]
        end: String,
        #[arg(long)]
        force: bool,
    },
    Verify {
        #[arg(long, default_value = "binance-um-top7-2025")]
        preset: String,
        #[arg(long, default_value = "2025-01-01")]
        start: String,
        #[arg(long, default_value = "2026-01-01")]
        end: String,
    },
    Coverage,
}

#[derive(Debug, Subcommand)]
#[allow(clippy::large_enum_variant)]
enum WfoCommand {
    Run {
        #[arg(long, default_value = "smoke")]
        grid: String,
        #[arg(long, value_delimiter = ',')]
        symbols: Vec<String>,
        #[arg(long)]
        indicator_group: Option<String>,
        #[arg(long)]
        strategy_set: Option<String>,
        #[arg(long, default_value = "point_in_time_fold_local")]
        optimizer_mode: OptimizerMode,
        #[arg(long)]
        resume_run_id: Option<String>,
        #[arg(long)]
        min_profit_factor: Option<f64>,
        #[arg(long)]
        candidate_min_profit_factor: Option<f64>,
        #[arg(long)]
        account_balance: Option<f64>,
        #[arg(long)]
        fees_bps: Option<f64>,
        #[arg(long)]
        trials: Option<usize>,
        #[arg(long)]
        random_startup_fraction: Option<f64>,
        #[arg(long)]
        tpe_seed: Option<u64>,
        #[arg(long)]
        is_weeks: Option<i64>,
        #[arg(long)]
        is_days: Option<i64>,
        #[arg(long)]
        oos_weeks: Option<i64>,
        #[arg(long)]
        oos_days: Option<i64>,
        #[arg(long)]
        step_weeks: Option<i64>,
        #[arg(long)]
        step_days: Option<i64>,
        #[arg(long)]
        gap_weeks: Option<i64>,
        #[arg(long)]
        gap_days: Option<i64>,
        #[arg(long, allow_hyphen_values = true)]
        start_offset_days: Option<i64>,
        #[arg(long)]
        fold_start_index: Option<usize>,
        #[arg(long)]
        fold_limit: Option<usize>,
        #[arg(long)]
        start_date: Option<String>,
        #[arg(long)]
        end_date: Option<String>,
    },
    OptunaRun {
        #[arg(long, value_delimiter = ',')]
        symbols: Vec<String>,
        #[arg(long)]
        indicator_group: Option<String>,
        #[arg(long)]
        strategy_set: Option<String>,
        #[arg(long, default_value = "point_in_time_fold_local")]
        optimizer_mode: OptimizerMode,
        #[arg(long, default_value_t = 150)]
        trials: usize,
        #[arg(long)]
        seed: Option<u64>,
        #[arg(long)]
        tpe_consensus_min_passing_windows: Option<usize>,
        #[arg(long, default_value_t = 0.15)]
        random_startup_fraction: f64,
        #[arg(long, default_value_t = 128)]
        ei_candidates: usize,
        #[arg(long)]
        batch_size: Option<usize>,
        #[arg(long, default_value = "memory")]
        storage: String,
        #[arg(long)]
        min_profit_factor: Option<f64>,
        #[arg(long)]
        candidate_min_profit_factor: Option<f64>,
        #[arg(long)]
        account_balance: Option<f64>,
        #[arg(long)]
        fees_bps: Option<f64>,
        #[arg(long, default_value_t = 2)]
        is_weeks: i64,
        #[arg(long)]
        is_days: Option<i64>,
        #[arg(long, default_value_t = 1)]
        oos_weeks: i64,
        #[arg(long)]
        oos_days: Option<i64>,
        #[arg(long, default_value_t = 1)]
        step_weeks: i64,
        #[arg(long)]
        step_days: Option<i64>,
        #[arg(long, default_value_t = 0)]
        gap_weeks: i64,
        #[arg(long)]
        gap_days: Option<i64>,
        #[arg(long, default_value_t = 0, allow_hyphen_values = true)]
        start_offset_days: i64,
        #[arg(long)]
        fold_start_index: Option<usize>,
        #[arg(long)]
        fold_limit: Option<usize>,
        #[arg(long)]
        start_date: Option<String>,
        #[arg(long)]
        end_date: Option<String>,
    },
    Verify,
    SummaryPage {
        #[arg(long)]
        run_id: String,
    },
    Diagnose {
        #[arg(long)]
        run_id: String,
        #[arg(long, value_delimiter = ',')]
        pairs: Vec<String>,
    },
    Stress {
        #[arg(long)]
        run_id: String,
        #[arg(long, value_delimiter = ',')]
        pairs: Vec<String>,
        #[arg(long, default_value_t = 1.2)]
        min_profit_factor: f64,
    },
    Ecc {
        #[arg(long)]
        run_id: String,
        #[arg(long, value_delimiter = ',')]
        pairs: Vec<String>,
        #[arg(long, value_delimiter = ',')]
        select_symbols: Vec<String>,
        #[arg(long, value_delimiter = ',')]
        report_symbols: Vec<String>,
    },
    Combo {
        #[arg(long, value_delimiter = ',')]
        components: Vec<String>,
    },
    DailyOffsetEnsemble {
        #[arg(long, default_value = "frama-5m-7offset-stacked-consensus")]
        name: String,
        #[arg(long, default_value = "frama-5m-confirm")]
        strategy_set: String,
        #[arg(
            long,
            value_delimiter = ',',
            default_value = "BTCUSDT,ETHUSDT,BNBUSDT,SOLUSDT,XRPUSDT,DOGEUSDT,SUIUSDT"
        )]
        symbols: Vec<String>,
        #[arg(
            long,
            value_delimiter = ',',
            default_value = "0,1,2,3,4,5,6",
            allow_hyphen_values = true
        )]
        offsets: Vec<i64>,
        #[arg(long, value_delimiter = ',')]
        run_ids: Vec<String>,
        #[arg(long, default_value_t = 500)]
        trials: usize,
        #[arg(long, default_value_t = 42)]
        seed: u64,
        #[arg(long, default_value_t = 0.15)]
        random_startup_fraction: f64,
        #[arg(long, default_value_t = 128)]
        ei_candidates: usize,
        #[arg(long)]
        batch_size: Option<usize>,
        #[arg(long, default_value = "memory")]
        storage: String,
        #[arg(long, default_value = "point_in_time_fold_local")]
        optimizer_mode: OptimizerMode,
        #[arg(long, default_value = "1.10")]
        min_profit_factor: Option<f64>,
        #[arg(long, default_value = "1.10")]
        candidate_min_profit_factor: Option<f64>,
        #[arg(long, default_value_t = 4)]
        tpe_consensus_min_passing_windows: usize,
        #[arg(long, default_value_t = 10_000.0)]
        account_balance: f64,
        #[arg(long)]
        fees_bps: Option<f64>,
        #[arg(long, default_value_t = 2)]
        is_weeks: i64,
        #[arg(long)]
        is_days: Option<i64>,
        #[arg(long, default_value_t = 1)]
        oos_weeks: i64,
        #[arg(long)]
        oos_days: Option<i64>,
        #[arg(long, default_value_t = 1)]
        step_weeks: i64,
        #[arg(long)]
        step_days: Option<i64>,
        #[arg(long, default_value_t = 0)]
        gap_weeks: i64,
        #[arg(long)]
        gap_days: Option<i64>,
        #[arg(long)]
        fold_start_index: Option<usize>,
        #[arg(long)]
        fold_limit: Option<usize>,
        #[arg(long)]
        rollup_only: bool,
        #[arg(long)]
        start_date: Option<String>,
        #[arg(long)]
        end_date: Option<String>,
    },
    FillModelExperiment {
        #[arg(long, default_value = "cayden_submit_20260627")]
        package_dir: PathBuf,
        #[arg(long, default_value_t = 1)]
        fold_start_index: usize,
        #[arg(long, default_value_t = 2)]
        fold_limit: usize,
        #[arg(long, value_delimiter = ',', allow_hyphen_values = true)]
        offsets: Vec<i64>,
    },
    PrefixDecay {
        #[arg(long)]
        manifest: String,
    },
    IsDailyScan {
        #[arg(long)]
        run_id: String,
        #[arg(long, value_delimiter = ',', allow_hyphen_values = true)]
        scan_offset_days: Vec<i64>,
        #[arg(long, default_value_t = 14)]
        min_profitable_days: usize,
        #[arg(long, default_value_t = 250)]
        top_rows: usize,
    },
    SpaceScan {
        #[arg(long, default_value = "strategy-4448")]
        strategy_set: String,
        #[arg(
            long,
            value_delimiter = ',',
            default_value = "BTCUSDT,ETHUSDT,SOLUSDT,XRPUSDT,SUIUSDT"
        )]
        symbols: Vec<String>,
        #[arg(long, default_value_t = 0)]
        fold_index: usize,
        #[arg(long, default_value_t = 0, allow_hyphen_values = true)]
        start_offset_days: i64,
        #[arg(long, default_value_t = 5120)]
        trials: usize,
        #[arg(long, default_value_t = 2)]
        is_weeks: i64,
        #[arg(long, default_value_t = 1)]
        oos_weeks: i64,
        #[arg(long, default_value_t = 1)]
        step_weeks: i64,
        #[arg(long, default_value_t = 0)]
        gap_weeks: i64,
    },
}

#[derive(Debug, Subcommand)]
enum DashboardCommand {
    Serve {
        #[arg(long, default_value_t = 7878)]
        port: u16,
    },
    RecordCheck {
        #[arg(long)]
        name: String,
        #[arg(long)]
        status: String,
        #[arg(long)]
        command: String,
        #[arg(long, default_value = "")]
        details: String,
    },
}

fn main() -> Result<()> {
    let cli = Cli::parse();
    match cli.command {
        Some(Command::Data { command }) => run_data_command(command),
        Some(Command::Wfo { command }) => run_wfo_command(command),
        Some(Command::Dashboard { command }) => run_dashboard_command(command),
        None => {
            print_ready_message();
            Ok(())
        }
    }
}

fn run_data_command(command: DataCommand) -> Result<()> {
    let store = KlineStore::from_env()?;
    match command {
        DataCommand::Sync {
            preset,
            start,
            end,
            force,
        } => {
            let symbols = preset_symbols(&preset)?;
            let start = parse_date(&start)?;
            let end = parse_date(&end)?;
            let report = store.sync_range(&symbols, start, end, force)?;
            println!(
                "sync complete: root={}, synced_months={}, skipped_months={}, rows_written={}, synthetic_rows={}",
                store.root().display(),
                report.synced_months,
                report.skipped_months,
                report.rows_written,
                report.synthetic_rows
            );
            Ok(())
        }
        DataCommand::Verify { preset, start, end } => {
            let symbols = preset_symbols(&preset)?;
            let start = parse_date(&start)?;
            let end = parse_date(&end)?;
            let summary = store.verify_range(&symbols, start, end)?;
            let total_rows: usize = summary.symbols.iter().map(|s| s.rows).sum();
            for symbol in &summary.symbols {
                println!(
                    "{}: rows={}/{} archive={} api_backfill={} synthetic={}",
                    symbol.symbol,
                    symbol.rows,
                    symbol.expected_rows,
                    symbol.archive_rows,
                    symbol.api_rows,
                    symbol.synthetic_rows
                );
            }
            println!(
                "verify complete: root={}, symbols={}, total_rows={}",
                store.root().display(),
                summary.symbols.len(),
                total_rows
            );
            Ok(())
        }
        DataCommand::Coverage => {
            println!("{}", store.root().join("_meta/coverage.json").display());
            Ok(())
        }
    }
}

fn run_wfo_command(command: WfoCommand) -> Result<()> {
    match command {
        WfoCommand::Run {
            grid,
            symbols,
            indicator_group,
            strategy_set,
            optimizer_mode,
            resume_run_id,
            min_profit_factor,
            candidate_min_profit_factor,
            account_balance,
            fees_bps,
            trials,
            random_startup_fraction,
            tpe_seed,
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
        } => {
            let grid = GridSize::parse(&grid)?;
            if grid == GridSize::Tpe && resume_run_id.is_none() {
                return run_optuna_python(
                    WfoRunOptions {
                        symbols,
                        indicator_group,
                        strategy_set,
                        optimizer_mode: Some(optimizer_mode),
                        resume_run_id: None,
                        min_profit_factor,
                        candidate_min_profit_factor,
                        account_balance,
                        fees_bps,
                        tpe_trials: trials,
                        tpe_random_startup_fraction: random_startup_fraction,
                        tpe_seed,
                        tpe_is_consensus_min_passing_windows: None,
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
                    },
                    128,
                    None,
                    "memory",
                );
            }
            let path = rust_trend::wfo::run_wfo_with_options(
                grid,
                WfoRunOptions {
                    symbols,
                    indicator_group,
                    strategy_set,
                    optimizer_mode: Some(optimizer_mode),
                    resume_run_id,
                    min_profit_factor,
                    candidate_min_profit_factor,
                    account_balance,
                    fees_bps,
                    tpe_trials: trials,
                    tpe_random_startup_fraction: random_startup_fraction,
                    tpe_seed,
                    tpe_is_consensus_min_passing_windows: None,
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
                },
            )?;
            println!("wfo run complete: {}", path.display());
            Ok(())
        }
        WfoCommand::OptunaRun {
            symbols,
            indicator_group,
            strategy_set,
            optimizer_mode,
            trials,
            seed,
            tpe_consensus_min_passing_windows,
            random_startup_fraction,
            ei_candidates,
            batch_size,
            storage,
            min_profit_factor,
            candidate_min_profit_factor,
            account_balance,
            fees_bps,
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
        } => run_optuna_python(
            WfoRunOptions {
                symbols,
                indicator_group,
                strategy_set,
                optimizer_mode: Some(optimizer_mode),
                resume_run_id: None,
                min_profit_factor,
                candidate_min_profit_factor,
                account_balance,
                fees_bps,
                tpe_trials: Some(trials),
                tpe_random_startup_fraction: Some(random_startup_fraction),
                tpe_seed: seed,
                tpe_is_consensus_min_passing_windows: tpe_consensus_min_passing_windows,
                is_weeks: Some(is_weeks),
                is_days,
                oos_weeks: Some(oos_weeks),
                oos_days,
                step_weeks: Some(step_weeks),
                step_days,
                gap_weeks: Some(gap_weeks),
                gap_days,
                start_offset_days: Some(start_offset_days),
                fold_start_index,
                fold_limit,
                start_date,
                end_date,
            },
            ei_candidates,
            batch_size,
            &storage,
        ),
        WfoCommand::Verify => {
            let path = rust_trend::wfo::verify_wfo()?;
            println!("wfo verify complete: {}", path.display());
            Ok(())
        }
        WfoCommand::SummaryPage { run_id } => {
            let path = rust_trend::wfo::write_run_summary_page(&run_id)?;
            println!("wfo summary page: {}", path.display());
            Ok(())
        }
        WfoCommand::Diagnose { run_id, pairs } => {
            let reports = rust_trend::wfo::diagnose_run_strategies(&run_id, &pairs)?;
            println!("{}", serde_json::to_string_pretty(&reports)?);
            Ok(())
        }
        WfoCommand::Stress {
            run_id,
            pairs,
            min_profit_factor,
        } => {
            let path = rust_trend::wfo::stress_validate_run(&run_id, &pairs, min_profit_factor)?;
            println!("wfo stress validation: {}", path.display());
            Ok(())
        }
        WfoCommand::Ecc {
            run_id,
            pairs,
            select_symbols,
            report_symbols,
        } => {
            let path = rust_trend::wfo::equity_control_validate_run(
                &run_id,
                &pairs,
                &select_symbols,
                &report_symbols,
            )?;
            println!("wfo equity control validation: {}", path.display());
            Ok(())
        }
        WfoCommand::Combo { components } => {
            let path = rust_trend::wfo::combine_strategy_components(&components)?;
            println!("wfo portfolio combo: {}", path.display());
            Ok(())
        }
        WfoCommand::DailyOffsetEnsemble {
            name,
            strategy_set,
            symbols,
            offsets,
            run_ids,
            trials,
            seed,
            random_startup_fraction,
            ei_candidates,
            batch_size,
            storage,
            optimizer_mode,
            min_profit_factor,
            candidate_min_profit_factor,
            tpe_consensus_min_passing_windows,
            account_balance,
            fees_bps,
            is_weeks,
            is_days,
            oos_weeks,
            oos_days,
            step_weeks,
            step_days,
            gap_weeks,
            gap_days,
            fold_start_index,
            fold_limit,
            rollup_only,
            start_date,
            end_date,
        } => {
            let path = run_daily_offset_ensemble_command(DailyOffsetEnsembleCliOptions {
                name,
                strategy_set,
                symbols,
                offsets,
                run_ids,
                trials,
                seed,
                random_startup_fraction,
                ei_candidates,
                batch_size,
                storage,
                optimizer_mode,
                min_profit_factor,
                candidate_min_profit_factor,
                tpe_consensus_min_passing_windows,
                account_balance,
                fees_bps,
                is_weeks,
                is_days,
                oos_weeks,
                oos_days,
                step_weeks,
                step_days,
                gap_weeks,
                gap_days,
                fold_start_index,
                fold_limit,
                rollup_only,
                start_date,
                end_date,
            })?;
            println!("wfo daily-offset ensemble: {}", path.display());
            Ok(())
        }
        WfoCommand::FillModelExperiment {
            package_dir,
            fold_start_index,
            fold_limit,
            offsets,
        } => {
            let path =
                rust_trend::wfo::run_fill_model_experiment(FillModelExperimentOptions {
                    package_dir,
                    fold_start_index,
                    fold_limit,
                    offsets,
                })?;
            println!("wfo fill-model experiment: {}", path.display());
            Ok(())
        }
        WfoCommand::PrefixDecay { manifest } => {
            let path = rust_trend::wfo::write_oos_prefix_decay_report(&manifest)?;
            println!("wfo prefix decay report: {}", path.display());
            Ok(())
        }
        WfoCommand::IsDailyScan {
            run_id,
            scan_offset_days,
            min_profitable_days,
            top_rows,
        } => {
            let path = rust_trend::wfo::scan_is_daily_profit(
                &run_id,
                &scan_offset_days,
                min_profitable_days,
                top_rows,
            )?;
            println!("wfo IS daily-profit scan: {}", path.display());
            Ok(())
        }
        WfoCommand::SpaceScan {
            strategy_set,
            symbols,
            fold_index,
            start_offset_days,
            trials,
            is_weeks,
            oos_weeks,
            step_weeks,
            gap_weeks,
        } => {
            let path =
                rust_trend::wfo::run_strategy_space_scan(rust_trend::wfo::SpaceScanOptions {
                    strategy_set,
                    symbols,
                    fold_index,
                    start_offset_days,
                    trials,
                    is_weeks,
                    oos_weeks,
                    step_weeks,
                    gap_weeks,
                })?;
            println!("wfo space scan: {}", path.display());
            Ok(())
        }
    }
}

struct DailyOffsetEnsembleCliOptions {
    name: String,
    strategy_set: String,
    symbols: Vec<String>,
    offsets: Vec<i64>,
    run_ids: Vec<String>,
    trials: usize,
    seed: u64,
    random_startup_fraction: f64,
    ei_candidates: usize,
    batch_size: Option<usize>,
    storage: String,
    optimizer_mode: OptimizerMode,
    min_profit_factor: Option<f64>,
    candidate_min_profit_factor: Option<f64>,
    tpe_consensus_min_passing_windows: usize,
    account_balance: f64,
    fees_bps: Option<f64>,
    is_weeks: i64,
    is_days: Option<i64>,
    oos_weeks: i64,
    oos_days: Option<i64>,
    step_weeks: i64,
    step_days: Option<i64>,
    gap_weeks: i64,
    gap_days: Option<i64>,
    fold_start_index: Option<usize>,
    fold_limit: Option<usize>,
    rollup_only: bool,
    start_date: Option<String>,
    end_date: Option<String>,
}

fn run_daily_offset_ensemble_command(options: DailyOffsetEnsembleCliOptions) -> Result<PathBuf> {
    if options.offsets.is_empty() {
        anyhow::bail!("daily-offset ensemble requires at least one --offsets value");
    }
    let mut run_ids = parse_daily_offset_run_ids(&options.offsets, &options.run_ids)?;
    for offset in &options.offsets {
        if run_ids.iter().any(|run| run.offset_days == *offset) {
            continue;
        }
        if options.rollup_only {
            anyhow::bail!("missing run id for offset {offset}; remove --rollup-only to run it");
        }
        let run_path = run_optuna_python_capture(
            WfoRunOptions {
                symbols: options.symbols.clone(),
                indicator_group: None,
                strategy_set: Some(options.strategy_set.clone()),
                optimizer_mode: Some(options.optimizer_mode),
                resume_run_id: None,
                min_profit_factor: options.min_profit_factor,
                candidate_min_profit_factor: options.candidate_min_profit_factor,
                account_balance: Some(options.account_balance),
                fees_bps: options.fees_bps,
                tpe_trials: Some(options.trials),
                tpe_random_startup_fraction: Some(options.random_startup_fraction),
                tpe_seed: Some(options.seed),
                tpe_is_consensus_min_passing_windows: Some(
                    options.tpe_consensus_min_passing_windows,
                ),
                is_weeks: Some(options.is_weeks),
                is_days: options.is_days,
                oos_weeks: Some(options.oos_weeks),
                oos_days: options.oos_days,
                step_weeks: Some(options.step_weeks),
                step_days: options.step_days,
                gap_weeks: Some(options.gap_weeks),
                gap_days: options.gap_days,
                start_offset_days: Some(*offset),
                fold_start_index: options.fold_start_index,
                fold_limit: options.fold_limit,
                start_date: options.start_date.clone(),
                end_date: options.end_date.clone(),
            },
            options.ei_candidates,
            options.batch_size,
            &options.storage,
        )?;
        let run_id = run_path
            .file_name()
            .and_then(|value| value.to_str())
            .with_context(|| format!("invalid WFO run path {}", run_path.display()))?
            .to_string();
        run_ids.push(DailyOffsetRunSpec {
            offset_days: *offset,
            run_id,
        });
    }
    run_ids.sort_by_key(|run| run.offset_days);
    rust_trend::wfo::write_daily_offset_ensemble_rollup(DailyOffsetEnsembleOptions {
        name: options.name,
        offset_runs: run_ids,
        account_balance: options.account_balance,
    })
}

fn parse_daily_offset_run_ids(
    offsets: &[i64],
    values: &[String],
) -> Result<Vec<DailyOffsetRunSpec>> {
    let mut out = Vec::new();
    for (index, value) in values.iter().enumerate() {
        if let Some((offset, run_id)) = value.split_once('=') {
            out.push(DailyOffsetRunSpec {
                offset_days: offset.parse::<i64>().with_context(|| {
                    format!("invalid offset in --run-ids value {value}; use offset=run_id")
                })?,
                run_id: run_id.to_string(),
            });
        } else {
            let offset_days = offsets.get(index).copied().with_context(|| {
                format!("run id {value} has no matching offset; use offset=run_id")
            })?;
            out.push(DailyOffsetRunSpec {
                offset_days,
                run_id: value.to_string(),
            });
        }
    }
    Ok(out)
}

fn run_optuna_python(
    options: WfoRunOptions,
    ei_candidates: usize,
    batch_size: Option<usize>,
    storage: &str,
) -> Result<()> {
    let mut command = build_optuna_python_command(options, ei_candidates, batch_size, storage);
    let status = command.status()?;
    if !status.success() {
        anyhow::bail!("Optuna WFO runner exited with status {status}");
    }
    Ok(())
}

fn run_optuna_python_capture(
    options: WfoRunOptions,
    ei_candidates: usize,
    batch_size: Option<usize>,
    storage: &str,
) -> Result<PathBuf> {
    let output =
        build_optuna_python_command(options, ei_candidates, batch_size, storage).output()?;
    let stdout = String::from_utf8_lossy(&output.stdout);
    let stderr = String::from_utf8_lossy(&output.stderr);
    if !stdout.trim().is_empty() {
        print!("{stdout}");
    }
    if !stderr.trim().is_empty() {
        eprint!("{stderr}");
    }
    if !output.status.success() {
        anyhow::bail!("Optuna WFO runner exited with status {}", output.status);
    }
    stdout
        .lines()
        .rev()
        .find_map(|line| line.strip_prefix("wfo run complete: "))
        .map(PathBuf::from)
        .context("Optuna WFO runner did not print final run path")
}

fn build_optuna_python_command(
    options: WfoRunOptions,
    ei_candidates: usize,
    batch_size: Option<usize>,
    storage: &str,
) -> ProcessCommand {
    let trials = options.tpe_trials.unwrap_or(150);
    let random_startup_fraction = options.tpe_random_startup_fraction.unwrap_or(0.15);
    let mut command = ProcessCommand::new("uv");
    command
        .arg("run")
        .arg("python")
        .arg("-m")
        .arg("rust_trend_optuna")
        .arg("run")
        .arg("--trials")
        .arg(trials.to_string())
        .arg("--random-startup-fraction")
        .arg(random_startup_fraction.to_string())
        .arg("--ei-candidates")
        .arg(ei_candidates.to_string())
        .arg("--storage")
        .arg(storage)
        .arg("--optimizer-mode")
        .arg(
            options
                .optimizer_mode
                .unwrap_or(OptimizerMode::PointInTimeFoldLocal)
                .as_str(),
        )
        .arg("--is-weeks")
        .arg(options.is_weeks.unwrap_or(2).to_string())
        .arg("--oos-weeks")
        .arg(options.oos_weeks.unwrap_or(1).to_string())
        .arg("--step-weeks")
        .arg(options.step_weeks.unwrap_or(1).to_string())
        .arg("--gap-weeks")
        .arg(options.gap_weeks.unwrap_or(0).to_string())
        .arg("--start-offset-days")
        .arg(options.start_offset_days.unwrap_or(0).to_string());
    if !options.symbols.is_empty() {
        command.arg("--symbols").arg(options.symbols.join(","));
    }
    if let Some(value) = options.indicator_group {
        command.arg("--indicator-group").arg(value);
    }
    if let Some(value) = options.strategy_set {
        command.arg("--strategy-set").arg(value);
    }
    if let Some(value) = options.tpe_seed {
        command.arg("--seed").arg(value.to_string());
    }
    if let Some(value) = options.tpe_is_consensus_min_passing_windows {
        command
            .arg("--tpe-consensus-min-passing-windows")
            .arg(value.to_string());
    }
    if let Some(value) = batch_size {
        command.arg("--batch-size").arg(value.to_string());
    }
    if let Some(value) = options.min_profit_factor {
        command.arg("--min-profit-factor").arg(value.to_string());
    }
    if let Some(value) = options.candidate_min_profit_factor {
        command
            .arg("--candidate-min-profit-factor")
            .arg(value.to_string());
    }
    if let Some(value) = options.account_balance {
        command.arg("--account-balance").arg(value.to_string());
    }
    if let Some(value) = options.fees_bps {
        command.arg("--fees-bps").arg(value.to_string());
    }
    if let Some(value) = options.is_days {
        command.arg("--is-days").arg(value.to_string());
    }
    if let Some(value) = options.oos_days {
        command.arg("--oos-days").arg(value.to_string());
    }
    if let Some(value) = options.step_days {
        command.arg("--step-days").arg(value.to_string());
    }
    if let Some(value) = options.gap_days {
        command.arg("--gap-days").arg(value.to_string());
    }
    if let Some(value) = options.fold_start_index {
        command.arg("--fold-start-index").arg(value.to_string());
    }
    if let Some(value) = options.fold_limit {
        command.arg("--fold-limit").arg(value.to_string());
    }
    if let Some(value) = options.start_date {
        command.arg("--start-date").arg(value);
    }
    if let Some(value) = options.end_date {
        command.arg("--end-date").arg(value);
    }
    command
}

fn run_dashboard_command(command: DashboardCommand) -> Result<()> {
    match command {
        DashboardCommand::Serve { port } => rust_trend::dashboard::serve(port),
        DashboardCommand::RecordCheck {
            name,
            status,
            command,
            details,
        } => {
            rust_trend::wfo::record_check(&name, &status, &command, &details)?;
            println!("recorded dashboard check: {name}={status}");
            Ok(())
        }
    }
}

fn print_ready_message() {
    let result = run_backtest(&[], BacktestConfig::default());

    println!(
        "rust_trend ready: starting_equity={:.2}, ending_equity={:.2}, points={}",
        result.starting_equity,
        result.ending_equity,
        result.equity_curve.len()
    );
}
