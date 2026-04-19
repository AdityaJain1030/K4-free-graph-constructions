"""
scripts/import_sat_pareto.py
============================
Convert SAT_old/k4free_ilp/results/pareto_n*.json into the graphs/ store.

Reads every Pareto frontier entry that has edges, computes its canonical id
and sparse6, and writes all records to graphs/sat_pareto_ilp.json.

Usage (from repo root, with 4cycle env active):
    python scripts/import_sat_pareto.py
    python scripts/import_sat_pareto.py --results-dir path/to/results
    python scripts/import_sat_pareto.py --sync   # also fill cache.db
"""

import argparse
import glob
import json
import os
import sys

# Make graph_db importable from repo root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from graph_db import GraphStore, canonical_id, graph_to_sparse6, edges_to_nx

REPO_ROOT    = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_RESULTS = os.path.join(REPO_ROOT, "SAT_old", "k4free_ilp", "results")
GRAPHS_DIR   = os.path.join(REPO_ROOT, "graphs")
CACHE_PATH   = os.path.join(REPO_ROOT, "cache.db")
OUT_FILENAME = "sat_pareto_ilp.json"


def load_pareto_files(results_dir: str) -> list[dict]:
    """
    Read all pareto_n*.json files and return a flat list of raw frontier
    entries, each augmented with 'n' from the parent file.
    """
    entries = []
    for path in sorted(glob.glob(os.path.join(results_dir, "pareto_n*.json"))):
        with open(path) as f:
            data = json.load(f)
        n = data["n"]
        for entry in data.get("pareto_frontier", []):
            edges = entry.get("edges", [])
            # Skip empty graphs (d_max=0) — not interesting
            if not edges and entry.get("d_max", 0) == 0:
                continue
            entries.append({**entry, "n": n})
    return entries


def convert(entry: dict) -> dict | None:
    """
    Convert one pareto frontier entry into a graph store record.
    Returns None if the entry cannot be converted (e.g. no edges at all).
    """
    n = entry["n"]
    edges = entry.get("edges", [])
    G = edges_to_nx(edges, n)

    gid, cs6 = canonical_id(G)
    s6 = graph_to_sparse6(G)

    metadata = {
        "n":            n,
        "alpha":        entry.get("alpha"),
        "d_max":        entry.get("d_max"),
        "c_log":        entry.get("c_log"),
        "solve_time_s": entry.get("solve_time"),
        "method":       entry.get("method"),
        "iterations":   entry.get("iterations"),
    }
    # Remove None values to keep metadata clean
    metadata = {k: v for k, v in metadata.items() if v is not None}

    return {
        "id":       gid,
        "sparse6":  s6,
        "source":   "sat_pareto",
        "metadata": metadata,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--results-dir", default=DEFAULT_RESULTS,
                        help="Path to pareto_n*.json files")
    parser.add_argument("--sync", action="store_true",
                        help="Also compute and fill cache.db after import")
    args = parser.parse_args()

    print(f"Reading pareto results from: {args.results_dir}")
    entries = load_pareto_files(args.results_dir)
    print(f"Found {len(entries)} frontier entries across all N values")

    records = []
    seen_ids = set()
    for entry in entries:
        rec = convert(entry)
        if rec is None:
            continue
        if rec["id"] in seen_ids:
            continue
        seen_ids.add(rec["id"])
        records.append(rec)

    print(f"Converted to {len(records)} unique graph records")

    store = GraphStore(GRAPHS_DIR)
    written, skipped = store.write_batch(records, OUT_FILENAME)
    print(f"Wrote {written} new records to graphs/{OUT_FILENAME} "
          f"({skipped} already existed)")

    if args.sync:
        from graph_db import DB
        with DB(GRAPHS_DIR, CACHE_PATH, auto_sync=False) as db:
            db.sync(verbose=True)


if __name__ == "__main__":
    main()
