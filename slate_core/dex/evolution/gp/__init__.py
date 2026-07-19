"""Structure-level genetic programming for DEX market-making (native, no LLM).

Package layout:
  genome.py     - expression-tree individual + microstructure grammar + source gen
  operators.py  - native GP operators (ramped init, subtree crossover/mutation)
  fitness.py    - structure-level fitness (sandbox-compile -> tick backtest -> walk-forward + novelty)
  controller.py - the GP evolution loop + LLM-free wiring
"""
from slate_core.dex.evolution.gp.genome import (
    FEATURES, FUNCTIONS, CONSTANTS, Node, Individual,
    random_tree, random_individual, ramped_half_and_half,
    node_to_source, policy_source, complexity, individual_hash, all_nodes,
    serialize, deserialize,
)

__all__ = ["FEATURES", "FUNCTIONS", "CONSTANTS", "Node", "Individual",
           "random_tree", "random_individual", "ramped_half_and_half",
           "node_to_source", "policy_source", "complexity", "individual_hash",
           "all_nodes", "serialize", "deserialize"]
