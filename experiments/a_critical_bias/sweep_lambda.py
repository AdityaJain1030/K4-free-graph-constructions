#!/usr/bin/env python3
"""
experiments/a_critical_bias/sweep_lambda.py
============================================
Sweep λ (the α-criticality penalty weight) at fixed N and β. Records one
CSV row per trial × λ and prints a summary table.

λ=0 is the control (no α-bias; pure c_log_surrogate gradient over the
add+remove valid set).

Usage
-----
    python experiments/a_critical_bias/sweep_lambda.py \\
        --n 20 --beta 4 --trials 3 --stop alpha --target 5
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
from types import SimpleNamespace

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, REPO)
sys.path.insert(0, HERE)

from add_remove_a_critical import run, _parse_beta


DEFAULT_LAMS = (0.0, 0.01, 0.1, 1.0, 10.0)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, required=True)
    ap.add_argument("--beta", type=_parse_beta, default=4.0)
    ap.add_argument("--lams", type=float, nargs="+", default=list(DEFAULT_LAMS))
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

    out_csv = args.out_csv or os.path.join(
        HERE, "results", f"lambda_sweep_n{args.n}_beta{args.beta}.csv"
    )
    os.makedirs(os.path.dirname(out_csv), exist_ok=True)

    all_rows: list[dict] = []
    for lam in args.lams:
        sub = SimpleNamespace(
            n=args.n, lam=lam, beta=args.beta,
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

        # Summary: best c_log per λ
        print("\n  λ      best_c_log    a_critical_count   median_n_bad_v")
        print("  " + "-" * 60)
        by_lam: dict[float, list[dict]] = {}
        for r in all_rows:
            by_lam.setdefault(r["lam"], []).append(r)
        for lam in sorted(by_lam):
            sub = by_lam[lam]
            cs = [r["c_log"] for r in sub if r["c_log"] is not None]
            best = min(cs) if cs else None
            ac = sum(1 for r in sub if r.get("is_a_critical"))
            bads = sorted([r["n_non_critical_v"] for r in sub
                           if r.get("n_non_critical_v") is not None])
            med = bads[len(bads) // 2] if bads else None
            print(f"  {lam:<6}  {best if best is not None else '—':<10}     "
                  f"{ac}/{len(sub):<3}              {med if med is not None else '—'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
