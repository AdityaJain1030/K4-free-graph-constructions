"""
Prototype: SAT encoding of K4-free circulants.

Goal: measure how far CP-SAT can push circulant feasibility (and later α).
Encoding:
  - Bool var g[k] for k=1..n/2 (gap indicator).
  - K4-free: for each canonical triple (a, b, c) with a,b,c>=1, a+b+c<n,
    forbid all 6 folded gaps {a, b, c, a+b, b+c, a+b+c} being in S.
  - Optional: degree constraint sum(deg coefficients * g[k]) == d.
  - Optional: symmetry break: g[1] = 1 (pin smallest gap in S). Sound iff
    we dedup by multiplier action afterward — but for feasibility-only
    probes this speeds things up.

What this script does NOT do yet:
  - α bound (CEGAR loop) — separate experiment.
  - Multiplier-action canonical form inside the solver.
"""

import argparse
import time
from math import gcd

from ortools.sat.python import cp_model


def fold(x: int, n: int) -> int:
    x = x % n
    return x if 2 * x <= n else n - x


def _k4_gap_sets(n: int):
    """Yield frozensets of folded gaps for every K4 {0, a, a+b, a+b+c}.

    Deduped across different (a,b,c) triples that produce the same 6-multiset.
    """
    seen = set()
    for a in range(1, n - 2):
        fa = fold(a, n)
        for b in range(1, n - a - 1):
            fb = fold(b, n)
            fab = fold(a + b, n)
            for c in range(1, n - a - b):
                fc = fold(c, n)
                fbc = fold(b + c, n)
                fabc = fold(a + b + c, n)
                key = tuple(sorted((fa, fb, fc, fab, fbc, fabc)))
                if key in seen:
                    continue
                seen.add(key)
                yield key
    return


def build_model(n: int, target_d: int | None, *, pin_g1: bool = False):
    """Return (model, g_vars, t_build_seconds, n_clauses)."""
    t0 = time.time()
    model = cp_model.CpModel()
    half = n // 2
    g = [None] + [model.NewBoolVar(f"g_{k}") for k in range(1, half + 1)]

    n_clauses = 0
    for gap_tuple in _k4_gap_sets(n):
        distinct = set(gap_tuple)  # multiset → set; one g.Not() per distinct k
        # constraint: not all gaps present → at least one gap's g is False
        model.AddBoolOr([g[k].Not() for k in distinct])
        n_clauses += 1

    if target_d is not None:
        if n % 2 == 0:
            # deg = 2*sum(g[1..half-1]) + g[half]
            model.Add(2 * sum(g[k] for k in range(1, half)) + g[half] == target_d)
        else:
            model.Add(2 * sum(g[k] for k in range(1, half + 1)) == target_d)

    if pin_g1:
        model.Add(g[1] == 1)

    return model, g, time.time() - t0, n_clauses


def solve(model, time_limit_s: float = 60.0, workers: int = 8):
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit_s
    solver.parameters.num_search_workers = workers
    t0 = time.time()
    status = solver.Solve(model)
    return solver, status, time.time() - t0


def extract_S(solver, g, n) -> list[int]:
    half = n // 2
    return [k for k in range(1, half + 1) if solver.Value(g[k]) == 1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, required=True)
    ap.add_argument("--d", type=int, default=None, help="target degree (optional)")
    ap.add_argument("--time-limit", type=float, default=60.0)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--pin-g1", action="store_true")
    args = ap.parse_args()

    print(f"N={args.n}  d={args.d}  pin_g1={args.pin_g1}")
    t0 = time.time()
    model, g, t_build, n_cl = build_model(args.n, args.d, pin_g1=args.pin_g1)
    print(f"  build: {t_build:.2f}s  clauses={n_cl}")
    solver, status, t_solve = solve(model, args.time_limit, args.workers)
    name = solver.StatusName(status)
    print(f"  solve: {t_solve:.2f}s  status={name}")

    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        S = extract_S(solver, g, args.n)
        print(f"  S = {S}  |S|={len(S)}  deg={2*len(S) - (1 if args.n%2==0 and args.n//2 in S else 0)}")

    print(f"  total: {time.time()-t0:.2f}s")


if __name__ == "__main__":
    main()
