#!/usr/bin/env python3
"""
scripts/run_cayley.py
=====================
Run CayleyResidueSearch across primes p in [5, 200] under one
AggregateLogger. Saves K4-free residue-Cayley graphs into graph_db
(source='cayley') and prints a per-p summary.

Each p is tried under k ∈ {2, 3, 6} — only eligible (p ≡ 1 mod 2k)
combinations produce a graph. Non-prime n and ineligible primes are
silent no-ops.

Run from repo root::

    micromamba run -n k4free python scripts/run_cayley.py
"""

import os
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from search import AggregateLogger, CayleyResidueSearch


P_RANGE = range(5, 201)
RESIDUE_INDICES = (2, 3, 6)
TOP_K = 3


def _fmt(x):
    return "—" if x is None else f"{x:.6f}"


def main() -> int:
    rows: list[tuple[int, int, float | None, int, int, int, float]] = []

    with AggregateLogger(name="cayley_sweep") as agg:
        for p in P_RANGE:
            t0 = time.monotonic()
            search = CayleyResidueSearch(
                n=p,
                top_k=TOP_K,
                verbosity=1,
                parent_logger=agg,
                residue_indices=RESIDUE_INDICES,
            )
            results = search.run()
            if results:
                search.save(results)
            dt = time.monotonic() - t0
            for r in results:
                k = r.metadata.get("residue_index")
                rows.append((p, k, r.c_log, r.alpha, r.d_max, int(r.is_k4_free), dt))
                print(
                    f"[cayley p={p:>3} k={k}] "
                    f"c={_fmt(r.c_log)}  α={r.alpha}  d_max={r.d_max}  "
                    f"k4free={int(r.is_k4_free)}  ({dt:.2f}s)",
                    flush=True,
                )

    print()
    print("=" * 72)
    print(f"{'p':>4}{'k':>4}{'c_log':>14}{'alpha':>8}{'d_max':>7}{'k4f':>5}{'t(s)':>9}")
    print("=" * 72)
    for p, k, c, a, d, kf, dt in rows:
        print(f"{p:>4}{k:>4}{_fmt(c):>14}{a:>8}{d:>7}{kf:>5}{dt:>9.2f}")
    if not rows:
        print("  (no eligible (p, k) produced a graph)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
