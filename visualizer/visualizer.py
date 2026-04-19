"""
visualizer/visualizer.py
========================
Interactive K₄-free graph explorer backed by graph_db.

Usage:
    python visualizer/visualizer.py
    python visualizer/visualizer.py --source sat_pareto
    python -m visualizer.visualizer
"""

import os
import sys
import warnings
from collections import Counter

import numpy as np
import networkx as nx
warnings.filterwarnings("ignore", category=RuntimeWarning, module="networkx")
warnings.filterwarnings("ignore", category=UserWarning,    module="networkx")

import tkinter as tk
from tkinter import ttk

import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

# ── repo root on sys.path ─────────────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from graph_db import DB

# ---------------------------------------------------------------------------
# Palette
# ---------------------------------------------------------------------------
C_NODE     = "#4A90D9"
C_MIS      = "#E74C3C"
C_TRIANGLE = "#F39C12"
C_HIGH_DEG = "#2ECC71"
C_SELECTED = "#9B59B6"
C_NEIGHBOR = "#F1C40F"
C_DIM      = "#D5DBDB"
C_EDGE     = "#B0BEC5"
C_EDGE_TRI = "#E67E22"
C_BG       = "#FAFAFA"

NODE_SIZE_BASE  = 260
FONT_SIZE_LABEL = 8

_PLOT_ATTRS = ["n", "α", "d_max", "c_log", "m", "density"]


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def _extract_attr(rec: dict, name: str):
    if name == "n":       return rec["n"]
    if name == "α":       return rec["alpha"]
    if name == "d_max":   return rec["d_max"]
    if name == "c_log":   return rec.get("c_log")
    if name == "m":       return rec["m"]
    if name == "density": return rec["density"]
    return None


def _format_metrics(rec: dict) -> tuple[dict, list, list, list]:
    """
    Build the metrics display dict and return spectral arrays + degree seq
    from cache data (no recomputation needed).
    """
    m = {}
    m["Vertices"]        = str(rec["n"])
    m["Edges"]           = str(rec["m"])
    m["Density"]         = f"{rec['density']:.4f}"

    if rec["is_regular"]:
        m["Regularity"]  = f"Yes ({rec['regularity_d']}-regular)"
    else:
        deg_set = sorted(set(rec["degree_sequence"]))
        m["Regularity"]  = f"No (degs: {deg_set})"

    m["Degree range"]    = f"{rec['d_min']} – {rec['d_max']}"
    m["Avg degree"]      = f"{rec['d_avg']:.2f}"

    if rec["is_connected"]:
        m["Connected"]   = "Yes"
        m["Diameter"]    = str(rec["diameter"])
        m["Radius"]      = str(rec["radius"])
    else:
        m["Connected"]   = f"No ({rec['n_components']} components)"
        m["Diameter"]    = "∞"
        m["Radius"]      = "–"

    m["Girth"]           = str(rec["girth"]) if rec["girth"] else "∞ (acyclic)"
    m["Triangles"]       = str(rec["n_triangles"])
    m["Clustering coeff"]= f"{rec['avg_clustering']:.4f}"

    if rec["is_connected"] and rec["n"] > 1:
        m["Edge connectivity"]   = str(rec["edge_connectivity"])
        m["Vertex connectivity"] = str(rec["vertex_connectivity"])
    else:
        m["Edge connectivity"]   = "–"
        m["Vertex connectivity"] = "–"

    m["Clique number (ω)"] = str(rec["clique_num"])
    m["Chromatic bound"]   = (f"{rec['clique_num']} ≤ χ ≤ "
                               f"{rec['greedy_chromatic_bound']}")

    assort = rec.get("assortativity")
    m["Assortativity"]     = f"{assort:.4f}" if assort is not None else "–"

    sr = rec.get("spectral_radius")
    sg = rec.get("spectral_gap")
    ac = rec.get("algebraic_connectivity")
    m["Spectral radius"]        = f"{sr:.4f}" if sr is not None else "–"
    m["Spectral gap"]           = f"{sg:.4f}" if sg is not None else "–"
    m["Algebraic connectivity"] = f"{ac:.4f}" if ac is not None else "–"

    m["α (independence #)"] = str(rec["alpha"])
    m["d_max"]              = str(rec["d_max"])
    c = rec.get("c_log")
    m["c_log"]              = f"{c:.4f}" if c is not None else "–"
    b = rec.get("beta")
    m["beta"]               = f"{b:.4f}" if b is not None else "–"
    m["source"]             = rec["source"]

    eig_adj = rec.get("eigenvalues_adj", [])
    eig_lap = rec.get("eigenvalues_lap", [])
    degrees = rec.get("degree_sequence", [])
    return m, eig_adj, eig_lap, degrees


