#!/usr/bin/env python3
"""
experiments/fragility/plot_fragility_vs_n.py
============================================
Plot how the one-step Δc_log distribution evolves with N, for the
single best-per-N graph at each N (i.e., the fragility shape *along
the c_log frontier*).

Two figures:
  * `<stem>_vs_n_lines.png`: mean Δ and P(>τ) per move vs N. Log-x.
  * `<stem>_vs_n_heatmap.png`: per move, heatmap of the Δ histogram
    columns over N. Lets you see the distribution shape change with
    N at a glance.

    micromamba run -n k4free python experiments/fragility/plot_fragility_vs_n.py \\
        --in experiments/fragility/data/delta_dist_extralarge.json
"""

import argparse
import json
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))


def _src_color(src: str) -> str:
    palette = {
        "brute_force":      "#1f77b4",
        "sat_exact":        "#d62728",
        "server_sat_exact": "#d62728",
        "sat_regular":      "#e377c2",
        "cayley":           "#2ca02c",
        "cayley_tabu":      "#17becf",
        "cayley_tabu_gap":  "#2ca02c",
        "polarity":         "#9467bd",
        "disjoint_lift":    "#bcbd22",
        "circulant_fast":   "#8c564b",
        "random":           "#7f7f7f",
    }
    return palette.get(src, "#000000")


def plot_lines(data: dict, out_path: str) -> None:
    moves = data["moves"]
    rows = sorted(data["results"], key=lambda r: r["n"])

    fig, axes = plt.subplots(3, len(moves),
                             figsize=(3.4 * len(moves), 9.0),
                             squeeze=False, sharex=True)
    for j, m in enumerate(moves):
        ax_mu = axes[0][j]
        ax_rel = axes[1][j]
        ax_p = axes[2][j]
        ns: list[int] = []
        means: list[float] = []
        rels: list[float] = []
        ps: list[float] = []
        srcs: list[str] = []
        for r in rows:
            s = r["per_move"][m]
            if s["mean"] is None:
                continue
            cl = (r.get("indicators") or {}).get("c_log")
            ns.append(r["n"])
            means.append(s["mean"])
            rels.append(s["mean"] / cl if (cl and cl > 0) else float("nan"))
            ps.append(s.get("p_gt_0.05") or 0.0)
            srcs.append(r["source"])
        if not ns:
            continue
        # background line connecting all points
        ax_mu.plot(ns, means, color="#888", linewidth=0.7, alpha=0.5,
                   zorder=1)
        ax_rel.plot(ns, rels, color="#888", linewidth=0.7, alpha=0.5,
                    zorder=1)
        ax_p.plot(ns, ps, color="#888", linewidth=0.7, alpha=0.5,
                  zorder=1)
        # colored markers per source
        for n, mu, rel, p, src in zip(ns, means, rels, ps, srcs):
            ax_mu.scatter([n], [mu], color=_src_color(src),
                          edgecolor="black", linewidth=0.4,
                          s=40, zorder=3, label=src)
            ax_rel.scatter([n], [rel], color=_src_color(src),
                           edgecolor="black", linewidth=0.4,
                           s=40, zorder=3, label=src)
            ax_p.scatter([n], [p], color=_src_color(src),
                         edgecolor="black", linewidth=0.4,
                         s=40, zorder=3, label=src)
        ax_mu.set_title(m, fontsize=10)
        ax_mu.axhline(0, color="black", linewidth=0.6, alpha=0.5)
        ax_mu.grid(alpha=0.3, which="both")
        ax_rel.axhline(0, color="black", linewidth=0.6, alpha=0.5)
        ax_rel.grid(alpha=0.3, which="both")
        ax_p.set_xlabel("N (log)")
        ax_p.set_xscale("log")
        ax_p.set_ylim(-0.05, 1.05)
        ax_p.grid(alpha=0.3, which="both")
        if j == 0:
            ax_mu.set_ylabel(r"mean $\Delta c_{\log}$")
            ax_rel.set_ylabel(r"mean $\Delta c_{\log}$ / $c_{\log}(G_0)$"
                              "\n(relative fragility)")
            ax_p.set_ylabel(r"$\Pr[\Delta c_{\log} > 0.05]$")
        # legend dedup
        handles, labels = ax_mu.get_legend_handles_labels()
        seen = set()
        keep = []
        for h, l in zip(handles, labels):
            if l in seen:
                continue
            seen.add(l)
            keep.append((h, l))
        if j == len(moves) - 1 and keep:
            ax_mu.legend([h for h, _ in keep], [l for _, l in keep],
                         fontsize=6, loc="upper right",
                         ncol=1, framealpha=0.9)
    fig.suptitle(
        "Test A — fragility along the c_log frontier (best graph per N)",
        fontsize=11,
    )
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(out_path, dpi=160, bbox_inches="tight")
    print(f"wrote {out_path}")


