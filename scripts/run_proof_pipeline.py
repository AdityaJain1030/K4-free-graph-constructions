#!/usr/bin/env python3
"""
scripts/run_proof_pipeline.py
==============================
End-to-end optimality-proof pipeline for K4-free extremal search at a
given N range. Designed for the 200 GB / 32-core server — the easy-scan
phase uses parallel α-tracks, and the hard-box phase pours every worker
into one CP-SAT solve at a time.

Phases, per N, in order:

  1. Easy scan  — SATExact with short per-box timeout and parallel-α.
                  Produces a c* witness and a per-box verdict log. Seed
                  comes from CirculantSearchFast, which is sub-minute at
                  any n in the practical range.

  2. Enumerate  — parse the scan log + optimality_proofs.json and collect
                  every (α, d) box with c_bound < c* that isn't already
                  Ramsey-infeasible, c_bound-pruned, or closed.

  3. Hard box   — for each open box, prove_box.prove_one with long
                  timeout and hard_box_params=True. On a TIMEOUT verdict
                  the timeout doubles and the box is retried (with a
                  different random seed) up to --hard-timeout-max. A
                  FEASIBLE witness that beats c* drops it, and the open
                  set is recomputed before the next box is handed to the
                  solver — shrinking c* as early as possible maximizes
                  c_bound pruning on the remainder.

  4. Report     — final verify; emit PROVED or the remaining open boxes.

Nothing new is written to disk that the existing tools don't already
consume:
  - easy scan → logs/search/sat_exact_n{N}_*.log  (via SATExact)
  - hard proofs → logs/optimality_proofs.json     (via prove_box)
The pipeline also writes a compact run-summary under logs/pipeline/.

Usage
-----
  # Prove N = 30..40 on a 32-core server.
  python scripts/run_proof_pipeline.py \
      --n-min 30 --n-max 40 \
      --easy-timeout 300 --easy-workers 4 --alpha-tracks 8 \
      --hard-timeout 3600 --hard-timeout-max 14400 --hard-workers 32

  # Resume: skip easy scan if a prior log produced a c*.
  python scripts/run_proof_pipeline.py --n 25 --resume

  # Skip the hard phase (just get best-found c*).
  python scripts/run_proof_pipeline.py --n-min 30 --n-max 40 --skip-hard
"""

from __future__ import annotations

import argparse
import faulthandler
import json
import os
import sys
import time

# enable() already handles SIGILL/SEGV/FPE/ABRT/BUS — that's its whole point.
# Writes a Python + C stack to stderr (logs/pipeline/job_*.err) on crash.
faulthandler.enable()

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from search import AggregateLogger, SATExact  # noqa: E402

from scripts.prove_box import prove_one, _append_result  # noqa: E402
from scripts.proof_report import _recover_c_star  # noqa: E402
from scripts.verify_optimality import (  # noqa: E402
    _load_proofs, _load_scan_log, verify,
)

DEFAULT_PROOFS    = os.path.join(REPO, "logs", "optimality_proofs.json")
DEFAULT_SCAN_LOGS = os.path.join(REPO, "logs", "search")
DEFAULT_OUT_DIR   = os.path.join(REPO, "logs", "pipeline")


# ── phase 1 ──────────────────────────────────────────────────────────────────


def _easy_scan(n, args, agg_logger):
    s = SATExact(
        n=n,
        top_k=args.top_k,
        verbosity=args.verbosity,
        parent_logger=agg_logger,
        timeout_s=args.easy_timeout,
        workers=args.easy_workers,
        parallel_alpha=args.alpha_tracks > 0,
        parallel_alpha_tracks=args.alpha_tracks,
    )
    t0 = time.monotonic()
    results = s.run()
    dt = time.monotonic() - t0
    if args.save_graphs and results:
        s.save(results)
    c = min((r.c_log for r in results if r.c_log is not None), default=None)
    return results, c, dt


# ── phase 3 ──────────────────────────────────────────────────────────────────


