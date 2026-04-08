"""
k4free_greedy.py
================
GRASP + Simulated Annealing search for K4-free graphs minimizing
the ratio alpha(G) * d / (n * log(d)), i.e. the constant c in
the bound alpha(G) >= c * n * log(d) / d.

Usage
-----
# Validate against ground truth (n=4..10)
python k4free_greedy.py --validate --gt ground_truth.json

# Run search for specific n values
python k4free_greedy.py --n_values 15 20 25 30 --trials 1000

# Full pipeline: validate then scale up
python k4free_greedy.py --validate --gt ground_truth.json --n_values 15 20 25 30
"""

import argparse
import csv
import json
import math
import os
import random
import sys
import time
from collections import defaultdict

import numpy as np

# Force unbuffered output
sys.stdout.reconfigure(line_buffering=True)

# ============================================================================
# Graph representation with incremental tracking
# ============================================================================

class K4FreeGraph:
    """
    Adjacency-matrix graph with incremental degree and internal-edge tracking.
    Uses numpy boolean arrays for fast bitwise operations.
    """

    def __init__(self, n):
        self.n = n
        self.adj = np.zeros((n, n), dtype=np.bool_)
        self.degree = np.zeros(n, dtype=np.int32)
        self.internal_edges = np.zeros(n, dtype=np.int32)  # edges within N(v)
        self.num_edges = 0

    def copy(self):
        g = K4FreeGraph.__new__(K4FreeGraph)
        g.n = self.n
        g.adj = self.adj.copy()
        g.degree = self.degree.copy()
        g.internal_edges = self.internal_edges.copy()
        g.num_edges = self.num_edges
        return g

    def has_edge(self, u, v):
        return self.adj[u, v]

    def common_neighbors(self, u, v):
        """Return indices of common neighbors of u and v."""
        return np.where(self.adj[u] & self.adj[v])[0]

    def codegree(self, u, v):
        """Number of common neighbors of u and v."""
        return int(np.sum(self.adj[u] & self.adj[v]))

    def neighbors(self, v):
        """Return array of neighbor indices."""
        return np.where(self.adj[v])[0]

    def add_edge(self, u, v):
        """Add edge u-v, updating all incremental counters. No validation."""
        self.adj[u, v] = True
        self.adj[v, u] = True
        self.degree[u] += 1
        self.degree[v] += 1
        self.num_edges += 1

        # Update internal_edges:
        # Common neighbors of u,v see both endpoints become neighbors
        cn = self.common_neighbors(u, v)
        codeg = len(cn)

        # For vertex u: edges within N(u) increase by codeg(u,v)
        # because v is now in N(u) and v is adjacent to each w in cn,
        # and each w is already in N(u)
        self.internal_edges[u] += codeg
        # Same for v
        self.internal_edges[v] += codeg
        # For each w in common neighborhood: w gains 1 internal edge
        # (the new edge u-v, both of which are in N(w))
        self.internal_edges[cn] += 1

    def remove_edge(self, u, v):
        """Remove edge u-v, updating all incremental counters."""
        cn = self.common_neighbors(u, v)
        codeg = len(cn)

        self.adj[u, v] = False
        self.adj[v, u] = False
        self.degree[u] -= 1
        self.degree[v] -= 1
        self.num_edges -= 1

        self.internal_edges[u] -= codeg
        self.internal_edges[v] -= codeg
        self.internal_edges[cn] -= 1

    def max_degree(self):
        return int(np.max(self.degree)) if self.n > 0 else 0

    def edge_list(self):
        """Return list of edges (u,v) with u < v."""
        rows, cols = np.where(np.triu(self.adj, k=1))
        return list(zip(rows.tolist(), cols.tolist()))

    def non_edge_list(self):
        """Return list of non-edges (u,v) with u < v."""
        rows, cols = np.where(np.triu(~self.adj & ~np.eye(self.n, dtype=np.bool_), k=1))
        return list(zip(rows.tolist(), cols.tolist()))


# ============================================================================
# Filter cascade for edge validation
# ============================================================================

