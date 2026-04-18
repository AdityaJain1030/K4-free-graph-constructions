"""
k4free_enum.py
==============
Enumerates all non-isomorphic K4-free graphs for n in [min_n, max_n],
computes alpha (max independent set) for each, and reports:
  - the minimum alpha over all graphs with a given (n, d) pair
  - the full ground-truth table of unique (n, d, alpha) triples

where d = max degree of the graph.

Requires nauty (provides nauty-geng):
    Linux:   apt install nauty
    macOS:   brew install nauty

Storage
-------
Pass --save_pkl DIR to persist graphs.  The directory will contain one
file per n:

    DIR/k4free_n<N>.pkl

Each file is a dict:

    {
      "n": N,
      "format": "sparse6",
      "graphs": {
          (d, alpha): [sparse6_string, ...],   # list for each (d,a) bucket
          ...
      }
    }

Use k4free_explorer.py to query the stored graphs.
"""

import argparse
import itertools
import math
import os
import pickle
import shutil
import subprocess
import sys
import tempfile
import time
from collections import defaultdict

import networkx as nx

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.graph_props import alpha_exact_nx, is_k4_free_nx


# ---------------------------------------------------------------------------
# Maximum independent set (via utils)
# ---------------------------------------------------------------------------
def alpha(G: nx.Graph) -> int:
    """Exact maximum independent set size."""
    size, _ = alpha_exact_nx(G)
    return size


# ---------------------------------------------------------------------------
# K4-free check (via utils)
# ---------------------------------------------------------------------------
def is_k4_free(G: nx.Graph) -> bool:
    return is_k4_free_nx(G)


def iso_cert(G: nx.Graph) -> tuple:
    deg_seq = tuple(sorted(d for _, d in G.degree()))
    wl = nx.weisfeiler_lehman_graph_hash(G, iterations=4)
    return (deg_seq, wl)


# ---------------------------------------------------------------------------
# Graph generators
# ---------------------------------------------------------------------------
def find_geng() -> str | None:
    for name in ("geng", "nauty-geng"):
        path = shutil.which(name)
        if path:
            return path
    return None


