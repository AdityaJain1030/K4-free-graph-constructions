"""
k4free_explorer.py
==================
Query interface for the K4-free graph database produced by k4free_enum.py
with the --save_pkl flag.

Usage examples
--------------
# List all (n, d, alpha) triples and graph counts in the database
python k4free_explorer.py --db ./k4free_db --list

# Fetch all graphs with n=7, d=4, alpha=2  (exact match on all three)
python k4free_explorer.py --db ./k4free_db --n 7 --d 4 --alpha 2

# Fetch all graphs with n=8, alpha=3  (any d)
python k4free_explorer.py --db ./k4free_db --n 8 --alpha 3

# Fetch all graphs with d=5  (any n, any alpha)
python k4free_explorer.py --db ./k4free_db --d 5

# Limit output to the first 10 matches
python k4free_explorer.py --db ./k4free_db --n 7 --d 4 --alpha 2 --limit 10

# Print adjacency matrices in dense numpy format instead of edge-list
python k4free_explorer.py --db ./k4free_db --n 6 --d 3 --alpha 2 --format numpy

# Export matching graphs to a CSV of edge-lists
python k4free_explorer.py --db ./k4free_db --n 6 --d 3 --alpha 2 --export matches.csv

Output formats
--------------
  edgelist (default)  — one line per edge: "u v"
  numpy               — dense 0/1 adjacency matrix rows
  sparse6             — raw sparse6 string (compact, for piping)
  summary             — just print (n, d, alpha, #nodes, #edges) per graph

Storage layout (written by k4free_enum.py --save_pkl DIR)
----------------------------------------------------------
  DIR/k4free_n<N>.pkl   — one file per n value

  Each pkl contains a dict:
    {
      "n":      int,
      "format": "sparse6",
      "graphs": { (d, alpha): [sparse6_str, ...], ... }
    }
"""

import argparse
import glob
import os
import pickle
import sys
from typing import Iterator

import networkx as nx
import numpy as np


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def shard_path(db_dir: str, n: int) -> str:
    return os.path.join(db_dir, f"k4free_n{n}.pkl")


def available_ns(db_dir: str) -> list[int]:
    """Return sorted list of n values that have a shard file in db_dir."""
    paths = glob.glob(os.path.join(db_dir, "k4free_n*.pkl"))
    ns = []
    for p in paths:
        base = os.path.basename(p)
        try:
            n = int(base.replace("k4free_n", "").replace(".pkl", ""))
            ns.append(n)
        except ValueError:
            pass
    return sorted(ns)


def load_shard(db_dir: str, n: int) -> dict | None:
    path = shard_path(db_dir, n)
    if not os.path.exists(path):
        return None
    with open(path, "rb") as fh:
        return pickle.load(fh)


def s6_to_graph(s6: str) -> nx.Graph:
    """Decode a sparse6 string back to a NetworkX graph."""
    return nx.from_sparse6_bytes(s6.encode("ascii"))


# ---------------------------------------------------------------------------
# Listing / inventory
# ---------------------------------------------------------------------------

def cmd_list(db_dir: str):
    ns = available_ns(db_dir)
    if not ns:
        print(f"No shard files found in '{db_dir}'.")
        return

    print(f"{'n':>4}  {'d':>4}  {'alpha':>5}  {'#graphs':>9}")
    print("-" * 30)
    total = 0
    for n in ns:
        shard = load_shard(db_dir, n)
        if shard is None:
            continue
        for (d, a), lst in sorted(shard["graphs"].items()):
            cnt = len(lst)
            print(f"  {n:>3}  {d:>4}  {a:>5}  {cnt:>9}")
            total += cnt
    print("-" * 30)
    print(f"  Total stored graphs: {total}")


# ---------------------------------------------------------------------------
# Query + decode
# ---------------------------------------------------------------------------

def iter_matches(
    db_dir: str,
    n_filter: int | None,
    d_filter: int | None,
    alpha_filter: int | None,
) -> Iterator[tuple[int, int, int, nx.Graph]]:
    """
    Yield (n, d, alpha, G) for every stored graph that matches the filters.
    Any filter left as None matches everything.
    """
    if n_filter is not None:
        ns = [n_filter] if os.path.exists(shard_path(db_dir, n_filter)) else []
    else:
        ns = available_ns(db_dir)

    for n in ns:
        shard = load_shard(db_dir, n)
        if shard is None:
            continue
        for (d, a), s6_list in shard["graphs"].items():
            if d_filter is not None and d != d_filter:
                continue
            if alpha_filter is not None and a != alpha_filter:
                continue
            for s6 in s6_list:
                yield n, d, a, s6_to_graph(s6)


