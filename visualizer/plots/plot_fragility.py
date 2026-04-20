#!/usr/bin/env python3
"""
visualizer/plots/plot_fragility.py
==================================
Average c_log trajectory under Probe-2 random edge-switch walks, one
line per starting N. Reads ``visualizer/plots/data/fragility.json``
(produced by ``scripts/run_fragility.py``) and writes two panels:

    - absolute c_log vs step (linear x)
    - c_log shift (Δ from step-0) vs step (log-spaced x)

Shape reading guide:
    * if the Δ-panel curves converge at large N (slow degradation) and
      diverge at small N (fast degradation), the basin is *widening*
      with N — local search / PatternBoost should help more at large N.
    * if all curves are parallel, the landscape is scale-invariant and
      perturbation cost is N-independent; PatternBoost won't help.

Usage::

    micromamba run -n k4free python visualizer/plots/plot_fragility.py
    micromamba run -n k4free python visualizer/plots/plot_fragility.py --html
"""

import argparse
import json
import os
import sys

import matplotlib

_INTERACTIVE = "--interactive" in sys.argv or "-i" in sys.argv
_HTML = "--html" in sys.argv
if not _INTERACTIVE:
    matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
IN_JSON = os.path.join(REPO, "visualizer", "plots", "data", "fragility.json")
IMG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "images")
OUT_PNG = os.path.join(IMG_DIR, "fragility.png")
OUT_HTML = os.path.join(IMG_DIR, "fragility.html")


def _cmap_for_ns(ns: list[int]):
    """Viridis by N — small N dark, large N bright."""
    norm = plt.Normalize(vmin=min(ns), vmax=max(ns))
    cmap = plt.get_cmap("viridis")
    return {n: cmap(norm(n)) for n in ns}


def render_matplotlib(data: dict, out_path: str) -> plt.Figure:
    results = sorted(data["results"], key=lambda r: r["n"])
    steps = data["record_steps"]
    ns = [r["n"] for r in results]
    if not ns:
        raise ValueError("no results to plot")
    norm = matplotlib.colors.Normalize(vmin=min(ns), vmax=max(ns))
    cmap = plt.get_cmap("viridis")

    fig, (ax_abs, ax_delta) = plt.subplots(
        1, 2, figsize=(13, 5.5), constrained_layout=True,
    )

    for r in results:
        n = r["n"]
        mean = np.array(r["mean_c_log"], dtype=float)
        std = np.array(r["std_c_log"], dtype=float)
        color = cmap(norm(n))

        ax_abs.plot(steps, mean, color=color, linewidth=1.1, alpha=0.75)
        ax_abs.fill_between(
            steps, mean - std, mean + std, color=color, alpha=0.05,
        )

        base = mean[0]
        delta = mean - base
        x = np.array(steps, dtype=float)
        mask = x > 0
        ax_delta.plot(
            x[mask], delta[mask], color=color, linewidth=1.1, alpha=0.75,
        )

    ax_abs.set_xlabel("walk step")
    ax_abs.set_ylabel(r"mean $c_{\log} = \alpha\, d_{\max} / (N \ln d_{\max})$")
    ax_abs.set_title("Fragility: absolute c_log under random edge-switch walk")
    ax_abs.grid(alpha=0.3)

    ax_delta.set_xscale("log")
    ax_delta.set_xlabel("walk step (log)")
    ax_delta.set_ylabel(r"$\Delta c_{\log}$ from step 0")
    ax_delta.set_title("Fragility: c_log shift (convergence → basin widening)")
    ax_delta.axhline(0, color="black", linewidth=0.7, alpha=0.6)
    ax_delta.grid(alpha=0.3, which="both")

    # Single colorbar for N across both panels.
    sm = plt.cm.ScalarMappable(norm=norm, cmap=cmap)
    sm.set_array([])
    cbar = fig.colorbar(sm, ax=[ax_abs, ax_delta],
                        fraction=0.03, pad=0.02, aspect=40)
    cbar.set_label("N (starting graph size)")

    fig.suptitle(
        f"Probe 2 — fragility across N   "
        f"({len(results)} seeds, trials={data['trials']}, "
        f"walk={data['walk_length']}, α={data['alpha_solver']})",
        fontsize=11,
    )
    return fig


