#!/usr/bin/env python3
"""
scripts/ablate_sat_exact.py
============================
Ablation harness for SATExact optimizations. Sweeps a set of configs
at N=10..15 with a per-box SAT timeout, reports elapsed time and best
c_log for each. Raw JSON written to logs/sat_exact_ablation.json.

Each optimization is a kwarg flag on SATExact; configs are combinations
of those flags. Point of this file: answer, for each optimization,
"did it actually help, and how much?" — individually and in combination.

Reference c_log (from reference/pareto):
    n=12 → 0.7767,  n=15 → 0.7195
Runs that don't match these are reported with a ❌; runs that match with ✓.
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


REFERENCE_C_LOG = {12: 0.7767, 15: 0.7195}

# Each config is (label, kwargs). Kwargs must name SATExact kwargs exactly.
# The default new-opt config below must explicitly disable c_log_prune and
# seed_from_circulant where it is not wanted — both are True by default on
# SATExact. Without these kwargs every config would inherit the full set of
# accelerators and the ablation table would read flat.
_NO_CLOG = {"c_log_prune": False,
            "seed_from_circulant": False}

CONFIGS: list[tuple[str, dict]] = [
    # Baseline: no symmetry, no Ramsey, no c_log prune, no seed.
    ("baseline",
     {"symmetry_mode": "none", "ramsey_prune": False,
      "scan_from_ramsey_floor": False, **_NO_CLOG}),
    # One optimization at a time.
    ("ramsey_prune",
     {"symmetry_mode": "none", "ramsey_prune": True,
      "scan_from_ramsey_floor": False, **_NO_CLOG}),
    ("scan_floor",
     {"symmetry_mode": "none", "ramsey_prune": True,
      "scan_from_ramsey_floor": True, **_NO_CLOG}),
    ("sym_anchor",
     {"symmetry_mode": "anchor", "ramsey_prune": False,
      "scan_from_ramsey_floor": False, **_NO_CLOG}),
    ("sym_chain",
     {"symmetry_mode": "chain", "ramsey_prune": False,
      "scan_from_ramsey_floor": False, **_NO_CLOG}),
    ("sym_edgelex",
     {"symmetry_mode": "edge_lex", "ramsey_prune": False,
      "scan_from_ramsey_floor": False, **_NO_CLOG}),
    # Stacked.
    ("ramsey+anchor",
     {"symmetry_mode": "anchor", "ramsey_prune": True,
      "scan_from_ramsey_floor": True, **_NO_CLOG}),
    ("ramsey+chain",
     {"symmetry_mode": "chain", "ramsey_prune": True,
      "scan_from_ramsey_floor": True, **_NO_CLOG}),
    ("ramsey+edgelex",
     {"symmetry_mode": "edge_lex", "ramsey_prune": True,
      "scan_from_ramsey_floor": True, **_NO_CLOG}),
    # c_log-bound pruning (the big N≥16 win). Measured in isolation and
    # stacked on top of the ramsey+edgelex stack.
    ("clog_prune_only",
     {"symmetry_mode": "none", "ramsey_prune": False,
      "scan_from_ramsey_floor": False,
      "c_log_prune": True,
      "seed_from_circulant": False}),
    ("clog_prune+seed",
     {"symmetry_mode": "none", "ramsey_prune": False,
      "scan_from_ramsey_floor": False,
      "c_log_prune": True,
      "seed_from_circulant": True}),
    # Full stack — current default.
    ("all_on",
     {"symmetry_mode": "edge_lex", "ramsey_prune": True,
      "scan_from_ramsey_floor": True,
      "c_log_prune": True,
      "seed_from_circulant": True}),
]


def _run_one(n: int, cfg: dict, timeout_s: float, workers: int) -> dict:
    t0 = time.monotonic()
    s = SATExact(
        n=n, top_k=n, verbosity=0, timeout_s=timeout_s, workers=workers,
        **cfg,
    )
    results = s.run()
    dt = time.monotonic() - t0
    best = results[0] if results else None
    c_log = round(best.c_log, 4) if best and best.c_log is not None else None
    ref = REFERENCE_C_LOG.get(n)
    match = (ref is None) or (c_log == ref)
    return {
        "n":        n,
        "elapsed":  round(dt, 2),
        "c_log":    c_log,
        "alpha":    best.alpha if best else None,
        "d_max":    best.d_max if best else None,
        "n_results": len(results),
        "matches_ref": match,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-min", type=int, default=10)
    ap.add_argument("--n-max", type=int, default=15)
    ap.add_argument("--timeout", type=float, default=60.0,
                    help="Per-box SAT timeout in seconds.")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--configs", type=str, default=None,
                    help="Comma-separated list of config labels to run "
                         "(default: all).")
    ap.add_argument("--out-json", type=str,
                    default=os.path.join(REPO, "logs",
                                         "sat_exact_ablation.json"))
    args = ap.parse_args()

    configs = CONFIGS
    if args.configs:
        want = set(args.configs.split(","))
        configs = [(lbl, cfg) for (lbl, cfg) in CONFIGS if lbl in want]
        if not configs:
            ap.error(f"no configs matched {want}")

    ns = list(range(args.n_min, args.n_max + 1))
    results_by_config: dict[str, list[dict]] = {}
    for label, cfg in configs:
        print(f"\n── {label}  ({cfg}) ──")
        per_n = []
        for n in ns:
            row = _run_one(n, cfg, args.timeout, args.workers)
            per_n.append(row)
            mark = "✓" if row["matches_ref"] else "❌"
            print(f"  n={n:>2}: c_log={row['c_log']} "
                  f"α={row['alpha']} d={row['d_max']}  "
                  f"{row['elapsed']:>7.2f}s  {mark}")
        total = sum(r["elapsed"] for r in per_n)
        max_n_s = max(r["elapsed"] for r in per_n)
        print(f"  Σ {total:.2f}s   max-N {max_n_s:.2f}s")
        results_by_config[label] = per_n

    os.makedirs(os.path.dirname(os.path.abspath(args.out_json)) or ".",
                exist_ok=True)
    payload = {
        "n_range":  [args.n_min, args.n_max],
        "timeout":  args.timeout,
        "workers":  args.workers,
        "configs":  {lbl: cfg for lbl, cfg in configs},
        "results":  results_by_config,
    }
    with open(args.out_json, "w") as f:
        json.dump(payload, f, indent=2)
    print(f"\nWrote raw → {args.out_json}")

    # Summary table.
    print()
    print("=" * 78)
    header = f"{'config':<18}"
    for n in ns:
        header += f"  n={n:>2}"
    header += f"  {'Σ':>8}  {'max':>7}"
    print(header)
    print("=" * 78)
    for label, _ in configs:
        per_n = results_by_config[label]
        row = f"{label:<18}"
        for r in per_n:
            mark = "" if r["matches_ref"] else "!"
            row += f"  {r['elapsed']:>4.1f}{mark:1}"
        row += f"  {sum(r['elapsed'] for r in per_n):>7.1f}s"
        row += f"  {max(r['elapsed'] for r in per_n):>6.1f}s"
        print(row)
    print("=" * 78)
    return 0


if __name__ == "__main__":
    sys.exit(main())
