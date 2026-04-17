#!/usr/bin/env python3
"""
Extend Forced-Matching Experiment with Large, Ramsey-Relevant Blocks
====================================================================
The base experiment (run_experiment.py) hit an asymptotic floor at c ≈ 0.9017
due to |S| ≤ α and the small-n library. This script adds larger blocks:

    1. Paley P(17)               — 17-regular strongly-regular (17,8,3,4),
                                   K₄-free, α=3, d=8. Vertex-transitive ⇒
                                   predicted k*=0 (no α-forced vertices).
    2. Random K₄-free at n=10,12,16 — keep the minimum-α graph per size.
    3. SAT-optimal K₄-free at n=24  — from pareto_n24.json (α=4, d=10).

Each new block:
    - analyzed for α-forced vertices and linear-drop capacity k*
    - swept k=2..k_max copies with SAT-verified α

Outputs (append / regenerate):
    - block_scan.csv           (new rows for new blocks, with source tag)
    - construction_results.csv (new sweep rows)
    - tradeoff_plot.png        (old + new blocks, new ones starred)
    - c_vs_N.png               (baseline + new blocks overlaid)
    - summary.md               (+ `## Large Block Extension` section)
    - large_blocks_results.json (full dump for reproducibility)

Usage:
    micromamba run -n funsearch python experiments/forced_matching/extend_large_blocks.py
"""

import argparse
import csv
import importlib.util
import json
import math
import os
import random
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


_fm = _load_module("fm_run", os.path.join(_HERE, "run_experiment.py"))
_bd = _fm._bd
_sc = _load_module(
    "sel_cross",
    os.path.join(_HERE, "..", "selective_crossedge", "run_experiment.py"),
)

alpha_exact = _bd.alpha_exact
alpha_sat = _bd.alpha_sat
alpha_of_subset = _bd.alpha_of_subset
is_k4_free = _bd.is_k4_free
compute_c_value = _bd.compute_c_value
adj_to_graph6 = _bd.adj_to_graph6
find_alpha_dropping_sets = _bd.find_alpha_dropping_sets

would_create_k4 = _sc.would_create_k4
compute_nbr_masks = _sc.compute_nbr_masks

scan_blocks = _fm.scan_blocks
evaluate_single_type_sweep = _fm.evaluate_single_type_sweep
extract_forced_vertices = _fm.extract_forced_vertices
linear_drop_capacity = _fm.linear_drop_capacity
block_to_adj = _fm.block_to_adj
compute_alpha = _fm.compute_alpha
plot_tradeoff = _fm.plot_tradeoff
plot_c_vs_n = _fm.plot_c_vs_n
load_sat_optimal_map = _fm.load_sat_optimal_map

PARETO_DIR = _fm.PARETO_DIR
OUTDIR = _HERE


# =============================================================================
# Block constructors
# =============================================================================

def paley_graph_17():
    """Paley graph P(17): vertices Z/17, (u,v) edge iff (u-v) mod 17 is a QR.
    QR mod 17 = {1, 2, 4, 8, 9, 13, 15, 16}. Parameters (17, 8, 3, 4)."""
    n = 17
    qr = {pow(x, 2, 17) for x in range(1, 17)}  # {1,2,4,8,9,13,15,16}
    adj = np.zeros((n, n), dtype=np.bool_)
    for u in range(n):
        for v in range(n):
            if u != v and ((u - v) % 17) in qr:
                adj[u, v] = True
    # sanity: symmetric (QR set is closed under negation mod 17)
    assert np.array_equal(adj, adj.T), "Paley adj not symmetric"
    degs = adj.sum(axis=1)
    assert (degs == 8).all(), f"Paley not 8-regular: degs={degs}"
    assert is_k4_free(adj), "Paley P(17) should be K4-free"
    alpha, _ = alpha_exact(adj)
    assert alpha == 3, f"Paley P(17) should have α=3 (got {alpha})"
    assert int(adj.sum()) // 2 == 68, f"Paley P(17) should have 68 edges"
    return adj


