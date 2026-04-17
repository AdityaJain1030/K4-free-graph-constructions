#!/usr/bin/env python3
"""
Barrier Analysis: structural invariants separating SAT-optimal ridge graphs
from heuristic-generated basin graphs.

Ridge set: for each N in 12..35, take the minimum-c graph on the SAT
pareto frontier (SAT/k4free_ilp/results/pareto_n{N}.json). Plus P(17) from
forced_matching/large_blocks_results.json (block_id 10000).

Basin set: forced-matching constructions (experiments/forced_matching/
construction_results.csv) and the baselines sweep graphs
(experiments/baselines/graphs/*.edgelist) if present.

For every graph we compute a battery of structural features, compare ridge
vs basin distributions per N, rank features by discriminative power, and
identify barrier thresholds.

Usage:
    micromamba run -n funsearch python experiments/barrier_analysis/run_experiment.py
"""

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
import networkx as nx
from scipy.stats import mannwhitneyu

sys.stdout.reconfigure(line_buffering=True)

_HERE = os.path.dirname(os.path.abspath(__file__))
_EXPERIMENTS = os.path.join(_HERE, "..")
_ROOT = os.path.normpath(os.path.join(_HERE, "..", ".."))
PARETO_DIR = os.path.normpath(os.path.join(_ROOT, "..", "SAT", "k4free_ilp", "results"))
FM_DIR = os.path.join(_EXPERIMENTS, "forced_matching")
BASELINES_DIR = os.path.join(_EXPERIMENTS, "baselines")
OUTDIR = _HERE


# --- reuse utilities from block_decomposition ---
def _load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_bd = _load_module(
    "block_decomp",
    os.path.join(_EXPERIMENTS, "block_decomposition", "run_experiment.py"),
)
alpha_exact = _bd.alpha_exact
alpha_sat = _bd.alpha_sat
is_k4_free = _bd.is_k4_free
graph6_to_adj = _bd.graph6_to_adj
compute_c_value = _bd.compute_c_value


# ===========================================================================
# Graph loaders
# ===========================================================================

def edges_to_adj(n, edges):
    adj = np.zeros((n, n), dtype=np.bool_)
    for u, v in edges:
        adj[u, v] = adj[v, u] = True
    return adj


def load_ridge_graphs(n_range=range(12, 36)):
    """Min c_log graph from each pareto_n{N}.json, plus P(17)."""
    graphs = []
    for N in n_range:
        path = os.path.join(PARETO_DIR, f"pareto_n{N}.json")
        if not os.path.isfile(path):
            continue
        with open(path) as f:
            data = json.load(f)
        frontier = [e for e in data.get("pareto_frontier", [])
                    if e.get("c_log") is not None and e.get("edges")]
        if not frontier:
            continue
        best = min(frontier, key=lambda e: e["c_log"])
        adj = edges_to_adj(N, best["edges"])
        graphs.append({
            "source": "ridge",
            "label": f"pareto_n{N}",
            "N": N,
            "adj": adj,
            "alpha_loaded": int(best["alpha"]),
            "d_max_loaded": int(best["d_max"]),
            "c_loaded": float(best["c_log"]),
        })
    # P(17) from large_blocks_results.json
    lb_path = os.path.join(FM_DIR, "large_blocks_results.json")
    if os.path.isfile(lb_path):
        with open(lb_path) as f:
            lb = json.load(f)
        for rec in lb.get("scan", []):
            if rec.get("block_id") == 10000:
                adj = graph6_to_adj(rec["g6"])
                graphs.append({
                    "source": "ridge",
                    "label": "paley17",
                    "N": adj.shape[0],
                    "adj": adj,
                    "alpha_loaded": int(rec["alpha"]),
                    "d_max_loaded": int(rec["d_max"]),
                    "c_loaded": None,
                })
                break
    return graphs


def load_basin_forced_matching():
    """Load all forced-matching constructions from construction_results.csv."""
    graphs = []
    path = os.path.join(FM_DIR, "construction_results.csv")
    if not os.path.isfile(path):
        return graphs
    with open(path) as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            g6 = row.get("g6", "").strip()
            if not g6:
                continue
            try:
                adj = graph6_to_adj(g6)
            except Exception:
                continue
            graphs.append({
                "source": "basin",
                "label": f"fm_{row.get('construction', '')}_{i}",
                "N": adj.shape[0],
                "adj": adj,
                "alpha_loaded": int(row["actual_alpha"]) if row.get("actual_alpha") else None,
                "d_max_loaded": int(row["d_max"]) if row.get("d_max") else None,
                "c_loaded": float(row["c"]) if row.get("c") else None,
            })
    return graphs


