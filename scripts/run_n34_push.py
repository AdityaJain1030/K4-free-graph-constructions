#!/usr/bin/env python3
"""
scripts/run_n34_push.py
========================
Targeted SAT-exact push at N=34, seeded with 2·P(17).

Why a dedicated driver
----------------------
`run_proof_pipeline.py` is the general N-range pipeline. It seeds c*
from CirculantSearchFast, which is a DFS with heuristic pruning — not
exhaustive — so it is not guaranteed to recover the known optimum at
n=34. We already proved (verify_p17_lift.py, verify_dihedral.py) that
2·P(17) is the unique c-minimizer among *all* Cayley graphs on 34
vertices, so we hand the solver that graph directly as both:

  1. the c* seed (drives c_log_prune across the scan),
  2. a CP-SAT warm-start hint for the α=6 d=8 box (cheap SAT confirm;
     no-op on the α ≤ 5 UNSAT boxes).

The flow per N=34:

  Phase 1 — SAT_exact Pareto scan with `seed_graph = 2·P(17)`. All
            (α, d) boxes whose c-bound ≥ 0.6789 are skipped by
            c_log_prune. Remaining boxes are SAT-solved with a short
            timeout; each returns FEASIBLE (new witness!) or
            INFEASIBLE (frontier closed) or TIMEOUT.

  Phase 2 — Parse logs, collect every box with c_bound < c* that
            isn't yet PROVED or closed.

  Phase 3 — Hard-box prove each open box with long timeout and
            hard_box_params=True. On a new FEASIBLE beating c*, c*
            drops and subsequent boxes prune harder. On TIMEOUT,
            escalate once before leaving OPEN.

  Phase 4 — Final verify + report.

Usage
-----
  # Cluster default: 8 α-tracks × 4 CP-SAT threads = 32 cores
  python scripts/run_n34_push.py \\
      --easy-timeout 600 --easy-workers 4 --alpha-tracks 8 \\
      --hard-timeout 7200 --hard-timeout-max 43200 --hard-workers 32

  # Local smoke test at N=34 with tiny budget (will leave boxes OPEN):
  python scripts/run_n34_push.py --easy-timeout 30 --alpha-tracks 0 \\
      --skip-hard
"""

from __future__ import annotations

import argparse
import faulthandler
import json
import math
import os
import sys
import time
from math import gcd

import networkx as nx

faulthandler.enable()

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from search import AggregateLogger, SATExact  # noqa: E402

from scripts.prove_box import prove_one, _append_result  # noqa: E402
from scripts.verify_optimality import _load_proofs, _load_scan_log, verify  # noqa: E402

DEFAULT_PROOFS    = os.path.join(REPO, "logs", "optimality_proofs.json")
DEFAULT_SCAN_LOGS = os.path.join(REPO, "logs", "search")
DEFAULT_OUT_DIR   = os.path.join(REPO, "logs", "pipeline")

N = 34
QR_17 = frozenset({1, 2, 4, 8, 9, 13, 15, 16})


# ── 2·P(17) constructor ──────────────────────────────────────────────────────


def build_2p17() -> nx.Graph:
    """Construct the 2-lift of P(17) as a Cayley graph on Z_34.

    Connection set is the CRT image of {0} × QR_17 under Z_2 × Z_17 ≅ Z_34.
    Equals {2, 4, 8, 16, 18, 26, 30, 32} (see verify_p17_lift.py and
    project memory `project_srg_catalog_screen` / `project_sat_regular_refactor`).
    Symmetric (closed under negation mod 34); degree 8; α = 6;
    c_log = 48 / (34 · ln 8) = 0.678915…
    """
    assert gcd(2, 17) == 1
    b = pow(2, -1, 17)  # 9
    S = frozenset((2 * x * b) % N for x in QR_17)
    assert S == frozenset({2, 4, 8, 16, 18, 26, 30, 32}), S
    G = nx.Graph()
    G.add_nodes_from(range(N))
    for v in range(N):
        for s in S:
            u = (v + s) % N
            if u != v:
                G.add_edge(v, u)
    return G


def _describe_seed(G: nx.Graph) -> dict:
    from utils.graph_props import alpha_exact_nx, c_log_value, is_k4_free_nx

    degs = dict(G.degree())
    d = max(degs.values()) if degs else 0
    a, _ = alpha_exact_nx(G)
    return {
        "n":          G.number_of_nodes(),
        "edges":      G.number_of_edges(),
        "d_max":      d,
        "alpha":      a,
        "c_log":      c_log_value(a, G.number_of_nodes(), d),
        "k4_free":    bool(is_k4_free_nx(G)),
        "regular":    len(set(degs.values())) == 1,
    }


# ── phase 1 ──────────────────────────────────────────────────────────────────


