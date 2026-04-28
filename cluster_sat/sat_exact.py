#!/usr/bin/env python3
"""
cluster_sat/sat_exact.py
========================
Box-scan driver over the naive K4-free decider in `search/SAT/sat.py`,
tuned for 16-CPU / 200-GB cluster runs in *find-good-graphs* mode (we
prefer fast feasibility witnesses over UNSAT certification).

Per-N strategy
--------------
1. Enumerate (alpha, d_max) cells under Caro-Wei lower, Ramsey upper,
   and (optionally) Hajnal upper caps.
2. Group cells into rows keyed by alpha (each row sweeps d ascending,
   breaks at first SAT — smallest d minimises c_log on the row).
3. Sort rows by their c_log floor `alpha * d_lo / (N * ln d_lo)` so the
   most promising row runs first; the witness it yields tightens the
   shared c_star and prunes dominated rows before they spawn a SAT
   call.
4. Dispatch rows to a ProcessPoolExecutor (one row per task). Each
   worker reads/updates a multiprocessing.Value c_star.
5. Per-cell SAT calls run with `num_search_workers=1` (we parallelize
   externally; CP-SAT scales poorly on small models past ~4 internal
   threads). On TIMED_OUT we bump d and continue — never burn budget
   trying to certify UNSAT.

Cluster invocation
------------------
    python -m cluster_sat.sat_exact \\
        --n-min 22 --n-max 30 \\
        --workers 16 --hajnal --c-seed-from-db --skip-on-timeout \\
        --time-limit 600 --save \\
        --out-json logs/sat_box/run.json
"""

from __future__ import annotations

import argparse
import json
import math
import multiprocessing as mp
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from math import comb

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

import networkx as nx

from search.SAT.sat import SAT
from utils.graph_props import c_log_value
from utils.ramsey import KNOWN_RAMSEY


# ── geometry helpers ─────────────────────────────────────────────────────────

def _caro_wei_d_lo(n: int, alpha: int) -> int:
    if alpha <= 0:
        return 1
    return max(1, math.ceil(n / alpha) - 1)


def _ramsey_d_hi(alpha: int, n: int) -> int:
    r = KNOWN_RAMSEY.get((3, alpha + 1))
    return min(n - 1, r - 1) if r is not None else n - 1


def _hajnal_d_hi(n: int, alpha: int) -> int:
    return max(0, n - 2 * alpha + 1)


def _row_floor(n: int, alpha: int, d_lo: int) -> float:
    """Tightest c_log achievable on this row (using d_lo). +inf if d_lo <= 1
    (the c_log formula is undefined there — those rows can't beat any
    real witness, so push them to the back)."""
    c = c_log_value(alpha, n, d_lo)
    return float("inf") if c is None else c


def _row_clause_count(n: int, alpha: int) -> int:
    """Approx CP-SAT clause count for one cell on this row:
    C(n,4) K4-clauses + C(n, alpha+1) alpha-clauses + n degree caps.
    The alpha term dominates and drives memory."""
    if alpha + 1 > n:
        return comb(n, 4) + n
    return comb(n, 4) + comb(n, alpha + 1) + n


def _row_memory_gb(n: int, alpha: int, bytes_per_clause: int = 120) -> float:
    """Rough peak RSS estimate for one cell, in GiB. CP-SAT typically
    pushes 4-6x of the raw clause count during presolve, so we apply a
    fudge factor."""
    raw = _row_clause_count(n, alpha) * bytes_per_clause
    return raw * 5.0 / (1024 ** 3)


def _build_rows(
    n: int,
    *,
    alpha: int | None,
    use_hajnal: bool,
    alpha_max: int | None,
) -> list[dict]:
    if alpha is not None:
        alpha_range = [alpha]
    else:
        hi = n - 1 if alpha_max is None else min(n - 1, alpha_max)
        alpha_range = list(range(1, hi + 1))
    rows: list[dict] = []
    for a in alpha_range:
        d_lo = _caro_wei_d_lo(n, a)
        d_hi_ramsey = _ramsey_d_hi(a, n)
        d_hi_hajnal = _hajnal_d_hi(n, a) if use_hajnal else None
        d_hi = d_hi_ramsey if not use_hajnal else min(d_hi_ramsey, d_hi_hajnal)
        rows.append({
            "n":           n,
            "alpha":       a,
            "d_lo":        d_lo,
            "d_hi":        d_hi,
            "d_hi_ramsey": d_hi_ramsey,
            "d_hi_hajnal": d_hi_hajnal,
            "floor":       _row_floor(n, a, d_lo),
            "mem_gb_est":  round(_row_memory_gb(n, a), 2),
        })
    rows.sort(key=lambda r: r["floor"])
    return rows


