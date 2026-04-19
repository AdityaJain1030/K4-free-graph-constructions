#!/usr/bin/env python3
"""
scripts/prove_box.py
====================
Target-solve a single (n, α, d) box with extended timeout and aggressive
CP-SAT params, for the stubborn INFEASIBLE/FEASIBLE proofs at the Pareto
feasibility boundary (the boxes where a 60–600s scan timed out).

Appends one record per box to logs/optimality_proofs.json so repeated runs
accumulate proofs instead of overwriting.

Usage
-----
  # Single box
  python scripts/prove_box.py --n 20 --alpha 4 --d-max 6 \\
      --timeout 1800 --workers 4

  # Batch (all open N=20..23 boxes):
  python scripts/prove_box.py --batch open_boxes.json --timeout 1800
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from search import SATExact
from utils.graph_props import alpha_exact_nx, c_log_value, is_k4_free_nx


DEFAULT_OUT = os.path.join(REPO, "logs", "optimality_proofs.json")


def prove_one(
    n: int,
    alpha: int,
    d_max: int,
    *,
    timeout_s: float,
    workers: int,
    symmetry_mode: str,
    random_seed: int | None,
    solver_log: bool,
) -> dict:
    t0 = time.monotonic()
    s = SATExact(
        n=n,
        alpha=alpha,
        d_max=d_max,
        top_k=1,
        verbosity=1,
        timeout_s=timeout_s,
        workers=workers,
        symmetry_mode=symmetry_mode,
        ramsey_prune=True,
        scan_from_ramsey_floor=False,  # caller fixes d explicitly
        c_log_prune=False,              # single-box: no scan pruning
        seed_from_circulant=False,
        hard_box_params=True,
        solver_log=solver_log,
        random_seed=random_seed,
    )
    results = s.run()
    wall = time.monotonic() - t0

    witness = None
    if results:
        G = results[0]
        a, _ = alpha_exact_nx(G)
        d = max(dict(G.degree()).values()) if G.number_of_nodes() else 0
        witness = {
            "alpha_actual": a,
            "d_max_actual": d,
            "c_log":        c_log_value(a, n, d),
            "is_k4_free":   bool(is_k4_free_nx(G)),
            "edges":        sorted(tuple(sorted(e)) for e in G.edges()),
        }
        status = "FEASIBLE"
    else:
        # no results from a single-box call means the box is INFEASIBLE or
        # the solver timed out. Distinguish by checking the log tail — the
        # _single_box path emits one ATTEMPT line with the real status.
        status = "INFEASIBLE_OR_TIMEOUT"
        # Peek the most recent log line for the definitive status.
        log_file = getattr(getattr(s, "_logger", None), "path", None)
        if log_file and os.path.exists(log_file):
            with open(log_file) as fh:
                tail = fh.readlines()[-3:]
            for line in tail:
                if "ATTEMPT" in line and f"alpha={alpha}" in line:
                    if "status=INFEASIBLE" in line and "INFEASIBLE_RAMSEY" not in line:
                        status = "INFEASIBLE"
                    elif "status=INFEASIBLE_RAMSEY" in line:
                        status = "INFEASIBLE_RAMSEY"
                    elif "status=TIMEOUT" in line:
                        status = "TIMEOUT"

    return {
        "n":             n,
        "alpha":         alpha,
        "d_max":         d_max,
        "status":        status,
        "wall_s":        round(wall, 2),
        "timeout_s":     timeout_s,
        "workers":       workers,
        "symmetry_mode": symmetry_mode,
        "random_seed":   random_seed,
        "witness":       witness,
        "timestamp":     time.strftime("%Y-%m-%d %H:%M:%S"),
    }


def _append_result(out_path: str, rec: dict) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(out_path)) or ".", exist_ok=True)
    data: list[dict] = []
    if os.path.exists(out_path):
        try:
            with open(out_path) as f:
                data = json.load(f)
        except (json.JSONDecodeError, ValueError):
            data = []
    data.append(rec)
    with open(out_path, "w") as f:
        json.dump(data, f, indent=2)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n",     type=int)
    ap.add_argument("--alpha", type=int)
    ap.add_argument("--d-max", type=int, dest="d_max")
    ap.add_argument("--batch", type=str, default=None,
                    help="JSON file with [{n, alpha, d_max}, ...]")
    ap.add_argument("--timeout", type=float, default=1800.0)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--symmetry", type=str, default="edge_lex",
                    choices=["none", "anchor", "chain", "edge_lex"])
    ap.add_argument("--random-seed", type=int, default=None)
    ap.add_argument("--solver-log", action="store_true")
    ap.add_argument("--out-json", type=str, default=DEFAULT_OUT)
    args = ap.parse_args()

    if args.batch:
        with open(args.batch) as f:
            boxes = json.load(f)
    elif args.n is not None and args.alpha is not None and args.d_max is not None:
        boxes = [{"n": args.n, "alpha": args.alpha, "d_max": args.d_max}]
    else:
        ap.error("Either --batch or (--n --alpha --d-max) required.")

    for box in boxes:
        print(f"\n── N={box['n']} α={box['alpha']} d={box['d_max']} "
              f"  timeout={args.timeout}s ──", flush=True)
        rec = prove_one(
            n=box["n"],
            alpha=box["alpha"],
            d_max=box["d_max"],
            timeout_s=args.timeout,
            workers=args.workers,
            symmetry_mode=args.symmetry,
            random_seed=args.random_seed,
            solver_log=args.solver_log,
        )
        print(f"  → status={rec['status']}  wall={rec['wall_s']}s")
        if rec["witness"]:
            w = rec["witness"]
            print(f"  witness: α={w['alpha_actual']} d={w['d_max_actual']} "
                  f"c_log={w['c_log']}  k4_free={w['is_k4_free']}")
        _append_result(args.out_json, rec)
    print(f"\nAppended → {args.out_json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