def _prove_open_boxes(n, open_boxes, c_star, args):
    """Walk open boxes by ascending c_bound, escalating timeout on
    TIMEOUT verdicts. Each FEASIBLE that beats c* updates it and lets
    subsequent boxes skip cheaply; re-enumeration happens in the outer
    loop so the scan log stays the source of truth."""
    open_sorted = sorted(open_boxes, key=lambda t: t[2])
    lowered = False

    for alpha, d, cb in open_sorted:
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
                n=n, alpha=alpha, d_max=d,
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

            # TIMEOUT (or ambiguous); escalate or give up.
            if tmo >= args.hard_timeout_max:
                print(f"       ! unresolved after {tmo:.0f}s; leaving OPEN")
                break
            tmo  = min(tmo * 2, args.hard_timeout_max)
            seed = (0 if seed is None else seed) + 1

    return c_star, lowered


# ── per-N orchestration ──────────────────────────────────────────────────────


def run_one_n(n, args, agg_logger, out_records):
    print("\n" + "=" * 72)
    print(f"Pipeline  N={n}")
    print("=" * 72)
    t_n0 = time.monotonic()

    # ── Phase 1 ──
    c_star = _recover_c_star(args.scan_logs, n) if args.resume else None
    if c_star is not None:
        print(f"[phase 1] resumed: c*={c_star:.6f} from prior scan log")
    else:
        print(
            f"[phase 1] easy scan  timeout={args.easy_timeout}s "
            f"workers={args.easy_workers} α-tracks={args.alpha_tracks}"
        )
        _, c_star, dt = _easy_scan(n, args, agg_logger)
        msg_c = f"{c_star:.6f}" if c_star is not None else "—"
        print(f"          → c*={msg_c}  ({dt:.1f}s)")

    if c_star is None:
        print("          ! no witness; leaving N OPEN.")
        out_records.append({
            "n": n, "status": "NO_SEED", "c_star": None,
            "open": [], "wall_s": round(time.monotonic() - t_n0, 2),
        })
        return

    if args.skip_hard:
        proofs = _load_proofs(args.proofs)
        scan   = _load_scan_log(args.scan_logs, n)
        rep    = verify(n, c_star, proofs, scan)
        status = "PROVED" if not rep["open"] else "OPEN"
        out_records.append({
            "n": n, "status": status, "c_star": c_star,
            "open": [(a, d) for a, d, _ in rep["open"]],
            "covered_n": len(rep["covered"]),
            "wall_s": round(time.monotonic() - t_n0, 2),
        })
        return

    # ── Phase 2 + 3 loop ──
    for rnd in range(1, args.max_prove_rounds + 1):
        proofs = _load_proofs(args.proofs)
        scan   = _load_scan_log(args.scan_logs, n)
        rep    = verify(n, c_star, proofs, scan)
        opens  = rep["open"]

        print(
            f"[phase 2] round {rnd}: covered={len(rep['covered'])} "
            f"open={len(opens)}  c*={c_star:.6f}"
        )
        if not opens:
            break
        for a, d, cb in sorted(opens, key=lambda t: t[2]):
            print(f"          OPEN α={a:2} d={d:2}  c_bound={cb:.4f}")

        print(f"[phase 3] hard-box prove (round {rnd})")
        c_star, lowered = _prove_open_boxes(n, opens, c_star, args)
        if not lowered:
            # No c* drop — the only way the next round does less work is
            # via the proofs we just appended, which the re-verify picks
            # up. One more round catches any boxes lowered-pruned by a
            # mid-round FEASIBLE; more rounds are rarely productive.
            if rnd >= 2:
                break

    # ── Phase 4 ──
    proofs = _load_proofs(args.proofs)
    scan   = _load_scan_log(args.scan_logs, n)
    rep    = verify(n, c_star, proofs, scan)

    if not rep["open"]:
        status = "PROVED"
        print(f"[phase 4] PROVED  c*={c_star:.6f} ✓")
    else:
        status = "OPEN"
        print(f"[phase 4] OPEN  c*={c_star:.6f}  {len(rep['open'])} box(es) unresolved")
        for a, d, cb in rep["open"]:
            print(f"          α={a:2} d={d:2}  c_bound={cb:.4f}")

    out_records.append({
        "n": n, "status": status, "c_star": c_star,
        "open": [(a, d) for a, d, _ in rep["open"]],
        "covered_n": len(rep["covered"]),
        "wall_s": round(time.monotonic() - t_n0, 2),
    })


# ── entry point ──────────────────────────────────────────────────────────────


