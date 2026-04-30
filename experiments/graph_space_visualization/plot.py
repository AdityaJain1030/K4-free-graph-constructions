"""
experiments/graph_space_visualization/plot.py
=============================================
2D scatter renderers. PNG via matplotlib, HTML via plotly.
Color by categorical label, marker size by a per-point scalar.
"""
from __future__ import annotations

import numpy as np


def _palette(n_groups: int):
    import matplotlib.pyplot as plt
    name = "tab20" if n_groups > 10 else "tab10"
    cmap = plt.get_cmap(name)
    return [cmap(i % cmap.N) for i in range(n_groups)]


def _normalize_sizes(values: np.ndarray | None, lo: float, hi: float) -> np.ndarray:
    if values is None:
        return None
    v = np.asarray(values, dtype=np.float64)
    if not np.isfinite(v).any():
        return np.full_like(v, (lo + hi) / 2.0)
    finite = v[np.isfinite(v)]
    vmin, vmax = float(finite.min()), float(finite.max())
    if vmax - vmin < 1e-12:
        return np.full_like(v, (lo + hi) / 2.0)
    scaled = lo + (hi - lo) * (v - vmin) / (vmax - vmin)
    scaled[~np.isfinite(v)] = lo
    return scaled


def scatter_png(
    coords: np.ndarray,
    labels: list[str],
    sizes: np.ndarray | None,
    title: str,
    out_path: str,
    highlight_mask: np.ndarray | None = None,
    best_mask: np.ndarray | None = None,
) -> None:
    import matplotlib.pyplot as plt

    sizes_pt = _normalize_sizes(sizes, lo=20.0, hi=200.0)
    unique = sorted(set(labels))
    colors = _palette(len(unique))
    color_of = {lab: colors[i] for i, lab in enumerate(unique)}

    fig, ax = plt.subplots(figsize=(10, 8))
    arr_labels = np.array(labels)
    for lab in unique:
        mask = arr_labels == lab
        ax.scatter(
            coords[mask, 0], coords[mask, 1],
            s=(sizes_pt[mask] if sizes_pt is not None else 40),
            c=[color_of[lab]],
            label=lab,
            alpha=0.75,
            edgecolors="black",
            linewidths=0.3,
        )
    if highlight_mask is not None and highlight_mask.any():
        ax.scatter(
            coords[highlight_mask, 0], coords[highlight_mask, 1],
            s=300, facecolors="none", edgecolors="red", linewidths=1.5,
            label="highlight",
        )
    if best_mask is not None and best_mask.any():
        ax.scatter(
            coords[best_mask, 0], coords[best_mask, 1],
            s=400, marker="*", c="gold", edgecolors="black", linewidths=1.0,
            label="best c_log", zorder=10,
        )
    ax.set_title(title)
    ax.set_xlabel("dim 1")
    ax.set_ylabel("dim 2")
    ax.legend(loc="best", fontsize=8, markerscale=0.7, framealpha=0.85)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def scatter_html(
    coords: np.ndarray,
    labels: list[str],
    sizes: np.ndarray | None,
    hover_text: list[str] | None,
    title: str,
    out_path: str,
    highlight_mask: np.ndarray | None = None,
    best_mask: np.ndarray | None = None,
) -> None:
    import plotly.graph_objects as go

    sizes_pt = _normalize_sizes(sizes, lo=6.0, hi=22.0)
    fig = go.Figure()
    arr_labels = np.array(labels)
    for lab in sorted(set(labels)):
        idx = np.where(arr_labels == lab)[0]
        fig.add_trace(go.Scatter(
            x=coords[idx, 0], y=coords[idx, 1],
            mode="markers",
            marker=dict(
                size=(sizes_pt[idx] if sizes_pt is not None else 10),
                line=dict(width=0.4, color="black"),
            ),
            name=lab,
            text=([hover_text[i] for i in idx] if hover_text is not None else None),
            hoverinfo=("text" if hover_text is not None else "name"),
        ))
    if highlight_mask is not None and highlight_mask.any():
        idx = np.where(highlight_mask)[0]
        fig.add_trace(go.Scatter(
            x=coords[idx, 0], y=coords[idx, 1],
            mode="markers",
            marker=dict(size=22, symbol="circle-open", color="red", line=dict(width=2)),
            name="highlight",
            text=([hover_text[i] for i in idx] if hover_text is not None else None),
            hoverinfo=("text" if hover_text is not None else "name"),
        ))
    if best_mask is not None and best_mask.any():
        idx = np.where(best_mask)[0]
        fig.add_trace(go.Scatter(
            x=coords[idx, 0], y=coords[idx, 1],
            mode="markers",
            marker=dict(size=24, symbol="star", color="gold",
                        line=dict(width=1.0, color="black")),
            name="best c_log",
            text=([hover_text[i] for i in idx] if hover_text is not None else None),
            hoverinfo=("text" if hover_text is not None else "name"),
        ))
    fig.update_layout(
        title=title,
        xaxis_title="dim 1",
        yaxis_title="dim 2",
        hovermode="closest",
        legend=dict(itemsizing="constant"),
    )
    fig.write_html(out_path, include_plotlyjs="cdn")