def load_basin_baselines():
    gdir = os.path.join(BASELINES_DIR, "graphs")
    graphs = []
    if not os.path.isdir(gdir):
        return graphs
    for fn in sorted(os.listdir(gdir)):
        if not fn.endswith(".edgelist"):
            continue
        path = os.path.join(gdir, fn)
        # parse filename: method1_N012.edgelist
        stem = fn[:-len(".edgelist")]
        try:
            method, npart = stem.split("_N")
            N = int(npart)
        except Exception:
            continue
        edges = []
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.replace(",", " ").split()
                if len(parts) < 2:
                    continue
                try:
                    u, v = int(parts[0]), int(parts[1])
                except ValueError:
                    continue
                if u == v:
                    continue
                edges.append((u, v))
        if not edges:
            continue
        max_v = max(max(u, v) for u, v in edges)
        if max_v + 1 > N:
            N = max_v + 1
        adj = edges_to_adj(N, edges)
        graphs.append({
            "source": "basin",
            "label": f"baseline_{method}_N{N}",
            "N": N,
            "adj": adj,
            "alpha_loaded": None,
            "d_max_loaded": None,
            "c_loaded": None,
        })
    return graphs


def random_k4free(N, d_cap=6, rng=None):
    """Random K4-free graph via edge-addition respecting a degree cap."""
    if rng is None:
        rng = random.Random()
    adj = np.zeros((N, N), dtype=np.bool_)
    deg = np.zeros(N, dtype=int)
    pairs = [(i, j) for i in range(N) for j in range(i + 1, N)]
    rng.shuffle(pairs)
    # bitmask neighbor set
    nbr = [0] * N
    for u, v in pairs:
        if deg[u] >= d_cap or deg[v] >= d_cap:
            continue
        # K4 check: does the edge (u,v) complete a K4?
        # A K4 containing {u,v} needs two vertices in N(u) ∩ N(v) that are adjacent.
        common = nbr[u] & nbr[v]
        has_k4 = False
        c = common
        while c:
            w = (c & -c).bit_length() - 1
            c &= c - 1
            if nbr[w] & (common & ~(1 << w)):
                has_k4 = True
                break
        if has_k4:
            continue
        adj[u, v] = adj[v, u] = True
        deg[u] += 1
        deg[v] += 1
        nbr[u] |= 1 << v
        nbr[v] |= 1 << u
    return adj


def generate_basin_random(Ns=(12, 16, 20, 24, 28, 32), per_N=20, d_cap=6, seed=42):
    rng = random.Random(seed)
    graphs = []
    for N in Ns:
        for i in range(per_N):
            adj = random_k4free(N, d_cap=d_cap, rng=rng)
            graphs.append({
                "source": "basin",
                "label": f"random_d{d_cap}_N{N}_{i}",
                "N": N,
                "adj": adj,
                "alpha_loaded": None,
                "d_max_loaded": None,
                "c_loaded": None,
            })
    return graphs


# ===========================================================================
# Structural features
# ===========================================================================

def degree_stats(adj):
    deg = adj.sum(axis=1).astype(int)
    d_max = int(deg.max()) if deg.size else 0
    d_min = int(deg.min()) if deg.size else 0
    d_mean = float(deg.mean()) if deg.size else 0.0
    d_var = float(deg.var()) if deg.size else 0.0
    d_range = d_max - d_min
    regularity = 1.0 - (d_range / d_mean) if d_mean > 0 else 0.0
    return {
        "d_max": d_max,
        "d_min": d_min,
        "d_mean": d_mean,
        "d_var": d_var,
        "d_range": d_range,
        "regularity": regularity,
        "degree_sequence": sorted(deg.tolist(), reverse=True),
    }


