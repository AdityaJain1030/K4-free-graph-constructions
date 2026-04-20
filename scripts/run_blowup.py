#!/usr/bin/env python3
"""
scripts/run_blowup.py
=====================
Run BlowupSearch (Probe 4) over a preset sweep of seeds.

The default sweep lex-blows up the best circulant frontier at
n ∈ {13, 17, 19, 21, 25} with k ∈ {2, 3} and also tensors the best
small circulant with the best small cayley. Intended as seeds for
downstream polish, not as finished products.

Run from repo root::

    micromamba run -n k4free python scripts/run_blowup.py
"""

import argparse
import os
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from search import AggregateLogger, BlowupSearch


LEX_SEEDS = [13, 17, 19, 21, 25, 29]
LEX_KS = [2, 3]
MAX_N = 100  # blow-ups aren't sparse algebraic — stay at the general cap

TENSOR_PAIRS = [
    # (seed_source, seed_n, other_source, other_n). Products' n is
    # seed_n * other_n; filter against MAX_N below.
    ("circulant", 13, "cayley", 7),   # 91
    ("circulant", 17, "cayley", 7),   # 119 — filtered
    ("circulant", 17, "circulant", 5),  # 85
    ("cayley", 11, "circulant", 5),   # 55
]


def _fmt(x):
    return "—" if x is None else f"{x:.6f}"


def _run_one(agg, mode: str, **kw):
    t0 = time.monotonic()
    try:
        search = BlowupSearch(n=0, top_k=1, verbosity=1,
                              parent_logger=agg, mode=mode, **kw)
        results = search.run()
        search.save([r for r in results if r.is_k4_free])
    except Exception as exc:
        print(f"[blowup {mode} {kw}] FAILED: {exc!r}")
        return None
    dt = time.monotonic() - t0
    if not results:
        print(f"[blowup {mode} {kw}] 0 results  ({dt:.2f}s)")
        return None
    r = results[0]
    print(f"[blowup {mode} {kw}] n={r.n} α={r.alpha} d_max={r.d_max} "
          f"c_log={_fmt(r.c_log)} k4_free={r.is_k4_free} ({dt:.2f}s)")
    return r


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed-source", default="circulant",
                    help="graph_db source to pull lex seeds from")
    args = ap.parse_args()

    results = []
    with AggregateLogger(name="blowup_sweep") as agg:
        for n in LEX_SEEDS:
            for k in LEX_KS:
                if n * k > MAX_N:
                    print(f"[blowup lex n={n} k={k}] skip (n*k={n*k} > {MAX_N})")
                    continue
                r = _run_one(agg, "lex",
                             k=k, seed_source=args.seed_source, seed_n=n)
                if r is not None:
                    results.append(("lex", n, k, r))
        for seed_src, seed_n, other_src, other_n in TENSOR_PAIRS:
            if seed_n * other_n > MAX_N:
                print(f"[blowup tensor {seed_src}×{other_src} "
                      f"{seed_n}*{other_n}={seed_n*other_n}] skip (> {MAX_N})")
                continue
            r = _run_one(agg, "tensor",
                         seed_source=seed_src, seed_n=seed_n,
                         other_source=other_src, other_n=other_n)
            if r is not None:
                results.append(("tensor", (seed_src, seed_n),
                                (other_src, other_n), r))

    print()
    print("=" * 72)
    print(f"  {len(results)} blow-up graphs produced")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    sys.exit(main())