def generate_random_k4free(n, num_trials, seed=0, verbose=False):
    """Random K4-free graph: shuffle all C(n,2) edges, add each if K4-free.
    Return the instance minimizing α (tiebreak lower d_max).
    Also returns a small log of (trial, alpha, d_max)."""
    rng = random.Random(seed)
    all_edges = [(u, v) for u in range(n) for v in range(u + 1, n)]
    best_adj = None
    best_alpha = float("inf")
    best_dmax = float("inf")
    log = []
    for t in range(num_trials):
        order = list(all_edges)
        rng.shuffle(order)
        adj = np.zeros((n, n), dtype=np.bool_)
        nbr = [0] * n
        for u, v in order:
            if (nbr[u] & nbr[v]):
                common = nbr[u] & nbr[v]
                tmp = common
                k4 = False
                while tmp:
                    c = (tmp & -tmp).bit_length() - 1
                    if nbr[c] & (common & ~(1 << c)):
                        k4 = True
                        break
                    tmp &= tmp - 1
                if k4:
                    continue
            adj[u, v] = adj[v, u] = True
            nbr[u] |= 1 << v
            nbr[v] |= 1 << u
        a, _ = alpha_exact(adj)
        d = int(adj.sum(axis=1).max())
        if (a, d) < (best_alpha, best_dmax):
            best_alpha = a
            best_dmax = d
            best_adj = adj.copy()
            if verbose:
                print(f"    [n={n} trial {t}] new best α={a}, d_max={d}")
        if len(log) < 50:
            log.append({"trial": t, "alpha": int(a), "d_max": d})
    return best_adj, {"best_alpha": int(best_alpha), "best_d_max": int(best_dmax),
                      "num_trials": num_trials, "sample_log": log}


def load_min_alpha_n24():
    """Load minimum-α K4-free from SAT/k4free_ilp/results/pareto_n24.json."""
    path = os.path.join(PARETO_DIR, "pareto_n24.json")
    with open(path) as f:
        data = json.load(f)
    frontier = [e for e in data.get("pareto_frontier", [])
                if e.get("c_log") is not None]
    if not frontier:
        raise RuntimeError("pareto_n24 has no valid entries")
    best = min(frontier, key=lambda e: (e["alpha"], e["d_max"]))
    n = data["n"]
    adj = np.zeros((n, n), dtype=np.bool_)
    for u, v in best["edges"]:
        adj[u, v] = adj[v, u] = True
    assert is_k4_free(adj), "pareto_n24 min-α entry not K4-free"
    return adj, best


# =============================================================================
# adj → block dict
# =============================================================================

def adj_to_block(adj, block_id, source_tag, alpha=None, max_is=50000):
    """Build a library-compatible block dict from an adjacency matrix."""
    n = adj.shape[0]
    if alpha is None:
        a, _ = alpha_exact(adj)
        alpha = int(a)
    d_max = int(adj.sum(axis=1).max())
    edges = [[u, v] for u in range(n) for v in range(u + 1, n) if adj[u, v]]
    print(f"  [{source_tag}] computing alpha-dropping sets (n={n}, α={alpha})...")
    t0 = time.time()
    dropping = find_alpha_dropping_sets(adj, alpha, max_is=max_is)
    print(f"    found {len(dropping)} alpha-dropping IS "
          f"({sum(1 for d in dropping if d['size'] == 1)} single-vertex) "
          f"in {time.time() - t0:.1f}s")
    return {
        "block_id": block_id,
        "source": source_tag,
        "n": n,
        "alpha": int(alpha),
        "d_max": d_max,
        "edges": edges,
        "alpha_dropping_sets": dropping,
        "g6": adj_to_graph6(adj),
    }


# =============================================================================
# Paley-specific linear-drop probe
# =============================================================================

