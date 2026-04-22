"""
Faster variant of prototype_sat_circulant.py: vectorized K4 triple enumeration
with packed-uint64 dedup. Also computes exact α for the returned circulant.

Usage:
  micromamba run -n k4free python scripts/prototype_sat_circulant_fast.py --n 1000 --d 16
"""

import argparse
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ortools.sat.python import cp_model
from utils.graph_props import alpha_cpsat, c_log_value


def _k4_keys_fast(n: int) -> np.ndarray:
    """Return unique sorted 6-tuples of folded gaps packed into uint64.

    Each gap k ∈ [1, n//2] fits in ceil(log2(n)) bits. We pack 6 sorted gaps
    with 11 bits each (up to n ≈ 2048) into one uint64 and dedup via np.unique.
    """
    assert n <= 2048, "packing uses 11 bits per gap"
    half = n // 2
    BITS = 11
    MASK = (1 << BITS) - 1

    all_keys = []
    for a in range(1, n - 2):
        fa = a if 2 * a <= n else n - a
        for b in range(1, n - a - 1):
            c_max = n - a - b - 1
            if c_max < 1:
                continue
            fb = b if 2 * b <= n else n - b
            ab = a + b
            fab = ab if 2 * ab <= n else n - ab

            cs = np.arange(1, c_max + 1, dtype=np.int64)
            fcs = np.where(2 * cs <= n, cs, n - cs)
            bcs = b + cs
            fbcs = np.where(2 * bcs <= n, bcs, n - bcs)
            abcs = a + b + cs
            fabcs = np.where(2 * abcs <= n, abcs, n - abcs)

            # stack into (L, 6) and sort along axis 1
            block = np.stack(
                [
                    np.full_like(cs, fa),
                    np.full_like(cs, fb),
                    fcs,
                    np.full_like(cs, fab),
                    fbcs,
                    fabcs,
                ],
                axis=1,
            )
            block.sort(axis=1)

            # pack
            packed = (
                (block[:, 0].astype(np.uint64) << (BITS * 5))
                | (block[:, 1].astype(np.uint64) << (BITS * 4))
                | (block[:, 2].astype(np.uint64) << (BITS * 3))
                | (block[:, 3].astype(np.uint64) << (BITS * 2))
                | (block[:, 4].astype(np.uint64) << BITS)
                | block[:, 5].astype(np.uint64)
            )
            all_keys.append(packed)

    if not all_keys:
        return np.empty(0, dtype=np.uint64)
    flat = np.concatenate(all_keys)
    return np.unique(flat)


def _unpack(key: np.uint64) -> tuple[int, ...]:
    BITS = 11
    MASK = (1 << BITS) - 1
    return tuple(int((key >> (BITS * (5 - i))) & MASK) for i in range(6))


def build_model(n: int, target_d: int | None, *, pin_g1: bool = False):
    t0 = time.time()
    half = n // 2
    keys = _k4_keys_fast(n)
    t_keys = time.time() - t0

    t1 = time.time()
    model = cp_model.CpModel()
    g = [None] + [model.NewBoolVar(f"g_{k}") for k in range(1, half + 1)]

    n_clauses = 0
    for key in keys.tolist():
        gaps = _unpack(np.uint64(key))
        distinct = set(gaps)
        model.AddBoolOr([g[k].Not() for k in distinct])
        n_clauses += 1

    if target_d is not None:
        if n % 2 == 0:
            model.Add(2 * sum(g[k] for k in range(1, half)) + g[half] == target_d)
        else:
            model.Add(2 * sum(g[k] for k in range(1, half + 1)) == target_d)

    if pin_g1:
        model.Add(g[1] == 1)
    t_build = time.time() - t1

    return model, g, t_keys, t_build, n_clauses


def extract_S(solver, g, n):
    half = n // 2
    return [k for k in range(1, half + 1) if solver.Value(g[k]) == 1]


def _circulant_adj(n: int, S_half: list[int]) -> np.ndarray:
    S_full = set()
    for s in S_half:
        S_full.add(s % n)
        S_full.add((n - s) % n)
    S_arr = np.fromiter(S_full, dtype=np.int64, count=len(S_full))
    adj = np.zeros((n, n), dtype=np.uint8)
    for i in range(n):
        adj[i, (i + S_arr) % n] = 1
    return adj


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, required=True)
    ap.add_argument("--d", type=int, default=None)
    ap.add_argument("--time-limit", type=float, default=300.0)
    ap.add_argument("--alpha-time-limit", type=float, default=120.0)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--pin-g1", action="store_true")
    ap.add_argument("--no-alpha", action="store_true", help="skip α computation")
    args = ap.parse_args()

    print(f"N={args.n}  d={args.d}  pin_g1={args.pin_g1}")
    t0 = time.time()
    model, g, t_keys, t_build, n_cl = build_model(args.n, args.d, pin_g1=args.pin_g1)
    print(f"  keys: {t_keys:.2f}s  build: {t_build:.2f}s  clauses={n_cl}")

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = args.time_limit
    solver.parameters.num_search_workers = args.workers
    t_s = time.time()
    status = solver.Solve(model)
    t_solve = time.time() - t_s
    name = solver.StatusName(status)
    print(f"  solve: {t_solve:.2f}s  status={name}")

    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        S = extract_S(solver, g, args.n)
        d_max = 2 * len(S) - (1 if args.n % 2 == 0 and args.n // 2 in S else 0)
        print(f"  S = {S}  |S|={len(S)}  d_max={d_max}")

        if not args.no_alpha:
            t_a = time.time()
            adj = _circulant_adj(args.n, S)
            alpha, _ = alpha_cpsat(
                adj,
                vertex_transitive=True,
                time_limit=args.alpha_time_limit,
            )
            t_alpha = time.time() - t_a
            c = c_log_value(alpha, args.n, d_max)
            print(f"  alpha: {t_a:.2f}s α={alpha}  c_log={c}")

    print(f"  total: {time.time()-t0:.2f}s")


if __name__ == "__main__":
    main()
