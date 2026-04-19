"""
scripts/run_circulant.py
========================
Run CirculantSearch for n in [n_min, n_max] and save results to graph_db.

Usage:
    # Save best circulant for each n:
    python scripts/run_circulant.py

    # Save top-5 per n, n from 5 to 35:
    python scripts/run_circulant.py --n_min 5 --n_max 35 --top_k 5

    # Show top-10 for a single n without saving:
    python scripts/run_circulant.py --n 17 --top_k 10 --show_only

    # Verify against reference CSV (prints c_log for all n ≤ 35):
    python scripts/run_circulant.py --n_max 35 --show_only --top_k 1
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from search_N import CirculantSearch
from graph_db import DB

REPO_ROOT  = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GRAPHS_DIR = os.path.join(REPO_ROOT, "graphs")
CACHE_DB   = os.path.join(REPO_ROOT, "cache.db")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--n_min", type=int, default=5)
    p.add_argument("--n_max", type=int, default=CirculantSearch.MAX_N)
    p.add_argument("--n", type=int, default=None,
                   help="Single n value (overrides n_min/n_max)")
    p.add_argument("--top_k", type=int, default=1,
                   help="Number of graphs to keep per n (default 1 = best only)")
    p.add_argument("--show_only", action="store_true",
                   help="Print results without saving to graph_db")
    args = p.parse_args()

    n_range = (
        [args.n] if args.n
        else range(args.n_min, min(args.n_max, CirculantSearch.MAX_N) + 1)
    )
    saved_any = False

    for n in n_range:
        if args.show_only:
            print(f"\n=== n={n} ===")
            top = CirculantSearch.top_k_circulants(n, k=args.top_k)
            if not top:
                print("  No valid K4-free circulants found")
                continue
            for i, entry in enumerate(top, 1):
                print(
                    f"  #{i}  conn={list(entry['connection_set'])}  "
                    f"d={entry['d']}  alpha={entry['alpha']}  "
                    f"c_log={entry['c_log']:.6f}"
                )
        else:
            print(f"\n=== CirculantSearch  n={n} ===")
            searcher = CirculantSearch(n=n, top_k=args.top_k)
            graphs = searcher.run()
            if not graphs:
                print("  No results")
                continue
            for rank, G in enumerate(graphs, 1):
                c     = CirculantSearch.c_log(G)
                d_max = max(d for _, d in G.degree())
                conn  = G.graph.get("connection_set", [])
                gid, was_new = searcher.save(
                    G,
                    filename="circulant.json",
                    rank=rank,
                    connection_set=conn,
                    c_log=round(c, 6) if c else None,
                    d_max=d_max,
                )
                status = "NEW  " if was_new else "exists"
                print(
                    f"  [{status}] id={gid[:10]}  conn={conn}  "
                    f"d={d_max}  c_log={c:.6f}  rank={rank}"
                )
                saved_any = True

    if saved_any:
        print("\nSyncing cache...")
        with DB(GRAPHS_DIR, CACHE_DB, auto_sync=False) as db:
            db.sync(verbose=True)
    print("\nDone.")


if __name__ == "__main__":
    main()