def check_degree_cap(g, u, v, alpha_target):
    """Filter 1: degree cap from codegree averaging bound d <= sqrt(n * alpha)."""
    d_cap = int(math.floor(math.sqrt(g.n * alpha_target))) + 1
    if g.degree[u] + 1 > d_cap or g.degree[v] + 1 > d_cap:
        return False
    return True


def check_codegree_cap(g, u, v, alpha_target):
    """Filter 2: codegree cap. Common neighborhood is independent in K4-free,
    so if codeg > alpha_target, then alpha > alpha_target."""
    codeg = g.codegree(u, v)
    if codeg > alpha_target:
        return False
    return True


def check_k4_free(g, u, v):
    """Filter 3: check if adding edge u-v would create a K4.
    A K4 is created iff two common neighbors of u,v are adjacent."""
    cn = g.common_neighbors(u, v)
    if len(cn) < 2:
        return True
    # Check if any two vertices in cn are adjacent
    # Extract submatrix and check for any edge
    sub = g.adj[np.ix_(cn, cn)]
    if np.any(np.triu(sub, k=1)):
        return False
    return True


def check_neighborhood_density(g, u, v):
    """Filter 4: Turan density bound. N(v) is triangle-free in K4-free graphs,
    so internal_edges[v] <= degree[v]^2 / 4."""
    codeg = g.codegree(u, v)
    cn = g.common_neighbors(u, v)

    # After adding edge, internal_edges would change:
    new_ie_u = g.internal_edges[u] + codeg
    new_ie_v = g.internal_edges[v] + codeg
    new_deg_u = g.degree[u] + 1
    new_deg_v = g.degree[v] + 1

    if new_ie_u > new_deg_u * new_deg_u / 4:
        return False
    if new_ie_v > new_deg_v * new_deg_v / 4:
        return False

    # Check each common neighbor w
    for w in cn:
        new_ie_w = g.internal_edges[w] + 1
        deg_w = g.degree[w]
        if new_ie_w > deg_w * deg_w / 4:
            return False

    return True


def is_valid_edge(g, u, v, alpha_target):
    """Run full filter cascade. Returns True if edge u-v can be added."""
    if g.has_edge(u, v):
        return False
    if not check_degree_cap(g, u, v, alpha_target):
        return False
    if not check_codegree_cap(g, u, v, alpha_target):
        return False
    if not check_k4_free(g, u, v):
        return False
    if not check_neighborhood_density(g, u, v):
        return False
    return True


# ============================================================================
# Edge scoring heuristic
# ============================================================================

def score_edge(g, u, v, w_primary=3.0, w_secondary=1.0, w_tertiary=-0.5):
    """Score an edge for GRASP selection. Higher = better to add.

    Primary: count vertices non-adjacent to both u and v (destroying IS potential)
    Secondary: prefer low-degree endpoints (uniform degree)
    Tertiary: prefer low codegree (headroom before cap)
    """
    # Primary: vertices non-adjacent to both u and v (excluding u,v themselves)
    non_adj_both = int(np.sum(~g.adj[u] & ~g.adj[v])) - 2  # subtract u,v themselves
    # Secondary: negative of max degree of endpoints (prefer low degree)
    max_ep_deg = max(g.degree[u], g.degree[v])
    # Tertiary: codegree
    codeg = g.codegree(u, v)

    return w_primary * non_adj_both + w_secondary * (-max_ep_deg) + w_tertiary * codeg


# ============================================================================
# Exact independence number via branch-and-bound
# ============================================================================

def exact_alpha(g, timeout=None):
    """Exact maximum independent set size via branch-and-bound.
    Orders vertices by decreasing degree for faster pruning.
    Returns (alpha, timed_out) tuple."""
    n = g.n
    adj_sets = [set(g.neighbors(v)) for v in range(n)]

    # Order vertices by decreasing degree
    order = sorted(range(n), key=lambda v: -g.degree[v])
    # Map: position in order -> original vertex
    # We work with sets of original vertex indices

    best = [0]
    start_time = time.time()
    timed_out = [False]

    def branch(cands, size):
        if timeout and time.time() - start_time > timeout:
            timed_out[0] = True
            return
        if not cands:
            if size > best[0]:
                best[0] = size
            return
        if size + len(cands) <= best[0]:
            return
        # Pick vertex with most connections to candidates (for pruning)
        v = max(cands, key=lambda x: len(adj_sets[x] & cands))
        # Include v
        branch(cands - adj_sets[v] - {v}, size + 1)
        if timed_out[0]:
            return
        # Exclude v
        branch(cands - {v}, size)

    branch(set(range(n)), 0)
    return best[0], timed_out[0]


