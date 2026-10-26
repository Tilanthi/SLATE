from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import statistics
import time
from collections import Counter
from pathlib import Path
from typing import Any

import optuna

from ._rust import WfoEvaluator


DEFAULT_SYMBOLS = ""
MIN_EXIT_STOP_ATR_MULTIPLE = 0.50
MAX_EXIT_STOP_ATR_MULTIPLE = 5.00
MIN_EXIT_TARGET_ATR_MULTIPLE = 0.50
TPE_MIN_TARGET_ATR_MULTIPLE = 0.75
MAX_EXIT_TARGET_ATR_MULTIPLE = 12.00
MAX_EXIT_TARGET_STOP_RATIO = 4.00
TPE_MIN_LOOKBACK_BARS = 4
TPE_MAX_LOOKBACK_BARS = 240
TPE_MIN_ATR_BARS = 20
TPE_MAX_ATR_BARS = 200
TPE_ATR_STEP_BARS = 5
TPE_MAX_TIME_STOP_BARS = 288
TPE_MAX_ENTRY_ATR_MULTIPLE = 1.50


def split_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [part.strip() for part in value.split(",") if part.strip()]


def build_options(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "symbols": split_csv(args.symbols),
        "indicator_group": args.indicator_group,
        "strategy_set": args.strategy_set,
        "optimizer_mode": args.optimizer_mode,
        "resume_run_id": None,
        "min_profit_factor": args.min_profit_factor,
        "candidate_min_profit_factor": args.candidate_min_profit_factor,
        "account_balance": args.account_balance,
        "fees_bps": args.fees_bps,
        "tpe_trials": args.trials,
        "tpe_random_startup_fraction": args.random_startup_fraction,
        "tpe_seed": args.seed,
        "tpe_is_consensus_min_passing_windows": args.tpe_consensus_min_passing_windows,
        "is_weeks": args.is_weeks,
        "is_days": args.is_days,
        "oos_weeks": args.oos_weeks,
        "oos_days": args.oos_days,
        "step_weeks": args.step_weeks,
        "step_days": args.step_days,
        "gap_weeks": args.gap_weeks,
        "gap_days": args.gap_days,
        "start_offset_days": args.start_offset_days,
        "fold_start_index": args.fold_start_index,
        "fold_limit": args.fold_limit,
        "start_date": getattr(args, "start_date", None),
        "end_date": getattr(args, "end_date", None),
    }


