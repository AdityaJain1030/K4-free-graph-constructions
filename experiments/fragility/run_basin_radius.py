#!/usr/bin/env python3
"""
experiments/fragility/run_basin_radius.py
=========================================
Test E variant — basin radius under degree-preserving descent.

Where ``run_basin_volume.py`` answers
    "how often does random_init under add+delete descend to G*?"
this script answers the complementary question for *plateau* and
*degree-locked* targets:
    "if I start at G* and apply K random degree-preserving moves
     (switch), does best-improving descent return to G*?"

This is the right basin probe for graphs that

  (a) sit on a flat c_log plateau (Test A's N=35 finding —
      most switch-moves preserve c_log exactly), or
  (b) live on a connected component of the switch graph that random
      density-matched seeds cannot reach (degree-sequence mismatch).

For each target G*, for each K ∈ perturb_steps:
  1. Apply K random K4-safe switches starting from G*.
  2. Run best-improving switch-descent with random plateau escape.
  3. Record:
       - canonical_id(endpoint) == canonical_id(G*)?    (exact match)
       - |c_log(endpoint) - c_log(G*)| < plateau_eps?   (plateau match)

Two reach rates are reported per (target, K):
  p̂_exact(K) — fraction that returned to the exact isomorphism class
  p̂_plateau(K) — fraction whose endpoint sits at the same c_log
                  (within plateau_eps) as the target

The plateau rate is the right observable when c_log has high
multiplicity in the move graph; the exact rate is the strict
attractor probability.

Run from repo root::

    micromamba run -n k4free python experiments/fragility/run_basin_radius.py \\
        --target-source cayley_tabu_gap --target-n 35 \\
        --perturb-steps 1 5 20 50 100 --trials 50 \\
        --candidate-cap 100 --plateau-eps 0.005

Output goes to ``experiments/fragility/data/basin_radius_<tag>.json``.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)

import numpy as np  # noqa: E402
import networkx as nx  # noqa: E402

from graph_db import open_db  # noqa: E402
from utils.graph_props import (  # noqa: E402
    alpha_approx,
    alpha_bb_clique_cover,
    c_log_value,
)
from utils.nauty import canonical_id  # noqa: E402

from experiments.fragility.move_taxonomy import (  # noqa: E402
    sample_switch, _ENUMERATORS,
)
from experiments.fragility.run_basin_volume import descend  # noqa: E402


def perturb_with_switches(adj: np.ndarray, k: int,
                          rng: random.Random) -> np.ndarray:
    """Apply k uniform random K4-safe switch moves. If a step finds no
    legal switch, return the current state (rare in practice)."""
    cur = adj.copy()
    for _ in range(k):
        new = sample_switch(cur, rng)
        if new is None:
            break
        cur = new
    return cur


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target-source", nargs="+",
                    default=["cayley_tabu_gap", "cayley", "server_sat_exact"],
                    help="graph_db source tags")
    ap.add_argument("--target-n", type=int, nargs="+",
                    default=[30, 35, 39],
                    help="N values to probe")
    ap.add_argument("--perturb-steps", type=int, nargs="+",
                    default=[1, 3, 10, 30, 100],
                    help="K values for random-switch perturbation")
    ap.add_argument("--trials", type=int, default=50,
                    help="independent perturbation trials per (target, K)")
    ap.add_argument("--move", nargs="+", default=["switch"],
                    help="move family for descent (default switch)")
    ap.add_argument("--alpha", choices=("approx", "exact"), default="approx")
    ap.add_argument("--candidate-cap", type=int, default=100,
                    help="cap proposals per move per descent step "
                         "(switch enumeration is O(|E|²); cap aggressively)")
    ap.add_argument("--plateau-cap-mult", type=float, default=2.0)
    ap.add_argument("--plateau-eps", type=float, default=5e-3,
                    help="|c_log_end - c_log_target| threshold for "
                         "plateau-match")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    if args.out is None:
        tag = "_".join(args.move) + "_" + "_".join(map(str, args.target_n))
        args.out = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "data", f"basin_radius_{tag}.json")

    if args.alpha == "exact":
        alpha_fn = lambda a: alpha_bb_clique_cover(a)[0]
    else:
        alpha_fn = lambda a: alpha_approx(a, restarts=200)

    rng = random.Random(args.seed)

    # Pick targets ------------------------------------------------------------
    with open_db() as db:
        targets = []
        for src in args.target_source:
            for n in args.target_n:
                rows = db.frontier(by="n", minimize="c_log",
                                   is_k4_free=1, source=src, n=n)
                if not rows:
                    continue
                targets.append(rows[0])
        targets = db.hydrate(targets)

    if not targets:
        print("[basin_radius] no targets found", file=sys.stderr)
        return 1

    print(f"[basin_radius] {len(targets)} targets × "
          f"{len(args.perturb_steps)} K-values × {args.trials} trials  "
          f"move={'+'.join(args.move)}  α={args.alpha}  "
          f"cap={args.candidate_cap}")

    results = []
    for target in targets:
        gid_t = target["graph_id"]
        src_t = target["source"]
        n = target["n"]
        G_t: nx.Graph = target["G"]
        adj_t = np.array(nx.to_numpy_array(G_t, dtype=np.uint8))
        c_log_t = target.get("c_log")
        if c_log_t is None:
            d_max_t = int(adj_t.sum(axis=1).max())
            c_log_t = c_log_value(int(target["alpha"]), n, d_max_t)
        plateau_cap = int(np.ceil(args.plateau_cap_mult * n))

        print(f"\n[basin_radius] === target gid={gid_t} src={src_t} n={n} "
              f"|E|={int(adj_t.sum()//2)} c_log={c_log_t:.4f} ===")

        per_K = {}
        for K in args.perturb_steps:
            t0 = time.monotonic()
            exact_hits = 0
            plateau_hits = 0
            endpoint_clogs: list[float] = []
            for trial in range(args.trials):
                init = perturb_with_switches(adj_t, K, rng)
                res = descend(
                    init,
                    moves=args.move,
                    alpha_fn=alpha_fn,
                    rng=rng,
                    plateau_cap=plateau_cap,
                    candidate_cap=args.candidate_cap,
                )
                final = res["final_adj"]
                d_max_e = int(final.sum(axis=1).max())
                a_e = int(alpha_fn(final))
                cl_e = (c_log_value(a_e, n, d_max_e)
                        if d_max_e > 1 else None)
                endpoint_clogs.append(cl_e if cl_e is not None else float("nan"))
                try:
                    gid_e, _ = canonical_id(nx.from_numpy_array(final))
                except Exception:
                    gid_e = ""
                if gid_e == gid_t:
                    exact_hits += 1
                if cl_e is not None and abs(cl_e - c_log_t) < args.plateau_eps:
                    plateau_hits += 1
            wall = time.monotonic() - t0
            per_K[K] = {
                "trials": args.trials,
                "exact_hits": exact_hits,
                "plateau_hits": plateau_hits,
                "p_exact": exact_hits / args.trials,
                "p_plateau": plateau_hits / args.trials,
                "endpoint_clogs": endpoint_clogs,
                "wall_time_s": round(wall, 2),
            }
            print(f"  K={K:>4d}  exact={exact_hits:>3d}/{args.trials} "
                  f"({exact_hits/args.trials:.2f})  "
                  f"plateau={plateau_hits:>3d}/{args.trials} "
                  f"({plateau_hits/args.trials:.2f})  "
                  f"({wall:.1f}s)")
        results.append({
            "graph_id": gid_t, "source": src_t, "n": n,
            "c_log": c_log_t,
            "n_edges": int(adj_t.sum() // 2),
            "per_K": per_K,
        })

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w") as f:
        json.dump({
            "move": args.move,
            "alpha_solver": args.alpha,
            "candidate_cap": args.candidate_cap,
            "plateau_cap_mult": args.plateau_cap_mult,
            "plateau_eps": args.plateau_eps,
            "perturb_steps": args.perturb_steps,
            "trials": args.trials,
            "seed": args.seed,
            "results": results,
        }, f, indent=2, default=str)
    print(f"\n[basin_radius] wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