def render_plotly_html(data: dict, out_path: str) -> None:
    try:
        import plotly.graph_objects as go
        from plotly.subplots import make_subplots
    except ImportError:
        print("plotly not installed; install with: pip install plotly",
              file=sys.stderr)
        sys.exit(2)

    results = data["results"]
    steps = data["record_steps"]
    ns = sorted({r["n"] for r in results})
    palette = _cmap_for_ns(ns)

    def rgba(c):
        return f"rgba({int(c[0]*255)},{int(c[1]*255)},{int(c[2]*255)},1.0)"

    fig = make_subplots(
        rows=1, cols=2,
        subplot_titles=("absolute c_log", "Δ c_log from step 0 (log-x)"),
    )

    for r in sorted(results, key=lambda r: r["n"]):
        n = r["n"]
        mean = np.array(r["mean_c_log"], dtype=float)
        std = np.array(r["std_c_log"], dtype=float)
        color = rgba(palette[n])
        fig.add_trace(go.Scatter(
            x=steps, y=mean.tolist(), mode="lines+markers",
            name=f"N={n} ({r['source']})",
            line=dict(color=color, width=2),
            error_y=dict(type="data", array=std.tolist(), visible=True),
        ), row=1, col=1)
        base = float(mean[0])
        delta = (mean - base).tolist()
        x = [s for s in steps if s > 0]
        y = [d for s, d in zip(steps, delta) if s > 0]
        fig.add_trace(go.Scatter(
            x=x, y=y, mode="lines+markers",
            name=f"N={n}",
            line=dict(color=color, width=2),
            showlegend=False,
        ), row=1, col=2)

    fig.update_xaxes(title_text="walk step", row=1, col=1)
    fig.update_xaxes(title_text="walk step (log)", type="log", row=1, col=2)
    fig.update_yaxes(title_text="c_log", row=1, col=1)
    fig.update_yaxes(title_text="Δ c_log", row=1, col=2)
    fig.update_layout(
        title=(f"Probe 2 — fragility across N  "
               f"(trials={data['trials']}, walk={data['walk_length']}, "
               f"α={data['alpha_solver']})"),
        height=560,
    )
    fig.write_html(out_path, include_plotlyjs="cdn", full_html=True)


def _try_open_in_browser(path: str) -> None:
    import shutil
    import subprocess
    for opener in ("wslview", "explorer.exe", "xdg-open", "open"):
        if shutil.which(opener):
            try:
                subprocess.Popen([opener, path],
                                 stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL)
                print(f"opened with {opener}")
                return
            except Exception:
                continue
    print(f"(open {path} manually)")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in-json", default=IN_JSON,
                    help=f"input JSON (default {IN_JSON})")
    ap.add_argument("-i", "--interactive", action="store_true")
    ap.add_argument("--html", action="store_true")
    ap.add_argument("--no-save", action="store_true")
    args = ap.parse_args()

    if not os.path.exists(args.in_json):
        print(f"[plot_fragility] no input at {args.in_json}\n"
              f"run scripts/run_fragility.py first", file=sys.stderr)
        return 1

    with open(args.in_json) as f:
        data = json.load(f)

    if not data.get("results"):
        print("[plot_fragility] JSON has no results", file=sys.stderr)
        return 1

    os.makedirs(IMG_DIR, exist_ok=True)

    if args.html:
        render_plotly_html(data, OUT_HTML)
        print(f"wrote {OUT_HTML}")
        _try_open_in_browser(OUT_HTML)
        if args.no_save:
            return 0

    fig = render_matplotlib(data, OUT_PNG)
    if not args.no_save:
        fig.savefig(OUT_PNG, dpi=160, bbox_inches="tight")
        print(f"wrote {OUT_PNG}")
    if args.interactive:
        plt.show()
    return 0


if __name__ == "__main__":
    sys.exit(main())
