"""
experiments/bound_tightness/plot_tightness.py
=============================================
Tightness plots from `results_per_n.csv`. Two figures:

  1. tightness_by_n.png  — bound/α vs N, points coloured by graph family,
     with a binned median trend line per family. Shows where each family
     sits in (N, slack)-space.
  2. tightness_by_clog.png — bound/α vs c_log, same colouring. Shows the
     correlation between SDP saturation and the c_log frontier.

Usage:
  micromamba run -n k4free python experiments/bound_tightness/plot_tightness.py
"""
from __future__ import annotations

import argparse
import csv
import os
import statistics
from collections import defaultdict

import matplotlib.pyplot as plt
import numpy as np


HERE = os.path.dirname(os.path.abspath(__file__))


# (csv field, plot label, "upper"/"lower")
BOUNDS = [
    ("hoffman_over_alpha",      r"$H/\alpha$ (regular only)",  "upper"),
    ("theta_over_alpha",        r"$\vartheta/\alpha$",         "upper"),
    ("theta_prime_over_alpha",  r"$\vartheta'/\alpha$",        "upper"),
    ("chi_f_over_alpha",        r"$\chi_f(\bar G)/\alpha$",    "upper"),
    ("clique_cover_over_alpha", r"greedy $\#$cliques$/\alpha$","upper"),
    ("alpha_over_hardcore",     r"$\alpha/E_{\max}$ (lower)",  "lower"),
]


# Group raw sources into broader families with stable colours.
FAMILIES = [
    ("Cayley plateau", {"cayley", "cayley_tabu", "cayley_tabu_gap"}, "C0"),
    ("SAT-certified",  {"sat_exact", "sat_regular", "sat_near_regular_nonreg",
                        "server_sat_exact", "sat_circulant_optimal"},  "C3"),
    ("Circulant",      {"circulant", "circulant_fast"},                "C2"),
    ("Disjoint lift",  {"disjoint_lift"},                              "C4"),
    ("Brute force",    {"brute_force"},                                "C7"),
]
DEFAULT_COLOR = "C5"


def family_for(source: str) -> tuple[str, str]:
    for label, members, color in FAMILIES:
        if source in members:
            return label, color
    return "other", DEFAULT_COLOR


def f(s: str) -> float | None:
    return float(s) if s not in ("", "None") else None


def load(path: str) -> list[dict]:
    with open(path) as f_:
        return list(csv.DictReader(f_))


def binned_median(xs: list[float], ys: list[float], bins: np.ndarray):
    """Return (bin_centers, median_per_bin) skipping empty bins."""
    by_bin: dict[int, list[float]] = defaultdict(list)
    for x, y in zip(xs, ys):
        idx = int(np.searchsorted(bins, x))
        by_bin[idx].append(y)
    out_x, out_y = [], []
    for idx in sorted(by_bin):
        if 1 <= idx <= len(bins):
            center = 0.5 * (bins[idx - 1] + bins[min(idx, len(bins) - 1)])
        elif idx == 0:
            center = bins[0]
        else:
            center = bins[-1]
        out_x.append(center)
        out_y.append(statistics.median(by_bin[idx]))
    return out_x, out_y


def panel(ax, rows, key, label, x_field, x_label, x_bins):
    """Draw one bound's panel: scatter + per-family median trend."""
    pts_by_fam: dict[str, list[tuple[float, float, str]]] = defaultdict(list)
    for r in rows:
        y = f(r[key])
        if y is None:
            continue
        x = float(r[x_field]) if x_field == "c_log" else int(r[x_field])
        fam, color = family_for(r["source"])
        pts_by_fam[fam].append((x, y, color))

    for fam, _, color in FAMILIES:
        pts = pts_by_fam.get(fam, [])
        if not pts:
            continue
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        ax.scatter(xs, ys, s=22, alpha=0.7, color=color, label=fam,
                   edgecolors="white", linewidths=0.4, zorder=3)
        if len(pts) >= 4:
            mx, my = binned_median(xs, ys, x_bins)
            if len(mx) >= 2:
                ax.plot(mx, my, color=color, lw=1.2, alpha=0.55, zorder=2)

    # Other / unmatched
    other = pts_by_fam.get("other", [])
    if other:
        ax.scatter([p[0] for p in other], [p[1] for p in other],
                   s=22, alpha=0.7, color=DEFAULT_COLOR, label="other",
                   edgecolors="white", linewidths=0.4, zorder=3)

    ax.axhline(1.0, color="black", lw=0.8, linestyle="--", alpha=0.5, zorder=1)
    ax.set_xlabel(x_label)
    ax.set_ylabel(label)
    all_y = [y for r in rows for y in [f(r[key])] if y is not None]
    if all_y:
        ax.set_title(f"{label}   min={min(all_y):.3f}  max={max(all_y):.3f}",
                     fontsize=10)
    ax.grid(True, alpha=0.25)


def make_figure(rows, x_field, x_label, x_bins, suptitle, out_path):
    fig, axes = plt.subplots(2, 3, figsize=(16, 9), sharex=True)
    axes = axes.flatten()
    for ax, (key, label, _) in zip(axes, BOUNDS):
        panel(ax, rows, key, label, x_field, x_label, x_bins)

    # one shared legend
    handles, labels = axes[1].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=len(labels),
               frameon=False, fontsize=9)
    fig.suptitle(suptitle, fontsize=11)
    fig.tight_layout(rect=[0, 0.04, 1, 0.96])
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    print(f"[plot] wrote {out_path}", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default=os.path.join(HERE, "results_per_n.csv"))
    ap.add_argument("--out-dir", default=HERE)
    args = ap.parse_args()

    rows = load(args.csv)

    n_bins = np.arange(0, 110, 10)
    make_figure(
        rows, "n", r"$N$", n_bins,
        f"Bound tightness vs $N$  ({len(rows)} graphs, {os.path.basename(args.csv)})",
        os.path.join(args.out_dir, "tightness_by_n.png"),
    )

    c_bins = np.arange(0.65, 1.10, 0.025)
    make_figure(
        rows, "c_log", r"$c_{\log}$", c_bins,
        f"Bound tightness vs $c_{{\\log}}$  ({len(rows)} graphs)",
        os.path.join(args.out_dir, "tightness_by_clog.png"),
    )


if __name__ == "__main__":
    main()
