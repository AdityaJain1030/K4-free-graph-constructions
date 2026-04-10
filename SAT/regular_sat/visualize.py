"""Interactive K4-free graph visualizer for regular_sat results.

Usage:
    python -m regular_sat.visualize
    python -m regular_sat.visualize --results-dir path/to/results
"""

import argparse
import json
import os
import sys
import warnings
from collections import Counter, deque

import numpy as np
import networkx as nx
warnings.filterwarnings("ignore", category=RuntimeWarning, module="networkx")

import tkinter as tk
from tkinter import ttk

import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from k4free_ilp.alpha_exact import alpha_exact
from k4free_ilp.k4_check import find_k4

# ---------------------------------------------------------------------------
# Colors
# ---------------------------------------------------------------------------
C_NODE = "#4A90D9"
C_MIS = "#E74C3C"
C_TRIANGLE = "#F39C12"
C_HIGH_DEG = "#2ECC71"
C_SELECTED = "#9B59B6"
C_NEIGHBOR = "#F1C40F"
C_DIM = "#D5DBDB"
C_EDGE = "#B0BEC5"
C_EDGE_TRI = "#E67E22"
C_BG = "#FAFAFA"

NODE_SIZE_BASE = 260
FONT_SIZE_LABEL = 8

# Plottable attributes across all Pareto points
_PLOT_ATTRS = ["n", "α", "d_max", "c_log", "edges", "density"]


def _extract_attr(point, name):
    """Extract a numeric attribute from a Pareto point. Returns None if unavailable."""
    if name == "n":
        return point["n"]
    if name == "α":
        return point["alpha"]
    if name == "d_max":
        return point["d_max"]
    if name == "c_log":
        return point.get("c_log")
    if name == "edges":
        return len(point["edges"])
    if name == "density":
        n = point["n"]
        return 2 * len(point["edges"]) / (n * (n - 1)) if n > 1 else 0
    return None

# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_all_results(results_dir):
    """Load all n*_a*.json result files. Returns {n: [point_dicts]} sorted by n."""
    data = {}
    if not os.path.isdir(results_dir):
        return data
    for fname in sorted(os.listdir(results_dir)):
        if not fname.endswith(".json"):
            continue
        # Accept n{N}_a{alpha}.json (regular_sat format)
        if not (fname.startswith("n") and "_a" in fname):
            continue
        with open(os.path.join(results_dir, fname)) as f:
            raw = json.load(f)
        if raw.get("edges") is None:
            continue  # skip infeasible results
        n = raw["n"]
        edges = [tuple(e) for e in raw["edges"]]
        adj = np.zeros((n, n), dtype=np.uint8)
        for i, j in edges:
            adj[i, j] = adj[j, i] = 1
        G = nx.from_numpy_array(adj)
        point = {**raw, "edges": edges, "adj": adj, "G": G, "n": n}
        if n not in data:
            data[n] = []
        data[n].append(point)
    return data


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def compute_girth(G):
    """Shortest cycle via BFS from each vertex."""
    girth = float("inf")
    for v in G.nodes():
        dist = {v: 0}
        queue = deque([(v, -1)])
        while queue:
            u, parent = queue.popleft()
            for w in G.neighbors(u):
                if w == parent:
                    continue
                if w in dist:
                    girth = min(girth, dist[u] + dist[w] + 1)
                else:
                    dist[w] = dist[u] + 1
                    queue.append((w, u))
            if girth == 3:
                return 3
    return girth if girth < float("inf") else None


