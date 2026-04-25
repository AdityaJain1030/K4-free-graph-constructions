#!/usr/bin/env python3
"""
scripts/report_sat_near_regular_nonreg.py
==========================================
After running `run_sat_near_regular_nonreg.py`, summarise what landed:
per (n, α) how many iso classes, how many are genuinely new (only
sourced from `sat_near_regular_nonreg`), best c_log vs the frontier,
and how many beat or tie the frontier.

Run::

    micromamba run -n k4free python scripts/report_sat_near_regular_nonreg.py
"""

from __future__ import annotations

import os
import sys
from collections import defaultdict

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from graph_db import DB

SRC = "sat_near_regular_nonreg"


def main() -> int:
    with DB(auto_sync=False) as db:
        rows = db.query(source=SRC, order_by=['n', 'alpha', 'c_log'])
        if not rows:
            print(f"No rows under source={SRC!r}")
            return 0

        # Per-n frontier c_log (across all sources, excluding None)
        frontier = {r['n']: r for r in db.frontier(by='n', minimize='c_log')}

        # Cross-source map for each returned graph_id
        all_srcs: dict[str, set[str]] = defaultdict(set)
        for gid in {r['graph_id'] for r in rows}:
            for rec in db.get_all(gid):
                all_srcs[gid].add(rec['source'])

        by_na: dict[tuple[int, int], list[dict]] = defaultdict(list)
        for r in rows:
            by_na[(r['n'], r['alpha'])].append(r)

        print(f"{'n':>4}{'α':>4}{'iso':>5}{'unique':>8}{'best c':>10}"
              f"{'frontier':>11}{'Δ':>9}{'tied':>6}{'beat':>6}")
        print("=" * 75)

        totals = dict(rows=0, iso_unique_to_us=0, tied=0, beat=0)
        for (n, a), lst in sorted(by_na.items()):
            iso_ids = sorted({r['graph_id'] for r in lst})
            unique = [gid for gid in iso_ids
                      if all_srcs[gid] == {SRC}]
            best = min(r['c_log'] for r in lst if r['c_log'] is not None)
            fr = frontier.get(n)
            fr_c = fr['c_log'] if fr else None
            if fr_c is not None:
                delta = best - fr_c
                tied = sum(1 for r in lst
                           if r['c_log'] is not None
                           and abs(r['c_log'] - fr_c) < 1e-9)
                beat = sum(1 for r in lst
                           if r['c_log'] is not None
                           and r['c_log'] < fr_c - 1e-9)
            else:
                delta = None
                tied = beat = 0
            totals['rows'] += len(lst)
            totals['iso_unique_to_us'] += len(unique)
            totals['tied'] += tied
            totals['beat'] += beat
            delta_s = "—" if delta is None else f"{delta:+.4f}"
            fr_s = "—" if fr_c is None else f"{fr_c:.4f}"
            print(f"{n:>4}{a:>4}{len(iso_ids):>5}{len(unique):>8}"
                  f"{best:>10.4f}{fr_s:>11}{delta_s:>9}{tied:>6}{beat:>6}")

        print("=" * 75)
        print(f"TOTAL rows={totals['rows']} "
              f"new_iso_only_here={totals['iso_unique_to_us']} "
              f"tied_frontier={totals['tied']} "
              f"beat_frontier={totals['beat']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