# ── shared c_star state for workers ──────────────────────────────────────────

_C_STAR: mp.Value | None = None  # set in worker init


def _worker_init(c_star_value):
    global _C_STAR
    _C_STAR = c_star_value


def _read_c_star() -> float:
    if _C_STAR is None:
        return float("inf")
    with _C_STAR.get_lock():
        return _C_STAR.value


def _try_update_c_star(new: float) -> bool:
    if _C_STAR is None:
        return False
    with _C_STAR.get_lock():
        if new < _C_STAR.value:
            _C_STAR.value = new
            return True
        return False


# ── per-row scan (worker entrypoint) ─────────────────────────────────────────

def _vlog(verbosity: int, level: int, msg: str) -> None:
    """Worker-side progress print. flush=True so output appears live."""
    if verbosity >= level:
        print(msg, flush=True)


def _scan_row_worker(row: dict, time_limit_s: float, skip_on_timeout: bool,
                     cp_workers: int = 1, verbosity: int = 1,
                     seed_graph: "nx.Graph | None" = None) -> dict:
    """Walk d ascending in [d_lo, d_hi]. First SAT wins.
    Honours c_star (skip dominated rows / rows whose smallest possible
    c_log already loses).

    Verbosity (worker-local stdout, flushed):
      0 = silent
      1 = row start + row end + c* updates (default)
      2 = + per-cell start
      3 = + per-cell end with wall time
    """
    n     = row["n"]
    alpha = row["alpha"]
    d_lo  = row["d_lo"]
    d_hi  = row["d_hi"]
    pid   = os.getpid()
    cells: list[dict] = []

    tag = f"[w{pid} N={n} α={alpha:>2}]"

    if d_lo > d_hi:
        _vlog(verbosity, 1, f"{tag} EMPTY_ROW (d_lo={d_lo} > d_hi={d_hi})")
        return {**row, "status": "EMPTY_ROW", "best_d": None,
                "c_log": None, "sparse6": None, "cells": cells,
                "wall_s": 0.0}

    _vlog(verbosity, 1,
          f"{tag} START   d∈[{d_lo},{d_hi}]  mem~{row.get('mem_gb_est', 0):.2f}G  "
          f"floor={row.get('floor', float('inf')):.4f}  c*={_read_c_star():.4f}")

    t0 = time.monotonic()

    for d in range(d_lo, d_hi + 1):
        # Even the cheapest row floor may have been beaten by another worker.
        c_floor_here = c_log_value(alpha, n, d)
        c_star = _read_c_star()
        if c_floor_here is not None and c_floor_here >= c_star - 1e-12:
            cells.append({"alpha": alpha, "d_max": d, "status": "DOMINATED",
                          "wall_s": 0.0, "c_floor": c_floor_here,
                          "c_star": c_star})
            _vlog(verbosity, 2,
                  f"{tag} d={d:>2}  DOMINATED  floor={c_floor_here:.4f} ≥ c*={c_star:.4f}")
            continue

        _vlog(verbosity, 2, f"{tag} d={d:>2}  ── solving (limit={time_limit_s}s) ...")
        cell_t0 = time.monotonic()
        search = SAT(
            n=n,
            alpha=alpha,
            d_max=d,
            time_limit_s=time_limit_s,
            cp_workers=cp_workers,
            seed_graph=seed_graph,
            verbosity=0,
        )
        results = search.run()
        cell_wall = time.monotonic() - cell_t0
        r = results[0]
        status = r.metadata.get("status", "UNKNOWN")
        cells.append({
            "alpha":  alpha,
            "d_max":  d,
            "status": status,
            "wall_s": r.metadata.get("wall_time_s", 0.0),
            "pruned": r.metadata.get("pruned_by"),
        })
        _vlog(verbosity, 2 if status == "UNSAT" else 1,
              f"{tag} d={d:>2}  {status:>9}  wall={cell_wall:>6.1f}s")

        if status == "SAT" and r.G.number_of_edges() > 0:
            c = c_log_value(alpha, n, d)
            if c is not None and _try_update_c_star(c):
                _vlog(verbosity, 1,
                      f"{tag} *** c* tightened to {c:.6f} (α={alpha} d={d}) ***")
            return {
                **row,
                "status":  "ROW_SAT",
                "best_d":  d,
                "c_log":   c,
                "sparse6": nx.to_sparse6_bytes(r.G, header=False).decode().strip(),
                "cells":   cells,
                "wall_s":  round(time.monotonic() - t0, 3),
            }

        if status == "TIMED_OUT" and not skip_on_timeout:
            _vlog(verbosity, 1,
                  f"{tag} ROW_TIMEOUT at d={d}  (skip_on_timeout=False)")
            return {**row, "status": "ROW_TIMEOUT", "best_d": None,
                    "c_log": None, "sparse6": None, "cells": cells,
                    "wall_s": round(time.monotonic() - t0, 3)}

        # UNSAT or (TIMED_OUT with skip_on_timeout) → next d.

    _vlog(verbosity, 1,
          f"{tag} ROW_UNSAT  total_wall={time.monotonic()-t0:.1f}s")
    return {**row, "status": "ROW_UNSAT", "best_d": None,
            "c_log": None, "sparse6": None, "cells": cells,
            "wall_s": round(time.monotonic() - t0, 3)}


