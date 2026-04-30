"""
experiments/edge_gradients/run_followpath_sweep.py
==================================================
Sweep the saddle-escape gradient-following test across multiple N
values. Concatenates each per-N run into combined CSVs with an extra
`n` column.

CLI:
  --ns 15,18,20,22,25     comma-separated N values
  --seeds 25              saddle starts per N
  --steps 20              T per trajectory
  --density 0.30          density for random K4-free generation
  --rng-seed 42           base RNG seed (per-N seed = rng-seed + n)
  --methods               comma-separated methods. Default trims expensive
                          ones at large N (drop_e_max & drop_l_hc kept
                          only for n ≤ 22).
"""
from __future__ import annotations

import argparse
import csv
import os
import random
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from nonedge_methods import METHODS  # noqa: E402
from run_followpath import find_saddles, trajectory  # noqa: E402
from utils.graph_props import alpha_bb_clique_cover_nx as alpha_nx  # noqa: E402


# Default method ladder by graph size — cheap methods always run; the
# O(|E|·2^N) drop-* methods are gated on n.
DEFAULT_CHEAP = ["random", "drop_alpha", "hardcore_comarg",
                 "sdp_X_uw", "lp_xu_plus_xw", "hoffman_grad"]
DEFAULT_EXPENSIVE = ["drop_e_max", "drop_l_hc"]
EXPENSIVE_N_CAP = 20


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ns", default="15,18,20,22,25")
    ap.add_argument("--seeds", type=int, default=25)
    ap.add_argument("--steps", type=int, default=20)
    ap.add_argument("--density", type=float, default=0.30)
    ap.add_argument("--rng-seed", type=int, default=42)
    ap.add_argument("--methods", default=None,
                    help="Override the n-gated default. Comma-separated.")
    ap.add_argument("--expensive-n-cap", type=int, default=EXPENSIVE_N_CAP)
    ap.add_argument("--out", default=os.path.join(HERE, "sweep_results.csv"))
    ap.add_argument("--summary", default=os.path.join(HERE, "sweep_summary.csv"))
    args = ap.parse_args()

    ns = [int(x) for x in args.ns.split(",") if x.strip()]
    print(f"[sweep] N sweep over {ns}, seeds={args.seeds}, T={args.steps}",
          flush=True)

    rows: list[dict] = []
    summary: list[dict] = []
    grand_t0 = time.time()

    for n in ns:
        if args.methods:
            method_names = [m.strip() for m in args.methods.split(",")]
        else:
            method_names = list(DEFAULT_CHEAP)
            if n <= args.expensive_n_cap:
                method_names = method_names + DEFAULT_EXPENSIVE
        print(f"\n[sweep] === N = {n} ===  methods = {method_names}", flush=True)
        n_t0 = time.time()
        rng = random.Random(args.rng_seed + n)
        saddles = find_saddles(n, args.seeds, args.density, rng)
        print(f"[sweep] N={n}: {len(saddles)} saddles", flush=True)

        for sidx, (G0, a0, _, _) in enumerate(saddles):
            for method in method_names:
                traj_rng = random.Random(args.rng_seed * 1_000 + n * 1_000 + sidx)
                t_start = time.time()
                r = trajectory(G0, method, args.steps, traj_rng)
                wall = time.time() - t_start
                alphas = r["alphas"]
                for t, a in enumerate(alphas):
                    rows.append(dict(
                        n=n, saddle=sidx, method=method, t=t,
                        alpha=a, alpha_drop=a0 - a,
                        m0=G0.number_of_edges(),
                        skipped=int(r["skipped"]),
                    ))
                first_drop = next((t for t, a in enumerate(alphas) if a < a0), None)
                wasted = sum(1 for i in range(1, len(alphas))
                             if alphas[i] == alphas[i - 1])
                summary.append(dict(
                    n=n, saddle=sidx, method=method,
                    a0=a0, alpha_final=alphas[-1],
                    alpha_drop=a0 - alphas[-1],
                    steps_taken=len(alphas) - 1,
                    first_drop_t=first_drop,
                    wasted_steps=wasted,
                    wall_s=round(wall, 3),
                    skipped=int(r["skipped"]),
                ))
            if (sidx + 1) % 5 == 0 or sidx + 1 == len(saddles):
                print(f"  N={n} [{sidx+1}/{len(saddles)}] "
                      f"({time.time() - n_t0:.0f}s elapsed in this N)",
                      flush=True)
        print(f"[sweep] N={n} done in {time.time() - n_t0:.1f}s",
              flush=True)

    print(f"\n[sweep] total wall = {time.time() - grand_t0:.1f}s", flush=True)
    with open(args.out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        for r in rows:
            w.writerow(r)
    with open(args.summary, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(summary[0].keys()))
        w.writeheader()
        for r in summary:
            w.writerow(r)
    print(f"[sweep] wrote {args.out} ({len(rows)} rows) and "
          f"{args.summary} ({len(summary)} rows)")


if __name__ == "__main__":
    main()
