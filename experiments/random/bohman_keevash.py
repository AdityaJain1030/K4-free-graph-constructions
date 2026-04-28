#!/usr/bin/env python3
"""
experiments/random/bohman_keevash.py
=====================================
Bohman–Keevash random K4-free process — single canonical entry point.

Algorithm:
  start empty → repeatedly add a uniformly random K4-safe non-edge →
  stop at saturation (no safe edge remains).

Theory a.a.s. as N → ∞ (Wolfovitz 2010, arXiv:1008.4044):
  |E| = Θ(N^{8/5} (ln N)^{1/5}),
  α   = O(N^{3/5} (ln N)^{1/5}),
  Δ   ≈ Θ(N^{3/5} (ln N)^{1/5}).

Modes
-----
    # single N — print per-trial c_log, no persistence
    python experiments/random/bohman_keevash.py --n 50 --trials 5

    # full sweep — runs N-range, writes CSV + scaling plots, persists
    # best-per-N into graph_db (this is the authoritative producer).
    python experiments/random/bohman_keevash.py --sweep \
        --n-min 10 --n-max 100 --step 5 --trials 10

    # quick sweep — log-log fit only, no CSV/plots/persist
    python experiments/random/bohman_keevash.py --sweep --quick \
        --n-min 10 --n-max 60 --trials 5
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
import time
from math import log

import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, REPO)

from search import AggregateLogger
from search.stochastic_walk.edge_flip_walk import EdgeFlipWalk
from graph_db import DEFAULT_GRAPHS
from graph_db.store import GraphStore


DEFAULT_OUT_DIR = os.path.join(REPO, "docs", "images")
DEFAULT_RESULTS_CSV = os.path.join(HERE, "results", "bohman_keevash_sweep.csv")


# ── proposer: uniform over valid ADD moves only ───────────────────────────
# At saturation the valid-add set is empty → walk fails this step → with
# max_consecutive_failures=1 the trial halts cleanly.

def propose_adds_only(adj, valid_moves, info, rng, k):
    adds = [m for m in valid_moves if m[2]]
    if not adds:
        return []
    if k is None or k >= len(adds):
        return adds
    idx = rng.choice(len(adds), size=k, replace=False)
    return [adds[i] for i in idx]


def make_walk(n: int, num_trials: int, seed: int, agg) -> EdgeFlipWalk:
    """EdgeFlipWalk configured as the BK process; saves under name=bohman_keevash."""
    return EdgeFlipWalk(
        n=n,
        stop_fn=None,                                  # run to saturation
        propose_from_valid_moves_fn=propose_adds_only,
        n_candidates=1,                                # uniform 1-sample per step
        top_k=num_trials,                              # keep every trial
        verbosity=0,
        parent_logger=agg,
        num_trials=num_trials,
        seed=seed,
        max_steps=10 * n * n,
        max_consecutive_failures=1,                    # saturation = halt
        name="bohman_keevash",                         # persistence routes via this
    )


# ── single-N driver ────────────────────────────────────────────────────────


def cmd_single(args) -> None:
    with AggregateLogger(name="bohman_keevash") as agg:
        search = make_walk(args.n, args.trials, args.seed, agg)
        results = search.run()
    if not results:
        print(f"[n={args.n}] no result")
        return
    print(f"\n  bohman_keevash  n={args.n}  trials={args.trials}")
    print("  " + "-" * 60)
    for i, r in enumerate(results):
        print(f"  trial {i:>2}: c_log={r.c_log:.4f}  α={r.alpha:>3}  "
              f"d_max={r.d_max:>3}  |E|={r.metadata.get('edges', 0):>5}")
    best = min(results, key=lambda r: r.c_log if r.c_log is not None else float("inf"))
    print(f"  best c_log = {best.c_log:.4f}")


# ── sweep ─────────────────────────────────────────────────────────────────


def run_sweep(ns: list[int], trials: int, seed: int):
    """Returns (rows, bests, summary).

    rows    — every per-trial record (used by scatter plots).
    bests   — list of (n, best_result, search) for graph_db persistence.
    summary — one row per N for the CSV/log table.
    """
    rows: list[dict] = []
    bests: list[tuple] = []
    summary: list[dict] = []

    with AggregateLogger(name="bohman_keevash_sweep") as agg:
        for n in ns:
            t0 = time.monotonic()
            search = make_walk(n, trials, seed, agg)
            results = search.run()
            dt = time.monotonic() - t0
            if not results:
                print(f"  N={n:>3}  no result  ({dt:.1f}s)", flush=True)
                continue
            valid = [r for r in results if r.is_k4_free and r.c_log is not None]
            for r in valid:
                rows.append({
                    "n": n,
                    "trial": r.metadata.get("trial", 0),
                    "seed": r.metadata.get("seed", seed),
                    "alpha": int(r.alpha),
                    "d_max": int(r.d_max),
                    "edges": int(r.metadata.get("edges", 0)),
                    "steps": int(r.metadata.get("steps", 0)),
                    "c_log": float(r.c_log),
                })
            if not valid:
                continue
            best = min(valid, key=lambda r: r.c_log)
            bests.append((n, best, search))
            cs = np.array([r.c_log for r in valid])
            al = np.array([r.alpha for r in valid])
            dm = np.array([r.d_max for r in valid])
            em = np.array([r.metadata.get("edges", 0) for r in valid])
            row = {
                "n": n,
                "trials": len(valid),
                "best_c_log":   round(float(best.c_log), 6),
                "best_alpha":   int(best.alpha),
                "best_d_max":   int(best.d_max),
                "best_m":       int(best.metadata.get("edges", 0)),
                "mean_c_log":   round(float(cs.mean()), 6),
                "median_c_log": round(float(np.median(cs)), 6),
                "std_c_log":    round(float(cs.std()), 6),
                "mean_alpha":   round(float(al.mean()), 3),
                "median_alpha": round(float(np.median(al)), 3),
                "mean_d_max":   round(float(dm.mean()), 3),
                "median_d_max": round(float(np.median(dm)), 3),
                "mean_m":       round(float(em.mean()), 3),
                "median_m":     round(float(np.median(em)), 3),
                "elapsed_s":    round(dt, 3),
            }
            summary.append(row)
            print(
                f"  N={n:>3}  best c_log={row['best_c_log']:.4f}  "
                f"med α={row['median_alpha']:.1f}  med d={row['median_d_max']:.1f}  "
                f"med m={row['median_m']:.1f}  ({dt:.1f}s, {row['trials']} trials)",
                flush=True,
            )

    return rows, bests, summary


# ── persistence ───────────────────────────────────────────────────────────


def persist_bests(bests):
    """Wipe stale `bohman_keevash` records, then save best-per-N."""
    store = GraphStore(DEFAULT_GRAPHS)
    n_removed = store.remove(source="bohman_keevash")
    print(f"  cleared {n_removed} stale bohman_keevash records")
    new_count = 0
    for _n, r, search in bests:
        out = search.save([r])
        new_count += sum(1 for _, was_new in out if was_new)
    print(f"  saved {new_count} best-per-N graphs to graphs/bohman_keevash.json")


def write_csv(summary: list[dict], path: str) -> None:
    if not summary:
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fields = list(summary[0].keys())
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(summary)
    print(f"  wrote {path}")


# ── plots ─────────────────────────────────────────────────────────────────


def loglog_fit(xs, ys) -> tuple[float, float]:
    lx = np.log(np.asarray(xs, float))
    ly = np.log(np.asarray(ys, float))
    s, b = np.polyfit(lx, ly, 1)
    return float(s), float(b)


def make_plots(rows: list[dict], summary: list[dict], out_dir: str) -> dict:
    """
    Theory lines use Wolfovitz (2010, arXiv:1008.4044), which matches Bohman's
    lower bound up to constants:
        |E|   = Θ(N^{8/5} log^{1/5} N)        a.a.s.
        α     = O(N^{3/5} log^{1/5} N)        a.a.s.   (Wolfovitz Thm 1.2 / 1.3)
        Δ     ≈ Θ(N^{3/5} log^{1/5} N)        — empirical, no closed-form
                                                in the literature; tracks 2|E|/N
        c_log ≈ Θ(N^{1/5} log^{1/5} N / log N) = Θ(N^{1/5} / log^{4/5} N)
                                              — derived from the above
    """
    os.makedirs(out_dir, exist_ok=True)
    ns    = np.array([r["n"]            for r in summary], dtype=float)
    medm  = np.array([r["median_m"]     for r in summary], dtype=float)
    meda  = np.array([r["median_alpha"] for r in summary], dtype=float)
    medd  = np.array([r["median_d_max"] for r in summary], dtype=float)
    bestc = np.array([r["best_c_log"]   for r in summary], dtype=float)

    s_e, _ = loglog_fit(ns, medm)
    s_a, _ = loglog_fit(ns, meda)
    s_d, _ = loglog_fit(ns, medd)
    s_c, _ = loglog_fit(ns, bestc)

    all_n = np.array([r["n"] for r in rows], dtype=float) if rows else np.array([])
    all_m = np.array([r["edges"] for r in rows], dtype=float) if rows else np.array([])
    all_a = np.array([r["alpha"] for r in rows], dtype=float) if rows else np.array([])
    all_d = np.array([r["d_max"] for r in rows], dtype=float) if rows else np.array([])
    all_c = np.array([r["c_log"] for r in rows], dtype=float) if rows else np.array([])

    def _anchor(curve, target_first):
        return curve * (target_first / curve[0])

    fig, axs = plt.subplots(2, 2, figsize=(11.5, 9.5), constrained_layout=True)

    ax = axs[0, 0]
    if all_n.size:
        ax.loglog(all_n, all_m, "o", alpha=0.18, color="steelblue", ms=4, label="per trial")
    ax.loglog(ns, medm, "s-", color="navy", lw=1.5, ms=6,
              label=fr"median  (fit $N^{{{s_e:.3f}}}$)")
    th_e = _anchor(ns ** (8/5) * np.log(ns) ** (1/5), medm[0])
    ax.loglog(ns, th_e, "r--", lw=1.5, label=r"theory $N^{8/5}\log^{1/5}\!N$")
    ax.set_xlabel("N"); ax.set_ylabel("|E|")
    ax.set_title(r"Edges $|E|\sim N^{8/5}\log^{1/5}\!N$")
    ax.legend(loc="lower right", fontsize=9)
    ax.grid(True, which="both", alpha=0.3)

    ax = axs[0, 1]
    if all_n.size:
        ax.loglog(all_n, all_a, "o", alpha=0.18, color="seagreen", ms=4, label="per trial")
    ax.loglog(ns, meda, "s-", color="darkgreen", lw=1.5, ms=6,
              label=fr"median  (fit $N^{{{s_a:.3f}}}$)")
    th_a = _anchor(ns ** (3/5) * np.log(ns) ** (1/5), meda[0])
    ax.loglog(ns, th_a, "r--", lw=1.5, label=r"Wolfovitz $N^{3/5}\log^{1/5}\!N$")
    th_a_pure = _anchor(ns ** (3/5), meda[0])
    ax.loglog(ns, th_a_pure, "r:", lw=1.2, label=r"$N^{3/5}$ (no polylog)")
    ax.set_xlabel("N"); ax.set_ylabel(r"$\alpha$")
    ax.set_title(r"Independence number  $\alpha\sim N^{3/5}\log^{1/5}\!N$")
    ax.legend(loc="lower right", fontsize=9)
    ax.grid(True, which="both", alpha=0.3)

    ax = axs[1, 0]
    if all_n.size:
        ax.loglog(all_n, all_d, "o", alpha=0.18, color="goldenrod", ms=4, label="per trial")
    ax.loglog(ns, medd, "s-", color="darkorange", lw=1.5, ms=6,
              label=fr"median  (fit $N^{{{s_d:.3f}}}$)")
    th_d = _anchor(ns ** (3/5) * np.log(ns) ** (1/5), medd[0])
    ax.loglog(ns, th_d, "r--", lw=1.5,
              label=r"$N^{3/5}\log^{1/5}\!N$ (parallels $\alpha$)")
    th_d_pure = _anchor(ns ** (3/5), medd[0])
    ax.loglog(ns, th_d_pure, "r:", lw=1.2, label=r"$N^{3/5}$ (no polylog)")
    ax.set_xlabel("N"); ax.set_ylabel(r"$\Delta = d_{\max}$")
    ax.set_title(r"Max degree  $\Delta\sim N^{3/5}$")
    ax.legend(loc="lower right", fontsize=9)
    ax.grid(True, which="both", alpha=0.3)

    ax = axs[1, 1]
    if all_n.size:
        ax.semilogx(all_n, all_c, "o", alpha=0.18, color="crimson", ms=4, label="per trial")
    ax.semilogx(ns, bestc, "s-", color="darkred", lw=1.5, ms=6,
                label=fr"best per N  (fit $N^{{{s_c:.3f}}}$)")
    th_c = _anchor(ns ** (1/5) / np.log(ns) ** (3/5), bestc[0])
    ax.semilogx(ns, th_c, "r--", lw=1.5,
                label=r"Wolfovitz $\propto N^{1/5}/\log^{3/5}\!N$")
    ax.axhline(0.6789, color="black", linestyle=":", lw=1, label="frontier P(17): 0.6789")
    ax.set_xlabel("N"); ax.set_ylabel(r"$c_{\log}$")
    ax.set_title(r"$c_{\log} = \alpha\cdot d_{\max} / (N \ln d_{\max})$")
    ax.legend(loc="lower right", fontsize=9)
    ax.grid(True, which="both", alpha=0.3)

    n_trials_caption = f", {len(rows)} trials" if rows else ""
    fig.suptitle(
        f"Bohman–Keevash K4-free process: empirical vs theory "
        f"(N={int(ns.min())}..{int(ns.max())}{n_trials_caption})",
        fontsize=13,
    )
    out = os.path.join(out_dir, "bohman_keevash_scaling.png")
    fig.savefig(out, dpi=140, bbox_inches="tight")
    plt.close(fig)
    print(f"  wrote {out}")

    fig2, ax = plt.subplots(figsize=(7.5, 5), constrained_layout=True)
    if all_n.size:
        ax.semilogx(all_n, all_c, "o", alpha=0.22, color="crimson", ms=4,
                    label="per trial")
    ax.semilogx(ns, bestc, "s-", color="darkred", lw=2, ms=7, label="best per N")
    th_c = _anchor(ns ** (1/5) / np.log(ns) ** (3/5), bestc[0])
    ax.semilogx(ns, th_c, "r--", lw=1.5,
                label=r"Wolfovitz $\propto N^{1/5}/\log^{3/5}\!N$")
    ax.axhline(0.6789, color="black", linestyle=":", lw=1.3,
               label="frontier P(17) = 0.6789")
    ax.set_xlabel("N")
    ax.set_ylabel(r"$c_{\log}$")
    ax.set_title(r"Bohman–Keevash $c_{\log}$ growth with N")
    ax.legend(loc="best", fontsize=10)
    ax.grid(True, which="both", alpha=0.3)
    out2 = os.path.join(out_dir, "bohman_keevash_clog.png")
    fig2.savefig(out2, dpi=140, bbox_inches="tight")
    plt.close(fig2)
    print(f"  wrote {out2}")

    return {"slope_m": s_e, "slope_alpha": s_a, "slope_d_max": s_d, "slope_c_log": s_c}


# ── sweep entrypoint ──────────────────────────────────────────────────────


def cmd_sweep(args) -> None:
    ns = list(range(args.n_min, args.n_max + 1, args.step))
    print(f"\n  bohman_keevash sweep  N in {ns[0]}..{ns[-1]} step {args.step}  "
          f"trials={args.trials}  seed={args.seed}")
    print("  " + "-" * 76)

    rows, bests, summary = run_sweep(ns, args.trials, args.seed)

    if args.quick:
        # Lightweight mode: log-log fit only, no artifacts.
        if len(summary) >= 4:
            ns_arr = [r["n"] for r in summary]
            s_e, _ = loglog_fit(ns_arr, [r["median_m"] for r in summary])
            s_a, _ = loglog_fit(ns_arr, [r["median_alpha"] for r in summary])
            s_d, _ = loglog_fit(ns_arr, [r["median_d_max"] for r in summary])
            s_c, _ = loglog_fit(ns_arr, [r["best_c_log"] for r in summary])
            print("\n  log-log slopes (median per N, c_log = best per N):")
            print(f"    |E|   ~ N^{s_e:.3f}    Wolfovitz 1.600 + log^{1/5:.2f} N")
            print(f"    α     ~ N^{s_a:.3f}    Wolfovitz 0.600 + log^{1/5:.2f} N")
            print(f"    d_max ~ N^{s_d:.3f}    parallels α  (0.600 + log^{1/5:.2f})")
            print(f"    c_log ~ N^{s_c:.3f}    Wolfovitz N^{1/5:.2f} / log^{3/5:.2f} N")
        else:
            print("\nNot enough points for a fit.")
        return

    # Write CSV + plots BEFORE persistence — graph_db save requires nauty's
    # `labelg`, and we don't want a missing binary to lose 25 min of compute.
    if not args.no_csv:
        write_csv(summary, args.csv_path)
    if not args.no_plots:
        slopes = make_plots(rows, summary, args.plot_dir)
        print("\n  log-log slopes (median per N, c_log = best per N):")
        print(f"    |E|   ~ N^{slopes['slope_m']:.3f}    Wolfovitz 1.600 + log^{1/5:.2f} N")
        print(f"    α     ~ N^{slopes['slope_alpha']:.3f}    Wolfovitz 0.600 + log^{1/5:.2f} N")
        print(f"    d_max ~ N^{slopes['slope_d_max']:.3f}    parallels α  (0.600 + log^{1/5:.2f})")
        print(f"    c_log ~ N^{slopes['slope_c_log']:.3f}    Wolfovitz N^{1/5:.2f} / log^{3/5:.2f} N")
    if not args.no_save_graphs:
        try:
            persist_bests(bests)
        except RuntimeError as exc:
            print(f"\n  WARNING: persistence failed: {exc}")
            print(f"  CSV + plots already written; rerun with --no-csv --no-plots after fixing.")


# ── CLI ───────────────────────────────────────────────────────────────────


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sweep", action="store_true",
                    help="run an N-range sweep (default: single N via --n)")
    ap.add_argument("--quick", action="store_true",
                    help="(sweep mode) log-log fit only — skip CSV, plots, graph_db")
    ap.add_argument("--n", type=int, default=None,
                    help="(single mode) target N")
    ap.add_argument("--trials", type=int, default=10)
    ap.add_argument("--seed", type=int, default=20260427)
    ap.add_argument("--n-min", type=int, default=10)
    ap.add_argument("--n-max", type=int, default=100)
    ap.add_argument("--step", type=int, default=5)
    ap.add_argument("--no-save-graphs", action="store_true",
                    help="(sweep mode) skip overwriting graphs/bohman_keevash.json")
    ap.add_argument("--no-csv", action="store_true",
                    help="(sweep mode) skip CSV summary")
    ap.add_argument("--no-plots", action="store_true",
                    help="(sweep mode) skip scaling plots")
    ap.add_argument("--csv-path", default=DEFAULT_RESULTS_CSV)
    ap.add_argument("--plot-dir", default=DEFAULT_OUT_DIR)
    args = ap.parse_args()

    if args.sweep:
        cmd_sweep(args)
    else:
        if args.n is None:
            ap.error("--n required (or use --sweep)")
        cmd_single(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