def hoffman_alpha_bound(g):
    """Hoffman bound: alpha >= n * (-lambda_min) / (d_max - lambda_min).
    Returns an upper bound on alpha (actually this gives a lower bound,
    but we use it as a quick check)."""
    if g.num_edges == 0:
        return g.n
    adj_float = g.adj.astype(np.float64)
    try:
        eigenvalues = np.linalg.eigvalsh(adj_float)
        lambda_min = eigenvalues[0]
        d_max = g.max_degree()
        if d_max + abs(lambda_min) < 1e-10:
            return g.n
        # Hoffman bound gives alpha(G) >= n * (-lambda_min) / (d_max - lambda_min)
        bound = g.n * (-lambda_min) / (d_max - lambda_min)
        return bound
    except Exception:
        return g.n


# ============================================================================
# GRASP construction phase
# ============================================================================

def grasp_construct(n, alpha_target, rng, grasp_alpha=0.15,
                    w_primary=3.0, w_secondary=1.0, w_tertiary=-0.5,
                    d_max_cap=None):
    """Construct a K4-free graph via GRASP.

    d_max_cap: if set, additionally reject edges that would push any
               vertex degree above this cap.

    Returns the graph, or None if construction yields nothing useful.
    """
    g = K4FreeGraph(n)

    max_score_sample = 200  # Only score this many candidates for large n

    while True:
        # Collect all valid candidate edges
        candidates = []

        # For efficiency, iterate over non-edges
        non_edges = g.non_edge_list()
        if not non_edges:
            break

        for u, v in non_edges:
            # Extra degree cap
            if d_max_cap is not None:
                if g.degree[u] + 1 > d_max_cap or g.degree[v] + 1 > d_max_cap:
                    continue
            if is_valid_edge(g, u, v, alpha_target):
                candidates.append((u, v))

        if not candidates:
            break

        # For large candidate sets, score a random subset
        if len(candidates) > max_score_sample:
            sample_idx = rng.choice(len(candidates), size=max_score_sample, replace=False)
            sample = [candidates[i] for i in sample_idx]
        else:
            sample = candidates

        # Score sampled candidates
        scores = []
        for u, v in sample:
            s = score_edge(g, u, v, w_primary, w_secondary, w_tertiary)
            scores.append(s)

        # GRASP: pick randomly from top fraction
        scores = np.array(scores)
        threshold_idx = max(1, int(len(scores) * grasp_alpha))
        top_indices = np.argpartition(scores, -threshold_idx)[-threshold_idx:]

        chosen_idx = rng.choice(top_indices)
        u, v = sample[chosen_idx]

        g.add_edge(u, v)

    return g


# ============================================================================
# Phase 2: Simulated Annealing for degree minimization
# ============================================================================

