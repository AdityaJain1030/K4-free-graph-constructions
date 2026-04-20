"""
visualizer/plots/_common.py
===========================
Shared helpers for the 10 landscape plots under visualizer/plots/. Each
plot is otherwise a single self-contained script.

SOURCE_CATEGORY maps each `source` string in graph_db to one of:
    'sat'        exact-optimal from a SAT/ILP search (ground truth)
    'algebraic'  algebraic constructions (Paley-variants, polarity,
                 Mattheus–Verstraete, Brown, norm graph, Cayley)
    'circulant'  circulants — algebraic in theory but kept separate
                 because they dominate the low-N frontier
    'greedy'     random / local-search (probe 1 and friends)
    'blowup'     lex/tensor blow-ups of smaller DB graphs (probe 4)

Each category has a fixed plotting marker and colour so every figure
uses the same visual language.
"""

import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

IMG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "images")


SOURCE_CATEGORY = {
    # SAT / exact — will print a skip line if missing from the DB
    "sat_pareto":        "sat",
    "sat_pareto_ilp":    "sat",
    "sat_exact":         "sat",
    "brute_force":       "sat",
    # algebraic
    "cayley":            "algebraic",
    "polarity":          "algebraic",
    "mattheus_verstraete": "algebraic",
    "brown":             "algebraic",
    "norm_graph":        "algebraic",
    # circulant (separate bucket since they dominate low-N)
    "circulant":         "circulant",
    "circulant_fast":    "circulant",
    # greedy / local search
    "random":            "greedy",
    "random_regular_switch": "greedy",
    "regularity":        "greedy",
    "regularity_alpha":  "greedy",
    # blowup
    "blowup":            "blowup",
}

CATEGORY_STYLE = {
    # category -> (color, marker, label)
    "sat":        ("#1f77b4", "o",  "SAT / exact"),
    "algebraic":  ("#d62728", "^",  "algebraic"),
    "circulant":  ("#ff7f0e", "D",  "circulant"),
    "greedy":     ("#2ca02c", "x",  "greedy"),
    "blowup":     ("#9467bd", "s",  "blowup"),
    "other":      ("#777777", ".",  "other"),
}

PALEY_C_LOG = 0.679  # Paley N=17 is 8-regular, α=3 → 3·8 / (17·ln 8) ≈ 0.679


def category_for(source: str) -> str:
    return SOURCE_CATEGORY.get(source, "other")


def check_sat_available(rows: list[dict]) -> bool:
    """Print a skip-line and return False if the given rows include no SAT seeds."""
    has_sat = any(category_for(r["source"]) == "sat" for r in rows)
    if not has_sat:
        print("[plot] skipping SAT overlay: no SAT/brute-force rows in graph_db")
    return has_sat


def ensure_img_dir() -> str:
    os.makedirs(IMG_DIR, exist_ok=True)
    return IMG_DIR


def open_browser(path: str) -> None:
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
