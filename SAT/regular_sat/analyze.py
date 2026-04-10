"""Analysis and plotting for regular_sat results.

Produces:
  - Summary table with (N, d_max, alpha, c_log, beta, regularity)
  - c_log vs N plot (results/c_vs_n.png)
  - beta vs N plot (results/beta_vs_n.png)
  - Text assessment (results/analysis.txt)
"""

import json
import os
import sys
from math import log

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

RESULTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")


def load_results():
    """Load all individual n*_a*.json results, return sorted list."""
    results = []
    for fname in sorted(os.listdir(RESULTS_DIR)):
        if not (fname.startswith("n") and "_a" in fname and fname.endswith(".json")):
            continue
        with open(os.path.join(RESULTS_DIR, fname)) as f:
            r = json.load(f)
        if r.get("edges") is not None:
            results.append(r)
    results.sort(key=lambda r: (r["n"], r["max_alpha"]))
    return results


def print_summary_table(results):
    """Print (N, d_max, alpha, c_log, beta, regularity) for each result."""
    print(f"{'N':>3} {'α':>2} {'d_min':>5} {'d_max':>5} {'|E|':>5} "
          f"{'c_log':>7} {'beta':>7} {'regular':>10} {'status':>8}")
    print("-" * 65)
    for r in results:
        d_min = r["d_min"]
        d_max = r["d_max"]
        regular = "exact" if d_min == d_max else "near"
        c_log = f"{r['c_log']:.4f}" if r["c_log"] is not None else "-"
        beta = f"{r['beta']:.4f}" if r["beta"] is not None else "-"
        print(f"{r['n']:>3} {r['max_alpha']:>2} {d_min:>5} {d_max:>5} "
              f"{r['num_edges']:>5} {c_log:>7} {beta:>7} {regular:>10} "
              f"{r['status']:>8}")


def plot_c_vs_n(results):
    """Plot c_log vs N, color-coded by alpha, with Ramsey boundary lines."""
    fig, ax = plt.subplots(figsize=(10, 6))

    alpha_colors = {3: "#E74C3C", 4: "#3498DB", 5: "#2ECC71"}
    alpha_labels = {3: "α = 3", 4: "α = 4", 5: "α = 5"}

    for alpha in sorted(alpha_colors.keys()):
        ns = [r["n"] for r in results
              if r["max_alpha"] == alpha and r["c_log"] is not None]
        cs = [r["c_log"] for r in results
              if r["max_alpha"] == alpha and r["c_log"] is not None]
        if ns:
            ax.scatter(ns, cs, c=alpha_colors[alpha], label=alpha_labels[alpha],
                       s=60, zorder=5, edgecolors="white", linewidth=0.5)
            ax.plot(ns, cs, c=alpha_colors[alpha], alpha=0.4, linewidth=1.5)

    # Ramsey boundaries
    ax.axvline(x=17.5, color="#888", linestyle="--", linewidth=1, alpha=0.7)
    ax.text(17.5, ax.get_ylim()[1] * 0.98, " R(4,4)=18", fontsize=8,
            ha="left", va="top", color="#666")
    ax.axvline(x=24.5, color="#888", linestyle="--", linewidth=1, alpha=0.7)
    ax.text(24.5, ax.get_ylim()[1] * 0.98, " R(4,5)=25", fontsize=8,
            ha="left", va="top", color="#666")

    ax.set_xlabel("N (vertices)", fontsize=12)
    ax.set_ylabel("c_log = α d_max / (N ln d_max)", fontsize=12)
    ax.set_title("c_log vs N for minimum-edge K₄-free near-regular graphs", fontsize=13)
    ax.legend(fontsize=10)
    ax.grid(True, alpha=0.3)

    out = os.path.join(RESULTS_DIR, "c_vs_n.png")
    fig.tight_layout()
    fig.savefig(out, dpi=150)
    plt.close(fig)
    print(f"Saved {out}")


