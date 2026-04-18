"""
utils/graph_props.py
====================
Canonical graph property utilities shared across SAT_old, tabusearch, and graph_db.
Do not import funsearch here; funsearch keeps its own copies.
"""

from collections import deque
from math import log

import numpy as np
import networkx as nx


# ---------------------------------------------------------------------------
# Independence number
# ---------------------------------------------------------------------------

def alpha_exact(adj: np.ndarray) -> tuple[int, list[int]]:
    """
    Exact maximum independent set via bitmask branch-and-bound.
    Returns (alpha_value, sorted_vertex_list).
    """
    n = adj.shape[0]
    nbr = [0] * n
    for i in range(n):
        for j in range(n):
            if adj[i, j]:
                nbr[i] |= 1 << j

    best_size = 0
    best_set  = 0

    def popcount(x):
        return bin(x).count("1")

    def branch(candidates, current_set, current_size):
        nonlocal best_size, best_set
        if current_size + popcount(candidates) <= best_size:
            return
        if candidates == 0:
            if current_size > best_size:
                best_size = current_size
                best_set  = current_set
            return
        v = (candidates & -candidates).bit_length() - 1
        branch(candidates & ~nbr[v] & ~(1 << v), current_set | (1 << v), current_size + 1)
        branch(candidates & ~(1 << v), current_set, current_size)

    branch((1 << n) - 1, 0, 0)

    result, tmp = [], best_set
    while tmp:
        v = (tmp & -tmp).bit_length() - 1
        result.append(v)
        tmp &= tmp - 1
    return best_size, sorted(result)


def alpha_exact_nx(G: nx.Graph) -> tuple[int, list[int]]:
    """Convenience wrapper: accepts nx.Graph instead of np.ndarray."""
    adj = np.array(nx.to_numpy_array(G, dtype=np.uint8))
    return alpha_exact(adj)


# ---------------------------------------------------------------------------
# K4-free checking
# ---------------------------------------------------------------------------

def find_k4(adj: np.ndarray) -> tuple | None:
    """Return (a, b, c, d) witnessing a K4, or None if the graph is K4-free."""
    n = adj.shape[0]
    nbr = [0] * n
    for i in range(n):
        for j in range(n):
            if adj[i, j]:
                nbr[i] |= 1 << j

    for a in range(n):
        for b in range(a + 1, n):
            if not (nbr[a] >> b & 1):
                continue
            common_ab = nbr[a] & nbr[b] & ~((1 << (b + 1)) - 1)
            tmp = common_ab
            while tmp:
                c = (tmp & -tmp).bit_length() - 1
                tmp &= tmp - 1
                common_abc = common_ab & nbr[c] & ~((1 << (c + 1)) - 1)
                if common_abc:
                    d = (common_abc & -common_abc).bit_length() - 1
                    return (a, b, c, d)
    return None


def is_k4_free(adj: np.ndarray) -> bool:
    """Return True if the graph (n×n numpy adjacency matrix) contains no K4."""
    return find_k4(adj) is None


def is_k4_free_nx(G: nx.Graph) -> bool:
    """Convenience wrapper: accepts nx.Graph instead of np.ndarray."""
    adj = np.array(nx.to_numpy_array(G, dtype=np.uint8))
    return is_k4_free(adj)


# ---------------------------------------------------------------------------
# Girth
# ---------------------------------------------------------------------------

def girth(G: nx.Graph) -> int | None:
    """Shortest cycle length via BFS from each vertex. Returns None if acyclic."""
    g = float("inf")
    for v in G.nodes():
        dist = {v: 0}
        q    = deque([(v, -1)])
        while q:
            u, par = q.popleft()
            for w in G.neighbors(u):
                if w == par:
                    continue
                if w in dist:
                    g = min(g, dist[u] + dist[w] + 1)
                else:
                    dist[w] = dist[u] + 1
                    q.append((w, u))
            if g == 3:
                return 3
    return int(g) if g < float("inf") else None


# ---------------------------------------------------------------------------
# Triangle sets
# ---------------------------------------------------------------------------

def triangle_sets(G: nx.Graph) -> tuple[list, list]:
    """
    Return (triangle_edges, triangle_vertices).
    triangle_edges: sorted list of [u, v] pairs that lie in at least one triangle.
    triangle_vertices: sorted list of vertex indices that lie in at least one triangle.
    """
    adj   = {v: set(G.neighbors(v)) for v in G.nodes()}
    edges = set()
    verts = set()
    for u in G.nodes():
        for v in adj[u]:
            if v <= u:
                continue
            for w in adj[u] & adj[v]:
                if w <= v:
                    continue
                edges |= {(min(u, v), max(u, v)),
                          (min(u, w), max(u, w)),
                          (min(v, w), max(v, w))}
                verts |= {u, v, w}
    return sorted(edges), sorted(verts)


# ---------------------------------------------------------------------------
# High-degree vertices
# ---------------------------------------------------------------------------

def high_degree_verts(G: nx.Graph) -> list[int]:
    """Return sorted list of vertices with maximum degree."""
    if G.number_of_nodes() == 0:
        return []
    d_max = max(d for _, d in G.degree())
    return sorted(int(v) for v, d in G.degree() if d == d_max)


# ---------------------------------------------------------------------------
# Independence number (approximate)
# ---------------------------------------------------------------------------

def alpha_approx(adj: np.ndarray, restarts: int = 400) -> int:
    """
    Random greedy MIS approximation via repeated random-order greedy.
    Faster than alpha_exact for large n; use as a lower bound.
    """
    n = adj.shape[0]
    nbr = [0] * n
    for i in range(n):
        for j in range(n):
            if adj[i, j]:
                nbr[i] |= 1 << j
    import random
    best = 0
    verts = list(range(n))
    for _ in range(restarts):
        random.shuffle(verts)
        avail = (1 << n) - 1
        size = 0
        for v in verts:
            if avail >> v & 1:
                size += 1
                avail &= ~nbr[v] & ~(1 << v)
        if size > best:
            best = size
    return best


# ---------------------------------------------------------------------------
# Extremal metric
# ---------------------------------------------------------------------------

def c_log_value(alpha: int, n: int, d_max: int) -> float | None:
    """Compute alpha * d_max / (n * ln(d_max)). Returns None if d_max <= 1."""
    if d_max <= 1:
        return None
    return alpha * d_max / (n * log(d_max))