# ── parent-side orchestration ────────────────────────────────────────────────

def _seed_c_star_from_db(n: int) -> tuple[float, str | None]:
    """Best known K4-free graph at this N; returns (c_log, source) or
    (+inf, None) if the cache is empty."""
    try:
        from graph_db import open_db
    except Exception:
        return float("inf"), None
    try:
        with open_db() as db:
            rows = db.top("c_log", k=1, ascending=True, n=n)
    except Exception:
        return float("inf"), None
    if not rows:
        return float("inf"), None
    r = rows[0]
    c = r.get("c_log")
    return (c, r.get("source")) if c is not None else (float("inf"), None)


# SAT-derived sources are excluded from hint lookups: hinting CP-SAT
# with a graph the SAT pipeline itself just produced is circular —
# the hint smuggles in the answer at the same (N, α, d) cell. The c*
# seed (a scalar) can still come from SAT-derived rows; only the
# *graph* hint is filtered.
_HINT_EXCLUDE_SOURCES = ("sat_exact", "sat_box", "server_sat_exact",
                         "sat_circulant", "sat_circulant_optimal",
                         "sat_regular", "sat_near_regular_nonreg")


def _seed_hint_graph(n: int) -> tuple["nx.Graph | None", str | None, dict]:
    """Best known *non-SAT-derived* K4-free nx.Graph at N for CP-SAT
    solution-hint seeding. Returns (G, source, info) or (None, None, {})
    if no eligible graph exists in the cache."""
    try:
        from graph_db import open_db, GraphStore, DEFAULT_GRAPHS
    except Exception:
        return None, None, {}
    try:
        with open_db() as db:
            # Pull more than 1; first eligible (non-SAT) row wins.
            rows = db.top("c_log", k=20, ascending=True, n=n)
            if not rows:
                return None, None, {}
            r = next(
                (row for row in rows
                 if row.get("source") not in _HINT_EXCLUDE_SOURCES),
                None,
            )
            if r is None:
                return None, None, {}
            store = GraphStore(DEFAULT_GRAPHS)
            for rec in store.all_records():
                if rec.get("id") == r["graph_id"]:
                    G = nx.from_sparse6_bytes(rec["sparse6"].encode())
                    return G, r["source"], {
                        "alpha":  r.get("alpha"),
                        "d_max":  r.get("d_max"),
                        "c_log":  r.get("c_log"),
                    }
    except Exception:
        return None, None, {}
    return None, None, {}