def plot_beta_vs_n(results):
    """Plot beta vs N, color-coded by alpha."""
    fig, ax = plt.subplots(figsize=(10, 6))

    alpha_colors = {3: "#E74C3C", 4: "#3498DB", 5: "#2ECC71"}
    alpha_labels = {3: "α = 3", 4: "α = 4", 5: "α = 5"}

    for alpha in sorted(alpha_colors.keys()):
        ns = [r["n"] for r in results
              if r["max_alpha"] == alpha and r["beta"] is not None]
        bs = [r["beta"] for r in results
              if r["max_alpha"] == alpha and r["beta"] is not None]
        if ns:
            ax.scatter(ns, bs, c=alpha_colors[alpha], label=alpha_labels[alpha],
                       s=60, zorder=5, edgecolors="white", linewidth=0.5)
            ax.plot(ns, bs, c=alpha_colors[alpha], alpha=0.4, linewidth=1.5)

    # Reference line at beta = 1
    all_ns = [r["n"] for r in results if r["beta"] is not None]
    if all_ns:
        ax.axhline(y=1.0, color="#E67E22", linestyle="--", linewidth=1.5,
                    alpha=0.7, label="β = 1 (conjecture boundary)")

    # Ramsey boundaries
    ax.axvline(x=17.5, color="#888", linestyle="--", linewidth=1, alpha=0.7)
    ax.axvline(x=24.5, color="#888", linestyle="--", linewidth=1, alpha=0.7)

    ax.set_xlabel("N (vertices)", fontsize=12)
    ax.set_ylabel("β  where  d_avg = (N/α) · (ln N/α)^β", fontsize=12)
    ax.set_title("β vs N for minimum-edge K₄-free near-regular graphs", fontsize=13)
    ax.legend(fontsize=10)
    ax.grid(True, alpha=0.3)

    out = os.path.join(RESULTS_DIR, "beta_vs_n.png")
    fig.tight_layout()
    fig.savefig(out, dpi=150)
    plt.close(fig)
    print(f"Saved {out}")


def write_assessment(results):
    """Write analysis.txt based on trends in c_log and beta."""
    valid = [r for r in results if r["c_log"] is not None and r["beta"] is not None]
    if not valid:
        return

    ns = [r["n"] for r in valid]
    clogs = [r["c_log"] for r in valid]
    betas = [r["beta"] for r in valid]

    # Linear regression: c_log vs n
    ns_arr = np.array(ns, dtype=float)
    clogs_arr = np.array(clogs, dtype=float)
    betas_arr = np.array(betas, dtype=float)

    if len(ns_arr) > 1:
        c_slope, c_intercept = np.polyfit(ns_arr, clogs_arr, 1)
        b_slope, b_intercept = np.polyfit(ns_arr, betas_arr, 1)
        c_corr = np.corrcoef(ns_arr, clogs_arr)[0, 1]
        b_corr = np.corrcoef(ns_arr, betas_arr)[0, 1]
    else:
        c_slope = b_slope = c_intercept = b_intercept = 0
        c_corr = b_corr = 0

    lines = [
        "Analysis of minimum-edge K4-free near-regular graphs",
        "=" * 55,
        "",
        f"Data points: {len(valid)} solved instances, N in [{min(ns)}, {max(ns)}]",
        "",
        "c_log trend:",
        f"  Range: [{min(clogs):.4f}, {max(clogs):.4f}]",
        f"  Mean:  {np.mean(clogs_arr):.4f}",
        f"  Linear fit: c_log = {c_slope:.5f} * N + {c_intercept:.4f} (r={c_corr:.4f})",
        "",
        "beta trend:",
        f"  Range: [{min(betas):.4f}, {max(betas):.4f}]",
        f"  Mean:  {np.mean(betas_arr):.4f}",
        f"  Linear fit: beta = {b_slope:.5f} * N + {b_intercept:.4f} (r={b_corr:.4f})",
        "",
        "Assessment:",
    ]

    # Determine trend
    if b_slope > 0.01:
        lines.append(f"  beta is increasing with N (slope={b_slope:.4f}).")
        if max(betas) >= 0.95:
            lines.append("  beta is approaching 1 from below for larger N.")
            lines.append("  This is consistent with d_avg ~ (N/alpha) * ln(N/alpha),")
            lines.append("  i.e. the Ramsey-theoretic lower bound is tight.")
            lines.append("  If beta -> 1, then c_log -> constant, suggesting the")
            lines.append("  conjecture (c bounded away from 0) may be TRUE.")
        else:
            lines.append("  beta remains well below 1, suggesting d_avg grows slower")
            lines.append("  than (N/alpha) * ln(N/alpha).")
    elif b_slope < -0.01:
        lines.append(f"  beta is decreasing with N (slope={b_slope:.4f}).")
        lines.append("  This would imply c_log -> 0, suggesting the conjecture is FALSE.")
    else:
        lines.append("  beta is roughly stable across the range.")

    lines.append("")
    lines.append("CAVEAT: many results are FEASIBLE (not OPTIMAL) due to solver timeouts")
    lines.append("on lower D values. True optima may have fewer edges and different beta.")
    lines.append("Cluster runs with longer time limits will provide more definitive data.")

    text = "\n".join(lines)
    out = os.path.join(RESULTS_DIR, "analysis.txt")
    with open(out, "w") as f:
        f.write(text + "\n")
    print(f"\nSaved {out}")
    print(text)


def main():
    results = load_results()
    if not results:
        print("No results found")
        return

    print_summary_table(results)
    print()
    plot_c_vs_n(results)
    plot_beta_vs_n(results)
    write_assessment(results)


if __name__ == "__main__":
    main()
