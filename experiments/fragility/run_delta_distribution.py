#!/usr/bin/env python3
"""
experiments/fragility/run_delta_distribution.py
===============================================
Test A — local differential structure (object A in
``experiments/fragility/README.md``).

For each (seed, move family) pair, enumerate (or uniformly sample) the
legal proposals at T=1 and report the empirical distribution of

    Δc_log(move) = c_log(G + move) − c_log(G_0)

This replaces the v0 trajectory-mean fragility with a proper
distributional probe: tails matter.

What we report per (seed, move_kind):

  * histogram of Δc_log values (binned)
  * P(Δ < 0)                        — improving move exists?
  * P(Δ > τ) for τ ∈ {0, 0.01, 0.05, 0.1}
  * Shannon entropy of the binned histogram
  * mean, median, std (for backwards comparison with v0)
  * sample_method ∈ {'enum', 'sample'} and the sample budget used

Run from repo root::

    micromamba run -n k4free python experiments/fragility/run_delta_distribution.py
    micromamba run -n k4free python experiments/fragility/run_delta_distribution.py \\
        --sources sat_exact cayley brute_force random --n 17 19 22 \\
        --moves slide switch add delete --max-proposals 1000

Default seeds: per (source, n) cell in the default cross-product, pick
the lowest-c_log K₄-free graph from graph_db. The default source list
matches the families pre-registered in the README.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import random
import sys
import time
from collections import Counter
from typing import Iterable

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)

import numpy as np  # noqa: E402
import networkx as nx  # noqa: E402

from graph_db import open_db  # noqa: E402
from utils.graph_props import alpha_approx, alpha_bb_clique_cover, c_log_value  # noqa: E402

from experiments.fragility.indicators import (  # noqa: E402
    compute_indicators, indicators_to_dict,
)
from experiments.fragility.move_taxonomy import (  # noqa: E402
    enumerate_add, enumerate_delete, enumerate_flip,
    enumerate_slide, enumerate_switch,
    all_move_kinds,
)


_ENUM = {
    "add":    enumerate_add,
    "delete": enumerate_delete,
    "flip":   enumerate_flip,
    "slide":  enumerate_slide,
    "switch": enumerate_switch,
}

_DEFAULT_SOURCES = [
    "sat_exact",
    "server_sat_exact",
    "cayley",
    "cayley_tabu_gap",
    "brute_force",
    "random",
    "polarity",
]
_DEFAULT_NS = [12, 15, 17, 19, 22]
_DEFAULT_MOVES = ["add", "delete", "slide", "switch"]
_TAU_GRID = [0.0, 0.01, 0.05, 0.1]
_BIN_EDGES = np.linspace(-0.30, 0.30, 31)  # 30 bins of width 0.02


# ---------------------------------------------------------------------------
# Δ computation
# ---------------------------------------------------------------------------

def _c_log(adj: np.ndarray, alpha_fn) -> float | None:
    n = adj.shape[0]
    d_max = int(adj.sum(axis=1).max())
    if d_max <= 1:
        return None
    return c_log_value(alpha_fn(adj), n, d_max)


def _alpha_fn(name: str):
    if name == "approx":
        return lambda a: alpha_approx(a, restarts=200)
    if name == "exact":
        return lambda a: alpha_bb_clique_cover(a)[0]
    raise ValueError(f"--alpha must be 'approx' or 'exact', got {name!r}")


def deltas_for_move(adj: np.ndarray, kind: str, alpha_fn,
                    *, max_proposals: int, rng: random.Random
                    ) -> tuple[list[float], str, int]:
    """Return (delta_list, sample_method, n_proposals_total).

    sample_method is 'enum' if the full enumeration fit under
    `max_proposals`, else 'sample' (uniform random subset).
    """
    enumerator = _ENUM[kind]
    if kind == "switch" or kind == "flip":
        # These have potentially large enumerations; pass the cap.
        all_props = enumerator(adj, max_proposals=max_proposals * 4)  # type: ignore[call-arg]
    else:
        all_props = enumerator(adj)

    total = len(all_props)
    if total == 0:
        return [], "enum", 0

    if total <= max_proposals:
        chosen = all_props
        method = "enum"
    else:
        idx = rng.sample(range(total), max_proposals)
        chosen = [all_props[i] for i in idx]
        method = "sample"

    base = _c_log(adj, alpha_fn)
    if base is None:
        return [], method, total

    deltas = []
    for prop in chosen:
        v = _c_log(prop, alpha_fn)
        if v is None:
            continue
        deltas.append(v - base)
    return deltas, method, total


# ---------------------------------------------------------------------------
# Distribution summarisation
# ---------------------------------------------------------------------------

def _entropy_from_counts(counts: np.ndarray) -> float:
    s = counts.sum()
    if s <= 0:
        return 0.0
    p = counts / s
    nz = p > 0
    return float(-(p[nz] * np.log(p[nz])).sum())


def summarise(deltas: list[float]) -> dict:
    if not deltas:
        return {
            "n": 0, "mean": None, "median": None, "std": None,
            "p_lt0": None, "p_gt0": None,
            **{f"p_gt_{tau}": None for tau in _TAU_GRID[1:]},
            "entropy": None, "hist_bins": None, "hist_counts": None,
        }
    arr = np.asarray(deltas, dtype=float)
    counts, _ = np.histogram(arr, bins=_BIN_EDGES)
    return {
        "n": int(arr.size),
        "mean": float(arr.mean()),
        "median": float(np.median(arr)),
        "std": float(arr.std()),
        "p_lt0": float((arr < 0).mean()),
        "p_gt0": float((arr > 0).mean()),
        **{f"p_gt_{tau}": float((arr > tau).mean()) for tau in _TAU_GRID[1:]},
        "entropy": _entropy_from_counts(counts),
        "hist_bins": _BIN_EDGES.tolist(),
        "hist_counts": counts.astype(int).tolist(),
    }


# ---------------------------------------------------------------------------
# Seed selection
# ---------------------------------------------------------------------------

def pick_seeds(db, sources: list[str], ns: list[int]) -> list[dict]:
    """For each (source, n), pick the lowest-c_log K₄-free row.
    Returns the hydrated records (including 'G')."""
    seeds: list[dict] = []
    for src in sources:
        for n in ns:
            rows = db.frontier(by="n", minimize="c_log",
                               is_k4_free=1, source=src, n=n)
            if not rows:
                continue
            seeds.append(rows[0])
    return db.hydrate(seeds)


def pick_best_per_n(db, ns: list[int],
                    exclude_sources: list[str] | None = None) -> list[dict]:
    """For each n, pick the single lowest-c_log K₄-free row across *all*
    sources (optionally excluding some). Returns hydrated records."""
    excl = set(exclude_sources or [])
    seeds: list[dict] = []
    for n in ns:
        rows = db.query(is_k4_free=1, n=n,
                        order_by="c_log", limit=200)
        rows = [r for r in rows if r["source"] not in excl]
        if not rows:
            continue
        seeds.append(rows[0])
    return db.hydrate(seeds)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sources", nargs="+", default=_DEFAULT_SOURCES,
                    help="graph_db source tags to pull seeds from "
                         "(ignored if --best-per-n is set)")
    ap.add_argument("--best-per-n", action="store_true",
                    help="instead of picking one seed per (source, n), "
                         "pick the single lowest-c_log graph at each n "
                         "across all sources")
    ap.add_argument("--exclude-sources", nargs="+", default=[],
                    help="when --best-per-n is set, exclude these source "
                         "tags from the candidate pool")
    ap.add_argument("--n", "--ns", dest="ns", type=int, nargs="+",
                    default=_DEFAULT_NS, help="N values to probe")
    ap.add_argument("--moves", nargs="+", default=_DEFAULT_MOVES,
                    choices=all_move_kinds(),
                    help="move families to probe")
    ap.add_argument("--max-proposals", type=int, default=1000,
                    help="cap on legal proposals per (seed, move). If the "
                         "enumeration is larger, sample uniformly.")
    ap.add_argument("--alpha", choices=("approx", "exact"), default="approx",
                    help="α solver. 'approx' = greedy lower-bound (fast); "
                         "'exact' = alpha_bb_clique_cover.")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--skip-indicators", action="store_true",
                    help="don't compute the per-seed indicator block "
                         "(skips |E| α solves per seed)")
    ap.add_argument("--out", default=os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "data", "delta_dist.json"),
        help="output JSON path")
    args = ap.parse_args()

    alpha_fn = _alpha_fn(args.alpha)
    rng = random.Random(args.seed)

    with open_db() as db:
        if args.best_per_n:
            seeds = pick_best_per_n(db, args.ns,
                                    exclude_sources=args.exclude_sources)
        else:
            seeds = pick_seeds(db, args.sources, args.ns)

    if not seeds:
        print("[delta_dist] no eligible seeds; populate graph_db first",
              file=sys.stderr)
        return 1

    print(f"[delta_dist] {len(seeds)} seeds × {len(args.moves)} moves; "
          f"α={args.alpha}; cap={args.max_proposals}")

    results = []
    t_total = time.monotonic()
    for s_idx, seed in enumerate(seeds, 1):
        gid = seed["graph_id"]
        src = seed["source"]
        n = seed["n"]
        G: nx.Graph = seed["G"]
        adj = np.array(nx.to_numpy_array(G, dtype=np.uint8))

        ind = (compute_indicators(
            adj,
            compute_theta=False,
            compute_sensitivities=not args.skip_indicators,
            move_kinds=args.moves,
        ) if True else None)

        per_move = {}
        for kind in args.moves:
            t0 = time.monotonic()
            deltas, method, total = deltas_for_move(
                adj, kind, alpha_fn,
                max_proposals=args.max_proposals,
                rng=rng,
            )
            summary = summarise(deltas)
            summary["sample_method"] = method
            summary["legal_proposals_total"] = total
            summary["wall_time_s"] = round(time.monotonic() - t0, 3)
            per_move[kind] = summary
            head = (f"[seed {s_idx}/{len(seeds)} src={src} n={n} "
                    f"{kind:7s}] props={total:>6d} ({method})")
            if summary["mean"] is None:
                print(f"{head} (no valid Δ)")
            else:
                print(f"{head} μ={summary['mean']:+.4f} "
                      f"P(<0)={summary['p_lt0']:.2f} "
                      f"P(>0.05)={summary['p_gt_0.05']:.2f} "
                      f"H={summary['entropy']:.3f} "
                      f"({summary['wall_time_s']:.1f}s)")

        results.append({
            "graph_id": gid,
            "source": src,
            "n": n,
            "indicators": indicators_to_dict(ind),
            "per_move": per_move,
        })

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w") as f:
        json.dump({
            "alpha_solver": args.alpha,
            "max_proposals": args.max_proposals,
            "moves": args.moves,
            "sources": args.sources,
            "ns": args.ns,
            "seed": args.seed,
            "tau_grid": _TAU_GRID,
            "results": results,
        }, f, indent=2, default=str)
    print(f"[delta_dist] wrote {args.out} "
          f"({time.monotonic() - t_total:.1f}s total)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
