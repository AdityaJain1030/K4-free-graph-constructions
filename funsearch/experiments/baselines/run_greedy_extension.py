#!/usr/bin/env python3
"""
Greedy extension of baselines sweep
====================================
Fast version of run_baselines that uses greedy MIS (lower bound on α)
instead of SAT. Covers N=5..100 in minutes, not hours.

Strategy:
  - For N ≤ 20: reuse existing SAT-verified results from all_results.csv
    (compute c_greedy too for comparison).
  - For N=21..37: graphs already saved by prior run; recompute c_greedy
    from saved edgelists without re-running construction.
  - For N=38..100: run construction methods fresh, compute c_greedy only.

Output:
  - greedy_all_results.csv: all rows with c_sat (where available) + c_greedy
  - greedy_best_results.csv: best per (method, N) by c_greedy
  - c_vs_N_greedy.png: unified plot showing both SAT and greedy
  - greedy_summary.md: attractor values and SAT-vs-greedy comparison

Note: greedy_mis is a LOWER bound on α, so c_greedy ≤ c_sat. Using greedy
gives an optimistic (lower) estimate of c. For flat/random constructions
the greedy-vs-exact gap is typically < 5%; for structured graphs it can
be larger.

Usage:
    micromamba run -n funsearch python experiments/baselines/run_greedy_extension.py
"""

import argparse
import csv
import importlib.util
import json
import math
import os
import sys
import time
from collections import defaultdict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

sys.stdout.reconfigure(line_buffering=True)

_HERE = os.path.dirname(os.path.abspath(__file__))


def _load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_bl = _load_module("bl", os.path.join(_HERE, "run_baselines.py"))

run_method = _bl.run_method
select_blocks = _bl.select_blocks
greedy_mis = _bl.greedy_mis
d_cap_sweep = _bl.d_cap_sweep
save_edgelist = _bl.save_edgelist
compute_c_value = _bl.compute_c_value
degree_stats = _bl.degree_stats
is_k4_free = _bl.is_k4_free
METHODS = _bl.METHODS
LIBRARY_PATH = _bl.LIBRARY_PATH
PARETO_DIR = _bl.PARETO_DIR

OUTDIR = _HERE
GRAPH_DIR = os.path.join(OUTDIR, "graphs")


def load_edgelist(path):
    edges = []
    max_v = -1
    with open(path) as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) != 2:
                continue
            u, v = int(parts[0]), int(parts[1])
            edges.append((u, v))
            max_v = max(max_v, u, v)
    n = max_v + 1
    adj = np.zeros((n, n), dtype=np.int8)
    for u, v in edges:
        adj[u, v] = adj[v, u] = 1
    return adj, n


def load_sat_csv(path):
    """Return {(method, N, d_cap): row-dict} from existing SAT run."""
    out = {}
    if not os.path.exists(path):
        return out
    with open(path) as f:
        for r in csv.DictReader(f):
            try:
                key = (r["method"], int(r["N"]), int(r["d_cap"]))
            except (KeyError, ValueError, TypeError):
                continue
            out[key] = r
    return out


def load_sat_optimal(max_n=35):
    out = {}
    for N in range(2, max_n + 1):
        path = os.path.join(PARETO_DIR, f"pareto_n{N}.json")
        if not os.path.isfile(path):
            continue
        with open(path) as f:
            data = json.load(f)
        frontier = [e for e in data.get("pareto_frontier", [])
                    if e.get("c_log") is not None]
        if frontier:
            best = min(frontier, key=lambda e: e["c_log"])
            out[N] = (best["c_log"], data.get("time_limit", None))
    return out


