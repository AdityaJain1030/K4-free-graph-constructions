"""
Ingest trivial k-copy disjoint-union lifts for n values where the frontier
is currently suboptimal. For each target n, find the best c_log graph at
the divisor n/k, replicate it k times as disjoint graphs, and add under
source='disjoint_lift'.

Usage:
    python scripts/ingest_disjoint_lifts.py           # scans automatically
    python scripts/ingest_disjoint_lifts.py --sync    # also run db.sync
"""
import argparse
import os
import sys
import sqlite3

import networkx as nx

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from graph_db import DB


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", default="cache.db")
    ap.add_argument("--sync", action="store_true")
    ap.add_argument("--nmax", type=int, default=120)
    ap.add_argument("--eps", type=float, default=5e-4)
    args = ap.parse_args()

    con = sqlite3.connect(args.cache)
    con.row_factory = sqlite3.Row

    # best c_log at each n, plus the winning graph_id+source
    cur = con.execute("""
        SELECT c.n, c.c_log, c.graph_id, c.source
        FROM cache c
        INNER JOIN (
            SELECT n, MIN(c_log) AS mc FROM cache
            WHERE is_k4_free=1 AND c_log IS NOT NULL GROUP BY n
        ) b ON c.n=b.n AND c.c_log=b.mc
        WHERE c.is_k4_free=1
    """)
    best_cell = {}
    for r in cur:
        best_cell.setdefault(r['n'], (r['c_log'], r['graph_id'], r['source']))
    best_c = {n: v[0] for n, v in best_cell.items()}

    def best_lift(n):
        lb, via = None, None
        for d in range(2, n+1):
            if n % d: continue
            sub = n // d
            if sub < 2 or sub not in best_c: continue
            if lb is None or best_c[sub] < lb:
                lb, via = best_c[sub], sub
        return lb, via

    db = DB()
    added_total = 0; skipped_total = 0
    for n in sorted(best_c.keys()):
        if n < 8 or n > args.nmax: continue
        lb, via = best_lift(n)
        if lb is None: continue
        cur_best = best_c[n]
        if cur_best <= lb + args.eps:
            continue  # connected or existing disc already achieves lift
        # we want to realize the best lift
        k = n // via
        _, gid, src = best_cell[via]
        Gsub = db.nx(gid)
        if Gsub is None or Gsub.number_of_nodes() != via:
            print(f"  [SKIP n={n}] could not load sub-graph {gid} at n={via}")
            continue
        # Build k disjoint copies
        G = nx.Graph()
        for i in range(k):
            offset = i * via
            for u, v in Gsub.edges():
                G.add_edge(u + offset, v + offset)
            for u in Gsub.nodes():
                G.add_node(u + offset)
        assert G.number_of_nodes() == n
        meta = {
            "lift_of_source": src,
            "lift_of_graph_id": gid,
            "lift_of_n": via,
            "lift_k": k,
            "lift_c_log_target": lb,
        }
        gid_new, was_new = db.add(G, source="disjoint_lift",
                                  filename="disjoint_lift.json", **meta)
        tag = "ADDED" if was_new else "DUP  "
        print(f"  [{tag}] n={n} = {k}×(n={via})  target c={lb:.4f}  "
              f"(was {cur_best:.4f})  id={gid_new[:10]}")
        if was_new: added_total += 1
        else: skipped_total += 1

    print(f"\nAdded {added_total} lifts, {skipped_total} duplicates.")

    if args.sync:
        print("\nSyncing source='disjoint_lift'…")
        res = db.sync(source="disjoint_lift", workers=4,
                      per_record_timeout_s=1800)
        print(res)


if __name__ == "__main__":
    main()
