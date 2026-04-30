#!/usr/bin/env python3
"""
experiments/fragility/run_basin_volume.py
=========================================
Test E — basin volume under greedy descent (object C in
``experiments/fragility/README.md``).

The headline test of the fragility folder. Estimates

    p̂_M(G*) = Pr[ random_init → G* under greedy descent under M ]

for each frontier target G* and each move family M. The decision-
relevant question for the rest of `experiments/`: are c_log frontier
graphs reachable by greedy descent from random init, or are their
basins so small that local search cannot find them?

Pre-registered prediction (April 2026): structured extremizers
(Paley/Cayley) have basins shrinking like exp(−cN); SAT-irregular
optima have larger basins; both are dwarfed by basins of generic
local minima. Falsifier: Paley basin ≥ 1e-2 at N=22.

Pipeline per run
----------------
1. Pick frontier targets G* via --target-source / --target-n.
2. Sample K random K4-free graphs at matched density via the
   Bohman–Keevash adder (random K4-safe edges added one at a time
   until target |E| or saturation).
3. Run greedy descent under --move from each random init:
     * enumerate (or k-cap) all legal proposals
     * if any has Δc_log < 0, take the *best* (uniform tie-break)
     * else if any has Δc_log = 0, take a random plateau move
       (limit total plateau steps to L = 2N)
     * else terminate
   α during descent uses --alpha-descent (default approx, fast).
4. Verify endpoint with --alpha-verify (default exact).
5. Canonicalize endpoint; tally how often it matches each target.

One run handles one move family per command for clarity. Run the
three move families {'add+delete', 'slide', 'switch'} separately and
diff the result tables.

Example
-------
    micromamba run -n k4free python experiments/fragility/run_basin_volume.py \\
        --target-source cayley sat_exact --target-n 17 19 22 \\
        --move add delete --inits 1000 --plateau-cap-mult 2

Output goes to ``experiments/fragility/data/basin_volume_<move>.json``.
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
    find_k4,
)
from utils.nauty import canonical_id  # noqa: E402

from experiments.fragility.move_taxonomy import (  # noqa: E402
    _ENUMERATORS, all_move_kinds, best_step, sample_n_proposals,
)


# ---------------------------------------------------------------------------
# Random K4-free seed generator (Bohman–Keevash adder, density-targeted)
# ---------------------------------------------------------------------------

def random_k4free(n: int, target_edges: int | None,
                  rng: random.Random) -> np.ndarray:
    """Build a K4-free graph by adding K4-safe random edges one at a time
    until target_edges is reached, or saturation if target_edges is None.

    Uses a permutation of all non-edges; tries them in random order. This
    is exactly the Bohman–Keevash process (uniform among K4-safe edges
    at each step).
    """
    adj = np.zeros((n, n), dtype=np.uint8)
    pairs = [(i, j) for i in range(n) for j in range(i + 1, n)]
    rng.shuffle(pairs)
    added = 0
    for u, v in pairs:
        if target_edges is not None and added >= target_edges:
            break
        adj[u, v] = adj[v, u] = 1
        if find_k4(adj) is not None:
            adj[u, v] = adj[v, u] = 0
        else:
            added += 1
    return adj


# ---------------------------------------------------------------------------
# Greedy descent with plateau handling
# ---------------------------------------------------------------------------

def _c_log_score(alpha_fn):
    def score(adj: np.ndarray) -> float | None:
        n = adj.shape[0]
        d_max = int(adj.sum(axis=1).max())
        if d_max <= 1:
            return None
        return c_log_value(alpha_fn(adj), n, d_max)
    return score


def descend(adj0: np.ndarray, *,
            moves: list[str],
            alpha_fn,
            rng: random.Random,
            plateau_cap: int,
            max_steps: int = 10000,
            candidate_cap: int | None = None,
            ) -> dict:
    """Greedy best-improving descent with random plateau escape.

    Termination:
      * 'stuck' — no legal move at all
      * 'plateau-exhausted' — plateau steps without improvement reach
        plateau_cap
      * 'max-steps' — guard against runaway

    Returns a dict with the final adjacency, descent length, plateau
    count, and termination kind.
    """
    score = _c_log_score(alpha_fn)
    adj = adj0.copy()
    steps_total = 0
    steps_improve = 0
    steps_plateau_run = 0  # consecutive plateau moves since last improve
    steps_plateau_total = 0
    initial_c = score(adj0)

    while steps_total < max_steps:
        # If candidate_cap is set, *sample* candidate_cap proposals
        # per move kind without paying the O(|E|²) enumeration cost.
        if candidate_cap is not None:
            local_score = score
            def _bounded_best_step(_adj):
                base = local_score(_adj)
                if base is None:
                    from experiments.fragility.move_taxonomy import DescentStep
                    return DescentStep(None, 0.0, "stuck")
                best_d = float("inf")
                best_pool = []
                plateau_pool = []
                any_legal = False
                for kind in moves:
                    props = sample_n_proposals(_adj, kind, candidate_cap, rng)
                    for prop in props:
                        s = local_score(prop)
                        if s is None:
                            continue
                        any_legal = True
                        d = s - base
                        if d < -1e-12:
                            if d < best_d - 1e-12:
                                best_d = d
                                best_pool = [prop]
                            elif abs(d - best_d) <= 1e-12:
                                best_pool.append(prop)
                        elif abs(d) <= 1e-12:
                            plateau_pool.append(prop)
                from experiments.fragility.move_taxonomy import DescentStep
                if best_pool:
                    return DescentStep(rng.choice(best_pool), best_d, "improve")
                if plateau_pool:
                    return DescentStep(rng.choice(plateau_pool), 0.0, "plateau")
                return DescentStep(None, 0.0, "stuck")
            step = _bounded_best_step(adj)
        else:
            step = best_step(adj, score, moves, rng=rng)

        if step.kind == "stuck":
            return {
                "final_adj": adj, "kind": "stuck",
                "steps_total": steps_total,
                "steps_improve": steps_improve,
                "steps_plateau_total": steps_plateau_total,
                "initial_c_log": initial_c,
            }
        if step.kind == "improve":
            adj = step.new_adj
            steps_improve += 1
            steps_total += 1
            steps_plateau_run = 0
            continue
        # plateau
        if steps_plateau_run >= plateau_cap:
            return {
                "final_adj": adj, "kind": "plateau-exhausted",
                "steps_total": steps_total,
                "steps_improve": steps_improve,
                "steps_plateau_total": steps_plateau_total,
                "initial_c_log": initial_c,
            }
        adj = step.new_adj
        steps_plateau_run += 1
        steps_plateau_total += 1
        steps_total += 1

    return {
        "final_adj": adj, "kind": "max-steps",
        "steps_total": steps_total,
        "steps_improve": steps_improve,
        "steps_plateau_total": steps_plateau_total,
        "initial_c_log": initial_c,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target-source", nargs="+",
                    default=["cayley", "cayley_tabu_gap", "sat_exact",
                             "server_sat_exact", "brute_force"],
                    help="graph_db source tags whose lowest-c_log graph "
                         "per N is a frontier target.")
    ap.add_argument("--target-n", type=int, nargs="+",
                    default=[15, 17, 19, 22],
                    help="N values to run.")
    ap.add_argument("--move", nargs="+", default=["add", "delete"],
                    choices=all_move_kinds(),
                    help="Move family for this run (descent under union "
                         "of these). Run 'add delete' for the agent-style "
                         "move; 'slide' or 'switch' for the others.")
    ap.add_argument("--inits", type=int, default=1000,
                    help="random K4-free initializations per (target_n)")
    ap.add_argument("--plateau-cap-mult", type=float, default=2.0,
                    help="plateau-step cap = ceil(plateau_cap_mult * N)")
    ap.add_argument("--candidate-cap", type=int, default=None,
                    help="if set, subsample at most this many proposals "
                         "per move per step (k-best-improving descent). "
                         "Useful for switch/flip whose enumeration is big.")
    ap.add_argument("--alpha-descent", choices=("approx", "exact"),
                    default="approx",
                    help="α solver during descent (default approx for speed)")
    ap.add_argument("--alpha-verify", choices=("approx", "exact"),
                    default="exact",
                    help="α solver for endpoint verification")
    ap.add_argument("--density-match", choices=("target", "saturation"),
                    default="target",
                    help="random-init density: match each target's |E| "
                         "exactly, or run BK to saturation")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", default=None,
                    help="output JSON; default "
                         "data/basin_volume_<move-tag>.json")
    args = ap.parse_args()

    move_tag = "_".join(sorted(args.move))
    if args.out is None:
        args.out = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "data", f"basin_volume_{move_tag}.json")

    def _make_alpha(name: str):
        if name == "exact":
            return lambda a: alpha_bb_clique_cover(a)[0]
        return lambda a: alpha_approx(a, restarts=200)

    alpha_descent = _make_alpha(args.alpha_descent)
    alpha_verify = _make_alpha(args.alpha_verify)

    # 1. Pull frontier targets ------------------------------------------------
    with open_db() as db:
        targets: list[dict] = []
        for src in args.target_source:
            for n in args.target_n:
                rows = db.frontier(by="n", minimize="c_log",
                                   is_k4_free=1, source=src, n=n)
                if not rows:
                    continue
                targets.append(rows[0])
        targets = db.hydrate(targets)

    if not targets:
        print("[basin] no targets found; populate graph_db", file=sys.stderr)
        return 1

    target_ids = {t["graph_id"]: (t["source"], t["n"]) for t in targets}
    target_meta = {
        t["graph_id"]: {
            "source": t["source"], "n": t["n"], "c_log": t.get("c_log"),
            "n_edges": int(np.array(nx.to_numpy_array(t["G"])).sum() // 2),
        }
        for t in targets
    }

    print(f"[basin] move={'+'.join(args.move)}  inits/N={args.inits}  "
          f"targets={len(targets)}  α-descent={args.alpha_descent}")
    for gid, meta in target_meta.items():
        print(f"  target {gid}  src={meta['source']:20s} n={meta['n']:>3d} "
              f"|E|={meta['n_edges']:>3d} c_log={meta['c_log']}")

    # 2. For each target N, sample inits and descend --------------------------
    rng = random.Random(args.seed)
    all_runs: list[dict] = []
    target_hits: dict[str, int] = {gid: 0 for gid in target_ids}
    endpoint_counts: dict[str, dict] = {}
    # group targets by N for shared init pool per N
    by_n: dict[int, list[dict]] = {}
    for t in targets:
        by_n.setdefault(t["n"], []).append(t)

    t_outer = time.monotonic()
    for n, t_list in sorted(by_n.items()):
        # density per target — for matched-density runs we use the *largest*
        # |E| among the targets at this N as the cap (so all targets are
        # reachable).
        target_edges_list = [
            int(np.array(nx.to_numpy_array(t["G"])).sum() // 2)
            for t in t_list
        ]
        target_edges = max(target_edges_list) if args.density_match == "target" else None
        plateau_cap = int(np.ceil(args.plateau_cap_mult * n))

        print(f"\n[basin] === N={n}  inits={args.inits}  target_edges="
              f"{target_edges}  plateau_cap={plateau_cap} ===")
        t_n = time.monotonic()
        for run_idx in range(args.inits):
            init_adj = random_k4free(n, target_edges, rng)
            t0 = time.monotonic()
            res = descend(
                init_adj,
                moves=args.move,
                alpha_fn=alpha_descent,
                rng=rng,
                plateau_cap=plateau_cap,
                candidate_cap=args.candidate_cap,
            )
            wall = time.monotonic() - t0
            final_adj = res["final_adj"]
            try:
                gid_end, _ = canonical_id(nx.from_numpy_array(final_adj))
            except Exception:
                gid_end = "ERR"

            # endpoint stats
            n_edges_end = int(final_adj.sum() // 2)
            d_max_end = int(final_adj.sum(axis=1).max())
            alpha_end = int(alpha_verify(final_adj)) if d_max_end > 0 else 0
            c_log_end = (c_log_value(alpha_end, n, d_max_end)
                         if d_max_end > 1 else None)

            hit = gid_end in target_ids
            if hit:
                target_hits[gid_end] = target_hits.get(gid_end, 0) + 1
            ec = endpoint_counts.setdefault(
                gid_end, {"count": 0, "n": n,
                          "n_edges": n_edges_end, "d_max": d_max_end,
                          "alpha": alpha_end, "c_log": c_log_end,
                          "is_target": hit,
                          "target_meta": target_meta.get(gid_end)})
            ec["count"] += 1

            all_runs.append({
                "n": n, "run_idx": run_idx,
                "endpoint_gid": gid_end,
                "is_target": hit,
                "endpoint_n_edges": n_edges_end,
                "endpoint_d_max": d_max_end,
                "endpoint_alpha": alpha_end,
                "endpoint_c_log": c_log_end,
                "init_n_edges": int(init_adj.sum() // 2),
                "descent_kind": res["kind"],
                "steps_total": res["steps_total"],
                "steps_improve": res["steps_improve"],
                "steps_plateau_total": res["steps_plateau_total"],
                "wall_time_s": round(wall, 3),
            })
            if (run_idx + 1) % max(1, args.inits // 10) == 0:
                hits_so_far = sum(1 for r in all_runs
                                  if r["n"] == n and r["is_target"])
                print(f"  N={n} {run_idx+1}/{args.inits}  "
                      f"target-hits={hits_so_far}  "
                      f"({wall:.2f}s)")
        print(f"[basin] N={n} done in {time.monotonic() - t_n:.1f}s")

    # 3. Aggregate ------------------------------------------------------------
    summary = []
    for gid, meta in target_meta.items():
        n = meta["n"]
        denom = sum(1 for r in all_runs if r["n"] == n)
        hits = target_hits.get(gid, 0)
        p_hat = hits / denom if denom else 0.0
        summary.append({
            "target_gid": gid,
            "source": meta["source"],
            "n": n,
            "target_c_log": meta["c_log"],
            "inits": denom,
            "hits": hits,
            "p_hat": p_hat,
        })

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w") as f:
        json.dump({
            "move": args.move,
            "alpha_descent": args.alpha_descent,
            "alpha_verify": args.alpha_verify,
            "inits_per_n": args.inits,
            "plateau_cap_mult": args.plateau_cap_mult,
            "candidate_cap": args.candidate_cap,
            "density_match": args.density_match,
            "seed": args.seed,
            "summary": summary,
            "endpoint_counts": endpoint_counts,
            "runs": all_runs,
        }, f, indent=2, default=str)

    print(f"\n[basin] wrote {args.out} "
          f"(total {time.monotonic() - t_outer:.1f}s)")
    print("\n[basin] target hit rates:")
    for s in sorted(summary, key=lambda x: (x["n"], -x["p_hat"])):
        print(f"  N={s['n']:>3d} src={s['source']:20s} "
              f"hits={s['hits']:>4d}/{s['inits']:<4d}  "
              f"p̂={s['p_hat']:.3e}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
