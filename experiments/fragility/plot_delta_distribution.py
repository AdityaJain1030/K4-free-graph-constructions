#!/usr/bin/env python3
"""
experiments/fragility/plot_delta_distribution.py
================================================
Visualise run_delta_distribution.py output.

Two figures:
  * `delta_dist_histograms.png`: per (move, N) panel, histogram per source
    overlaid. Lets you see whether structured families have a different
    Δc_log shape than random.
  * `delta_dist_tails.png`: per (move) panel, P(Δ > 0.05) vs N coloured
    by source. The tail-mass scaling with N is the family signal.

    micromamba run -n k4free python experiments/fragility/plot_delta_distribution.py
"""

import argparse
import json
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))


def _color(src: str) -> str:
    palette = {
        "brute_force":      "#1f77b4",
        "sat_exact":        "#d62728",
        "server_sat_exact": "#d62728",
        "cayley":           "#2ca02c",
        "cayley_tabu_gap":  "#2ca02c",
        "polarity":         "#9467bd",
        "random":           "#7f7f7f",
    }
    return palette.get(src, "#000000")


def _label(src: str) -> str:
    aliases = {"server_sat_exact": "sat_exact", "cayley_tabu_gap": "cayley"}
    return aliases.get(src, src)


def plot_histograms(data: dict, out_path: str) -> None:
    moves = data["moves"]
    ns = sorted({r["n"] for r in data["results"]})
    rows = data["results"]

    fig, axes = plt.subplots(
        len(moves), len(ns),
        figsize=(3 * len(ns), 2.4 * len(moves)),
        squeeze=False, sharex=True,
    )

    # de-dup sources where two tags refer to same family
    canon = {}
    for r in rows:
        key = (_label(r["source"]), r["n"])
        canon.setdefault(key, r)

    for i, m in enumerate(moves):
        for j, n in enumerate(ns):
            ax = axes[i][j]
            seen_labels = set()
            for r in sorted(canon.values(), key=lambda x: x["source"]):
                if r["n"] != n:
                    continue
                s = r["per_move"][m]
                if s["mean"] is None or s["hist_counts"] is None:
                    continue
                bins = np.array(s["hist_bins"])
                cnts = np.array(s["hist_counts"], dtype=float)
                if cnts.sum() == 0:
                    continue
                cnts = cnts / cnts.sum()
                centres = (bins[:-1] + bins[1:]) / 2
                lab = _label(r["source"])
                ax.step(centres, cnts, where="mid",
                        color=_color(r["source"]),
                        label=lab if lab not in seen_labels else None,
                        linewidth=1.2, alpha=0.85)
                seen_labels.add(lab)
            ax.axvline(0, color="black", linewidth=0.6, alpha=0.6)
            ax.set_xlim(-0.30, 0.30)
            if i == 0:
                ax.set_title(f"N={n}", fontsize=10)
            if j == 0:
                ax.set_ylabel(f"{m}", fontsize=10)
            if i == len(moves) - 1:
                ax.set_xlabel(r"$\Delta c_{\log}$", fontsize=9)
            ax.tick_params(axis="both", which="major", labelsize=8)
            if i == 0 and j == len(ns) - 1:
                ax.legend(fontsize=7, loc="upper right")

    fig.suptitle(
        "Test A — one-step Δc_log distribution per family per move per N "
        f"(α={data['alpha_solver']}, max_props={data['max_proposals']})",
        fontsize=10,
    )
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    fig.savefig(out_path, dpi=160, bbox_inches="tight")
    print(f"wrote {out_path}")


def plot_tails(data: dict, out_path: str) -> None:
    moves = data["moves"]
    rows = data["results"]
    canon = {}
    for r in rows:
        key = (_label(r["source"]), r["n"])
        canon.setdefault(key, r)

    fig, axes = plt.subplots(
        3, len(moves), figsize=(3.2 * len(moves), 9.5), squeeze=False, sharex=True,
    )
    for j, m in enumerate(moves):
        ax_p = axes[0][j]
        ax_mu = axes[1][j]
        ax_rel = axes[2][j]
        per_src: dict[str, list[tuple[int, float, float, float]]] = {}
        for r in canon.values():
            s = r["per_move"][m]
            if s["mean"] is None:
                continue
            cl = (r.get("indicators") or {}).get("c_log")
            rel = s["mean"] / cl if (cl and cl > 0) else float("nan")
            per_src.setdefault(_label(r["source"]), []).append(
                (r["n"], s.get("p_gt_0.05") or 0.0, s["mean"], rel))
        for src, pts in sorted(per_src.items()):
            pts.sort()
            xs = [p[0] for p in pts]
            ys_p = [p[1] for p in pts]
            ys_mu = [p[2] for p in pts]
            ys_rel = [p[3] for p in pts]
            ax_p.plot(xs, ys_p, marker="o",
                      color=_color(src), label=src,
                      linewidth=1.5, markersize=5)
            ax_mu.plot(xs, ys_mu, marker="o",
                       color=_color(src), label=src,
                       linewidth=1.5, markersize=5)
            ax_rel.plot(xs, ys_rel, marker="o",
                        color=_color(src), label=src,
                        linewidth=1.5, markersize=5)
        ax_p.set_title(m, fontsize=10)
        ax_rel.set_xlabel("N")
        if j == 0:
            ax_p.set_ylabel(r"$\Pr[\Delta c_{\log} > 0.05]$", fontsize=9)
            ax_mu.set_ylabel(r"$\mathrm{mean}[\Delta c_{\log}]$", fontsize=9)
            ax_rel.set_ylabel(r"$\mathrm{mean}\,\Delta c_{\log} / c_{\log}(G_0)$"
                              "\n(relative)", fontsize=9)
        ax_p.set_ylim(-0.05, 1.05)
        ax_p.grid(alpha=0.3)
        ax_mu.axhline(0, color="black", linewidth=0.6, alpha=0.6)
        ax_mu.grid(alpha=0.3)
        ax_rel.axhline(0, color="black", linewidth=0.6, alpha=0.6)
        ax_rel.grid(alpha=0.3)
        if j == len(moves) - 1:
            ax_p.legend(fontsize=8, loc="best")
    fig.suptitle("Test A — tail mass / mean Δ / relative Δ per move",
                 fontsize=10)
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    fig.savefig(out_path, dpi=160, bbox_inches="tight")
    print(f"wrote {out_path}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="in_path",
                    default=os.path.join(HERE, "data", "delta_dist.json"))
    args = ap.parse_args()
    with open(args.in_path) as f:
        data = json.load(f)

    img_dir = os.path.join(HERE, "images")
    os.makedirs(img_dir, exist_ok=True)
    stem = os.path.splitext(os.path.basename(args.in_path))[0]
    plot_histograms(data, os.path.join(img_dir, f"{stem}_histograms.png"))
    plot_tails(data, os.path.join(img_dir, f"{stem}_tails.png"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