def paley_linear_probe(adj, alpha, num_trials=30, seed=0):
    """For Paley (vertex-transitive), check α(B - T) for random k-subsets.
    Reports: is any single vertex α-forced? What's the actual drop pattern?
    """
    rng = random.Random(seed)
    n = adj.shape[0]
    all_mask = (1 << n) - 1
    out = {}
    # Single-vertex: by vertex-transitivity, same for all v; check v=0.
    mask = all_mask & ~(1 << 0)
    a1 = alpha_of_subset(adj, mask)
    out["alpha_minus_any_vertex"] = int(a1)
    out["any_vertex_forced"] = (a1 == alpha - 1)
    for k in range(2, alpha + 2):
        results = []
        for t in range(num_trials):
            T = rng.sample(range(n), k)
            m = all_mask
            for v in T:
                m &= ~(1 << v)
            results.append(alpha_of_subset(adj, m))
        out[f"k={k}"] = {
            "min": int(min(results)),
            "max": int(max(results)),
            "mean": float(np.mean(results)),
            "predicted_linear": alpha - k,
            "num_hits_linear": int(sum(1 for r in results if r == alpha - k)),
            "num_trials": num_trials,
        }
    return out


# =============================================================================
# CSV append helpers
# =============================================================================

def _find_existing(paths):
    for p in paths:
        if os.path.isfile(p):
            return p
    return None


SCAN_CSV = os.path.join(OUTDIR, "block_scan.csv")
CONS_CSV = os.path.join(OUTDIR, "construction_results.csv")
SCAN_TXT = os.path.join(OUTDIR, "block_scan.txt")
SCAN_TXT2 = os.path.join(OUTDIR, "construction_results (2).txt")  # observed name
CONS_TXT = os.path.join(OUTDIR, "construction_results.txt")

SCAN_COLS = [
    "block_id", "source", "n", "alpha", "d_max", "num_forced",
    "alpha_ratio", "forced_ratio",
    "worst_linear_k", "best_linear_k", "linear_witness",
    "is_triangle_free", "min_forced_deg", "forced", "g6",
]

CONS_COLS = [
    "construction", "N", "num_blocks", "num_matching",
    "predicted_alpha", "actual_alpha", "alpha_gap",
    "d_max", "c", "k4_free", "block_ids", "k_copies", "source", "g6",
]


def _read_existing_csv(paths, expected_cols):
    """Read existing CSV rows (from .csv or fallback .txt).
    Return (rows_list_of_dict, source_path_used). Missing columns are blanked."""
    src = _find_existing(paths)
    if not src:
        return [], None
    rows = []
    with open(src, newline="") as f:
        reader = csv.DictReader(f)
        for r in reader:
            # Fill missing columns with blank
            for c in expected_cols:
                if c not in r:
                    r[c] = ""
            rows.append(r)
    return rows, src


def _write_csv(path, rows, cols):
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rows:
            # restrict to expected columns; blank missing
            row = {c: r.get(c, "") for c in cols}
            w.writerow(row)


def scan_rec_to_csvrow(rec, source_tag):
    return {
        "block_id": rec["block_id"],
        "source": source_tag,
        "n": rec["n"],
        "alpha": rec["alpha"],
        "d_max": rec["d_max"],
        "num_forced": rec["num_forced"],
        "alpha_ratio": f"{rec['alpha_ratio']:.4f}",
        "forced_ratio": f"{rec['forced_ratio']:.4f}",
        "worst_linear_k": rec.get("worst_linear_k", 0),
        "best_linear_k": rec.get("best_linear_k", 0),
        "linear_witness": "|".join(str(v) for v in rec.get("linear_witness", [])),
        "is_triangle_free": int(rec["is_triangle_free"]),
        "min_forced_deg": rec["min_forced_deg"] if rec["min_forced_deg"] is not None else "",
        "forced": "|".join(str(v) for v in rec["forced"]),
        "g6": rec["g6"],
    }


def sweep_rec_to_csvrow(r, source_tag):
    return {
        "construction": r["construction"],
        "N": r["N"],
        "num_blocks": 1,
        "num_matching": r["num_matching"],
        "predicted_alpha": r["predicted_alpha"],
        "actual_alpha": r["actual_alpha"],
        "alpha_gap": r["alpha_gap"],
        "d_max": r["d_max"],
        "c": r["c"],
        "k4_free": int(r["k4_free"]),
        "block_ids": r["block_id"],
        "k_copies": r["k_copies"],
        "source": source_tag,
        "g6": r["g6"],
    }


