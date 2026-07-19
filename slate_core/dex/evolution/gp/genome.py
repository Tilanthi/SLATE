"""GP genome: expression trees over microstructure features -> quoting policy.

An individual is a quoting POLICY = three expression trees (half_spread_bps,
inv_skew_bps, size). Trees use microstructure-feature terminals + arithmetic/
logic/conditional functions, then compile to a sandboxed `policy_fn(state)` via
`signal_sandbox.compile_function`. This is STRUCTURE-level evolution: the FORM
of the quoting logic varies, not just three scalars of a fixed archetype.
"""
from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass, field
from typing import List, Tuple

# Microstructure feature terminals. Names MUST match `SnapshotState` fields built
# by mm_tick_backtester. Deliberately NON-textbook: order-flow imbalance, traded
# depth-deltas, queue-ahead, vol-of-vol, recent adverse selection — not TA.
FEATURES: Tuple[str, ...] = (
    "mid_ret1", "mid_ret5",                  # 1/5-snapshot mid returns
    "imbalance",                             # top-of-book order-flow imbalance (-1..1)
    "spread_bps",                            # bid-ask spread (bps)
    "depth_imb",                             # (bid_depth - ask_depth) / total
    "bid_consumed", "ask_consumed",          # traded volume that hit each side
    "queue_ahead_bid", "queue_ahead_ask",    # size resting at better prices (queue proxy)
    "inv_frac",                              # signed inventory fraction (-1..1)
    "vol_of_vol",                            # rolling volatility of mid returns
    "adv_recent",                            # recent adverse-selection cost
    "equity_slope",                          # recent equity-curve slope
)

# Functions: name -> arity. Source templates use only sandbox-safe builtins
# (abs/min/max) + Python conditional/comparison expressions (no forbidden names).
FUNCTIONS: Tuple[Tuple[str, int], ...] = (
    ("add", 2), ("sub", 2), ("mul", 2), ("safe_div", 2),
    ("abs", 1), ("min2", 2), ("max2", 2),
    ("gt", 2), ("lt", 2), ("if_else", 3),
)

_FN_ARITY = dict(FUNCTIONS)
_FN_NAMES = tuple(name for name, _ in FUNCTIONS)

# Ephemeral random constants (ratios, bps-ish, thresholds).
CONSTANTS: Tuple[float, ...] = (
    -1.0, -0.5, -0.1, 0.0, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0, 25.0, 50.0, 100.0,
)

_FUNC_SRC = {
    "add":      "(({a}) + ({b}))",
    "sub":      "(({a}) - ({b}))",
    "mul":      "(({a}) * ({b}))",
    "safe_div": "(({a}) / ({b}) if ({b}) != 0 else 0.0)",
    "abs":      "abs({a})",
    "min2":     "min({a}, {b})",
    "max2":     "max({a}, {b})",
    "gt":       "(1.0 if ({a}) > ({b}) else 0.0)",
    "lt":       "(1.0 if ({a}) < ({b}) else 0.0)",
    "if_else":  "(({b}) if ({a}) != 0 else ({c}))",   # if_else(cond, then, else_)
}


@dataclass
class Node:
    """One GP tree node."""
    kind: str                                   # "feature" | "const" | "func"
    value: object                              # feature name | const float | func name
    children: List["Node"] = field(default_factory=list)

    def copy(self) -> "Node":
        return Node(self.kind, self.value, [c.copy() for c in self.children])


@dataclass
class Individual:
    """A quoting policy = three expression trees -> (half_spread_bps, inv_skew_bps, size)."""
    half: Node
    skew: Node
    size: Node

    def copy(self) -> "Individual":
        return Individual(self.half.copy(), self.skew.copy(), self.size.copy())

    def roots(self) -> Tuple[Node, Node, Node]:
        return (self.half, self.skew, self.size)


# --- generation -------------------------------------------------------------

def _random_terminal(rng: random.Random) -> Node:
    if rng.random() < 0.7:
        return Node("feature", rng.choice(FEATURES))
    return Node("const", rng.choice(CONSTANTS))


def random_tree(rng: random.Random, max_depth: int, full: bool = False, depth: int = 0) -> Node:
    """Grow (mixed terminals/functions) or Full (functions until last level) tree."""
    if depth >= max_depth or (not full and depth > 0 and rng.random() < 0.3):
        return _random_terminal(rng)
    fname = rng.choice(_FN_NAMES)
    arity = _FN_ARITY[fname]
    children = [random_tree(rng, max_depth, full, depth + 1) for _ in range(arity)]
    return Node("func", fname, children)


