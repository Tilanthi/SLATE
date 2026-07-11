"""Tests for the Phase 4 signal sandbox (evolution/signal_sandbox.py).

The sandbox compiles LLM-proposed signal code only after AST validation and
inside a restricted namespace, and clamps output to {-1,0,1}.
"""
import pandas as pd
import pytest

from slate_core.discovery.evolution.signal_sandbox import (
    compile_signal, safe_eval_signal,
)


_BENIGN = (
    "def signal_fn(df, i, params):\n"
    "    close = df['close'].iloc[i]\n"
    "    prev = df['close'].iloc[i - 1]\n"
    "    return 1 if close > prev else -1\n"
)


def _df():
    return pd.DataFrame({"close": [1.0, 2.0, 1.5, 3.0, 2.0]})


def test_compile_signal_runs_benign_stub():
    fn = compile_signal(_BENIGN)
    df = _df()
    assert fn(df, 1, {}) == 1     # 2.0 > 1.0
    assert fn(df, 2, {}) == -1    # 1.5 < 2.0


def test_compile_signal_rejects_import():
    with pytest.raises(ValueError):
        compile_signal("import os\ndef signal_fn(df,i,params):\n    return 0\n")


def test_compile_signal_rejects_dunder_attribute():
    with pytest.raises(ValueError):
        compile_signal("def signal_fn(df,i,params):\n    return df.__class__\n")


def test_compile_signal_rejects_open_call():
    with pytest.raises(ValueError):
        compile_signal("def signal_fn(df,i,params):\n    open('/etc/passwd')\n    return 0\n")


def test_compile_signal_clamps_output():
    fn = compile_signal("def signal_fn(df,i,params):\n    return 5\n")
    assert fn(None, 0, {}) == 1
    fn2 = compile_signal("def signal_fn(df,i,params):\n    return -9\n")
    assert fn2(None, 0, {}) == -1
    fn3 = compile_signal("def signal_fn(df,i,params):\n    return 0\n")
    assert fn3(None, 0, {}) == 0


def test_safe_eval_signal_times_out_on_infinite_loop():
    # A loop that is infinite at runtime but NOT statically detectable
    # (x stays 0 forever) - safe_eval_signal must abandon it via SIGALRM.
    fn = compile_signal("def signal_fn(df,i,params):\n    x = 0\n"
                        "    while x < 1:\n        x = x * 2\n    return 0\n")
    result = safe_eval_signal(fn, _df(), 1, {}, timeout_s=0.5)
    assert result == 0


def test_compile_signal_rejects_unconditional_infinite_loop():
    """Fix 7: `while True` / `while 1` (constant-truthy) are rejected at compile
    so a runaway loop can never reach the (threaded) backtest."""
    for src in (
        "def signal_fn(df,i,params):\n    while True:\n        pass\n    return 0\n",
        "def signal_fn(df,i,params):\n    while 1:\n        pass\n    return 0\n",
    ):
        with pytest.raises(ValueError):
            compile_signal(src)


def test_compile_signal_rejects_df_file_writes():
    """Fix 7: DataFrame export/write methods (the demonstrated filesystem leak)
    are blocked; indexing/iloc remain allowed."""
    for src in (
        "def signal_fn(df,i,params):\n    df.to_csv('/tmp/x')\n    return 0\n",
        "def signal_fn(df,i,params):\n    df.to_pickle('/tmp/x')\n    return 0\n",
        "def signal_fn(df,i,params):\n    df.to_parquet('/tmp/x')\n    return 0\n",
    ):
        with pytest.raises(ValueError):
            compile_signal(src)


def test_compile_signal_allows_benign_df_indexing():
    """Indexing and iloc must remain allowed after the write-method gate."""
    fn = compile_signal(
        "def signal_fn(df,i,params):\n"
        "    c = df['close'].iloc[i]\n"
        "    cols = df.columns\n"
        "    return 1 if c > 0 else -1\n"
    )
    assert fn(_df(), 1, {}) in (-1, 0, 1)
