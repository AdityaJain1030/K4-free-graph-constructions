"""
MV-style pencil-bipartization of incidence-structure collinearity graphs.

Given an incidence structure with points P and lines (= "pencils") L, each
line defines a clique in the collinearity graph G. MV's idea: replace each
pencil's clique with a complete bipartite graph K_{|A|,|B|} by splitting
the pencil's points into two parts and deleting intra-part edges. For a
K4-free-by-design structure (e.g. a generalized quadrangle), any partition
preserves K4-freeness (the whole point of Prop 2.iv).

This module provides:
  * gq22_points_lines()          — GQ(2,2) a.k.a. Cremona-Richmond / the doily
  * collinearity_graph(P, L)     — K4-free base graph
  * bipartize(G, lines, parts)   — MV-style pencil bipartization
  * search_partitions(P, L)      — random/exhaustive search over partition
                                    choices, returns the best c_log graph
"""
from __future__ import annotations

import math
import random
from itertools import combinations, permutations
from typing import Any

import networkx as nx


# ---------------------------------------------------------------------------
# GQ(2,2) — the smallest non-trivial generalized quadrangle, 15 pts / 15 lines
# ---------------------------------------------------------------------------

def gq22_points_lines() -> tuple[list[frozenset], list[frozenset]]:
    """
    Cremona–Richmond (15_3) configuration = collinearity structure of GQ(2,2).

    Points  = 2-subsets of {1..6}                (|P| = 15)
    Lines   = partitions of {1..6} into three 2-subsets (|L| = 15)
             each line is a frozenset of three points
    Two points are collinear  iff  they are disjoint 2-subsets, iff
             they lie in a common line.
    """
    points = [frozenset((i, j)) for i, j in combinations(range(1, 7), 2)]
    seen: set[frozenset] = set()
    for perm in permutations(range(1, 7)):
        line = frozenset([
            frozenset((perm[0], perm[1])),
            frozenset((perm[2], perm[3])),
            frozenset((perm[4], perm[5])),
        ])
        seen.add(line)
    lines = sorted(seen, key=lambda L: sorted(tuple(sorted(p)) for p in L))
    assert len(lines) == 15 and len(points) == 15
    # Sanity: each point on 3 lines, each line has 3 points
    for p in points:
        c = sum(1 for L in lines if p in L)
        assert c == 3, f"point {p} on {c} lines"
    return points, lines


# ---------------------------------------------------------------------------
# GQ(3,3) = W(3), symplectic quadrangle over F_3. 40 pts / 40 lines.
# ---------------------------------------------------------------------------

def _normalize_point_F3(v: tuple[int, ...]) -> tuple[int, ...]:
    """Canonical rep in PG(n-1, 3): last nonzero entry scaled to 1."""
    for i in range(len(v) - 1, -1, -1):
        if v[i] != 0:
            inv = pow(v[i], -1, 3)
            return tuple((x * inv) % 3 for x in v)
    raise ValueError("zero vector has no projective rep")


def _sympl_F3_4(u, v) -> int:
    # standard alternating form on F_3^4: u0 v2 - u2 v0 + u1 v3 - u3 v1
    return (u[0]*v[2] - u[2]*v[0] + u[1]*v[3] - u[3]*v[1]) % 3


def _line_through_F3_4(p, q) -> frozenset:
    pts = set()
    for a in range(3):
        for b in range(3):
            if a == 0 and b == 0:
                continue
            w = tuple((a*p[i] + b*q[i]) % 3 for i in range(4))
            pts.add(_normalize_point_F3(w))
    return frozenset(pts)


