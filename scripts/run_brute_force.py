"""
scripts/run_brute_force.py
==========================
Run BruteForce search for n in [n_min, n_max] and save results to graph_db.
Only practical for n ≤ 10.

Usage:
    python scripts/run_brute_force.py
    python scripts/run_brute_force.py --n_min 4 --n_max 8
    python scripts/run_brute_force.py --n_max 10 --top_k 3
"""

import argparse
import os
import sys
import atexit

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from search_N import BruteForce
from graph_db import DB

REPO_ROOT  = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GRAPHS_DIR = os.path.join(REPO_ROOT, "graphs")
CACHE_DB   = os.path.join(REPO_ROOT, "cache.db")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--n_min", type=int, default=4)
    p.add_argument("--n_max", type=int, default=BruteForce.MAX_N)
    p.add_argument("--top_k", type=int, default=1,
                   help="Number of graphs to keep per n (default 1 = best only)")
    args = p.parse_args()

    n_max = min(args.n_max, BruteForce.MAX_N)
    saved_any = False

    for n in range(args.n_min, n_max + 1):
        print(f"\n=== BruteForce  n={n} ===")
        searcher = BruteForce(n=n, top_k=args.top_k)
        graphs = searcher.run()
        if not graphs:
            print("  No results")
            continue
        for rank, G in enumerate(graphs, 1):
            c = BruteForce.c_log(G)
            d_max = max(d for _, d in G.degree())
            gid, was_new = searcher.save(
                G,
                filename="brute_force.json",
                rank=rank,
                c_log=round(c, 6) if c else None,
                d_max=d_max,
            )
            status = "NEW  " if was_new else "exists"
            print(f"  [{status}] id={gid[:10]}  c_log={c:.6f}  d_max={d_max}  rank={rank}")
            saved_any = True

    if saved_any:
        print("\nSyncing cache...")
        with DB(GRAPHS_DIR, CACHE_DB, auto_sync=False) as db:
            db.sync(verbose=True)
    print("\nDone.")


if __name__ == "__main__":
    main()
    os._exit(0)  # force exit — OR-Tools background threads otherwise hang the process
