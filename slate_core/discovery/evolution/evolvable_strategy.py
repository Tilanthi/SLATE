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

# Diverse starting archetypes for when the population is EMPTY. Without these,
# every mutation restarts from BASE_SIGNAL_CODE and the search collapses onto one
# overfit attractor (no diversity pressure - the funnel showed ~163 rejects
# clustered at a near-identical IS edge). Each archetype spans a distinct
# behavioural family so the funnel can show VARIED signals failing instead of
# one clone. All are sandbox-clean (no imports/dunder/forbidden attrs) and read
# only OHLCV + the backtester-injected ema_20.
SEED_ARCHETYPES = [
    ("momentum",
     "# EVOLVE-BLOCK-START\n"
     "def signal_fn(df, i, params):\n"
     "    \"\"\"Momentum: long above the 20-EMA, short below.\"\"\"\n"
     "    close = df['close'].iloc[i]\n"
     "    ema = df['ema_20'].iloc[i] if 'ema_20' in df.columns else df['close'].iloc[i - 1]\n"
     "    return 1 if close > ema else -1\n"
     "# EVOLVE-BLOCK-END\n"),
    ("mean_reversion",
     "# EVOLVE-BLOCK-START\n"
     "def signal_fn(df, i, params):\n"
     "    \"\"\"Mean-reversion: long when oversold vs the 20-EMA, short when overbought.\"\"\"\n"
     "    close = df['close'].iloc[i]\n"
     "    ema = df['ema_20'].iloc[i] if 'ema_20' in df.columns else df['close'].iloc[i - 1]\n"
     "    return 1 if close < ema else -1\n"
     "# EVOLVE-BLOCK-END\n"),
    ("breakout",
     "# EVOLVE-BLOCK-START\n"
     "def signal_fn(df, i, params):\n"
     "    \"\"\"Range breakout: long on a 20-bar high break, short on a low break.\"\"\"\n"
     "    if i < 20:\n"
     "        return 0\n"
     "    close = df['close'].iloc[i]\n"
     "    hi = df['high'].iloc[i - 20:i].max()\n"
     "    lo = df['low'].iloc[i - 20:i].min()\n"
     "    if close > hi:\n"
     "        return 1\n"
     "    if close < lo:\n"
     "        return -1\n"
     "    return 0\n"
     "# EVOLVE-BLOCK-END\n"),
    ("funding_reversal",
     "# EVOLVE-BLOCK-START\n"
     "def signal_fn(df, i, params):\n"
     "    \"\"\"Funding reversal: long on extreme negative funding (short squeeze).\"\"\"\n"
     "    if 'funding' not in df.columns or i < 30:\n"
     "        return 0\n"
     "    fr = df['funding'].iloc[i]\n"
     "    if fr == 0.0:\n"
     "        return 0\n"
     "    hist = df['funding'].iloc[max(0, i - 90):i + 1]\n"
     "    p1 = np.percentile(hist, 1)\n"
     "    if fr <= p1:\n"
     "        return 1\n"
     "    return 0\n"
     "# EVOLVE-BLOCK-END\n"),
    ("funding_carry",
     "# EVOLVE-BLOCK-START\n"
     "def signal_fn(df, i, params):\n"
     "    \"\"\"Funding carry: short when funding above median (longs pay).\"\"\"\n"
     "    if 'funding' not in df.columns or i < 30:\n"
     "        return 0\n"
     "    fr = df['funding'].iloc[i]\n"
     "    if fr == 0.0:\n"
     "        return 0\n"
     "    hist = df['funding'].iloc[max(0, i - 90):i + 1]\n"
     "    med = np.median(hist)\n"
     "    if fr > med and fr > 0.00005:\n"
     "        return -1\n"
     "    return 0\n"
     "# EVOLVE-BLOCK-END\n"),
]


_FENCE_RE = re.compile(r"```(?:[a-zA-Z0-9_+-]*)?\n(.*?)```", re.DOTALL)


def extract_code_block(text: str) -> str:
    """Strip markdown fences / surrounding prose from an LLM response.

    - If the text contains a fenced block, return the first fence's contents.
    - Otherwise return the text unchanged (covers SEARCH/REPLACE blocks and
      plain code). This makes the live model path usable: real LLMs wrap code
      in ```python fences, which would otherwise break ast.parse.
    """
    if not text:
        return text
    m = _FENCE_RE.search(text)
    if m:
        return m.group(1).strip() + "\n"
    return text


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