def _run_one_n(
    n: int,
    *,
    alpha: int | None,
    alpha_max: int | None,
    time_limit_s: float,
    use_hajnal: bool,
    skip_on_timeout: bool,
    workers: int,
    cp_workers: int,
    seed_c_star: float,
    seed_source: str | None,
    seed_graph: "nx.Graph | None" = None,
    verbosity: int = 1,
    save: bool = False,
    progress_jsonl: str | None = None,
) -> dict:
    rows = _build_rows(n, alpha=alpha, use_hajnal=use_hajnal, alpha_max=alpha_max)
    skipped_oom: list[dict] = []  # retained for output schema; never populated.

    c_star_shared = mp.Value("d", float(seed_c_star))

    # Open lazily — only need GraphStore when there's something to save.
    incremental_store = None
    if save:
        try:
            from graph_db import GraphStore, DEFAULT_GRAPHS
            incremental_store = GraphStore(DEFAULT_GRAPHS)
        except Exception as exc:
            print(f"[parent] WARN: GraphStore unavailable, --save disabled: {exc}",
                  flush=True)

    def _commit_row(res_row: dict) -> None:
        """Per-row incremental persistence. Called from the parent as
        each row finishes. Two layers:
          (a) graph_db: if the row found a SAT witness, store it now.
          (b) progress_jsonl: append one line per completed row.
        Both layers fsync-ish (flush + close on JSONL append) so a
        SIGKILL between rows loses at most the in-flight rows, not
        already-completed ones."""
        if incremental_store is not None and res_row.get("sparse6"):
            # Skip witnesses with undefined c_log (d_max ≤ 1 — formula
            # divides by ln d). They aren't c_log-frontier candidates
            # and clutter the cache.
            if res_row.get("c_log") is None:
                if verbosity >= 1:
                    print(f"[parent] skip-save (c_log undefined) "
                          f"N={res_row['n']} α={res_row['alpha']} "
                          f"d={res_row['best_d']}", flush=True)
            else:
                try:
                    G = nx.from_sparse6_bytes(res_row["sparse6"].encode())
                    gid, was_new = incremental_store.add_graph(
                        G,
                        source="sat_exact",
                        filename="sat_exact.json",
                        n=res_row["n"],
                        alpha_target=res_row["alpha"],
                        d_max_target=res_row["best_d"],
                        status="FEASIBLE",
                    )
                    if verbosity >= 1:
                        tag = "NEW" if was_new else "DUP"
                        c_str = f"c={res_row['c_log']:.4f}"
                        print(f"[parent] saved {tag} graph_id={gid} "
                              f"(N={res_row['n']} α={res_row['alpha']} "
                              f"d={res_row['best_d']} {c_str})",
                              flush=True)
                except Exception as exc:
                    print(f"[parent] WARN: graph_db save failed: {exc}",
                          flush=True)

        if progress_jsonl is not None:
            payload = {
                "ts":      time.time(),
                "n":       res_row["n"],
                "alpha":   res_row["alpha"],
                "d_lo":    res_row.get("d_lo"),
                "d_hi":    res_row.get("d_hi"),
                "status":  res_row.get("status"),
                "best_d":  res_row.get("best_d"),
                "c_log":   res_row.get("c_log"),
                "sparse6": res_row.get("sparse6"),
                "wall_s":  res_row.get("wall_s"),
                "cells":   res_row.get("cells", []),
            }
            try:
                with open(progress_jsonl, "a") as f:
                    f.write(json.dumps(payload) + "\n")
                    f.flush()
                    os.fsync(f.fileno())
            except Exception as exc:
                print(f"[parent] WARN: jsonl append failed: {exc}", flush=True)

    t0 = time.monotonic()
    out_rows: list[dict] = []
    if workers <= 1:
        # Single-process path (also useful for laptop debug).
        global _C_STAR
        _C_STAR = c_star_shared
        for row in rows:
            res_row = _scan_row_worker(row, time_limit_s, skip_on_timeout,
                                       cp_workers, verbosity, seed_graph)
            out_rows.append(res_row)
            _commit_row(res_row)
        _C_STAR = None
    else:
        with ProcessPoolExecutor(
            max_workers=workers,
            initializer=_worker_init,
            initargs=(c_star_shared,),
        ) as pool:
            futures = {
                pool.submit(_scan_row_worker, row, time_limit_s,
                            skip_on_timeout, cp_workers, verbosity,
                            seed_graph): row
                for row in rows
            }
            done = 0
            for fut in as_completed(futures):
                done += 1
                try:
                    res_row = fut.result()
                    out_rows.append(res_row)
                    if verbosity >= 1:
                        bl = res_row.get("c_log")
                        bl_s = "—" if bl is None else f"{bl:.6f}"
                        print(f"[parent] row {done}/{len(rows)} done  "
                              f"α={res_row['alpha']:>2}  {res_row['status']:>13}  "
                              f"c_log={bl_s}  c*={c_star_shared.value:.4f}",
                              flush=True)
                    # Commit immediately — survives SIGKILL.
                    _commit_row(res_row)
                except Exception as exc:  # noqa: BLE001
                    row = futures[fut]
                    res_row = {**row, "status": f"WORKER_ERROR: {exc}",
                               "best_d": None, "c_log": None,
                               "sparse6": None, "cells": [], "wall_s": 0.0}
                    out_rows.append(res_row)
                    print(f"[parent] WORKER_ERROR α={row['alpha']}: {exc}",
                          flush=True)
                    _commit_row(res_row)

    out_rows.sort(key=lambda r: (r["alpha"]))

    best = None
    for r in out_rows:
        if r.get("c_log") is None:
            continue
        if best is None or r["c_log"] < best["c_log"]:
            best = {"alpha": r["alpha"], "d_max": r["best_d"],
                    "c_log": r["c_log"], "sparse6": r["sparse6"]}

    return {
        "n":           n,
        "rows":        out_rows,
        "skipped_oom": skipped_oom,
        "best":        best,
        "c_star_seed": (seed_c_star if seed_c_star != float("inf") else None),
        "c_star_seed_source": seed_source,
        "elapsed_s":   round(time.monotonic() - t0, 3),
    }