def _easy_scan(seed_G: nx.Graph, args, agg_logger):
    s = SATExact(
        n=N,
        top_k=args.top_k,
        verbosity=args.verbosity,
        parent_logger=agg_logger,
        timeout_s=args.easy_timeout,
        workers=args.easy_workers,
        parallel_alpha=args.alpha_tracks > 0,
        parallel_alpha_tracks=args.alpha_tracks,
        seed_from_circulant=False,   # override with explicit seed below
        seed_graph=seed_G,
        seed_hint=args.seed_hint,
    )
    t0 = time.monotonic()
    results = s.run()
    dt = time.monotonic() - t0
    if args.save_graphs and results:
        s.save(results)
    c = min((r.c_log for r in results if r.c_log is not None), default=None)
    return results, c, dt


# ── phase 3 ──────────────────────────────────────────────────────────────────


def _prove_open_boxes(open_boxes, c_star, args):
    """Hard-box-prove every open (α, d) in ascending c_bound order.
    Escalate timeout on TIMEOUT verdicts once before leaving OPEN."""
    lowered = False
    for alpha, d, cb in sorted(open_boxes, key=lambda t: t[2]):
        if cb >= c_star - 1e-6:
            print(f"    skip α={alpha} d={d}: c_bound={cb:.4f} ≥ c*={c_star:.4f}")
            continue

        tmo  = args.hard_timeout
        seed = args.random_seed
        while True:
            print(
                f"    ── α={alpha} d={d}  timeout={tmo:.0f}s  seed={seed}",
                flush=True,
            )
            rec = prove_one(
                n=N, alpha=alpha, d_max=d,
                timeout_s=tmo,
                workers=args.hard_workers,
                symmetry_mode=args.symmetry,
                random_seed=seed,
                solver_log=args.solver_log,
            )
            _append_result(args.proofs, rec)
            print(f"       → {rec['status']}  wall={rec['wall_s']}s")

            if rec["status"] == "FEASIBLE":
                w = rec["witness"] or {}
                c_w = w.get("c_log")
                print(
                    f"       witness α={w.get('alpha_actual')} "
                    f"d={w.get('d_max_actual')} c_log={c_w}"
                )
                if c_w is not None and c_w < c_star - 1e-9:
                    c_star = c_w
                    lowered = True
                    print(f"       c* ↓ {c_star:.6f}")
                break
            if rec["status"] in ("INFEASIBLE", "INFEASIBLE_RAMSEY"):
                break
            if tmo >= args.hard_timeout_max:
                print(f"       ! unresolved after {tmo:.0f}s; leaving OPEN")
                break
            tmo  = min(tmo * 2, args.hard_timeout_max)
            seed = (0 if seed is None else seed) + 1

    return c_star, lowered


# ── orchestration ────────────────────────────────────────────────────────────


def run(args, agg_logger) -> dict:
    print("=" * 72)
    print(f"N={N} push — seed = 2·P(17)")
    print("=" * 72)

    # Build and describe the seed
    seed_G = build_2p17()
    meta = _describe_seed(seed_G)
    print(f"[seed] 2·P(17): n={meta['n']} m={meta['edges']} "
          f"d={meta['d_max']} α={meta['alpha']} c={meta['c_log']:.6f} "
          f"k4_free={meta['k4_free']} regular={meta['regular']}")
    if not meta["k4_free"]:
        raise RuntimeError("2·P(17) seed failed K4-free check — bug in builder.")
    c_seed = meta["c_log"]

    t0 = time.monotonic()

    # ── Phase 1 ──
    print(f"[phase 1] easy scan  timeout={args.easy_timeout}s "
          f"workers={args.easy_workers} α-tracks={args.alpha_tracks} "
          f"hint={args.seed_hint}")
    _, c_star, dt = _easy_scan(seed_G, args, agg_logger)
    if c_star is None or c_star > c_seed:
        c_star = c_seed  # seed witness guarantees this c*
    print(f"          → c*={c_star:.6f}  ({dt:.1f}s)")

    if args.skip_hard:
        proofs = _load_proofs(args.proofs)
        scan   = _load_scan_log(args.scan_logs, N)
        rep    = verify(N, c_star, proofs, scan)
        status = "PROVED" if not rep["open"] else "OPEN"
        return {
            "n": N, "status": status, "c_star": c_star,
            "open": [(a, d) for a, d, _ in rep["open"]],
            "covered_n": len(rep["covered"]),
            "wall_s": round(time.monotonic() - t0, 2),
        }

    # ── Phase 2 + 3 loop ──
    for rnd in range(1, args.max_prove_rounds + 1):
        proofs = _load_proofs(args.proofs)
        scan   = _load_scan_log(args.scan_logs, N)
        rep    = verify(N, c_star, proofs, scan)
        opens  = rep["open"]

        print(f"[phase 2] round {rnd}: covered={len(rep['covered'])} "
              f"open={len(opens)}  c*={c_star:.6f}")
        if not opens:
            break
        for a, d, cb in sorted(opens, key=lambda t: t[2]):
            print(f"          OPEN α={a:2} d={d:2}  c_bound={cb:.4f}")

        print(f"[phase 3] hard-box prove (round {rnd})")
        c_star, lowered = _prove_open_boxes(opens, c_star, args)
        if not lowered and rnd >= 2:
            break

    # ── Phase 4 ──
    proofs = _load_proofs(args.proofs)
    scan   = _load_scan_log(args.scan_logs, N)
    rep    = verify(N, c_star, proofs, scan)
    if not rep["open"]:
        status = "PROVED"
        print(f"[phase 4] PROVED  c*={c_star:.6f} ✓")
    else:
        status = "OPEN"
        print(f"[phase 4] OPEN  c*={c_star:.6f}  "
              f"{len(rep['open'])} box(es) unresolved")
        for a, d, cb in rep["open"]:
            print(f"          α={a:2} d={d:2}  c_bound={cb:.4f}")

    return {
        "n": N, "status": status, "c_star": c_star,
        "open": [(a, d) for a, d, _ in rep["open"]],
        "covered_n": len(rep["covered"]),
        "wall_s": round(time.monotonic() - t0, 2),
    }


