#!/usr/bin/env python3
"""
experiments/fragility/plot_basin_volume.py
==========================================
Visualise run_basin_volume.py output.

Two figures:
  * `basin_volume_<move>.png` — bar chart of p̂_M(G*) per (N, source).
    Log-y scale because the prediction is exp(−cN). A floor at 1/inits
    is drawn so 0 hits doesn't disappear off the bottom.
  * `basin_volume_endpoints_<move>.png` — top-K most common endpoints
    by count, coloured by whether each is a target. Surfaces the
    "boring local minima" that dominate measure.

    micromamba run -n k4free python experiments/fragility/plot_basin_volume.py \\
        --in experiments/fragility/data/basin_volume_add_delete.json
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


def plot_basin(data: dict, out_path: str) -> None:
    move = "+".join(data["move"])
    inits = data["inits_per_n"]
    summary = data["summary"]

    # group by N
    by_n: dict[int, list[dict]] = {}
    for row in summary:
        by_n.setdefault(row["n"], []).append(row)

    ns = sorted(by_n.keys())
    sources = sorted({_label(r["source"]) for r in summary})

    fig, ax = plt.subplots(figsize=(max(7, 1.4 * len(ns)), 4.5))
    width = 0.8 / max(1, len(sources))
    floor = 1.0 / max(1, inits)

    for i, src in enumerate(sources):
        xs, ys = [], []
        for n in ns:
            rows = [r for r in by_n[n] if _label(r["source"]) == src]
            if not rows:
                continue
            r = rows[0]
            xs.append(n + (i - len(sources) / 2 + 0.5) * width)
            p = max(r["p_hat"], floor / 2)  # avoid zero on log scale
            ys.append(p)
        if xs:
            ax.bar(xs, ys, width=width, color=_color(src), label=src,
                   edgecolor="black", linewidth=0.5)

    ax.set_yscale("log")
    ax.axhline(floor, color="black", linewidth=0.6, linestyle="--",
               alpha=0.5, label=f"1/inits = {floor:.3g}")
    ax.set_xticks(ns)
    ax.set_xticklabels([str(n) for n in ns])
    ax.set_xlabel("N")
    ax.set_ylabel(r"$\hat p_M(G^*) = \Pr[\mathrm{descent} \to G^*]$")
    ax.set_title(f"Test E — basin volume per family per N  (move={move}, "
                 f"inits/N={inits})")
    ax.grid(axis="y", which="both", alpha=0.3)
    ax.legend(fontsize=8, loc="best")
    fig.tight_layout()
    fig.savefig(out_path, dpi=160, bbox_inches="tight")
    print(f"wrote {out_path}")


def plot_endpoints(data: dict, out_path: str, *, top_k: int = 12) -> None:
    move = "+".join(data["move"])
    endpoint_counts = data["endpoint_counts"]
    runs = data["runs"]

    ns = sorted({r["n"] for r in runs})
    fig, axes = plt.subplots(
        1, len(ns), figsize=(3.0 * len(ns), 4.0), squeeze=False, sharey=False,
    )

    for j, n in enumerate(ns):
        ax = axes[0][j]
        # all endpoints whose runs are at this N
        endpoints = [
            (gid, info) for gid, info in endpoint_counts.items()
            if info.get("n") == n
        ]
        endpoints.sort(key=lambda x: -x[1]["count"])
        endpoints = endpoints[:top_k]
        labels = []
        counts = []
        colors = []
        for gid, info in endpoints:
            is_target = info.get("is_target", False)
            tag = "T" if is_target else " "
            cl = info.get("c_log")
            cl_s = f"{cl:.3f}" if cl is not None else "—"
            labels.append(f"{tag} {gid[:8]}  c={cl_s}")
            counts.append(info["count"])
            colors.append("#d62728" if is_target else "#7f7f7f")
        ypos = np.arange(len(labels))[::-1]
        ax.barh(ypos, counts, color=colors, edgecolor="black", linewidth=0.5)
        ax.set_yticks(ypos)
        ax.set_yticklabels(labels, fontsize=7, family="monospace")
        ax.set_xlabel("descent endpoints (count)", fontsize=8)
        ax.set_title(f"N={n}", fontsize=10)
        ax.grid(axis="x", alpha=0.3)
    fig.suptitle(f"Test E — top descent endpoints per N "
                 f"(move={move}, red = target frontier graph)",
                 fontsize=10)
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    fig.savefig(out_path, dpi=160, bbox_inches="tight")
    print(f"wrote {out_path}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="in_path", required=True,
                    help="path to basin_volume_<move>.json")
    args = ap.parse_args()
    with open(args.in_path) as f:
        data = json.load(f)
    move_tag = "_".join(data["move"])
    img_dir = os.path.join(HERE, "images")
    os.makedirs(img_dir, exist_ok=True)
    plot_basin(data, os.path.join(img_dir, f"basin_volume_{move_tag}.png"))
    plot_endpoints(data, os.path.join(img_dir, f"basin_volume_endpoints_{move_tag}.png"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