def compute_row(adj, method, N, d_cap, alpha_sat=None, sat_timed_out=False,
                elapsed=0.0):
    d_max, d_min, d_mean, d_var, _ = degree_stats(adj)
    if d_max < 2:
        return None
    gmis = greedy_mis(adj)
    c_greedy = compute_c_value(gmis, N, d_max)
    c_sat = None
    if alpha_sat is not None:
        c_sat = compute_c_value(alpha_sat, N, d_max)
    return {
        "method": method,
        "N": N,
        "d_cap": d_cap,
        "d_max": d_max,
        "d_min": d_min,
        "d_mean": round(d_mean, 3),
        "d_var": round(d_var, 3),
        "greedy_mis": gmis,
        "alpha_sat": alpha_sat if alpha_sat is not None else "",
        "alpha_timed_out": int(sat_timed_out),
        "c_greedy": round(c_greedy, 4) if c_greedy and math.isfinite(c_greedy) else None,
        "c_sat": round(c_sat, 4) if c_sat is not None and math.isfinite(c_sat) else "",
        "time_s": round(elapsed, 2),
    }


def save_rows(rows, path):
    if not rows:
        return
    fields = ["method", "N", "d_cap", "d_max", "d_min", "d_mean", "d_var",
              "greedy_mis", "alpha_sat", "alpha_timed_out", "c_greedy", "c_sat",
              "time_s"]
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow(r)


def plot_c_vs_N(best_per_method_N, sat_opt_limited, out_path,
                sat_reliable_max=25):
    fig, ax = plt.subplots(figsize=(11, 6))
    colors = plt.cm.tab10.colors
    method_names = sorted({m for (m, _) in best_per_method_N.keys()})
    for i, method in enumerate(method_names):
        pts = sorted([(N, row["c_greedy"]) for (m, N), row in best_per_method_N.items()
                      if m == method and row["c_greedy"] is not None])
        if not pts:
            continue
        xs, ys = zip(*pts)
        ax.plot(xs, ys, "-o", color=colors[i % 10], markersize=3,
                linewidth=1.3, alpha=0.85, label=f"{method} (greedy)")
        # Overlay SAT-verified c_sat where available (N ≤ 20 typically)
        sat_pts = sorted([(N, float(row["c_sat"])) for (m, N), row in best_per_method_N.items()
                          if m == method and row.get("c_sat") not in ("", None)])
        if sat_pts:
            sxs, sys_ = zip(*sat_pts)
            ax.plot(sxs, sys_, "s", color=colors[i % 10], markersize=5,
                    markerfacecolor="white", markeredgewidth=1.3)

    # SAT-optimal reference (reliable portion only)
    if sat_opt_limited:
        xs = sorted(N for N in sat_opt_limited if N <= sat_reliable_max)
        ys = [sat_opt_limited[N][0] for N in xs]
        ax.plot(xs, ys, "--", color="red", linewidth=2, label=f"ILP-opt (N ≤ {sat_reliable_max})")
        # Extend unreliable portion as dotted
        xs2 = sorted(N for N in sat_opt_limited if N > sat_reliable_max)
        ys2 = [sat_opt_limited[N][0] for N in xs2]
        if xs2:
            ax.plot(xs2, ys2, ":", color="red", alpha=0.5, linewidth=1.5,
                    label="ILP upper bound (time-limited)")

    # P(17) disjoint-union baseline
    ax.axhline(0.6789, linestyle="-.", color="purple", linewidth=2,
               label="P(17) disjoint union = 0.679")
    ax.axhline(1.15, linestyle=":", color="gray", alpha=0.6,
               label="random baseline ≈ 1.15")

    ax.set_xlabel("N")
    ax.set_ylabel("c = α·d_max / (N·log(d_max))")
    ax.set_title("Baselines: greedy-MIS estimate of c vs N\n"
                 "solid = greedy α; open squares = SAT-verified α (N ≤ 20)")
    ax.legend(fontsize=8, loc="upper right")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)
    print(f"  Wrote {out_path}")