def suggest_params(trial: optuna.trial.Trial, indicator: str, timeframe: str) -> dict[str, Any]:
    if indicator == "strategy_4448_kama_ker":
        kama1_fast = trial.suggest_int("strategy_4448_kama1_fast", 2, 120)
        kama1_span = trial.suggest_int("strategy_4448_kama1_span", 1, 158)
        kama1_slow = min(160, kama1_fast + kama1_span)
        if kama1_slow <= kama1_fast:
            kama1_fast = max(2, kama1_slow - 1)
        kama2_fast = trial.suggest_int("strategy_4448_kama2_fast", 2, 30)
        kama2_span = trial.suggest_int("strategy_4448_kama2_span", 1, 158)
        kama2_slow = min(160, kama2_fast + kama2_span)
        if kama2_slow <= kama2_fast:
            kama2_fast = max(2, kama2_slow - 1)
        stop_atr_multiple = trial.suggest_float(
            "strategy_4448_stop_atr_multiple",
            MIN_EXIT_STOP_ATR_MULTIPLE,
            MAX_EXIT_STOP_ATR_MULTIPLE,
        )
        target_upper = min(
            MAX_EXIT_TARGET_ATR_MULTIPLE,
            stop_atr_multiple * MAX_EXIT_TARGET_STOP_RATIO,
        )
        return {
            "strategy_4448_lookback": trial.suggest_int("strategy_4448_lookback", 5, 120),
            "strategy_4448_atr_period": trial.suggest_int("strategy_4448_atr_period", 20, 200, step=5),
            "strategy_4448_stop_atr_multiple": stop_atr_multiple,
            "strategy_4448_target_atr_multiple": trial.suggest_float(
                "strategy_4448_target_atr_multiple", 2.00, target_upper
            ),
            "strategy_4448_kama1_er": trial.suggest_int("strategy_4448_kama1_er", 5, 120),
            "strategy_4448_kama1_short": kama1_fast,
            "strategy_4448_kama1_long": kama1_slow,
            "strategy_4448_kama2_er": trial.suggest_int("strategy_4448_kama2_er", 5, 60),
            "strategy_4448_kama2_short": kama2_fast,
            "strategy_4448_kama2_long": kama2_slow,
            "strategy_4448_count_bars": trial.suggest_int("strategy_4448_count_bars", 3, 15),
        }
    if indicator in {"strategy_336_kama_tpo", "strategy_3635_kama_tpo", "strategy_3938_kama_tpo"}:
        return {}
    stop_atr_multiple = trial.suggest_float(
        "stop_atr_multiple", MIN_EXIT_STOP_ATR_MULTIPLE, MAX_EXIT_STOP_ATR_MULTIPLE
    )
    target_upper = min(
        MAX_EXIT_TARGET_ATR_MULTIPLE,
        stop_atr_multiple * MAX_EXIT_TARGET_STOP_RATIO,
    )
    return {
        "signal_polarity": trial.suggest_categorical("signal_polarity", [-1, 1]),
        "entry_mode": trial.suggest_categorical("entry_mode", ["pullback", "breakout"]),
        "lookback_bars": trial.suggest_int("lookback_bars", TPE_MIN_LOOKBACK_BARS, TPE_MAX_LOOKBACK_BARS),
        "atr_bars": trial.suggest_int(
            "atr_bars", TPE_MIN_ATR_BARS, TPE_MAX_ATR_BARS, step=TPE_ATR_STEP_BARS
        ),
        "entry_atr_multiple": trial.suggest_float("entry_atr_multiple", 0.0, TPE_MAX_ENTRY_ATR_MULTIPLE),
        "stop_atr_multiple": stop_atr_multiple,
        "target_atr_multiple": trial.suggest_float(
            "target_atr_multiple", TPE_MIN_TARGET_ATR_MULTIPLE, target_upper
        ),
        "time_stop_bars": trial.suggest_int("time_stop_bars", 0, TPE_MAX_TIME_STOP_BARS),
        "hurst_min": trial.suggest_float("hurst_min", -0.25, 0.65),
        "hurst_max": trial.suggest_float("hurst_max", 0.45, 1.25),
        "shannon_max": trial.suggest_float("shannon_max", 0.75, 1.25),
    }


def constraints_func(trial: optuna.trial.FrozenTrial) -> list[float]:
    value = trial.user_attrs.get("constraints")
    if isinstance(value, list) and value:
        return [float(item) for item in value]
    return [0.0, 0.0]


def study_storage(storage: str, run_dir: Path, study_name: str) -> Any:
    if storage == "memory":
        return None
    if storage == "journal":
        backend = optuna.storages.journal.JournalFileBackend(
            str(run_dir / f"{study_name}.journal.log")
        )
        return optuna.storages.JournalStorage(backend)
    return storage


def fold_study_seed(
    base_seed: int | None,
    offset_days: int,
    indicator: str,
    timeframe: str,
    fold_index: int,
) -> int:
    payload = f"{base_seed or 0}:{offset_days}:{indicator}:{timeframe}:{fold_index}".encode()
    return int.from_bytes(hashlib.sha256(payload).digest()[:4], "big")


def fold_study_name(
    indicator: str,
    timeframe: str,
    offset_days: int,
    fold_index: int,
    seed: int,
) -> str:
    offset_label = str(offset_days).replace("-", "m")
    return f"{indicator}__{timeframe}__offset_{offset_label}__fold_{fold_index}__seed_{seed}"


def create_study(
    args: argparse.Namespace,
    run_dir: Path,
    study_name: str,
    seed: int | None,
    trials: int,
) -> optuna.Study:
    trials = max(1, int(trials))
    startup = max(1, min(trials, math.ceil(trials * args.random_startup_fraction)))
    sampler = optuna.samplers.TPESampler(
        seed=seed,
        n_startup_trials=startup,
        n_ei_candidates=args.ei_candidates,
        multivariate=True,
        group=True,
        constant_liar=True,
        constraints_func=constraints_func,
    )
    storage = study_storage(args.storage, run_dir, study_name)
    return optuna.create_study(
        direction="maximize",
        sampler=sampler,
        storage=storage,
        study_name=study_name,
        load_if_exists=False,
    )


def write_sampler_health(run_dir: Path, run_id: str, rows: list[dict[str, Any]]) -> None:
    path = run_dir / "sampler_health.json"
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps({"run_id": run_id, "groups": rows}, indent=2) + "\n")
    tmp.replace(path)


