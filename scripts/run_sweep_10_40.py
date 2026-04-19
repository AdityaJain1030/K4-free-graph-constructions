#!/usr/bin/env python3
"""
scripts/run_sweep_10_40.py
==========================
One-off driver: run CirculantSearch, RandomSearch, RegularitySearch,
RegularityAlphaSearch for n=10..40 with top_k=1, saving the single best
result per (source, n) into graph_db.

Run from repo root::

    micromamba run -n k4free python scripts/run_sweep_10_40.py
"""

import os
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from search import (
    AggregateLogger,
    CirculantSearch,
    RandomSearch,
    RegularitySearch,
    RegularityAlphaSearch,
)


N_RANGE = range(10, 41)
TOP_K = 1
METHODS = [
    ("circulant",         CirculantSearch),
    ("random",            RandomSearch),
    ("regularity",        RegularitySearch),
    ("regularity_alpha",  RegularityAlphaSearch),
]


def _fmt(x):
    return "—" if x is None else f"{x:.6f}"


def main() -> int:
    all_summary: dict[str, list] = {m: [] for m, _ in METHODS}

    for method_name, cls in METHODS:
        print(f"\n===== {method_name} =====", flush=True)
        with AggregateLogger(name=f"{method_name}_sweep_10_40") as agg:
            for n in N_RANGE:
                t0 = time.monotonic()
                search = cls(n=n, top_k=TOP_K, verbosity=1, parent_logger=agg)
                results = search.run()
                if results:
                    search.save(results)
                dt = time.monotonic() - t0
                if results:
                    best = results[0]
                    all_summary[method_name].append(
                        (n, best.c_log, best.alpha, best.d_max, dt)
                    )
                    print(f"[{method_name} n={n:>2}] "
                          f"c={_fmt(best.c_log)}  α={best.alpha}  "
                          f"d_max={best.d_max}  ({dt:.2f}s)",
                          flush=True)
                else:
                    all_summary[method_name].append((n, None, 0, 0, dt))
                    print(f"[{method_name} n={n:>2}] no results  ({dt:.2f}s)",
                          flush=True)

    # pooled summary
    print()
    print("=" * 84)
    hdr = f"{'n':>4}"
    for m, _ in METHODS:
        hdr += f"{m:>18}"
    print(hdr)
    print("=" * 84)
    for n in N_RANGE:
        row = f"{n:>4}"
        for m, _ in METHODS:
            entry = next((s for s in all_summary[m] if s[0] == n), None)
            c = entry[1] if entry else None
            row += f"{_fmt(c):>18}"
        print(row)
    return 0


if __name__ == "__main__":
    sys.exit(main())
