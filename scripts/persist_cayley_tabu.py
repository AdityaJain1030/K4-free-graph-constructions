#!/usr/bin/env python3
"""
scripts/persist_cayley_tabu.py
===============================
Read the completed Cayley-tabu sweep outputs in `results/cayley_tabu/`
and add each K₄-free graph to `graphs/cayley_tabu.json` under
source='cayley_tabu'. Skips records already present (dedup by
canonical id + source).

Run::

    micromamba run -n k4free python scripts/persist_cayley_tabu.py
"""

from __future__ import annotations

import glob
import json
import os
import sys
from pathlib import Path

import networkx as nx

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from graph_db import GraphStore, DEFAULT_GRAPHS


def _build_graph(n: int, edges: list[list[int]]) -> nx.Graph:
    G = nx.Graph()
    G.add_nodes_from(range(n))
    G.add_edges_from([tuple(e) for e in edges])
    return G


def main() -> int:
    store = GraphStore(DEFAULT_GRAPHS)
    detail_paths = sorted(glob.glob(str(Path(REPO) / "results" / "cayley_tabu" / "detail_N*.json")))
    if not detail_paths:
        print("No detail_N*.json found in results/cayley_tabu/.")
        return 1

    total_written = 0
    total_skipped = 0
    per_n_counts: dict[int, tuple[int, int]] = {}

    for path in detail_paths:
        with open(path) as f:
            records = json.load(f)
        if not records:
            continue
        n_written = 0
        n_skipped = 0
        for r in records:
            if not r.get("is_k4_free"):
                continue
            G = _build_graph(r["n"], r["edges"])
            metadata = {
                "algo": r.get("algo", "cayley_tabu"),
                "alpha": r["alpha"],
                "d_max": r["d_max"],
                "c_log": r["c_log"],
                "group": r.get("metadata", {}).get("group"),
                "connection_set": r.get("metadata", {}).get("connection_set"),
                "surrogate_c_log": r.get("metadata", {}).get("surrogate_c_log"),
                "tabu_n_iters": r.get("metadata", {}).get("tabu_n_iters"),
                "tabu_best_iter": r.get("metadata", {}).get("tabu_best_iter"),
            }
            metadata = {k: v for k, v in metadata.items() if v is not None}
            gid, was_new = store.add_graph(
                G,
                source="cayley_tabu",
                filename="cayley_tabu.json",
                **metadata,
            )
            if was_new:
                n_written += 1
            else:
                n_skipped += 1
        per_n_counts[records[0]["n"]] = (n_written, n_skipped)
        total_written += n_written
        total_skipped += n_skipped

    print("Per-N persistence (written / already-present):")
    for n in sorted(per_n_counts):
        w, s = per_n_counts[n]
        print(f"  N={n:>3}: +{w}  ={s}")
    print(f"\nTotal new records written:   {total_written}")
    print(f"Total duplicate records skipped: {total_skipped}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
