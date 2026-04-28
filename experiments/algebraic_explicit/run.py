#!/usr/bin/env python3
"""
experiments/algebraic_explicit/run.py
======================================
Unified driver for all closed-form algebraic constructions.

Usage:
    micromamba run -n k4free python experiments/algebraic_explicit/run.py --construction polarity
    micromamba run -n k4free python experiments/algebraic_explicit/run.py --construction polarity --max-n 200
    micromamba run -n k4free python experiments/algebraic_explicit/run.py --construction brown --min-n 100 --max-n 500
    micromamba run -n k4free python experiments/algebraic_explicit/run.py --construction prime_circulants --min-n 50 --max-n 200
    micromamba run -n k4free python experiments/algebraic_explicit/run.py --construction mattheus_verstraete --ns 12 63
    micromamba run -n k4free python experiments/algebraic_explicit/run.py --construction mattheus_verstraete --seed 42 --top-k 5
"""

import argparse
import os
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)

from utils.primes import is_prime
from search import (
    AggregateLogger,
    BrownSearch,
    MattheusVerstraeteSearch,
    NormGraphSearch,
    PolaritySearch,
    PrimeCirculantSearch,
)

_CLASSES = {
    "polarity":            PolaritySearch,
    "brown":               BrownSearch,
    "norm_graph":          NormGraphSearch,
    "prime_circulants":    PrimeCirculantSearch,
    "mattheus_verstraete": MattheusVerstraeteSearch,
}

# Sensible default max-n per construction (used when neither --ns nor --max-n given)
_DEFAULT_MAX_N = {
    "polarity":            183,   # q=13
    "brown":               343,   # q=7
    "norm_graph":          168,   # q=13
    "prime_circulants":    200,
    "mattheus_verstraete": 63,    # q=3; q=5 (n=525) is slow
}


def _eligible_ns(construction: str, min_n: int, max_n: int) -> list[int]:
    """Generate all valid N for a construction in [min_n, max_n]."""
    ns = []
    q = 2
    if construction == "polarity":
        while (n := q * q + q + 1) <= max_n:
            if is_prime(q) and n >= min_n:
                ns.append(n)
            q += 1
    elif construction == "brown":
        while (n := q ** 3) <= max_n:
            if is_prime(q) and q >= 5 and n >= min_n:
                ns.append(n)
            q += 1
    elif construction == "norm_graph":
        while (n := q * q - 1) <= max_n:
            if is_prime(q) and n >= min_n:
                ns.append(n)
            q += 1
    elif construction == "prime_circulants":
        ns = [n for n in range(max(min_n, 5), max_n + 1) if is_prime(n)]
    elif construction == "mattheus_verstraete":
        while (n := q * q * (q * q - q + 1)) <= max_n:
            if is_prime(q) and n >= min_n:
                ns.append(n)
            q += 1
    return ns


def _fmt(x):
    return "—" if x is None else f"{x:.6f}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--construction", required=True, choices=sorted(_CLASSES),
                    help="which algebraic construction to run")
    ap.add_argument("--ns", type=int, nargs="+",
                    help="explicit N values (overrides --min-n / --max-n)")
    ap.add_argument("--min-n", type=int, default=1,
                    help="lower bound on eligible N values")
    ap.add_argument("--max-n", type=int,
                    help="upper bound on eligible N values (default varies by construction)")
    ap.add_argument("--top-k", type=int, default=1,
                    help="max results to keep per N")
    ap.add_argument("--seed", type=int, default=0,
                    help="RNG seed (mattheus_verstraete only)")
    ap.add_argument("--no-save", action="store_true",
                    help="dry run — print results without writing to graph_db")
    args = ap.parse_args()

    if args.ns:
        ns = args.ns
    else:
        max_n = args.max_n if args.max_n is not None else _DEFAULT_MAX_N[args.construction]
        ns = _eligible_ns(args.construction, args.min_n, max_n)

    if not ns:
        print(f"No eligible N values for {args.construction} in the requested range.")
        return 0

    rows = []
    with AggregateLogger(name=f"{args.construction}_sweep") as agg:
        for n in ns:
            t0 = time.monotonic()
            search = _CLASSES[args.construction](
                n=n,
                top_k=args.top_k,
                verbosity=1,
                parent_logger=agg,
                seed=args.seed,
            )
            results = search.run()
            if results and not args.no_save:
                search.save(results)
            dt = time.monotonic() - t0

            if not results:
                print(f"[{args.construction} n={n:>5}] skipped ({dt:.2f}s)", flush=True)
                continue

            for r in results:
                k = r.metadata.get("residue_index")
                rows.append((n, k, r.c_log, r.alpha, r.d_max, r.is_k4_free, dt))
                k_str = f" k={k}" if k is not None else ""
                print(
                    f"[{args.construction} n={n:>5}{k_str}]  "
                    f"c_log={_fmt(r.c_log)}  α={r.alpha}  d_max={r.d_max}  "
                    f"k4_free={int(r.is_k4_free)}  ({dt:.2f}s)",
                    flush=True,
                )

    if not rows:
        print("(no results)")
        return 0

    has_k = any(k is not None for _, k, *_ in rows)
    print()
    print("=" * 72)
    print(
        f"{'n':>6}"
        + (f"{'k':>4}" if has_k else "")
        + f"{'c_log':>14}{'α':>6}{'d_max':>7}{'t(s)':>9}"
    )
    print("=" * 72)
    for n, k, c, a, d, k4, dt in rows:
        print(
            f"{n:>6}"
            + (f"{k:>4}" if has_k else "")
            + f"{_fmt(c):>14}{a:>6}{d:>7}{dt:>9.2f}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
