#!/usr/bin/env python3
"""
scripts/run_cayley_tabu_gap_parallel.py
========================================
ProcessPoolExecutor-parallel driver for the GAP-backed Cayley tabu.

Unit of work is one `(N, group_name)` pair, not one `N`. This keeps
all 32 workers busy even when one N has many more SmallGroups than
another (N=32 has 51, N=24 has 15, N=29 has 1). Workers run tabu for
their single assigned group and return scored results; the main
process serialises all graph_db writes so the JSON batch file sees
only one writer.

Intended to be the single cluster entrypoint (one HTCondor job, 32
CPUs, 200 GB, 3-day walltime). Also works locally — scale with
`--workers`, which defaults to cpu_count() - 2.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from graph_db import GraphStore, DEFAULT_GRAPHS, open_db
from graph_db.encoding import graph_to_sparse6, sparse6_to_nx
from search import CayleyTabuGapSearch
from search.groups_gap import families_of_order_gap


SOURCE = "cayley_tabu_gap"


# ── worker ─────────────────────────────────────────────────────────────────


def _worker(task: dict) -> dict:
    """
    Run tabu on one (N, group_name) pair in an isolated process. Keep
    the return payload small and picklable: sparse6 for the graph,
    flat scoring fields, and metadata.

    Per-search file logging is suppressed (two workers on the same N
    would otherwise race the timestamped log path). The main process
    prints a structured summary line per task.
    """
    n = task["n"]
    group_name = task["group_name"]
    opts = task["opts"]

    # Deterministic per-pair seed so reruns are reproducible without
    # coupling across groups.
    seed = opts["random_seed"] ^ (n * 1000003) ^ (hash(group_name) & 0xFFFFFFFF)

    s = CayleyTabuGapSearch(
        n=n,
        groups=[group_name],
        top_k=1,
        verbosity=0,
        n_iters=opts["n_iters"],
        n_restarts=opts["n_restarts"],
        lb_restarts=opts["lb_restarts"],
        tabu_len=opts["tabu_len"],
        time_limit_s=opts["time_limit_s"],
        random_seed=seed,
    )

    # Disable the per-search log file — workers on the same N would
    # otherwise collide on the timestamped filename. Aggregate summary
    # goes back to the main process as print lines.
    s._logger.write = lambda *a, **kw: None  # type: ignore[method-assign]
    s._logger.close = lambda: None  # type: ignore[method-assign]

    t0 = time.monotonic()
    try:
        results = s.run()
    except Exception as exc:
        return {
            "n": n,
            "group_name": group_name,
            "ok": False,
            "error": repr(exc),
            "elapsed_s": time.monotonic() - t0,
            "results": [],
        }
    elapsed = time.monotonic() - t0

    payload: list[dict] = []
    for r in results:
        payload.append(
            {
                "sparse6": graph_to_sparse6(r.G),
                "n": r.n,
                "alpha": r.alpha,
                "d_max": r.d_max,
                "c_log": r.c_log,
                "is_k4_free": r.is_k4_free,
                "time_to_find": r.time_to_find,
                "metadata": dict(r.metadata),
            }
        )
    return {
        "n": n,
        "group_name": group_name,
        "ok": True,
        "elapsed_s": elapsed,
        "results": payload,
    }


# ── main-process helpers ───────────────────────────────────────────────────


def _best_c_per_n_from_db() -> dict[int, float]:
    """
    Best c_log per N for our source, read from cache.db via the DB class.
    Raw JSON records don't carry `c_log` / `n` at the metadata level — those
    live in the property cache — so `GraphStore.all_records()` is not usable
    for this lookup.
    """
    best: dict[int, float] = {}
    db = open_db()
    for r in db.query(source=SOURCE):
        c = r.get("c_log")
        n = r.get("n")
        if c is None or n is None:
            continue
        if n not in best or c < best[n]:
            best[n] = float(c)
    return best


def _enumerate_tasks(n_values: list[int]) -> list[tuple[int, str]]:
    """Return a list of (n, group_name) pairs from GAP's SmallGroups."""
    pairs: list[tuple[int, str]] = []
    for n in n_values:
        for fam in families_of_order_gap(n):
            pairs.append((n, fam.name))
    return pairs


def _persist(store: GraphStore, result_payload: dict, filename: str) -> tuple[str, bool] | None:
    """Reconstruct nx.Graph from sparse6 and add one record to the store."""
    if not result_payload:
        return None
    G = sparse6_to_nx(result_payload["sparse6"])
    md = dict(result_payload["metadata"])
    return store.add_graph(G, source=SOURCE, filename=filename, **md)


