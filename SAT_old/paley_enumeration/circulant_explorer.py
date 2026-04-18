"""
Paley / Circulant K4-Free Graph Explorer.

Generates Paley graphs P(p) for primes p = 1 mod 4, checks K4-freeness,
repairs those with K4s, runs local search for better circulants, and computes
independence numbers to study the constant c = alpha*d/(N*ln(d)).
"""

import argparse
import csv
import math
import os
import random
import sys
import time
from collections import Counter

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from ortools.sat.python import cp_model

# Allow importing from sibling packages
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from k4free_ilp.alpha_exact import alpha_exact


# ---------------------------------------------------------------------------
# Section 1: Number theory utilities
# ---------------------------------------------------------------------------

def is_prime(n: int) -> bool:
    if n < 2:
        return False
    if n < 4:
        return True
    if n % 2 == 0 or n % 3 == 0:
        return False
    i = 5
    while i * i <= n:
        if n % i == 0 or n % (i + 2) == 0:
            return False
        i += 6
    return True


def quadratic_residues(p: int) -> set:
    """Return the set of nonzero quadratic residues mod p."""
    return {(i * i) % p for i in range(1, p)}


def primes_1mod4(limit: int) -> list:
    """Return all primes p = 1 mod 4 with p <= limit."""
    return [p for p in range(5, limit + 1) if is_prime(p) and p % 4 == 1]


# ---------------------------------------------------------------------------
# Section 2: Paley / circulant graph construction
# ---------------------------------------------------------------------------

def paley_connection_set(p: int) -> tuple:
    """
    Build the Paley connection set for prime p = 1 mod 4.
    Returns (S_half, S_full):
      S_half = QR mod p intersected with {1, ..., (p-1)/2}
      S_full = all nonzero QR mod p (the full symmetric connection set)
    """
    qr = quadratic_residues(p)
    S_full = qr  # nonzero QR; 0 is excluded since i >= 1
    half = (p - 1) // 2
    S_half = {s for s in S_full if 1 <= s <= half}
    return S_half, S_full


def s_half_to_full(S_half: set, p: int) -> set:
    """Expand S_half to the full symmetric connection set."""
    S_full = set()
    for s in S_half:
        S_full.add(s)
        S_full.add(p - s)
    return S_full


def circulant_adj(n: int, S_full: set) -> np.ndarray:
    """Build the n x n adjacency matrix for circulant C(n, S_full)."""
    adj = np.zeros((n, n), dtype=np.uint8)
    S_arr = np.array(sorted(S_full), dtype=np.int64)
    for i in range(n):
        neighbors = (i + S_arr) % n
        adj[i, neighbors] = 1
    return adj


# ---------------------------------------------------------------------------
# Section 3: K4-freeness check for circulants (O(|S_full|^3))
# ---------------------------------------------------------------------------

def find_k4_triples(S_full: set, p: int) -> list:
    """
    Find all triples {a, b, c} from S_full such that {0, a, b, c} is a K4.
    Requires: a, b, c in S_full and all pairwise diffs in S_full.
    Returns list of (a, b, c) with a < b < c.
    """
    S_sorted = sorted(S_full)
    triples = []
    for i in range(len(S_sorted)):
        a = S_sorted[i]
        for j in range(i + 1, len(S_sorted)):
            b = S_sorted[j]
            if (b - a) % p not in S_full:
                continue
            for k in range(j + 1, len(S_sorted)):
                c = S_sorted[k]
                if ((c - a) % p in S_full) and ((c - b) % p in S_full):
                    triples.append((a, b, c))
    return triples


def circulant_is_k4_free(S_full: set, p: int) -> bool:
    """Check if circulant C(p, S_full) is K4-free."""
    S_sorted = sorted(S_full)
    for i in range(len(S_sorted)):
        a = S_sorted[i]
        for j in range(i + 1, len(S_sorted)):
            b = S_sorted[j]
            if (b - a) % p not in S_full:
                continue
            for k in range(j + 1, len(S_sorted)):
                c = S_sorted[k]
                if ((c - a) % p in S_full) and ((c - b) % p in S_full):
                    return False
    return True


# ---------------------------------------------------------------------------
# Section 4: K4 repair
# ---------------------------------------------------------------------------

