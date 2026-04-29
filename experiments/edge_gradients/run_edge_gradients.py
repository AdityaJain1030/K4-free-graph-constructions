"""
experiments/edge_gradients/run_edge_gradients.py
================================================
Score every edge of a benchmark graph with several α-attribution
methods and compare them against the exact drop-α gold standard.

Two graph populations:
  (a) Frontier — lowest-c_log K4-free graphs in graph_db. These are
      α-critical (drop-α = 1 for every edge), so they test whether a
      method *correctly* says "all edges equal" rather than introducing
      spurious ranking.
  (b) Perturbed — frontier graphs with one extra valid edge added
      (K4-free preserved). Most of these are non-critical, giving
      drop-α a real variance for rank-correlation comparison.

Outputs:
  results.csv   — one row per (graph_id, edge): all method scores.
  summary.csv   — one row per graph: spread, drop-α support size,
                  per-method Spearman against drop-α (when defined).
"""
from __future__ import annotations

import argparse
import csv
import os
import random
import sys
import time

import networkx as nx
import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from graph_db import DB  # noqa: E402
from utils.graph_props import is_k4_free  # noqa: E402
from edge_methods import METHODS  # noqa: E402


def perturb(G: nx.Graph, seed: int = 0, max_attempts: int = 200) -> nx.Graph | None:
    """Add one random non-edge to G that keeps it K4-free."""
    rng = random.Random(seed)
    nodes = list(G.nodes())
    non_edges = [(u, v) for i, u in enumerate(nodes) for v in nodes[i + 1:]
                 if not G.has_edge(u, v)]
    rng.shuffle(non_edges)
    for u, v in non_edges[:max_attempts]:
        H = G.copy()
        H.add_edge(u, v)
        if is_k4_free(nx.to_numpy_array(H, dtype=np.uint8)):
            return H
    return None


def spearman(xs, ys):
    """Manual Spearman rank correlation (avoids scipy dep)."""
    n = len(xs)
    if n < 2:
        return None
    rx = _ranks(xs)
    ry = _ranks(ys)
    mx = sum(rx) / n
    my = sum(ry) / n
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    dx = sum((a - mx) ** 2 for a in rx)
    dy = sum((b - my) ** 2 for b in ry)
    if dx == 0 or dy == 0:
        return None
    return num / (dx * dy) ** 0.5


def _ranks(xs):
    pairs = sorted(enumerate(xs), key=lambda p: p[1])
    rank = [0.0] * len(xs)
    i = 0
    while i < len(pairs):
        j = i
        while j + 1 < len(pairs) and pairs[j + 1][1] == pairs[i][1]:
            j += 1
        avg = 0.5 * (i + j) + 1
        for k in range(i, j + 1):
            rank[pairs[k][0]] = avg
        i = j + 1
    return rank


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(HERE, "results.csv"))
    ap.add_argument("--summary", default=os.path.join(HERE, "summary.csv"))
    args = ap.parse_args()

    # Hand-picked frontier graphs (mix of vertex-transitive and irregular).
    targets = [
        ("Paley(17)",      "n=17 AND source='cayley'"),
        ("CR(19)",         "n=19 AND source='cayley'"),
        ("n=22 cayley",    "n=22 AND source='cayley_tabu'"),
        ("n=21 cayley_gap","n=21 AND source='cayley_tabu_gap'"),
        ("n=8 brute",      "n=8 AND source='brute_force'"),
        ("n=14 sat_exact", "n=14 AND source='sat_exact'"),
        ("n=14 sat_near",  "n=14 AND source='sat_near_regular_nonreg'"),
        ("n=15 sat_near",  "n=15 AND source='sat_near_regular_nonreg'"),
        ("n=20 sat_exact", "n=20 AND source='sat_exact'"),
        ("n=25 sat_exact", "n=25 AND source='sat_exact'"),
    ]

    rows: list[dict] = []
    summary: list[dict] = []
    with DB(auto_sync=False) as db:
        for label, where in targets:
            r = db.raw_execute(
                f"SELECT graph_id, n, alpha, source FROM cache "
                f"WHERE {where} AND is_k4_free=1 ORDER BY c_log LIMIT 1"
            )
            if not r:
                print(f"  skip {label}: no match")
                continue
            r = r[0]
            G = db.nx(r["graph_id"])
            run_one(label, "frontier", G, r, rows, summary)

            # Perturbed variant
            H = perturb(G, seed=hash(r["graph_id"]) & 0xFFFF)
            if H is not None:
                pseudo = dict(r)
                pseudo["graph_id"] = r["graph_id"] + "+1"
                pseudo["alpha"] = None  # recompute
                run_one(label + " (+1 edge)", "perturbed", H, pseudo,
                        rows, summary)

    # Persist
    with open(args.out, "w", newline="") as f:
        fields = list(rows[0].keys())
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for row in rows:
            w.writerow(row)
    print(f"[edge] wrote {args.out} ({len(rows)} edge rows)")

    with open(args.summary, "w", newline="") as f:
        fields = list(summary[0].keys())
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for row in summary:
            w.writerow(row)
    print(f"[edge] wrote {args.summary} ({len(summary)} graph rows)")


def run_one(label, kind, G, r, rows, summary):
    from utils.graph_props import alpha_bb_clique_cover_nx as alpha_nx
    n_e = G.number_of_edges()
    print(f"[{kind:9s}] {label:25s}  n={G.number_of_nodes()}  |E|={n_e}", flush=True)
    if r["alpha"] is None:
        a, _ = alpha_nx(G)
    else:
        a = int(r["alpha"])
    method_results = {}
    timings = {}
    for name, fn in METHODS.items():
        t = time.time()
        try:
            method_results[name] = fn(G)
        except Exception as ex:
            method_results[name] = None
            print(f"    {name}: FAILED ({ex})")
        timings[name] = round(time.time() - t, 3)

    edges = sorted(tuple(sorted(e)) for e in G.edges())
    for e in edges:
        row = dict(graph_id=r["graph_id"], label=label, kind=kind,
                   n=G.number_of_nodes(), m=n_e, alpha=a,
                   edge_u=e[0], edge_v=e[1])
        for name in METHODS:
            v = method_results[name]
            row[name] = (v[e] if v is not None and e in v else None)
        rows.append(row)

    # Per-graph summary
    s = dict(graph_id=r["graph_id"], label=label, kind=kind,
             n=G.number_of_nodes(), m=n_e, alpha=a)
    drop_a = method_results["drop_alpha"]
    if drop_a is not None:
        vals = [drop_a[e] for e in edges]
        s["drop_alpha_min"] = min(vals)
        s["drop_alpha_max"] = max(vals)
        s["drop_alpha_nonzero"] = sum(1 for v in vals if v > 0)
    for name in METHODS:
        if name == "drop_alpha":
            continue
        m = method_results[name]
        if m is None or drop_a is None:
            s[f"spearman_{name}"] = None
            s[f"{name}_t"] = timings.get(name)
            continue
        xs = [drop_a[e] for e in edges]
        ys = [m[e] for e in edges]
        s[f"spearman_{name}"] = spearman(xs, ys)
        s[f"{name}_t"] = timings.get(name)
    summary.append(s)


if __name__ == "__main__":
    main()