def best_at_checkpoint(objectives: list[float], count: int) -> float | None:
    if not objectives or count <= 0:
        return None
    return max(objectives[: min(count, len(objectives))])


def objective_improvement_count(objectives: list[float]) -> int:
    best = -math.inf
    improvements = 0
    for value in objectives:
        if value > best:
            improvements += 1
            best = value
    return improvements


def median_numeric_params(params: list[dict[str, Any]]) -> dict[str, float]:
    if not params:
        return {}
    keys = sorted({key for row in params for key, value in row.items() if isinstance(value, (int, float))})
    medians: dict[str, float] = {}
    for key in keys:
        values = [float(row[key]) for row in params if isinstance(row.get(key), (int, float))]
        if values:
            medians[key] = statistics.median(values)
    return medians


def health_row(
    group: dict[str, Any],
    elapsed: float,
    signatures: list[str],
    objectives: list[float],
    best_seen_trial: int | None,
    params: list[dict[str, Any]],
    startup_trials: int,
) -> dict[str, Any]:
    counts = Counter(signatures)
    last_quarter = signatures[max(0, len(signatures) * 3 // 4) :]
    unique_last_quarter = len(set(last_quarter))
    objective_counts = Counter(round(value, 9) for value in objectives)
    first_half = params[: len(params) // 2]
    second_half = params[len(params) // 2 :]
    checkpoints = {
        "startup": best_at_checkpoint(objectives, startup_trials),
        "25_pct": best_at_checkpoint(objectives, max(1, math.ceil(len(objectives) * 0.25))),
        "50_pct": best_at_checkpoint(objectives, max(1, math.ceil(len(objectives) * 0.50))),
        "75_pct": best_at_checkpoint(objectives, max(1, math.ceil(len(objectives) * 0.75))),
        "100_pct": best_at_checkpoint(objectives, len(objectives)),
    }
    return {
        "indicator": group["indicator"],
        "timeframe": group["timeframe"],
        "trials": group["trials"],
        "elapsed_seconds": elapsed,
        "trials_per_second": len(signatures) / elapsed if elapsed > 0 else 0.0,
        "unique_params": len(counts),
        "unique_param_ratio": len(counts) / len(signatures) if signatures else 0.0,
        "last_quarter_unique_params": unique_last_quarter,
        "last_quarter_unique_param_ratio": unique_last_quarter / len(last_quarter)
        if last_quarter
        else 0.0,
        "top_duplicate_count": counts.most_common(1)[0][1] if counts else 0,
        "best_seen_trial": best_seen_trial,
        "best_objective": max(objectives) if objectives else None,
        "median_objective": statistics.median(objectives) if objectives else None,
        "distinct_objectives": len(objective_counts),
        "distinct_objective_ratio": len(objective_counts) / len(objectives) if objectives else 0.0,
        "hard_invalid_objectives": sum(1 for value in objectives if value <= -999.0),
        "positive_objectives": sum(1 for value in objectives if value > 0.0),
        "best_improvement_count": objective_improvement_count(objectives),
        "best_at": checkpoints,
        "first_half_param_medians": median_numeric_params(first_half),
        "second_half_param_medians": median_numeric_params(second_half),
    }


def tell_trial(study: optuna.Study, trial: optuna.trial.Trial, result: dict[str, Any]) -> None:
    constraints = [float(value) for value in result.get("constraints", [0.0, 0.0])]
    trial.set_user_attr("constraints", constraints)
    trial.set_user_attr("candidate_id", result["candidate_id"])
    trial.set_user_attr("params_signature", result["params_signature"])
    trial.set_user_attr("validation_trades", result["validation_trades"])
    trial.set_user_attr("validation_profit_factor", result["validation_profit_factor"])
    trial.set_user_attr("validation_net_return_pct", result["validation_net_return_pct"])
    trial.set_user_attr("max_timestamp_seen", result.get("max_timestamp_seen", 0))
    if result.get("fold_index") is not None:
        trial.set_user_attr("fold_index", result["fold_index"])
    trial.set_user_attr(
        "validation_eligible_fraction",
        result["validation_eligible_fraction"],
    )
    trial.set_user_attr(
        "validation_net_positive_fraction",
        result["validation_net_positive_fraction"],
    )
    trial.set_user_attr(
        "validation_median_profit_factor",
        result["validation_median_profit_factor"],
    )
    trial.set_user_attr("validation_q25_score", result["validation_q25_score"])
    trial.set_user_attr(
        "validation_median_score",
        result["validation_median_score"],
    )
    trial.set_user_attr(
        "validation_nonnegative_score_fraction",
        result.get("validation_nonnegative_score_fraction", 0.0),
    )
    trial.set_user_attr(
        "average_trade_penalty",
        result.get("average_trade_penalty", 0.0),
    )
    trial.set_user_attr(
        "average_profit_factor_penalty",
        result.get("average_profit_factor_penalty", 0.0),
    )
    trial.set_user_attr("average_net_penalty", result.get("average_net_penalty", 0.0))
    trial.set_user_attr("average_fill_penalty", result.get("average_fill_penalty", 0.0))
    trial.set_user_attr(
        "average_participation_penalty",
        result.get("average_participation_penalty", 0.0),
    )
    trial.set_user_attr("dispersion_penalty", result["dispersion_penalty"])
    study.tell(trial, float(result["objective_score"]))


def run(args: argparse.Namespace) -> int:
    evaluator = WfoEvaluator(json.dumps(build_options(args)))
    run_id = evaluator.run_id()
    run_dir = Path(evaluator.run_dir())
    config = json.loads(evaluator.config_json())
    groups = json.loads(evaluator.groups_json())
    folds = json.loads(evaluator.folds_json())
    health_rows: list[dict[str, Any]] = []
    print(f"optuna wfo run: {run_id}", flush=True)
    print(f"run dir: {run_dir}", flush=True)
    if args.optimizer_mode == "retrospective_global_research_only":
        print("WARNING: retrospective_global_research_only mode is research-only, not clean OOS validation", flush=True)
        for group in groups:
            if group["status"] == "complete":
                continue
            indicator = group["indicator"]
            timeframe = group["timeframe"]
            trials = int(group["trials"])
            evaluator.start_group(indicator, timeframe)
            study_name = f"{indicator}__{timeframe}__{args.seed or 'noseed'}__research_only"
            study = create_study(args, run_dir, study_name, args.seed, trials)
            signatures: list[str] = []
            objectives: list[float] = []
            sampled_params: list[dict[str, Any]] = []
            best_seen_trial: int | None = None
            group_started = time.monotonic()
            startup_trials = max(1, min(trials, math.ceil(trials * args.random_startup_fraction)))
            for offset in range(0, trials, args.batch_size):
                current_batch_size = min(args.batch_size, trials - offset)
                trial_objects: list[optuna.trial.Trial] = []
                payload: list[dict[str, Any]] = []
                for index in range(current_batch_size):
                    trial = study.ask()
                    params = suggest_params(trial, indicator, timeframe)
                    trial_objects.append(trial)
                    payload.append({"trial_index": offset + index + 1, "params": params})
                    sampled_params.append(params)
                results = json.loads(
                    evaluator.evaluate_batch_json(indicator, timeframe, json.dumps(payload))
                )
                for trial, result in zip(trial_objects, results, strict=True):
                    tell_trial(study, trial, result)
                    signatures.append(result["params_signature"])
                    value = float(result["objective_score"])
                    objectives.append(value)
                    if value >= max(objectives):
                        best_seen_trial = len(objectives)
                health_rows = [
                    row
                    for row in health_rows
                    if not (row["indicator"] == indicator and row["timeframe"] == timeframe)
                ]
                health_rows.append(
                    health_row(
                        group,
                        time.monotonic() - group_started,
                        signatures,
                        objectives,
                        best_seen_trial,
                        sampled_params,
                        startup_trials,
                    )
                )
                write_sampler_health(run_dir, run_id, health_rows)
            evaluator.complete_group(indicator, timeframe)
            print(
                f"complete {indicator} {timeframe}: "
                f"{len(signatures)} trials, {len(set(signatures))} unique params",
                flush=True,
            )
    else:
        offset_days = int(config.get("start_offset_days") or 0)
        for group in groups:
            if group["status"] == "complete":
                continue
            indicator = group["indicator"]
            timeframe = group["timeframe"]
            trials = int(group["trials"])
            evaluator.start_group(indicator, timeframe)
            for fold in folds:
                fold_index = int(fold["index"])
                seed = fold_study_seed(args.seed, offset_days, indicator, timeframe, fold_index)
                study_name = fold_study_name(indicator, timeframe, offset_days, fold_index, seed)
                evaluator.start_fold_group(indicator, timeframe, fold_index, study_name, seed, trials)
                study = create_study(args, run_dir, study_name, seed, trials)
                signatures = []
                objectives = []
                sampled_params = []
                best_seen_trial = None
                fold_started = time.monotonic()
                startup_trials = max(1, min(trials, math.ceil(trials * args.random_startup_fraction)))
                for offset in range(0, trials, args.batch_size):
                    current_batch_size = min(args.batch_size, trials - offset)
                    trial_objects = []
                    payload = []
                    for index in range(current_batch_size):
                        trial = study.ask()
                        params = suggest_params(trial, indicator, timeframe)
                        trial_objects.append(trial)
                        payload.append({"trial_index": offset + index + 1, "params": params})
                        sampled_params.append(params)
                    results = json.loads(
                        evaluator.evaluate_fold_batch_json(
                            indicator,
                            timeframe,
                            fold_index,
                            json.dumps(payload),
                        )
                    )
                    for trial, result in zip(trial_objects, results, strict=True):
                        tell_trial(study, trial, result)
                        signatures.append(result["params_signature"])
                        value = float(result["objective_score"])
                        objectives.append(value)
                        if value >= max(objectives):
                            best_seen_trial = len(objectives)
                    health_rows = [
                        row
                        for row in health_rows
                        if not (
                            row["indicator"] == indicator
                            and row["timeframe"] == timeframe
                            and row.get("fold_index") == fold_index
                        )
                    ]
                    row = health_row(
                        group,
                        time.monotonic() - fold_started,
                        signatures,
                        objectives,
                        best_seen_trial,
                        sampled_params,
                        startup_trials,
                    )
                    row["fold_index"] = fold_index
                    row["study_name"] = study_name
                    row["seed"] = seed
                    health_rows.append(row)
                    write_sampler_health(run_dir, run_id, health_rows)
                evaluator.complete_fold_group(indicator, timeframe, fold_index)
                print(
                    f"complete {indicator} {timeframe} fold {fold_index}: "
                    f"{len(signatures)} trials, {len(set(signatures))} unique params",
                    flush=True,
                )
            evaluator.complete_group(indicator, timeframe)
    final_dir = evaluator.finalize()
    write_sampler_health(run_dir, run_id, health_rows)
    print(f"wfo run complete: {final_dir}", flush=True)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="rust-trend-optuna")
    subcommands = parser.add_subparsers(dest="command", required=True)
    run_parser = subcommands.add_parser("run")
    run_parser.add_argument("--symbols", default=DEFAULT_SYMBOLS)
    run_parser.add_argument("--indicator-group")
    run_parser.add_argument("--strategy-set")
    run_parser.add_argument("--trials", type=int, default=150)
    run_parser.add_argument("--seed", type=int)
    run_parser.add_argument("--tpe-consensus-min-passing-windows", type=int)
    run_parser.add_argument("--random-startup-fraction", type=float, default=0.15)
    run_parser.add_argument("--ei-candidates", type=int, default=128)
    run_parser.add_argument("--batch-size", type=int, default=max(1, (os.cpu_count() or 4) // 2))
    run_parser.add_argument("--storage", default="memory")
    run_parser.add_argument(
        "--optimizer-mode",
        default="point_in_time_fold_local",
        choices=["point_in_time_fold_local", "retrospective_global_research_only"],
    )
    run_parser.add_argument("--min-profit-factor", type=float)
    run_parser.add_argument("--candidate-min-profit-factor", type=float)
    run_parser.add_argument("--account-balance", type=float)
    run_parser.add_argument("--fees-bps", type=float)
    run_parser.add_argument("--is-weeks", type=int, default=2)
    run_parser.add_argument("--is-days", type=int)
    run_parser.add_argument("--oos-weeks", type=int, default=1)
    run_parser.add_argument("--oos-days", type=int)
    run_parser.add_argument("--step-weeks", type=int, default=1)
    run_parser.add_argument("--step-days", type=int)
    run_parser.add_argument("--gap-weeks", type=int, default=0)
    run_parser.add_argument("--gap-days", type=int)
    run_parser.add_argument("--start-offset-days", type=int, default=0)
    run_parser.add_argument("--fold-start-index", type=int)
    run_parser.add_argument("--fold-limit", type=int)
    run_parser.add_argument("--start-date")
    run_parser.add_argument("--end-date")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "run":
        return run(args)
    parser.error(f"unknown command {args.command}")
    return 2