def greedy_repair(S_half: set, p: int) -> set:
    """
    Remove elements from S_half greedily to eliminate all K4 patterns.
    At each step, remove the S_half element involved in the most K4 triples.
    """
    S_half = set(S_half)
    while True:
        S_full = s_half_to_full(S_half, p)
        triples = find_k4_triples(S_full, p)
        if not triples:
            return S_half

        # Count participation of each S_full element in K4 triples
        counts = Counter()
        for a, b, c in triples:
            counts[a] += 1
            counts[b] += 1
            counts[c] += 1

        # Map to S_half representatives and pick the worst
        half_counts = Counter()
        for s, cnt in counts.items():
            rep = s if s <= (p - 1) // 2 else p - s
            half_counts[rep] += cnt

        worst = half_counts.most_common(1)[0][0]
        S_half.discard(worst)


def try_single_removals(S_half: set, p: int) -> list:
    """
    Try removing each single element of S_half.
    Return list of (removed_element, resulting_S_half) for K4-free results.
    """
    results = []
    for s in sorted(S_half):
        trial = S_half - {s}
        trial_full = s_half_to_full(trial, p)
        if circulant_is_k4_free(trial_full, p):
            results.append((s, trial))
    return results


# ---------------------------------------------------------------------------
# Section 5: Independence number computation
# ---------------------------------------------------------------------------

def hoffman_bound(S_full: set, n: int) -> float:
    """
    Hoffman bound for circulant C(n, S_full).
    Eigenvalues: lambda_k = sum_{s in S_full} 2*cos(2*pi*k*s/n) for k=0..n-1.
    (The factor of 2 accounts for the DFT of the indicator; but actually for
    circulants, lambda_k = sum_{s in S_full} exp(2*pi*i*k*s/n) which is real
    since S_full is symmetric. So lambda_k = sum_{s in S_full} cos(2*pi*k*s/n).)
    alpha <= -n * lambda_min / (lambda_max - lambda_min).
    """
    S_arr = np.array(sorted(S_full), dtype=np.float64)
    ks = np.arange(n, dtype=np.float64)
    # Eigenvalues: lambda_k = sum_s cos(2*pi*k*s/n) for s in S_full
    # Use outer product for vectorized computation
    angles = (2.0 * np.pi / n) * np.outer(ks, S_arr)
    eigenvalues = np.cos(angles).sum(axis=1)

    lam_max = eigenvalues[0]  # = |S_full| (the degree)
    lam_min = eigenvalues.min()

    if lam_min >= 0:
        return float(n)  # trivially, alpha <= n

    return float(-n * lam_min / (lam_max - lam_min))


def greedy_independent_set(adj: np.ndarray, num_starts: int = 20) -> list:
    """
    Find a large independent set via greedy with multiple random restarts.
    Returns the largest independent set found.
    """
    n = adj.shape[0]
    best = []

    for trial in range(num_starts):
        if trial == 0:
            order = list(range(n))
        else:
            order = list(range(n))
            random.shuffle(order)

        available = np.ones(n, dtype=bool)
        indep = []
        for v in order:
            if available[v]:
                indep.append(v)
                available[adj[v].astype(bool)] = False
                available[v] = False  # mark used

        if len(indep) > len(best):
            best = indep

    return best


def alpha_cpsat(adj: np.ndarray, time_limit: float = 300.0) -> tuple:
    """
    Compute maximum independent set via OR-Tools CP-SAT.
    Returns (alpha_value, independent_set_vertices) or (None, None) on timeout.
    """
    n = adj.shape[0]
    model = cp_model.CpModel()
    x = [model.new_bool_var(f"x_{i}") for i in range(n)]

    # Edge constraints
    for i in range(n):
        for j in range(i + 1, n):
            if adj[i, j]:
                model.add(x[i] + x[j] <= 1)

    # Symmetry breaking: vertex-transitive, so fix x[0] = 1
    model.add(x[0] == 1)

    model.maximize(sum(x))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit
    solver.parameters.num_workers = min(8, os.cpu_count() or 4)

    status = solver.solve(model)

    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        alpha_val = int(round(solver.objective_value))
        indep = [i for i in range(n) if solver.value(x[i])]
        return alpha_val, indep
    return None, None


