#!/usr/bin/env python3
"""
scripts/verify_p17_lift.py
==========================
Exhaustive Cayley-on-Z_n verification of the P(17)-lift conjecture
(see docs/theory/P17_LIFT_OPTIMALITY.md).

For n ∈ {17, 34} we enumerate every symmetric connection set
S ⊆ Z_n \\ {0}, build Cay(Z_n, S), and for the K₄-free ones compute
exact α (via alpha_bb_clique_cover, leveraging vertex-transitivity).
We report:

  * the minimum c_log achieved,
  * every S (up to Z_n* multiplication) that attains it,
  * confirmation that the k-lift of P(17) is among the minimizers
    (for n = 34).

Run::

    micromamba run -n k4free python scripts/verify_p17_lift.py --n 17
    micromamba run -n k4free python scripts/verify_p17_lift.py --n 34
"""

from __future__ import annotations

import argparse
import math
import os
import sys
import time
from itertools import product
from math import gcd

import networkx as nx
import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from graph_db import DEFAULT_GRAPHS, GraphStore
from utils.graph_props import is_k4_free, alpha_bb_clique_cover


def _enumerate_symmetric_subsets(n: int):
    """Yield every symmetric S ⊆ Z_n \\ {0} as a frozenset.

    Uses a bit-index representation over the 'positive half':
      pairs {k, n-k} for k = 1..⌊(n-1)/2⌋,  plus the self-inverse {n/2}
      when n is even.
    """
    pairs = [(k, n - k) for k in range(1, (n // 2) + (0 if n % 2 == 0 else 1))]
    self_inv = [n // 2] if n % 2 == 0 else []
    n_slots = len(pairs) + len(self_inv)
    for bits in range(1 << n_slots):
        S = []
        for i, (a, b) in enumerate(pairs):
            if (bits >> i) & 1:
                S.append(a)
                S.append(b)
        for j, s in enumerate(self_inv):
            if (bits >> (len(pairs) + j)) & 1:
                S.append(s)
        yield frozenset(S)


def _enumerate_symmetric_bitmasks(n: int):
    """Yield every symmetric S ⊆ Z_n \\ {0} as a Python int bitmask.

    Bit i is set iff i ∈ S. Ten-ish times faster than the frozenset
    variant; consumers that only need symmetric comparison benefit.
    """
    pairs = [(k, n - k) for k in range(1, (n // 2) + (0 if n % 2 == 0 else 1))]
    self_inv = [n // 2] if n % 2 == 0 else []
    slot_masks = []
    for a, b in pairs:
        slot_masks.append((1 << a) | (1 << b))
    for s in self_inv:
        slot_masks.append(1 << s)
    n_slots = len(slot_masks)
    for bits in range(1 << n_slots):
        mask = 0
        x = bits
        i = 0
        while x:
            if x & 1:
                mask |= slot_masks[i]
            x >>= 1
            i += 1
        yield mask


def _apply_unit_to_bitmask(mask: int, u: int, n: int) -> int:
    """Return bitmask of { (u*s) mod n : s ∈ S } given S's bitmask."""
    out = 0
    x = mask
    s = 0
    while x:
        if x & 1:
            out |= 1 << ((u * s) % n)
        x >>= 1
        s += 1
    return out


def _bitmask_to_set(mask: int) -> frozenset[int]:
    S = []
    x = mask
    s = 0
    while x:
        if x & 1:
            S.append(s)
        x >>= 1
        s += 1
    return frozenset(S)


def _is_lex_min_under_units(mask: int, unit_mult_tables: list[list[int]]) -> bool:
    """Check whether `mask` is the numerically smallest of {u·mask : u ∈ units}.

    Early-exits as soon as some u·mask < mask.

    `unit_mult_tables[i][s] = (u_i * s) % n` precomputed per unit for speed.
    """
    for table in unit_mult_tables:
        # Compute u*mask: for each set bit s, set bit table[s].
        out = 0
        x = mask
        s = 0
        while x:
            if x & 1:
                out |= 1 << table[s]
            x >>= 1
            s += 1
        if out < mask:
            return False
    return True


def _build_cayley_adj(n: int, S: frozenset[int]) -> np.ndarray:
    """Cay(Z_n, S). Assumes S is symmetric."""
    adj = np.zeros((n, n), dtype=np.uint8)
    S = np.fromiter(S, dtype=np.int64)
    if S.size == 0:
        return adj
    for i in range(n):
        js = (i + S) % n
        adj[i, js] = 1
    return adj


def _units_mod_n(n: int) -> list[int]:
    return [u for u in range(1, n) if gcd(u, n) == 1]


def _canonical_rep(S: frozenset[int], n: int, units: list[int]) -> frozenset[int]:
    """Canonical (Z_n)*-orbit representative: lex-min over u·S mod n."""
    best = None
    for u in units:
        Su = frozenset((u * s) % n for s in S)
        key = tuple(sorted(Su))
        if best is None or key < best[0]:
            best = (key, Su)
    return best[1]


def _c_log(alpha: int, d_max: int, n: int) -> float:
    if d_max <= 1:
        return math.inf
    return alpha * d_max / (n * math.log(d_max))


def _lift_connection_set(k: int) -> frozenset[int] | None:
    """Return the CRT image of {0}×QR_17 in Z_{17k}, i.e. the k-lift of P(17).

    Requires gcd(k, 17) = 1.
    """
    if gcd(k, 17) != 1:
        return None
    QR_17 = {1, 2, 4, 8, 9, 13, 15, 16}
    n = 17 * k
    # CRT: (i mod k, x mod 17)  <->  (17·i·a + k·x·b) mod n, where
    #   a = 17^{-1} mod k,  b = k^{-1} mod 17.
    # For i=0 and x ∈ QR_17, the image is (k·x·b) mod n.
    if k == 1:
        return frozenset(QR_17)
    b = pow(k, -1, 17)
    return frozenset((k * x * b) % n for x in QR_17)


def scan(n: int, *, verbosity: int = 1, progress_every: int = 500_000) -> dict:
    """Stream symmetric subsets of Z_n, computing c for each K₄-free Cayley
    graph. Uses inline lex-min orbit pruning under (Z_n)*: only one
    representative per orbit passes the K₄/α tests. Typical speedup vs
    naive streaming is roughly |(Z_n)*|× minus small constant overhead.
    """
    units = _units_mod_n(n)
    pairs = [(k, n - k) for k in range(1, (n // 2) + (0 if n % 2 == 0 else 1))]
    self_inv = [n // 2] if n % 2 == 0 else []
    total_subsets = 1 << (len(pairs) + len(self_inv))

    # Precompute (u*s) mod n tables so the lex-min check is a tight loop.
    unit_mult_tables = [[(u * s) % n for s in range(n)] for u in units]

    if verbosity:
        print(f"[N={n}] enumerating {total_subsets:,} symmetric subsets "
              f"(|(Z_{n})*| = {len(units)}, mode: lex-min orbit pruning)",
              flush=True)

    best_c = math.inf
    best_rows: list[tuple[float, int, int, frozenset[int]]] = []
    n_k4free = 0
    n_examined = 0
    n_orbit_reps = 0
    t0 = time.monotonic()

    for mask in _enumerate_symmetric_bitmasks(n):
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
        if not _is_lex_min_under_units(mask, unit_mult_tables):
            continue
        n_orbit_reps += 1

        S = _bitmask_to_set(mask)
        adj = _build_cayley_adj(n, S)
        d_max = int(adj.sum(axis=1).max()) if S else 0
        if d_max < 2:
            continue
        if not is_k4_free(adj):
            continue
        alpha, _indep = alpha_bb_clique_cover(adj)
        c = _c_log(alpha, d_max, n)
        n_k4free += 1

        if c < best_c - 1e-9:
            best_c = c
            best_rows = [(c, alpha, d_max, S)]
        elif abs(c - best_c) < 1e-9:
            best_rows.append((c, alpha, d_max, S))

    dt = time.monotonic() - t0
    if verbosity:
        print(f"[N={n}] examined {n_examined:,}, orbits {n_orbit_reps:,}, "
              f"K₄-free {n_k4free:,}, elapsed {dt:.1f}s",
              flush=True)

    minimizers = list(best_rows)

    return {
        "n": n,
        "total_subsets": total_subsets,
        "orbits_examined": n_orbit_reps,
        "k4_free_count": n_k4free,
        "best_c": best_c,
        "minimizers": minimizers,
        "elapsed_s": dt,
    }


def report(result: dict) -> None:
    n = result["n"]
    print()
    print(f"=== N = {n} ===")
    print(f"Symmetric subsets enumerated:   {result['total_subsets']:,}")
    if result.get("orbits_examined") is not None:
        print(f"Distinct (Z_{n})*-orbits:         {result['orbits_examined']:,}")
    print(f"K₄-free orbits found:           {result['k4_free_count']:,}")
    print(f"Min c_log over Cay(Z_{n}, ·):     {result['best_c']:.6f}")

    minimizers = result["minimizers"]
    print(f"Number of minimizers (orbits):  {len(minimizers)}")
    for i, (c, a, d, S) in enumerate(minimizers[:8]):
        Sl = sorted(S)
        print(f"  [{i}] S = {Sl}")
        print(f"      α = {a},  d_max = {d},  c = {c:.6f}")

    if n % 17 == 0:
        k = n // 17
        lift_S = _lift_connection_set(k)
        if lift_S is not None:
            units = _units_mod_n(n)
            # Build the full (Z_n)* orbit of the lift connection set.
            lift_orbit = set()
            for u in units:
                uS = frozenset((u * s) % n for s in lift_S)
                lift_orbit.add(tuple(sorted(uS)))
            minimizer_keys = {tuple(sorted(S)) for (_, _, _, S) in minimizers}
            if lift_orbit & minimizer_keys:
                print(f"  [lift] k={k} lift of P(17) IS a minimizer ✓")
            else:
                print(f"  [lift] k={k} lift of P(17) is NOT a minimizer — "
                      "evaluating lift directly:")
                adj = _build_cayley_adj(n, lift_S)
                d = int(adj.sum(axis=1).max())
                a, _ = alpha_bb_clique_cover(adj)
                c = _c_log(a, d, n)
                print(f"         S = {sorted(lift_S)}")
                print(f"         α = {a}, d_max = {d}, c = {c:.6f}")


def _save_minimizers_to_db(result: dict, source: str, filename: str) -> int:
    """Persist each minimizer's Cayley graph to graph_db with a certificate
    that it is the exact minimum of c over Cay(Z_n, ·), up to (Z_n)* action.

    Returns number of new records written (already-present ids are skipped).
    """
    n = result["n"]
    store = GraphStore(DEFAULT_GRAPHS)
    written = 0
    for c, a, d, S in result["minimizers"]:
        adj = _build_cayley_adj(n, S)
        G = nx.from_numpy_array(np.asarray(adj, dtype=np.uint8))
        _, is_new = store.add_graph(
            G, source=source, filename=filename,
            n=n,
            alpha=int(a),
            d_max=int(d),
            c_log=float(c),
            group="cyclic",
            connection_set=sorted(int(s) for s in S),
            orbits_examined=int(result["orbits_examined"]),
            k4_free_orbits=int(result["k4_free_count"]),
            certificate="exact cyclic Cayley minimum, verified by exhaustive "
                        "(Z_n)*-orbit enumeration",
        )
        if is_new:
            written += 1
    return written


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=17,
                    help="cyclic order (17 or 34 recommended; 51+ is slow)")
    ap.add_argument("--verbosity", type=int, default=1)
    ap.add_argument("--save-db", action="store_true",
                    help="Persist the minimizer graph(s) to graph_db under "
                         "source='cyclic_exhaustive_min'.")
    ap.add_argument("--db-source", default="cyclic_exhaustive_min",
                    help="graph_db source tag for persisted records.")
    ap.add_argument("--db-filename", default="cyclic_exhaustive_min.json",
                    help="graph_db filename for persisted records.")
    args = ap.parse_args()

    result = scan(args.n, verbosity=args.verbosity)
    report(result)

    # Reference: target c_log from P(17).
    c_p17 = 3 * 8 / (17 * math.log(8))
    print()
    print(f"Reference: c(P(17)) = {c_p17:.6f}")
    if result["best_c"] <= c_p17 + 1e-9:
        print("RESULT: min_c ≤ c(P(17)) — consistent with lift-optimality.")
    else:
        print("RESULT: min_c > c(P(17)) — this N's cyclic best is STRICTLY worse.")

    if args.save_db:
        written = _save_minimizers_to_db(
            result, source=args.db_source, filename=args.db_filename
        )
        print(f"DB: wrote {written} new record(s) "
              f"(source='{args.db_source}', file='{args.db_filename}').")
    return 0


if __name__ == "__main__":
    sys.exit(main())