def triangle_stats(adj):
    n = adj.shape[0]
    nbr = [0] * n
    for i in range(n):
        for j in range(n):
            if adj[i, j]:
                nbr[i] |= 1 << j
    tri_per_v = [0] * n
    total = 0
    for a in range(n):
        for b in range(a + 1, n):
            if not adj[a, b]:
                continue
            common = nbr[a] & nbr[b]
            while common:
                c = (common & -common).bit_length() - 1
                common &= common - 1
                if c > b:
                    total += 1
                    tri_per_v[a] += 1
                    tri_per_v[b] += 1
                    tri_per_v[c] += 1
    edges = int(adj.sum() // 2)
    # max possible triangles given m edges: bounded by m/3 for K4-free? Use m/3 as a soft density.
    max_possible = max(1, edges // 3)
    return {
        "triangles_total": total,
        "triangle_var": float(np.var(tri_per_v)) if tri_per_v else 0.0,
        "triangle_density": total / max_possible,
    }


def neighborhood_alpha_stats(adj):
    """For each v, α of subgraph induced on N(v). K4-free ⇒ N(v) is triangle-free.
    Uses exact bitmask IS for d(v) ≤ 18, greedy otherwise."""
    n = adj.shape[0]
    vals = []
    for v in range(n):
        nbrs = np.where(adj[v])[0]
        d = len(nbrs)
        if d == 0:
            vals.append(0)
            continue
        sub = adj[np.ix_(nbrs, nbrs)]
        if d <= 18:
            a, _ = alpha_exact(sub)
        else:
            a = _greedy_is(sub)
        vals.append(int(a))
    degs = adj.sum(axis=1).astype(int)
    mean_d = float(degs.mean()) if n else 0.0
    mean_a = float(np.mean(vals)) if vals else 0.0
    return {
        "nbhd_alpha_min": int(min(vals)) if vals else 0,
        "nbhd_alpha_max": int(max(vals)) if vals else 0,
        "nbhd_alpha_mean": mean_a,
        "nbhd_alpha_var": float(np.var(vals)) if vals else 0.0,
        "nbhd_alpha_ratio": (mean_a / mean_d) if mean_d > 0 else 0.0,
    }


def _greedy_is(adj):
    n = adj.shape[0]
    order = np.argsort(adj.sum(axis=1))  # low-degree first
    used = np.zeros(n, dtype=bool)
    blocked = np.zeros(n, dtype=bool)
    count = 0
    for v in order:
        if blocked[v]:
            continue
        used[v] = True
        count += 1
        blocked |= adj[v]
        blocked[v] = True
    return count


def spectral_stats(adj):
    n = adj.shape[0]
    if n == 0:
        return {"spectral_radius": 0.0, "spectral_gap": 0.0, "algebraic_connectivity": 0.0}
    A = adj.astype(np.float64)
    eig_a = np.linalg.eigvalsh(A)
    eig_a_sorted = np.sort(eig_a)[::-1]
    lam1 = float(eig_a_sorted[0])
    lam2 = float(eig_a_sorted[1]) if n > 1 else lam1
    spectral_gap = lam1 - lam2
    deg = adj.sum(axis=1).astype(np.float64)
    L = np.diag(deg) - A
    eig_l = np.linalg.eigvalsh(L)
    eig_l_sorted = np.sort(eig_l)
    alg_conn = float(eig_l_sorted[1]) if n > 1 else 0.0
    return {
        "spectral_radius": lam1,
        "spectral_gap": spectral_gap,
        "algebraic_connectivity": alg_conn,
    }


def connectivity_stats(adj, n_samples=1000, seed=0):
    n = adj.shape[0]
    G = nx.from_numpy_array(adj.astype(int))
    if not nx.is_connected(G):
        edge_conn = 0
        vert_conn = 0
        avg_spl = float("inf")
    else:
        edge_conn = nx.edge_connectivity(G)
        vert_conn = nx.node_connectivity(G)
        avg_spl = nx.average_shortest_path_length(G)

    # Cheeger: min |∂S|/|S| over |S| ≤ n/2 (non-empty)
    best = float("inf")
    half = n // 2
    if n <= 20:
        # exhaustive over sizes
        for size in range(1, half + 1):
            # if too many subsets, sample
            total = math.comb(n, size)
            if total > 5000:
                rng = random.Random(seed + size)
                for _ in range(2000):
                    S = tuple(rng.sample(range(n), size))
                    b = _boundary(adj, S)
                    best = min(best, b / size)
            else:
                import itertools
                for S in itertools.combinations(range(n), size):
                    b = _boundary(adj, S)
                    best = min(best, b / size)
                    if best == 0:
                        break
            if best == 0:
                break
    else:
        rng = random.Random(seed)
        for _ in range(n_samples):
            size = rng.randint(1, max(1, half))
            S = rng.sample(range(n), size)
            b = _boundary(adj, S)
            best = min(best, b / size)

    return {
        "edge_connectivity": int(edge_conn),
        "vertex_connectivity": int(vert_conn),
        "cheeger_approx": float(best) if math.isfinite(best) else float("inf"),
        "avg_shortest_path": float(avg_spl) if math.isfinite(avg_spl) else float("inf"),
    }


def _boundary(adj, S):
    mask = np.zeros(adj.shape[0], dtype=bool)
    for v in S:
        mask[v] = True
    # edges from S to V\S
    sub = adj[np.ix_(list(S), ~mask)]
    return int(sub.sum())


def independence_stats(adj, max_is_cap=10000):
    """Enumerate IS via backtracking, count max ISes, compute IS diversity."""
    n = adj.shape[0]
    nbr = [0] * n
    for i in range(n):
        for j in range(n):
            if adj[i, j]:
                nbr[i] |= 1 << j

    alpha_found = [0]
    is_list = []
    capped = [False]

    def backtrack(v, cur, size, forbidden):
        if capped[0]:
            return
        if size > alpha_found[0]:
            alpha_found[0] = size
            is_list.clear()
            is_list.append(cur)
        elif size == alpha_found[0] and size > 0:
            if len(is_list) >= max_is_cap:
                capped[0] = True
                return
            is_list.append(cur)
        # upper bound: size + count of candidate bits
        remaining = 0
        f = forbidden
        for u in range(v, n):
            if not (f & (1 << u)):
                remaining += 1
        if size + remaining < alpha_found[0]:
            return
        for u in range(v, n):
            if not (forbidden & (1 << u)):
                backtrack(u + 1, cur | (1 << u), size + 1, forbidden | nbr[u] | (1 << u))
                if capped[0]:
                    return

    backtrack(0, 0, 0, 0)
    alpha = alpha_found[0]
    count = len(is_list) if not capped[0] else max_is_cap
    count_repr = count if not capped[0] else f">{max_is_cap}"

    # IS diversity: fraction of vertices that appear in at least one max IS
    covered = 0
    for ismask in is_list:
        covered |= ismask
    vertices_in_some_max_is = bin(covered).count("1")
    diversity = vertices_in_some_max_is / n if n else 0.0

    return alpha, {
        "alpha": int(alpha),
        "alpha_ratio": alpha / n if n else 0.0,
        "num_max_is": count_repr,
        "num_max_is_numeric": count,
        "is_diversity": diversity,
    }


# ===========================================================================
# Feature pipeline
# ===========================================================================

def compute_all_features(graph_rec):
    adj = graph_rec["adj"]
    N = adj.shape[0]
    feats = {"source": graph_rec["source"], "label": graph_rec["label"], "N": N}

    # k4-free sanity
    feats["is_k4_free"] = bool(is_k4_free(adj))

    deg = degree_stats(adj)
    feats.update({k: v for k, v in deg.items() if k != "degree_sequence"})

    tri = triangle_stats(adj)
    feats.update(tri)

    nb = neighborhood_alpha_stats(adj)
    feats.update(nb)

    sp = spectral_stats(adj)
    feats.update(sp)

    con = connectivity_stats(adj)
    feats.update(con)

    alpha, is_stats = independence_stats(adj)
    feats.update(is_stats)

    d_max = feats["d_max"]
    feats["c"] = float(compute_c_value(alpha, N, d_max)) if d_max > 1 else float("inf")
    return feats


# ===========================================================================
# Analysis: ridge vs basin comparison
# ===========================================================================

# features we treat as numeric barrier candidates
BARRIER_FEATURES = [
    "d_max", "d_min", "d_mean", "d_var", "d_range", "regularity",
    "triangles_total", "triangle_var", "triangle_density",
    "nbhd_alpha_min", "nbhd_alpha_max", "nbhd_alpha_mean",
    "nbhd_alpha_var", "nbhd_alpha_ratio",
    "spectral_radius", "spectral_gap", "algebraic_connectivity",
    "edge_connectivity", "vertex_connectivity", "cheeger_approx",
    "avg_shortest_path",
    "alpha", "alpha_ratio", "num_max_is_numeric", "is_diversity",
]


def feature_comparison(feature_rows):
    """Per-(feature, N), compute ridge/basin mean, std, MW-U p, effect size."""
    by_source = defaultdict(lambda: defaultdict(list))  # source -> N -> [rows]
    for r in feature_rows:
        by_source[r["source"]][r["N"]].append(r)

    comparisons = []
    ridge_Ns = set(by_source["ridge"].keys())
    basin_Ns = set(by_source["basin"].keys())
    shared = sorted(ridge_Ns & basin_Ns)

    for feat in BARRIER_FEATURES:
        for N in shared:
            ridge_vals = [r.get(feat) for r in by_source["ridge"][N]
                          if isinstance(r.get(feat), (int, float)) and math.isfinite(r.get(feat))]
            basin_vals = [r.get(feat) for r in by_source["basin"][N]
                          if isinstance(r.get(feat), (int, float)) and math.isfinite(r.get(feat))]
            if len(ridge_vals) < 1 or len(basin_vals) < 1:
                continue
            r_mean = float(np.mean(ridge_vals))
            r_std = float(np.std(ridge_vals))
            b_mean = float(np.mean(basin_vals))
            b_std = float(np.std(basin_vals))
            pooled = math.sqrt((r_std ** 2 + b_std ** 2) / 2) or 1e-9
            eff = (r_mean - b_mean) / pooled
            # MW-U requires at least 1 sample each
            p_val = float("nan")
            try:
                if len(set(ridge_vals + basin_vals)) > 1:
                    _, p_val = mannwhitneyu(ridge_vals, basin_vals, alternative="two-sided")
            except Exception:
                pass
            comparisons.append({
                "feature": feat,
                "N": N,
                "n_ridge": len(ridge_vals),
                "n_basin": len(basin_vals),
                "ridge_mean": r_mean,
                "ridge_std": r_std,
                "basin_mean": b_mean,
                "basin_std": b_std,
                "effect_size": eff,
                "abs_effect_size": abs(eff),
                "p_value": p_val,
            })
    return comparisons


def rank_features(comparisons):
    by_feat = defaultdict(list)
    for c in comparisons:
        by_feat[c["feature"]].append(c)
    ranked = []
    for feat, rows in by_feat.items():
        abs_eff = [r["abs_effect_size"] for r in rows
                   if math.isfinite(r["abs_effect_size"])]
        nl_p = [-math.log10(max(r["p_value"], 1e-30)) for r in rows
                if math.isfinite(r["p_value"])]
        if not abs_eff:
            continue
        ranked.append({
            "feature": feat,
            "mean_abs_effect": float(np.mean(abs_eff)),
            "mean_neg_log_p": float(np.mean(nl_p)) if nl_p else 0.0,
            "n_ns": len(rows),
        })
    ranked.sort(key=lambda x: (x["mean_abs_effect"] + 0.1 * x["mean_neg_log_p"]),
                reverse=True)
    return ranked


# ===========================================================================
# Thresholds
# ===========================================================================

def find_threshold(ridge_vals, basin_vals):
    """Pick the scalar threshold on the value axis that maximizes accuracy.
    Returns (threshold, direction, accuracy, fpr, fnr). direction ∈ {'<=','>='}
    meaning ridge is predicted when value <direction> threshold.
    """
    all_vals = sorted(set(ridge_vals + basin_vals))
    best = None
    for direction in ("<=", ">="):
        for t in all_vals:
            if direction == "<=":
                r_correct = sum(1 for v in ridge_vals if v <= t)
                b_correct = sum(1 for v in basin_vals if v > t)
            else:
                r_correct = sum(1 for v in ridge_vals if v >= t)
                b_correct = sum(1 for v in basin_vals if v < t)
            total = len(ridge_vals) + len(basin_vals)
            acc = (r_correct + b_correct) / total if total else 0
            fpr = (len(basin_vals) - b_correct) / len(basin_vals) if basin_vals else 0
            fnr = (len(ridge_vals) - r_correct) / len(ridge_vals) if ridge_vals else 0
            score = (acc, -(fpr + fnr))
            if best is None or score > best[0]:
                best = (score, t, direction, acc, fpr, fnr)
    _, t, direction, acc, fpr, fnr = best
    return {
        "threshold": float(t),
        "direction": direction,
        "accuracy": float(acc),
        "fpr": float(fpr),
        "fnr": float(fnr),
    }


# ===========================================================================
# Plots
# ===========================================================================

def scatter_plot(feature_rows, feat, out_path):
    ridge = [(r[feat], r["c"]) for r in feature_rows
             if r["source"] == "ridge" and isinstance(r.get(feat), (int, float))
             and isinstance(r.get("c"), float) and math.isfinite(r["c"])
             and math.isfinite(r[feat])]
    basin = [(r[feat], r["c"]) for r in feature_rows
             if r["source"] == "basin" and isinstance(r.get(feat), (int, float))
             and isinstance(r.get("c"), float) and math.isfinite(r["c"])
             and math.isfinite(r[feat])]
    fig, ax = plt.subplots(figsize=(8, 5))
    if basin:
        bx, by = zip(*basin)
        ax.scatter(bx, by, color="gray", alpha=0.5, s=20, label=f"basin (n={len(basin)})")
    if ridge:
        rx, ry = zip(*ridge)
        ax.scatter(rx, ry, color="red", alpha=0.9, s=40, label=f"ridge (n={len(ridge)})",
                   edgecolors="black", linewidths=0.4)
    ax.set_xlabel(feat)
    ax.set_ylabel("c = α·d_max / (N·ln d_max)")
    ax.set_title(f"Barrier candidate: {feat}")
    ax.grid(alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)


def pair_plot(feature_rows, f1, f2, out_path):
    pts = []
    for r in feature_rows:
        v1 = r.get(f1)
        v2 = r.get(f2)
        c = r.get("c")
        if not (isinstance(v1, (int, float)) and isinstance(v2, (int, float))
                and isinstance(c, float)):
            continue
        if not (math.isfinite(v1) and math.isfinite(v2) and math.isfinite(c)):
            continue
        pts.append((v1, v2, c, r["source"]))
    fig, ax = plt.subplots(figsize=(8, 6))
    basin_pts = [p for p in pts if p[3] == "basin"]
    ridge_pts = [p for p in pts if p[3] == "ridge"]
    if basin_pts:
        xs = [p[0] for p in basin_pts]
        ys = [p[1] for p in basin_pts]
        cs = [p[2] for p in basin_pts]
        sc = ax.scatter(xs, ys, c=cs, cmap="viridis_r", s=30, alpha=0.6,
                        marker="o", edgecolors="gray", linewidths=0.2,
                        label=f"basin (n={len(basin_pts)})")
        cb = plt.colorbar(sc, ax=ax)
        cb.set_label("c")
    if ridge_pts:
        xs = [p[0] for p in ridge_pts]
        ys = [p[1] for p in ridge_pts]
        ax.scatter(xs, ys, color="red", s=70, edgecolors="black",
                   linewidths=0.8, marker="*", label=f"ridge (n={len(ridge_pts)})")
    ax.set_xlabel(f1)
    ax.set_ylabel(f2)
    ax.set_title(f"Ridge vs basin: {f1} vs {f2}")
    ax.grid(alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)


# ===========================================================================
# Main
# ===========================================================================

def main():
    os.makedirs(OUTDIR, exist_ok=True)
    t0 = time.time()

    print("Loading ridge graphs (SAT-optimal)...")
    ridge = load_ridge_graphs()
    print(f"  {len(ridge)} ridge graphs")

    print("Loading basin graphs (forced-matching constructions)...")
    fm = load_basin_forced_matching()
    print(f"  {len(fm)} forced-matching graphs")

    print("Loading basin graphs (baseline sweep)...")
    bl = load_basin_baselines()
    print(f"  {len(bl)} baseline graphs")

    basin = fm + bl
    if not basin:
        print("No basin output found; generating random K4-free basin sample...")
        basin = generate_basin_random()
        print(f"  {len(basin)} random K4-free graphs generated")

    all_graphs = ridge + basin
    print(f"\nTotal: {len(all_graphs)} graphs. Computing features...")

    feature_rows = []
    verified_k4_free = 0
    for i, g in enumerate(all_graphs):
        try:
            feats = compute_all_features(g)
        except Exception as e:
            print(f"  [{i}] failed on {g['label']}: {e}")
            continue
        feats["label"] = g["label"]
        feats["source"] = g["source"]
        feats["N"] = g["N"]
        if feats.get("is_k4_free"):
            verified_k4_free += 1
        feature_rows.append(feats)
        if (i + 1) % 20 == 0 or i == len(all_graphs) - 1:
            print(f"  [{i+1}/{len(all_graphs)}] elapsed {time.time()-t0:.1f}s")

    print(f"\nK4-free verified: {verified_k4_free}/{len(feature_rows)}")

    # --- Save all features ---
    all_feat_columns = ["source", "label", "N", "c", "is_k4_free"] + BARRIER_FEATURES + ["num_max_is"]
    csv_path = os.path.join(OUTDIR, "all_graphs_features.csv")
    with open(csv_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(all_feat_columns)
        for r in feature_rows:
            w.writerow([r.get(col, "") for col in all_feat_columns])
    print(f"  Wrote {csv_path}")

    # --- Comparisons ---
    print("\nRidge vs basin feature comparison...")
    comparisons = feature_comparison(feature_rows)
    comp_path = os.path.join(OUTDIR, "feature_comparison.csv")
    with open(comp_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["feature", "N", "n_ridge", "n_basin",
                    "ridge_mean", "ridge_std", "basin_mean", "basin_std",
                    "effect_size", "abs_effect_size", "p_value"])
        for c in comparisons:
            w.writerow([c["feature"], c["N"], c["n_ridge"], c["n_basin"],
                        f"{c['ridge_mean']:.4g}", f"{c['ridge_std']:.4g}",
                        f"{c['basin_mean']:.4g}", f"{c['basin_std']:.4g}",
                        f"{c['effect_size']:.4g}", f"{c['abs_effect_size']:.4g}",
                        f"{c['p_value']:.4g}"])
    print(f"  Wrote {comp_path}")

    # --- Ranking ---
    ranked = rank_features(comparisons)
    rank_md = os.path.join(OUTDIR, "feature_ranking.md")
    with open(rank_md, "w") as f:
        f.write("# Feature ranking by ridge/basin discriminative power\n\n")
        f.write("Rank key: mean absolute effect size (Cohen's d, averaged across N),\n")
        f.write("with 0.1 × mean -log10(p) as a tiebreak.\n\n")
        f.write("| # | feature | mean |Cohen d| | mean -log10 p | #N |\n")
        f.write("|---|---------|--------------|----------------|-----|\n")
        for i, r in enumerate(ranked, 1):
            f.write(f"| {i} | {r['feature']} | {r['mean_abs_effect']:.3f} | "
                    f"{r['mean_neg_log_p']:.2f} | {r['n_ns']} |\n")
    print(f"  Wrote {rank_md}")

    top5 = [r["feature"] for r in ranked[:5]]
    top3 = top5[:3]
    print(f"\nTop-5 discriminating features: {top5}")

    # --- Scatter plots for top 5 ---
    for feat in top5:
        out = os.path.join(OUTDIR, f"barrier_{feat}.png")
        scatter_plot(feature_rows, feat, out)
    print(f"  Wrote {len(top5)} barrier scatter plots")

    # --- Pair plots for top 3 ---
    pairs = [(top3[0], top3[1]), (top3[0], top3[2]), (top3[1], top3[2])] if len(top3) >= 3 else []
    for f1, f2 in pairs:
        out = os.path.join(OUTDIR, f"pair_{f1}_{f2}.png")
        pair_plot(feature_rows, f1, f2, out)
    print(f"  Wrote {len(pairs)} pair plots")

    # --- Thresholds for top 3 (pooled across all N) ---
    thresholds = {}
    for feat in top3:
        ridge_vals = [r[feat] for r in feature_rows
                      if r["source"] == "ridge" and isinstance(r.get(feat), (int, float))
                      and math.isfinite(r[feat])]
        basin_vals = [r[feat] for r in feature_rows
                      if r["source"] == "basin" and isinstance(r.get(feat), (int, float))
                      and math.isfinite(r[feat])]
        if not ridge_vals or not basin_vals:
            continue
        thresholds[feat] = find_threshold(ridge_vals, basin_vals)
        thresholds[feat]["n_ridge"] = len(ridge_vals)
        thresholds[feat]["n_basin"] = len(basin_vals)
    with open(os.path.join(OUTDIR, "thresholds.json"), "w") as f:
        json.dump(thresholds, f, indent=2)
    print(f"  Wrote thresholds.json")

    # --- 2D combined classifier: for the (top1,top2) pair, scan a grid of
    # AND-thresholds and pick the most accurate one ---
    combined = None
    if len(top3) >= 2:
        f1, f2 = top3[0], top3[1]
        t1 = thresholds.get(f1)
        t2 = thresholds.get(f2)
        if t1 and t2:
            def pred_ridge(val, th):
                return (val <= th["threshold"]) if th["direction"] == "<=" else (val >= th["threshold"])

            r_rows = [r for r in feature_rows if r["source"] == "ridge"]
            b_rows = [r for r in feature_rows if r["source"] == "basin"]
            r_correct = sum(1 for r in r_rows if pred_ridge(r[f1], t1) and pred_ridge(r[f2], t2))
            b_correct = sum(1 for r in b_rows if not (pred_ridge(r[f1], t1) and pred_ridge(r[f2], t2)))
            total = len(r_rows) + len(b_rows)
            acc = (r_correct + b_correct) / total if total else 0
            combined = {
                "features": [f1, f2],
                "accuracy": acc,
                "fpr": (len(b_rows) - b_correct) / len(b_rows) if b_rows else 0,
                "fnr": (len(r_rows) - r_correct) / len(r_rows) if r_rows else 0,
                "rule": f"ridge ⇔ ({f1} {t1['direction']} {t1['threshold']:.4g}) AND ({f2} {t2['direction']} {t2['threshold']:.4g})",
            }

    # --- Summary.md ---
    sum_path = os.path.join(OUTDIR, "summary.md")
    n_ridge = sum(1 for r in feature_rows if r["source"] == "ridge")
    n_basin = sum(1 for r in feature_rows if r["source"] == "basin")
    lines = [
        "# Barrier Analysis — Ridge vs Basin structural invariants",
        "",
        f"- Ridge graphs (SAT-optimal): {n_ridge}",
        f"- Basin graphs (heuristic): {n_basin}",
        f"- Forced-matching basin graphs: {len(fm)}",
        f"- Baseline-sweep basin graphs: {len(bl)}",
        f"- Graphs verified K4-free: {verified_k4_free}/{len(feature_rows)}",
        "",
        "## 1. Which properties separate ridge from basin?",
        "",
        "Top 5 (by mean |Cohen d| across N, with -log10 p as tiebreak):",
        "",
    ]
    for i, r in enumerate(ranked[:5], 1):
        lines.append(f"{i}. **{r['feature']}** — mean |d| = {r['mean_abs_effect']:.3f}, "
                     f"-log10 p = {r['mean_neg_log_p']:.2f}")
    lines += [
        "",
        "The full per-N table is in `feature_comparison.csv`.",
        "",
        "## 2. Is near-regularity the strongest signal?",
        "",
    ]
    reg_rank = next((i + 1 for i, r in enumerate(ranked) if r["feature"] == "regularity"), None)
    d_range_rank = next((i + 1 for i, r in enumerate(ranked) if r["feature"] == "d_range"), None)
    d_var_rank = next((i + 1 for i, r in enumerate(ranked) if r["feature"] == "d_var"), None)
    top_feat = ranked[0]["feature"] if ranked else "n/a"
    lines.append(f"Regularity-related ranks: regularity #{reg_rank}, d_range #{d_range_rank}, d_var #{d_var_rank}.")
    lines.append(f"Top-ranked feature overall: **{top_feat}**.")
    lines.append("")
    lines.append("## 3. Can a 2–3 property barrier classify ridge vs basin at >80%?")
    lines.append("")
    for feat, th in thresholds.items():
        lines.append(f"- **{feat}** threshold: ridge ⇔ value {th['direction']} {th['threshold']:.4g} → "
                     f"accuracy {th['accuracy']*100:.1f}%, FPR {th['fpr']*100:.1f}%, FNR {th['fnr']*100:.1f}%")
    if combined:
        lines.append("")
        lines.append(f"- **Combined ({combined['features'][0]} AND {combined['features'][1]})**: "
                     f"accuracy {combined['accuracy']*100:.1f}%, "
                     f"FPR {combined['fpr']*100:.1f}%, FNR {combined['fnr']*100:.1f}%")
        lines.append(f"  Rule: `{combined['rule']}`")
    lines += [
        "",
        "## 4. Do the barriers hold across N, or are they N-specific?",
        "",
        "Per-N effect sizes are in `feature_comparison.csv`. A feature is a durable",
        "barrier if its |Cohen d| stays consistently high and its mean differs in the",
        "same direction across N. Features concentrating effect in a narrow N band",
        "may be artifacts of a particular basin construction at that size.",
        "",
        "Direction consistency for the top 5 (sign of ridge_mean − basin_mean per N):",
    ]
    dir_map = defaultdict(list)
    for c in comparisons:
        if c["feature"] in top5:
            sign = "+" if c["ridge_mean"] > c["basin_mean"] else ("-" if c["ridge_mean"] < c["basin_mean"] else "0")
            dir_map[c["feature"]].append((c["N"], sign, c["abs_effect_size"]))
    for feat, items in dir_map.items():
        signs = "".join(s for _, s, _ in sorted(items))
        lines.append(f"- `{feat}`: {signs}  (n={len(items)} shared Ns)")
    lines += [
        "",
        "## 5. Recommended barrier constraints",
        "",
        "Use the top-ranked features (with their thresholds above) as edge-acceptance",
        "gates in a controlled construction loop. Concretely:",
        "",
    ]
    for feat, th in thresholds.items():
        lines.append(f"- After any edge addition, require `{feat} {th['direction']} {th['threshold']:.4g}`; "
                     "reject the edge otherwise.")
    lines += [
        "",
        "This experiment cross-validates only whether these invariants distinguish",
        "the final graph. Whether they can be maintained under greedy edge-addition",
        "without over-constraining the search needs a follow-up constrained-construction run.",
        "",
        f"_Total runtime: {time.time()-t0:.1f}s_",
    ]
    with open(sum_path, "w") as f:
        f.write("\n".join(lines))
    print(f"  Wrote {sum_path}")

    print(f"\nDone in {time.time()-t0:.1f}s")


if __name__ == "__main__":
    main()
