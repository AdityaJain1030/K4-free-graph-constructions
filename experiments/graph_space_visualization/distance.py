"""
experiments/graph_space_visualization/distance.py
=================================================
Pairwise dissimilarity matrices over canonical edge vectors.

`pairwise_hamming` is the default — vectorized via the Gram trick:
    H[i,j] = ||x_i||_1 + ||x_j||_1 - 2 * <x_i, x_j>
for x in {0,1}^m, where ||·||_1 counts ones. O(K^2 m) flops, O(K^2) memory.

`pairwise_ged` is the small-N exact graph edit distance, intended as a
correctness check / honest baseline for the canonical-Hamming proxy.
NP-hard in general; gated behind a per-pair timeout.
"""
from __future__ import annotations

import numpy as np


def pairwise_hamming(X: np.ndarray) -> np.ndarray:
    """X: (K, m) of {0,1}. Returns (K, K) int32 Hamming distances."""
    if X.dtype != np.uint8:
        X = X.astype(np.uint8)
    Xi = X.astype(np.int32)
    row_sums = Xi.sum(axis=1)
    inner = Xi @ Xi.T
    D = row_sums[:, None] + row_sums[None, :] - 2 * inner
    np.fill_diagonal(D, 0)
    return D.astype(np.int32)


def pairwise_ged(graphs: list, timeout_per_pair_s: float = 1.0) -> np.ndarray:
    """Exact graph edit distance via networkx, per-pair timed.

    Only sane for small N (≤ ~10). Pairs that time out are filled with the
    canonical-Hamming distance as a fallback, and the indices are returned
    as a second array so the caller can flag them.
    """
    import networkx as nx

    K = len(graphs)
    D = np.zeros((K, K), dtype=np.float64)
    timed_out: list[tuple[int, int]] = []
    for i in range(K):
        for j in range(i + 1, K):
            try:
                d = nx.graph_edit_distance(
                    graphs[i], graphs[j], timeout=timeout_per_pair_s
                )
            except Exception:
                d = None
            if d is None:
                timed_out.append((i, j))
                d = float("nan")
            D[i, j] = D[j, i] = d
    return D, timed_out
