#!/usr/bin/env python3
"""
visualizer/plots/plot_n_alpha_dmax.py
=====================================
3D scatter of every cached graph in (N, d_max, α) space, color-coded by
source algorithm, with the Caro–Wei lower-bound surface α = N/(d_max+1)
drawn as a translucent mesh. Every K₄-free graph must sit on or above
this surface — it's the cheapest universal lower bound on α from degree
alone.

Usage (from repo root):
    micromamba run -n k4free python visualizer/plots/plot_n_alpha_dmax.py
    micromamba run -n k4free python visualizer/plots/plot_n_alpha_dmax.py --interactive
    micromamba run -n k4free python visualizer/plots/plot_n_alpha_dmax.py --html

Writes visualizer/plots/images/n_alpha_dmax_3d.png. With --interactive,
also opens a rotatable matplotlib window (requires a display; on WSL2
needs WSLg or an X server, and is laggy). With --html, writes a
self-contained Plotly HTML to images/n_alpha_dmax_3d.html and opens it
in the Windows-side browser — WebGL rendering, no X server, smooth.
Requires `pip install plotly` in the env.
"""

import argparse
import os
import sys

import matplotlib

_INTERACTIVE = "--interactive" in sys.argv or "-i" in sys.argv
_HTML = "--html" in sys.argv
if not _INTERACTIVE:
    matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from mpl_toolkits.mplot3d import Axes3D  # noqa: F401,E402  (3d proj side-effect)

PALETTE = {
    "brute_force":         "#1f77b4",
    "circulant":           "#ff7f0e",
    "cayley":              "#d62728",
    "random":              "#2ca02c",
    "regularity":          "#9467bd",
    "regularity_alpha":    "#8c564b",
    "mattheus_verstraete": "#e377c2",
    "sat_pareto_ilp":      "#17becf",
}
DEFAULT_COLOR = "#555555"

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)

from graph_db import open_db  # noqa: E402

IMG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "images")
OUT_PNG = os.path.join(IMG_DIR, "n_alpha_dmax_3d.png")
OUT_HTML = os.path.join(IMG_DIR, "n_alpha_dmax_3d.html")


def load_points() -> dict[str, tuple[np.ndarray, np.ndarray, np.ndarray]]:
    """Return {source: (n, d_max, alpha)} for every cached K4-free graph."""
    with open_db() as db:
        rows = db.query(is_k4_free=1)
    by_src: dict[str, list[tuple[int, int, int]]] = {}
    for r in rows:
        by_src.setdefault(r["source"], []).append((r["n"], r["d_max"], r["alpha"]))
    return {
        src: (np.array([p[0] for p in pts]),
              np.array([p[1] for p in pts]),
              np.array([p[2] for p in pts]))
        for src, pts in by_src.items()
    }


def _caro_wei_surface(n_all, d_all, a_all, resolution: int = 40):
    """Return (N, D, CW_clipped, z_top) for the Caro–Wei lower bound."""
    n_grid = np.linspace(max(2, n_all.min()), n_all.max(), resolution)
    d_grid = np.linspace(max(1, d_all.min()), d_all.max(), resolution)
    N, D = np.meshgrid(n_grid, d_grid)
    CW = N / (D + 1.0)
    z_top = max(a_all.max() * 1.08, 5)
    return N, D, np.clip(CW, None, z_top), z_top


def render_matplotlib(data, interactive: bool) -> plt.Figure:
    fig = plt.figure(figsize=(11, 9))
    ax = fig.add_subplot(111, projection="3d")

    n_all = np.concatenate([v[0] for v in data.values()])
    d_all = np.concatenate([v[1] for v in data.values()])
    a_all = np.concatenate([v[2] for v in data.values()])

    # For interactive use on WSL2, rasterize the surface and shrink the mesh:
    # matplotlib's 3D redraws every primitive on every rotation, and a vector
    # 50x50 surface chokes the Tk event loop. rasterized=True bakes the
    # surface to a bitmap that doesn't re-tessellate on rotation.
    res = 24 if interactive else 40
    N, D, CW, z_top = _caro_wei_surface(n_all, d_all, a_all, resolution=res)
    ax.plot_surface(
        N, D, CW,
        alpha=0.32, cmap="Greys", edgecolor="none",
        shade=False, zorder=0, rasterized=True,
    )
    ax.plot_wireframe(
        N, D, CW, color="dimgray", alpha=0.45, linewidth=0.5,
        rcount=8, ccount=8, rasterized=True,
    )

    order = sorted(data.keys(), key=lambda s: -len(data[s][0]))
    for src in order:
        n, dm, a = data[src]
        ax.scatter(
            n, dm, a, s=28,
            c=PALETTE.get(src, DEFAULT_COLOR),
            label=f"{src} ({len(n)})",
            alpha=0.85, edgecolor="black", linewidth=0.3,
            depthshade=not interactive,  # depthshade is expensive per-frame
        )

    ax.set_xlabel("N (vertices)", labelpad=8)
    ax.set_ylabel(r"$d_{\max}$", labelpad=8)
    ax.set_zlabel(r"$\alpha$ (independence number)", labelpad=8)
    ax.set_title(
        r"K$_4$-free graphs in (N, $d_{\max}$, $\alpha$) "
        r"with Caro–Wei floor $\alpha = N/(d_{\max}{+}1)$"
    )
    ax.legend(loc="upper left", fontsize=9, framealpha=0.9)
    ax.view_init(elev=18, azim=-72)
    ax.set_zlim(0, z_top)
    plt.tight_layout()
    return fig


