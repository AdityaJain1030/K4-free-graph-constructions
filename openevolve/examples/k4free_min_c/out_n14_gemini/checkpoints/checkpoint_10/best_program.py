"""
K4-free min-c_log search — OpenEvolve target program.

The LLM evolves `construct(N)` to return a K4-free graph that minimises
    c_log(G) = alpha(G) * d_max(G) / (N * ln(d_max(G))).

Paley(17) sits at c_log ≈ 0.679; heuristic baselines plateau near 0.94.
This initial_program starts where the AlphaEvolve Ramsey setup does: a
random seed with a cheap K4-free greedy, no algebraic priors.
"""

import os
import sys

import numpy as np

# Expose the vendored helpers at module scope so evolved versions of
# construct() can call them without re-implementing K4 detection.
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
from graph_utils import is_k4_free, find_k4, alpha_bb_clique_cover  # noqa: E402


# Fixed problem size. Set via env var so one file serves N=14 and N=15.
N = int(os.environ.get("K4FREE_N", "14"))


# EVOLVE-BLOCK-START
def construct(N: int) -> np.ndarray:
    """
    Build an N-vertex K4-free graph aimed at small c_log.

    For N >= 4, constructs a circulant graph C(N, {1, 2}) which is
    regular of degree 4 and K4-free. For N < 4, falls back to a
    random-order K4-free greedy construction.

    Returns an N x N symmetric 0/1 uint8 adjacency matrix with zero
    diagonal. Must be K4-free; the evaluator rejects non-K4-free
    outputs (combined_score = 0).

    Helpers available at module scope (already imported, DO NOT
    redefine): `is_k4_free(adj) -> bool`, `find_k4(adj) -> tuple|None`,
    `alpha_bb_clique_cover(adj) -> (alpha, mis_vertices)`. Prefer
    these to hand-rolled K4/α checks.
    """
    if N < 4:
        # For small N, random greedy is fine and avoids issues with circulant definitions.
        rng = np.random.default_rng()
        adj = np.zeros((N, N), dtype=np.uint8)
        edges = [(i, j) for i in range(N) for j in range(i + 1, N)]
        rng.shuffle(edges)

        # Track neighbour bitmasks for O(1) K4 check on an added edge (i, j):
        # adding (i, j) creates a K4 iff N(i) ∩ N(j) already contains an edge.
        nbr = [0] * N
        for i, j in edges:
            common = nbr[i] & nbr[j]
            creates_k4 = False
            if common:
                tmp = common
                while tmp and not creates_k4:
                    u = (tmp & -tmp).bit_length() - 1
                    tmp &= tmp - 1
                    if nbr[u] & common & ~(1 << u):
                        creates_k4 = True
            if not creates_k4:
                adj[i, j] = 1
                adj[j, i] = 1
                nbr[i] |= 1 << j
                nbr[j] |= 1 << i
        return adj
    else:
        # Construct C(N, {1, 2}) for N >= 4.
        # This graph is K4-free, regular of degree 4.
        adj = np.zeros((N, N), dtype=np.uint8)
        S = {1, 2}
        for i in range(N):
            for s in S:
                neighbor = (i + s) % N
                adj[i, neighbor] = 1
                adj[neighbor, i] = 1
        return adj
# EVOLVE-BLOCK-END


def _baseline_greedy(n: int) -> np.ndarray:
    """Random-order K4-free greedy — guaranteed-valid fallback."""
    rng = np.random.default_rng()
    adj = np.zeros((n, n), dtype=np.uint8)
    edges = [(i, j) for i in range(n) for j in range(i + 1, n)]
    rng.shuffle(edges)
    nbr = [0] * n
    for i, j in edges:
        common = nbr[i] & nbr[j]
        creates_k4 = False
        if common:
            tmp = common
            while tmp and not creates_k4:
                u = (tmp & -tmp).bit_length() - 1
                tmp &= tmp - 1
                if nbr[u] & common & ~(1 << u):
                    creates_k4 = True
        if not creates_k4:
            adj[i, j] = 1
            adj[j, i] = 1
            nbr[i] |= 1 << j
            nbr[j] |= 1 << i
    return adj


def run_search() -> np.ndarray:
    """
    Entry point called by the evaluator. Always returns a valid
    K4-free adjacency matrix: if the evolved construct(N) raises,
    returns the wrong shape/type, or produces a non-K4-free graph,
    we fall back to the random-greedy baseline so the evaluator
    still gets a scorable graph (≈ c_log 1.10–1.17 at N=14–15).
    """
    try:
        adj = construct(N)
        if not isinstance(adj, np.ndarray):
            adj = np.asarray(adj)
        if adj.ndim != 2 or adj.shape != (N, N):
            raise ValueError(f"construct returned shape {adj.shape}, expected ({N},{N})")
        adj = ((adj + adj.T) > 0).astype(np.uint8)
        np.fill_diagonal(adj, 0)
        if not is_k4_free(adj):
            raise ValueError("construct returned a graph containing a K4")
        return adj
    except Exception:
        return _baseline_greedy(N)


if __name__ == "__main__":
    adj = run_search()
    print(f"N={N} edges={int(adj.sum() // 2)} d_max={int(adj.sum(axis=1).max())}")
