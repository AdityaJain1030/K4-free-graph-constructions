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
    micromamba run -n k4free python experiments/algebraic_explicit/run.py --construction folded_cube         # iterates d=3..8
    micromamba run -n k4free python experiments/algebraic_explicit/run.py --construction folded_cube --d 4   # Clebsch
    micromamba run -n k4free python experiments/algebraic_explicit/run.py --construction shrikhande
    micromamba run -n k4free python experiments/algebraic_explicit/run.py --construction a5_double_transpositions
    micromamba run -n k4free python experiments/algebraic_explicit/run.py --construction hamming           # default H(3,3)
    micromamba run -n k4free python experiments/algebraic_explicit/run.py --construction hamming --max-n 100
    micromamba run -n k4free python experiments/algebraic_explicit/run.py --construction hamming --d 3 --q 3
    micromamba run -n k4free python experiments/algebraic_explicit/run.py --construction psl_involutions
    micromamba run -n k4free python experiments/algebraic_explicit/run.py --construction psl_involutions --q 7
"""

import argparse
import os
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)

from utils.algebra import is_prime, prime_power
from search import (
    AggregateLogger,
    A5DoubleTranspositionsSearch,
    BrownSearch,
    FoldedCubeSearch,
    HammingSearch,
    MattheusVerstraeteSearch,
    NormGraphSearch,
    PolaritySearch,
    PrimeCirculantSearch,
    PSLInvolutionsSearch,
    ShrikhandeSearch,
)

_CLASSES = {
    "polarity":                 PolaritySearch,
    "brown":                    BrownSearch,
    "norm_graph":               NormGraphSearch,
    "prime_circulants":         PrimeCirculantSearch,
    "mattheus_verstraete":      MattheusVerstraeteSearch,
    "folded_cube":              FoldedCubeSearch,
    "shrikhande":               ShrikhandeSearch,
    "hamming":                  HammingSearch,
    "a5_double_transpositions": A5DoubleTranspositionsSearch,
    "psl_involutions":          PSLInvolutionsSearch,
}

# Sensible default max-n per construction (used when neither --ns nor --max-n given)
_DEFAULT_MAX_N = {
    "polarity":                 183,
    "brown":                    343,
    "norm_graph":               168,
    "prime_circulants":         200,
    "mattheus_verstraete":      63,
    "folded_cube":              256,   # through d=8 (folded 9-cube)
    "shrikhande":               16,
    "hamming":                  64,    # H(3,4), H(2,8); H(3,3)=27 is the only K4-free hit
    "a5_double_transpositions": 60,
    "psl_involutions":          1100,  # through PSL(2, 13)
}


def _psl_order(q: int) -> int:
    """|PSL(2, q)| = q(q²−1) / gcd(2, q−1)."""
    return q * (q * q - 1) // (1 if q % 2 == 0 else 2)


def _eligible_calls(
    construction: str,
    min_n: int,
    max_n: int,
    *,
    q_filter: int | None = None,
    d_filter: int | None = None,
) -> list[tuple[int, dict]]:
    """Generate (N, extra_kwargs) pairs for the construction in [min_n, max_n].

    `q_filter` / `d_filter` restrict the parameter sweep when set.
    """
    out: list[tuple[int, dict]] = []
    q = 2

    if construction == "polarity":
        while (n := q * q + q + 1) <= max_n:
            if prime_power(q) is not None and n >= min_n:
                out.append((n, {}))
            q += 1
    elif construction == "brown":
        while (n := q ** 3) <= max_n:
            if is_prime(q) and q >= 5 and n >= min_n:
                out.append((n, {}))
            q += 1
    elif construction == "norm_graph":
        while (n := q * q - 1) <= max_n:
            if is_prime(q) and n >= min_n:
                out.append((n, {}))
            q += 1
    elif construction == "prime_circulants":
        out = [(n, {}) for n in range(max(min_n, 5), max_n + 1) if is_prime(n)]
    elif construction == "mattheus_verstraete":
        while (n := q * q * (q * q - q + 1)) <= max_n:
            if is_prime(q) and n >= min_n:
                out.append((n, {}))
            q += 1
    elif construction == "folded_cube":
        # Cay(Z_2^d, {e_1, ..., e_d, all-ones}). K4-free for d ≥ 3.
        # d=4 reproduces Clebsch.
        for d_val in range(3, 12):
            if d_filter is not None and d_val != d_filter:
                continue
            n = 2 ** d_val
            if n < min_n or n > max_n:
                continue
            out.append((n, {"d": d_val}))
    elif construction == "shrikhande":
        if min_n <= 16 <= max_n:
            out.append((16, {}))
    elif construction == "a5_double_transpositions":
        if min_n <= 60 <= max_n:
            out.append((60, {}))
    elif construction == "hamming":
        # Iterate (d, q); K4-freeness checks at runtime, but we limit the
        # sweep to q ∈ [2, 6] and d ∈ [2, 6] for sanity.
        for q_val in range(2, 7):
            if q_filter is not None and q_val != q_filter:
                continue
            for d_val in range(2, 7):
                if d_filter is not None and d_val != d_filter:
                    continue
                n = q_val ** d_val
                if n < min_n or n > max_n:
                    continue
                out.append((n, {"d": d_val, "q": q_val}))
    elif construction == "psl_involutions":
        # Iterate q over prime powers; |PSL(2,q)| in range. Dedupe by n
        # so PSL(2,4) ≅ PSL(2,5) (both 60) is run once at the smaller q.
        seen_n: set[int] = set()
        q_val = 2
        while True:
            if prime_power(q_val) is not None:
                n = _psl_order(q_val)
                if n > max_n and q_val > 2:
                    break
                if min_n <= n <= max_n and n not in seen_n:
                    if q_filter is None or q_val == q_filter:
                        out.append((n, {"q": q_val}))
                        seen_n.add(n)
            q_val += 1
            if q_val > 200:
                break

    return out


def _fmt(x):
    return "—" if x is None else f"{x:.6f}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--construction", required=True, choices=sorted(_CLASSES),
                    help="which algebraic construction to run")
    ap.add_argument("--ns", type=int, nargs="+",
                    help="explicit N values (overrides --min-n / --max-n; for "
                         "parameterized constructions also requires explicit "
                         "--q and/or --d)")
    ap.add_argument("--min-n", type=int, default=1,
                    help="lower bound on eligible N values")
    ap.add_argument("--max-n", type=int,
                    help="upper bound on eligible N values (default varies by construction)")
    ap.add_argument("--q", type=int, default=None,
                    help="restrict q parameter (psl_involutions, hamming)")
    ap.add_argument("--d", type=int, default=None,
                    help="restrict d parameter (hamming)")
    ap.add_argument("--top-k", type=int, default=1,
                    help="max results to keep per N")
    ap.add_argument("--seed", type=int, default=0,
                    help="RNG seed (mattheus_verstraete only)")
    ap.add_argument("--no-save", action="store_true",
                    help="dry run — print results without writing to graph_db")
    args = ap.parse_args()

    if args.ns:
        # Caller supplied explicit Ns — combine with any explicit param overrides.
        extra = {}
        if args.q is not None:
            extra["q"] = args.q
        if args.d is not None:
            extra["d"] = args.d
        calls = [(n, dict(extra)) for n in args.ns]
    else:
        max_n = args.max_n if args.max_n is not None else _DEFAULT_MAX_N[args.construction]
        calls = _eligible_calls(args.construction, args.min_n, max_n,
                                q_filter=args.q, d_filter=args.d)

    if not calls:
        print(f"No eligible N values for {args.construction} in the requested range.")
        return 0

    rows = []
    with AggregateLogger(name=f"{args.construction}_sweep") as agg:
        for n, extra in calls:
            t0 = time.monotonic()
            search = _CLASSES[args.construction](
                n=n,
                top_k=args.top_k,
                verbosity=1,
                parent_logger=agg,
                seed=args.seed,
                **extra,
            )
            results = search.run()
            # Defensive: only save K4-free graphs. Most construction
            # classes filter at _run() time, but a stray non-K4-free graph
            # would otherwise pollute graph_db.
            kept = [r for r in results if r.is_k4_free]
            dropped = len(results) - len(kept)
            if kept and not args.no_save:
                search.save(kept)
            dt = time.monotonic() - t0

            extra_str = ""
            if extra:
                extra_str = " " + " ".join(f"{k}={v}" for k, v in sorted(extra.items()))
            if not kept:
                drop_str = f" (dropped {dropped} non-K4-free)" if dropped else ""
                print(f"[{args.construction} n={n:>5}{extra_str}] skipped{drop_str} ({dt:.2f}s)", flush=True)
                continue

            for r in kept:
                k = r.metadata.get("residue_index")
                rows.append((n, k, r.c_log, r.alpha, r.d_max, r.is_k4_free, dt))
                k_str = f" k={k}" if k is not None else ""
                print(
                    f"[{args.construction} n={n:>5}{extra_str}{k_str}]  "
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
