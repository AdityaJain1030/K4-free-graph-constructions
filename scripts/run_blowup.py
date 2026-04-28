#!/usr/bin/env python3
"""
scripts/run_blowup.py
=====================
Run lex and tensor blow-ups (Probe 4) over a preset sweep of seeds.

The default sweep lex-blows up the best circulant frontier at
n ∈ {13, 17, 19, 21, 25} with k ∈ {2, 3} and also tensors the best
small circulant with the best small cayley. Intended as seeds for
downstream polish, not as finished products.

Seeds are resolved out of `graph_db` here and handed to the blow-up
classes as `nx.Graph` objects.

Run from repo root::

    micromamba run -n k4free python scripts/run_blowup.py
"""

import argparse
import os
import sys
import time

import networkx as nx

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from graph_db import DB
from search import AggregateLogger, LexBlowupSearch, TensorBlowupSearch


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


def _resolve_seed(db: DB, source: str, n: int) -> tuple[nx.Graph, dict]:
    """Frontier-min by c_log over (source, n). Returns (graph, provenance)."""
    rows = db.top("c_log", k=1, ascending=True, source=source, n=n)
    if not rows:
        raise ValueError(f"no seed matched source={source!r}, n={n!r}")
    rec = rows[0]
    G = db.nx(rec["graph_id"])
    meta = {
        "id": rec["graph_id"],
        "source": rec["source"],
        "n": rec["n"],
        "c_log": rec.get("c_log"),
    }
    return G, meta


def _run_lex(db, agg, seed_source: str, seed_n: int, k: int):
    label = f"lex {seed_source} n={seed_n} k={k}"
    t0 = time.monotonic()
    try:
        seed, seed_meta = _resolve_seed(db, seed_source, seed_n)
        search = LexBlowupSearch(top_k=1, verbosity=1, parent_logger=agg,
                                 seed=seed, k=k, seed_meta=seed_meta)
        results = search.run()
        search.save([r for r in results if r.is_k4_free])
    except Exception as exc:
        print(f"[{label}] FAILED: {exc!r}")
        return None
    dt = time.monotonic() - t0
    if not results:
        print(f"[{label}] 0 results  ({dt:.2f}s)")
        return None
    r = results[0]
    print(f"[{label}] n={r.n} α={r.alpha} d_max={r.d_max} "
          f"c_log={_fmt(r.c_log)} k4_free={r.is_k4_free} ({dt:.2f}s)")
    return r


def _run_tensor(db, agg, seed_source, seed_n, other_source, other_n):
    label = f"tensor {seed_source} n={seed_n} × {other_source} n={other_n}"
    t0 = time.monotonic()
    try:
        seed, seed_meta = _resolve_seed(db, seed_source, seed_n)
        other, other_meta = _resolve_seed(db, other_source, other_n)
        search = TensorBlowupSearch(top_k=1, verbosity=1, parent_logger=agg,
                                    seed=seed, other=other,
                                    seed_meta=seed_meta, other_meta=other_meta)
        results = search.run()
        search.save([r for r in results if r.is_k4_free])
    except Exception as exc:
        print(f"[{label}] FAILED: {exc!r}")
        return None
    dt = time.monotonic() - t0
    if not results:
        print(f"[{label}] 0 results  ({dt:.2f}s)")
        return None
    r = results[0]
    print(f"[{label}] n={r.n} α={r.alpha} d_max={r.d_max} "
          f"c_log={_fmt(r.c_log)} k4_free={r.is_k4_free} ({dt:.2f}s)")
    return r


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed-source", default="circulant",
                    help="graph_db source to pull lex seeds from")
    args = ap.parse_args()

    results = []
    with DB() as db, AggregateLogger(name="blowup_sweep") as agg:
        for n in LEX_SEEDS:
            for k in LEX_KS:
                if n * k > MAX_N:
                    print(f"[lex {args.seed_source} n={n} k={k}] skip (n*k={n*k} > {MAX_N})")
                    continue
                r = _run_lex(db, agg, args.seed_source, n, k)
                if r is not None:
                    results.append(("lex", n, k, r))
        for seed_src, seed_n, other_src, other_n in TENSOR_PAIRS:
            if seed_n * other_n > MAX_N:
                print(f"[tensor {seed_src} × {other_src} "
                      f"{seed_n}*{other_n}={seed_n*other_n}] skip (> {MAX_N})")
                continue
            r = _run_tensor(db, agg, seed_src, seed_n, other_src, other_n)
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
