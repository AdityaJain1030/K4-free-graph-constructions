"""
Targeted probe: cyclotomic circulants past the exhaustive N=35 cutoff.

For each prime p in {37, 41, 61, 73, 89} and order d in {4, 6} with d | (p-1),
enumerate every symmetric union of index-d cyclotomic cosets of Z_p^*, build
Cay(Z_p, S), keep K4-free survivors, compute alpha, print c_log.

Goal: find any circulant with c_log <= 0.6789 (the P(17) basin) or tight
evidence that this slice of circulant space stays above it.
"""
import os
import sys
from math import log

import networkx as nx

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.graph_props import alpha_nx, is_k4_free_nx

PRIMES = [37, 41, 61, 73, 89]
ORDERS = [4, 6]
TARGET = 0.6789  # P(17)


def primitive_root(p: int) -> int:
    def ord_of(g):
        x, k = g, 1
        while x != 1:
            x = (x * g) % p
            k += 1
        return k
    for g in range(2, p):
        if ord_of(g) == p - 1:
            return g
    raise RuntimeError(f"no primitive root for p={p}")


def cyclotomic_cosets(p: int, d: int) -> list[list[int]]:
    """Partition Z_p^* into d cosets of the index-d subgroup, via primitive root g."""
    assert (p - 1) % d == 0
    g = primitive_root(p)
    cosets = [[] for _ in range(d)]
    x = 1
    for i in range(p - 1):
        cosets[i % d].append(x)
        x = (x * g) % p
    return cosets


def symmetric_coset_partition(p: int, cosets: list[list[int]]) -> tuple[list[list[int]], str]:
    """
    Group cosets into classes closed under negation. Return (classes, tag)
    where tag is 'self' (each coset is symmetric) or 'paired' (cosets come
    in negation-pairs).
    """
    d = len(cosets)
    neg = {}  # coset index i -> coset index j such that -C_i = C_j
    index_of = {}
    for i, C in enumerate(cosets):
        for x in C:
            index_of[x] = i
    for i, C in enumerate(cosets):
        neg[i] = index_of[(-C[0]) % p]
    if all(neg[i] == i for i in range(d)):
        return [[i] for i in range(d)], "self"
    # Pair cosets.
    seen, pairs = set(), []
    for i in range(d):
        if i in seen:
            continue
        j = neg[i]
        pairs.append(sorted({i, j}))
        seen.add(i)
        seen.add(j)
    return pairs, "paired"


def build_circulant(p: int, S: set[int]) -> nx.Graph:
    G = nx.Graph()
    G.add_nodes_from(range(p))
    for i in range(p):
        for s in S:
            G.add_edge(i, (i + s) % p)
    return G


def c_log(alpha: int, n: int, d: int) -> float | None:
    if d <= 1:
        return None
    return alpha * d / (n * log(d))


def probe(p: int, d: int) -> list[tuple[float, int, int, tuple[int, ...]]]:
    cosets = cyclotomic_cosets(p, d)
    classes, tag = symmetric_coset_partition(p, cosets)
    hits = []
    checked = 0
    k4_free_count = 0
    for mask in range(1, 1 << len(classes)):
        chosen = [cls for b, cls in enumerate(classes) if (mask >> b) & 1]
        class_idx = tuple(sorted(i for cls in chosen for i in cls))
        S = set()
        for i in class_idx:
            S.update(cosets[i])
        checked += 1
        if not S:
            continue
        G = build_circulant(p, S)
        if not is_k4_free_nx(G):
            continue
        k4_free_count += 1
        alpha, _ = alpha_nx(G)
        dmax = max(dict(G.degree()).values())
        c = c_log(alpha, p, dmax)
        if c is not None:
            hits.append((c, alpha, dmax, class_idx))
    print(
        f"  p={p:2d} d={d} {tag:7s} classes={len(classes)} "
        f"configs={checked} k4-free={k4_free_count}"
    )
    return sorted(hits)


def main():
    print(f"TARGET (P(17) basin): c_log = {TARGET}\n")
    all_hits = []
    for p in PRIMES:
        for d in ORDERS:
            if (p - 1) % d != 0:
                print(f"  p={p} d={d} skipped (d does not divide p-1)")
                continue
            hits = probe(p, d)
            for h in hits:
                all_hits.append((p, d) + h)

    print("\nBest c_log per (p, d):")
    by_pd: dict[tuple[int, int], tuple] = {}
    for p, d, c, a, dm, idx in all_hits:
        if (p, d) not in by_pd or c < by_pd[(p, d)][0]:
            by_pd[(p, d)] = (c, a, dm, idx)
    for (p, d), (c, a, dm, idx) in sorted(by_pd.items()):
        flag = "  <-- BEATS P(17)" if c < TARGET else ("  tied" if abs(c - TARGET) < 1e-4 else "")
        print(f"  p={p:2d} d={d}  c_log={c:.4f}  alpha={a}  dmax={dm}  cosets={idx}{flag}")

    below = [h for h in all_hits if h[2] < TARGET]
    if below:
        print(f"\n!!! {len(below)} configs below P(17) basin:")
        for p, d, c, a, dm, idx in sorted(below, key=lambda x: x[2]):
            print(f"    p={p} d={d} c_log={c:.4f} alpha={a} dmax={dm} cosets={idx}")
    else:
        print(f"\nNo configs below P(17) basin ({TARGET}).")


if __name__ == "__main__":
    main()