def gq33_points_lines() -> tuple[list[tuple[int, ...]], list[frozenset]]:
    """
    GQ(3,3) = W(3): points = PG(3,3) points, lines = totally isotropic
    2-subspaces w.r.t. the standard symplectic form on F_3^4.
    |P|=40, |L|=40, each line has 4 pts, each pt on 4 lines.
    """
    from itertools import product
    points = sorted({
        _normalize_point_F3(v)
        for v in product(range(3), repeat=4)
        if any(v)
    })
    lines: set[frozenset] = set()
    for i, p in enumerate(points):
        for q in points[i+1:]:
            if _sympl_F3_4(p, q) == 0:
                lines.add(_line_through_F3_4(p, q))
    lines_sorted = sorted(lines, key=lambda L: tuple(sorted(L)))
    assert len(points) == 40, f"got {len(points)} points"
    assert len(lines_sorted) == 40, f"got {len(lines_sorted)} lines"
    for L in lines_sorted:
        assert len(L) == 4, f"line has |L|={len(L)}"
    for p in points:
        c = sum(1 for L in lines_sorted if p in L)
        assert c == 4, f"pt {p} on {c} lines"
    return points, lines_sorted


# ---------------------------------------------------------------------------
# Collinearity graph + bipartization
# ---------------------------------------------------------------------------

def collinearity_graph(points: list, lines: list[frozenset]) -> tuple[nx.Graph, dict]:
    idx = {p: i for i, p in enumerate(points)}
    G = nx.Graph()
    G.add_nodes_from(range(len(points)))
    for line in lines:
        for u, v in combinations(sorted(idx[p] for p in line), 2):
            G.add_edge(u, v)
    return G, idx


def bipartize(
    lines: list[frozenset],
    idx: dict,
    partition: dict[frozenset, dict[int, int]],
) -> nx.Graph:
    """
    Build the MV-bipartized graph from scratch given a partition choice.

    For each line L:
      - partition[L][v] ∈ {0,1} assigns each point-index to a side
      - we add an edge (u,v) iff partition[L][u] != partition[L][v]
        (i.e. keep only cross-side edges)

    Works for any incidence structure. For GQ(2,2), since each line's 3
    points were pairwise adjacent before, bipartization only removes
    edges; for structures where pencils aren't cliques, bipartization
    can add edges (cross-side pairs that weren't already collinear).
    """
    G = nx.Graph()
    G.add_nodes_from(range(len(idx)))
    for line in lines:
        pts_idx = sorted(idx[p] for p in line)
        part = partition[line]
        for u, v in combinations(pts_idx, 2):
            if part[u] != part[v]:
                G.add_edge(u, v)
    return G


# ---------------------------------------------------------------------------
# Exact α via brute force (fine for n ≤ 25)
# ---------------------------------------------------------------------------

def exact_alpha(G: nx.Graph) -> int:
    n = G.number_of_nodes()
    # Bron-Kerbosch on complement
    adj = {v: set(G.neighbors(v)) for v in G}
    best = [0]

    def bk(R: frozenset, P: set, X: set):
        if not P and not X:
            if len(R) > best[0]:
                best[0] = len(R)
            return
        # pivot for speedup
        u = next(iter(P | X))
        for v in list(P - adj[u] - adj[v] if False else P - adj[u]):
            # Standard BK but on complement => we want v not adjacent to u
            pass
        # Simpler: iterate P
        for v in list(P):
            if G.has_edge(v, next(iter(R), v)) and R:
                # should be independent of R ⇒ no edge to any r in R
                pass
            # check independence
            if any(G.has_edge(v, r) for r in R):
                P.discard(v); continue
            bk(R | {v}, P - adj[v] - {v}, X - adj[v])
            P.discard(v)
            X.add(v)
    bk(frozenset(), set(G.nodes()), set())
    return best[0]


def exact_alpha_simple(G: nx.Graph) -> int:
    """Reliable brute-force α for small n (≤ 20)."""
    nodes = list(G.nodes())
    n = len(nodes)
    best = 0
    adj = {v: set(G.neighbors(v)) for v in G}

    def rec(chosen: list[int], candidates: set[int]):
        nonlocal best
        if len(chosen) + len(candidates) <= best:
            return
        if not candidates:
            best = max(best, len(chosen))
            return
        v = next(iter(candidates))
        rec(chosen + [v], candidates - {v} - adj[v])
        rec(chosen, candidates - {v})
    rec([], set(nodes))
    return best


