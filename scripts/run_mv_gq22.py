"""
Experiment: MV-pencil-bipartization of GQ(2,2) at N=15.

Goal: test whether structure-aware bipartization of the doily's 15 lines
can reach (or beat) SAT's frontier at N=15 (c_log ≈ 0.7195, α=3, d=7).

Writes:
  - log  logs/mv_bipartization/gq22_<TS>.log
  - DB   adds best-few graphs under source="mv_bipartization"
"""
from __future__ import annotations
import argparse
import datetime
import json
import os
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from search.mv_bipartization import (
    gq22_points_lines, collinearity_graph, search_partitions,
    exact_alpha_simple, _c_log,
)
from graph_db import DB


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--trials", type=int, default=20000)
    ap.add_argument("--top-k",  type=int, default=5)
    ap.add_argument("--seed",   type=int, default=0)
    ap.add_argument("--no-save", action="store_true",
                    help="don't write to graph_db")
    args = ap.parse_args()

    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    log_dir = os.path.join(REPO, "logs", "mv_bipartization")
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, f"gq22_{ts}.log")

    def log(msg: str):
        line = f"[{time.strftime('%H:%M:%S')}] {msg}"
        print(line, flush=True)
        with open(log_path, "a") as f:
            f.write(line + "\n")

    log(f"== MV bipartization of GQ(2,2) ==")
    log(f"log_path={log_path}")
    log(f"trials={args.trials} seed={args.seed} top_k={args.top_k}")

    points, lines = gq22_points_lines()
    log(f"GQ(2,2): |P|={len(points)} |L|={len(lines)}")

    # Baseline: collinearity graph (pre-bipartization)
    G_base, idx = collinearity_graph(points, lines)
    n = G_base.number_of_nodes()
    m = G_base.number_of_edges()
    d_max0 = max(dict(G_base.degree()).values())
    alpha0 = exact_alpha_simple(G_base)
    c0 = _c_log(alpha0, d_max0, n)
    log(f"baseline collinearity graph: n={n} m={m} d_max={d_max0} "
        f"α={alpha0} c_log={c0:.4f}  "
        f"(K(6,2) = Kneser / srg(15,6,1,3))")

    # Reference: SAT frontier at n=15
    log(f"SAT frontier reference at n=15: c_log=0.7195 (α=3, d=7)")
    log(f"Target: beat 0.7195 via pencil bipartization.")
    log("")

    # Search
    t0 = time.monotonic()
    results = search_partitions(points, lines,
                                n_trials=args.trials,
                                seed=args.seed,
                                top_k=args.top_k)
    elapsed = time.monotonic() - t0
    log(f"Search complete: {len(results)} distinct best graphs in {elapsed:.1f}s")
    log("")

    # Report
    log(f"{'rank':>4} {'c_log':>7} {'α':>3} {'d_min':>5} {'d_max':>5} {'m':>4} {'trial':>6}")
    log('-' * 45)
    for i, r in enumerate(results, 1):
        log(f"{i:>4} {r['c_log']:>7.4f} {r['alpha']:>3} "
            f"{r['d_min']:>5} {r['d_max']:>5} {r['m']:>4} {r['trial']:>6}")
    log("")

    best = results[0] if results else None
    if best:
        verdict = (
            "BEATS SAT frontier!" if best['c_log'] < 0.7195 - 1e-4 else
            "ties SAT frontier"    if abs(best['c_log'] - 0.7195) < 1e-4 else
            "loses to SAT frontier"
        )
        log(f"VERDICT: {verdict}  (best c_log = {best['c_log']:.4f} vs 0.7195)")
        log(f"  gap: {best['c_log'] - 0.7195:+.4f}")

    # Save to DB
    if not args.no_save and results:
        db = DB(auto_sync=False)
        saved = 0
        for r in results[:args.top_k]:
            G = r['G']
            meta = {
                "construction": "mv_bipartize_gq22",
                "base_structure": "GQ(2,2)/Cremona-Richmond",
                "n_lines": 15,
                "alpha_exact": r['alpha'],
                "d_max": r['d_max'],
                "d_min": r['d_min'],
                "c_log_computed": r['c_log'],
                "search_trial": r['trial'],
                "search_seed": args.seed,
            }
            gid, was_new = db.add(G, source="mv_bipartization",
                                  filename="mv_bipartization.json", **meta)
            tag = "ADDED" if was_new else "DUP"
            log(f"  [{tag}] id={gid[:10]} c={r['c_log']:.4f} α={r['alpha']} d={r['d_max']}")
            if was_new:
                saved += 1
        log(f"Saved {saved} new graph(s) to graph_db under source='mv_bipartization'.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
