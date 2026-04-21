"""
utils/alpha_targeted.py
=======================
α-targeted local-search moves on near-regular K4-free graphs.

Primitive used by `search/alpha_targeted.py` (Method 2 from the
landscape study): instead of rewiring blindly to shrink edge density,
directly attack the current maximum independent set by wiring two of its
vertices together, with a compensating edge deletion to preserve
near-regularity.

Move
----
Let I be a (greedy-approximate) MIS of G. Pick u, v ∈ I (non-adjacent by
construction). Pick an edge (x, y) ∈ E(G) with {x, y} ∩ {u, v} = ∅.
Propose G' = G + uv - xy. Accept if

    (1) G' is K4-free,
    (2) max-min degree spread of G' ≤ cap, and
    (3) greedy α(G') < greedy α(G).

Why an MIS move at all: forcing u, v together breaks the current MIS I
as an independent set; the greedy recomputation must pick a new MIS of
size ≤ |I|, and very often of size < |I| when the graph is already
locally dense.
"""

import random as _random

import numpy as np

from utils.graph_props import alpha_approx, find_k4


def alpha_approx_set(
    adj: np.ndarray,
    *,
    restarts: int = 400,
    rng: _random.Random | None = None,
) -> tuple[int, list[int]]:
    """
    Greedy MIS approximation that also returns the best set found.

    Same algorithm as `utils.graph_props.alpha_approx`, but threads an
    explicit RNG (so callers in a search loop don't contend with the
    global `random` state) and records which vertices realised the best
    size.
    """
    rng = rng or _random.Random()
    n = adj.shape[0]
    nbr = [0] * n
    for i in range(n):
        row_i = adj[i]
        for j in range(n):
            if row_i[j]:
                nbr[i] |= 1 << j

    best_size = 0
    best_mask = 0
    verts = list(range(n))
    for _ in range(restarts):
        rng.shuffle(verts)
        avail = (1 << n) - 1
        size = 0
        cur = 0
        for v in verts:
            if (avail >> v) & 1:
                size += 1
                cur |= 1 << v
                avail &= ~nbr[v] & ~(1 << v)
        if size > best_size:
            best_size = size
            best_mask = cur

    indep: list[int] = []
    tmp = best_mask
    while tmp:
        b = (tmp & -tmp).bit_length() - 1
        indep.append(b)
        tmp &= tmp - 1
    return best_size, indep


def alpha_targeted_move(
    adj: np.ndarray,
    rng: _random.Random,
    *,
    alpha_restarts: int = 64,
    pair_attempts: int = 40,
    remove_attempts: int = 30,
    max_degree_spread: int = 2,
    known_indep: list[int] | None = None,
    known_alpha: int | None = None,
) -> tuple[np.ndarray, int, list[int]] | None:
    """
    Attempt one α-reducing move. Returns (new_adj, new_alpha, new_indep)
    on success, or None if no improving move was found within the attempt
    budget.

    Parameters
    ----------
    alpha_restarts : int
        Greedy-α restarts, both for the initial MIS and for the candidate
        evaluation. 32–128 is the practical range; higher = more reliable
        but more costly.
    pair_attempts : int
        Maximum |I|-choose-2 pairs to try per call.
    remove_attempts : int
        Maximum candidate removal edges per (u, v) pair.
    max_degree_spread : int
        Hard cap on d_max − d_min of the accepted graph (relaxes to the
        current spread if the input already exceeds this value).
    known_indep, known_alpha : optional caller cache
        If supplied, skip the initial α computation. The caller is
        responsible for these being in sync with `adj`.
    """
    n = adj.shape[0]

    if known_indep is None or known_alpha is None:
        alpha_now, indep = alpha_approx_set(adj, restarts=alpha_restarts, rng=rng)
    else:
        alpha_now, indep = known_alpha, list(known_indep)

    if len(indep) < 2:
        return None

    degs = adj.sum(axis=1)
    cur_spread = int(degs.max()) - int(degs.min())
    cap = max(max_degree_spread, cur_spread)

    # Prefer wiring together low-degree MIS vertices (they can afford +1).
    indep_sorted = sorted(indep, key=lambda v: int(degs[v]))
    pairs = [
        (indep_sorted[i], indep_sorted[j])
        for i in range(len(indep_sorted))
        for j in range(i + 1, len(indep_sorted))
    ]
    # Light shuffle so we don't get stuck on the same pair every call.
    rng.shuffle(pairs)
    pairs = pairs[:pair_attempts]

    # Precompute edges and a weight for each — heavier = endpoints are
    # both at high degree, i.e. can afford to lose an incidence.
    edges_all = [
        (i, j)
        for i in range(n)
        for j in range(i + 1, n)
        if adj[i, j]
    ]
    edge_weight = {e: int(degs[e[0]]) + int(degs[e[1]]) for e in edges_all}

    for u, v in pairs:
        # Bias removal toward high-degree edges: weighted sample without
        # replacement via rng.choices + dedup.
        weights = [edge_weight[e] for e in edges_all]
        order = rng.choices(range(len(edges_all)), weights=weights, k=min(
            len(edges_all), remove_attempts * 4,
        ))
        seen: set[int] = set()
        tried = 0
        for idx in order:
            if idx in seen:
                continue
            seen.add(idx)
            x, y = edges_all[idx]
            if tried >= remove_attempts:
                break
            if x == u or x == v or y == u or y == v:
                continue
            tried += 1

            new = adj.copy()
            new[u, v] = new[v, u] = 1
            new[x, y] = new[y, x] = 0

            d_new = new.sum(axis=1)
            if int(d_new.max()) - int(d_new.min()) > cap:
                continue

            if find_k4(new) is not None:
                continue

            new_alpha, new_indep = alpha_approx_set(
                new, restarts=alpha_restarts, rng=rng,
            )
            if new_alpha < alpha_now:
                return new, new_alpha, new_indep

    return None