def _load_data(source_filter: str | None = None) -> dict[int, list[dict]]:
    """
    Open graph_db, sync, load all records with G+adj attached.
    Returns {n: [rec, ...]} sorted by n.
    """
    kwargs = {}
    if source_filter:
        kwargs["source"] = source_filter

    with DB() as db:
        records = db.hydrate(db.query(**kwargs))

    data: dict[int, list[dict]] = {}
    for rec in records:
        data.setdefault(rec["n"], []).append(rec)
    for n in data:
        data[n].sort(key=lambda r: (r.get("c_log") or float("inf")))
    return data


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------

class App(tk.Tk):
    def __init__(self, source_filter: str | None = None):
        super().__init__()
        self.title("K₄-Free Graph Explorer")
        self.geometry("1400x900")
        self.configure(bg=C_BG)

        self.data = _load_data(source_filter)
        if not self.data:
            msg = "No graphs found"
            if source_filter:
                msg += f" for source='{source_filter}'"
            tk.Label(self, text=msg, font=("sans-serif", 14)).pack(expand=True)
            return

        self.n_idx  = 0
        self.pt_idx = 0

        # State
        self.pos           = {}
        self.dragging      = None
        self.selected_node = None
        self.layout_name   = tk.StringVar(value="Spring")

        # Filters
        self.filter_min_clog = tk.BooleanVar(value=False)

        # Highlights
        self.hl_mis       = tk.BooleanVar(value=False)
        self.hl_triangles = tk.BooleanVar(value=False)
        self.hl_high_deg  = tk.BooleanVar(value=False)
        self.hl_neighbors = tk.BooleanVar(value=False)

        # Cross-graph plot
        self.cg_x   = tk.StringVar(value="n")
        self.cg_y   = tk.StringVar(value="c_log")
        self.cg_agg = tk.StringVar(value="min")

        # Histogram
        self.hist_var = tk.StringVar(value="c_log")

        self._recompute_view()
        self._build_ui()
        self._load_current_graph()

    # ── View ─────────────────────────────────────────────────────────────────

    def _recompute_view(self):
        if self.filter_min_clog.get():
            self._view_data: dict[int, list[dict]] = {}
            for n, pts in self.data.items():
                best = min(
                    (p for p in pts if p.get("c_log") is not None),
                    key=lambda p: p["c_log"],
                    default=None,
                )
                if best:
                    self._view_data[n] = [best]
        else:
            self._view_data = self.data

        self._view_n_values   = sorted(self._view_data.keys())
        self._view_all_points = [
            pt for n in self._view_n_values for pt in self._view_data[n]
        ]

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        pw = tk.PanedWindow(self, orient=tk.HORIZONTAL, sashwidth=10,
                            sashrelief=tk.RAISED, bg="#999",
                            sashpad=2, opaqueresize=True)
        pw.pack(fill=tk.BOTH, expand=True)
        self._paned = pw

        # Left: graph canvas
        left = tk.Frame(pw, bg=C_BG)
        pw.add(left, minsize=300, stretch="always")

        self.fig_graph = plt.Figure(figsize=(8, 7), dpi=100, facecolor=C_BG)
        self.ax_graph  = self.fig_graph.add_subplot(111)
        self.ax_graph.set_facecolor("white")
        self.ax_graph.set_aspect("equal")
        self.ax_graph.axis("off")
        self.canvas_graph = FigureCanvasTkAgg(self.fig_graph, master=left)
        self.canvas_graph.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        self.fig_graph.canvas.mpl_connect("button_press_event",   self._on_press)
        self.fig_graph.canvas.mpl_connect("motion_notify_event",  self._on_motion)
        self.fig_graph.canvas.mpl_connect("button_release_event", self._on_release)

        # Right: scrollable control panel
        right_outer = tk.Frame(pw, bg=C_BG)
        pw.add(right_outer, minsize=250, stretch="always")

        scroll_canvas = tk.Canvas(right_outer, bg=C_BG, highlightthickness=0)
        scrollbar     = ttk.Scrollbar(right_outer, orient=tk.VERTICAL,
                                      command=scroll_canvas.yview)
        self.right_panel = tk.Frame(scroll_canvas, bg=C_BG)

        self.right_panel.bind(
            "<Configure>",
            lambda e: scroll_canvas.configure(
                scrollregion=scroll_canvas.bbox("all")))
        scroll_canvas.create_window((0, 0), window=self.right_panel, anchor="nw")
        scroll_canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        scroll_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        def _mw(event):
            scroll_canvas.yview_scroll(
                -1 * (event.delta // 120 or (1 if event.num == 4 else -1)), "units")
        scroll_canvas.bind_all("<MouseWheel>", _mw)
        scroll_canvas.bind_all("<Button-4>",  _mw)
        scroll_canvas.bind_all("<Button-5>",  _mw)

        rp = self.right_panel

        # Graph selector
        self._section_label(rp, "Graph Selector")
        sel = tk.Frame(rp, bg=C_BG)
        sel.pack(fill=tk.X, padx=8, pady=2)

        tk.Label(sel, text="n:", bg=C_BG, font=("sans-serif", 11)).pack(side=tk.LEFT)
        tk.Button(sel, text="◄", width=2, command=self._prev_n).pack(side=tk.LEFT)
        self.lbl_n = tk.Label(sel, text="", bg=C_BG,
                               font=("sans-serif", 12, "bold"), width=4)
        self.lbl_n.pack(side=tk.LEFT)
        tk.Button(sel, text="►", width=2, command=self._next_n).pack(side=tk.LEFT)

        tk.Label(sel, text="   Point:", bg=C_BG,
                 font=("sans-serif", 11)).pack(side=tk.LEFT)
        tk.Button(sel, text="◄", width=2, command=self._prev_pt).pack(side=tk.LEFT)
        self.lbl_pt = tk.Label(sel, text="", bg=C_BG,
                                font=("sans-serif", 12, "bold"), width=6)
        self.lbl_pt.pack(side=tk.LEFT)
        tk.Button(sel, text="►", width=2, command=self._next_pt).pack(side=tk.LEFT)

        self.lbl_summary = tk.Label(rp, text="", bg=C_BG, font=("sans-serif", 10),
                                     anchor="w", justify=tk.LEFT)
        self.lbl_summary.pack(fill=tk.X, padx=8, pady=(0, 2))

        filter_frame = tk.Frame(rp, bg=C_BG)
        filter_frame.pack(fill=tk.X, padx=8, pady=(0, 4))
        tk.Checkbutton(filter_frame, text="Only show min c_log per n",
                       variable=self.filter_min_clog, bg=C_BG,
                       font=("sans-serif", 9, "bold"),
                       command=self._on_filter_changed).pack(side=tk.LEFT)

        # Layout
        self._section_label(rp, "Layout")
        lay = tk.Frame(rp, bg=C_BG)
        lay.pack(fill=tk.X, padx=8, pady=2)
        for name in ["Spring", "Circular", "Shell", "Kamada-Kawai"]:
            tk.Radiobutton(lay, text=name, variable=self.layout_name, value=name,
                           bg=C_BG, command=self._on_layout_changed).pack(
                               side=tk.LEFT, padx=4)

        # Highlights
        self._section_label(rp, "Highlights")
        hl = tk.Frame(rp, bg=C_BG)
        hl.pack(fill=tk.X, padx=8, pady=2)
        for var, text, color in [
            (self.hl_mis,       "Max Independent Set",          C_MIS),
            (self.hl_triangles, "Triangles",                    C_TRIANGLE),
            (self.hl_high_deg,  "High-degree vertices",         C_HIGH_DEG),
            (self.hl_neighbors, "Click-to-select neighborhood", C_NEIGHBOR),
        ]:
            f = tk.Frame(hl, bg=C_BG)
            f.pack(fill=tk.X, pady=1)
            tk.Canvas(f, width=14, height=14, bg=color,
                      highlightthickness=1,
                      highlightbackground="#888").pack(side=tk.LEFT, padx=(0, 6))
            tk.Checkbutton(f, text=text, variable=var, bg=C_BG,
                           command=self._on_highlight_changed).pack(side=tk.LEFT)

        # Metrics
        self._section_label(rp, "Metrics")
        self.metrics_text = tk.Text(rp, height=22, width=42,
                                     font=("Consolas", 10), bg="white",
                                     relief=tk.GROOVE, bd=1, state=tk.DISABLED)
        self.metrics_text.pack(fill=tk.X, padx=8, pady=2)

        # Degree distribution
        self._section_label(rp, "Degree Distribution")
        self.fig_deg = plt.Figure(figsize=(3.8, 2.2), dpi=100, facecolor=C_BG)
        self.ax_deg  = self.fig_deg.add_subplot(111)
        self.canvas_deg = FigureCanvasTkAgg(self.fig_deg, master=rp)
        self.canvas_deg.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=8, pady=2)

        # Adjacency spectrum
        self._section_label(rp, "Adjacency Spectrum")
        self.fig_eig = plt.Figure(figsize=(3.8, 2.2), dpi=100, facecolor=C_BG)
        self.ax_eig  = self.fig_eig.add_subplot(111)
        self.canvas_eig = FigureCanvasTkAgg(self.fig_eig, master=rp)
        self.canvas_eig.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=8, pady=2)

        # Laplacian spectrum
        self._section_label(rp, "Laplacian Spectrum")
        self.fig_lap = plt.Figure(figsize=(3.8, 2.2), dpi=100, facecolor=C_BG)
        self.ax_lap  = self.fig_lap.add_subplot(111)
        self.canvas_lap = FigureCanvasTkAgg(self.fig_lap, master=rp)
        self.canvas_lap.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=8, pady=2)

        # Cross-graph scatter
        self._section_label(rp, "Cross-Graph Plot (All Points)")
        cg_ctrl = tk.Frame(rp, bg=C_BG)
        cg_ctrl.pack(fill=tk.X, padx=8, pady=2)

        tk.Label(cg_ctrl, text="X:", bg=C_BG, font=("sans-serif", 9)).pack(side=tk.LEFT)
        cg_x_menu = ttk.Combobox(cg_ctrl, textvariable=self.cg_x,
                                  values=_PLOT_ATTRS, width=8, state="readonly")
        cg_x_menu.pack(side=tk.LEFT, padx=(2, 8))

        tk.Label(cg_ctrl, text="Y:", bg=C_BG, font=("sans-serif", 9)).pack(side=tk.LEFT)
        cg_y_menu = ttk.Combobox(cg_ctrl, textvariable=self.cg_y,
                                  values=_PLOT_ATTRS, width=8, state="readonly")
        cg_y_menu.pack(side=tk.LEFT, padx=(2, 8))

        tk.Label(cg_ctrl, text="Best:", bg=C_BG,
                 font=("sans-serif", 9)).pack(side=tk.LEFT)
        tk.Radiobutton(cg_ctrl, text="min", variable=self.cg_agg, value="min",
                       bg=C_BG, command=self._draw_cross_graph).pack(side=tk.LEFT)
        tk.Radiobutton(cg_ctrl, text="max", variable=self.cg_agg, value="max",
                       bg=C_BG, command=self._draw_cross_graph).pack(side=tk.LEFT)

        cg_x_menu.bind("<<ComboboxSelected>>", lambda e: self._draw_cross_graph())
        cg_y_menu.bind("<<ComboboxSelected>>", lambda e: self._draw_cross_graph())

        self.fig_cg = plt.Figure(figsize=(3.8, 2.4), dpi=100, facecolor=C_BG)
        self.ax_cg  = self.fig_cg.add_subplot(111)
        self.canvas_cg = FigureCanvasTkAgg(self.fig_cg, master=rp)
        self.canvas_cg.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=8, pady=2)

        # Histogram
        self._section_label(rp, "Histogram (All Points)")
        hist_ctrl = tk.Frame(rp, bg=C_BG)
        hist_ctrl.pack(fill=tk.X, padx=8, pady=2)

        tk.Label(hist_ctrl, text="Variable:", bg=C_BG,
                 font=("sans-serif", 9)).pack(side=tk.LEFT)
        hist_menu = ttk.Combobox(hist_ctrl, textvariable=self.hist_var,
                                  values=_PLOT_ATTRS, width=10, state="readonly")
        hist_menu.pack(side=tk.LEFT, padx=(2, 0))
        hist_menu.bind("<<ComboboxSelected>>", lambda e: self._draw_histogram())

        self.fig_hist = plt.Figure(figsize=(3.8, 2.4), dpi=100, facecolor=C_BG)
        self.ax_hist  = self.fig_hist.add_subplot(111)
        self.canvas_hist = FigureCanvasTkAgg(self.fig_hist, master=rp)
        self.canvas_hist.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=8, pady=2)

        # Keyboard shortcuts
        self.bind("<Left>",  lambda e: self._prev_pt())
        self.bind("<Right>", lambda e: self._next_pt())
        self.bind("<Up>",    lambda e: self._next_n())
        self.bind("<Down>",  lambda e: self._prev_n())

        self.after(100, lambda: self._paned.sash_place(0, int(self.winfo_width() * 0.6), 0))

    def _section_label(self, parent, text):
        f = tk.Frame(parent, bg="#E0E0E0")
        f.pack(fill=tk.X, padx=4, pady=(8, 2))
        tk.Label(f, text=text, bg="#E0E0E0", font=("sans-serif", 10, "bold"),
                 anchor="w").pack(fill=tk.X, padx=4, pady=2)

    # ── Filter ────────────────────────────────────────────────────────────────

    def _on_filter_changed(self):
        cur_n = self._view_n_values[self.n_idx] if self._view_n_values else None
        self._recompute_view()
        if cur_n is not None and cur_n in self._view_data:
            self.n_idx = self._view_n_values.index(cur_n)
        else:
            self.n_idx = 0
        self.pt_idx = 0
        self._load_current_graph()

    # ── Navigation ────────────────────────────────────────────────────────────

    def _current_point(self) -> dict:
        return self._view_data[self._view_n_values[self.n_idx]][self.pt_idx]

    def _prev_n(self):
        if self.n_idx > 0:
            self.n_idx -= 1; self.pt_idx = 0; self._load_current_graph()

    def _next_n(self):
        if self.n_idx < len(self._view_n_values) - 1:
            self.n_idx += 1; self.pt_idx = 0; self._load_current_graph()

    def _prev_pt(self):
        if self.pt_idx > 0:
            self.pt_idx -= 1; self._load_current_graph()

    def _next_pt(self):
        n = self._view_n_values[self.n_idx]
        if self.pt_idx < len(self._view_data[n]) - 1:
            self.pt_idx += 1; self._load_current_graph()

    # ── Graph loading ─────────────────────────────────────────────────────────

    def _load_current_graph(self):
        rec = self._current_point()
        n   = self._view_n_values[self.n_idx]
        total = len(self._view_data[n])

        self.lbl_n.config(text=str(n))
        self.lbl_pt.config(text=f"{self.pt_idx + 1}/{total}")

        c = rec.get("c_log")
        c_str = f"{c:.4f}" if c is not None else "–"
        method = rec.get("metadata", {}).get("method", "?")
        self.lbl_summary.config(
            text=f"α={rec['alpha']}, d_max={rec['d_max']}, "
                 f"c_log={c_str}, edges={rec['m']}, "
                 f"source={rec['source']}, method={method}"
        )

        self._compute_layout(rec)
        self.selected_node = None

        metrics, eig_adj, eig_lap, degrees = _format_metrics(rec)

        self.metrics_text.config(state=tk.NORMAL)
        self.metrics_text.delete("1.0", tk.END)
        for key, val in metrics.items():
            self.metrics_text.insert(tk.END, f"{key:.<28s} {val}\n")
        self.metrics_text.config(state=tk.DISABLED)

        self._draw_degree_dist(degrees)
        self._draw_eigenvalues(eig_adj, self.ax_eig, self.canvas_eig, "Adjacency eigenvalues")
        self._draw_eigenvalues(eig_lap, self.ax_lap, self.canvas_lap, "Laplacian eigenvalues")
        self._draw_cross_graph()
        self._draw_histogram()
        self._draw_graph()

    def _compute_layout(self, rec: dict):
        G    = rec["G"]
        name = self.layout_name.get()
        if name == "Circular":
            self.pos = nx.circular_layout(G)
        elif name == "Shell":
            degs   = dict(G.degree())
            shells = [
                [v for v, d in degs.items() if d == deg]
                for deg in sorted(set(degs.values()), reverse=True)
            ] if degs else []
            self.pos = nx.shell_layout(G, nlist=shells) if shells else nx.circular_layout(G)
        elif name == "Kamada-Kawai":
            self.pos = nx.kamada_kawai_layout(G)
        else:
            self.pos = nx.spring_layout(
                G, seed=42,
                k=1.5 / max(1, G.number_of_nodes() ** 0.5),
                iterations=80,
            )

    def _on_layout_changed(self):
        self._compute_layout(self._current_point())
        self._draw_graph()

    def _on_highlight_changed(self):
        self._draw_graph()

    # ── Drawing ───────────────────────────────────────────────────────────────

    def _draw_graph(self):
        ax = self.ax_graph
        ax.clear()
        ax.set_facecolor("white")
        ax.axis("off")

        rec = self._current_point()
        G   = rec["G"]

        if G.number_of_nodes() == 0:
            self.canvas_graph.draw_idle()
            return

        node_colors, node_edge_colors, node_edge_widths = self._compute_node_colors(rec)
        edge_colors, edge_widths                        = self._compute_edge_colors(rec)

        n         = G.number_of_nodes()
        node_size = max(80, NODE_SIZE_BASE - n * 5)
        font_size = max(6, FONT_SIZE_LABEL - max(0, n - 20) // 5)

        edge_list = list(G.edges())
        if edge_list:
            nx.draw_networkx_edges(G, self.pos, ax=ax, edgelist=edge_list,
                                    edge_color=edge_colors, width=edge_widths, alpha=0.7)

        nx.draw_networkx_nodes(G, self.pos, ax=ax, node_color=node_colors,
                                node_size=node_size, edgecolors=node_edge_colors,
                                linewidths=node_edge_widths)
        nx.draw_networkx_labels(G, self.pos, ax=ax, font_size=font_size,
                                 font_color="white", font_weight="bold")

        c = rec.get("c_log")
        c_str = f"c_log={c:.4f}" if c is not None else ""
        ax.set_title(
            f"n={rec['n']}, α={rec['alpha']}, d_max={rec['d_max']}  {c_str}",
            fontsize=12, fontweight="bold", pad=10,
        )

        self.fig_graph.tight_layout()
        self.canvas_graph.draw_idle()

    def _compute_node_colors(self, rec: dict):
        G     = rec["G"]
        nodes = list(G.nodes())
        n     = len(nodes)

        colors      = [C_NODE]    * n
        edge_colors = ["#333333"] * n
        edge_widths = [1.0]       * n

        any_hl = (self.hl_mis.get() or self.hl_triangles.get() or
                  self.hl_high_deg.get() or
                  (self.hl_neighbors.get() and self.selected_node is not None))
        if any_hl:
            colors      = [C_DIM]    * n
            edge_colors = ["#AAAAAA"] * n

        if self.hl_mis.get():
            mis_set = set(rec["mis_vertices"])
            for i, v in enumerate(nodes):
                if v in mis_set:
                    colors[i]      = C_MIS
                    edge_colors[i] = "#922B21"
                    edge_widths[i] = 2.5

        if self.hl_triangles.get():
            tri_verts = set(rec["triangle_vertices"])
            for i, v in enumerate(nodes):
                if v in tri_verts:
                    if colors[i] == C_DIM:
                        colors[i] = C_TRIANGLE
                    edge_colors[i] = "#B7950B"
                    edge_widths[i] = 2.0

        if self.hl_high_deg.get():
            hdv = set(rec["high_degree_vertices"])
            for i, v in enumerate(nodes):
                if v in hdv:
                    if colors[i] == C_DIM:
                        colors[i] = C_HIGH_DEG
                    edge_colors[i] = "#1E8449"
                    edge_widths[i] = 2.5

        if self.hl_neighbors.get() and self.selected_node is not None:
            sv   = self.selected_node
            nbrs = set(G.neighbors(sv))
            for i, v in enumerate(nodes):
                if v == sv:
                    colors[i]      = C_SELECTED
                    edge_colors[i] = "#6C3483"
                    edge_widths[i] = 3.0
                elif v in nbrs:
                    if colors[i] == C_DIM:
                        colors[i] = C_NEIGHBOR
                    edge_colors[i] = "#B7950B"
                    edge_widths[i] = 2.0

        return colors, edge_colors, edge_widths

    def _compute_edge_colors(self, rec: dict):
        G     = rec["G"]
        edges = list(G.edges())
        colors = [C_EDGE] * len(edges)
        widths = [1.2]    * len(edges)

        if self.hl_triangles.get():
            tri_edge_set = {tuple(e) for e in rec["triangle_edges"]}
            for i, (u, v) in enumerate(edges):
                if (min(u, v), max(u, v)) in tri_edge_set:
                    colors[i] = C_EDGE_TRI
                    widths[i] = 2.5

        if self.hl_neighbors.get() and self.selected_node is not None:
            sv = self.selected_node
            for i, (u, v) in enumerate(edges):
                if u == sv or v == sv:
                    colors[i] = C_SELECTED
                    widths[i] = 2.5

        return colors, widths

    # ── Drag ──────────────────────────────────────────────────────────────────

    def _on_press(self, event):
        if event.inaxes != self.ax_graph or event.xdata is None:
            return
        G        = self._current_point()["G"]
        min_dist = float("inf")
        closest  = None
        for node, (x, y) in self.pos.items():
            d = (x - event.xdata) ** 2 + (y - event.ydata) ** 2
            if d < min_dist:
                min_dist = d; closest = node

        if closest is not None:
            xlim      = self.ax_graph.get_xlim()
            threshold = ((xlim[1] - xlim[0]) * 0.04) ** 2
            if min_dist < threshold and event.button == 1:
                self.dragging = closest
                if self.hl_neighbors.get():
                    self.selected_node = closest
                    self._draw_graph()

    def _on_motion(self, event):
        if self.dragging is None or event.inaxes != self.ax_graph or event.xdata is None:
            return
        self.pos[self.dragging] = (event.xdata, event.ydata)
        self._draw_graph()

    def _on_release(self, _event):
        self.dragging = None

    # ── Charts ────────────────────────────────────────────────────────────────

    def _draw_degree_dist(self, degrees):
        ax = self.ax_deg
        ax.clear()
        if not degrees:
            self.canvas_deg.draw_idle()
            return
        counts = Counter(degrees)
        xs = sorted(counts.keys())
        ax.bar(xs, [counts[d] for d in xs], color=C_NODE, edgecolor="#333", linewidth=0.5)
        ax.set_xlabel("Degree", fontsize=8)
        ax.set_ylabel("Count",  fontsize=8)
        ax.set_xticks(xs)
        ax.tick_params(labelsize=7)
        self.fig_deg.tight_layout()
        self.canvas_deg.draw_idle()

    def _draw_eigenvalues(self, eigenvalues, ax, canvas, title):
        ax.clear()
        if not eigenvalues:
            canvas.draw_idle()
            return
        ax.stem(range(len(eigenvalues)), eigenvalues,
                linefmt="-", markerfmt="o", basefmt="k-")
        ax.axhline(y=0, color="gray", linewidth=0.5, linestyle="--")
        ax.set_xlabel("Index", fontsize=8)
        ax.set_ylabel("λ",     fontsize=8)
        ax.tick_params(labelsize=7)
        ax.set_title(title, fontsize=8, pad=4)
        ax.get_figure().tight_layout()
        canvas.draw_idle()

    def _draw_cross_graph(self):
        ax     = self.ax_cg
        ax.clear()
        x_name = self.cg_x.get()
        y_name = self.cg_y.get()
        agg_fn = min if self.cg_agg.get() == "min" else max

        groups:  dict = {}
        all_xy:  list = []
        for pt in self._view_all_points:
            xv = _extract_attr(pt, x_name)
            yv = _extract_attr(pt, y_name)
            if xv is None or yv is None:
                continue
            all_xy.append((xv, yv))
            groups.setdefault(xv, []).append(yv)

        if not groups:
            ax.set_title(f"No data for {x_name} vs {y_name}", fontsize=8)
            self.fig_cg.tight_layout()
            self.canvas_cg.draw_idle()
            return

        ax.scatter([t[0] for t in all_xy], [t[1] for t in all_xy],
                   s=15, color=C_DIM, edgecolors="#AAA", linewidths=0.5,
                   zorder=1, label="all")

        best_x = sorted(groups.keys())
        best_y = [agg_fn(groups[xv]) for xv in best_x]
        ax.plot(best_x, best_y, "o-", color=C_NODE, markersize=5,
                linewidth=1.5, zorder=2, label=f"{self.cg_agg.get()}({y_name})")

        cur = self._current_point()
        cx  = _extract_attr(cur, x_name)
        cy  = _extract_attr(cur, y_name)
        if cx is not None and cy is not None:
            ax.scatter([cx], [cy], s=80, color=C_MIS, edgecolors="#922B21",
                       linewidths=2, zorder=3, marker="*", label="current")

        ax.set_xlabel(x_name, fontsize=8)
        ax.set_ylabel(f"{self.cg_agg.get()}({y_name})", fontsize=8)
        ax.tick_params(labelsize=7)
        ax.legend(fontsize=6, loc="best")
        ax.grid(True, alpha=0.3)
        self.fig_cg.tight_layout()
        self.canvas_cg.draw_idle()

    def _draw_histogram(self):
        ax       = self.ax_hist
        var_name = self.hist_var.get()
        ax.clear()

        values = [
            v for pt in self._view_all_points
            if (v := _extract_attr(pt, var_name)) is not None
        ]
        if not values:
            ax.set_title(f"No data for {var_name}", fontsize=8)
            self.fig_hist.tight_layout()
            self.canvas_hist.draw_idle()
            return

        unique = sorted(set(values))
        if all(v == int(v) for v in values) and len(unique) <= 30:
            bins = range(int(min(values)), int(max(values)) + 2)
        else:
            bins = min(20, max(5, len(values) // 3))

        ax.hist(values, bins=bins, color=C_NODE, edgecolor="#333",
                linewidth=0.5, alpha=0.85)

        cur = self._current_point()
        cv  = _extract_attr(cur, var_name)
        if cv is not None:
            ax.axvline(cv, color=C_MIS, linewidth=2, linestyle="--",
                       label=f"current={cv}")
            ax.legend(fontsize=6, loc="best")

        ax.set_xlabel(var_name, fontsize=8)
        ax.set_ylabel("Count",  fontsize=8)
        ax.tick_params(labelsize=7)
        self.fig_hist.tight_layout()
        self.canvas_hist.draw_idle()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    import argparse
    parser = argparse.ArgumentParser(description="K₄-Free Graph Explorer")
    parser.add_argument("--source", default=None,
                        help="Filter by source tag (e.g. sat_pareto)")
    args = parser.parse_args()
    App(source_filter=args.source).mainloop()


if __name__ == "__main__":
    main()
