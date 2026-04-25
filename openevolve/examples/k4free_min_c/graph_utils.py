"""
Scoring helpers for the K4-free min-c_log example.

Vendored from the parent repo's utils/graph_props.py (trimmed to the
three functions the evaluator needs): alpha_bb_clique_cover, is_k4_free,
c_log_value. Keeps this example self-contained — no PYTHONPATH hacks.
"""

from math import log

import numpy as np


# --- independence number -----------------------------------------------------

def alpha_bb_clique_cover(adj: np.ndarray) -> tuple[int, list[int]]:
    """Exact α via bitmask B&B with a greedy clique-cover upper bound."""
    n = adj.shape[0]
    nbr = [0] * n
    for i in range(n):
        for j in range(n):
            if adj[i, j]:
                nbr[i] |= 1 << j

    def popcount(x):
        return bin(x).count("1")

    def clique_cover_bound(candidates: int) -> int:
        cliques = 0
        remaining = candidates
        while remaining:
            cliques += 1
            v = (remaining & -remaining).bit_length() - 1
            clique_mask = 1 << v
            extendable = remaining & nbr[v]
            while extendable:
                w = (extendable & -extendable).bit_length() - 1
                clique_mask |= 1 << w
                extendable &= nbr[w]
                extendable &= ~(1 << w)
            remaining &= ~clique_mask
        return cliques

    best_size = 0
    best_set = 0

    def branch(candidates: int, current_set: int, current_size: int):
        nonlocal best_size, best_set
        if candidates == 0:
            if current_size > best_size:
                best_size = current_size
                best_set = current_set
            return
        if current_size + popcount(candidates) <= best_size:
            return
        if current_size + clique_cover_bound(candidates) <= best_size:
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


# --- K4 containment ----------------------------------------------------------

def find_k4(adj: np.ndarray):
    """Return (a, b, c, d) witnessing a K4, or None if K4-free."""
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
    return find_k4(adj) is None


# --- extremal metric ---------------------------------------------------------

def c_log_value(alpha: int, n: int, d_max: int) -> float | None:
    """Compute α · d_max / (n · ln(d_max)). None if d_max <= 1."""
    if d_max <= 1:
        return None
    return alpha * d_max / (n * log(d_max))