# ── entry point ──────────────────────────────────────────────────────────────


def main() -> int:
    ap = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=__doc__,
    )
    # Phase 1
    ap.add_argument("--easy-timeout", type=float, default=600.0,
                    help="Per-box SAT timeout during easy scan. Default 600.")
    ap.add_argument("--easy-workers", type=int, default=4,
                    help="CP-SAT threads per α-track. Default 4.")
    ap.add_argument("--alpha-tracks", type=int, default=8,
                    help="α-tracks in parallel during easy scan. "
                         "0 = sequential. Default 8.")
    ap.add_argument("--top-k", type=int, default=1)
    ap.add_argument("--save-graphs", action="store_true")
    ap.add_argument("--seed-hint", action="store_true",
                    help="Pass the 2·P(17) seed to CP-SAT as a warm-start "
                         "hint. Helps SAT proofs (α=6 d=8) and is neutral "
                         "for UNSAT (α ≤ 5).")
    # Phase 3
    ap.add_argument("--hard-timeout", type=float, default=7200.0,
                    help="Initial per-box timeout in hard phase. Default 7200 (2h).")
    ap.add_argument("--hard-timeout-max", type=float, default=43200.0,
                    help="Per-box timeout ceiling after escalation. "
                         "Default 43200 (12h).")
    ap.add_argument("--hard-workers", type=int, default=32)
    ap.add_argument("--symmetry", type=str, default="edge_lex",
                    choices=["none", "anchor", "chain", "edge_lex"])
    ap.add_argument("--random-seed", type=int, default=None)
    ap.add_argument("--solver-log", action="store_true")
    ap.add_argument("--max-prove-rounds", type=int, default=3)
    ap.add_argument("--skip-hard", action="store_true")
    # IO
    ap.add_argument("--proofs",    type=str, default=DEFAULT_PROOFS)
    ap.add_argument("--scan-logs", type=str, default=DEFAULT_SCAN_LOGS)
    ap.add_argument("--out-dir",   type=str, default=DEFAULT_OUT_DIR)
    ap.add_argument("--verbosity", type=int, default=1)
    args = ap.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)
    stamp    = time.strftime("%Y%m%d_%H%M%S")
    out_path = os.path.join(args.out_dir, f"n34_push_{stamp}.json")

    t0 = time.monotonic()
    with AggregateLogger(name="n34_push") as agg:
        try:
            rec = run(args, agg)
        except KeyboardInterrupt:
            print("\n!! interrupted")
            rec = {"n": N, "status": "INTERRUPTED",
                   "c_star": None, "open": [], "wall_s": 0.0}

    print("\n" + "=" * 72)
    print("N=34 PUSH SUMMARY")
    print("=" * 72)
    cstar = rec.get("c_star")
    cstar_s = f"{cstar:.6f}" if isinstance(cstar, (int, float)) else "—"
    print(f"status={rec.get('status','?')}  c*={cstar_s}  "
          f"open={len(rec.get('open', []))}  "
          f"wall={rec.get('wall_s', 0):.1f}s")
    if rec.get("open"):
        for (a, d) in rec["open"]:
            print(f"  OPEN α={a:2} d={d:2}")
    print(f"\nTotal wall: {time.monotonic() - t0:.1f}s")

    with open(out_path, "w") as f:
        json.dump(rec, f, indent=2)
    print(f"Wrote → {out_path}")

    return 0 if rec.get("status") == "PROVED" else 1


if __name__ == "__main__":
    sys.exit(main())