# ---------------------------------------------------------------------------
# Display / export
# ---------------------------------------------------------------------------

def adjacency_matrix(G: nx.Graph) -> np.ndarray:
    nodes = sorted(G.nodes())
    idx = {v: i for i, v in enumerate(nodes)}
    n = len(nodes)
    mat = np.zeros((n, n), dtype=np.int8)
    for u, v in G.edges():
        mat[idx[u], idx[v]] = 1
        mat[idx[v], idx[u]] = 1
    return mat


def print_graph(i: int, n: int, d: int, a: int, G: nx.Graph, fmt: str):
    print(f"\n--- Graph #{i}  n={n}  d={d}  alpha={a}  "
          f"nodes={G.number_of_nodes()}  edges={G.number_of_edges()} ---")

    if fmt == "edgelist":
        edges = sorted(G.edges())
        if edges:
            for u, v in edges:
                print(f"  {u} -- {v}")
        else:
            print("  (no edges)")

    elif fmt == "numpy":
        mat = adjacency_matrix(G)
        for row in mat:
            print("  " + " ".join(str(x) for x in row))

    elif fmt == "sparse6":
        s6 = nx.to_sparse6_bytes(G).decode("ascii").strip()
        print(f"  {s6}")

    elif fmt == "summary":
        pass   # header line already printed above


def export_csv(
    db_dir: str,
    n_filter, d_filter, alpha_filter,
    out_path: str,
    limit: int | None,
):
    """Write matching graphs to a CSV with columns: graph_id,n,d,alpha,u,v"""
    import csv
    count = 0
    with open(out_path, "w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["graph_id", "n", "d", "alpha", "u", "v"])
        for n, d, a, G in iter_matches(db_dir, n_filter, d_filter, alpha_filter):
            count += 1
            gid = count
            for u, v in sorted(G.edges()):
                writer.writerow([gid, n, d, a, u, v])
            if limit and count >= limit:
                break
    print(f"Exported {count} graphs to '{out_path}'.")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Query the K4-free graph database produced by k4free_enum.py."
    )
    parser.add_argument("--db", required=True, metavar="DIR",
                        help="Directory containing k4free_n<N>.pkl shard files.")

    # Filters
    parser.add_argument("--n", type=int, default=None,
                        help="Filter by number of vertices.")
    parser.add_argument("--d", type=int, default=None,
                        help="Filter by max degree.")
    parser.add_argument("--alpha", type=int, default=None,
                        help="Filter by independence number.")

    # Actions
    parser.add_argument("--list", action="store_true",
                        help="List all (n, d, alpha) triples and counts "
                             "in the database, then exit.")
    parser.add_argument("--count", action="store_true",
                        help="Print only the number of matching graphs.")
    parser.add_argument("--export", metavar="FILE", default=None,
                        help="Export matching graphs to a CSV file.")

    # Output control
    parser.add_argument("--format", choices=["edgelist", "numpy", "sparse6", "summary"],
                        default="edgelist",
                        help="Adjacency representation for printed graphs "
                             "(default: edgelist).")
    parser.add_argument("--limit", type=int, default=None,
                        help="Stop after this many matching graphs.")

    args = parser.parse_args()

    if not os.path.isdir(args.db):
        print(f"Error: database directory '{args.db}' does not exist.", file=sys.stderr)
        sys.exit(1)

    # ---- list mode --------------------------------------------------------
    if args.list:
        cmd_list(args.db)
        return

    # ---- export mode ------------------------------------------------------
    if args.export:
        export_csv(args.db, args.n, args.d, args.alpha, args.export, args.limit)
        return

    # ---- count mode -------------------------------------------------------
    if args.count:
        total = sum(1 for _ in iter_matches(args.db, args.n, args.d, args.alpha))
        filters = []
        if args.n is not None: filters.append(f"n={args.n}")
        if args.d is not None: filters.append(f"d={args.d}")
        if args.alpha is not None: filters.append(f"alpha={args.alpha}")
        desc = ", ".join(filters) if filters else "no filters (all graphs)"
        print(f"{total} graphs matching: {desc}")
        return

    # ---- default: print matching graphs -----------------------------------
    if args.n is None and args.d is None and args.alpha is None:
        print("No filters specified.  Use --list to see available triples, "
              "or pass --n / --d / --alpha to query.  Use --help for options.")
        return

    count = 0
    for n, d, a, G in iter_matches(args.db, args.n, args.d, args.alpha):
        count += 1
        print_graph(count, n, d, a, G, args.format)
        if args.limit and count >= args.limit:
            print(f"\n[limit reached: {args.limit}]")
            break

    print(f"\nTotal matching graphs printed: {count}")


if __name__ == "__main__":
    main()