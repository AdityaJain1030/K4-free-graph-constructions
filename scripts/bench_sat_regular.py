"""
scripts/bench_sat_regular.py
============================
Sweep SATRegular across (n, α) pairs and compare against the true
Pareto min-edge references in `reference/pareto/`.

Two configs per (n, α):
  A) spread=1, minimize_edges=True — near-regular heuristic + min-edge objective.
  B) spread=3, minimize_edges=True — relaxes near-regularity; can reach true
     optima whose optimal degree sequence spans >2 values (e.g. n=10 α=3: {2,3,4}).

Both use `edge_lex` + `branch_on_v0`.

Ranges are picked by the caller via --range. Default is "10-20".

Run:
    micromamba run -n k4free python scripts/bench_sat_regular.py
    micromamba run -n k4free python scripts/bench_sat_regular.py --range 20-25
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from search.sat_regular import SATRegular

REF_PARETO = ROOT / "reference" / "pareto"
OUT_DIR = ROOT / "logs"

PER_RUN_TIMEOUT = 900.0       # 15 min cap per single solve


def load_pareto(n: int) -> dict | None:
    for name in (f"pareto_n{n}.json", f"ilp_pareto_n{n}.json", f"brute_force_n{n}.json"):
        p = REF_PARETO / name
        if p.exists():
            return json.load(open(p))
    return None


def pareto_points(pareto: dict | None) -> list[tuple[int, int, int]]:
    """Return [(alpha, min_edges_at_alpha, d_max)] from pareto_frontier.

    Multiple entries with the same α are collapsed via min on edge count.
    """
    if pareto is None:
        return []
    seen: dict[int, tuple[int, int]] = {}
    for pt in pareto.get("pareto_frontier", []):
        a = pt.get("alpha")
        edges = pt.get("edges")
        e = len(edges) if isinstance(edges, list) else pt.get("num_edges")
        d = pt.get("d_max")
        if a is None or e is None:
            continue
        if a not in seen or e < seen[a][0]:
            seen[a] = (e, d)
    return sorted([(a, e, d) for a, (e, d) in seen.items()])


def run_one(n: int, a: int, spread: int, *, timeout: float, workers: int) -> dict:
    s = SATRegular(
        n=n, alpha=a,
        timeout_s=timeout,
        workers=workers,
        degree_spread=spread,
        symmetry_mode="none",
        branch_on_v0=True,
        minimize_edges=True,
        verbosity=0,
    )
    t0 = time.monotonic()
    results = s.run()
    elapsed = time.monotonic() - t0
    if not results:
        return {"status": "NO_WITNESS", "elapsed_s": round(elapsed, 2)}
    r = results[0]
    G = r.G
    degs = sorted(dict(G.degree()).values())
    return {
        "status":     "FEASIBLE",
        "num_edges":  G.number_of_edges(),
        "alpha":      r.alpha,
        "d_min":      min(degs),
        "d_max":      r.d_max,
        "D":          r.metadata.get("D"),
        "is_k4_free": bool(r.is_k4_free),
        "elapsed_s":  round(elapsed, 2),
        "edges":      sorted([sorted(e) for e in G.edges()]),
        "degree_seq": degs,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--range", default="10-20", help="n range, e.g. 10-20")
    ap.add_argument("--out",   default=None, help="output json path")
    ap.add_argument("--timeout", type=float, default=PER_RUN_TIMEOUT)
    ap.add_argument("--alpha-cap", type=int, default=7,
                    help="skip α values greater than this (trivial graphs)")
    args = ap.parse_args()

    lo, hi = [int(x) for x in args.range.split("-")]
    out_path = Path(args.out) if args.out else OUT_DIR / f"bench_sat_regular_{lo}_{hi}.json"

    cpus = os.cpu_count() or 8
    print(f"[bench] n={lo}..{hi}  α_cap={args.alpha_cap}  timeout={args.timeout}s  cpus={cpus}")
    print()

    rows: list[dict] = []
    t_total = time.monotonic()

    for n in range(lo, hi + 1):
        pareto = load_pareto(n)
        points = pareto_points(pareto)
        if not points:
            print(f"── n={n}: no pareto reference, skipping")
            continue
        for a, ref_edges, ref_d_max in points:
            if a > args.alpha_cap:
                continue
            if ref_edges == 0:
                continue

            label = f"n={n:2d} α={a}"
            print(f"── {label}  [ref: edges={ref_edges}, d_max={ref_d_max}]")

            # Config A: spread=1 (near-regular heuristic) + minimize
            a_got = run_one(n, a, spread=1, timeout=args.timeout, workers=cpus)
            match_A = a_got.get("num_edges") == ref_edges if a_got["status"] == "FEASIBLE" else False
            better_A = (a_got.get("num_edges", 10**9) < ref_edges) if a_got["status"] == "FEASIBLE" else False
            print(f"   spread=1: {a_got.get('status'):10s} edges={a_got.get('num_edges','-')} "
                  f"D={a_got.get('D','-')} t={a_got['elapsed_s']}s  "
                  f"{'✓match' if match_A else ('★better' if better_A else 'gap')}")

            # Config B: spread=3 (relaxed) + minimize
            b_got = run_one(n, a, spread=3, timeout=args.timeout, workers=cpus)
            match_B = b_got.get("num_edges") == ref_edges if b_got["status"] == "FEASIBLE" else False
            better_B = (b_got.get("num_edges", 10**9) < ref_edges) if b_got["status"] == "FEASIBLE" else False
            print(f"   spread=3: {b_got.get('status'):10s} edges={b_got.get('num_edges','-')} "
                  f"D={b_got.get('D','-')} t={b_got['elapsed_s']}s  "
                  f"{'✓match' if match_B else ('★better' if better_B else 'gap')}")

            rows.append({
                "n": n, "alpha": a,
                "pareto": {"ref_edges": ref_edges, "ref_d_max": ref_d_max},
                "spread_1": a_got,
                "spread_3": b_got,
                "match_spread_1": bool(match_A or better_A),
                "match_spread_3": bool(match_B or better_B),
            })

            # Persist incrementally so long runs don't lose data on interrupt.
            OUT_DIR.mkdir(parents=True, exist_ok=True)
            with out_path.open("w") as f:
                json.dump({
                    "range": [lo, hi],
                    "wall_s_so_far": round(time.monotonic() - t_total, 2),
                    "cases": rows,
                }, f, indent=2)

    wall = time.monotonic() - t_total
    print()
    print(f"[bench] wall={wall:.1f}s  wrote {out_path}")

    # Summary table.
    print()
    print(f"{'n':>3} {'α':>3} {'ref_e':>6} | {'s1_e':>5} {'s1_t':>6} {'s1_ok':>5} | {'s3_e':>5} {'s3_t':>6} {'s3_ok':>5}")
    print("-" * 70)
    for r in rows:
        s1, s3 = r["spread_1"], r["spread_3"]
        print(f"{r['n']:>3} {r['alpha']:>3} {r['pareto']['ref_edges']:>6} | "
              f"{s1.get('num_edges','-'):>5} {s1['elapsed_s']:>6} {str(r['match_spread_1']):>5} | "
              f"{s3.get('num_edges','-'):>5} {s3['elapsed_s']:>6} {str(r['match_spread_3']):>5}")


if __name__ == "__main__":
    main()
