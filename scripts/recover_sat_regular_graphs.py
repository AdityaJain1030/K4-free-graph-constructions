"""
scripts/recover_sat_regular_graphs.py
=====================================
Re-solve each (n, α, spread) case from the bench json files and save the
resulting graphs to `graphs/sat_regular.json`. Since we already know the
target edge count and degree window, each re-solve is a tight CP-SAT
feasibility query (seconds per case).

Usage:
    micromamba run -n k4free python scripts/recover_sat_regular_graphs.py
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from math import comb
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import networkx as nx

from search.sat_regular import SATRegular, _LAZY_THRESHOLD

BENCH_FILES = [
    ROOT / "logs" / "bench_sat_regular_10_20.json",
    ROOT / "logs" / "bench_sat_regular_20_25.json",
]
OUT_PATH = ROOT / "graphs" / "sat_regular.json"

PER_CASE_TIMEOUT = 60.0


def graph_id(G: nx.Graph) -> str:
    edges = sorted(tuple(sorted(e)) for e in G.edges())
    blob = str(edges).encode()
    return hashlib.sha1(blob).hexdigest()[:16]


def recover_one(n: int, alpha: int, D: int, spread: int, num_edges: int, workers: int):
    s = SATRegular(
        n=n, alpha=alpha,
        timeout_s=PER_CASE_TIMEOUT, workers=workers,
        degree_spread=spread, symmetry_mode="none",
        branch_on_v0=True, minimize_edges=False,
        verbosity=0,
    )
    k = alpha + 1
    direct = (k > n) or (comb(n, k) <= _LAZY_THRESHOLD)
    model, x = s._build_model(
        D=D, enumerate_alpha=direct, alpha_cuts=None,
        minimize=False, edge_ub=num_edges,
    )
    status, G = s._solve_model(
        model, x, time_limit=PER_CASE_TIMEOUT, hard_params=True
    )
    return status, G


def main() -> None:
    cpus = os.cpu_count() or 8
    cases: list[tuple] = []
    for bench_file in BENCH_FILES:
        if not bench_file.exists():
            print(f"[skip] {bench_file} not found")
            continue
        with bench_file.open() as f:
            bench = json.load(f)
        for row in bench["cases"]:
            n, a = row["n"], row["alpha"]
            for spread_key, spread in (("spread_1", 1), ("spread_3", 3)):
                s = row[spread_key]
                if s.get("status") != "FEASIBLE":
                    continue
                cases.append({
                    "n": n, "alpha": a, "spread": spread,
                    "num_edges": s["num_edges"],
                    "d_min": s["d_min"], "d_max": s["d_max"], "D": s["D"],
                    "ref_edges": row["pareto"]["ref_edges"],
                    "source_bench": bench_file.name,
                })

    print(f"[recover] {len(cases)} cases to resolve (timeout {PER_CASE_TIMEOUT}s each, workers={cpus})")
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    out_graphs: list[dict] = []
    seen_ids: set[str] = set()
    t0 = time.monotonic()
    failures: list[dict] = []

    for i, c in enumerate(cases, 1):
        t_case = time.monotonic()
        status, G = recover_one(
            c["n"], c["alpha"], c["D"], c["spread"],
            c["num_edges"], cpus,
        )
        dt = time.monotonic() - t_case
        tag = f"n={c['n']:>2} α={c['alpha']} s={c['spread']} target_e={c['num_edges']}"
        if G is None:
            print(f"[{i:>3}/{len(cases)}] {tag}  FAILED ({status})  t={dt:.1f}s")
            failures.append({**c, "recover_status": status})
            continue
        e_got = G.number_of_edges()
        gid = graph_id(G)
        note = "" if e_got == c["num_edges"] else f" (got {e_got} vs target {c['num_edges']})"
        dedup = " [dup]" if gid in seen_ids else ""
        print(f"[{i:>3}/{len(cases)}] {tag}  OK e={e_got}{note}  t={dt:.1f}s  id={gid}{dedup}")

        if gid in seen_ids:
            continue
        seen_ids.add(gid)

        degs = sorted(dict(G.degree()).values())
        out_graphs.append({
            "id": gid,
            "sparse6": nx.to_sparse6_bytes(G, header=False).decode().strip(),
            "source": "sat_regular",
            "metadata": {
                "n": c["n"],
                "alpha_target": c["alpha"],
                "num_edges": e_got,
                "D": c["D"],
                "d_min": degs[0],
                "d_max": degs[-1],
                "degree_spread": c["spread"],
                "ref_edges": c["ref_edges"],
                "source_bench": c["source_bench"],
            },
        })

        if i % 5 == 0 or i == len(cases):
            with OUT_PATH.open("w") as f:
                json.dump(out_graphs, f, indent=2)

    with OUT_PATH.open("w") as f:
        json.dump(out_graphs, f, indent=2)

    wall = time.monotonic() - t0
    print()
    print(f"[recover] wrote {len(out_graphs)} graphs ({len(cases)-len(out_graphs)-len(failures)} dedup) to {OUT_PATH}")
    print(f"[recover] failures: {len(failures)}")
    print(f"[recover] wall: {wall:.1f}s")
    if failures:
        for f_ in failures:
            print(f"  FAIL n={f_['n']} α={f_['alpha']} s={f_['spread']} e={f_['num_edges']} status={f_['recover_status']}")


if __name__ == "__main__":
    main()
