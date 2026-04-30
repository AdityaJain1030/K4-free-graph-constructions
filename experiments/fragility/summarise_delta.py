#!/usr/bin/env python3
"""
experiments/fragility/summarise_delta.py
========================================
Print a compact summary of run_delta_distribution.py output.

For each (move, N) cell, prints one row per source: mean, P(<0),
P(>0.05), entropy, total legal proposals. The point is to make the
family-vs-family separation visible without opening the JSON.

    micromamba run -n k4free python experiments/fragility/summarise_delta.py \\
        --in experiments/fragility/data/delta_dist.json
"""

import argparse
import json
import os
import sys


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="in_path", default=os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "data", "delta_dist.json"))
    args = ap.parse_args()

    with open(args.in_path) as f:
        data = json.load(f)

    moves = data["moves"]
    rows = data["results"]

    # group by (move, N)
    by_move_n: dict[tuple[str, int], list[dict]] = {}
    for r in rows:
        seed_cl = (r.get("indicators") or {}).get("c_log")
        for m in moves:
            by_move_n.setdefault((m, r["n"]), []).append({
                "source": r["source"],
                "graph_id": r["graph_id"][:10],
                "seed_c_log": seed_cl,
                "summary": r["per_move"][m],
            })

    for m in moves:
        ns = sorted({n for (mm, n) in by_move_n if mm == m})
        print(f"\n=========== move = {m} ===========")
        for n in ns:
            print(f"\n  N={n}")
            print(f"  {'source':22s}  {'gid':>10s}  {'props':>6s}  "
                  f"{'mean':>8s}  {'rel μ':>7s}  {'P(<0)':>6s}  "
                  f"{'P(>0.05)':>9s}  {'entropy':>7s}")
            for entry in sorted(by_move_n[(m, n)], key=lambda x: x["source"]):
                s = entry["summary"]
                if s["mean"] is None:
                    print(f"  {entry['source']:22s}  {entry['graph_id']:>10s}  "
                          f"{s['legal_proposals_total']:>6d}  (no valid Δ)")
                    continue
                cl = entry["seed_c_log"]
                rel = (s["mean"] / cl) if (cl and cl > 0) else float("nan")
                rel_s = f"{rel:>+7.3f}" if rel == rel else "    nan"
                print(f"  {entry['source']:22s}  {entry['graph_id']:>10s}  "
                      f"{s['legal_proposals_total']:>6d}  "
                      f"{s['mean']:>+8.4f}  "
                      f"{rel_s}  "
                      f"{s['p_lt0']:>6.2f}  "
                      f"{s['p_gt_0.05']:>9.2f}  "
                      f"{s['entropy']:>7.3f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
