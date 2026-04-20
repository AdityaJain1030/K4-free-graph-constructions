"""
utils/edge_switch.py
====================
Degree-preserving edge-switch moves on K4-free graphs.

Shared primitive for local search and random-walk fragility probes
(search/random_regular_switch.py, scripts/probe_fragility.py, …).

A "switch" is the classical Markov-chain move on labelled graphs:
pick two disjoint edges (a, b), (c, d); replace them with (a, c),
(b, d) or (a, d), (b, c). Each vertex keeps its degree.

Here we wrap the move with a K4-freeness guard and a configurable
degree-spread guard (used by probe 2 to stay near-regular even
though the switch by itself preserves degrees exactly).
"""

import random as _random
from typing import Iterable

import numpy as np

from utils.graph_props import find_k4


# ---------------------------------------------------------------------------
# Adjacency helpers (numpy-backed for speed — local search calls these in a hot loop)
# ---------------------------------------------------------------------------

def _creates_k4_local(adj: np.ndarray, added_edges: Iterable[tuple[int, int]]) -> bool:
    """Full re-check; fine for n≤200 where find_k4 is O(m·Δ²). Simpler than incremental."""
    return find_k4(adj) is not None


def safe_switch(
    adj: np.ndarray,
    e1: tuple[int, int],
    e2: tuple[int, int],
    *,
    rewiring: str = "ac_bd",
) -> np.ndarray | None:
    """
    Try to switch e1=(a,b), e2=(c,d) → (a,c),(b,d) (or (a,d),(b,c) if
    rewiring=="ad_bc"). Returns the new adjacency if the switch is legal
    and K4-free, else None. Does not mutate `adj`.

    Legality: all four endpoints distinct, neither new edge already
    present, no self-loops.
    """
    a, b = e1
    c, d = e2
    if rewiring == "ad_bc":
        c, d = d, c
    elif rewiring != "ac_bd":
        raise ValueError(f"rewiring must be 'ac_bd' or 'ad_bc', got {rewiring!r}")

    if len({a, b, c, d}) != 4:
        return None
    if adj[a, c] or adj[b, d]:
        return None

    new = adj.copy()
    new[a, b] = new[b, a] = 0
    new[c, d] = new[d, c] = 0
    new[a, c] = new[c, a] = 1
    new[b, d] = new[d, b] = 1

    if find_k4(new) is not None:
        return None
    return new


def random_switch(
    adj: np.ndarray,
    rng: _random.Random,
    *,
    max_attempts: int = 50,
) -> np.ndarray | None:
    """
    Attempt up to `max_attempts` random disjoint-edge pairs. Returns the
    first adjacency matrix produced by a legal K4-free switch, else None.
    """
    n = adj.shape[0]
    edges = [(i, j) for i in range(n) for j in range(i + 1, n) if adj[i, j]]
    if len(edges) < 2:
        return None
    for _ in range(max_attempts):
        e1, e2 = rng.sample(edges, 2)
        for rewiring in ("ac_bd", "ad_bc"):
            new = safe_switch(adj, e1, e2, rewiring=rewiring)
            if new is not None:
                return new
    return None


# ---------------------------------------------------------------------------
# Single-edge random-walk move (used by probe 2 fragility)
# ---------------------------------------------------------------------------

def random_walk_move(
    adj: np.ndarray,
    rng: _random.Random,
    *,
    max_degree_spread: int = 2,
    max_attempts: int = 50,
) -> np.ndarray | None:
    """
    Probe-2 random walk step: pick a random edge uv, a random non-neighbour
    w of u (w ≠ u, w ≠ v), propose G' = G - uv + uw. Accept iff the result
    is K4-free and the resulting degree spread (d_max - d_min) ≤
    `max_degree_spread`. Returns the new adjacency matrix or None.

    This is *not* degree-preserving: deg(u) is unchanged, deg(v) drops by 1,
    deg(w) rises by 1. The spread cap keeps the walk on near-regular graphs;
    the walk itself is unbiased w.r.t. c_log (it's a walk, not a climb).
    """
    n = adj.shape[0]
    edges = [(i, j) for i in range(n) for j in range(i + 1, n) if adj[i, j]]
    if not edges:
        return None

    for _ in range(max_attempts):
        u, v = rng.choice(edges)
        if rng.random() < 0.5:
            u, v = v, u  # random orientation of the edge
        non_nbrs = [w for w in range(n) if w != u and w != v and not adj[u, w]]
        if not non_nbrs:
            continue
        w = rng.choice(non_nbrs)

        new = adj.copy()
        new[u, v] = new[v, u] = 0
        new[u, w] = new[w, u] = 1

        if find_k4(new) is not None:
            continue
        degs = new.sum(axis=1)
        if int(degs.max()) - int(degs.min()) > max_degree_spread:
            continue
        return new

    return None


# ---------------------------------------------------------------------------
# Degree-targeted switches (used by hill-climbing)
# ---------------------------------------------------------------------------

def rebalancing_switch(
    adj: np.ndarray,
    rng: _random.Random,
    *,
    max_attempts: int = 50,
) -> np.ndarray | None:
    """
    Bias the switch toward degree-rebalancing: pick one edge incident to a
    current max-degree vertex and one edge incident to a current
    min-degree vertex. Falls back to uniform if either side is empty.
    Degree sum is preserved; degree *spread* may shrink or stay the same.
    """
    n = adj.shape[0]
    degs = adj.sum(axis=1)
    d_max = int(degs.max())
    d_min = int(degs.min())
    if d_max == d_min:
        return random_switch(adj, rng, max_attempts=max_attempts)

    hi = [v for v in range(n) if degs[v] == d_max]
    lo = [v for v in range(n) if degs[v] == d_min]
    hi_edges = [(u, v) for u in hi for v in range(n) if v != u and adj[u, v]]
    lo_edges = [(u, v) for u in lo for v in range(n) if v != u and adj[u, v]]
    if not hi_edges or not lo_edges:
        return random_switch(adj, rng, max_attempts=max_attempts)

    for _ in range(max_attempts):
        e1 = rng.choice(hi_edges)
        e2 = rng.choice(lo_edges)
        if len({*e1, *e2}) != 4:
            continue
        for rewiring in ("ac_bd", "ad_bc"):
            new = safe_switch(adj, e1, e2, rewiring=rewiring)
            if new is not None:
                return new
    return random_switch(adj, rng, max_attempts=max_attempts)