def main() -> int:
    ap = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=__doc__,
    )
    ap.add_argument("--n",     type=int, default=None, help="Single N.")
    ap.add_argument("--n-min", type=int, default=None)
    ap.add_argument("--n-max", type=int, default=None)

    # Phase 1
    ap.add_argument("--easy-timeout", type=float, default=300.0,
                    help="Per-box SAT timeout during easy scan. Default 300.")
    ap.add_argument("--easy-workers", type=int, default=4,
                    help="CP-SAT threads per α-track. Default 4.")
    ap.add_argument("--alpha-tracks", type=int, default=8,
                    help="α-tracks in parallel during easy scan. 0 = "
                         "sequential. Default 8 (for 32-core server).")
    ap.add_argument("--top-k", type=int, default=1)
    ap.add_argument("--save-graphs", action="store_true",
                    help="Persist easy-scan witnesses to graph_db.")

    # Phase 3
    ap.add_argument("--hard-timeout", type=float, default=3600.0,
                    help="Initial per-box timeout in hard phase. Default 3600.")
    ap.add_argument("--hard-timeout-max", type=float, default=14400.0,
                    help="Per-box timeout ceiling after escalation. "
                         "Default 14400 (4h).")
    ap.add_argument("--hard-workers", type=int, default=32,
                    help="CP-SAT threads per box during hard phase. Default 32.")
    ap.add_argument("--symmetry", type=str, default="edge_lex",
                    choices=["none", "anchor", "chain", "edge_lex"])
    ap.add_argument("--random-seed", type=int, default=None)
    ap.add_argument("--solver-log", action="store_true",
                    help="Stream CP-SAT log_search_progress during hard phase.")
    ap.add_argument("--max-prove-rounds", type=int, default=3,
                    help="Cap on phase-2+3 iterations per N.")
    ap.add_argument("--skip-hard", action="store_true",
                    help="Run only the easy scan; skip hard-box phase.")

    # IO
    ap.add_argument("--proofs",    type=str, default=DEFAULT_PROOFS)
    ap.add_argument("--scan-logs", type=str, default=DEFAULT_SCAN_LOGS)
    ap.add_argument("--out-dir",   type=str, default=DEFAULT_OUT_DIR)
    ap.add_argument("--verbosity", type=int, default=1)
    ap.add_argument("--resume", action="store_true",
                    help="Skip easy scan if a scan log for this N already exists.")
    args = ap.parse_args()

    if args.n is None and args.n_min is None:
        ap.error("Provide --n or --n-min/--n-max.")
    ns = (
        [args.n] if args.n is not None
        else list(range(args.n_min, (args.n_max or args.n_min) + 1))
    )

    os.makedirs(args.out_dir, exist_ok=True)
    stamp    = time.strftime("%Y%m%d_%H%M%S")
    out_path = os.path.join(args.out_dir, f"proof_pipeline_{stamp}.json")

    t0 = time.monotonic()
    out_records: list[dict] = []
    with AggregateLogger(name="proof_pipeline") as agg:
        for n in ns:
            try:
                run_one_n(n, args, agg, out_records)
            except KeyboardInterrupt:
                print(f"\n!! interrupted during N={n}")
                break
            except Exception as exc:  # noqa: BLE001
                import traceback
                traceback.print_exc()
                out_records.append({
                    "n": n, "status": f"ERROR: {exc}",
                    "c_star": None, "open": [], "wall_s": 0.0,
                })

    # Summary
    print("\n" + "=" * 72)
    print("PIPELINE SUMMARY")
    print("=" * 72)
    print(f"{'N':>4}  {'status':<10}  {'c*':>10}  {'open':>5}  {'wall (s)':>10}")
    for rec in out_records:
        cstar   = rec.get("c_star")
        cstar_s = f"{cstar:.6f}" if isinstance(cstar, (int, float)) else "—"
        opens   = len(rec.get("open", []))
        wall    = rec.get("wall_s", 0) or 0
        print(
            f"{rec['n']:>4}  {rec.get('status','?'):<10}  "
            f"{cstar_s:>10}  {opens:>5}  {wall:>10.1f}"
        )
    print(f"\nTotal wall: {time.monotonic() - t0:.1f}s")

    with open(out_path, "w") as f:
        json.dump(out_records, f, indent=2)
    print(f"Wrote → {out_path}")

    return sum(1 for r in out_records if r.get("status") != "PROVED")


if __name__ == "__main__":
    sys.exit(main())