def compute_metrics(point):
    """Compute all metrics for a Pareto point. Returns dict of metric strings."""
    G = point["G"]
    adj = point["adj"]
    n = point["n"]
    num_edges = G.number_of_edges()
    degrees = [d for _, d in G.degree()]
    deg_set = sorted(set(degrees))
    d_max = max(degrees) if degrees else 0
    d_min = min(degrees) if degrees else 0

    m = {}
    m["Vertices"] = str(n)
    m["Edges"] = str(num_edges)
    m["Density"] = f"{nx.density(G):.4f}"

    if len(deg_set) == 1:
        m["Regularity"] = f"Yes ({deg_set[0]}-regular)"
    else:
        m["Regularity"] = f"No (degs: {deg_set})"

    m["Degree range"] = f"{d_min} – {d_max}"
    m["Avg degree"] = f"{np.mean(degrees):.2f}"

    if nx.is_connected(G):
        m["Connected"] = "Yes"
        m["Diameter"] = str(nx.diameter(G))
        m["Radius"] = str(nx.radius(G))
    else:
        cc = nx.number_connected_components(G)
        m["Connected"] = f"No ({cc} components)"
        m["Diameter"] = "∞"
        m["Radius"] = "–"

    girth = compute_girth(G)
    m["Girth"] = str(girth) if girth else "∞ (acyclic)"

    tri_count = sum(nx.triangles(G).values()) // 3
    m["Triangles"] = str(tri_count)
    m["Clustering coeff"] = f"{nx.average_clustering(G):.4f}"

    if nx.is_connected(G) and n > 1:
        m["Edge connectivity"] = str(nx.edge_connectivity(G))
        m["Vertex connectivity"] = str(nx.node_connectivity(G))
    else:
        m["Edge connectivity"] = "–"
        m["Vertex connectivity"] = "–"

    clique_num = max(len(c) for c in nx.find_cliques(G)) if G.number_of_nodes() > 0 else 0
    greedy_colors = len(set(nx.greedy_color(G, strategy="largest_first").values())) if G.number_of_nodes() > 0 else 0
    m["Clique number (ω)"] = str(clique_num)
    m["Chromatic bound"] = f"{clique_num} ≤ χ ≤ {greedy_colors}"

    try:
        assort = nx.degree_assortativity_coefficient(G)
        m["Assortativity"] = f"{assort:.4f}" if np.isfinite(assort) else "– (regular)"
    except Exception:
        m["Assortativity"] = "–"

    # Spectral
    adj_f = adj.astype(float)
    eig_adj = np.sort(np.linalg.eigvalsh(adj_f))[::-1]
    m["Spectral radius"] = f"{eig_adj[0]:.4f}"
    m["Spectral gap"] = f"{eig_adj[0] - eig_adj[1]:.4f}" if len(eig_adj) > 1 else "–"

    L = np.diag(degrees) - adj_f
    eig_lap = np.sort(np.linalg.eigvalsh(L))
    fiedler = eig_lap[1] if len(eig_lap) > 1 else 0
    m["Algebraic connectivity"] = f"{fiedler:.4f}"

    m["α (independence #)"] = str(point["alpha"])
    m["d_max"] = str(point["d_max"])
    c_log = point.get("c_log")
    m["c_log"] = f"{c_log:.4f}" if c_log is not None else "–"

    return m, eig_adj, eig_lap, degrees


# ---------------------------------------------------------------------------
# Highlight computations
# ---------------------------------------------------------------------------

def get_mis_vertices(adj):
    _, verts = alpha_exact(adj)
    return set(verts)


def get_triangle_edges(G):
    """Return set of edges that participate in at least one triangle."""
    tri_edges = set()
    tri_verts = set()
    for u, v, w in _iter_triangles(G):
        tri_edges.add((min(u, v), max(u, v)))
        tri_edges.add((min(u, w), max(u, w)))
        tri_edges.add((min(v, w), max(v, w)))
        tri_verts.update([u, v, w])
    return tri_edges, tri_verts


def _iter_triangles(G):
    """Yield all triangles (u, v, w) with u < v < w."""
    adj = {n: set(G.neighbors(n)) for n in G.nodes()}
    for u in G.nodes():
        for v in adj[u]:
            if v <= u:
                continue
            for w in adj[u] & adj[v]:
                if w <= v:
                    continue
                yield u, v, w


def get_high_degree_verts(G):
    """Vertices with max degree."""
    degs = dict(G.degree())
    mx = max(degs.values())
    return {v for v, d in degs.items() if d == mx}


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------

