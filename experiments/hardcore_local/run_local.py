"""
experiments/hardcore_local/run_local.py
=======================================
Compare three lower bounds on α:

  α        — exact (cached in graph_db)
  E_max(G) — global hard-core marginal, λ Z(G−N[v],λ) / Z(G,λ) summed
  L_HC(G)  — local hard-core, λ / (λ + Z(T_v,λ)) summed

For every graph that bound_tightness recorded an E_max for, we
recompute α/E_max and additionally compute α/L_HC. The local bound
needs only the open-neighbourhood subgraph T_v at each vertex; the
global bound needs the full independence polynomial of G.

Usage:
  micromamba run -n k4free python experiments/hardcore_local/run_local.py
  # custom source CSV:
  micromamba run -n k4free python experiments/hardcore_local/run_local.py \\
      --source experiments/bound_tightness/results.csv
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
from utils.alpha_bounds import hardcore_local  # noqa: E402


HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default=os.path.join(
        REPO, "experiments", "bound_tightness", "results_per_n.csv"),
        help="Source CSV (graph ids + cached E_max). "
             "Default: bound_tightness per-N best.")
    ap.add_argument("--out", default=os.path.join(HERE, "results.csv"))
    args = ap.parse_args()

    with open(args.source) as f:
        src_rows = list(csv.DictReader(f))
    print(f"[local] loaded {len(src_rows)} rows from {args.source}", flush=True)

    out_rows = []
    t0 = time.time()
    with DB(auto_sync=False) as db:
        for i, r in enumerate(src_rows):
            gid = r["graph_id"]
            G = db.nx(gid)
            if G is None:
                continue
            n = int(r["n"])
            alpha = int(r["alpha"])
            e_max = float(r["hardcore"]) if r["hardcore"] not in ("", "None") else None

            t = time.time()
            l_hc = hardcore_local(G).e_max
            local_t = round(time.time() - t, 4)

            out = dict(
                graph_id=gid, source=r["source"], n=n, d_max=int(r["d_max"]),
                alpha=alpha, c_log=float(r["c_log"]),
                E_max=e_max, L_HC=l_hc, local_t=local_t,
                alpha_over_L_HC=round(alpha / l_hc, 4) if l_hc > 0 else None,
                alpha_over_E_max=(round(alpha / e_max, 4)
                                  if e_max else None),
                L_HC_over_E_max=(round(l_hc / e_max, 4)
                                 if e_max else None),
                L_HC_over_alpha=round(l_hc / alpha, 4) if alpha else None,
            )
            out_rows.append(out)

            elapsed = time.time() - t0
            ehc = f"{e_max:.3f}" if e_max is not None else "  -  "
            print(f"  [{i+1}/{len(src_rows)}] n={n:3d}  α={alpha:3d}  "
                  f"E_max={ehc}  L_HC={l_hc:.3f}  "
                  f"L_HC/α={l_hc/alpha:.3f}  "
                  f"({local_t*1000:.1f} ms, total {elapsed:.1f}s)",
                  flush=True)

    fields = list(out_rows[0].keys())
    with open(args.out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for row in out_rows:
            w.writerow(row)
    print(f"[local] wrote {args.out}", flush=True)


if __name__ == "__main__":
    main()