# =============================================================================
# Plot overlay helpers
# =============================================================================

def plot_tradeoff_overlay(base_rows, new_scan_recs, block_best_c, out_path):
    fig, ax = plt.subplots(figsize=(9, 6))
    # base rows (from existing CSV): only plot if best_linear_k > 0 and we have a best_c
    base_xs, base_ys, base_cs, base_sz = [], [], [], []
    for r in base_rows:
        try:
            nf = int(r["num_forced"])
        except (ValueError, TypeError):
            continue
        if nf == 0:
            continue
        try:
            bid = int(r["block_id"])
            n = int(r["n"])
            a = int(r["alpha"])
        except (ValueError, TypeError):
            continue
        bc = block_best_c.get(bid)
        if bc is None:
            continue
        base_xs.append(a / n)
        base_ys.append(nf / n)
        base_cs.append(bc)
        base_sz.append(10 + 5 * n)
    if base_xs:
        sc = ax.scatter(base_xs, base_ys, c=base_cs, s=base_sz, cmap="viridis_r",
                        alpha=0.55, edgecolors="k", linewidths=0.3,
                        label="library (n≤8)")
        cb = plt.colorbar(sc, ax=ax)
        cb.set_label("best c achieved (lower is better)")

    # new blocks — star markers, annotated
    nxs, nys, ncs, nsz, labels = [], [], [], [], []
    for rec in new_scan_recs:
        if rec["num_forced"] == 0:
            # still plot at y=0 to show the absence-of-forced case
            nxs.append(rec["alpha_ratio"])
            nys.append(0.0)
            ncs.append(block_best_c.get(rec["block_id"], 2.0))
            nsz.append(120 + 6 * rec["n"])
            labels.append(f"{rec.get('source','?')}\nn={rec['n']},α={rec['alpha']},|S|=0")
            continue
        nxs.append(rec["alpha_ratio"])
        nys.append(rec["forced_ratio"])
        ncs.append(block_best_c.get(rec["block_id"], 2.0))
        nsz.append(120 + 6 * rec["n"])
        labels.append(f"{rec.get('source','?')}\nn={rec['n']},α={rec['alpha']},k*={rec.get('best_linear_k',0)}")
    if nxs:
        ax.scatter(nxs, nys, c=ncs, s=nsz, marker="*", cmap="viridis_r",
                   edgecolors="red", linewidths=1.3, label="large blocks (new)")
        for x, y, lab in zip(nxs, nys, labels):
            ax.annotate(lab, (x, y), fontsize=7, xytext=(6, 6),
                        textcoords="offset points", color="darkred")

    ax.set_xlabel(r"$\alpha(B)/|V(B)|$")
    ax.set_ylabel(r"$|S|/|V(B)|$ (forced-vertex density)")
    ax.set_title("Block tradeoff — small library + large blocks")
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=9, loc="best")
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)


