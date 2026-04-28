#!/usr/bin/env python3
"""
experiments/alpha/generate_graphs.py
=====================================
Generates representative K4-free graphs from 7 structural classes used
in the alpha accuracy and performance benchmarks.

Classes
-------
1. prime_circulant     Best K4-free circulant C(n,S) at each prime n in CIRCULANT_NS
                       (algebraic, regular, well-studied; from circulant_fast DB)
2. dihedral_cayley     Best dihedral-group Cayley graphs from cayley_tabu_gap
                       (non-abelian, pulled from graph_db)
3. polarity            Erdos-Renyi polarity graphs ER(q) for prime powers q
4. random_k4free       Random K4-free graphs via degree-capped edge addition
5. synthetic_circulant C(n,{1,2}) and C(n,{1,2,4}) at n=20..300 (no DB, perf baseline)
6. brown               The single Reiman-Brown R(3,k) graph at n=125
7. sat_exact           SAT-certified optima at n=10..20 (highly irregular)
8. near_regular        random_regular_switch outputs (near-regular, n=20..60)

Usage
-----
    micromamba run -n k4free python experiments/alpha/generate_graphs.py
    micromamba run -n k4free python experiments/alpha/generate_graphs.py --classes prime_circulant random_k4free
    micromamba run -n k4free python experiments/alpha/generate_graphs.py --list
"""

from __future__ import annotations

import argparse
import os
import random
import sys
from typing import Generator

import networkx as nx
import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)

from graph_db.db import open_db
from graph_db.encoding import sparse6_to_nx
from utils.graph_props import is_k4_free

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

POLARITY_QS  = [5, 7, 8, 9, 11, 13]               # n = q^2+q+1
CIRCULANT_NS = [17, 29, 37, 41, 53, 61, 73, 89]   # prime n for circulant sweep
RANDOM_NS    = [20, 30, 40, 50, 60, 80, 100]
RANDOM_PER_N = 5                                    # graphs per N

# Synthetic circulant families used in performance benchmarks
SYNTH_NS     = [20, 40, 60, 80, 100, 150, 200, 250, 300]
SYNTH_FAMILIES: dict[str, list[int]] = {
    "12":   [1, 2],       # 4-regular, α = ⌊n/3⌋
    "124":  [1, 2, 4],    # 6-regular
}


# ---------------------------------------------------------------------------
# Class 1: Prime circulants — best K4-free circulant per prime n from DB
# ---------------------------------------------------------------------------

def load_prime_circulants() -> list[dict]:
    """Best (lowest c_log) K4-free circulant at each prime n in CIRCULANT_NS.
    Uses circulant_fast source; falls back to circulant if not present."""
    db = open_db()
    out = []
    for n in CIRCULANT_NS:
        rows = db.query(
            isin={"source": ["circulant_fast", "circulant"]},
            where={"n": n},
            order_by="c_log",
            limit=1,
        )
        if not rows:
            continue
        r = rows[0]
        G = sparse6_to_nx(db.sparse6(r["graph_id"]))
        m = r.get("metadata") or {}
        jumps = m.get("jumps") or m.get("connection_set") or "?"
        out.append({
            "class": "prime_circulant",
            "n": n,
            "label": f"C({n},{jumps})",
            "graph_id": r["graph_id"],
            "graph": G,
            "c_log": r["c_log"],
        })
    return out


# ---------------------------------------------------------------------------
# Class 2: Dihedral Cayley graphs (non-abelian) from graph_db
# ---------------------------------------------------------------------------

def load_dihedral_cayley() -> list[dict]:
    db = open_db()
    rows = db.query(where={"source": "cayley_tabu_gap"}, ranges={"n": (20, 80)},
                    order_by="c_log", limit=200)
    out = []
    seen_n = set()
    for r in rows:
        m = r.get("metadata") or {}
        grp = m.get("group", "")
        # Keep only dihedral groups (D_n), one per n
        if "_D" not in grp:
            continue
        if r["n"] in seen_n:
            continue
        seen_n.add(r["n"])
        G = sparse6_to_nx(db.sparse6(r["graph_id"]))
        out.append({
            "class": "dihedral_cayley",
            "n": r["n"],
            "label": grp.split("_", 2)[-1],   # e.g. "D22"
            "graph_id": r["graph_id"],
            "graph": G,
            "c_log": r["c_log"],
        })
        if len(out) >= 8:
            break
    return out


