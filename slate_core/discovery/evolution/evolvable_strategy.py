"""Evolvable strategy template + SEARCH/REPLACE diff application (Phase 4).

The skeleton (risk caps, sizing, execution) is never evolved — only the body
of `signal_fn` inside the EVOLVE-BLOCK markers. apply_diff turns an LLM's
SEARCH/REPLACE proposal into the new code; if the proposal has no markers it
is treated as a full rewrite of signal_fn. Either way the result is then
compiled through the sandbox (signal_sandbox.compile_signal) before it can run.
"""
from __future__ import annotations

import re

# Anchor a SEARCH/REPLACE block. Tolerant of extra spaces after the keywords.
_BLOCK_RE = re.compile(
    r"<<<<<<<\s*SEARCH\n(.*?)\n=======\n(.*?)\n>>>>>>>\s*REPLACE",
    re.DOTALL,
)

# The initial program AlphaEvolve evolves from. Rudimentary but complete.
BASE_SIGNAL_CODE = '''# EVOLVE-BLOCK-START
def signal_fn(df, i, params):
    """Baseline: long if close above its 20-period EMA, else short. Evolve this."""
    close = df['close'].iloc[i]
    if 'ema_20' in df.columns:
        ema = df['ema_20'].iloc[i]
    else:
        ema = df['close'].iloc[i - 1]
    return 1 if close > ema else -1
# EVOLVE-BLOCK-END
'''


def apply_diff(code: str, diff: str) -> str:
    """Apply SEARCH/REPLACE blocks from an LLM proposal to the current code.

    With no markers, the diff is returned verbatim (full-rewrite mode). Raises
    ValueError if a SEARCH block cannot be found in the current code.
    """
    blocks = _BLOCK_RE.findall(diff)
    if not blocks:
        return diff  # full rewrite: caller will sandbox-validate it
    new_code = code
    for search, replace in blocks:
        if search not in new_code:
            raise ValueError(f"SEARCH block not found in current code: {search[:60]!r}")
        new_code = new_code.replace(search, replace, 1)
    return new_code
