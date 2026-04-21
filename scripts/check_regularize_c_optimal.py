"""
scripts/check_regularize_c_optimal.py
=====================================
Same question as check_regularize_nonregular.py but restricted to the
c_log-optimal non-regular graph at each n (i.e. the frontier graphs that
are the current best-known c_log and happen to be non-regular).

For each such G with (n, α, d_max):
  Does there exist a K4-free D-regular graph on n vertices with
    D ≤ d_max(G)  AND  α(G') ≤ α(G)?

Longer budgets per case since the frontier set is small.

Usage:
    micromamba run -n k4free python scripts/check_regularize_c_optimal.py
"""

from __future__ import annotations

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

OUT_PATH = ROOT / "logs" / "regularize_c_optimal.json"

PER_D_TIMEOUT = 120.0
PER_CASE_TIMEOUT = 600.0


def try_regular(n: int, alpha: int, D: int, workers: int, time_limit: float) -> str:
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
    status, _G = s._solve_model(model, x, time_limit=time_limit, hard_params=True)
    return status


def check_one(rec: dict, workers: int) -> dict:
    n, a, d_max, d_min = rec["n"], rec["alpha"], rec["d_max"], rec["d_min"]
    out = {
        "graph_id": rec["graph_id"], "source": rec["source"],
        "n": n, "alpha": a, "d_max": d_max, "d_min": d_min,
        "m": rec["m"], "c_log": rec.get("c_log"),
        "verdict": None, "witness_D": None, "tried": [],
    }
    t_case = time.monotonic()
    any_timeout = False
    for D in range(d_max, 0, -1):  # scan full [1, d_max], top-down
        remaining = PER_CASE_TIMEOUT - (time.monotonic() - t_case)
        if remaining <= 3.0:
            out["tried"].append({"D": D, "status": "SKIPPED_BUDGET"})
            any_timeout = True
            break
        tl = min(PER_D_TIMEOUT, remaining)
        status = try_regular(n, a, D, workers, tl)
        out["tried"].append({"D": D, "status": status, "time_limit_s": round(tl, 1)})
        print(f"    D={D}: {status} ({tl:.0f}s budget)")
        if status in ("FEASIBLE", "OPTIMAL"):
            out["verdict"] = "YES"
            out["witness_D"] = D
            return out
        if status == "TIMEOUT":
            any_timeout = True
    out["verdict"] = "TIMEOUT" if any_timeout else "NO"
    return out


def main() -> None:
    cpus = os.cpu_count() or 8

    with DB() as db:
        frontier = db.frontier(by="n", minimize="c_log", is_k4_free=1)

    targets = [r for r in frontier if not r["is_regular"]]
    print(f"[check] {len(targets)} c-optimal non-regular graphs:")
    for r in targets:
        print(f"    n={r['n']:>3} α={r['alpha']} d=[{r['d_min']},{r['d_max']}] "
              f"c_log={r['c_log']:.4f} src={r['source']}")
    print()

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    results: list[dict] = []
    t0 = time.monotonic()

    for i, rec in enumerate(targets, 1):
        print(f"── [{i}/{len(targets)}] n={rec['n']} α={rec['alpha']} d_max={rec['d_max']} src={rec['source']}")
        t_case = time.monotonic()
        out = check_one(rec, cpus)
        dt = time.monotonic() - t_case
        w = out["verdict"]
        detail = f" witness_D={out['witness_D']}" if out["witness_D"] is not None else ""
        print(f"   → {w}{detail}  ({dt:.1f}s)\n")
        results.append(out)
        with OUT_PATH.open("w") as f:
            json.dump({"results": results, "wall_s": round(time.monotonic() - t0, 2)}, f, indent=2)

    c_yes = sum(1 for r in results if r["verdict"] == "YES")
    c_no = sum(1 for r in results if r["verdict"] == "NO")
    c_to = sum(1 for r in results if r["verdict"] == "TIMEOUT")
    print(f"[check] YES={c_yes}  NO={c_no}  TIMEOUT={c_to}")
    print(f"[check] wrote {OUT_PATH}  ({time.monotonic() - t0:.1f}s)")


if __name__ == "__main__":
    main()