# ---------------------------------------------------------------------------
# Class 3: Erdos-Renyi polarity graphs from graph_db
# ---------------------------------------------------------------------------

def load_polarity() -> list[dict]:
    db = open_db()
    rows = db.query(where={"source": "polarity"}, order_by="n")
    out = []
    for r in rows:
        m = r.get("metadata") or {}
        if m.get("q") in POLARITY_QS:
            G = sparse6_to_nx(db.sparse6(r["graph_id"]))
            out.append({
                "class": "polarity",
                "n": r["n"],
                "label": f"ER({m['q']})",
                "graph_id": r["graph_id"],
                "graph": G,
                "c_log": r["c_log"],
            })
    return out


# ---------------------------------------------------------------------------
# Class 4: Random K4-free graphs (generated on the fly)
# ---------------------------------------------------------------------------

def _random_k4free(n: int, d_cap: int = 10, seed: int = 0) -> nx.Graph:
    """Random K4-free graph via degree-capped greedy edge addition."""
    rng = random.Random(seed)
    adj = np.zeros((n, n), dtype=np.bool_)
    nbr = [0] * n
    deg = [0] * n

    edges = [(i, j) for i in range(n) for j in range(i + 1, n)]
    rng.shuffle(edges)

    for u, v in edges:
        if deg[u] >= d_cap or deg[v] >= d_cap:
            continue
        # K4-free check: common neighbours of u and v must form an independent set
        common = nbr[u] & nbr[v]
        # Adding (u,v) creates K4 iff any two common neighbours are adjacent
        tmp = common
        bad = False
        while tmp and not bad:
            a = (tmp & -tmp).bit_length() - 1
            tmp2 = tmp & ~((1 << (a + 1)) - 1)
            while tmp2 and not bad:
                b = (tmp2 & -tmp2).bit_length() - 1
                if adj[a, b]:
                    bad = True
                tmp2 &= tmp2 - 1
            tmp &= tmp - 1
        if bad:
            continue
        adj[u, v] = adj[v, u] = True
        nbr[u] |= 1 << v
        nbr[v] |= 1 << u
        deg[u] += 1
        deg[v] += 1

    G = nx.from_numpy_array(adj.astype(np.uint8))
    return G


