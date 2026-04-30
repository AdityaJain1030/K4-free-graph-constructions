#!/usr/bin/env python3
"""
experiments/fragility/plot_basin_radius.py
==========================================
Visualise run_basin_radius.py output.

Two figures:
  * `basin_radius_<tag>_rates.png`: p̂_exact and p̂_plateau vs K
    (perturb steps), one line per target. Log-x.
  * `basin_radius_<tag>_endpoint_clogs.png`: scatter of endpoint
    c_log vs K, target's c_log marked. Shows whether descent stays
    at the plateau level or drifts.

    micromamba run -n k4free python experiments/fragility/plot_basin_radius.py \\
        --in experiments/fragility/data/basin_radius_switch_30_35_39.json
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


def plot_rates(data: dict, out_path: str) -> None:
    results = data["results"]
    Ks = data["perturb_steps"]
    move = "+".join(data["move"])

    fig, axes = plt.subplots(1, 2, figsize=(10, 4.0), sharex=True)
    cmap = plt.get_cmap("viridis")
    norm = plt.Normalize(vmin=min(r["n"] for r in results),
                         vmax=max(r["n"] for r in results))

    for r in sorted(results, key=lambda x: (x["n"], x["source"])):
        n = r["n"]
        gid = r["graph_id"]
        src = r["source"]
        color = cmap(norm(n))
        per_K = [r["per_K"][str(k)] if str(k) in r["per_K"] else r["per_K"][k]
                 for k in Ks]
        p_exact = [d["p_exact"] for d in per_K]
        p_plateau = [d["p_plateau"] for d in per_K]
        label = f"n={n} {src} c={r['c_log']:.3f}"
        axes[0].plot(Ks, p_exact, marker="o", color=color, label=label, linewidth=1.5)
        axes[1].plot(Ks, p_plateau, marker="o", color=color, label=label, linewidth=1.5)

    for ax, ylab in zip(axes, ["p̂ exact (canonical match)",
                               "p̂ plateau (|Δc_log| < eps)"]):
        ax.set_xscale("log")
        ax.set_xlabel("K (random switches before descent)")
        ax.set_ylabel(ylab)
        ax.set_ylim(-0.05, 1.05)
        ax.grid(alpha=0.3, which="both")
        ax.legend(fontsize=7, loc="best")
    fig.suptitle(f"Test E variant — basin radius under {move} descent  "
                 f"(plateau_eps={data['plateau_eps']}, "
                 f"trials={data['trials']})",
                 fontsize=10)
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    fig.savefig(out_path, dpi=160, bbox_inches="tight")
    print(f"wrote {out_path}")


def plot_endpoint_clogs(data: dict, out_path: str) -> None:
    results = data["results"]
    Ks = data["perturb_steps"]
    move = "+".join(data["move"])

    fig, axes = plt.subplots(
        1, len(results), figsize=(3.4 * len(results), 4.0),
        squeeze=False, sharey=False,
    )
    for j, r in enumerate(sorted(results, key=lambda x: x["n"])):
        ax = axes[0][j]
        c_t = r["c_log"]
        for K in Ks:
            d = r["per_K"][str(K)] if str(K) in r["per_K"] else r["per_K"][K]
            ys = [v for v in d["endpoint_clogs"]
                  if v is not None and not np.isnan(v)]
            xs = [K] * len(ys)
            ax.scatter(xs, ys, color="#444", alpha=0.4, s=18)
        ax.axhline(c_t, color="red", linewidth=1.0, linestyle="--",
                   label=f"target c={c_t:.3f}")
        ax.set_xscale("log")
        ax.set_xlabel("K (random switches before descent)")
        if j == 0:
            ax.set_ylabel(r"endpoint $c_{\log}$")
        ax.set_title(f"n={r['n']}  src={r['source']}", fontsize=9)
        ax.grid(alpha=0.3, which="both")
        ax.legend(fontsize=7, loc="best")
    fig.suptitle(f"Test E variant — descent endpoint c_log per K under {move}",
                 fontsize=10)
    fig.tight_layout(rect=(0, 0, 1, 0.94))
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
    plot_rates(data, os.path.join(img_dir, f"{stem}_rates.png"))
    plot_endpoint_clogs(data, os.path.join(img_dir, f"{stem}_endpoints.png"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
