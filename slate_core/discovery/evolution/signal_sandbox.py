"""AST-gated sandbox for evolved signal code (Phase 4).

Evolved strategy code is the most expressive (and most overfit-prone) search
space, so it runs inside a hard cage:

  1. AST validation: reject imports, dunder/private attribute access, and
     forbidden builtin names/calls (open, exec, eval, __import__, getattr, ...).
  2. Restricted execution namespace: only a curated set of safe builtins + a
     small numpy subset. No os/sys/builtins module — NameError at runtime if
     referenced.
  3. Output clamped to {-1, 0, 1}: the safety envelope (sizing/leverage/
     execution) lives in the backtester skeleton and can never be touched.
  4. safe_eval_signal wraps a single call in a SIGALRM timeout so a runaway
     loop is abandoned (the controller probes a few bars before the full run).
"""
from __future__ import annotations

import ast
import logging
import math
import signal as _signal
import types
from typing import Any, Callable, Dict

import numpy as np

logger = logging.getLogger(__name__)

SignalFn = Callable[..., int]

# Names the evolved code may never touch.
FORBIDDEN_NAMES = {
    "open", "exec", "eval", "compile", "__import__", "getattr", "setattr",
    "delattr", "globals", "locals", "vars", "input", "quit", "exit",
    "breakpoint", "memoryview", "classmethod", "staticmethod", "property",
    "type", "object", "super", "eval", "help",
}

# Object/DataFrame methods that write/export to disk, clipboard, or a DB - the
# demonstrated filesystem leak (df.to_csv wrote a file). Indexing/iloc/etc. stay
# allowed. (Fix 7.)
FORBIDDEN_ATTRS = {
    "to_csv", "to_pickle", "to_parquet", "to_hdf", "to_json", "to_excel",
    "to_sql", "to_stata", "to_feather", "to_orc", "to_xml", "to_markdown",
    "to_latex", "to_clipboard", "save", "savefig",
}

# Curated builtins only (use the builtins module directly — always a module).
import builtins as _builtins

_SAFE_BUILTINS = {
    k: getattr(_builtins, k)
    for k in ("abs", "min", "max", "sum", "len", "round", "int", "float",
              "bool", "sorted", "range", "zip", "enumerate", "any", "all", "pow")
}

# Curated numpy subset (no filesystem/process/random-seed access).
_SAFE_NP = types.SimpleNamespace(**{
    k: getattr(np, k) for k in
    ("mean", "std", "average", "median", "min", "max", "sum", "abs",
     "sqrt", "log", "exp", "sign", "where", "tanh", "percentile")
})


class SandboxError(ValueError):
    """Raised when proposed code violates the sandbox rules."""


def _validate(tree: ast.AST) -> None:
    """Walk the AST and reject dangerous constructs (blacklist + namespace guard)."""
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            raise SandboxError("imports are forbidden")
        if isinstance(node, ast.Attribute):
            attr = node.attr
            if isinstance(attr, str) and attr.startswith("_"):
                raise SandboxError(f"private/dunder attribute access forbidden: {attr!r}")
            if isinstance(attr, str) and attr in FORBIDDEN_ATTRS:
                raise SandboxError(f"forbidden attribute/method (write/export): {attr!r}")
        if isinstance(node, ast.Name) and node.id in FORBIDDEN_NAMES:
            raise SandboxError(f"forbidden name: {node.id!r}")
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id in FORBIDDEN_NAMES:
                raise SandboxError(f"forbidden call: {node.func.id!r}")
        if isinstance(node, (ast.Global, ast.Nonlocal)):
            raise SandboxError("global/nonlocal are forbidden")
        # Fix 7: reject unconditional infinite loops (while True / while 1) at
        # compile time so they never reach the (threaded) backtest. Non-obvious
        # loops (e.g. `while x < 1`) still slip through; safe_eval_signal handles
        # those on the main thread, and full worker-thread isolation needs a
        # subprocess (documented TODO).
        if isinstance(node, ast.While):
            test = node.test
            if isinstance(test, ast.Constant) and bool(test.value):
                raise SandboxError("infinite loop rejected: `while <constant-truthy>`")


def _clamp(v: Any) -> int:
    """Clamp any numeric/None/NaN to a direction in {-1, 0, 1}."""
    if v is None:
        return 0
    try:
        f = float(v)
    except (TypeError, ValueError):
        return 0
    if math.isnan(f) or math.isinf(f):
        return 0
    if f > 0:
        return 1
    if f < 0:
        return -1
    return 0


def compile_signal(code: str) -> SignalFn:
    """Validate + compile evolved code; return a clamped signal_fn(df, i, params).

    Raises SandboxError (ValueError) if the code violates the rules or does not
    define `signal_fn(df, i, params)`.
    """
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        raise SandboxError(f"syntax error: {exc.msg}") from exc
    _validate(tree)

    sandbox_globals: Dict[str, Any] = {"__builtins__": _SAFE_BUILTINS, "np": _SAFE_NP}
    # exec on the validated AST only; no access to real builtins or modules.
    exec(compile(tree, "<signal_sandbox>", "exec"), sandbox_globals)  # noqa: S102 - gated
    fn = sandbox_globals.get("signal_fn")
    if not callable(fn):
        raise SandboxError("code must define signal_fn(df, i, params)")

    def wrapped(df, i, params=None):
        try:
            return _clamp(fn(df, i, params or {}))
        except Exception:  # noqa: BLE001 - any runtime error => flat
            return 0

    wrapped.__name__ = "signal_fn"
    return wrapped


def safe_eval_signal(fn: SignalFn, df, i, params=None, timeout_s: float = 2.0) -> int:
    """Call a (sandboxed) signal fn with a SIGALRM timeout; 0 on timeout/error.

    Unix-only (uses SIGALRM); on platforms without it, calls directly.
    """
    if not hasattr(_signal, "SIGALRM"):
        try:
            return int(fn(df, i, params))
        except Exception:  # noqa: BLE001
            return 0

    class _Timeout(Exception):
        pass

    def _handler(signum, frame):
        raise _Timeout()

    old_handler = _signal.getsignal(_signal.SIGALRM)
    try:
        _signal.signal(_signal.SIGALRM, _handler)
        _signal.setitimer(_signal.ITIMER_REAL, timeout_s)
        return int(fn(df, i, params))
    except (_Timeout, Exception):  # noqa: BLE001 - timeout/error => flat
        return 0
    finally:
        _signal.setitimer(_signal.ITIMER_REAL, 0)
        _signal.signal(_signal.SIGALRM, old_handler)
