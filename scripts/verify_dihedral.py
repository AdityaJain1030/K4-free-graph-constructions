#!/usr/bin/env python3
"""
scripts/verify_dihedral.py
==========================
Exhaustive Cayley-on-D_p verification of the per-family k-lift optimality
conjecture (Conjecture B at k=2 for the P(17) family — and more generally
for any dihedral order).

D_p = ⟨r, s : r^p = s^2 = 1, s r s = r^{-1}⟩, |D_p| = 2p.
Elements indexed as:
    rotations   r^i      → index i           (i = 0..p-1)
    reflections s·r^j    → index p + j       (j = 0..p-1)

For each symmetric S ⊆ D_p \\ {1} we build Cay(D_p, S) and, for K₄-free
graphs, compute exact α via alpha_bb_clique_cover. We report the minimum
c and all Aut(D_p)-orbit representatives that attain it.

Orbit reduction under Aut(D_p) = Hol(Z_p) = Z_p ⋊ Z_p* of order p(p-1):
    φ_{u,v}(r^i)     = r^{u·i mod p},          u ∈ Z_p*, v ∈ Z_p
    φ_{u,v}(s·r^j)   = s·r^{(v + u·j) mod p}
D_p is CI for p odd prime (Babai), so Aut(D_p)-orbits are the graph-iso
classes of Cayley graphs on D_p.

Run::

    micromamba run -n k4free python scripts/verify_dihedral.py --p 5    # smoke test
    micromamba run -n k4free python scripts/verify_dihedral.py --p 17   # Conj B, k=2, P(17)
"""

from __future__ import annotations

import argparse
import math
import os
import sys
import time
from math import gcd

import networkx as nx
import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from graph_db import DEFAULT_GRAPHS, GraphStore
from utils.graph_props import alpha_bb_clique_cover, is_k4_free


# ── group structure ────────────────────────────────────────────────────────

def _units_mod_p(p: int) -> list[int]:
    return [u for u in range(1, p) if gcd(u, p) == 1]


def _aut_tables(p: int) -> list[list[int]]:
    """Precompute index permutations induced by each Aut(D_p) element.

    Returns a list of 2p-tuples; each maps index k ∈ {0,..,2p-1} to its
    image under φ_{u,v}. Identity is included (u=1, v=0, first entry).
    """
    n = 2 * p
    tables: list[list[int]] = []
    for u in _units_mod_p(p):
        for v in range(p):
            t = [0] * n
            for i in range(p):
                t[i] = (u * i) % p
            for j in range(p):
                t[p + j] = p + ((v + u * j) % p)
            tables.append(t)
    return tables


# ── enumeration ────────────────────────────────────────────────────────────

