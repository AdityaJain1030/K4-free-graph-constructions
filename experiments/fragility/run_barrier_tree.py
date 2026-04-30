#!/usr/bin/env python3
"""
experiments/fragility/run_barrier_tree.py
=========================================
Test D — disconnectivity graph / barrier tree at small N (object B in
``experiments/fragility/README.md``).

Pipeline
--------
1. Stream every K₄-free graph at N via ``geng -k N``. For each one
   compute α (exact) and c_log; keep those with c_log ≤ ``--threshold``.
2. For every kept graph, enumerate all *legal* move-neighbours under
   the chosen move family. Canonicalize each via nauty's ``labelg``.
3. Build the move-adjacency dict over the slice.
4. Run Kruskal-on-energy:
     * sort the slice by c_log ascending,
     * iterate; for each graph G, check its move-neighbours that have
       already been added (lower or equal c_log),
     * each cross-component union is a *saddle merge* at level c_log(G).
5. Output:
     * list of local minima (graphs with no in-slice move-neighbour
       at strictly lower c_log) with their basin sizes,
     * list of saddle merges (level, two-component representatives),
     * the sequence of (c_log, n_components) which is the barrier tree.

Output JSON shape::

    {
      "n": 9,
      "move": ["add", "delete"],
      "threshold": 1.2,
      "slice_size": 1234,
      "local_minima": [{"gid", "c_log", "alpha", "d_max", "basin_size", "n_edges"}, ...],
      "saddles": [{"level", "merged_min_a", "merged_min_b"}, ...],
      "barrier_tree": [{"level", "n_components"}, ...]
    }

Run from repo root::

    micromamba run -n k4free python experiments/fragility/run_barrier_tree.py \\
        --n 8 --threshold 1.2 --move add delete

"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)

import numpy as np  # noqa: E402
import networkx as nx  # noqa: E402

from utils.graph_props import (  # noqa: E402
    alpha_bb_clique_cover,
    c_log_value,
)
from utils.nauty import find_geng, graphs_via_geng, canonical_ids  # noqa: E402

from experiments.fragility.move_taxonomy import (  # noqa: E402
    enumerate_add, enumerate_delete, enumerate_flip,
    enumerate_slide, enumerate_switch,
    all_move_kinds,
)


_ENUMERATORS = {
    "add":    enumerate_add,
    "delete": enumerate_delete,
    "flip":   enumerate_flip,
    "slide":  enumerate_slide,
    "switch": enumerate_switch,
}


# ---------------------------------------------------------------------------
# Union-Find for Kruskal-on-energy
# ---------------------------------------------------------------------------

class UnionFind:
    def __init__(self):
        self.parent: dict = {}
        self.rep: dict = {}  # canonical representative (lowest-c_log node) per root

    def make_set(self, x: str, c_log: float) -> None:
        self.parent[x] = x
        self.rep[x] = (x, c_log)

    def find(self, x: str) -> str:
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, x: str, y: str) -> tuple[str, str] | None:
        """Union the two sets; return (rep_a, rep_b) of their previous local
        minima if a merge happened, else None."""
        rx, ry = self.find(x), self.find(y)
        if rx == ry:
            return None
        rep_x = self.rep[rx]
        rep_y = self.rep[ry]
        # link the higher-rep root under the lower-rep root
        if rep_x[1] <= rep_y[1]:
            self.parent[ry] = rx
            self.rep[rx] = rep_x
        else:
            self.parent[rx] = ry
            self.rep[ry] = rep_y
        return rep_x[0], rep_y[0]


# ---------------------------------------------------------------------------
# Step 1+2: enumerate slice and assign canonical IDs in a single batched pass
# ---------------------------------------------------------------------------

def enumerate_slice(n: int, threshold: float, alpha_max: int | None,
                    max_d: int | None = None) -> dict[str, dict]:
    """Stream geng -k N, compute α and c_log, keep graphs with c_log ≤ threshold.
    Returns dict {graph_id: {'sparse6', 'adj', 'c_log', 'alpha', 'd_max',
    'n_edges'}}.

    `max_d` is forwarded to geng's ``-D`` flag, which prunes the
    enumeration to graphs with max degree ≤ max_d. Use this to make N
    ≥ 10 tractable when you know the threshold only includes a few
    shelves.
    """
    geng = find_geng()
    if geng is None:
        raise RuntimeError("geng not found on PATH; run scripts/setup_nauty.sh")

    flags = "-k"
    if max_d is not None:
        flags = f"-k -D{max_d}"

    slice_graphs: list[nx.Graph] = []
    slice_meta: list[dict] = []
    n_total = 0
    t0 = time.monotonic()
    for G in graphs_via_geng(geng, n, flags=flags):
        n_total += 1
        adj = np.array(nx.to_numpy_array(G, dtype=np.uint8))
        d_max = int(adj.sum(axis=1).max()) if adj.size else 0
        if d_max <= 1:
            continue  # c_log undefined
        alpha, _ = alpha_bb_clique_cover(adj)
        if alpha_max is not None and alpha > alpha_max:
            continue
        cl = c_log_value(int(alpha), n, d_max)
        if cl is None or cl > threshold:
            continue
        slice_graphs.append(G)
        slice_meta.append({
            "alpha": int(alpha), "d_max": d_max,
            "c_log": float(cl), "adj": adj,
            "n_edges": int(adj.sum() // 2),
        })
        if len(slice_graphs) % 500 == 0:
            print(f"  enum: {n_total} streamed, {len(slice_graphs)} in slice "
                  f"({time.monotonic() - t0:.1f}s)", flush=True)

    print(f"  enum: {n_total} K₄-free graphs at N={n}, "
          f"{len(slice_graphs)} in slice "
          f"(c_log ≤ {threshold}, α ≤ {alpha_max if alpha_max else 'inf'})  "
          f"in {time.monotonic() - t0:.1f}s", flush=True)

    if not slice_graphs:
        return {}

    # Batched canonicalization.
    print(f"  canonicalising {len(slice_graphs)} slice graphs...", flush=True)
    t0 = time.monotonic()
    cids = canonical_ids(slice_graphs)
    print(f"  canonical_ids done in {time.monotonic() - t0:.1f}s", flush=True)

    out: dict[str, dict] = {}
    for (gid, cs6), meta in zip(cids, slice_meta):
        if gid in out:
            # geng yields one graph per iso class but be defensive
            continue
        meta["sparse6"] = cs6
        out[gid] = meta
    return out


# ---------------------------------------------------------------------------
# Step 3: build move adjacency over the slice
# ---------------------------------------------------------------------------

def build_move_adjacency(slice_dict: dict[str, dict],
                         moves: list[str],
                         batch_size: int = 5000
                         ) -> dict[str, list[str]]:
    """For each graph in the slice, enumerate move-neighbours, batch-
    canonicalize them, and keep only those whose canonical id is also in
    the slice."""
    enums = [_ENUMERATORS[m] for m in moves]

    adj: dict[str, list[str]] = {gid: [] for gid in slice_dict}
    pending_props: list[np.ndarray] = []
    pending_origin: list[str] = []  # graph_id of source for each proposal

    def flush(progress=""):
        nonlocal pending_props, pending_origin
        if not pending_props:
            return
        graphs = [nx.from_numpy_array(p) for p in pending_props]
        cids = canonical_ids(graphs)
        for src_gid, (nbr_gid, _) in zip(pending_origin, cids):
            if nbr_gid != src_gid and nbr_gid in slice_dict:
                adj[src_gid].append(nbr_gid)
        pending_props = []
        pending_origin = []
        if progress:
            print(progress, flush=True)

    n_done = 0
    n_total = len(slice_dict)
    t0 = time.monotonic()
    for gid, meta in slice_dict.items():
        for enum in enums:
            for prop in enum(meta["adj"]):
                pending_props.append(prop)
                pending_origin.append(gid)
                if len(pending_props) >= batch_size:
                    flush()
        n_done += 1
        if n_done % max(1, n_total // 20) == 0:
            print(f"  adj: {n_done}/{n_total} processed "
                  f"({time.monotonic() - t0:.1f}s)", flush=True)
    flush()

    # dedup + drop duplicates within each list
    for gid in adj:
        adj[gid] = sorted(set(adj[gid]))
    return adj


# ---------------------------------------------------------------------------
# Step 4: Kruskal-on-energy → barrier tree
# ---------------------------------------------------------------------------

def kruskal_barrier_tree(slice_dict: dict[str, dict],
                         adj: dict[str, list[str]]
                         ) -> dict:
    """Build the disconnectivity graph by Kruskal-on-energy.

    Algorithm: iterate graphs in ascending c_log order. Each graph G
    starts in its own singleton component. For every G, union G with
    each of its in-slice neighbours that has already been seen. A
    union that crosses two distinct components is a *saddle merge* at
    level c_log(G). At the end, the unique union-find roots are the
    barrier-tree leaves; each one's representative graph is its
    component's lowest-c_log node — i.e., a true local minimum of the
    slice.
    """
    sorted_ids = sorted(slice_dict.keys(),
                        key=lambda g: slice_dict[g]["c_log"])

    seen: set = set()
    uf = UnionFind()
    saddles: list[dict] = []
    barrier_tree: list[dict] = []
    n_components = 0

    for gid in sorted_ids:
        cl = slice_dict[gid]["c_log"]
        uf.make_set(gid, cl)
        n_components += 1

        for nbr in adj[gid]:
            if nbr not in seen:
                continue
            merged = uf.union(gid, nbr)
            if merged is not None:
                saddles.append({
                    "level": cl,
                    "merged_min_a": merged[0],
                    "merged_min_b": merged[1],
                    "saddle_gid": gid,
                })
                n_components -= 1

        seen.add(gid)
        barrier_tree.append({"c_log": cl, "n_components": n_components})

    # Final unique components → connected-component representatives
    # (lowest-c_log node of each component).
    rep_to_size: dict[str, int] = {}
    rep_to_gid: dict[str, str] = {}
    for gid in slice_dict:
        root = uf.find(gid)
        rep_gid, _ = uf.rep[root]
        rep_to_size[rep_gid] = rep_to_size.get(rep_gid, 0) + 1
        rep_to_gid[rep_gid] = rep_gid

    components = []
    for rep_gid in rep_to_gid:
        m = slice_dict[rep_gid]
        components.append({
            "gid": rep_gid,
            "c_log": m["c_log"],
            "alpha": m["alpha"],
            "d_max": m["d_max"],
            "n_edges": m["n_edges"],
            "sparse6": m.get("sparse6"),
            "size": rep_to_size[rep_gid],
        })
    components.sort(key=lambda x: x["c_log"])

    # Combinatorial local minima: graphs G with no in-slice neighbour at
    # strictly lower c_log. (Out-of-slice neighbours all have c_log >
    # threshold > c_log(G), so they're higher; only in-slice need check.)
    local_minima = []
    for gid, m in slice_dict.items():
        cl = m["c_log"]
        is_min = True
        for nbr in adj[gid]:
            if slice_dict[nbr]["c_log"] < cl - 1e-12:
                is_min = False
                break
        if is_min:
            local_minima.append({
                "gid": gid,
                "c_log": cl,
                "alpha": m["alpha"],
                "d_max": m["d_max"],
                "n_edges": m["n_edges"],
                "sparse6": m.get("sparse6"),
            })
    local_minima.sort(key=lambda x: x["c_log"])

    return {
        "components": components,
        "local_minima": local_minima,
        "saddles": saddles,
        "barrier_tree": barrier_tree,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, required=True,
                    help="number of vertices")
    ap.add_argument("--threshold", type=float, default=1.2,
                    help="keep graphs with c_log ≤ threshold "
                         "(default 1.2 — well above all known frontier).")
    ap.add_argument("--alpha-max", type=int, default=None,
                    help="optional cap on α to shrink the slice further")
    ap.add_argument("--max-d", type=int, default=None,
                    help="cap d_max via geng -D for early pruning (much "
                         "faster at N≥10 when the threshold restricts to "
                         "a few shelves).")
    ap.add_argument("--move", nargs="+", default=["add", "delete"],
                    choices=all_move_kinds(),
                    help="move family for the disconnectivity graph "
                         "(default add+delete = full K₄-free graph space).")
    ap.add_argument("--out", default=None,
                    help="output JSON path; default "
                         "data/barrier_tree_n<N>_<moves>.json")
    args = ap.parse_args()

    if args.out is None:
        move_tag = "_".join(args.move)
        args.out = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "data", f"barrier_tree_n{args.n}_{move_tag}.json")

    print(f"[barrier_tree] N={args.n} move={'+'.join(args.move)} "
          f"threshold c_log ≤ {args.threshold}")
    t_total = time.monotonic()

    slice_dict = enumerate_slice(args.n, args.threshold, args.alpha_max,
                                 max_d=args.max_d)
    if not slice_dict:
        print("[barrier_tree] empty slice; nothing to do", file=sys.stderr)
        return 1

    adj = build_move_adjacency(slice_dict, args.move)

    # connectivity stats
    n_pairs = sum(len(v) for v in adj.values())
    print(f"  move-graph density: {n_pairs} directed adjacencies, "
          f"avg degree {n_pairs / len(adj):.1f}")

    print(f"[barrier_tree] running Kruskal merges...")
    res = kruskal_barrier_tree(slice_dict, adj)
    res["n"] = args.n
    res["move"] = args.move
    res["threshold"] = args.threshold
    res["alpha_max"] = args.alpha_max
    res["slice_size"] = len(slice_dict)

    print(f"[barrier_tree] {len(res['components'])} connected components, "
          f"{len(res['local_minima'])} combinatorial local minima, "
          f"{len(res['saddles'])} saddle merges")
    print("[barrier_tree] top connected components by c_log:")
    for c in res["components"][:10]:
        print(f"    c_log={c['c_log']:.4f}  α={c['alpha']:>2d}  "
              f"d_max={c['d_max']:>2d}  |E|={c['n_edges']:>3d}  "
              f"size={c['size']:>5d}  gid={c['gid'][:10]}")
    if len(res["local_minima"]) > 1:
        print("[barrier_tree] top combinatorial local minima by c_log:")
        for lm in res["local_minima"][:10]:
            print(f"    c_log={lm['c_log']:.4f}  α={lm['alpha']:>2d}  "
                  f"d_max={lm['d_max']:>2d}  |E|={lm['n_edges']:>3d}  "
                  f"gid={lm['gid'][:10]}")

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w") as f:
        json.dump(res, f, indent=2, default=str)
    print(f"[barrier_tree] wrote {args.out}  "
          f"(total {time.monotonic() - t_total:.1f}s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
