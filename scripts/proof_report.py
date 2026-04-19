#!/usr/bin/env python3
"""
scripts/proof_report.py
=======================
Produce a per-N optimality-proof report from the scan logs in
logs/search/ and the targeted-box results in logs/optimality_proofs.json.

For each N in [n_min, n_max]:
  - recover c* (best witness c_log)
  - run verify_optimality logic
  - print PROVED / OPEN status with the list of still-open boxes

Exit status = number of N values still unproved (0 = all optimal).
"""

from __future__ import annotations

import argparse
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from scripts.verify_optimality import (  # noqa: E402
    _load_proofs, _load_scan_log, verify,
)


def _recover_c_star(log_dir: str, n: int) -> float | None:
    """Pull the best_c_log from the most recent scan log for this n."""
    if not os.path.isdir(log_dir):
        return None
    candidates = sorted(
        f for f in os.listdir(log_dir) if f.startswith(f"sat_exact_n{n}_")
    )
    best: float | None = None
    for fname in candidates:
        with open(os.path.join(log_dir, fname)) as f:
            for line in f:
                if "best_c_log=" in line and "SEARCH_END" in line:
                    for tok in line.split():
                        if tok.startswith("best_c_log="):
                            v = tok.split("=", 1)[1]
                            if v and v != "None":
                                try:
                                    c = float(v)
                                    if best is None or c < best:
                                        best = c
                                except ValueError:
                                    pass
    return best


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-min", type=int, default=10)
    ap.add_argument("--n-max", type=int, default=23)
    ap.add_argument("--proofs", type=str,
                    default=os.path.join(REPO, "logs",
                                         "optimality_proofs.json"))
    ap.add_argument("--scan-logs", type=str,
                    default=os.path.join(REPO, "logs", "search"))
    args = ap.parse_args()

    proofs = _load_proofs(args.proofs)
    open_count = 0

    print(f"{'N':>3}  {'c*':>10}  {'status':<8}  open boxes")
    print("-" * 70)
    for n in range(args.n_min, args.n_max + 1):
        c_star = _recover_c_star(args.scan_logs, n)
        if c_star is None:
            print(f"{n:>3}  {'?':>10}  {'NOLOG':<8}  (no scan log)")
            open_count += 1
            continue
        scan = _load_scan_log(args.scan_logs, n)
        rep = verify(n, c_star, proofs, scan)
        if not rep["open"]:
            print(f"{n:>3}  {c_star:>10.6f}  {'PROVED':<8}  ✓")
        else:
            open_count += 1
            tags = ", ".join(f"α={a} d={d}" for a, d, _ in rep["open"])
            print(f"{n:>3}  {c_star:>10.6f}  {'OPEN':<8}  {tags}")
    return open_count


if __name__ == "__main__":
    sys.exit(main())
