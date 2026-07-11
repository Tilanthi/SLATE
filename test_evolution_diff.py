"""Tests for Phase 4 apply_diff + the evolvable strategy template."""
import pandas as pd
import pytest

from slate_core.discovery.evolution.evolvable_strategy import (
    apply_diff, BASE_SIGNAL_CODE,
)
from slate_core.discovery.evolution.signal_sandbox import compile_signal


def test_apply_diff_simple_replacement():
    code = "def f():\n    return 1\n"
    diff = "<<<<<<< SEARCH\n    return 1\n=======\n    return 2\n>>>>>>> REPLACE"
    assert apply_diff(code, diff) == "def f():\n    return 2\n"


def test_apply_diff_multiple_blocks():
    code = "a = 1\nb = 2\n"
    diff = ("<<<<<<< SEARCH\na = 1\n=======\na = 10\n>>>>>>> REPLACE\n"
            "<<<<<<< SEARCH\nb = 2\n=======\nb = 20\n>>>>>>> REPLACE")
    out = apply_diff(code, diff)
    assert "a = 10" in out and "b = 20" in out


def test_apply_diff_raises_when_search_not_found():
    with pytest.raises(ValueError):
        apply_diff("x = 1", "<<<<<<< SEARCH\ny = 2\n=======\nz = 3\n>>>>>>> REPLACE")


def test_apply_diff_passthrough_when_no_blocks():
    full = "def signal_fn(df, i, params):\n    return 1\n"
    # No SEARCH/REPLACE markers => treat the whole output as a full rewrite.
    assert apply_diff("old code here", full) == full


def test_base_signal_code_compiles_and_runs():
    fn = compile_signal(BASE_SIGNAL_CODE)
    df = pd.DataFrame({"close": [1.0, 2.0, 1.5, 3.0]})
    out = fn(df, 1, {})
    assert out in (-1, 0, 1)


# ---------------------------------------------------------------------------
# LLM output extraction (robustness for live models that wrap code in markdown)
# ---------------------------------------------------------------------------

from slate_core.discovery.evolution.evolvable_strategy import extract_code_block

def test_extract_code_block_strips_markdown_fence():
    raw = ("Sure! Here is the improved function:\n\n"
           "```python\n"
           "def signal_fn(df, i, params):\n    return 1\n"
           "```\n\nLet me know!")
    out = extract_code_block(raw)
    assert "```" not in out
    assert "def signal_fn" in out
    assert "Sure" not in out and "Let me know" not in out


def test_extract_code_block_passthrough_plain():
    plain = "<<<<<<< SEARCH\n    return 1\n=======\n    return 2\n>>>>>>> REPLACE"
    assert extract_code_block(plain) == plain


def test_extract_code_block_plain_code_without_fence():
    code = "def signal_fn(df, i, params):\n    return 1\n"
    assert extract_code_block(code) == code
