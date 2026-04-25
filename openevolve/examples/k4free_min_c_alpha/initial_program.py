"""
K4-free min-c_log search — FIXED ALPHA variant.

Instead of fixing N and minimising c_log, we fix an independence-number
budget ALPHA_MAX and let the program choose its own N. The evaluator
rejects any graph containing a K4 or an independent set of size
> ALPHA_MAX; among valid graphs, the objective is still to minimise

    c_log = alpha(G) * d_max(G) / (N * ln(d_max(G))).

Mapping to Ramsey: an N-vertex K4-free graph with alpha(G) <= s - 1 is
exactly a Ramsey R(4, s) lower-bound witness. With ALPHA_MAX = 4 we are
searching for R(4, 5) graphs (known: R(4, 5) = 25, so N is bounded by
24). Best known c_log at alpha = 4 in our graph_db is 0.6995 (N=22,
d_max=8 — circulant / Cayley-tabu).
"""

import os
import sys

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
from graph_utils import (  # noqa: E402
    alpha_bb_clique_cover,
    find_k4,
    has_independent_set,
    is_k4_free,
)

# Fixed constraint: target maximum independence number.
ALPHA_MAX = int(os.environ.get("K4FREE_ALPHA", "4"))


# EVOLVE-BLOCK-START
def construct(alpha_max: int) -> np.ndarray:
    """
    Return a K4-free graph with alpha(G) <= alpha_max, chosen to
    minimise c_log = alpha * d_max / (N * ln d_max). You pick N.

    Helpers available at module scope (already imported):
      is_k4_free(adj) -> bool
      find_k4(adj)    -> (a,b,c,d) tuple or None
      has_independent_set(adj, k) -> bool   # fast early-exit MIS check
      alpha_bb_clique_cover(adj) -> (alpha, mis_vertices)

    Ramsey facts you should exploit:
      R(4, 5) = 25, so alpha_max = 4 is attainable only for N <= 24.
      R(4, 6) in [35, 40], so alpha_max = 5 is attainable for N <= 39.
      Paley(17) gives c_log = 0.679 (alpha = 3) — the standing benchmark.
      Best alpha=4 in graph_db: c_log = 0.6995 at N=22, d_max=8.

    Baseline below: greedy vertex-by-vertex extension. Start with a
    single vertex; at each step try to attach a new vertex to a
    random subset of existing vertices; accept if the extended graph
    is still K4-free and alpha(G) <= alpha_max. Stop when no
    extension succeeds in several attempts.
    """
    rng = np.random.default_rng()
    MAX_N = 40              # hard cap on graph size
    MAX_TRIES = 30          # extension attempts per new vertex

    adj = np.zeros((1, 1), dtype=np.uint8)  # start with 1 vertex, no edges

    for n in range(1, MAX_N):
        extended = False
        for _ in range(MAX_TRIES):
            # Propose neighbourhood for the new vertex: independent
            # Bernoulli(0.5) subset of existing vertices.
            nbrs = rng.integers(0, 2, size=n, dtype=np.uint8)
            new_adj = np.zeros((n + 1, n + 1), dtype=np.uint8)
            new_adj[:n, :n] = adj
            new_adj[n, :n] = nbrs
            new_adj[:n, n] = nbrs
            if is_k4_free(new_adj) and not has_independent_set(new_adj, alpha_max + 1):
                adj = new_adj
                extended = True
                break
        if not extended:
            break

    return adj
# EVOLVE-BLOCK-END


def _baseline_construct(alpha_max: int) -> np.ndarray:
    """Guaranteed-valid fallback (duplicate of the baseline EVOLVE body)."""
    rng = np.random.default_rng()
    adj = np.zeros((1, 1), dtype=np.uint8)
    for n in range(1, 40):
        extended = False
        for _ in range(30):
            nbrs = rng.integers(0, 2, size=n, dtype=np.uint8)
            new_adj = np.zeros((n + 1, n + 1), dtype=np.uint8)
            new_adj[:n, :n] = adj
            new_adj[n, :n] = nbrs
            new_adj[:n, n] = nbrs
            if is_k4_free(new_adj) and not has_independent_set(new_adj, alpha_max + 1):
                adj = new_adj
                extended = True
                break
        if not extended:
            break
    return adj


def run_search() -> np.ndarray:
    """
    Entry point called by the evaluator. Returns a K4-free graph with
    alpha <= ALPHA_MAX. On any failure in the evolved construct(),
    falls back to the greedy baseline.
    """
    try:
        adj = construct(ALPHA_MAX)
        if not isinstance(adj, np.ndarray):
            adj = np.asarray(adj)
        if adj.ndim != 2 or adj.shape[0] != adj.shape[1] or adj.shape[0] == 0:
            raise ValueError(f"construct returned bad shape {adj.shape}")
        adj = ((adj + adj.T) > 0).astype(np.uint8)
        np.fill_diagonal(adj, 0)
        if not is_k4_free(adj):
            raise ValueError("construct returned a graph containing a K4")
        if has_independent_set(adj, ALPHA_MAX + 1):
            raise ValueError(f"construct returned a graph with alpha > {ALPHA_MAX}")
        return adj
    except Exception:
        return _baseline_construct(ALPHA_MAX)


if __name__ == "__main__":
    adj = run_search()
    n = adj.shape[0]
    a, _ = alpha_bb_clique_cover(adj)
    d_max = int(adj.sum(axis=1).max()) if adj.any() else 0
    print(f"ALPHA_MAX={ALPHA_MAX} N={n} alpha={a} d_max={d_max}")