# ── persistence ──────────────────────────────────────────────────────────────

def _save_witnesses(results: list[dict], filename: str = "sat_box.json") -> int:
    """Persist row witnesses into graph_db under source='sat_box'."""
    try:
        from graph_db import GraphStore, DEFAULT_GRAPHS
    except Exception:
        return 0
    store = GraphStore(DEFAULT_GRAPHS)
    saved = 0
    for res in results:
        for row in res["rows"]:
            if row.get("sparse6") is None:
                continue
            G = nx.from_sparse6_bytes(row["sparse6"].encode())
            G.graph["metadata"] = {
                "alpha_target": row["alpha"],
                "d_max_target": row["best_d"],
                "status":       "FEASIBLE",
                "n":            res["n"],
            }
            try:
                store.add_graph(G, source="sat_box", filename=filename,
                                **G.graph["metadata"])
                saved += 1
            except Exception:
                pass
    return saved


# ── CLI ──────────────────────────────────────────────────────────────────────

def _fmt(x):
    if x is None:
        return "—"
    if isinstance(x, float):
        return f"{x:.6f}"
    return str(x)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n",     type=int, default=None)
    ap.add_argument("--n-min", type=int, default=None)
    ap.add_argument("--n-max", type=int, default=None)
    ap.add_argument("--alpha", type=int, default=None,
                    help="Pin one row; otherwise sweep alpha=1..n-1.")
    ap.add_argument("--time-limit", type=float, default=300.0,
                    help="Per-cell SAT wall-clock budget (seconds). "
                         "Default 300s — tune for cluster.")
    ap.add_argument("--workers", type=int, default=16,
                    help="Parallel rows. Set to 1 for single-process debug.")
    ap.add_argument("--hajnal", action="store_true", default=True,
                    help="Cap d_max <= N-2*alpha+1 (default ON; pass "
                         "--no-hajnal to disable).")
    ap.add_argument("--no-hajnal", dest="hajnal", action="store_false")
    ap.add_argument("--skip-on-timeout", action="store_true", default=True,
                    help="Treat TIMED_OUT cells as 'try larger d', not row-fatal.")
    ap.add_argument("--no-skip-on-timeout", dest="skip_on_timeout", action="store_false")
    ap.add_argument("--c-seed-from-db", action="store_true",
                    help="Seed c_star from the best K4-free graph at this N "
                         "in graph_db (so dominated rows are skipped).")
    ap.add_argument("--seed-hint", action="store_true",
                    help="Pass best non-SAT-derived graph at N to CP-SAT "
                         "as a solution hint (model.AddHint per edge). "
                         "Excludes sat_exact / sat_box / sat_circulant / "
                         "sat_regular sources so we don't hint with a "
                         "graph the SAT pipeline produced. Pure search "
                         "bias — no soundness impact.")
    ap.add_argument("--alpha-max", type=int, default=None,
                    help="Cap alpha sweep at this value. Default None "
                         "= full sweep (alpha=1..n-1). Set if you know "
                         "the c_log frontier lies below alpha=K.")
    ap.add_argument("--cp-workers", type=int, default=1,
                    help="Per-cell CP-SAT internal worker count "
                         "(num_search_workers). 1 by default since outer "
                         "process parallelism dominates; set >1 for hard "
                         "cells at large N. Total cores ≈ workers × cp-workers.")
    ap.add_argument("-v", "--verbosity", type=int, default=2,
                    help="0 silent, 1 row+c* events, 2 (default) +per-cell "
                         "start/end, 3 +UNSAT cell timings.")
    ap.add_argument("--save", action="store_true",
                    help="Persist witnesses into graph_db (source=sat_box).")
    ap.add_argument("--out-json", type=str, default=None,
                    help="Dump full sweep summary JSON.")
    ap.add_argument("--progress-jsonl", type=str, default=None,
                    help="Append one JSON line per completed row to this file. "
                         "fsync after each line, so a SIGKILL between rows "
                         "loses no completed-row records. Recommended for "
                         "long cluster runs.")
    args = ap.parse_args()

    if args.n is None and args.n_min is None:
        ap.error("Provide --n or --n-min/--n-max.")
    ns = (
        [args.n] if args.n is not None
        else list(range(args.n_min, (args.n_max or args.n_min) + 1))
    )

    summary: list[dict] = []
    for n in ns:
        seed_c, seed_src = (
            _seed_c_star_from_db(n) if args.c_seed_from_db else (float("inf"), None)
        )
        if seed_c != float("inf"):
            print(f"[N={n}] c_star seed = {seed_c:.6f}  (from {seed_src})")
        else:
            print(f"[N={n}] c_star seed = +inf")

        seed_graph = None
        if args.seed_hint:
            seed_graph, hint_src, hint_info = _seed_hint_graph(n)
            if seed_graph is not None:
                print(f"[N={n}] hint graph = {hint_src}  "
                      f"α={hint_info.get('alpha')} d_max={hint_info.get('d_max')} "
                      f"c_log={hint_info.get('c_log')}")
            else:
                print(f"[N={n}] hint graph = (none — no eligible cached graph)")

        alpha_max = args.alpha_max  # None = full sweep

        res = _run_one_n(
            n=n,
            alpha=args.alpha,
            alpha_max=alpha_max,
            time_limit_s=args.time_limit,
            use_hajnal=args.hajnal,
            skip_on_timeout=args.skip_on_timeout,
            workers=args.workers,
            cp_workers=args.cp_workers,
            seed_c_star=seed_c,
            seed_source=seed_src,
            seed_graph=seed_graph,
            verbosity=args.verbosity,
            save=args.save,
            progress_jsonl=args.progress_jsonl,
        )
        summary.append(res)

        print(f"\n=== N={n}  workers={args.workers}  cp_workers={args.cp_workers}  "
              f"hajnal={args.hajnal}  alpha_max={alpha_max}  "
              f"({res['elapsed_s']:.1f}s) ===")
        print(f"{'α':>3} {'d_lo':>5} {'d_hi':>5} "
              f"{'(Ram, Haj)':>14} {'mem~':>6} {'best_d':>7} {'c_log':>10} "
              f"{'wall_s':>8} {'status':>14}")
        for row in res["rows"]:
            ram = row["d_hi_ramsey"]
            haj = row["d_hi_hajnal"]
            tup = f"({ram}, {haj if haj is not None else '-'})"
            print(
                f"{row['alpha']:>3} {row['d_lo']:>5} {row['d_hi']:>5} "
                f"{tup:>14} "
                f"{row['mem_gb_est']:>5.2f}G "
                f"{(row['best_d'] if row['best_d'] is not None else '-'):>7} "
                f"{_fmt(row['c_log']):>10} "
                f"{row.get('wall_s', 0.0):>8.2f} "
                f"{row['status']:>14}"
            )
        if res["best"]:
            b = res["best"]
            print(f"  → best  α={b['alpha']}  d_max={b['d_max']}  "
                  f"c_log={b['c_log']:.6f}")
        else:
            print("  → no SAT witnesses in scanned region")

    # Witnesses already saved per-row inside _run_one_n; no end-of-run save.
    if args.save:
        total = sum(1 for s in summary for row in s["rows"]
                    if row.get("sparse6") is not None)
        print(f"\nWitnesses persisted incrementally: {total} (saved as found).")

    if args.out_json:
        os.makedirs(os.path.dirname(os.path.abspath(args.out_json)) or ".", exist_ok=True)
        with open(args.out_json, "w") as f:
            json.dump(summary, f, indent=2)
        print(f"Wrote summary → {args.out_json}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