def sa_minimize_degree(g, alpha_target, rng, max_iters=5000,
                       t_start=2.0, t_end=0.01, alpha_check_every=500):
    """Simulated annealing to minimize max degree while keeping alpha <= alpha_target.

    Move: remove a random edge, add a different random non-edge (if valid).
    """
    best_g = g.copy()
    best_dmax = g.max_degree()
    current_dmax = best_dmax

    t_ratio = (t_end / t_start) ** (1.0 / max(max_iters, 1))
    temp = t_start

    edges = g.edge_list()
    if not edges:
        return best_g

    for iteration in range(max_iters):
        # Pick a random edge to remove
        if g.num_edges == 0:
            break
        edges = g.edge_list()
        eu, ev = edges[rng.integers(len(edges))]

        # Remove it
        g.remove_edge(eu, ev)

        # Try to add a random valid non-edge
        non_edges = g.non_edge_list()
        if non_edges:
            rng.shuffle(non_edges)
            added = False
            # Try a few random non-edges
            for nu, nv in non_edges[:20]:
                if is_valid_edge(g, nu, nv, alpha_target):
                    g.add_edge(nu, nv)
                    added = True
                    break

            if not added:
                # Undo removal
                g.add_edge(eu, ev)
                temp *= t_ratio
                continue
        else:
            g.add_edge(eu, ev)
            temp *= t_ratio
            continue

        new_dmax = g.max_degree()
        delta = new_dmax - current_dmax

        # Accept or reject
        if delta < 0 or rng.random() < math.exp(-delta / max(temp, 1e-10)):
            current_dmax = new_dmax
            if new_dmax < best_dmax:
                # Verify alpha periodically
                if iteration % alpha_check_every == 0:
                    a, _ = exact_alpha(g, timeout=5.0)
                    if a > alpha_target:
                        # Undo: remove the added edge, re-add removed edge
                        g.remove_edge(nu, nv)
                        g.add_edge(eu, ev)
                        current_dmax = g.max_degree()
                        temp *= t_ratio
                        continue
                best_dmax = new_dmax
                best_g = g.copy()
        else:
            # Reject: undo
            g.remove_edge(nu, nv)
            g.add_edge(eu, ev)

        temp *= t_ratio

    return best_g


# ============================================================================
# Outer search loop
# ============================================================================

# Known Ramsey bounds: R(4,t) values
# R(4,3)=9, R(4,4)=18, R(4,5)=25, R(4,6)<=41, R(4,7)<=61, R(4,8)<=84, R(4,9)<=115
RAMSEY_R4 = {3: 9, 4: 18, 5: 25, 6: 41, 7: 61, 8: 84, 9: 115}


