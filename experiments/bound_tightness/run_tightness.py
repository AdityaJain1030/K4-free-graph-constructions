"""
experiments/bound_tightness/run_tightness.py
==================================================
Score every α bound in `utils/alpha_bounds` against true α on the
lowest-c_log K4-free graphs in the DB, and write a CSV.

Usage:
  micromamba run -n k4free python experiments/bound_tightness/run_tightness.py
  micromamba run -n k4free python experiments/bound_tightness/run_tightness.py --c-max 0.74 --n-max 25
"""
from __future__ import annotations

import argparse
import csv
import os
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)

from graph_db import DB  # noqa: E402
from utils.alpha_bounds import (  # noqa: E402
    hoffman_bound,
    lovasz_theta,
    schrijver_theta,
    fractional_chromatic_complement,
    greedy_clique_cover,
    hardcore_alpha,
)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--c-max", type=float, default=0.74,
                    help="Only graphs with c_log <= c-max")
    ap.add_argument("--n-max", type=int, default=25,
                    help="Only graphs with n <= n-max (caps hard-core cost)")
    ap.add_argument("--per-n-best", action="store_true",
                    help="Take the lowest-c_log graph per N (after dedup); "
                         "ignores --c-max. Hard-core is skipped for n > 22.")
    ap.add_argument("--hardcore-n-max", type=int, default=44,
                    help="Skip hard-core when n > this. Default 44 — empirically "
                         "the largest n at which the K4-free independence-set DFS "
                         "completes in ≤2s on graphs in this DB. Past n≈46 it "
                         "blows up (n=48 already times out at 60s).")
    ap.add_argument("--out", default=os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "results.csv"))
    args = ap.parse_args()

    with DB(auto_sync=False) as db:
        if args.per_n_best:
            rows = db.raw_execute("""
                SELECT graph_id, source, n, d_max, alpha, c_log
                FROM cache
                WHERE is_k4_free=1 AND alpha IS NOT NULL AND c_log IS NOT NULL
                  AND n <= ?
                ORDER BY n, c_log
            """, (args.n_max,))
            best_per_n: dict[int, dict] = {}
            for r in rows:
                if r["n"] not in best_per_n:
                    best_per_n[r["n"]] = r
            uniq = list(best_per_n.values())
        else:
            rows = db.raw_execute("""
                SELECT graph_id, source, n, d_max, alpha, c_log
                FROM cache
                WHERE is_k4_free=1 AND alpha IS NOT NULL AND c_log IS NOT NULL
                  AND c_log <= ? AND n <= ?
                ORDER BY c_log, n
            """, (args.c_max, args.n_max))
            seen = set(); uniq = []
            for r in rows:
                if r["graph_id"] in seen: continue
                seen.add(r["graph_id"]); uniq.append(r)

        graphs = []
        for r in uniq:
            G = db.nx(r["graph_id"])
            if G is None:
                print(f"  skip {r['graph_id'][:8]} (no graph found)", flush=True)
                continue
            graphs.append((r, G))

    mode = ("per-N best" if args.per_n_best
            else f"c_log ≤ {args.c_max}, n ≤ {args.n_max}")
    print(f"[tightness] {len(graphs)} unique graphs ({mode}) "
          f"hardcore_n_max={args.hardcore_n_max}", flush=True)

    out_rows = []
    t0 = time.time()
    for i, (r, G) in enumerate(graphs):
        gid, n, alpha = r["graph_id"], r["n"], r["alpha"]
        out = dict(
            graph_id=gid, source=r["source"], n=n, d_max=r["d_max"],
            alpha=alpha, c_log=r["c_log"],
        )

        t = time.time(); H = hoffman_bound(G); out["hoffman"] = H
        out["hoffman_t"] = round(time.time() - t, 4)

        t = time.time(); th = lovasz_theta(G); out["theta"] = th
        out["theta_t"] = round(time.time() - t, 4)

        t = time.time(); thp = schrijver_theta(G); out["theta_prime"] = thp
        out["theta_prime_t"] = round(time.time() - t, 4)

        t = time.time(); cf = fractional_chromatic_complement(G); out["chi_f"] = cf
        out["chi_f_t"] = round(time.time() - t, 4)

        t = time.time(); cc = greedy_clique_cover(G); out["clique_cover"] = cc
        out["clique_cover_t"] = round(time.time() - t, 4)

        if n <= args.hardcore_n_max:
            t = time.time()
            hc = hardcore_alpha(G)
            out["hardcore"] = hc.e_max
            out["hardcore_t"] = round(time.time() - t, 4)
        else:
            out["hardcore"] = None
            out["hardcore_t"] = None

        # Tightness ratios. Upper bounds: bound / α ≥ 1; closer to 1 is tighter.
        # Hardcore is a lower bound: α / hc ≥ 1; closer to 1 is tighter.
        for k in ("hoffman", "theta", "theta_prime", "chi_f", "clique_cover"):
            v = out[k]
            out[f"{k}_over_alpha"] = (round(v / alpha, 4)
                                      if v is not None and alpha else None)
        out["alpha_over_hardcore"] = (round(alpha / out["hardcore"], 4)
                                      if out["hardcore"] else None)

        out_rows.append(out)

        elapsed = time.time() - t0
        hc_str = f"{out['hardcore']:.3f}" if out["hardcore"] is not None else "  -  "
        print(f"  [{i+1}/{len(graphs)}] n={n:3d} α={alpha:3d} "
              f"H={out['hoffman']} θ={out['theta']} "
              f"θ'={out['theta_prime']} χ_f={out['chi_f']} "
              f"cc={out['clique_cover']} hc={hc_str} "
              f"({elapsed:.1f}s)", flush=True)

    fields = list(out_rows[0].keys())
    with open(args.out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for row in out_rows:
            w.writerow(row)
    print(f"[tightness] wrote {args.out}", flush=True)


if __name__ == "__main__":
    main()