def plot_c_vs_n_overlay(base_single_rows, new_single_results, sat_opt,
                        out_path, random_baseline=1.15, floor=0.9017):
    fig, ax = plt.subplots(figsize=(10, 6))

    # Aggregate base single-type results from CSV rows
    by_N_base = defaultdict(list)
    for r in base_single_rows:
        if r.get("construction") != "single":
            continue
        try:
            N = int(r["N"])
            c = float(r["c"]) if r["c"] not in (None, "") else None
        except (ValueError, TypeError):
            continue
        if c is not None:
            by_N_base[N].append(c)
    base_xs = sorted(by_N_base)
    base_best = [min(by_N_base[N]) for N in base_xs]
    if base_xs:
        ax.plot(base_xs, base_best, "-", color="#888888", linewidth=1.5,
                label="library best (existing)", alpha=0.8)

    # New blocks — one line per source tag
    by_src = defaultdict(list)
    for r in new_single_results:
        by_src[r["source"]].append(r)
    cmap = plt.cm.tab10
    for i, (src, rs) in enumerate(sorted(by_src.items())):
        rs_sorted = sorted(rs, key=lambda r: r["N"])
        xs = [r["N"] for r in rs_sorted if r["c"] is not None]
        ys = [r["c"] for r in rs_sorted if r["c"] is not None]
        if xs:
            ax.plot(xs, ys, "-o", color=cmap(i), label=src, markersize=5, linewidth=2)

    # SAT-optimal
    if sat_opt:
        xs = sorted(sat_opt.keys())
        ys = [sat_opt[n]["c"] for n in xs]
        ax.plot(xs, ys, "--", color="red", label="SAT-optimal", linewidth=2)

    ax.axhline(random_baseline, linestyle=":", color="gray",
               label=f"random baseline ~{random_baseline:.2f}")
    ax.axhline(floor, linestyle="-.", color="purple", alpha=0.6,
               label=f"library floor = {floor:.4f}")

    ax.set_xlabel("N")
    ax.set_ylabel(r"$c = \alpha \cdot d_{\max} / (N \log d_{\max})$")
    ax.set_title("c vs N — library + large blocks")
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=8, loc="best")
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)


# =============================================================================
# Summary append
# =============================================================================

def append_summary(path, scan_new, sweep_new, paley_probe, sources, overall_floor,
                   new_best_c, sat_opt):
    """Append a `## Large Block Extension` section to summary.md."""
    lines = [
        "",
        "",
        "---",
        "",
        "# Large Block Extension",
        "",
        "Added large blocks to test whether the c=0.9017 asymptotic floor (set by",
        "the small-n library with |S| ≤ α and discrete (n,α,d)) can be broken.",
        "",
        "## Blocks added",
        "",
        "| source | block_id | n | α | d_max | edges | \\|S\\| | k* | is_triangle_free |",
        "|--------|----------|---|---|-------|-------|-----|----|------------------|",
    ]
    for rec, src in zip(scan_new, sources):
        edges = len(rec.get("edges", [])) if "edges" in rec else "—"
        # edges are not in scan record; infer from adj re-build if needed
        n_edges = rec.get("n_edges", "—")
        lines.append(
            f"| {src} | {rec['block_id']} | {rec['n']} | {rec['alpha']} | "
            f"{rec['d_max']} | {n_edges} | {rec['num_forced']} | "
            f"{rec.get('best_linear_k', 0)} | {int(rec['is_triangle_free'])} |"
        )

    # Paley prominent finding
    lines += [
        "",
        "## Paley P(17) — the headline",
        "",
    ]
    if paley_probe is not None:
        a1 = paley_probe["alpha_minus_any_vertex"]
        forced = paley_probe["any_vertex_forced"]
        lines += [
            f"- α(P(17)) = 3, d = 8, 8-regular, 68 edges.",
            f"- α(P(17) − v) = **{a1}** for any vertex v (by vertex-transitivity, this is uniform).",
            f"- Any vertex α-forced? **{forced}** ⇒ k* = "
            f"{'≥1' if forced else '0'}.",
            "",
        ]
        if not forced:
            lines += [
                "**Finding — construction cannot exploit Paley P(17).**",
                "",
                "With k*=0, the forced-matching construction emits zero cross-edges between",
                "copies of P(17); the resulting graph is just a disjoint union. This means",
                "the best strongly-regular K₄-free graph at its size class is *invisible*",
                "to this construction. Predicted asymptotic c = ∞ (no matching at all).",
                "",
                "Deeper cause: P(17) is vertex-transitive, so α(P(17) − v) is the same for",
                "every v. Since α = 3 < n = 17, at least one max IS must omit any given vertex,",
                "hence α(P(17) − v) = α = 3 for every v. No vertex is α-forced.",
                "",
            ]
        else:
            lines += [
                "Paley IS α-forced. See `large_blocks_results.json` for full probe data.",
                "",
            ]
        # Probe summary table
        lines += ["### Multi-vertex removal probe (random k-subsets)", "",
                  "| k | α − k (linear pred) | min observed | max observed | mean | hits predicted |",
                  "|---|---------------------|--------------|--------------|------|----------------|"]
        for k in sorted([int(key.split("=")[1]) for key in paley_probe if key.startswith("k=")]):
            info = paley_probe[f"k={k}"]
            lines.append(
                f"| {k} | {info['predicted_linear']} | {info['min']} | {info['max']} | "
                f"{info['mean']:.2f} | {info['num_hits_linear']}/{info['num_trials']} |"
            )
        lines.append("")

    # Per-block best c
    lines += [
        "## Per-block best c (new blocks)",
        "",
        "| source | best c achieved | N | α | d_max | k_copies |",
        "|--------|-----------------|---|---|-------|----------|",
    ]
    by_src = defaultdict(list)
    for r in sweep_new:
        by_src[r["source"]].append(r)
    for src in sorted(by_src):
        rs = [r for r in by_src[src] if r["c"] is not None]
        if not rs:
            lines.append(f"| {src} | — (no matching) | — | — | — | — |")
            continue
        best = min(rs, key=lambda r: r["c"])
        lines.append(
            f"| {src} | {best['c']:.4f} | {best['N']} | {best['actual_alpha']} | "
            f"{best['d_max']} | {best['k_copies']} |"
        )
    for src in sources:
        if src not in by_src:
            lines.append(f"| {src} | — (no forced vertices / no matching) | — | — | — | — |")

    # Floor comparison
    lines += [
        "",
        "## Did we break the c=0.9017 floor?",
        "",
    ]
    if new_best_c is not None and new_best_c < overall_floor:
        lines.append(f"**Yes.** Best new c = {new_best_c:.4f} < {overall_floor:.4f}.")
    else:
        bc_str = f"{new_best_c:.4f}" if new_best_c is not None else "—"
        lines.append(f"**No.** Best new c = {bc_str} ≥ {overall_floor:.4f}.")
    lines += ["", ""]

    with open(path, "a") as f:
        f.write("\n".join(lines))