class App(tk.Tk):
    def __init__(self, results_dir):
        super().__init__()
        self.title("K₄-Free Graph Explorer")
        self.geometry("1400x900")
        self.configure(bg=C_BG)

        self.data = load_all_results(results_dir)
        if not self.data:
            tk.Label(self, text=f"No pareto_n*.json files in {results_dir}",
                     font=("sans-serif", 14)).pack(expand=True)
            return

        self.n_idx = 0
        self.pt_idx = 0

        # Current state
        self.pos = {}
        self.dragging = None
        self.selected_node = None
        self.layout_name = tk.StringVar(value="Spring")

        # Filter toggle
        self.filter_min_clog = tk.BooleanVar(value=False)

        # Highlight toggles
        self.hl_mis = tk.BooleanVar(value=False)
        self.hl_triangles = tk.BooleanVar(value=False)
        self.hl_high_deg = tk.BooleanVar(value=False)
        self.hl_neighbors = tk.BooleanVar(value=False)

        # Cached highlight data
        self._mis_cache = None
        self._tri_cache = None
        self._high_deg_cache = None

        # Cross-graph plot controls
        self.cg_x = tk.StringVar(value="n")
        self.cg_y = tk.StringVar(value="c_log")
        self.cg_agg = tk.StringVar(value="min")

        # Histogram control
        self.hist_var = tk.StringVar(value="c_log")

        # Build view (filtered or full)
        self._recompute_view()

        self._build_ui()
        self._load_current_graph()

    def _recompute_view(self):
        """Rebuild the active view data based on the min-c_log filter."""
        if self.filter_min_clog.get():
            self._view_data = {}
            for n, pts in self.data.items():
                best = None
                for pt in pts:
                    c = pt.get("c_log")
                    if c is not None and (best is None or c < best.get("c_log")):
                        best = pt
                if best is not None:
                    self._view_data[n] = [best]
        else:
            self._view_data = self.data

        self._view_n_values = sorted(self._view_data.keys())
        self._view_all_points = []
        for n in self._view_n_values:
            for pt in self._view_data[n]:
                self._view_all_points.append(pt)

    # ---- UI construction ----

    def _build_ui(self):
        # Main paned window — drag the sash to resize left/right panes
        pw = tk.PanedWindow(self, orient=tk.HORIZONTAL, sashwidth=10,
                            sashrelief=tk.RAISED, bg="#999",
                            sashpad=2, opaqueresize=True)
        pw.pack(fill=tk.BOTH, expand=True)
        self._paned = pw

        # Left: graph figure
        left = tk.Frame(pw, bg=C_BG)
        pw.add(left, minsize=300, stretch="always")

        self.fig_graph = plt.Figure(figsize=(8, 7), dpi=100, facecolor=C_BG)
        self.ax_graph = self.fig_graph.add_subplot(111)
        self.ax_graph.set_facecolor("white")
        self.ax_graph.set_aspect("equal")
        self.ax_graph.axis("off")
        self.canvas_graph = FigureCanvasTkAgg(self.fig_graph, master=left)
        self.canvas_graph.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        # Connect drag events
        self.fig_graph.canvas.mpl_connect("button_press_event", self._on_press)
        self.fig_graph.canvas.mpl_connect("motion_notify_event", self._on_motion)
        self.fig_graph.canvas.mpl_connect("button_release_event", self._on_release)

        # Right: scrollable control panel
        right_outer = tk.Frame(pw, bg=C_BG)
        pw.add(right_outer, minsize=250, stretch="always")

        canvas_scroll = tk.Canvas(right_outer, bg=C_BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(right_outer, orient=tk.VERTICAL, command=canvas_scroll.yview)
        self.right_panel = tk.Frame(canvas_scroll, bg=C_BG)

        self.right_panel.bind("<Configure>",
            lambda e: canvas_scroll.configure(scrollregion=canvas_scroll.bbox("all")))
        canvas_scroll.create_window((0, 0), window=self.right_panel, anchor="nw")
        canvas_scroll.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas_scroll.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Bind mousewheel on the scrollable area
        def _on_mousewheel(event):
            canvas_scroll.yview_scroll(-1 * (event.delta // 120 or (1 if event.num == 4 else -1)), "units")
        canvas_scroll.bind_all("<MouseWheel>", _on_mousewheel)
        canvas_scroll.bind_all("<Button-4>", _on_mousewheel)
        canvas_scroll.bind_all("<Button-5>", _on_mousewheel)

        rp = self.right_panel

        # --- Graph selector ---
        self._section_label(rp, "Graph Selector")

        sel_frame = tk.Frame(rp, bg=C_BG)
        sel_frame.pack(fill=tk.X, padx=8, pady=2)

        tk.Label(sel_frame, text="n:", bg=C_BG, font=("sans-serif", 11)).pack(side=tk.LEFT)
        tk.Button(sel_frame, text="◄", width=2, command=self._prev_n).pack(side=tk.LEFT)
        self.lbl_n = tk.Label(sel_frame, text="", bg=C_BG, font=("sans-serif", 12, "bold"), width=4)
        self.lbl_n.pack(side=tk.LEFT)
        tk.Button(sel_frame, text="►", width=2, command=self._next_n).pack(side=tk.LEFT)

        tk.Label(sel_frame, text="   Point:", bg=C_BG, font=("sans-serif", 11)).pack(side=tk.LEFT)
        tk.Button(sel_frame, text="◄", width=2, command=self._prev_pt).pack(side=tk.LEFT)
        self.lbl_pt = tk.Label(sel_frame, text="", bg=C_BG, font=("sans-serif", 12, "bold"), width=6)
        self.lbl_pt.pack(side=tk.LEFT)
        tk.Button(sel_frame, text="►", width=2, command=self._next_pt).pack(side=tk.LEFT)

        self.lbl_summary = tk.Label(rp, text="", bg=C_BG, font=("sans-serif", 10),
                                     anchor="w", justify=tk.LEFT)
        self.lbl_summary.pack(fill=tk.X, padx=8, pady=(0, 2))

        filter_frame = tk.Frame(rp, bg=C_BG)
        filter_frame.pack(fill=tk.X, padx=8, pady=(0, 4))
        tk.Checkbutton(filter_frame, text="Only show min c_log per n",
                       variable=self.filter_min_clog, bg=C_BG,
                       font=("sans-serif", 9, "bold"),
                       command=self._on_filter_changed).pack(side=tk.LEFT)

        # --- Layout selector ---
        self._section_label(rp, "Layout")
        layout_frame = tk.Frame(rp, bg=C_BG)
        layout_frame.pack(fill=tk.X, padx=8, pady=2)
        for name in ["Spring", "Circular", "Shell", "Kamada-Kawai"]:
            tk.Radiobutton(layout_frame, text=name, variable=self.layout_name, value=name,
                           bg=C_BG, command=self._on_layout_changed).pack(side=tk.LEFT, padx=4)

        # --- Highlight controls ---
        self._section_label(rp, "Highlights")
        hl_frame = tk.Frame(rp, bg=C_BG)
        hl_frame.pack(fill=tk.X, padx=8, pady=2)

        for var, text, color in [
            (self.hl_mis, "Max Independent Set", C_MIS),
            (self.hl_triangles, "Triangles", C_TRIANGLE),
            (self.hl_high_deg, "High-degree vertices", C_HIGH_DEG),
            (self.hl_neighbors, "Click-to-select neighborhood", C_NEIGHBOR),
        ]:
            f = tk.Frame(hl_frame, bg=C_BG)
            f.pack(fill=tk.X, pady=1)
            swatch = tk.Canvas(f, width=14, height=14, bg=color, highlightthickness=1,
                               highlightbackground="#888")
            swatch.pack(side=tk.LEFT, padx=(0, 6))
            tk.Checkbutton(f, text=text, variable=var, bg=C_BG,
                           command=self._on_highlight_changed).pack(side=tk.LEFT)

        # --- Metrics ---
        self._section_label(rp, "Metrics")
        self.metrics_text = tk.Text(rp, height=20, width=42, font=("Consolas", 10),
                                     bg="white", relief=tk.GROOVE, bd=1, state=tk.DISABLED)
        self.metrics_text.pack(fill=tk.X, padx=8, pady=2)

        # --- Degree distribution ---
        self._section_label(rp, "Degree Distribution")
        self.fig_deg = plt.Figure(figsize=(3.8, 2.2), dpi=100, facecolor=C_BG)
        self.ax_deg = self.fig_deg.add_subplot(111)
        self.canvas_deg = FigureCanvasTkAgg(self.fig_deg, master=rp)
        self.canvas_deg.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=8, pady=2)

        # --- Eigenvalue spectrum ---
        self._section_label(rp, "Adjacency Spectrum")
        self.fig_eig = plt.Figure(figsize=(3.8, 2.2), dpi=100, facecolor=C_BG)
        self.ax_eig = self.fig_eig.add_subplot(111)
        self.canvas_eig = FigureCanvasTkAgg(self.fig_eig, master=rp)
        self.canvas_eig.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=8, pady=2)

        # --- Laplacian spectrum ---
        self._section_label(rp, "Laplacian Spectrum")
        self.fig_lap = plt.Figure(figsize=(3.8, 2.2), dpi=100, facecolor=C_BG)
        self.ax_lap = self.fig_lap.add_subplot(111)
        self.canvas_lap = FigureCanvasTkAgg(self.fig_lap, master=rp)
        self.canvas_lap.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=8, pady=2)

        # --- Cross-graph scatter plot ---
        self._section_label(rp, "Cross-Graph Plot (All Pareto Points)")

        cg_ctrl = tk.Frame(rp, bg=C_BG)
        cg_ctrl.pack(fill=tk.X, padx=8, pady=2)

        tk.Label(cg_ctrl, text="X:", bg=C_BG, font=("sans-serif", 9)).pack(side=tk.LEFT)
        cg_x_menu = ttk.Combobox(cg_ctrl, textvariable=self.cg_x, values=_PLOT_ATTRS,
                                  width=8, state="readonly")
        cg_x_menu.pack(side=tk.LEFT, padx=(2, 8))

        tk.Label(cg_ctrl, text="Y:", bg=C_BG, font=("sans-serif", 9)).pack(side=tk.LEFT)
        cg_y_menu = ttk.Combobox(cg_ctrl, textvariable=self.cg_y, values=_PLOT_ATTRS,
                                  width=8, state="readonly")
        cg_y_menu.pack(side=tk.LEFT, padx=(2, 8))

        tk.Label(cg_ctrl, text="Best:", bg=C_BG, font=("sans-serif", 9)).pack(side=tk.LEFT)
        tk.Radiobutton(cg_ctrl, text="min", variable=self.cg_agg, value="min",
                       bg=C_BG, command=self._draw_cross_graph).pack(side=tk.LEFT)
        tk.Radiobutton(cg_ctrl, text="max", variable=self.cg_agg, value="max",
                       bg=C_BG, command=self._draw_cross_graph).pack(side=tk.LEFT)

        cg_x_menu.bind("<<ComboboxSelected>>", lambda e: self._draw_cross_graph())
        cg_y_menu.bind("<<ComboboxSelected>>", lambda e: self._draw_cross_graph())

        self.fig_cg = plt.Figure(figsize=(3.8, 2.4), dpi=100, facecolor=C_BG)
        self.ax_cg = self.fig_cg.add_subplot(111)
        self.canvas_cg = FigureCanvasTkAgg(self.fig_cg, master=rp)
        self.canvas_cg.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=8, pady=2)

        # --- Histogram ---
        self._section_label(rp, "Histogram (All Pareto Points)")

        hist_ctrl = tk.Frame(rp, bg=C_BG)
        hist_ctrl.pack(fill=tk.X, padx=8, pady=2)

        tk.Label(hist_ctrl, text="Variable:", bg=C_BG, font=("sans-serif", 9)).pack(side=tk.LEFT)
        hist_menu = ttk.Combobox(hist_ctrl, textvariable=self.hist_var, values=_PLOT_ATTRS,
                                  width=10, state="readonly")
        hist_menu.pack(side=tk.LEFT, padx=(2, 0))
        hist_menu.bind("<<ComboboxSelected>>", lambda e: self._draw_histogram())

        self.fig_hist = plt.Figure(figsize=(3.8, 2.4), dpi=100, facecolor=C_BG)
        self.ax_hist = self.fig_hist.add_subplot(111)
        self.canvas_hist = FigureCanvasTkAgg(self.fig_hist, master=rp)
        self.canvas_hist.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=8, pady=2)

        # Keyboard shortcuts
        self.bind("<Left>", lambda e: self._prev_pt())
        self.bind("<Right>", lambda e: self._next_pt())
        self.bind("<Up>", lambda e: self._next_n())
        self.bind("<Down>", lambda e: self._prev_n())

        # Set initial sash position (65% left, 35% right) after window maps
        self.after(100, lambda: self._paned.sash_place(0, int(self.winfo_width() * 0.6), 0))

    def _section_label(self, parent, text):
        f = tk.Frame(parent, bg="#E0E0E0")
        f.pack(fill=tk.X, padx=4, pady=(8, 2))
        tk.Label(f, text=text, bg="#E0E0E0", font=("sans-serif", 10, "bold"),
                 anchor="w").pack(fill=tk.X, padx=4, pady=2)

    # ---- Filter ----

    def _on_filter_changed(self):
        """Recompute view and reload, preserving current n if possible."""
        cur_n = self._view_n_values[self.n_idx] if self._view_n_values else None
        self._recompute_view()
        # Try to stay on the same n
        if cur_n is not None and cur_n in self._view_data:
            self.n_idx = self._view_n_values.index(cur_n)
        else:
            self.n_idx = 0
        self.pt_idx = 0
        self._load_current_graph()

    # ---- Navigation ----

    def _current_point(self):
        n = self._view_n_values[self.n_idx]
        pts = self._view_data[n]
        return pts[self.pt_idx]

    def _prev_n(self):
        if self.n_idx > 0:
            self.n_idx -= 1
            self.pt_idx = 0
            self._load_current_graph()

    def _next_n(self):
        if self.n_idx < len(self._view_n_values) - 1:
            self.n_idx += 1
            self.pt_idx = 0
            self._load_current_graph()

    def _prev_pt(self):
        if self.pt_idx > 0:
            self.pt_idx -= 1
            self._load_current_graph()

    def _next_pt(self):
        n = self._view_n_values[self.n_idx]
        if self.pt_idx < len(self._view_data[n]) - 1:
            self.pt_idx += 1
            self._load_current_graph()

    # ---- Graph loading ----

    def _load_current_graph(self):
        """Load graph, compute layout, metrics, redraw everything."""
        pt = self._current_point()
        n = self._view_n_values[self.n_idx]
        total_pts = len(self._view_data[n])

        # Update labels
        self.lbl_n.config(text=str(n))
        self.lbl_pt.config(text=f"{self.pt_idx + 1}/{total_pts}")
        c_str = f"{pt['c_log']:.4f}" if pt.get("c_log") is not None else "–"
        self.lbl_summary.config(
            text=f"α={pt['alpha']}, d_max={pt['d_max']}, c_log={c_str}, "
                 f"edges={len(pt['edges'])}, method={pt.get('method', '?')}"
        )

        # Compute layout
        self._compute_layout(pt)

        # Invalidate highlight caches
        self._mis_cache = None
        self._tri_cache = None
        self._high_deg_cache = None
        self.selected_node = None

        # Compute metrics
        metrics, eig_adj, eig_lap, degrees = compute_metrics(pt)

        # Update metrics text
        self.metrics_text.config(state=tk.NORMAL)
        self.metrics_text.delete("1.0", tk.END)
        for key, val in metrics.items():
            self.metrics_text.insert(tk.END, f"{key:.<28s} {val}\n")
        self.metrics_text.config(state=tk.DISABLED)

        # Update charts
        self._draw_degree_dist(degrees)
        self._draw_eigenvalues(eig_adj, self.ax_eig, self.canvas_eig, "Adjacency eigenvalues")
        self._draw_eigenvalues(eig_lap, self.ax_lap, self.canvas_lap, "Laplacian eigenvalues")
        self._draw_cross_graph()
        self._draw_histogram()

        # Draw graph
        self._draw_graph()

    def _compute_layout(self, pt):
        G = pt["G"]
        name = self.layout_name.get()
        if name == "Circular":
            self.pos = nx.circular_layout(G)
        elif name == "Shell":
            degs = dict(G.degree())
            if degs:
                shells = []
                for d in sorted(set(degs.values()), reverse=True):
                    shells.append([v for v, dv in degs.items() if dv == d])
                self.pos = nx.shell_layout(G, nlist=shells)
            else:
                self.pos = nx.circular_layout(G)
        elif name == "Kamada-Kawai":
            self.pos = nx.kamada_kawai_layout(G)
        else:
            self.pos = nx.spring_layout(G, seed=42, k=1.5 / max(1, G.number_of_nodes() ** 0.5),
                                         iterations=80)

    def _on_layout_changed(self):
        self._compute_layout(self._current_point())
        self._draw_graph()

    def _on_highlight_changed(self):
        self._draw_graph()

    # ---- Graph drawing ----

    def _draw_graph(self):
        ax = self.ax_graph
        ax.clear()
        ax.set_facecolor("white")
        ax.axis("off")

        pt = self._current_point()
        G = pt["G"]
        pos = self.pos

        if G.number_of_nodes() == 0:
            self.canvas_graph.draw_idle()
            return

        # Compute highlights
        node_colors, node_edge_colors, node_edge_widths = self._compute_node_colors(pt)
        edge_colors, edge_widths = self._compute_edge_colors(pt)

        # Determine node size based on graph size
        n = G.number_of_nodes()
        node_size = max(80, NODE_SIZE_BASE - n * 5)
        font_size = max(6, FONT_SIZE_LABEL - max(0, n - 20) // 5)

        # Draw edges
        edge_list = list(G.edges())
        if edge_list:
            nx.draw_networkx_edges(G, pos, ax=ax, edgelist=edge_list,
                                    edge_color=edge_colors, width=edge_widths, alpha=0.7)

        # Draw nodes
        nx.draw_networkx_nodes(G, pos, ax=ax, node_color=node_colors,
                                node_size=node_size, edgecolors=node_edge_colors,
                                linewidths=node_edge_widths)

        # Draw labels
        nx.draw_networkx_labels(G, pos, ax=ax, font_size=font_size, font_color="white",
                                 font_weight="bold")

        # Title
        ax.set_title(f"n={pt['n']}, α={pt['alpha']}, d_max={pt['d_max']}",
                      fontsize=12, fontweight="bold", pad=10)

        self.fig_graph.tight_layout()
        self.canvas_graph.draw_idle()

    def _compute_node_colors(self, pt):
        G = pt["G"]
        adj = pt["adj"]
        nodes = list(G.nodes())
        n = len(nodes)

        colors = [C_NODE] * n
        edge_colors = ["#333333"] * n
        edge_widths = [1.0] * n

        any_highlight = (self.hl_mis.get() or self.hl_triangles.get() or
                         self.hl_high_deg.get() or
                         (self.hl_neighbors.get() and self.selected_node is not None))

        if any_highlight:
            colors = [C_DIM] * n
            edge_colors = ["#AAAAAA"] * n

        if self.hl_mis.get():
            if self._mis_cache is None:
                self._mis_cache = get_mis_vertices(adj)
            for i, v in enumerate(nodes):
                if v in self._mis_cache:
                    colors[i] = C_MIS
                    edge_colors[i] = "#922B21"
                    edge_widths[i] = 2.5

        if self.hl_triangles.get():
            if self._tri_cache is None:
                self._tri_cache = get_triangle_edges(G)
            _, tri_verts = self._tri_cache
            for i, v in enumerate(nodes):
                if v in tri_verts:
                    if colors[i] == C_DIM:
                        colors[i] = C_TRIANGLE
                    edge_colors[i] = "#B7950B"
                    edge_widths[i] = 2.0

        if self.hl_high_deg.get():
            if self._high_deg_cache is None:
                self._high_deg_cache = get_high_degree_verts(G)
            for i, v in enumerate(nodes):
                if v in self._high_deg_cache:
                    if colors[i] == C_DIM:
                        colors[i] = C_HIGH_DEG
                    edge_colors[i] = "#1E8449"
                    edge_widths[i] = 2.5

        if self.hl_neighbors.get() and self.selected_node is not None:
            sv = self.selected_node
            nbrs = set(G.neighbors(sv))
            for i, v in enumerate(nodes):
                if v == sv:
                    colors[i] = C_SELECTED
                    edge_colors[i] = "#6C3483"
                    edge_widths[i] = 3.0
                elif v in nbrs:
                    if colors[i] == C_DIM:
                        colors[i] = C_NEIGHBOR
                    edge_colors[i] = "#B7950B"
                    edge_widths[i] = 2.0

        return colors, edge_colors, edge_widths

    def _compute_edge_colors(self, pt):
        G = pt["G"]
        edges = list(G.edges())
        colors = [C_EDGE] * len(edges)
        widths = [1.2] * len(edges)

        if self.hl_triangles.get():
            if self._tri_cache is None:
                self._tri_cache = get_triangle_edges(G)
            tri_edges, _ = self._tri_cache
            for i, (u, v) in enumerate(edges):
                key = (min(u, v), max(u, v))
                if key in tri_edges:
                    colors[i] = C_EDGE_TRI
                    widths[i] = 2.5

        if self.hl_neighbors.get() and self.selected_node is not None:
            sv = self.selected_node
            for i, (u, v) in enumerate(edges):
                if u == sv or v == sv:
                    colors[i] = C_SELECTED
                    widths[i] = 2.5

        return colors, widths

    # ---- Drag handling ----

    def _on_press(self, event):
        if event.inaxes != self.ax_graph or event.xdata is None:
            return
        pt = self._current_point()
        G = pt["G"]
        min_dist = float("inf")
        closest = None
        for node, (x, y) in self.pos.items():
            dist = (x - event.xdata) ** 2 + (y - event.ydata) ** 2
            if dist < min_dist:
                min_dist = dist
                closest = node

        if closest is not None:
            xlim = self.ax_graph.get_xlim()
            extent = xlim[1] - xlim[0]
            threshold = (extent * 0.04) ** 2
            if min_dist < threshold:
                if event.button == 1:
                    self.dragging = closest
                    if self.hl_neighbors.get():
                        self.selected_node = closest
                        self._draw_graph()

    def _on_motion(self, event):
        if self.dragging is None or event.inaxes != self.ax_graph or event.xdata is None:
            return
        self.pos[self.dragging] = (event.xdata, event.ydata)
        self._draw_graph()

    def _on_release(self, event):
        self.dragging = None

    # ---- Charts ----

    def _draw_degree_dist(self, degrees):
        ax = self.ax_deg
        ax.clear()
        if not degrees:
            self.canvas_deg.draw_idle()
            return
        counts = Counter(degrees)
        degs_sorted = sorted(counts.keys())
        vals = [counts[d] for d in degs_sorted]
        ax.bar(degs_sorted, vals, color=C_NODE, edgecolor="#333", linewidth=0.5)
        ax.set_xlabel("Degree", fontsize=8)
        ax.set_ylabel("Count", fontsize=8)
        ax.set_xticks(degs_sorted)
        ax.tick_params(labelsize=7)
        self.fig_deg.tight_layout()
        self.canvas_deg.draw_idle()

    def _draw_cross_graph(self):
        """Draw scatter plot of best y per unique x across all Pareto points."""
        ax = self.ax_cg
        ax.clear()

        x_name = self.cg_x.get()
        y_name = self.cg_y.get()
        agg = self.cg_agg.get()  # "min" or "max"
        agg_fn = min if agg == "min" else max

        # Collect (x, y) from all points, skipping None
        groups = {}  # x_val -> [y_vals]
        all_xy = []  # (x, y, point) for all valid points
        for pt in self._view_all_points:
            xv = _extract_attr(pt, x_name)
            yv = _extract_attr(pt, y_name)
            if xv is None or yv is None:
                continue
            all_xy.append((xv, yv, pt))
            groups.setdefault(xv, []).append(yv)

        if not groups:
            ax.set_title(f"No data for {x_name} vs {y_name}", fontsize=8)
            self.fig_cg.tight_layout()
            self.canvas_cg.draw_idle()
            return

        # All points as small gray dots
        all_x = [t[0] for t in all_xy]
        all_y = [t[1] for t in all_xy]
        ax.scatter(all_x, all_y, s=15, color=C_DIM, edgecolors="#AAA",
                   linewidths=0.5, zorder=1, label="all points")

        # Best per group
        best_x = sorted(groups.keys())
        best_y = [agg_fn(groups[xv]) for xv in best_x]
        ax.plot(best_x, best_y, "o-", color=C_NODE, markersize=5, linewidth=1.5,
                zorder=2, label=f"{agg}({y_name})")

        # Highlight current point
        cur = self._current_point()
        cx = _extract_attr(cur, x_name)
        cy = _extract_attr(cur, y_name)
        if cx is not None and cy is not None:
            ax.scatter([cx], [cy], s=80, color=C_MIS, edgecolors="#922B21",
                       linewidths=2, zorder=3, marker="*", label="current")

        ax.set_xlabel(x_name, fontsize=8)
        ax.set_ylabel(f"{agg}({y_name})", fontsize=8)
        ax.tick_params(labelsize=7)
        ax.legend(fontsize=6, loc="best")
        ax.grid(True, alpha=0.3)
        self.fig_cg.tight_layout()
        self.canvas_cg.draw_idle()

    def _draw_histogram(self):
        """Draw histogram of a chosen variable across all Pareto points."""
        ax = self.ax_hist
        ax.clear()

        var_name = self.hist_var.get()
        values = []
        for pt in self._view_all_points:
            v = _extract_attr(pt, var_name)
            if v is not None:
                values.append(v)

        if not values:
            ax.set_title(f"No data for {var_name}", fontsize=8)
            self.fig_hist.tight_layout()
            self.canvas_hist.draw_idle()
            return

        # Choose bins: for integer-valued attrs use integer bins, else auto
        unique = sorted(set(values))
        if all(v == int(v) for v in values) and len(unique) <= 30:
            lo = int(min(values))
            hi = int(max(values))
            bins = range(lo, hi + 2)  # +2 so last value gets its own bin
        else:
            bins = min(20, max(5, len(values) // 3))

        ax.hist(values, bins=bins, color=C_NODE, edgecolor="#333", linewidth=0.5,
                alpha=0.85)

        # Mark current point's value
        cur = self._current_point()
        cv = _extract_attr(cur, var_name)
        if cv is not None:
            ax.axvline(cv, color=C_MIS, linewidth=2, linestyle="--", label=f"current={cv}")
            ax.legend(fontsize=6, loc="best")

        ax.set_xlabel(var_name, fontsize=8)
        ax.set_ylabel("Count", fontsize=8)
        ax.tick_params(labelsize=7)
        self.fig_hist.tight_layout()
        self.canvas_hist.draw_idle()

    def _draw_eigenvalues(self, eigenvalues, ax, canvas, title):
        ax.clear()
        if len(eigenvalues) == 0:
            canvas.draw_idle()
            return
        ax.stem(range(len(eigenvalues)), eigenvalues, linefmt="-", markerfmt="o",
                basefmt="k-")
        ax.axhline(y=0, color="gray", linewidth=0.5, linestyle="--")
        ax.set_xlabel("Index", fontsize=8)
        ax.set_ylabel("λ", fontsize=8)
        ax.tick_params(labelsize=7)
        ax.set_title(title, fontsize=8, pad=4)
        fig = ax.get_figure()
        fig.tight_layout()
        canvas.draw_idle()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Interactive K4-free graph visualizer")
    parser.add_argument("--results-dir", default="regular_sat/results",
                        help="Directory containing pareto_n*.json files")
    args = parser.parse_args()

    app = App(args.results_dir)
    app.mainloop()


if __name__ == "__main__":
    main()