def write_summary(best_per_method_N, sat_opt_limited, runtime_s,
                  sat_reliable_max, out_path, n_max):
    by_method = defaultdict(list)
    for (m, N), row in best_per_method_N.items():
        if row["c_greedy"] is not None:
            by_method[m].append((N, row["c_greedy"]))
    for m in by_method:
        by_method[m].sort()

    final_c = {}
    for m, pts in by_method.items():
        tail = pts[-20:] if len(pts) >= 20 else pts
        if tail:
            final_c[m] = sum(c for _, c in tail) / len(tail)

    lines = [
        "# Baselines — Greedy Extension Summary",
        "",
        f"- Runtime: **{runtime_s/60:.1f} min**",
        f"- N range: {min(N for (_, N) in best_per_method_N.keys())}..{max(N for (_, N) in best_per_method_N.keys())}",
        f"- α estimator: **greedy MIS** (lower bound on true α → c_greedy ≤ c_true)",
        "- Caveat: For N ≤ 20, SAT-verified c_sat is available in the CSV for validation.",
        f"- Caveat: ILP-optimal reference is reliable only for N ≤ {sat_reliable_max}; "
        f"beyond that, pareto_n*.json entries are time-limited upper bounds.",
        "",
        "## 1. Attractor c (mean of last 20 samples, greedy α)",
        "",
        "| method | mean c_greedy (last 20 N) | samples |",
        "|--------|----------------------------|---------|",
    ]
    for m in sorted(final_c):
        lines.append(f"| {m} | {final_c[m]:.4f} | {len(by_method[m][-20:])} |")

    lines += ["",
              "## 2. c_greedy vs c_sat agreement (overlap region)",
              "",
              "For N ≤ 20 we have both. Greedy gap = c_sat − c_greedy "
              "(greedy underestimates α, so usually c_greedy ≤ c_sat).",
              ""]

    sat_overlap = [(m, N, row) for (m, N), row in best_per_method_N.items()
                   if row.get("c_sat") not in ("", None)
                   and row["c_greedy"] is not None]
    if sat_overlap:
        by_m = defaultdict(list)
        for m, N, row in sat_overlap:
            try:
                cs = float(row["c_sat"])
                gap = cs - row["c_greedy"]
                by_m[m].append(gap)
            except (TypeError, ValueError):
                continue
        lines += ["| method | mean |c_sat − c_greedy| | max gap | N points |",
                  "|--------|----------------------|---------|----------|"]
        for m in sorted(by_m):
            gaps = by_m[m]
            if gaps:
                lines.append(f"| {m} | {sum(abs(g) for g in gaps)/len(gaps):.4f} "
                             f"| {max(abs(g) for g in gaps):.4f} | {len(gaps)} |")

    lines += ["",
              "## 3. How much does c drop vs P(17) baseline?",
              "",
              "P(17) disjoint union: c = 0.6789 (trivial baseline).",
              "",
              "| method | attractor c_greedy | vs P(17) |",
              "|--------|---------------------|----------|"]
    for m in sorted(final_c):
        delta = final_c[m] - 0.6789
        sign = "+" if delta > 0 else ""
        lines.append(f"| {m} | {final_c[m]:.4f} | {sign}{delta:+.4f} |")

    lines += ["",
              "## 4. Best c_greedy per method across full N range",
              "",
              "| method | best N | best c_greedy | best α | best d_max |",
              "|--------|--------|----------------|--------|------------|"]
    for m in sorted(by_method):
        if not by_method[m]:
            continue
        best_pair = min(by_method[m], key=lambda t: t[1])
        N_best = best_pair[0]
        row = best_per_method_N[(m, N_best)]
        lines.append(f"| {m} | {N_best} | {best_pair[1]:.4f} "
                     f"| {row['greedy_mis']} | {row['d_max']} |")

    with open(out_path, "w") as f:
        f.write("\n".join(lines))
    print(f"  Wrote {out_path}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--n-min", type=int, default=5)
    parser.add_argument("--n-max", type=int, default=100)
    parser.add_argument("--methods", nargs="*", default=None)
    parser.add_argument("--method4-cutoff", type=int, default=60)
    parser.add_argument("--sat-reliable-max", type=int, default=25)
    args = parser.parse_args()

    t0 = time.time()
    os.makedirs(GRAPH_DIR, exist_ok=True)

    print("[step 1] Loading library and selecting blocks...")
    with open(LIBRARY_PATH) as f:
        library = json.load(f)
    blocks = select_blocks(library, os.path.join(OUTDIR, "blocks.json"))

    method_names = [m[0] for m in METHODS]
    if args.methods:
        method_names = [m for m in method_names if m in args.methods]

    print("[step 2] Loading existing SAT results for overlap validation...")
    sat_rows = load_sat_csv(os.path.join(OUTDIR, "all_results.csv"))
    print(f"  {len(sat_rows)} existing SAT rows")

    print("[step 3] Processing N=5..100...")
    all_rows = []
    best_per_method_N = {}  # (method, N) -> best row by c_greedy
    N_values = list(range(max(5, args.n_min), args.n_max + 1))

    for N in N_values:
        caps = d_cap_sweep(N)
        if not caps:
            continue
        t_N = time.time()
        for method in method_names:
            best = None
            for d_cap in caps:
                if method == "method4" and N > args.method4_cutoff:
                    continue
                # Check if we have an existing edgelist for this (method, N)
                # (saved by the killed SAT sweep).
                existing = os.path.join(GRAPH_DIR, f"{method}_N{N:03d}.edgelist")
                sat_key = (method, N, d_cap)
                sat_row = sat_rows.get(sat_key)
                # Construct if not cached — N ≥ 38 always needs this; for N ≤ 37
                # the saved graph might have been best across d_cap for the
                # prior sweep, but we still need to sweep d_cap to find the
                # best per method.
                try:
                    adj, elapsed = run_method(method, N, d_cap, blocks,
                                              rng_seed=N)
                except Exception as e:
                    print(f"  [N={N} {method} d={d_cap}] ERROR: {e}")
                    continue
                # Extract SAT alpha from row if available (timeout=60s ran)
                alpha_sat = None
                sat_to = False
                if sat_row is not None:
                    try:
                        alpha_sat = int(sat_row["alpha"])
                        sat_to = bool(int(sat_row.get("alpha_timed_out", 0)))
                    except (TypeError, ValueError):
                        alpha_sat = None
                row = compute_row(adj, method, N, d_cap,
                                  alpha_sat=alpha_sat, sat_timed_out=sat_to,
                                  elapsed=elapsed)
                if row is None:
                    continue
                all_rows.append(row)
                if row["c_greedy"] is not None:
                    if best is None or row["c_greedy"] < best["c_greedy"]:
                        best = dict(row)
                        best["adj"] = adj.copy()
            if best is not None:
                best_per_method_N[(method, N)] = best
                path = os.path.join(GRAPH_DIR, f"{method}_N{N:03d}.edgelist")
                save_edgelist(path, best["adj"])
        if N % 10 == 0 or N == N_values[-1]:
            t_total = time.time() - t0
            print(f"  [N={N}] total={t_total/60:.1f}min "
                  f"(N-elapsed={time.time()-t_N:.1f}s)")
        # Periodic save
        if N % 20 == 0:
            save_rows(all_rows, os.path.join(OUTDIR, "greedy_all_results.csv"))

    # Final save
    save_rows(all_rows, os.path.join(OUTDIR, "greedy_all_results.csv"))
    # Strip adj for serialization
    best_serialize = {k: {kk: vv for kk, vv in v.items() if kk != "adj"}
                      for k, v in best_per_method_N.items()}
    # Save best CSV
    best_rows = []
    for (m, N), row in sorted(best_per_method_N.items()):
        best_rows.append({kk: vv for kk, vv in row.items() if kk != "adj"})
    save_rows(best_rows, os.path.join(OUTDIR, "greedy_best_results.csv"))

    print("[step 4] SAT-optimal reference...")
    sat_opt = load_sat_optimal(max_n=35)

    print("[step 5] Plotting...")
    plot_c_vs_N(best_per_method_N, sat_opt,
                os.path.join(OUTDIR, "c_vs_N_greedy.png"),
                sat_reliable_max=args.sat_reliable_max)

    print("[step 6] Writing summary...")
    runtime_s = time.time() - t0
    write_summary(best_per_method_N, sat_opt, runtime_s,
                  args.sat_reliable_max,
                  os.path.join(OUTDIR, "greedy_summary.md"),
                  n_max=args.n_max)

    print(f"Done in {runtime_s/60:.1f} min.")


if __name__ == "__main__":
    main()