def generate_random_k4free() -> list[dict]:
    out = []
    for n in RANDOM_NS:
        for seed in range(RANDOM_PER_N):
            G = _random_k4free(n, d_cap=min(10, n // 3), seed=seed)
            out.append({
                "class": "random_k4free",
                "n": n,
                "label": f"rand(n={n},s={seed})",
                "graph_id": None,
                "graph": G,
                "c_log": None,
            })
    return out


# ---------------------------------------------------------------------------
# Class 5: Synthetic circulants (performance baseline, no DB needed)
# ---------------------------------------------------------------------------

def generate_synthetic_circulant() -> list[dict]:
    """C(n, S) for two jump families across a range of n.
    All graphs are K4-free by construction for these families.
    Used as the performance benchmark baseline in bench_alpha.py."""
    from utils.graph_props import is_k4_free_nx
    out = []
    for family, jumps in SYNTH_FAMILIES.items():
        for n in SYNTH_NS:
            j = [x for x in jumps if 1 <= x <= n // 2]
            if not j:
                continue
            G = nx.circulant_graph(n, j)
            if not is_k4_free_nx(G):
                continue
            out.append({
                "class":    "synthetic_circulant",
                "n":        n,
                "label":    f"C({n},{{{','.join(map(str, j))}}})",
                "graph_id": None,
                "graph":    G,
                "c_log":    None,
                "family":   family,
            })
    return out


# ---------------------------------------------------------------------------
# Class 6: Brown graph from graph_db

# ---------------------------------------------------------------------------

def load_brown() -> list[dict]:
    db = open_db()
    rows = db.query(where={"source": "brown"})
    out = []
    for r in rows:
        G = sparse6_to_nx(db.sparse6(r["graph_id"]))
        out.append({
            "class": "brown",
            "n": r["n"],
            "label": f"Brown(n={r['n']})",
            "graph_id": r["graph_id"],
            "graph": G,
            "c_log": r["c_log"],
        })
    return out


# ---------------------------------------------------------------------------
# Class 7: SAT-certified optima from graph_db
# ---------------------------------------------------------------------------

def load_sat_exact() -> list[dict]:
    db = open_db()
    # Best (lowest c_log) certified graph per n
    rows = db.query(where={"source": "sat_exact"}, ranges={"n": (10, 22)}, order_by="n")
    seen_n: dict[int, dict] = {}
    for r in rows:
        n = r["n"]
        if n not in seen_n or r["c_log"] < seen_n[n]["c_log"]:
            seen_n[n] = r
    out = []
    for r in seen_n.values():
        G = sparse6_to_nx(db.sparse6(r["graph_id"]))
        out.append({
            "class": "sat_exact",
            "n": r["n"],
            "label": f"SAT(n={r['n']})",
            "graph_id": r["graph_id"],
            "graph": G,
            "c_log": r["c_log"],
        })
    return sorted(out, key=lambda x: x["n"])


# ---------------------------------------------------------------------------
# Class 8: Near-regular (random_regular_switch) from graph_db
# ---------------------------------------------------------------------------

def load_near_regular() -> list[dict]:
    db = open_db()
    rows = db.query(where={"source": "random_regular_switch"},
                    ranges={"n": (20, 80)}, order_by="c_log", limit=100)
    seen_n: dict[int, dict] = {}
    for r in rows:
        n = r["n"]
        if n not in seen_n:
            seen_n[n] = r
    out = []
    for r in seen_n.values():
        G = sparse6_to_nx(db.sparse6(r["graph_id"]))
        out.append({
            "class": "near_regular",
            "n": r["n"],
            "label": f"NearReg(n={r['n']})",
            "graph_id": r["graph_id"],
            "graph": G,
            "c_log": r["c_log"],
        })
    return sorted(out, key=lambda x: x["n"])


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

ALL_CLASSES = {
    "prime_circulant":     load_prime_circulants,
    "dihedral_cayley":     load_dihedral_cayley,
    "polarity":            load_polarity,
    "random_k4free":       generate_random_k4free,
    "synthetic_circulant": generate_synthetic_circulant,
    "brown":               load_brown,
    "sat_exact":           load_sat_exact,
    "near_regular":        load_near_regular,
}


def load_all(classes: list[str] | None = None) -> list[dict]:
    """Return all graph instances for the requested classes (default: all)."""
    selected = classes or list(ALL_CLASSES)
    out = []
    for cls in selected:
        if cls not in ALL_CLASSES:
            raise ValueError(f"Unknown class {cls!r}. Choose from: {list(ALL_CLASSES)}")
        print(f"  Loading {cls}...", end=" ", flush=True)
        items = ALL_CLASSES[cls]()
        print(f"{len(items)} graphs")
        out.extend(items)
    return out


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate K4-free graph instances for benchmarks.")
    parser.add_argument("--classes", nargs="+", choices=list(ALL_CLASSES),
                        help="Which graph classes to load (default: all)")
    parser.add_argument("--list", action="store_true",
                        help="List available classes and exit")
    args = parser.parse_args()

    if args.list:
        for name in ALL_CLASSES:
            print(f"  {name}")
        sys.exit(0)

    print("Generating graphs:")
    graphs = load_all(args.classes)
    print(f"\nTotal: {len(graphs)} graphs across {len(set(g['class'] for g in graphs))} classes")
    by_class: dict[str, list] = {}
    for g in graphs:
        by_class.setdefault(g["class"], []).append(g)
    for cls, items in by_class.items():
        ns = sorted(set(i["n"] for i in items))
        print(f"  {cls:20s}: {len(items):3d} graphs, n ∈ {ns}")