def compute_alpha(adj: np.ndarray, S_full: set, n: int,
                  time_limit: float = 300.0) -> dict:
    """
    Compute independence number with tiered approach.
    Returns dict with: exact, lower, upper, independent_set, method.
    """
    # Always compute Hoffman upper bound
    upper = hoffman_bound(S_full, n)

    # Always compute greedy lower bound
    greedy_set = greedy_independent_set(adj, num_starts=30)
    lower = len(greedy_set)

    # Tier 1: bitmask B&B for small n
    if n <= 30:
        alpha_val, indep = alpha_exact(adj)
        return {
            "exact": alpha_val, "lower": alpha_val, "upper": alpha_val,
            "independent_set": indep, "method": "bitmask_bb",
            "hoffman": upper,
        }

    # Tier 2: CP-SAT — try for all sizes, fall back to bounds on timeout
    cpsat_alpha, cpsat_set = alpha_cpsat(adj, time_limit)
    if cpsat_alpha is not None:
        return {
            "exact": cpsat_alpha, "lower": cpsat_alpha, "upper": cpsat_alpha,
            "independent_set": cpsat_set, "method": "cpsat",
            "hoffman": upper,
        }

    # Tier 3: bounds only (solver timed out)
    return {
        "exact": None, "lower": lower, "upper": math.floor(upper),
        "independent_set": greedy_set, "method": "bounds",
        "hoffman": upper,
    }


# ---------------------------------------------------------------------------
# Section 6: Local search improvement
# ---------------------------------------------------------------------------

def compute_c(alpha: int, degree: int, n: int) -> float:
    """Compute c = alpha * d / (N * ln(d))."""
    if degree < 2:
        return float("inf")
    return alpha * degree / (n * math.log(degree))


def local_search(S_half: set, p: int, max_iters: int = 500,
                 time_limit: float = 30.0) -> tuple:
    """
    Hill-climb on the connection set to minimize c.
    Uses greedy alpha as proxy. Returns (best_S_half, best_c_proxy).
    """
    S_half = set(S_half)
    half = (p - 1) // 2
    complement = {s for s in range(1, half + 1)} - S_half

    # Compute baseline c with greedy alpha
    S_full = s_half_to_full(S_half, p)
    adj = circulant_adj(p, S_full)
    greedy_alpha = len(greedy_independent_set(adj, num_starts=10))
    degree = len(S_full)
    best_c = compute_c(greedy_alpha, degree, p)
    best_S = set(S_half)

    start_time = time.time()

    for iteration in range(max_iters):
        if time.time() - start_time > time_limit:
            break

        improved = False
        candidates = list(S_half)
        random.shuffle(candidates)

        for s_remove in candidates:
            if time.time() - start_time > time_limit:
                break

            comp_list = list(complement)
            random.shuffle(comp_list)

            for s_add in comp_list[:20]:  # try up to 20 additions per removal
                trial = (S_half - {s_remove}) | {s_add}
                trial_full = s_half_to_full(trial, p)

                if not circulant_is_k4_free(trial_full, p):
                    continue

                trial_adj = circulant_adj(p, trial_full)
                trial_alpha = len(greedy_independent_set(trial_adj, num_starts=5))
                trial_degree = len(trial_full)
                trial_c = compute_c(trial_alpha, trial_degree, p)

                if trial_c < best_c:
                    best_c = trial_c
                    best_S = set(trial)
                    S_half = set(trial)
                    complement = {s for s in range(1, half + 1)} - S_half
                    improved = True
                    break

            if improved:
                break

        if not improved:
            break

    return best_S, best_c


# ---------------------------------------------------------------------------
# Section 7: Main pipeline
# ---------------------------------------------------------------------------

