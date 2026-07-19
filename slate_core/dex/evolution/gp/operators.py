"""Native (LLM-free) GP variation operators.

All nodes evaluate to floats (features/consts are floats; gt/lt/if_else return
1.0/0.0 floats), so ANY subtree is type-compatible with ANY splice point —
crossover and mutation need no type matching. Depth is bounded to prevent bloat;
the controller enforces a separate AST-node complexity cap before evaluation.
"""
from __future__ import annotations

import random
from typing import List, Optional, Tuple

from slate_core.dex.evolution.gp.genome import (
    CONSTANTS, FEATURES, FUNCTIONS, Individual, Node,
    random_individual, random_tree,
)

_FN_ARITY = dict(FUNCTIONS)


def _max_depth(node: Node) -> int:
    if not node.children:
        return 1
    return 1 + max(_max_depth(c) for c in node.children)


def _individual_depth(ind: Individual) -> int:
    return max(_max_depth(r) for r in ind.roots())


def _nodes_with_parent(root: Node) -> List[Tuple[Node, Optional[Node], int]]:
    """All (node, parent, child_index) tuples. root's parent is None, index -1."""
    out: List[Tuple[Node, Optional[Node], int]] = [(root, None, -1)]
    stack = [root]
    # BFS collecting parent links
    while stack:
        n = stack.pop()
        for i, c in enumerate(n.children):
            out.append((c, n, i))
            stack.append(c)
    return out


def _set_child(parent: Optional[Node], idx: int, new_node: Node, root: Node) -> Node:
    """Return the (possibly new) root after replacing parent.children[idx]."""
    if parent is None:
        return new_node
    parent.children[idx] = new_node
    return root


def _replace_root(ind: Individual, which: int, new_root: Node) -> Individual:
    """which: 0=half,1=skew,2=size. Returns a NEW individual with that root replaced."""
    roots = list(ind.roots())
    roots[which] = new_root
    return Individual(roots[0], roots[1], roots[2])


# --- subtree crossover ------------------------------------------------------

def crossover(parent_a: Individual, parent_b: Individual, rng: random.Random,
              max_depth: int = 5, tries: int = 8) -> Individual:
    """Subtree crossover: graft a random subtree from B into a random node of A."""
    for _ in range(tries):
        child = parent_a.copy()
        which = rng.randrange(3)                       # pick half/skew/size tree
        root = list(child.roots())[which]
        sites = _nodes_with_parent(root)
        site_node, site_parent, site_idx = rng.choice(sites)
        # donor: any node from B's three trees
        donor_roots = list(parent_b.roots())
        donor = rng.choice([n for root in donor_roots for n in _flatten(root)])
        new_subtree = donor.copy()
        new_root = _set_child(site_parent, site_idx, new_subtree, root)
        child = _replace_root(child, which, new_root)
        if _individual_depth(child) <= max_depth:
            return child
    return parent_a.copy()                             # give up: return A unchanged


def _flatten(node: Node) -> List[Node]:
    out = [node]
    for c in node.children:
        out.extend(_flatten(c))
    return out


# --- subtree mutation -------------------------------------------------------

def mutate_subtree(ind: Individual, rng: random.Random,
                   max_depth: int = 5, subtree_depth: int = 3, tries: int = 8) -> Individual:
    """Replace a random node with a freshly-grown random subtree."""
    for _ in range(tries):
        child = ind.copy()
        which = rng.randrange(3)
        root = list(child.roots())[which]
        sites = _nodes_with_parent(root)
        site_node, site_parent, site_idx = rng.choice(sites)
        new_subtree = random_tree(rng, rng.randint(1, subtree_depth), full=False)
        new_root = _set_child(site_parent, site_idx, new_subtree, root)
        child = _replace_root(child, which, new_root)
        if _individual_depth(child) <= max_depth:
            return child
    return ind.copy()


# --- point mutation ---------------------------------------------------------

def mutate_point(ind: Individual, rng: Random_like) -> Individual:
    """Perturb a single node in place: const->const, feature->feature, func->same-arity func."""
    child = ind.copy()
    which = rng.randrange(3)
    root = list(child.roots())[which]
    nodes = _flatten(root)
    node = rng.choice(nodes)
    if node.kind == "const":
        node.value = rng.choice(CONSTANTS)
    elif node.kind == "feature":
        node.value = rng.choice(FEATURES)
    elif node.kind == "func":
        same_arity = [n for n, a in FUNCTIONS if a == _FN_ARITY[node.value]]
        node.value = rng.choice(same_arity)
    return child


# --- composite + selection --------------------------------------------------

def vary(ind: Individual, rng: random.Random, max_depth: int = 5,
         subtree_mut_rate: float = 0.4, point_mut_rate: float = 0.3,
         crossover_rate: float = 0.0, partner: Optional[Individual] = None) -> Individual:
    """Apply variation: optional crossover, then subtree and/or point mutation."""
    child = ind.copy()
    if crossover_rate > 0 and partner is not None and rng.random() < crossover_rate:
        child = crossover(child, partner, rng, max_depth=max_depth)
    if rng.random() < subtree_mut_rate:
        child = mutate_subtree(child, rng, max_depth=max_depth)
    if rng.random() < point_mut_rate:
        child = mutate_point(child, rng)
    return child


def tournament(population: List[Tuple[Individual, float]], k: int,
               rng: random.Random) -> Individual:
    """Tournament selection over (individual, fitness_score). Higher score wins."""
    if not population:
        return random_individual(rng)
    contenders = [rng.choice(population) for _ in range(min(k, len(population)))]
    best = max(contenders, key=lambda pif: pif[1])
    return best[0].copy()


# Type alias avoid hard import cycle (random.Random is fine but keep flexible).
Random_like = random.Random


__all__ = ["crossover", "mutate_subtree", "mutate_point", "vary", "tournament",
           "random_individual"]
