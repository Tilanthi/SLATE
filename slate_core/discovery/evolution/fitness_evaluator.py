"""Overfit-resistant fitness evaluator for SLATE evolution (Phase 0).

Implemented across Tasks 0.2-0.4. Public surface (added incrementally):
    FitnessConfig
    check_signal_correctness(signal_fn, df, parameters) -> (ok, reason)
    split_is_oos(df, is_fraction) -> (df_is, df_oos)
    run_backtest(signal_fn, parameters, df, edge_type, seed) -> dict
    FitnessResult
    evaluate_fitness(signal_fn, parameters, df, edge_type, config, candidate_id)
        -> FitnessResult
"""
