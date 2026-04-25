"""
Experiment runner: MV-pencil-bipartization over a chosen incidence structure.

Usage:
    python scripts/run_mv_bipartization.py --structure gq22 --trials 20000
    python scripts/run_mv_bipartization.py --structure gq33 --trials 20000

Writes a log under logs/mv_bipartization/<structure>_<TS>.log and saves
the top-k best K4-free graphs to graph_db under source="mv_bipartization".
"""
from __future__ import annotations
import argparse
import datetime
import os
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from search.mv_bipartization import (
    gq22_points_lines, gq33_points_lines,
    collinearity_graph, search_partitions, alpha_auto, _c_log,
)
from graph_db import DB


STRUCTURES = {
    "gq22": {
        "builder": gq22_points_lines,
        "label":   "GQ(2,2) / Cremona-Richmond",
        "n":       15,
        "sat_ref": 0.7195,  # SAT non-VT frontier at n=15
    },
    "gq33": {
        "builder": gq33_points_lines,
        "label":   "GQ(3,3) / W(3) symplectic",
        "n":       40,
        "sat_ref": 0.7195,  # best connected at n=40 is c_log=0.8372 from DB;
                            # quoting SAT n=15 frontier is wrong here.
                            # Will fetch live ref from DB.
    },
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--structure", choices=list(STRUCTURES), default="gq22")
    ap.add_argument("--trials", type=int, default=20000)
    ap.add_argument("--top-k",  type=int, default=8)
    ap.add_argument("--seed",   type=int, default=0)
    ap.add_argument("--no-save", action="store_true")
    args = ap.parse_args()

    spec = STRUCTURES[args.structure]

    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    log_dir = os.path.join(REPO, "logs", "mv_bipartization")
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, f"{args.structure}_{ts}.log")

    def log(msg: str):
        line = f"[{time.strftime('%H:%M:%S')}] {msg}"
        print(line, flush=True)
        with open(log_path, "a") as f:
            f.write(line + "\n")

    log(f"== MV bipartization on {spec['label']} ==")
    log(f"log_path={log_path}")
    log(f"trials={args.trials} seed={args.seed} top_k={args.top_k}")

    points, lines = spec["builder"]()
    log(f"{args.structure}: |P|={len(points)} |L|={len(lines)}  "
        f"(pts/line={len(lines[0])})")

    # Baseline collinearity graph
    G_base, idx = collinearity_graph(points, lines)
    n = G_base.number_of_nodes()
    m0 = G_base.number_of_edges()
    d_max0 = max(dict(G_base.degree()).values())
    alpha0 = alpha_auto(G_base)
    c0 = _c_log(alpha0, d_max0, n)
    log(f"baseline collinearity: n={n} m={m0} d_max={d_max0} "
        f"α={alpha0} c_log={c0:.4f}")

    # Reference: current best c_log at this n from graph_db
    try:
        import sqlite3
        db_con = sqlite3.connect(os.path.join(REPO, "cache.db"))
        cur = db_con.execute(
            "SELECT MIN(c_log) FROM cache WHERE n=? AND is_k4_free=1 AND c_log IS NOT NULL",
            (n,))
        ref = cur.fetchone()[0]
        db_con.close()
    except Exception as e:
        ref = None
        log(f"(could not read frontier ref: {e})")
    log(f"graph_db frontier at n={n}: c_log={ref}")

    t0 = time.monotonic()
    results = search_partitions(points, lines,
                                n_trials=args.trials,
                                seed=args.seed,
                                top_k=args.top_k)
    elapsed = time.monotonic() - t0
    log(f"Search complete: {len(results)} distinct graphs in {elapsed:.1f}s")
    log("")
    log(f"{'rank':>4} {'c_log':>7} {'α':>3} {'d_min':>5} {'d_max':>5} {'m':>5} {'trial':>7}")
    log('-' * 50)
    for i, r in enumerate(results, 1):
        log(f"{i:>4} {r['c_log']:>7.4f} {r['alpha']:>3} "
            f"{r['d_min']:>5} {r['d_max']:>5} {r['m']:>5} {r['trial']:>7}")
    log("")

    if results:
        best = results[0]
        if ref is not None:
            gap = best['c_log'] - ref
            verdict = ("BEATS frontier!"  if gap < -1e-4 else
                       "ties frontier"    if abs(gap) <= 1e-4 else
                       "loses to frontier")
            log(f"VERDICT: {verdict}  (best={best['c_log']:.4f} vs frontier={ref:.4f}, gap={gap:+.4f})")
        else:
            log(f"VERDICT: best={best['c_log']:.4f} (no frontier ref)")

    if not args.no_save and results:
        db = DB(auto_sync=False)
        saved = 0
        for r in results:
            G = r['G']
            meta = {
                "construction": f"mv_bipartize_{args.structure}",
                "base_structure": spec['label'],
                "n_lines": len(lines),
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
            if was_new: saved += 1
        log(f"Saved {saved} new graph(s) to graph_db.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