def graphs_via_geng(geng: str, n: int):
    """
    Stream all non-isomorphic K4-free graphs on n vertices via nauty-geng.
    NOTE: no -c flag, so disconnected graphs are included.
    """
    with tempfile.NamedTemporaryFile(suffix=".g6", delete=False) as f:
        tmpfile = f.name
    try:
        # -k  = K4-free
        # NO -c so we include disconnected graphs
        subprocess.run(
            [geng, "-k", str(n), tmpfile],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        yield from nx.read_graph6(tmpfile)
    finally:
        os.unlink(tmpfile)


def graphs_via_python(n: int):
    """Pure-Python fallback (feasible up to n ~ 6)."""
    if n == 1:
        G = nx.Graph(); G.add_node(0); yield G; return
    nodes = list(range(n))
    all_edges = list(itertools.combinations(nodes, 2))
    cert_map: dict = {}
    for num_e in range(0, len(all_edges) + 1):
        for edge_set in itertools.combinations(all_edges, num_e):
            G = nx.Graph(); G.add_nodes_from(nodes); G.add_edges_from(edge_set)
            if not is_k4_free(G):
                continue
            cert = iso_cert(G)
            bucket = cert_map.setdefault(cert, [])
            if any(nx.is_isomorphic(G, H) for H in bucket):
                continue
            bucket.append(G.copy())
            yield G


# ---------------------------------------------------------------------------
# Sparse6 encoding helpers
# ---------------------------------------------------------------------------
def graph_to_sparse6(G: nx.Graph) -> str:
    """Encode graph as a sparse6 string (compact for sparse graphs)."""
    # nx.to_sparse6_bytes returns bytes like b':?...\n'
    # We decode and strip the trailing newline for clean storage.
    return nx.to_sparse6_bytes(G).decode("ascii").strip()


# ---------------------------------------------------------------------------
# Conjecture bound
# ---------------------------------------------------------------------------
def bound(n: int, d: int) -> float:
    if d <= 1:
        return float("inf")
    return n * math.log(d) / d


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--max_n", type=int, default=8)
    parser.add_argument("--min_n", type=int, default=4)
    parser.add_argument("--min_degree", type=int, default=1,
                        help="Skip graphs whose max-degree is below this (default: 1)")
    parser.add_argument("--save_pkl", metavar="DIR", default=None,
                        help="Directory to write per-n pkl files "
                             "(e.g. --save_pkl ./k4free_db).  "
                             "Creates DIR if it does not exist.")
    args = parser.parse_args()

    geng = find_geng()

    print("=" * 70)
    print("  K4-free graph enumeration (all graphs, including disconnected)")
    print(f"  n = {args.min_n} to {args.max_n}")
    print(f"  Goal: min alpha(G) for each (n, d) pair, d = max degree")
    if geng:
        print(f"  Backend: {geng}")
    else:
        print("  Backend: pure Python  (install nauty for n >= 7)")
    if args.save_pkl:
        print(f"  Storing graphs  -> {args.save_pkl}/k4free_n<N>.pkl")
    print("=" * 70)

    if args.save_pkl:
        os.makedirs(args.save_pkl, exist_ok=True)

    # min_alpha[(n, d)] = minimum alpha seen across all graphs with that (n,d)
    min_alpha: dict[tuple, int] = {}
    # all unique (n, d, alpha) triples -> count of graphs achieving it
    triple_count: dict[tuple, int] = defaultdict(int)
    graph_counts: dict[int, int] = {}

    for n in range(args.min_n, args.max_n + 1):
        t0 = time.time()
        print(f"\nn = {n}: ", end="", flush=True)

        gen = graphs_via_geng(geng, n) if geng else graphs_via_python(n)

        total = 0
        # per-n storage: {(d, alpha): [sparse6_str, ...]}
        pkl_data: dict[tuple, list] = defaultdict(list) if args.save_pkl else None

        for G in gen:
            total += 1
            d = max(deg for _, deg in G.degree())
            if d < args.min_degree:
                if pkl_data is not None:
                    # still store even if below min_degree? No — honour the filter.
                    pass
                continue
            a = alpha(G)
            key = (n, d)
            if key not in min_alpha or a < min_alpha[key]:
                min_alpha[key] = a
            triple_count[(n, d, a)] += 1

            if pkl_data is not None:
                pkl_data[(d, a)].append(graph_to_sparse6(G))

        graph_counts[n] = total
        elapsed = time.time() - t0
        print(f"{total} graphs in {elapsed:.2f}s")

        if args.save_pkl and pkl_data is not None:
            out_path = os.path.join(args.save_pkl, f"k4free_n{n}.pkl")
            payload = {
                "n": n,
                "format": "sparse6",
                "graphs": dict(pkl_data),   # {(d, alpha): [s6, ...]}
            }
            with open(out_path, "wb") as fh:
                pickle.dump(payload, fh, protocol=pickle.HIGHEST_PROTOCOL)
            stored = sum(len(v) for v in pkl_data.values())
            print(f"   -> saved {stored} graphs to {out_path}")

    # ------------------------------------------------------------------
    # Table 1: Min alpha per (n, d) — the main result
    # ------------------------------------------------------------------
    print()
    print("=" * 70)
    print("  MIN ALPHA PER (n, d) PAIR")
    print("  (minimum independent set size over all K4-free graphs with")
    print("   n vertices and max-degree d)")
    print("=" * 70)
    print(f"  {'n':>3}  {'d':>4}  {'min_alpha':>9}  {'bound n*ln(d)/d':>15}  {'ratio':>7}")
    print(f"  {'-'*55}")

    for (n, d), a in sorted(min_alpha.items()):
        b = bound(n, d)
        ratio = a / b if b < float("inf") else float("inf")
        print(f"  {n:>3}  {d:>4}  {a:>9}  {b:>15.4f}  {ratio:>7.4f}")

    # ------------------------------------------------------------------
    # Table 2: Full (n, d, alpha) triple listing with counts
    # ------------------------------------------------------------------
    print()
    print("=" * 70)
    print("  ALL (n, d, alpha) TRIPLES  [sorted by (n, d, alpha)]")
    print("  (#graphs = number of non-isomorphic K4-free graphs achieving")
    print("   this exact triple; min marker shows the minimum alpha for (n,d))")
    print("=" * 70)
    print(f"  {'n':>3}  {'d':>4}  {'alpha':>5}  {'#graphs':>7}  {'bound':>8}  {'ratio':>7}  note")
    print(f"  {'-'*60}")

    for (n, d, a), cnt in sorted(triple_count.items()):
        b = bound(n, d)
        ratio = a / b if b < float("inf") else float("inf")
        is_min = "  <-- min" if min_alpha.get((n, d)) == a else ""
        print(f"  {n:>3}  {d:>4}  {a:>5}  {cnt:>7}  {b:>8.4f}  {ratio:>7.4f}{is_min}")

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    print()
    print("=" * 70)
    print("  SUMMARY")
    print("=" * 70)
    for n, cnt in graph_counts.items():
        print(f"  n={n}: {cnt} non-isomorphic K4-free graphs")
    print(f"\n  Total graphs : {sum(graph_counts.values())}")
    print(f"  Unique (n,d) pairs: {len(min_alpha)}")
    print(f"  Unique (n,d,alpha) triples: {len(triple_count)}")

    violations = {(n, d): a for (n, d), a in min_alpha.items()
                  if bound(n, d) < float("inf") and a < bound(n, d)}
    if violations:
        print(f"\n  Violations of min_alpha >= n*ln(d)/d  (c=1): {len(violations)}")
        for (n, d), a in sorted(violations.items(), key=lambda x: x[1] / bound(*x[0])):
            print(f"    n={n}, d={d}: min_alpha={a}, bound={bound(n,d):.4f}, "
                  f"ratio={a/bound(n,d):.4f}")
    else:
        print(f"\n  No violations of min_alpha >= n*ln(d)/d  (c=1) found.")


if __name__ == "__main__":
    main()