def random_individual(rng: random.Random, max_depth: int = 4) -> Individual:
    return Individual(
        random_tree(rng, max_depth, full=False),
        random_tree(rng, max_depth, full=False),
        random_tree(rng, max_depth, full=False),
    )


def ramped_half_and_half(rng: random.Random, max_depth: int = 4) -> Individual:
    """Ramped half-and-half init: random depth 2..max_depth, half full / half grow."""
    d = rng.randint(2, max_depth)
    full = rng.random() < 0.5
    return Individual(
        random_tree(rng, d, full=full),
        random_tree(rng, d, full=full),
        random_tree(rng, d, full=full),
    )


# --- source generation ------------------------------------------------------

def node_to_source(node: Node) -> str:
    if node.kind == "feature":
        return f"state.{node.value}"
    if node.kind == "const":
        return repr(float(node.value))
    fname = node.value
    a = node_to_source(node.children[0])
    if fname == "abs":
        return _FUNC_SRC[fname].format(a=a)
    b = node_to_source(node.children[1])
    if fname in ("add", "sub", "mul", "safe_div", "min2", "max2", "gt", "lt"):
        return _FUNC_SRC[fname].format(a=a, b=b)
    c = node_to_source(node.children[2])  # if_else
    return _FUNC_SRC[fname].format(a=a, b=b, c=c)


def policy_source(ind: Individual, fn_name: str = "policy_fn") -> str:
    """Compile an individual to a sandbox-ready `def policy_fn(state): return (...)`."""
    h = node_to_source(ind.half)
    s = node_to_source(ind.skew)
    z = node_to_source(ind.size)
    return f"def {fn_name}(state):\n    return ({h}, {s}, {z})\n"


# --- metrics / identity / traversal ----------------------------------------

def _node_count(node: Node) -> int:
    return 1 + sum(_node_count(c) for c in node.children)


def complexity(ind: Individual) -> int:
    """Total node count across the three trees (complexity-cap proxy, no reparse)."""
    return sum(_node_count(r) for r in (ind.half, ind.skew, ind.size))


def individual_hash(ind: Individual) -> str:
    return hashlib.sha256(policy_source(ind).encode()).hexdigest()[:16]


def all_nodes(node: Node) -> List[Node]:
    """Flatten a tree (for subtree selection in operators)."""
    out = [node]
    for c in node.children:
        out.extend(all_nodes(c))
    return out


def random_subtree(rng: random.Random, node: Node) -> Tuple[Node, List[Node], int]:
    """Return (subtree_root, path_of_children_indices, 0). Used by operators to
    locate a splice point; here we just return a random node + its path."""
    nodes = all_nodes(node)
    return rng.choice(nodes), [], 0


# --- serialization (store trees in Program.parameters, reconstruct parents) --

def node_to_tuple(node: Node) -> tuple:
    if node.kind == "feature":
        return ("X", node.value)
    if node.kind == "const":
        return ("C", float(node.value))
    return ("F", node.value, [node_to_tuple(c) for c in node.children])


def tuple_to_node(t: tuple) -> Node:
    if t[0] == "X":
        return Node("feature", t[1])
    if t[0] == "C":
        return Node("const", t[1])
    return Node("func", t[1], [tuple_to_node(c) for c in t[2]])


def serialize(ind: Individual) -> dict:
    """Serialize an individual's three trees to a JSON-friendly dict."""
    return {"half": node_to_tuple(ind.half),
            "skew": node_to_tuple(ind.skew),
            "size": node_to_tuple(ind.size)}


def deserialize(d: dict) -> Individual:
    """Reconstruct an individual from its serialized tree dict."""
    return Individual(tuple_to_node(d["half"]), tuple_to_node(d["skew"]),
                      tuple_to_node(d["size"]))


__all__ = ["FEATURES", "FUNCTIONS", "CONSTANTS", "Node", "Individual",
           "random_tree", "random_individual", "ramped_half_and_half",
           "node_to_source", "policy_source", "complexity", "individual_hash",
           "all_nodes", "random_subtree", "serialize", "deserialize"]