def process_prime(p: int, time_limit: float = 300.0,
                  do_local_search: bool = True) -> dict:
    """Process a single prime: Paley generation, K4 check, repair, alpha."""
    t0 = time.time()
    print(f"\n{'='*60}")
    print(f"Processing p = {p}")
    print(f"{'='*60}")

    S_half, S_full = paley_connection_set(p)
    degree = len(S_full)
    print(f"  Paley degree: {degree}, |S_half| = {len(S_half)}")

    # Check K4-freeness
    paley_k4_free = circulant_is_k4_free(S_full, p)
    print(f"  Paley K4-free: {paley_k4_free}")

    result = {
        "p": p,
        "paley_k4_free": paley_k4_free,
        "paley_degree": degree,
        "variants": [],
    }

    if paley_k4_free:
        # Compute alpha for the Paley graph directly
        adj = circulant_adj(p, S_full)
        alpha_info = compute_alpha(adj, S_full, p, time_limit)
        c_val = None
        if alpha_info["exact"] is not None:
            c_val = compute_c(alpha_info["exact"], degree, p)
        c_lower = compute_c(alpha_info["lower"], degree, p)
        c_upper = compute_c(alpha_info["upper"], degree, p) if alpha_info["upper"] else None

        variant = {
            "type": "paley",
            "S_half": sorted(S_half),
            "S_size": len(S_half),
            "degree": degree,
            "is_k4_free": True,
            **alpha_info,
            "c_exact": c_val,
            "c_lower": c_lower,
            "c_upper": c_upper,
        }
        result["variants"].append(variant)
        elapsed = time.time() - t0
        _print_variant(variant, p)
        print(f"  Time: {elapsed:.1f}s")
        result["solve_time"] = elapsed
        return result

    # --- Paley has K4: repair and search ---

    # Count K4 triples
    triples = find_k4_triples(S_full, p)
    print(f"  K4 triples found: {len(triples)}")

    # Greedy repair
    print(f"  Running greedy repair...")
    repaired_half = greedy_repair(S_half, p)
    repaired_full = s_half_to_full(repaired_half, p)
    rep_degree = len(repaired_full)
    print(f"  Repaired: removed {len(S_half) - len(repaired_half)} elements, "
          f"degree = {rep_degree}")

    adj = circulant_adj(p, repaired_full)
    alpha_info = compute_alpha(adj, repaired_full, p, time_limit)
    c_val = None
    if alpha_info["exact"] is not None:
        c_val = compute_c(alpha_info["exact"], rep_degree, p)
    c_lower = compute_c(alpha_info["lower"], rep_degree, p)
    c_upper = compute_c(alpha_info["upper"], rep_degree, p) if alpha_info["upper"] else None

    repair_variant = {
        "type": "paley_repaired",
        "S_half": sorted(repaired_half),
        "S_size": len(repaired_half),
        "degree": rep_degree,
        "is_k4_free": True,
        **alpha_info,
        "c_exact": c_val,
        "c_lower": c_lower,
        "c_upper": c_upper,
    }
    result["variants"].append(repair_variant)
    _print_variant(repair_variant, p)

    # Try single-element removals from original Paley (if feasible)
    best_single = None
    if len(S_half) <= 50:
        print(f"  Trying single-element removals from Paley...")
        singles = try_single_removals(S_half, p)
        print(f"  Found {len(singles)} single-removal K4-free variants")

        for removed, trial_half in singles:
            trial_full = s_half_to_full(trial_half, p)
            trial_degree = len(trial_full)
            trial_adj = circulant_adj(p, trial_full)
            trial_alpha = compute_alpha(trial_adj, trial_full, p,
                                        min(time_limit, 60.0))
            tc = None
            if trial_alpha["exact"] is not None:
                tc = compute_c(trial_alpha["exact"], trial_degree, p)
            tc_lower = compute_c(trial_alpha["lower"], trial_degree, p)

            if best_single is None or tc_lower < best_single["c_lower"]:
                best_single = {
                    "type": "paley_repaired",
                    "removed": removed,
                    "S_half": sorted(trial_half),
                    "S_size": len(trial_half),
                    "degree": trial_degree,
                    "is_k4_free": True,
                    **trial_alpha,
                    "c_exact": tc,
                    "c_lower": tc_lower,
                    "c_upper": compute_c(trial_alpha["upper"], trial_degree, p) if trial_alpha["upper"] else None,
                }

        if best_single is not None:
            # Only add if it's better than greedy repair
            if best_single["c_lower"] < repair_variant["c_lower"]:
                result["variants"].append(best_single)
                print(f"  Best single removal (removed {best_single['removed']}): "
                      f"c_lower = {best_single['c_lower']:.4f}")

    # Local search from best repaired variant
    if do_local_search:
        best_var = min(result["variants"], key=lambda v: v["c_lower"])
        search_base = set(best_var["S_half"])
        print(f"  Running local search from best variant (c_lower={best_var['c_lower']:.4f})...")
        ls_time = min(60.0, time_limit / 3)
        search_half, search_c_proxy = local_search(
            search_base, p, max_iters=500, time_limit=ls_time
        )

        if search_half != set(best_var["S_half"]):
            search_full = s_half_to_full(search_half, p)
            search_degree = len(search_full)
            search_adj = circulant_adj(p, search_full)
            search_alpha = compute_alpha(search_adj, search_full, p, time_limit)
            sc = None
            if search_alpha["exact"] is not None:
                sc = compute_c(search_alpha["exact"], search_degree, p)
            sc_lower = compute_c(search_alpha["lower"], search_degree, p)
            sc_upper = compute_c(search_alpha["upper"], search_degree, p) if search_alpha["upper"] else None

            ls_variant = {
                "type": "circulant_search",
                "S_half": sorted(search_half),
                "S_size": len(search_half),
                "degree": search_degree,
                "is_k4_free": True,
                **search_alpha,
                "c_exact": sc,
                "c_lower": sc_lower,
                "c_upper": sc_upper,
            }
            result["variants"].append(ls_variant)
            _print_variant(ls_variant, p)

    elapsed = time.time() - t0
    result["solve_time"] = elapsed
    print(f"  Total time for p={p}: {elapsed:.1f}s")
    return result


