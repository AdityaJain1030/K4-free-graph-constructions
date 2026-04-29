#!/usr/bin/env python3
"""
experiments/a_critical_bias/sweep_beta.py
==========================================
Sweep β (softmax temperature) at fixed N and λ. β=∞ is the greedy
ablation (argmax over candidate scores; uniform tie-break).

Usage
-----
    python experiments/a_critical_bias/sweep_beta.py \\
        --n 20 --lam 1.0 --trials 3
"""

from __future__ import annotations

import argparse
import csv
import math
import os
import sys
from types import SimpleNamespace

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, REPO)
sys.path.insert(0, HERE)

from add_remove_a_critical import run


DEFAULT_BETAS = (1.0, 2.0, 4.0, 8.0, float("inf"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, required=True)
    ap.add_argument("--lam", type=float, default=1.0)
    ap.add_argument("--betas", type=str, nargs="+",
                    default=[str(b) for b in DEFAULT_BETAS])
    ap.add_argument("--stop", choices=("none", "edges", "alpha"), default="none")
    ap.add_argument("--target", default=0)
    ap.add_argument("--seed-graph", choices=("empty", "from-db", "random-bk"),
                    default="empty")
    ap.add_argument("--trials", type=int, default=3)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--max-steps", type=int, default=0)
    ap.add_argument("--audit", action="store_true")
    ap.add_argument("--out-csv", default=None)
    args = ap.parse_args()

    betas = []
    for b in args.betas:
        if str(b).lower() in ("inf", "infinity", "greedy"):
            betas.append(float("inf"))
        else:
            betas.append(float(b))

    out_csv = args.out_csv or os.path.join(
        HERE, "results", f"beta_sweep_n{args.n}_lam{args.lam}.csv"
    )
    os.makedirs(os.path.dirname(out_csv), exist_ok=True)

    all_rows: list[dict] = []
    for beta in betas:
        sub = SimpleNamespace(
            n=args.n, lam=args.lam, beta=beta,
            stop=args.stop, target=args.target,
            seed_graph=args.seed_graph,
            w_min_deg=1.0, w_twin=1.0, w_hajnal=1.0,
            lb_restarts=4,
            trials=args.trials, seed=args.seed,
            max_steps=args.max_steps, save=False, audit=args.audit,
        )
        rows = run(sub)
        all_rows.extend(rows)

    if all_rows:
        keys = list(all_rows[0].keys())
        with open(out_csv, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=keys)
            w.writeheader()
            for r in all_rows:
                w.writerow(r)
        print(f"\nWrote {len(all_rows)} rows → {out_csv}")

        print("\n  β        best_c_log    a_critical_count   median_n_bad_v")
        print("  " + "-" * 60)
        by_beta: dict[float, list[dict]] = {}
        for r in all_rows:
            by_beta.setdefault(r["beta"], []).append(r)
        for beta in sorted(by_beta, key=lambda x: (math.isinf(x), x)):
            sub = by_beta[beta]
            cs = [r["c_log"] for r in sub if r["c_log"] is not None]
            best = min(cs) if cs else None
            ac = sum(1 for r in sub if r.get("is_a_critical"))
            bads = sorted([r["n_non_critical_v"] for r in sub
                           if r.get("n_non_critical_v") is not None])
            med = bads[len(bads) // 2] if bads else None
            label = "inf (greedy)" if math.isinf(beta) else f"{beta:<6}"
            print(f"  {label:<10}  {best if best is not None else '—':<10}     "
                  f"{ac}/{len(sub):<3}              {med if med is not None else '—'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
