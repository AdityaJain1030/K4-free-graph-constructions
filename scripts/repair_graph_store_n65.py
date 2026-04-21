#!/usr/bin/env python3
"""
scripts/repair_graph_store_n65.py
=================================
One-off repair for graphs/*.json records written with the pre-fix broken
pynauty certificate decoder (historical; canonical_id now goes through
nauty's labelg — see utils/nauty.py).

The broken decoder read the certificate byte row with `row[-1 - v // 8]`,
which only produces the correct adjacency for n ≤ 64 (one 64-bit setword
per row). At n ≥ 65 the row spans multiple setwords and reading from the
end inverts the word order, so the stored sparse6 decodes to a graph that
is *not* the graph the record's metadata claims. Every `id` derived from
that sparse6 is likewise wrong.

This script rebuilds the graph for each record from its metadata (the
content we trust), recomputes (id, sparse6) with the now-correct decoder,
and writes the corrected file. A .bak copy is left next to the original.

Sources handled:
    circulant_fast : G = nx.circulant_graph(n, metadata["connection_set"])
    cayley         : G = Cayley graph on Z_p with metadata["connection_set"]

Records at n ≤ 64 are re-encoded too (result is identical to the stored
value — round-trip serves as a consistency check).

Usage:
    micromamba run -n k4free python scripts/repair_graph_store_n65.py
    micromamba run -n k4free python scripts/repair_graph_store_n65.py --dry-run
"""

import argparse
import json
import os
import shutil
import sys

import networkx as nx

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from graph_db.encoding import sparse6_to_nx  # noqa: E402
from utils.nauty import canonical_id  # noqa: E402

GRAPHS_DIR = os.path.join(REPO, "graphs")


def _rebuild_from_metadata(r: dict) -> nx.Graph | None:
    src = r["source"]
    meta = r.get("metadata", {})
    cs = meta.get("connection_set")
    # The broken decoder preserved n in the sparse6 header, so we can still
    # read it back even when the edge data is wrong.
    n_from_stored = sparse6_to_nx(r["sparse6"]).number_of_nodes()

    if src == "circulant_fast":
        if cs is None:
            return None
        G = nx.circulant_graph(n_from_stored, cs)
        return G

    if src == "cayley":
        p = meta.get("prime")
        if p is None or cs is None:
            return None
        G = nx.Graph()
        G.add_nodes_from(range(p))
        S = set(cs)
        for v in range(p):
            for s in S:
                G.add_edge(v, (v + s) % p)
        return G

    return None


def _repair_file(path: str, dry_run: bool) -> tuple[int, int, int]:
    with open(path) as f:
        recs = json.load(f)

    changed = 0
    skipped = 0
    verified = 0
    new_recs: list[dict] = []
    for r in recs:
        G = _rebuild_from_metadata(r)
        if G is None:
            new_recs.append(r)
            skipped += 1
            continue
        gid, cs6 = canonical_id(G)
        if gid == r["id"] and cs6 == r["sparse6"]:
            new_recs.append(r)
            verified += 1
            continue
        new_r = dict(r)
        new_r["id"] = gid
        new_r["sparse6"] = cs6
        new_recs.append(new_r)
        changed += 1

    if changed and not dry_run:
        shutil.copy2(path, path + ".bak")
        with open(path, "w") as f:
            json.dump(new_recs, f, indent=2)

    return changed, verified, skipped


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dry-run", action="store_true",
                   help="Report what would change without writing.")
    args = p.parse_args()

    total_changed = 0
    for fn in sorted(os.listdir(GRAPHS_DIR)):
        if not fn.endswith(".json"):
            continue
        path = os.path.join(GRAPHS_DIR, fn)
        changed, verified, skipped = _repair_file(path, args.dry_run)
        total_changed += changed
        print(f"{fn}: changed={changed} verified_unchanged={verified} "
              f"no_metadata_handler={skipped}")

    print(f"\n{'(dry run) ' if args.dry_run else ''}total records rewritten: {total_changed}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
