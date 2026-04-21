"""
scripts/check_regularize_nonregular.py
======================================
For every non-regular K4-free graph G in graph_db, ask:

  Does there exist a K4-free D-regular graph G' on n=n(G) vertices with
    D      ≤ d_max(G)            (d_max does not increase), AND
    α(G')  ≤ α(G)                (α does not increase)?

We don't require preserving the vertex set / edges — the question is whether
a strictly-regular replacement exists within the same (n, α, d_max) envelope.

Approach per graph:
  scan D from d_max(G) down to max(1, d_min(G)). For each D, call SATRegular
  at alpha=α(G), degree_spread=0 (strict D-regular) with a short per-D
  timeout. First FEASIBLE → YES. All D infeasible → NO. Any D timeout with
  no later success → TIMEOUT.

Output: logs/regularize_check.json with per-case verdicts + summary.

Usage:
    micromamba run -n k4free python scripts/check_regularize_nonregular.py
    micromamba run -n k4free python scripts/check_regularize_nonregular.py --n-max 30
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from math import comb
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from graph_db import DB
from search.sat_regular import SATRegular, _LAZY_THRESHOLD

OUT_PATH = ROOT / "logs" / "regularize_check.json"

_DEFAULT_PER_D_TIMEOUT = 20.0
_DEFAULT_PER_CASE_TIMEOUT = 90.0
PER_D_TIMEOUT = _DEFAULT_PER_D_TIMEOUT
PER_CASE_TIMEOUT = _DEFAULT_PER_CASE_TIMEOUT


def try_regular(n: int, alpha: int, D: int, workers: int, time_limit: float) -> str:
    """Return 'FEASIBLE' | 'INFEASIBLE' | 'TIMEOUT'."""
    s = SATRegular(
        n=n, alpha=alpha,
        timeout_s=time_limit, workers=workers,
        degree_spread=0, symmetry_mode="none",
        branch_on_v0=True, minimize_edges=False,
        verbosity=0,
    )
    k = alpha + 1
    direct = (k > n) or (comb(n, k) <= _LAZY_THRESHOLD)
    model, x = s._build_model(
        D=D, enumerate_alpha=direct, alpha_cuts=None, minimize=False,
    )
    status, _G = s._solve_model(model, x, time_limit=time_limit, hard_params=False)
    return status


def check_one(rec: dict, workers: int) -> dict:
    n = rec["n"]
    a = rec["alpha"]
    d_max = rec["d_max"]
    d_min = rec["d_min"]

    out = {
        "graph_id": rec["graph_id"], "source": rec["source"],
        "n": n, "alpha": a, "d_max": d_max, "d_min": d_min,
        "m": rec["m"], "c_log": rec.get("c_log"),
        "verdict": None, "witness_D": None, "tried": [],
    }

    t_case = time.monotonic()
    any_timeout = False
    # Scan D from d_max down to max(1, d_min). Higher D is most likely to satisfy α.
    for D in range(d_max, max(0, d_min - 1), -1):
        remaining = PER_CASE_TIMEOUT - (time.monotonic() - t_case)
        if remaining <= 2.0:
            out["tried"].append({"D": D, "status": "SKIPPED_BUDGET"})
            any_timeout = True
            break
        tl = min(PER_D_TIMEOUT, remaining)
        status = try_regular(n=n, alpha=a, D=D, workers=workers, time_limit=tl)
        out["tried"].append({"D": D, "status": status, "time_limit_s": round(tl, 1)})
        if status in ("FEASIBLE", "OPTIMAL"):
            out["verdict"] = "YES"
            out["witness_D"] = D
            return out
        if status == "TIMEOUT":
            any_timeout = True

    out["verdict"] = "TIMEOUT" if any_timeout else "NO"
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-max", type=int, default=30,
                    help="skip graphs with n greater than this (large n is SAT-hard)")
    ap.add_argument("--per-d-timeout", type=float, default=_DEFAULT_PER_D_TIMEOUT)
    ap.add_argument("--per-case-timeout", type=float, default=_DEFAULT_PER_CASE_TIMEOUT)
    args = ap.parse_args()

    global PER_D_TIMEOUT, PER_CASE_TIMEOUT
    PER_D_TIMEOUT = args.per_d_timeout
    PER_CASE_TIMEOUT = args.per_case_timeout

    cpus = os.cpu_count() or 8

    with DB() as db:
        rows = db.query(is_k4_free=1, is_regular=0, order_by=["n", "alpha"])

    targets = [r for r in rows if r["n"] <= args.n_max]
    skipped_large = [r for r in rows if r["n"] > args.n_max]

    print(f"[check] {len(rows)} non-regular K4-free graphs in DB")
    print(f"[check] n≤{args.n_max}: {len(targets)} to check, {len(skipped_large)} skipped (too large)")
    print(f"[check] per-D={PER_D_TIMEOUT}s, per-case={PER_CASE_TIMEOUT}s, workers={cpus}")
    print()

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    results: list[dict] = []
    t0 = time.monotonic()

    for i, rec in enumerate(targets, 1):
        t_case = time.monotonic()
        out = check_one(rec, cpus)
        dt = time.monotonic() - t_case
        w = out["verdict"]
        tag = f"n={rec['n']:>3} α={rec['alpha']} d_max={rec['d_max']} src={rec['source']:<22s}"
        detail = f"witness_D={out['witness_D']}" if out["witness_D"] is not None else ""
        print(f"[{i:>3}/{len(targets)}] {tag}  {w:<8s} {detail}  t={dt:.1f}s")
        results.append(out)

        if i % 10 == 0 or i == len(targets):
            _persist(results, skipped_large, args, t0)

    _persist(results, skipped_large, args, t0)

    print()
    c_yes = sum(1 for r in results if r["verdict"] == "YES")
    c_no = sum(1 for r in results if r["verdict"] == "NO")
    c_to = sum(1 for r in results if r["verdict"] == "TIMEOUT")
    print(f"[check] verdicts: YES={c_yes}  NO={c_no}  TIMEOUT={c_to}")
    print(f"[check] wall: {time.monotonic() - t0:.1f}s")
    print(f"[check] wrote {OUT_PATH}")

    if c_no:
        print()
        print("NON-REGULARIZABLE cases (witness: no K4-free regular G' with α≤α_G, d≤d_max_G exists):")
        for r in results:
            if r["verdict"] == "NO":
                print(f"  n={r['n']:>3} α={r['alpha']} d_max={r['d_max']} "
                      f"id={r['graph_id'][:10]} src={r['source']}")


def _persist(results, skipped_large, args, t0):
    with OUT_PATH.open("w") as f:
        json.dump({
            "args": {
                "n_max": args.n_max,
                "per_d_timeout_s": PER_D_TIMEOUT,
                "per_case_timeout_s": PER_CASE_TIMEOUT,
            },
            "wall_s": round(time.monotonic() - t0, 2),
            "n_skipped_large": len(skipped_large),
            "skipped_large_ids": [r["graph_id"] for r in skipped_large],
            "results": results,
        }, f, indent=2)


if __name__ == "__main__":
    main()
