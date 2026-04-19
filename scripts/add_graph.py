"""
scripts/add_graph.py
====================
Add a graph to the graph store (graphs/*.json).

Input formats (pick one):
  --sparse6 ':Kexample'       sparse6 string (no header)
  --edges '[[0,1],[1,2]]' -n 5  JSON edge list + vertex count
  --g6 'IheA...'             graph6 string (converted to sparse6)

Examples:
    python scripts/add_graph.py --sparse6 ':KcEGhB_' --source my_source
    python scripts/add_graph.py --edges '[[0,1],[1,2],[0,2]]' -n 3 \\
        --source manual --file manual.json
    python scripts/add_graph.py --sparse6 ':K...' --source my_run \\
        --meta '{"alpha": 4, "method": "hand"}'
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from graph_db import GraphStore, canonical_id, sparse6_to_nx, graph_to_sparse6, edges_to_nx

REPO_ROOT    = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GRAPHS_DIR   = os.path.join(REPO_ROOT, "graphs")
DEFAULT_FILE = "manual.json"


def parse_args():
    p = argparse.ArgumentParser()

    # Input
    inp = p.add_mutually_exclusive_group(required=True)
    inp.add_argument("--sparse6", help="sparse6 string (no :Fheader)")
    inp.add_argument("--edges",   help="JSON edge list, e.g. '[[0,1],[1,2]]'")
    inp.add_argument("--g6",      help="graph6 string")

    p.add_argument("-n", "--vertices", type=int, default=None,
                   help="Number of vertices (required for --edges)")
    p.add_argument("--source", required=True,
                   help="Source tag (e.g. 'my_run', 'manual')")
    p.add_argument("--file", default=DEFAULT_FILE,
                   help=f"Target JSON file in graphs/ (default: {DEFAULT_FILE})")
    p.add_argument("--meta", default=None,
                   help="Optional JSON metadata dict, e.g. '{\"alpha\":4}'")
    p.add_argument("--sync", action="store_true",
                   help="Also compute cache properties after adding")
    return p.parse_args()


def main():
    args = parse_args()

    # ── Build the graph ───────────────────────────────────────────────────────
    if args.sparse6:
        s6 = args.sparse6
        if not s6.startswith(":"):
            s6 = ":" + s6
        G = sparse6_to_nx(s6)

    elif args.edges:
        if args.vertices is None:
            print("ERROR: --vertices / -n required when using --edges")
            sys.exit(1)
        edge_list = json.loads(args.edges)
        G = edges_to_nx(edge_list, args.vertices)

    else:  # --g6
        import networkx as nx
        G = nx.from_graph6_bytes(args.g6.encode())

    # ── Canonical ID check ────────────────────────────────────────────────────
    gid, cs6 = canonical_id(G)
    s6_out   = graph_to_sparse6(G)
    print(f"Graph: n={G.number_of_nodes()}, m={G.number_of_edges()}")
    print(f"  canonical id  : {gid}")
    print(f"  sparse6       : {s6_out}")

    # ── Metadata ──────────────────────────────────────────────────────────────
    metadata = {}
    if args.meta:
        metadata = json.loads(args.meta)

    # ── Write to store ────────────────────────────────────────────────────────
    filename = args.file
    if not filename.endswith(".json"):
        filename += ".json"

    store = GraphStore(GRAPHS_DIR)
    existing = store.all_ids()

    if gid in existing:
        print(f"Graph already in store (id={gid}). Nothing written.")
    else:
        rec = {
            "id":       gid,
            "sparse6":  s6_out,
            "source":   args.source,
        }
        if metadata:
            rec["metadata"] = metadata

        written, _ = store.write_batch([rec], filename)
        print(f"Added to graphs/{filename} (id={gid})")

    # ── Optional cache sync ───────────────────────────────────────────────────
    if args.sync:
        from graph_db import DB
        with DB(GRAPHS_DIR, os.path.join(REPO_ROOT, "cache.db"), auto_sync=False) as db:
            db.sync(verbose=True)


if __name__ == "__main__":
    main()