def plot_heatmap(data: dict, out_path: str) -> None:
    moves = data["moves"]
    rows = sorted(data["results"], key=lambda r: r["n"])

    fig, axes = plt.subplots(len(moves), 1,
                             figsize=(max(8, 0.4 * len(rows)),
                                      2.0 * len(moves)),
                             squeeze=False, sharex=True)
    for i, m in enumerate(moves):
        ax = axes[i][0]
        per_n = []
        ns_labels = []
        srcs_labels = []
        bins_arr = None
        for r in rows:
            s = r["per_move"][m]
            if s["hist_counts"] is None or s["mean"] is None:
                continue
            cnts = np.array(s["hist_counts"], dtype=float)
            if cnts.sum() > 0:
                cnts /= cnts.sum()
            per_n.append(cnts)
            ns_labels.append(r["n"])
            srcs_labels.append(r["source"])
            if bins_arr is None:
                bins_arr = np.array(s["hist_bins"])
        if not per_n:
            ax.text(0.5, 0.5, "no data", transform=ax.transAxes,
                    ha="center", va="center")
            continue
        mat = np.array(per_n).T  # rows = bin centres, cols = N
        centres = (bins_arr[:-1] + bins_arr[1:]) / 2
        # use a perceptually uniform cmap with white at 0
        im = ax.pcolormesh(
            np.arange(len(ns_labels) + 1), bins_arr, mat,
            shading="flat",
            norm=mcolors.PowerNorm(gamma=0.5, vmin=0, vmax=1),
            cmap="magma_r",
        )
        ax.axhline(0, color="cyan", linewidth=0.6, alpha=0.6)
        ax.set_ylabel(f"{m}\nΔc_log")
        ax.set_ylim(-0.30, 0.30)
        if i == len(moves) - 1:
            ax.set_xticks(np.arange(len(ns_labels)) + 0.5)
            ax.set_xticklabels([f"{n}\n{s[:8]}" for n, s in
                                zip(ns_labels, srcs_labels)],
                               rotation=45, ha="right", fontsize=6)
        else:
            ax.set_xticks(np.arange(len(ns_labels)) + 0.5)
            ax.set_xticklabels([])
        cbar = fig.colorbar(im, ax=ax, fraction=0.02, pad=0.02)
        cbar.ax.tick_params(labelsize=6)
    fig.suptitle("Test A — Δc_log distribution heatmap, best graph per N",
                 fontsize=11)
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    fig.savefig(out_path, dpi=160, bbox_inches="tight")
    print(f"wrote {out_path}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="in_path", required=True)
    args = ap.parse_args()
    with open(args.in_path) as f:
        data = json.load(f)
    img_dir = os.path.join(HERE, "images")
    os.makedirs(img_dir, exist_ok=True)
    stem = os.path.splitext(os.path.basename(args.in_path))[0]
    plot_lines(data, os.path.join(img_dir, f"{stem}_vs_n_lines.png"))
    plot_heatmap(data, os.path.join(img_dir, f"{stem}_vs_n_heatmap.png"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