def exact_alpha_cpsat(G: nx.Graph, timeout_s: float = 30.0) -> int:
    """CP-SAT α for 20 ≤ n ≤ 100."""
    from ortools.sat.python import cp_model
    n = G.number_of_nodes()
    model = cp_model.CpModel()
    nodes = sorted(G.nodes())
    x = {v: model.new_bool_var(f"x_{v}") for v in nodes}
    for u, v in G.edges():
        model.add(x[u] + x[v] <= 1)
    model.maximize(sum(x.values()))
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = timeout_s
    solver.parameters.num_search_workers = 4
    status = solver.solve(model)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        raise RuntimeError(f"CP-SAT α failed: status={status}")
    return int(round(solver.ObjectiveValue()))


def alpha_auto(G: nx.Graph) -> int:
    n = G.number_of_nodes()
    if n <= 20:
        return exact_alpha_simple(G)
    return exact_alpha_cpsat(G, timeout_s=30.0)


# ---------------------------------------------------------------------------
# K4 check
# ---------------------------------------------------------------------------

def has_k4(G: nx.Graph) -> bool:
    for u, v in G.edges():
        common = set(G.neighbors(u)) & set(G.neighbors(v))
        for a, b in combinations(common, 2):
            if G.has_edge(a, b):
                return True
    return False


# ---------------------------------------------------------------------------
# Partition-space search
# ---------------------------------------------------------------------------

def _c_log(alpha: int, d_max: int, n: int) -> float:
    if d_max < 2:
        return float("inf")
    return alpha * d_max / (n * math.log(d_max))


def _random_partition(lines, idx, rng) -> dict:
    """Random binary split per line, excluding all-on-one-side. Works for any
    line size."""
    part: dict[frozenset, dict[int, int]] = {}
    for line in lines:
        pts = sorted(idx[p] for p in line)
        k = len(pts)
        while True:
            sides = [rng.randint(0, 1) for _ in range(k)]
            if 0 in sides and 1 in sides:
                break
        part[line] = {v: sides[i] for i, v in enumerate(pts)}
    return part


def search_partitions(
    points,
    lines,
    n_trials: int = 20000,
    seed: int = 0,
    top_k: int = 5,
) -> list[dict]:
    """
    Random search over singleton-choice partitions. Returns the top-k
    distinct graphs by c_log.
    """
    rng = random.Random(seed)
    G_base, idx = collinearity_graph(points, lines)
    n = G_base.number_of_nodes()

    seen_edges: set[frozenset] = set()
    results: list[dict] = []

    for trial in range(n_trials):
        part = _random_partition(lines, idx, rng)
        G = bipartize(lines, idx, part)
        m = G.number_of_edges()
        if m == 0:
            continue
        ek = frozenset(frozenset(e) for e in G.edges())
        if ek in seen_edges:
            continue
        seen_edges.add(ek)

        # K4-freeness is guaranteed by GQ axiom (Prop 2.iv) but we verify once
        # for sanity — cheap at n=15
        if has_k4(G):
            raise RuntimeError(f"K4 appeared after bipartization, trial={trial}")

        degs = dict(G.degree()).values()
        d_max = max(degs); d_min = min(degs)
        alpha = alpha_auto(G)
        c = _c_log(alpha, d_max, n)
        results.append({
            "trial": trial, "c_log": c, "alpha": alpha,
            "d_max": d_max, "d_min": d_min, "m": m, "G": G,
            "partition": {
                tuple(sorted(tuple(sorted(p)) for p in L)):
                    {v: s for v, s in part[L].items()}
                for L in lines
            },
        })

    results.sort(key=lambda r: r["c_log"])
    return results[:top_k]