def _print_variant(v: dict, p: int):
    """Print a summary line for a variant."""
    alpha_str = str(v["exact"]) if v.get("exact") is not None else f"[{v['lower']},{v['upper']}]"
    c_str = f"{v['c_exact']:.4f}" if v.get("c_exact") is not None else f"[{v['c_lower']:.4f},{v['c_upper']:.4f}]"
    print(f"    {v['type']:20s}  degree={v['degree']:3d}  alpha={alpha_str:>8s}  "
          f"c={c_str:>16s}  method={v.get('method','?')}")


def run_all(limit: int = 200, time_limit: float = 300.0,
            do_local_search: bool = True) -> list:
    """Run the full pipeline for all primes p = 1 mod 4 up to limit."""
    primes = primes_1mod4(limit)
    print(f"Primes to process ({len(primes)}): {primes}")
    print(f"Solver time limit: {time_limit}s per graph")

    results = []
    for p in primes:
        result = process_prime(p, time_limit, do_local_search)
        results.append(result)

    return results


# ---------------------------------------------------------------------------
# Section 8: Output
# ---------------------------------------------------------------------------

def flatten_results(results: list) -> list:
    """Flatten results into one row per variant for CSV output."""
    rows = []
    for r in results:
        p = r["p"]
        for v in r["variants"]:
            rows.append({
                "N": p,
                "type": v["type"],
                "S_size": v["S_size"],
                "degree": v["degree"],
                "is_k4_free": v["is_k4_free"],
                "alpha_exact": v.get("exact"),
                "alpha_lower": v.get("lower"),
                "alpha_upper": v.get("upper"),
                "hoffman_bound": f"{v.get('hoffman', ''):.2f}" if v.get("hoffman") else "",
                "c_exact": f"{v['c_exact']:.6f}" if v.get("c_exact") is not None else "",
                "c_lower": f"{v['c_lower']:.6f}" if v.get("c_lower") is not None else "",
                "c_upper": f"{v['c_upper']:.6f}" if v.get("c_upper") is not None else "",
                "method": v.get("method", ""),
                "connection_set": " ".join(str(s) for s in v["S_half"]),
            })
    return rows


def save_csv(results: list, path: str):
    """Save flattened results to CSV."""
    rows = flatten_results(results)
    if not rows:
        print("No results to save.")
        return

    fieldnames = ["N", "type", "S_size", "degree", "is_k4_free",
                  "alpha_exact", "alpha_lower", "alpha_upper", "hoffman_bound",
                  "c_exact", "c_lower", "c_upper", "method", "connection_set"]

    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"\nResults saved to {path}")


def print_summary_table(results: list):
    """Print a summary table to stdout."""
    print(f"\n{'='*100}")
    print(f"{'N':>5s} {'Type':>20s} {'|S|':>4s} {'Deg':>4s} {'K4free':>6s} "
          f"{'Alpha':>10s} {'c':>16s} {'Method':>10s}")
    print(f"{'-'*100}")

    for r in results:
        for v in r["variants"]:
            p = r["p"]
            alpha_str = (str(v["exact"]) if v.get("exact") is not None
                         else f"[{v['lower']},{v['upper']}]")
            c_str = (f"{v['c_exact']:.4f}" if v.get("c_exact") is not None
                     else f"[{v['c_lower']:.4f},{v['c_upper']:.4f}]")
            print(f"{p:>5d} {v['type']:>20s} {v['S_size']:>4d} {v['degree']:>4d} "
                  f"{'Y' if v['is_k4_free'] else 'N':>6s} "
                  f"{alpha_str:>10s} {c_str:>16s} {v.get('method','?'):>10s}")

    print(f"{'='*100}")


