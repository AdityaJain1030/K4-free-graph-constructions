#!/usr/bin/env python3
"""
scripts/run_fragility.py
========================
Probe 2 — perturbation fragility across N.

For each target N we pick the best graph in graph_db (smallest c_log
among K4-free rows), then launch NUM_TRIALS independent random walks.
At each walk step we pick an edge uv, a random non-neighbour w of u,
and attempt G' = G - uv + uw. The move is accepted iff G' is K4-free
and the degree spread (d_max - d_min) stays ≤ 2. This is a random
walk, not hill-climbing — c_log is recorded but never used to accept.

For each starting graph we record c_log at steps
``[0, 1, 2, 5, 10, 20, 50, 100]`` and average across trials. Output is
written to ``visualizer/plots/data/fragility.json`` for
``visualizer/plots/plot_fragility.py`` to consume.

Run from repo root::

    micromamba run -n k4free python scripts/run_fragility.py
    micromamba run -n k4free python scripts/run_fragility.py \
        --trials 100 --steps 100 --alpha exact
"""

import argparse
import json
import os
import random
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

import networkx as nx  # noqa: E402
import numpy as np  # noqa: E402

from graph_db import open_db  # noqa: E402
from utils.edge_switch import random_walk_move  # noqa: E402
from utils.graph_props import (  # noqa: E402
    alpha_approx,
    alpha_bb_clique_cover,
    c_log_value,
)


RECORD_STEPS_DEFAULT = [0, 1, 2, 5, 10, 20, 50, 100]
OUT_JSON = os.path.join(
    REPO, "visualizer", "plots", "data", "fragility.json"
)


def _alpha_fn(name: str):
    if name == "approx":
        return lambda adj: alpha_approx(adj, restarts=200)
    if name == "exact":
        return lambda adj: alpha_bb_clique_cover(adj)[0]
    raise ValueError(f"--alpha must be 'approx' or 'exact', got {name!r}")


def _c_log_from_adj(adj: np.ndarray, alpha_fn) -> float | None:
    n = adj.shape[0]
    d_max = int(adj.sum(axis=1).max())
    if d_max <= 1:
        return None
    return c_log_value(alpha_fn(adj), n, d_max)


def pick_starting_graphs(db, target_ns: list[int]) -> list[dict]:
    """For each N in target_ns, return the cached row with smallest c_log."""
    seeds = []
    for n in target_ns:
        frontier = db.frontier(by="n", minimize="c_log", is_k4_free=1, n=n)
        if not frontier:
            print(f"[fragility] no K4-free seed at n={n}; skipping")
            continue
        seeds.append(frontier[0])
    return db.hydrate(seeds)


def run_walk(
    adj0: np.ndarray,
    *,
    num_steps: int,
    record_at: list[int],
    alpha_fn,
    rng: random.Random,
) -> list[float | None]:
    """One random walk of `num_steps`, c_log sampled at `record_at` indices."""
    adj = adj0.copy()
    record = {s: None for s in record_at}
    if 0 in record:
        record[0] = _c_log_from_adj(adj, alpha_fn)
    for step in range(1, num_steps + 1):
        new = random_walk_move(adj, rng)
        if new is not None:
            adj = new
        # if the move was rejected, adj stays; c_log at this step reflects
        # the graph we're sitting on, which is the right random-walk semantic
        if step in record:
            record[step] = _c_log_from_adj(adj, alpha_fn)
    return [record[s] for s in record_at]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--ns", type=int, nargs="+", default=None,
        help="target N values. Default: every N in the DB that has a K4-free "
             "seed between 7 and 100.",
    )
    ap.add_argument("--trials", type=int, default=30,
                    help="independent walks per starting graph (default 30)")
    ap.add_argument("--steps", type=int, default=100,
                    help="walk length (default 100)")
    ap.add_argument("--record", type=int, nargs="+",
                    default=RECORD_STEPS_DEFAULT,
                    help="step indices at which to record c_log")
    ap.add_argument("--alpha", choices=("approx", "exact"), default="approx",
                    help="α solver at recorded steps. approx = fast "
                         "lower-bound greedy; exact = alpha_bb_clique_cover.")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--max-n", type=int, default=100,
                    help="cap on N; the base step-0 c_log dominates for large "
                         "N and α is costly there.")
    ap.add_argument("--out", default=OUT_JSON,
                    help="output JSON path (default visualizer/plots/data/fragility.json)")
    args = ap.parse_args()

    alpha_fn = _alpha_fn(args.alpha)

    with open_db() as db:
        if args.ns is None:
            ns_avail = sorted({
                r["n"] for r in db.query(is_k4_free=1)
                if r["n"] <= args.max_n
            })
        else:
            ns_avail = sorted(n for n in args.ns if n <= args.max_n)

        seeds = pick_starting_graphs(db, ns_avail)

    if not seeds:
        print("[fragility] no eligible seeds; populate graph_db first",
              file=sys.stderr)
        return 1

    print(f"[fragility] {len(seeds)} seeds, trials={args.trials}, "
          f"steps={args.steps}, alpha={args.alpha}")

    results = []
    for seed in seeds:
        gid = seed["graph_id"]
        src = seed["source"]
        n = seed["n"]
        G: nx.Graph = seed["G"]
        adj = np.array(nx.to_numpy_array(G, dtype=np.uint8))

        rng = random.Random(f"{args.seed}-{gid}")
        t0 = time.monotonic()
        trajs = []
        for t in range(args.trials):
            trajs.append(run_walk(
                adj,
                num_steps=args.steps,
                record_at=args.record,
                alpha_fn=alpha_fn,
                rng=rng,
            ))
        dt = time.monotonic() - t0

        arr = np.array(
            [[v if v is not None else np.nan for v in t] for t in trajs],
            dtype=float,
        )
        mean = np.nanmean(arr, axis=0).tolist()
        std = np.nanstd(arr, axis=0).tolist()
        valid = (~np.isnan(arr)).sum(axis=0).tolist()
        base = float(mean[0]) if mean and not np.isnan(mean[0]) else None

        print(f"[fragility n={n:>3} src={src}] c_log {mean[0]:.4f}→"
              f"{mean[-1]:.4f}  Δ={mean[-1]-mean[0]:+.4f}  "
              f"trials={args.trials}  ({dt:.1f}s)")

        results.append({
            "n": n,
            "graph_id": gid,
            "source": src,
            "base_c_log": base,
            "record_steps": args.record,
            "mean_c_log": mean,
            "std_c_log": std,
            "n_valid": valid,
            "trials": args.trials,
            "walk_length": args.steps,
            "alpha_solver": args.alpha,
        })

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w") as f:
        json.dump({
            "record_steps": args.record,
            "trials": args.trials,
            "walk_length": args.steps,
            "alpha_solver": args.alpha,
            "seed": args.seed,
            "results": results,
        }, f, indent=2)
    print(f"[fragility] wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
