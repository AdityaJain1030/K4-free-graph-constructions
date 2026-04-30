#!/usr/bin/env python3
"""
experiments/graph_space_visualization/run.py
============================================
Project K4-free graphs at fixed N into 2D and color by family.

    micromamba run -n k4free python experiments/graph_space_visualization/run.py \
        --n 17 --method pca,tsne,umap --html --png

See README.md for the full flag list and the canonical-Hamming caveat.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time

import numpy as np

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(THIS_DIR))
sys.path.insert(0, REPO)
sys.path.insert(0, THIS_DIR)

from graph_db import DB  # noqa: E402

from vectorize import stack_edge_vectors  # noqa: E402
from distance import pairwise_hamming, pairwise_ged  # noqa: E402
from embed import METHODS, needs_distance_matrix  # noqa: E402
from plot import scatter_png, scatter_html  # noqa: E402


CACHE_DIR = os.path.join(THIS_DIR, "cache")
RESULTS_DIR_DEFAULT = os.path.join(THIS_DIR, "results")


def _parse_csv(s: str | None) -> list[str] | None:
    if s is None or s.strip() == "" or s.strip().lower() == "all":
        return None
    return [tok.strip() for tok in s.split(",") if tok.strip()]


def _hash_corpus(graph_ids: list[str], metric: str) -> str:
    h = hashlib.sha256()
    h.update(metric.encode())
    for gid in sorted(graph_ids):
        h.update(b"\x00")
        h.update(gid.encode())
    return h.hexdigest()[:16]


def load_corpus(n: int, sources: list[str] | None, c_log_max: float | None,
                max_per_source: int) -> list[dict]:
    """Single DB session: query → dedupe by graph_id → cap-per-source → hydrate.

    Dedup keeps the alphabetically-first source per canonical graph (rows are
    pre-sorted by source). Multiple rows with the same `graph_id` collapse to
    a single point in the projection — so the gold-star marker fires only on
    genuinely distinct graphs that tie at min c_log, not on rediscoveries.
    """
    where: dict = {"n": n}
    ranges: dict = {"c_log": (None, c_log_max)} if c_log_max is not None else {}
    isin = {"source": sources} if sources else {}

    with DB(auto_sync=False) as db:
        rows = db.query(where=where, ranges=ranges, isin=isin,
                        order_by=["source", "c_log"])
        seen: set[str] = set()
        deduped: list[dict] = []
        for r in rows:
            if r["graph_id"] in seen:
                continue
            seen.add(r["graph_id"])
            deduped.append(r)
        if max_per_source and max_per_source > 0:
            kept: dict[str, list[dict]] = {}
            for r in deduped:
                kept.setdefault(r["source"], []).append(r)
            deduped = [r for group in kept.values() for r in group[:max_per_source]]
        return db.hydrate(deduped)


def compute_distance(rows: list[dict], X: np.ndarray, metric: str,
                     n: int, cache_key: str) -> np.ndarray:
    os.makedirs(CACHE_DIR, exist_ok=True)
    dpath = os.path.join(CACHE_DIR, f"distance_n{n}_{metric}_{cache_key}.npy")
    if os.path.exists(dpath):
        return np.load(dpath)

    if metric == "hamming-canonical":
        D = pairwise_hamming(X)
    elif metric == "ged":
        if n > 12:
            raise ValueError("--metric ged is only sane for n <= 12")
        D, timed_out = pairwise_ged([r["G"] for r in rows], timeout_per_pair_s=1.0)
        if timed_out:
            print(f"[ged] {len(timed_out)} pairs timed out and are NaN", file=sys.stderr)
    else:
        raise ValueError(f"unknown --metric: {metric}")

    np.save(dpath, D)
    return D


def label_values(rows: list[dict], color_by: str) -> list[str]:
    if color_by == "source":
        return [r["source"] for r in rows]
    if color_by == "regular":
        return ["regular" if r.get("is_regular") else "non-regular" for r in rows]
    if color_by == "d_max":
        return [f"d_max={r.get('d_max')}" for r in rows]
    if color_by == "c_log":
        c = np.array([r.get("c_log") or np.nan for r in rows], dtype=float)
        q = np.nanquantile(c, [0.2, 0.4, 0.6, 0.8])
        labels = []
        for v in c:
            if not np.isfinite(v):
                labels.append("c_log=?")
            elif v <= q[0]: labels.append("c_log Q1 (best)")
            elif v <= q[1]: labels.append("c_log Q2")
            elif v <= q[2]: labels.append("c_log Q3")
            elif v <= q[3]: labels.append("c_log Q4")
            else:          labels.append("c_log Q5 (worst)")
        return labels
    raise ValueError(f"unknown --color-by: {color_by}")


def size_values(rows: list[dict], size_by: str) -> np.ndarray | None:
    if size_by == "none":
        return None
    key = {"c_log": "c_log", "alpha": "alpha", "d_max": "d_max"}.get(size_by)
    if key is None:
        raise ValueError(f"unknown --size-by: {size_by}")
    v = np.array([r.get(key) if r.get(key) is not None else np.nan
                  for r in rows], dtype=float)
    # Smaller c_log → larger marker; flip the sign so plot._normalize_sizes
    # maps the best graphs to the upper end of the marker-size range.
    return -v if size_by == "c_log" else v


def highlight_mask(rows: list[dict], spec: list[str] | None) -> np.ndarray:
    mask = np.zeros(len(rows), dtype=bool)
    if not spec:
        return mask
    for i, r in enumerate(rows):
        if any(r["graph_id"].startswith(tok) for tok in spec):
            mask[i] = True
    return mask


def best_clog_mask(rows: list[dict]) -> np.ndarray:
    c = np.array([r.get("c_log") if r.get("c_log") is not None else np.inf
                  for r in rows], dtype=float)
    if not np.isfinite(c).any():
        return np.zeros(len(rows), dtype=bool)
    return c == c.min()


def hover_text(rows: list[dict]) -> list[str]:
    return [
        f"id={r['graph_id'][:10]}<br>source={r['source']}<br>"
        f"α={r.get('alpha')}  d_max={r.get('d_max')}  c_log={(r.get('c_log') or float('nan')):.4f}"
        for r in rows
    ]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, required=True)
    ap.add_argument("--method", default="pca",
                    help="comma-list of pca,tsne,umap,mds")
    ap.add_argument("--metric", default="hamming-canonical",
                    choices=["hamming-canonical", "ged"])
    ap.add_argument("--sources", default="all",
                    help="comma-list of source tags, or 'all'")
    ap.add_argument("--c-log-max", type=float, default=None)
    ap.add_argument("--max-per-source", type=int, default=50)
    ap.add_argument("--color-by", default="source",
                    choices=["source", "c_log", "regular", "d_max"])
    ap.add_argument("--size-by", default="c_log",
                    choices=["c_log", "alpha", "d_max", "none"])
    ap.add_argument("--highlight", default="",
                    help="comma-list of graph_id prefixes to circle in red")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--png", action="store_true")
    ap.add_argument("--html", action="store_true")
    ap.add_argument("--out", default=RESULTS_DIR_DEFAULT)
    args = ap.parse_args()

    if not (args.png or args.html):
        args.png = args.html = True

    methods = [m.strip() for m in args.method.split(",") if m.strip()]
    for m in methods:
        if m not in METHODS:
            ap.error(f"unknown method '{m}', expected one of {sorted(METHODS)}")

    print(f"[load] n={args.n} sources={args.sources} c_log_max={args.c_log_max}")
    rows = load_corpus(args.n, _parse_csv(args.sources),
                       args.c_log_max, args.max_per_source)
    if len(rows) < 3:
        print(f"[load] only {len(rows)} rows — need at least 3", file=sys.stderr)
        return 1
    print(f"[load] {len(rows)} rows from {len(set(r['source'] for r in rows))} sources")

    X = stack_edge_vectors([r["adj"] for r in rows])
    cache_key = _hash_corpus([r["graph_id"] for r in rows], args.metric)
    out_dir = os.path.join(args.out, f"n{args.n}")
    os.makedirs(out_dir, exist_ok=True)

    D = None
    if any(needs_distance_matrix(m) for m in methods):
        t0 = time.time()
        D = compute_distance(rows, X, args.metric, args.n, cache_key)
        print(f"[dist] {args.metric} ({D.shape[0]}×{D.shape[0]}) in {time.time()-t0:.2f}s")

    labels = label_values(rows, args.color_by)
    sizes = size_values(rows, args.size_by)
    hl_mask = highlight_mask(rows, _parse_csv(args.highlight))
    bm = best_clog_mask(rows)
    hover = hover_text(rows)

    for method in methods:
        embed_fn = METHODS[method]
        t0 = time.time()
        coords, info = embed_fn(X if method == "pca" else D,
                                n_components=2, seed=args.seed)
        print(f"[embed] {method} in {time.time()-t0:.2f}s  info={info}")

        title = f"N={args.n}  K={len(rows)}  method={method}  metric={args.metric}"
        stem = f"n{args.n}_{method}_{args.metric}_seed{args.seed}"
        if args.png:
            scatter_png(coords, labels, sizes, title,
                        os.path.join(out_dir, stem + ".png"),
                        highlight_mask=hl_mask, best_mask=bm)
        if args.html:
            scatter_html(coords, labels, sizes, hover, title,
                         os.path.join(out_dir, stem + ".html"),
                         highlight_mask=hl_mask, best_mask=bm)

        meta = {
            "method": method, "metric": args.metric,
            "n": args.n, "k": len(rows), "seed": args.seed, "info": info,
            "graph_ids": [r["graph_id"] for r in rows],
            "sources": [r["source"] for r in rows],
        }
        with open(os.path.join(out_dir, stem + ".json"), "w") as f:
            json.dump(meta, f, indent=2)

    return 0


if __name__ == "__main__":
    sys.exit(main())