def render_plotly_html(data, out_path: str) -> None:
    """Write a self-contained Plotly HTML with WebGL 3D — smooth on WSL2."""
    try:
        import plotly.graph_objects as go
    except ImportError:
        print(
            "plotly not installed. Install with:\n"
            "    micromamba run -n k4free pip install plotly",
            file=sys.stderr,
        )
        sys.exit(2)

    n_all = np.concatenate([v[0] for v in data.values()])
    d_all = np.concatenate([v[1] for v in data.values()])
    a_all = np.concatenate([v[2] for v in data.values()])
    N, D, CW, _ = _caro_wei_surface(n_all, d_all, a_all, resolution=40)

    traces = [
        go.Surface(
            x=N, y=D, z=CW,
            colorscale=[[0, "rgba(120,120,120,0.25)"],
                        [1, "rgba(120,120,120,0.25)"]],
            showscale=False,
            name="Caro–Wei floor α = N/(d+1)",
            opacity=0.35,
            hovertemplate="N=%{x:.0f}  d=%{y:.0f}  floor α=%{z:.2f}<extra></extra>",
        )
    ]
    for src in sorted(data.keys(), key=lambda s: -len(data[s][0])):
        n, dm, a = data[src]
        traces.append(go.Scatter3d(
            x=n, y=dm, z=a,
            mode="markers",
            marker=dict(
                size=5,
                color=PALETTE.get(src, DEFAULT_COLOR),
                line=dict(width=0.5, color="black"),
            ),
            name=f"{src} ({len(n)})",
            hovertemplate=f"<b>{src}</b><br>N=%{{x}}  d_max=%{{y}}  α=%{{z}}<extra></extra>",
        ))

    fig = go.Figure(data=traces)
    fig.update_layout(
        title=("K₄-free graphs in (N, d_max, α) "
               "with Caro–Wei floor α = N/(d_max+1)"),
        scene=dict(
            xaxis_title="N (vertices)",
            yaxis_title="d_max",
            zaxis_title="α",
        ),
        legend=dict(itemsizing="constant"),
        margin=dict(l=0, r=0, t=40, b=0),
    )
    fig.write_html(out_path, include_plotlyjs="cdn", full_html=True)


def _try_open_in_browser(path: str) -> None:
    """Best-effort: open `path` in the Windows browser from WSL, else noop."""
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
    print(f"(no browser opener found; open {path} manually)")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "-i", "--interactive", action="store_true",
        help="open a rotatable matplotlib window (laggy on WSL2)",
    )
    parser.add_argument(
        "--html", action="store_true",
        help="write Plotly HTML and open in browser (smooth on WSL2, needs plotly)",
    )
    parser.add_argument(
        "--no-save", action="store_true",
        help="skip writing the PNG (only meaningful with --interactive or --html)",
    )
    args = parser.parse_args()

    data = load_points()
    if not data:
        print("no K4-free rows in graph_db — populate graphs/ and sync first",
              file=sys.stderr)
        return 1
    print(f"points: {sum(len(v[0]) for v in data.values())} across {len(data)} sources")

    os.makedirs(IMG_DIR, exist_ok=True)

    # ── Plotly path: render once, open browser, done. Bypasses matplotlib. ─
    if args.html:
        render_plotly_html(data, OUT_HTML)
        print(f"wrote {OUT_HTML}")
        _try_open_in_browser(OUT_HTML)
        if args.no_save:
            return 0
        # also emit the PNG unless the user opted out

    fig = render_matplotlib(data, interactive=args.interactive)

    if not args.no_save:
        fig.savefig(OUT_PNG, dpi=160, bbox_inches="tight")
        print(f"wrote {OUT_PNG}")

    if args.interactive:
        print(f"opening interactive window (backend: {matplotlib.get_backend()})")
        plt.show()
    return 0


if __name__ == "__main__":
    sys.exit(main())