def get_alpha_targets(n):
    """Determine feasible alpha targets for a given n.
    In a K4-free graph on n vertices, alpha >= some function of n.
    We search for graphs with small alpha, so we try targets from
    the theoretical minimum upward."""
    # Find mandatory lower bound from Ramsey: largest t such that R(4,t) <= n
    mandatory_min = 2
    for t, r in sorted(RAMSEY_R4.items()):
        if n >= r:
            mandatory_min = t

    # Try a focused range around the mandatory minimum
    targets = []
    for t in range(max(2, mandatory_min - 1), mandatory_min + 6):
        targets.append(t)

    # Also try some targets based on sqrt(n*log(n)) scaling
    theoretical_min = max(2, int(math.sqrt(n * math.log(max(n, 2)))) // 2)
    for t in range(theoretical_min, theoretical_min + 4):
        if t not in targets:
            targets.append(t)

    targets = sorted(set(t for t in targets if t >= 2))
    return targets


def compute_c_value(alpha_val, n, d):
    """Compute c = alpha * d / (n * log(d))."""
    if d <= 1:
        return float('inf')
    return alpha_val * d / (n * math.log(d))


def search_for_n(n, trials=500, sa_iters=3000, seed=42,
                 w_primary=3.0, w_secondary=1.0, w_tertiary=-0.5,
                 grasp_alpha=0.15, verbose=True):
    """Run GRASP + SA search for a given n. Returns list of result dicts.

    Explores both (alpha_target) and (alpha_target, d_max_cap) combinations
    to find different (n,d) pairs and minimize c overall.
    """
    rng = np.random.default_rng(seed)
    alpha_targets = get_alpha_targets(n)
    results = []
    # Track best per (alpha, d) to avoid redundant SA
    best_per_ad = {}  # (alpha_achieved, d_max) -> c_value

    if verbose:
        print(f"\n{'='*60}")
        print(f"  Searching n={n}, alpha targets: {alpha_targets}")
        print(f"  Trials per target: {trials}, SA iters: {sa_iters}")
        print(f"{'='*60}")

    # Determine degree caps to explore
    # Max possible d in K4-free graph: roughly sqrt(n * alpha) for small alpha
    max_d = n - 1
    d_caps = [None]  # None = no extra cap (unconstrained)
    for d in range(2, min(max_d + 1, int(2 * math.sqrt(n)) + 2)):
        d_caps.append(d)

    for alpha_target in alpha_targets:
        t0 = time.time()
        best_c = float('inf')
        best_result = None
        found_count = 0

        # Divide trials across degree caps
        trials_per_cap = max(1, trials // len(d_caps))

        for d_cap in d_caps:
            for trial in range(trials_per_cap):
                # Phase 1: GRASP construction
                g = grasp_construct(n, alpha_target, rng, grasp_alpha,
                                    w_primary, w_secondary, w_tertiary,
                                    d_max_cap=d_cap)

                if g.num_edges == 0:
                    continue

                d = g.max_degree()
                if d <= 1:
                    continue

                # Compute exact alpha
                a, timed_out = exact_alpha(g, timeout=10.0 if n <= 30 else 30.0)

                if timed_out:
                    # Fall back to Hoffman bound
                    hb = hoffman_alpha_bound(g)
                    if hb > alpha_target + 1:
                        continue
                    a = int(math.ceil(hb))

                if a <= alpha_target:
                    found_count += 1
                    c_val = compute_c_value(a, n, d)

                    ad_key = (a, d)
                    if ad_key in best_per_ad and best_per_ad[ad_key] <= c_val:
                        continue
                    best_per_ad[ad_key] = c_val

                    if c_val < best_c:
                        best_c = c_val
                        best_result = {
                            'n': n,
                            'alpha_target': alpha_target,
                            'alpha_achieved': a,
                            'd_max': d,
                            'num_edges': g.num_edges,
                            'c_value': c_val,
                            'trials': trial + 1,
                            'phase': 'grasp',
                        }

                        # Phase 2: SA degree minimization on promising graphs
                        if sa_iters > 0 and c_val < 5.0:
                            g_sa = sa_minimize_degree(
                                g.copy(), alpha_target, rng,
                                max_iters=sa_iters
                            )
                            d_sa = g_sa.max_degree()
                            if d_sa > 1:
                                a_sa, to = exact_alpha(g_sa, timeout=10.0)
                                if not to and a_sa <= alpha_target:
                                    c_sa = compute_c_value(a_sa, n, d_sa)
                                    if c_sa < best_c:
                                        best_c = c_sa
                                        best_result = {
                                            'n': n,
                                            'alpha_target': alpha_target,
                                            'alpha_achieved': a_sa,
                                            'd_max': d_sa,
                                            'num_edges': g_sa.num_edges,
                                            'c_value': c_sa,
                                            'trials': trial + 1,
                                            'phase': 'sa',
                                        }

        elapsed = time.time() - t0
        if best_result:
            best_result['time_seconds'] = round(elapsed, 2)
            results.append(best_result)
            if verbose:
                r = best_result
                print(f"  alpha_target={alpha_target}: "
                      f"alpha={r['alpha_achieved']}, d={r['d_max']}, "
                      f"c={r['c_value']:.4f}, "
                      f"found={found_count}/{trials}, "
                      f"time={elapsed:.1f}s ({r['phase']})")
        else:
            if verbose:
                print(f"  alpha_target={alpha_target}: "
                      f"no feasible graph found in {trials} trials "
                      f"({time.time()-t0:.1f}s)")

    return results


# ============================================================================
# Validation against ground truth
# ============================================================================

def validate(gt_path, trials=200, verbose=True):
    """Validate greedy against brute-force ground truth for n=4..10."""
    with open(gt_path) as f:
        gt = json.load(f)

    # gt format: {"(n, d)": {"min_alpha": ..., "c_value": ...}, ...}
    print("\n" + "=" * 70)
    print("  VALIDATION: Greedy vs Brute Force (n=4..10)")
    print("=" * 70)

    # Collect all greedy results for small n
    greedy_results = {}  # (n, d) -> min alpha found by greedy

    for n in range(4, 11):
        results = search_for_n(n, trials=trials, sa_iters=1000, seed=42,
                               verbose=verbose)
        for r in results:
            key = (r['n'], r['d_max'])
            a = r['alpha_achieved']
            if key not in greedy_results or a < greedy_results[key]:
                greedy_results[key] = a

    # Compare
    print("\n" + "-" * 70)
    print(f"  {'n':>3}  {'d':>3}  {'bf_alpha':>8}  {'greedy_alpha':>12}  {'match':>6}  {'note':>10}")
    print("-" * 70)

    total = 0
    matches = 0
    bugs = 0

    for key_str, info in sorted(gt.items()):
        n, d = eval(key_str)  # key is string "(n, d)"
        bf_alpha = info['min_alpha']

        if (n, d) in greedy_results:
            ga = greedy_results[(n, d)]
            match = ga == bf_alpha
            note = ""
            if ga < bf_alpha:
                note = "BUG!"
                bugs += 1
            elif ga > bf_alpha:
                note = "suboptimal"
            else:
                matches += 1
            total += 1
            print(f"  {n:>3}  {d:>3}  {bf_alpha:>8}  {ga:>12}  "
                  f"{'YES' if match else 'NO':>6}  {note:>10}")
        else:
            total += 1
            print(f"  {n:>3}  {d:>3}  {bf_alpha:>8}  {'---':>12}  "
                  f"{'---':>6}  {'not found':>10}")

    print("-" * 70)
    found = len([k for k in gt if eval(k) in greedy_results])
    print(f"  Found {found}/{total} (n,d) pairs. "
          f"Matches: {matches}. Bugs: {bugs}.")

    if bugs > 0:
        print("  WARNING: Found alpha values LOWER than brute force — indicates a bug!")
        return False

    return True


# ============================================================================
# Main
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="GRASP + SA search for K4-free graphs minimizing c = alpha*d/(n*log(d))")
    parser.add_argument("--validate", action="store_true",
                        help="Run validation against ground truth")
    parser.add_argument("--gt", default="ground_truth.json",
                        help="Path to ground truth JSON file")
    parser.add_argument("--n_values", type=int, nargs="+", default=None,
                        help="n values to search (e.g. 15 20 25 30)")
    parser.add_argument("--trials", type=int, default=500,
                        help="GRASP trials per alpha target")
    parser.add_argument("--sa_iters", type=int, default=3000,
                        help="SA iterations for degree minimization")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--grasp_alpha", type=float, default=0.15,
                        help="GRASP randomization (fraction of top candidates)")
    parser.add_argument("--w_primary", type=float, default=3.0)
    parser.add_argument("--w_secondary", type=float, default=1.0)
    parser.add_argument("--w_tertiary", type=float, default=-0.5)
    parser.add_argument("--outdir", default="results",
                        help="Output directory for results")

    args = parser.parse_args()

    if args.validate:
        ok = validate(args.gt, trials=200, verbose=True)
        if not ok:
            print("\nValidation FAILED. Fix bugs before scaling up.")
            return

    if args.n_values:
        os.makedirs(args.outdir, exist_ok=True)
        csv_path = os.path.join(args.outdir, "greedy_results.csv")

        all_results = []
        min_c_per_n = {}

        for n in args.n_values:
            results = search_for_n(
                n, trials=args.trials, sa_iters=args.sa_iters,
                seed=args.seed,
                w_primary=args.w_primary,
                w_secondary=args.w_secondary,
                w_tertiary=args.w_tertiary,
                grasp_alpha=args.grasp_alpha,
            )
            all_results.extend(results)

            # Track min c per n
            for r in results:
                key = r['n']
                if key not in min_c_per_n or r['c_value'] < min_c_per_n[key]['c_value']:
                    min_c_per_n[key] = r

        # Write CSV
        with open(csv_path, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=[
                'n', 'alpha_target', 'alpha_achieved', 'd_max',
                'num_edges', 'c_value', 'trials', 'time_seconds', 'phase'
            ])
            writer.writeheader()
            for r in all_results:
                writer.writerow(r)
        print(f"\nResults saved to {csv_path}")

        # Print summary
        print("\n" + "=" * 60)
        print("  MIN C VALUES BY N")
        print("=" * 60)
        for n in sorted(min_c_per_n.keys()):
            r = min_c_per_n[n]
            print(f"  n={n:>3}:  c={r['c_value']:.4f}  "
                  f"(alpha={r['alpha_achieved']}, d={r['d_max']})")


if __name__ == "__main__":
    main()