def _slot_masks(p: int) -> list[int]:
    """Indivisible bit-units for symmetric S ⊆ D_p \\ {1}.

    - Rotation pairs {i, p-i} for i = 1..(p-1)//2  → 2 bits each.
    - Each reflection s·r^j is its own inverse     → 1 bit each.
    """
    slots = []
    for i in range(1, (p - 1) // 2 + 1):
        slots.append((1 << i) | (1 << (p - i)))
    for j in range(p):
        slots.append(1 << (p + j))
    return slots


def _enumerate_symmetric_bitmasks(p: int):
    """Yield every symmetric S ⊆ D_p \\ {1} as an int bitmask."""
    slots = _slot_masks(p)
    n_slots = len(slots)
    for bits in range(1 << n_slots):
        mask = 0
        x = bits
        i = 0
        while x:
            if x & 1:
                mask |= slots[i]
            x >>= 1
            i += 1
        yield mask


def _is_lex_min_under_aut(mask: int, aut_tables: list[list[int]]) -> bool:
    """Return True iff mask is the numerically smallest of {φ(mask)}.

    Assumes aut_tables[0] is the identity (skipped).
    """
    for t in aut_tables[1:]:
        out = 0
        x = mask
        i = 0
        while x:
            if x & 1:
                out |= 1 << t[i]
            x >>= 1
            i += 1
        if out < mask:
            return False
    return True


def _bitmask_to_set(mask: int) -> list[int]:
    out = []
    x = mask
    i = 0
    while x:
        if x & 1:
            out.append(i)
        x >>= 1
        i += 1
    return out


# ── Cayley graph construction ──────────────────────────────────────────────

def _build_cayley_adj(p: int, S: list[int]) -> np.ndarray:
    """Adjacency matrix of Cay(D_p, S), S given as list of element indices.

    Mult table (right action):
      rot[i]*rot[j] = rot[(i+j) mod p]
      rot[i]*ref[j] = ref[(j-i) mod p]
      ref[i]*rot[j] = ref[(i+j) mod p]
      ref[i]*ref[j] = rot[(j-i) mod p]
    """
    n = 2 * p
    adj = np.zeros((n, n), dtype=np.uint8)
    for g in range(n):
        for s in S:
            if g < p and s < p:
                h = (g + s) % p
            elif g < p and s >= p:
                j = s - p
                h = p + ((j - g) % p)
            elif g >= p and s < p:
                i = g - p
                h = p + ((i + s) % p)
            else:
                i = g - p
                j = s - p
                h = (j - i) % p
            if g != h:
                adj[g, h] = 1
                adj[h, g] = 1
    return adj


def _c_log(alpha: int, d_max: int, n: int) -> float:
    if d_max <= 1:
        return math.inf
    return alpha * d_max / (n * math.log(d_max))


# ── lift recognition ───────────────────────────────────────────────────────

def _p17_lift_in_d17_connection_sets() -> list[list[int]]:
    """Return several representative k=2 lifts of P(17) viewed as subsets of D_17.

    The k=2 lift of P(17) lives on vertex set ≅ Z_2 × Z_17 (as a graph). The
    dihedral structure gives a second embedding. The simplest is
    "rotations-only" with QR_17: S = { r^x : x ∈ QR_17 }. No reflection bits.
    """
    QR_17 = [1, 2, 4, 8, 9, 13, 15, 16]
    return [sorted(QR_17)]  # rotation-only embedding


# ── persistence ────────────────────────────────────────────────────────────

def _save_minimizers_to_db(result: dict, source: str, filename: str) -> int:
    p = result["p"]
    n = 2 * p
    store = GraphStore(DEFAULT_GRAPHS)
    written = 0
    for c, a, d, S in result["minimizers"]:
        adj = _build_cayley_adj(p, sorted(S))
        G = nx.from_numpy_array(np.asarray(adj, dtype=np.uint8))
        _, is_new = store.add_graph(
            G, source=source, filename=filename,
            n=n,
            alpha=int(a),
            d_max=int(d),
            c_log=float(c),
            group=f"D_{p}",
            connection_set=sorted(int(s) for s in S),
            orbits_examined=int(result["orbits_examined"]),
            k4_free_orbits=int(result["k4_free_count"]),
            certificate=f"exact D_{p} Cayley minimum, verified by exhaustive "
                        "Aut(D_p)-orbit enumeration",
        )
        if is_new:
            written += 1
    return written


# ── main scan ──────────────────────────────────────────────────────────────

def scan(p: int, *, verbosity: int = 1, progress_every: int = 500_000) -> dict:
    slots = _slot_masks(p)
    total_subsets = 1 << len(slots)
    auts = _aut_tables(p)
    n_vertices = 2 * p

    if verbosity:
        print(f"[D_{p}, N={n_vertices}] enumerating {total_subsets:,} "
              f"symmetric subsets (|Aut(D_{p})| = {len(auts)}, "
              f"lex-min orbit pruning)",
              flush=True)

    best_c = math.inf
    best_rows: list[tuple[float, int, int, list[int]]] = []
    n_k4free = 0
    n_examined = 0
    n_orbit_reps = 0
    t0 = time.monotonic()

    for mask in _enumerate_symmetric_bitmasks(p):
        n_examined += 1
        if verbosity and n_examined % progress_every == 0:
            dt = time.monotonic() - t0
            rate = n_examined / max(dt, 1e-9)
            eta = (total_subsets - n_examined) / max(rate, 1e-9)
            print(f"  [{n_examined:>12,}/{total_subsets:,}] "
                  f"rate={rate:,.0f}/s  eta={eta/60:.1f}min  "
                  f"orbits={n_orbit_reps:,}  k4free={n_k4free:,}  "
                  f"best_c={best_c:.6f}",
                  flush=True)

        if mask == 0:
            continue
        if not _is_lex_min_under_aut(mask, auts):
            continue
        n_orbit_reps += 1

        S = _bitmask_to_set(mask)
        adj = _build_cayley_adj(p, S)
        d_max = int(adj.sum(axis=1).max()) if S else 0
        if d_max < 2:
            continue
        if not is_k4_free(adj):
            continue
        alpha, _indep = alpha_bb_clique_cover(adj)
        c = _c_log(alpha, d_max, n_vertices)
        n_k4free += 1

        if c < best_c - 1e-9:
            best_c = c
            best_rows = [(c, alpha, d_max, S)]
        elif abs(c - best_c) < 1e-9:
            best_rows.append((c, alpha, d_max, S))

    dt = time.monotonic() - t0
    if verbosity:
        print(f"[D_{p}] examined {n_examined:,}, orbits {n_orbit_reps:,}, "
              f"K₄-free {n_k4free:,}, elapsed {dt:.1f}s", flush=True)

    return {
        "p": p,
        "total_subsets": total_subsets,
        "orbits_examined": n_orbit_reps,
        "k4_free_count": n_k4free,
        "best_c": best_c,
        "minimizers": list(best_rows),
        "elapsed_s": dt,
    }


def _fmt_element(idx: int, p: int) -> str:
    if idx < p:
        return f"r^{idx}"
    return f"sr^{idx - p}"


def report(result: dict) -> None:
    p = result["p"]
    n = 2 * p
    print()
    print(f"=== D_{p}  (|V| = {n}) ===")
    print(f"Symmetric subsets:              {result['total_subsets']:,}")
    print(f"Distinct Aut(D_{p})-orbits:       {result['orbits_examined']:,}")
    print(f"K₄-free orbits found:           {result['k4_free_count']:,}")
    print(f"Min c_log over Cay(D_{p}, ·):     {result['best_c']:.6f}")

    minimizers = result["minimizers"]
    print(f"Number of minimizers (orbits):  {len(minimizers)}")
    for i, (c, a, d, S) in enumerate(minimizers[:8]):
        elems = [_fmt_element(idx, p) for idx in sorted(S)]
        print(f"  [{i}] S = {sorted(S)}  ({', '.join(elems)})")
        print(f"      α = {a},  d_max = {d},  c = {c:.6f}")

    if p == 17:
        # P(17)-lift embedding check: rotation-only with QR_17 bits.
        QR_17 = {1, 2, 4, 8, 9, 13, 15, 16}
        lift_mask = 0
        for x in QR_17:
            lift_mask |= 1 << x
        auts = _aut_tables(p)
        lift_orbit = set()
        for t in auts:
            out = 0
            x = lift_mask; idx = 0
            while x:
                if x & 1:
                    out |= 1 << t[idx]
                x >>= 1; idx += 1
            lift_orbit.add(out)
        minimizer_masks = set()
        for _, _, _, S in minimizers:
            m = 0
            for v in S:
                m |= 1 << v
            minimizer_masks.add(m)
        if lift_orbit & minimizer_masks:
            print("  [lift] D_17 k=2 lift of P(17) (rotations = QR_17) IS a minimizer ✓")
        else:
            print("  [lift] D_17 rotation-only embedding of P(17) is NOT a minimizer:")
            adj = _build_cayley_adj(p, sorted(QR_17))
            d_l = int(adj.sum(axis=1).max())
            a_l, _ = alpha_bb_clique_cover(adj)
            c_l = _c_log(a_l, d_l, n)
            print(f"         α = {a_l}, d_max = {d_l}, c = {c_l:.6f}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--p", type=int, default=5,
                    help="Odd prime; verifier runs on D_p (order 2p).")
    ap.add_argument("--verbosity", type=int, default=1)
    ap.add_argument("--save-db", action="store_true")
    ap.add_argument("--db-source", default="dihedral_exhaustive_min")
    ap.add_argument("--db-filename", default="dihedral_exhaustive_min.json")
    args = ap.parse_args()

    if args.p < 3:
        print("p must be ≥ 3", file=sys.stderr)
        return 2

    result = scan(args.p, verbosity=args.verbosity)
    report(result)

    if args.p == 17:
        c_p17 = 3 * 8 / (17 * math.log(8))
        print()
        print(f"Reference: c(P(17)) = {c_p17:.6f}")
        if result["best_c"] <= c_p17 + 1e-9:
            print("RESULT: min_c ≤ c(P(17)) — consistent with P(17)-lift optimality on D_17.")
        else:
            print("RESULT: min_c > c(P(17)) — D_17 cyclic best is STRICTLY worse.")

    if args.save_db:
        written = _save_minimizers_to_db(
            result, source=args.db_source, filename=args.db_filename
        )
        print(f"DB: wrote {written} new record(s) "
              f"(source='{args.db_source}', file='{args.db_filename}').")
    return 0


if __name__ == "__main__":
    sys.exit(main())