def plot_c_vs_n(results: list, path: str):
    """Generate scatter plot of c vs N."""
    fig, ax = plt.subplots(figsize=(14, 7))

    colors = {"paley": "blue", "paley_repaired": "red", "circulant_search": "green"}
    labels_seen = set()

    for r in results:
        p = r["p"]
        for v in r["variants"]:
            vtype = v["type"]
            color = colors.get(vtype, "gray")
            label = vtype if vtype not in labels_seen else None
            labels_seen.add(vtype)

            if v.get("c_exact") is not None:
                ax.scatter(p, v["c_exact"], c=color, s=50, zorder=5, label=label)
            else:
                c_lo = v.get("c_lower")
                c_hi = v.get("c_upper")
                if c_lo is not None and c_hi is not None:
                    mid = (c_lo + c_hi) / 2
                    ax.scatter(p, mid, c=color, s=50, zorder=5, label=label,
                               alpha=0.7)
                    ax.plot([p, p], [c_lo, c_hi], c=color, linewidth=1.5,
                            alpha=0.5, zorder=4)
                elif c_lo is not None:
                    ax.scatter(p, c_lo, c=color, s=50, zorder=5, label=label,
                               alpha=0.7, marker="v")

    # Reference lines
    ax.axhline(y=0.7213, color="orange", linestyle="--", linewidth=1.5,
               label="c = 0.7213 (ILP floor)", zorder=3)
    ax.axhline(y=0.6789, color="purple", linestyle="--", linewidth=1.5,
               label="c = 0.6789 (Paley P(17))", zorder=3)

    ax.set_xlabel("p (prime, p = 1 mod 4)", fontsize=12)
    ax.set_ylabel(r"$c = \alpha \cdot d \,/\, (p \cdot \ln d)$", fontsize=12)
    ax.set_title(r"K$_4$-free circulant independence ratio from Paley graphs",
                 fontsize=14)
    ax.legend(loc="upper right", fontsize=10)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    print(f"Plot saved to {path}")


# ---------------------------------------------------------------------------
# Section 9: CLI entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Explore K4-free circulant graphs from Paley construction"
    )
    parser.add_argument("--limit", type=int, default=200,
                        help="Upper bound on primes p = 1 mod 4 (default: 200)")
    parser.add_argument("--time-limit", type=float, default=300.0,
                        help="CP-SAT solver time limit in seconds (default: 300)")
    parser.add_argument("--no-plot", action="store_true",
                        help="Skip plot generation")
    parser.add_argument("--no-local-search", action="store_true",
                        help="Skip local search phase")
    parser.add_argument("--primes", type=int, nargs="*",
                        help="Specific primes to process (overrides --limit)")
    parser.add_argument("--seed", type=int, default=42,
                        help="Random seed (default: 42)")
    args = parser.parse_args()

    random.seed(args.seed)
    np.random.seed(args.seed)

    out_dir = os.path.dirname(os.path.abspath(__file__))

    if args.primes:
        # Process specific primes
        for p in args.primes:
            if p % 4 != 1 or not is_prime(p):
                print(f"Warning: {p} is not a prime = 1 mod 4, skipping")
        primes = [p for p in args.primes if p % 4 == 1 and is_prime(p)]
        results = []
        for p in primes:
            result = process_prime(p, args.time_limit,
                                   not args.no_local_search)
            results.append(result)
    else:
        results = run_all(args.limit, args.time_limit,
                          not args.no_local_search)

    # Output
    print_summary_table(results)

    csv_path = os.path.join(out_dir, "circulant_results.csv")
    save_csv(results, csv_path)

    if not args.no_plot:
        plot_path = os.path.join(out_dir, "c_vs_N.png")
        plot_c_vs_n(results, plot_path)

    # Summary statistics
    all_c = []
    for r in results:
        for v in r["variants"]:
            if v.get("c_exact") is not None:
                all_c.append((r["p"], v["c_exact"], v["type"]))
            elif v.get("c_lower") is not None:
                all_c.append((r["p"], v["c_lower"], v["type"]))

    if all_c:
        print(f"\n--- Summary ---")
        min_c = min(all_c, key=lambda x: x[1])
        max_c = max(all_c, key=lambda x: x[1])
        print(f"Min c: {min_c[1]:.4f} at p={min_c[0]} ({min_c[2]})")
        print(f"Max c: {max_c[1]:.4f} at p={max_c[0]} ({max_c[2]})")

        # Check if c stays bounded away from 0
        large_p_c = [c for p, c, t in all_c if p >= 50]
        if large_p_c:
            print(f"For p >= 50: min c = {min(large_p_c):.4f}, "
                  f"max c = {max(large_p_c):.4f}")
            if min(large_p_c) > 0.3:
                print("Conjecture appears SUPPORTED: c stays bounded away from 0")
            else:
                print("Conjecture status UNCLEAR: c drops below 0.3 for large p")


if __name__ == "__main__":
    main()
