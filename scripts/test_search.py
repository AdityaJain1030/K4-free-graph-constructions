#!/usr/bin/env python3
"""
scripts/test_search_N.py
========================
Smoke test for the search_N framework.

- Runs BruteForce for n=4..9 and CirculantSearch for n=8..30,
  all under a single AggregateLogger.
- Saves every result into graph_db via Search.save().
- Reads everything back through the DB and prints a summary.

Run from repo root::

    python scripts/test_search_N.py
"""

import os
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from search_N import AggregateLogger, BruteForce, CirculantSearch
from graph_db import DB


BF_RANGE  = range(4, 10)       # inclusive 4..9
CIRC_RANGE = range(8, 31)      # inclusive 8..30
TOP_K = 3


def main() -> int:
    summary: list[tuple[str, int, int, float | None]] = []

    with AggregateLogger(name="smoke") as agg:
        # Brute force
        for n in BF_RANGE:
            t0 = time.monotonic()
            search = BruteForce(n=n, top_k=TOP_K, verbosity=1, parent_logger=agg)
            results = search.run()
            search.save(results)
            best = results[0].c_log if results else None
            dt = time.monotonic() - t0
            summary.append(("brute_force", n, len(results), best))
            print(f"[brute_force n={n:>2}] {len(results):>2} results, "
                  f"best c_log={_fmt(best)}, {dt:.2f}s")

        # Circulant
        for n in CIRC_RANGE:
            t0 = time.monotonic()
            search = CirculantSearch(n=n, top_k=TOP_K, verbosity=1, parent_logger=agg)
            results = search.run()
            search.save(results)
            best = results[0].c_log if results else None
            dt = time.monotonic() - t0
            summary.append(("circulant", n, len(results), best))
            print(f"[circulant   n={n:>2}] {len(results):>2} results, "
                  f"best c_log={_fmt(best)}, {dt:.2f}s")

    print()
    print("=" * 60)
    print("Summary")
    print("=" * 60)
    print(f"{'algo':<12}{'n':>4}{'k':>4}{'best c_log':>14}")
    for algo, n, k, c in summary:
        print(f"{algo:<12}{n:>4}{k:>4}{_fmt(c):>14}")

    # Read back via graph_db (auto-sync populates the cache)
    print()
    print("=" * 60)
    print("graph_db stats after ingest")
    print("=" * 60)
    with DB() as db:
        stats = db.stats()
        for k, v in stats.items():
            print(f"  {k}: {v}")

        print()
        print("Top 10 by c_log across all sources:")
        for r in db.top("c_log", k=10):
            print(f"  n={r['n']:>3}  source={r['source']:<12} "
                  f"c_log={_fmt(r['c_log']):>10}  alpha={r['alpha']}  d_max={r['d_max']}")

    return 0


def _fmt(x):
    if x is None:
        return "—"
    return f"{x:.6f}"


if __name__ == "__main__":
    sys.exit(main())