# =============================================================================
# Main
# =============================================================================

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--trials-random", type=int, default=1000)
    parser.add_argument("--k-max", type=int, default=12)
    parser.add_argument("--sweep-timeout", type=int, default=180)
    parser.add_argument("--max-is", type=int, default=50000)
    parser.add_argument("--skip", nargs="*", default=[],
                        help="tags to skip: paley17, random_n10, random_n12, random_n16, pareto_n24")
    parser.add_argument("--random-seed", type=int, default=42)
    args = parser.parse_args()

    t0 = time.time()
    print("=" * 60)
    print("Forced-Matching Extension — Large Blocks")
    print("=" * 60)

    # --- Build new blocks ---
    new_blocks = []
    block_log = []  # for JSON

    def _consider(tag, adj_builder):
        if tag in args.skip:
            print(f"  [{tag}] skipped")
            return None
        try:
            adj = adj_builder()
        except Exception as e:
            print(f"  [{tag}] ERROR building adj: {e}")
            return None
        return adj

    # Paley P(17)
    adj = _consider("paley17", paley_graph_17)
    if adj is not None:
        block = adj_to_block(adj, 10000, "paley17", max_is=args.max_is)
        new_blocks.append(block)
        block_log.append({"source": "paley17", "n": 17, "alpha": 3, "d_max": 8,
                          "edges": len(block["edges"])})

    # Random K4-free at n = 10, 12, 16
    for i, n in enumerate([10, 12, 16]):
        tag = f"random_n{n}"
        if tag in args.skip:
            print(f"  [{tag}] skipped")
            continue
        print(f"\n[{tag}] generating {args.trials_random} random K4-free graphs...")
        seed = args.random_seed + i
        adj, info = generate_random_k4free(n, args.trials_random, seed=seed, verbose=True)
        print(f"  best α={info['best_alpha']} d_max={info['best_d_max']}")
        block = adj_to_block(adj, 10001 + i, tag, alpha=info["best_alpha"],
                             max_is=args.max_is)
        new_blocks.append(block)
        block_log.append({"source": tag, "n": n, "alpha": info["best_alpha"],
                          "d_max": info["best_d_max"],
                          "edges": len(block["edges"]),
                          "search_info": info})

    # Pareto n=24
    if "pareto_n24" not in args.skip:
        print("\n[pareto_n24] loading from SAT pareto frontier...")
        try:
            adj, entry = load_min_alpha_n24()
            block = adj_to_block(adj, 10004, "pareto_n24",
                                 alpha=entry["alpha"], max_is=args.max_is)
            new_blocks.append(block)
            block_log.append({"source": "pareto_n24", "n": 24,
                              "alpha": entry["alpha"],
                              "d_max": entry["d_max"],
                              "edges": len(block["edges"])})
        except Exception as e:
            print(f"  ERROR loading pareto_n24: {e}")

    # --- Scan new blocks ---
    print("\n" + "=" * 60)
    print("Scanning new blocks for α-forced vertices + linear-drop capacity")
    print("=" * 60)
    # scan_blocks calls linear_drop_capacity with max_check=min(6, len(forced))
    scan_recs = scan_blocks(new_blocks, compute_linearity=True, max_check=6)
    # Also stash source tag and edge count per record
    for rec, blk in zip(scan_recs, new_blocks):
        rec["source"] = blk["source"]
        rec["n_edges"] = len(blk["edges"])
    for rec in scan_recs:
        print(f"  {rec['source']:14s} n={rec['n']:2d} α={rec['alpha']} d={rec['d_max']:2d} "
              f"|S|={rec['num_forced']:3d} k*={rec.get('best_linear_k', 0)} "
              f"triangle-free={rec['is_triangle_free']}")

    # --- Paley linear-drop probe (empirical, independent of scan_blocks) ---
    paley_probe = None
    for blk in new_blocks:
        if blk["source"] == "paley17":
            print("\n[paley17] Running dedicated linear-drop probe...")
            paley_adj = block_to_adj(blk)
            paley_probe = paley_linear_probe(paley_adj, blk["alpha"],
                                             num_trials=30, seed=0)
            print(f"  α(P(17) - v) for any v = {paley_probe['alpha_minus_any_vertex']} "
                  f"(α-1 would be {blk['alpha']-1})")
            print(f"  Any vertex α-forced? {paley_probe['any_vertex_forced']}")

    # --- Single-type sweep k=2..k_max ---
    print("\n" + "=" * 60)
    print("Single-type sweep (SAT-verified α)")
    print("=" * 60)
    sweep_results = []
    for blk, rec in zip(new_blocks, scan_recs):
        print(f"\n[{blk['source']}] sweeping k=2..{args.k_max}...")
        if rec["num_forced"] == 0 or rec.get("best_linear_k", 0) == 0:
            print("  skipped (no α-forced vertices / k*=0 ⇒ no legal matching)")
            continue
        # Inject scan-derived fields expected by max_forced_matching
        blk2 = dict(blk)
        blk2["forced"] = rec["forced"]
        blk2["forced_degrees"] = rec["forced_degrees"]
        blk2["linear_witness"] = rec["linear_witness"]
        blk2["best_linear_k"] = rec["best_linear_k"]
        t_sweep = time.time()
        series = evaluate_single_type_sweep(blk2, args.k_max,
                                            timeout=args.sweep_timeout,
                                            verify_alpha=True,
                                            use_linear_witness=True)
        for r in series:
            r["source"] = blk["source"]
        sweep_results.extend(series)
        best = min((r for r in series if r["c"] is not None),
                   key=lambda r: r["c"], default=None)
        if best:
            print(f"  [{blk['source']}] best: k={best['k_copies']} N={best['N']} "
                  f"c={best['c']} α={best['actual_alpha']} (pred {best['predicted_alpha']}) "
                  f"d={best['d_max']} gap={best['alpha_gap']} "
                  f"(sweep {time.time()-t_sweep:.1f}s)")
        else:
            print(f"  [{blk['source']}] no usable results")

    # --- Append to CSVs ---
    print("\n" + "=" * 60)
    print("Appending to CSVs")
    print("=" * 60)
    # block_scan
    existing_scan, scan_src = _read_existing_csv(
        [SCAN_CSV, SCAN_TXT, SCAN_TXT2], SCAN_COLS)
    new_scan_rows = [scan_rec_to_csvrow(r, r.get("source", "")) for r in scan_recs]
    # dedupe: drop any existing row whose block_id matches a new block_id
    new_ids = {str(r["block_id"]) for r in new_scan_rows}
    existing_scan = [r for r in existing_scan if str(r.get("block_id", "")) not in new_ids]
    combined_scan = existing_scan + new_scan_rows
    _write_csv(SCAN_CSV, combined_scan, SCAN_COLS)
    print(f"  Wrote {SCAN_CSV} ({len(existing_scan)} existing + {len(new_scan_rows)} new rows; source={scan_src})")

    # construction_results
    existing_cons, cons_src = _read_existing_csv(
        [CONS_CSV, CONS_TXT], CONS_COLS)
    new_cons_rows = [sweep_rec_to_csvrow(r, r["source"]) for r in sweep_results]
    combined_cons = existing_cons + new_cons_rows
    _write_csv(CONS_CSV, combined_cons, CONS_COLS)
    print(f"  Wrote {CONS_CSV} ({len(existing_cons)} existing + {len(new_cons_rows)} new rows; source={cons_src})")

    # --- Regenerate plots ---
    print("\n" + "=" * 60)
    print("Regenerating plots")
    print("=" * 60)

    # block_best_c combines existing (from cons CSV) with new sweep results
    block_best_c = {}
    for r in existing_cons:
        if r.get("construction") != "single":
            continue
        try:
            bid = int(r["block_ids"])
            c = float(r["c"]) if r["c"] not in ("", None) else None
        except (ValueError, TypeError):
            continue
        if c is None:
            continue
        if bid not in block_best_c or c < block_best_c[bid]:
            block_best_c[bid] = c
    for r in sweep_results:
        bid = r["block_id"]
        if r["c"] is None:
            continue
        if bid not in block_best_c or r["c"] < block_best_c[bid]:
            block_best_c[bid] = r["c"]

    plot_tradeoff_overlay(existing_scan, scan_recs, block_best_c,
                          os.path.join(OUTDIR, "tradeoff_plot.png"))
    print("  Wrote tradeoff_plot.png")

    sat_opt = load_sat_optimal_map(max_n=35)
    plot_c_vs_n_overlay(existing_cons, sweep_results, sat_opt,
                        os.path.join(OUTDIR, "c_vs_N.png"),
                        random_baseline=1.15, floor=0.9017)
    print("  Wrote c_vs_N.png")

    # --- Append summary ---
    print("\n" + "=" * 60)
    print("Updating summary.md")
    print("=" * 60)
    sources = [blk["source"] for blk in new_blocks]
    new_best = None
    for r in sweep_results:
        if r["c"] is not None and (new_best is None or r["c"] < new_best):
            new_best = r["c"]
    append_summary(os.path.join(OUTDIR, "summary.md"), scan_recs, sweep_results,
                   paley_probe, sources, 0.9017, new_best, sat_opt)
    print("  Appended `## Large Block Extension` section to summary.md")

    # --- Dump full JSON ---
    dump = {
        "runtime_seconds": round(time.time() - t0, 2),
        "args": vars(args),
        "new_blocks_info": block_log,
        "scan": [
            {k: v for k, v in rec.items() if k != "edges"}
            for rec in scan_recs
        ],
        "sweep": sweep_results,
        "paley_probe": paley_probe,
        "new_best_c": new_best,
        "floor": 0.9017,
    }
    dump_path = os.path.join(OUTDIR, "large_blocks_results.json")
    with open(dump_path, "w") as f:
        json.dump(dump, f, indent=2, default=str)
    print(f"  Wrote {dump_path}")

    print(f"\nDone in {time.time()-t0:.1f}s. "
          f"New best c = {new_best if new_best is not None else 'N/A'} "
          f"(floor = 0.9017).")


if __name__ == "__main__":
    main()