# ── CLI ────────────────────────────────────────────────────────────────────


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-lo", type=int, default=10)
    ap.add_argument("--n-hi", type=int, default=40)
    ap.add_argument("--n-list", type=int, nargs="*", default=None)
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 2),
                    help="ProcessPoolExecutor max_workers.")
    ap.add_argument("--n-iters", type=int, default=600)
    ap.add_argument("--n-restarts", type=int, default=8)
    ap.add_argument("--lb-restarts", type=int, default=24)
    ap.add_argument("--tabu-len", type=int, default=None)
    ap.add_argument("--time-limit", type=float, default=300.0,
                    help="Per-group wall-clock cap (seconds).")
    ap.add_argument("--random-seed", type=int, default=20260422)
    ap.add_argument("--better-only", action="store_true",
                    help="Skip persisting records that don't improve the db's "
                         f"existing best c_log per N for source='{SOURCE}'.")
    ap.add_argument("--no-save-db", action="store_true",
                    help="Don't persist to graph_db. Default is to save.")
    args = ap.parse_args()

    if args.n_list:
        n_values = sorted(set(args.n_list))
    else:
        n_values = list(range(args.n_lo, args.n_hi + 1))

    save_db = not args.no_save_db
    store = GraphStore(DEFAULT_GRAPHS) if save_db else None
    existing_best: dict[int, float] = (
        _best_c_per_n_from_db() if args.better_only else {}
    )

    tasks = _enumerate_tasks(n_values)
    print(
        f"Planning {len(tasks)} tasks over {len(n_values)} N values "
        f"on {args.workers} workers, "
        f"time_limit={args.time_limit:.0f}s per group.",
        flush=True,
    )

    opts = {
        "n_iters": args.n_iters,
        "n_restarts": args.n_restarts,
        "lb_restarts": args.lb_restarts,
        "tabu_len": args.tabu_len,
        "time_limit_s": args.time_limit,
        "random_seed": args.random_seed,
    }
    dispatched = [
        {"n": n, "group_name": g, "opts": opts} for (n, g) in tasks
    ]

    filename = f"{SOURCE}.json"

    # Track best-per-N this run so we can print improvements in order.
    best_this_run: dict[int, tuple[float, str]] = {}
    done = 0
    fails = 0
    t_sweep = time.monotonic()

    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(_worker, t) for t in dispatched]
        for fut in as_completed(futures):
            res = fut.result()
            done += 1
            n = res["n"]; g = res["group_name"]
            if not res["ok"]:
                fails += 1
                print(
                    f"[{done:>4}/{len(futures)}] N={n:>3} {g:<32}  "
                    f"FAIL: {res['error']}  ({res['elapsed_s']:.1f}s)",
                    flush=True,
                )
                continue

            # Worker returns top_k=1 so at most one payload.
            payloads = res["results"]
            if not payloads:
                print(
                    f"[{done:>4}/{len(futures)}] N={n:>3} {g:<32}  "
                    f"no feasible graph  ({res['elapsed_s']:.1f}s)",
                    flush=True,
                )
                continue

            pl = payloads[0]
            c = pl.get("c_log")
            mark = ""
            if c is not None:
                cur = best_this_run.get(n)
                if cur is None or c < cur[0]:
                    best_this_run[n] = (c, g)
                prev = existing_best.get(n)
                keep_prev = (
                    args.better_only
                    and prev is not None
                    and (c is None or c >= prev - 1e-9)
                )
                if save_db and not keep_prev:
                    assert store is not None
                    _persist(store, pl, filename)
                    if prev is not None and c < prev - 1e-9:
                        mark = "  (improved)"
                    elif prev is None:
                        mark = "  (new)"
                elif keep_prev:
                    mark = "  (kept prev)"

            print(
                f"[{done:>4}/{len(futures)}] N={n:>3} {g:<32}  "
                f"c_log={c if c is None else f'{c:.6f}'}  "
                f"α={pl.get('alpha')}  d={pl.get('d_max')}  "
                f"({res['elapsed_s']:.1f}s){mark}",
                flush=True,
            )

    dt = time.monotonic() - t_sweep
    print()
    print(f"Sweep done in {dt/60:.1f} min.  failures={fails}/{len(futures)}")
    if best_this_run:
        print("Best per N (this run):")
        for n in sorted(best_this_run):
            c, g = best_this_run[n]
            print(f"  N={n:>3}  c_log={c:.6f}  group={g}")
    if save_db:
        print(f"Persisted to graph_db under source='{SOURCE}'.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
