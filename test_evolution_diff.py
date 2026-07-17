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


# ---------------------------------------------------------------------------
# Missing-terminator robustness.
#
# Live LLMs (notably GLM via the Z.ai proxy) frequently emit a SEARCH/REPLACE
# block with the opening `<<<<<<< SEARCH` and the `=======` separator but OMIT
# the closing `>>>>>>> REPLACE` terminator. The strict _BLOCK_RE regex requires
# all three markers, so such a block was treated as "no blocks found" and the
# raw text (still containing the `<<<<<<<` / `=======` markers) was returned
# verbatim as a full rewrite — which then failed to compile. This was the root
# cause of the AMM layer's ~98% compile-stage attrition. The parser must apply
# a terminator-less block by taking the replacement as everything after the
# `=======` separator.
# ---------------------------------------------------------------------------

def test_apply_diff_handles_missing_replace_terminator():
    code = "def lp_fn(bar):\n    return {'action': 'HOLD'}\n"
    # No `>>>>>>> REPLACE` terminator — this is the GLM output we observed.
    diff = ("<<<<<<< SEARCH\n"
            "    return {'action': 'HOLD'}\n"
            "=======\n"
            "    return {'action': 'ENTER', 'range_bps': 20}\n")
    out = apply_diff(code, diff)
    assert "ENTER" in out and "'action': 'HOLD'" not in out
    # The leftover SEARCH/======= markers must NOT leak into the result.
    assert "<<<" not in out and "====" not in out and "REPLACE" not in out


def test_apply_diff_missing_terminator_produces_compilable_code():
    code = ("def lp_fn(bar):\n"
            "    close = float(bar['close'])\n"
            "    return {'action': 'HOLD'}\n")
    diff = ("<<<<<<< SEARCH\n"
            "    return {'action': 'HOLD'}\n"
            "=======\n"
            "    if close > 1.0:\n"
            "        return {'action': 'ENTER', 'range_bps': 20}\n"
            "    return {'action': 'HOLD'}\n")  # no >>>>>>> REPLACE
    out = apply_diff(code, diff)
    # The whole point: the result must be valid Python (no marker text).
    compile(out, "<test>", "exec")


def test_apply_diff_multiple_blocks_last_missing_terminator():
    code = "a = 1\nb = 2\nc = 3\n"
    diff = ("<<<<<<< SEARCH\na = 1\n=======\na = 10\n>>>>>>> REPLACE\n"
            "<<<<<<< SEARCH\nb = 2\n=======\nb = 20\n")  # 2nd block no terminator
    out = apply_diff(code, diff)
    assert "a = 10" in out and "b = 20" in out and "c = 3" in out
    assert "<<<" not in out and "====" not in out


def test_apply_diff_missing_terminator_still_raises_when_search_absent():
    # A terminator-less block whose SEARCH text isn't in the current code must
    # still surface as a ValueError (not silently pass through as full rewrite).
    with pytest.raises(ValueError):
        apply_diff("x = 1", "<<<<<<< SEARCH\ny = 2\n=======\nz = 3\n")


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
