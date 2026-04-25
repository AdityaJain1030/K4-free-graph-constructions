"""
Ingest K4-free Ramsey lower-bound constructions from DeepMind's
ramsey_number_bounds/improved_bounds directory into graph_db as
source="deepmind_ramsey".

Upstream: https://github.com/google-research/google-research/tree/master/ramsey_number_bounds/improved_bounds

Each R(4, s) >= n.txt file holds the printed NumPy adjacency matrix of
an (n-1)-vertex K4-free graph with α < s.

Usage:
    python scripts/ingest_deepmind_ramsey.py [--dir /tmp/deepmind_ramsey] [--sync]
"""
import argparse
import os
import re
import sys

import numpy as np
import networkx as nx

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from graph_db import DB


FNAME_RE = re.compile(r"R\(4,(\d+)\)_ge(\d+)\.txt$")


def parse_matrix(text: str) -> np.ndarray:
    """NumPy's 2-D array print-format → ndarray. Strip [ ] and newlines."""
    cleaned = re.sub(r"[\[\]]", " ", text)
    nums = cleaned.split()
    vals = [int(x) for x in nums]
    n = int(round(len(vals) ** 0.5))
    assert n * n == len(vals), f"Non-square count {len(vals)}"
    return np.asarray(vals, dtype=np.int8).reshape(n, n)


def has_k4(G: nx.Graph) -> bool:
    """Exact K4 check: any triangle with a common 4th vertex among all three."""
    for u, v, w in ((u, v, w) for u in G for v in G[u] if v > u
                              for w in G[u] if w > v and G.has_edge(v, w)):
        common = set(G[u]) & set(G[v]) & set(G[w])
        if any(x > w for x in common):
            return True
    return False


def validate(adj: np.ndarray, expected_s: int) -> tuple[nx.Graph, dict]:
    n = adj.shape[0]
    if not np.array_equal(adj, adj.T):
        raise ValueError("matrix is not symmetric")
    if adj.diagonal().any():
        raise ValueError("non-zero diagonal (self-loops)")
    if set(np.unique(adj).tolist()) - {0, 1}:
        raise ValueError("entries not 0/1")
    G = nx.from_numpy_array(adj)
    if has_k4(G):
        raise ValueError("contains a K4 (not K4-free)")
    info = {"n": n, "m": G.number_of_edges(),
            "d_min": min(dict(G.degree()).values()),
            "d_max": max(dict(G.degree()).values()),
            "alpha_upper_bound_claimed": expected_s - 1}
    return G, info


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="/tmp/deepmind_ramsey")
    ap.add_argument("--sync", action="store_true",
                    help="Run db.sync(source=...) after ingest.")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--timeout", type=float, default=1800,
                    help="Per-record sync timeout (seconds).")
    args = ap.parse_args()

    files = []
    for fn in sorted(os.listdir(args.dir)):
        m = FNAME_RE.search(fn)
        if not m:
            continue
        files.append((int(m.group(1)), int(m.group(2)), fn))

    if not files:
        sys.exit(f"No R(4,*)_ge*.txt files found in {args.dir}")

    db = DB()
    added = skipped = 0
    for s, bound, fn in files:
        path = os.path.join(args.dir, fn)
        with open(path) as f:
            text = f.read()
        adj = parse_matrix(text)
        G, info = validate(adj, expected_s=s)
        expected_n = bound - 1
        assert info["n"] == expected_n, (
            f"{fn}: filename claims n={expected_n}, matrix is n={info['n']}")
        meta = {
            "origin": "google-research/ramsey_number_bounds/improved_bounds",
            "ramsey_claim": f"R(4,{s}) >= {bound}",
            "ramsey_s": s,
            "ramsey_bound_n": bound,
            "alpha_upper_bound_claimed": info["alpha_upper_bound_claimed"],
            "d_max_input": info["d_max"],
            "d_min_input": info["d_min"],
            "m_input": info["m"],
        }
        gid, was_new = db.add(G, source="deepmind_ramsey",
                              filename="deepmind_ramsey.json", **meta)
        tag = "ADDED" if was_new else "DUP  "
        print(f"  [{tag}] R(4,{s})>={bound}  n={info['n']} m={info['m']}  "
              f"d∈[{info['d_min']},{info['d_max']}]  α<{s}  id={gid}")
        if was_new:
            added += 1
        else:
            skipped += 1

    print(f"\nIngest complete: {added} added, {skipped} duplicates.")

    if args.sync:
        print(f"\nSyncing source='deepmind_ramsey' "
              f"(workers={args.workers}, timeout={args.timeout}s)…")
        res = db.sync(source="deepmind_ramsey",
                      workers=args.workers,
                      per_record_timeout_s=args.timeout)
        print(res)


if __name__ == "__main__":
    main()
