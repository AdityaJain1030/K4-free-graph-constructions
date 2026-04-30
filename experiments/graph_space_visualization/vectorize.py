"""
experiments/graph_space_visualization/vectorize.py
==================================================
Canonical adjacency → upper-triangle bit vector.

Each isomorphism class collapses to one vector in {0,1}^(N choose 2).
"""
from __future__ import annotations

import numpy as np


def adj_to_edge_vector(adj: np.ndarray) -> np.ndarray:
    """Upper-triangle (k=1), row-major, dtype uint8."""
    if adj.shape[0] != adj.shape[1]:
        raise ValueError(f"adj must be square, got {adj.shape}")
    iu = np.triu_indices(adj.shape[0], k=1)
    return np.asarray(adj[iu], dtype=np.uint8)


def stack_edge_vectors(adj_list: list[np.ndarray]) -> np.ndarray:
    """Stack K canonical adjacencies into an (K, N(N-1)/2) uint8 matrix."""
    if not adj_list:
        raise ValueError("adj_list is empty")
    n = adj_list[0].shape[0]
    for i, A in enumerate(adj_list):
        if A.shape != (n, n):
            raise ValueError(f"row {i} has shape {A.shape}, expected ({n},{n})")
    return np.stack([adj_to_edge_vector(A) for A in adj_list], axis=0)


def edge_vector_dim(n: int) -> int:
    return n * (n - 1) // 2
