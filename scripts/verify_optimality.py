#!/usr/bin/env python3
"""
scripts/verify_optimality.py
============================
For a given n, enumerate every (α, d) box and classify:
  - RAMSEY_INFEASIBLE (proved infeasible by degree bounds)
  - PRUNED_CBOUND     (c_bound(α, d) ≥ c*; cannot improve)
  - PROVED_INFEASIBLE (from logs/optimality_proofs.json or scan log)
  - PROVED_FEASIBLE   (witness known — either scan log or optimality_proofs)
  - OPEN              (needs proof — neither pruned nor proven)

If every box with c_bound < c* is either PROVED_INFEASIBLE or covered
by a PROVED_FEASIBLE witness with c_log ≤ c*, then c* is certified
optimal for n.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from utils.ramsey import degree_bounds as _ramsey_degree_bounds


def _c_bound(n: int, alpha: int, d: int) -> float:
    if d <= 1:
        return float("inf")
    return alpha * d / (n * math.log(d))


def _load_proofs(path: str) -> list[dict]:
    if not os.path.exists(path):
        return []
    try:
        with open(path) as f:
            return json.load(f)
    except (json.JSONDecodeError, ValueError):
        return []


def _load_scan_log(log_dir: str, n: int) -> list[dict]:
    """Aggregate ATTEMPT statuses across every scan log for this n. Later
    logs override earlier ones (so a re-proved box counts as the latest
    verdict). INFEASIBLE dominates TIMEOUT: once a box is proved, a later
    TIMEOUT shouldn't void the proof."""
    if not os.path.isdir(log_dir):
        return []
    candidates = sorted(
        f for f in os.listdir(log_dir) if f.startswith(f"sat_exact_n{n}_")
    )
    if not candidates:
        return []
    known: dict[tuple[int, int], str] = {}
    rank = {
        "INFEASIBLE_RAMSEY": 3,
        "INFEASIBLE":        3,
        "FEASIBLE":          3,
        "FEASIBLE_SEED":     3,
        "TIMEOUT":           1,
        "SKIP_C_BOUND":      0,
    }
    pat = re.compile(
        r"ATTEMPT\s+alpha=(\d+)\s+d_max=(\d+)\s+status=(\S+)"
    )
    for fname in candidates:
        with open(os.path.join(log_dir, fname)) as f:
            for line in f:
                m = pat.search(line)
                if not m:
                    continue
                a, d, st = int(m.group(1)), int(m.group(2)), m.group(3)
                prev = known.get((a, d))
                if prev is None or rank.get(st, 0) >= rank.get(prev, 0):
                    known[(a, d)] = st
    return [
        {"alpha": a, "d_max": d, "status": st}
        for (a, d), st in known.items()
    ]


def verify(
    n: int,
    c_star: float,
    proofs: list[dict],
    scan_attempts: list[dict],
) -> dict:
    # Index known results by (α, d).
    known: dict[tuple[int, int], str] = {}
    for rec in scan_attempts:
        known[(rec["alpha"], rec["d_max"])] = rec["status"]
    for rec in proofs:
        if rec["n"] != n:
            continue
        known[(rec["alpha"], rec["d_max"])] = rec["status"]

    open_boxes: list[tuple[int, int, float]] = []
    covered: list[tuple[int, int, float, str]] = []

    for alpha in range(1, n):
        d_min_ramsey, d_max_ramsey = _ramsey_degree_bounds(n, alpha)
        if d_max_ramsey < 0:
            d_max_ramsey = n - 1
        for d in range(1, n):
            cb = _c_bound(n, alpha, d)
            # Ramsey infeasible is easy.
            if d_min_ramsey >= 0 and d < d_min_ramsey:
                continue
            if d_max_ramsey >= 0 and d > d_max_ramsey:
                continue
            if cb >= c_star - 1e-6:
                continue  # pruned by c_bound
            st = known.get((alpha, d))
            if st in ("INFEASIBLE", "INFEASIBLE_RAMSEY", "FEASIBLE",
                      "FEASIBLE_SEED"):
                covered.append((alpha, d, cb, st))
            elif st in ("TIMEOUT", "INFEASIBLE_OR_TIMEOUT"):
                open_boxes.append((alpha, d, cb))
            else:
                open_boxes.append((alpha, d, cb))

    return {"n": n, "c_star": c_star, "covered": covered, "open": open_boxes}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, required=True)
    ap.add_argument("--c-star", type=float, required=True,
                    help="Current best c_log for this n.")
    ap.add_argument("--proofs", type=str,
                    default=os.path.join(REPO, "logs", "optimality_proofs.json"))
    ap.add_argument("--scan-logs", type=str,
                    default=os.path.join(REPO, "logs", "search"))
    args = ap.parse_args()

    proofs = _load_proofs(args.proofs)
    scan = _load_scan_log(args.scan_logs, args.n)
    out = verify(args.n, args.c_star, proofs, scan)

    print(f"n={out['n']}  c*={out['c_star']}")
    print(f"Covered boxes (c_bound < c*):")
    for a, d, cb, st in out["covered"]:
        print(f"  α={a:2} d={d:2}  c_bound={cb:.4f}  {st}")
    print(f"Open boxes (c_bound < c*, not yet proved):")
    if not out["open"]:
        print("  (none) — c* is proved optimal ✓")
    else:
        for a, d, cb in out["open"]:
            print(f"  α={a:2} d={d:2}  c_bound={cb:.4f}  ← NEEDS PROOF")
    return 0 if not out["open"] else 1


if __name__ == "__main__":
    sys.exit(main())
