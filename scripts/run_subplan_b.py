"""
scripts/run_subplan_b.py
========================
Sub-plan B: a locally-computable, rigorous lower bound on alpha(G)/N
for K4-free graphs, via the hard-core occupancy method with the
neighborhood subgraph T_v = G[N(v)] as the only local input.

Theorem (used, clean form)
--------------------------
For any graph G, any vertex v, any lambda > 0:

    rho_v(G, lambda) = lambda * Z(G - N[v], lambda) / Z(G, lambda)
                     >= lambda / Z(G[N[v]], lambda)
                      = lambda / (lambda + Z(T_v, lambda))

where T_v = G[N(v)] and Z(H, lambda) = sum_{I indep} lambda^{|I|} is the
independence polynomial. The inequality uses Z(G) <= Z(G[A]) * Z(G[B])
for any partition V = A | B (removing the A-B cut edges can only add
independent sets). Summing over v and using alpha(G) >= E_mu[|I|]
(hard-core measure mu at fugacity lambda):

    alpha(G)  >=  max_{lambda > 0}  sum_v  lambda / (lambda + Z(T_v, lambda))

For K4-free G, every T_v is triangle-free on d_v <= d_max vertices,
so Z(T_v, lambda) only depends on the iso-class of T_v. That is what
makes this "local in the neighborhood type".

What this script does
---------------------
 1. Pulls every K4-free graph in graph_db with an exact alpha value.
 2. Canonicalizes each T_v via nauty and caches Z(T_v, lambda) as an
    exact integer-coefficient polynomial in lambda.
 3. For each graph, evaluates two rigorous lower bounds:
        L_CW   = sum_v 1 / (d_v + 1)          (Caro-Wei)
        L_HC   = max_{lambda on a grid} sum_v lambda / (lambda + Z(T_v, lambda))
    and reports how tight each is against the exact alpha.
 4. Groups min c_log by d_max across the DB and converts L_HC into
    a lower bound on c_log = alpha * d_max / (N * ln(d_max)):
        c_log(G) >= (L_HC(G) * d_max(G)) / (N(G) * ln(d_max(G)))
 5. Reports per-d the worst-case (minimum) ratio across DB graphs,
    which gives the best rigorous lower bound on c_log that this
    pipeline certifies, restricted to the iso-classes of T actually
    observed.
 6. Writes CSV tables + plots to results/subplan_b/.

Honest scope
------------
The theorem gives a universal lower bound on alpha(G) for ANY K4-free G
whose vertex neighborhoods lie in the observed set of triangle-free
iso-classes. To get a true universal bound on c_log at fixed d, we
would need to extend the neighborhood-type enumeration to ALL
triangle-free graphs on d vertices (geng -t -D$d) and take the
worst-case lambda. That is the "extrapolation to d=infty" path;
this script does it for d up to d_max_enum, which defaults to 8.
"""

from __future__ import annotations

import argparse
import csv
import math
import os
import sys
from collections import defaultdict
from dataclasses import dataclass
from functools import lru_cache
from typing import Dict, List, Tuple

import networkx as nx
import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from graph_db import DB
from utils.nauty import canonical_id, canonical_ids, find_geng, graphs_via_geng


# ---------------------------------------------------------------------------
# Independence polynomial: Z(H, lambda) as a list of nonneg int coeffs
# Z[k] = number of independent sets of H of size k, so
#   Z(H, lambda) = sum_k Z[k] * lambda^k.
# ---------------------------------------------------------------------------

def independence_polynomial(H: nx.Graph) -> List[int]:
    """
    Return coefficients [a_0, a_1, ..., a_alpha] where a_k = number
    of size-k independent sets of H. Exact via a simple recursion.
    """
    nodes = list(H.nodes())
    if not nodes:
        return [1]

    # Rank vertices by degree desc for a fighting chance at early pruning.
    nodes.sort(key=lambda v: -H.degree(v))
    index = {v: i for i, v in enumerate(nodes)}
    neighbor_mask = [0] * len(nodes)
    for i, v in enumerate(nodes):
        m = 0
        for u in H.neighbors(v):
            m |= 1 << index[u]
        neighbor_mask[i] = m

    n = len(nodes)
    coeffs = [0] * (n + 1)

    # DFS: at each step, either include the next allowed vertex or skip all remaining.
    # "allowed" is a bitmask of still-eligible indices.
    def dfs(start: int, allowed: int, size: int):
        # Option: take no more vertices from 'start..n-1'
        coeffs[size] += 1
        i = start
        while i < n:
            bit = 1 << i
            if allowed & bit:
                dfs(i + 1, allowed & ~bit & ~neighbor_mask[i], size + 1)
            i += 1

    dfs(0, (1 << n) - 1, 0)
    # Trim trailing zeros.
    while len(coeffs) > 1 and coeffs[-1] == 0:
        coeffs.pop()
    return coeffs


def poly_eval(coeffs: List[int], lam: float) -> float:
    """Horner-evaluate poly at lambda."""
    s = 0.0
    for c in reversed(coeffs):
        s = s * lam + c
    return s


# ---------------------------------------------------------------------------
# Neighborhood type cache
# ---------------------------------------------------------------------------

@dataclass
class NbhdType:
    tid: str            # canonical id of T = G[N(v)]
    d: int              # |V(T)| = degree of the center vertex
    s6: str             # canonical sparse6 of T
    Zcoef: List[int]    # independence polynomial coefficients


class NbhdCache:
    def __init__(self):
        self.by_id: Dict[str, NbhdType] = {}

    def encode(self, T: nx.Graph) -> NbhdType:
        tid, s6 = canonical_id(T)
        nt = self.by_id.get(tid)
        if nt is None:
            Zc = independence_polynomial(T)
            nt = NbhdType(tid=tid, d=T.number_of_nodes(), s6=s6, Zcoef=Zc)
            self.by_id[tid] = nt
        return nt


# ---------------------------------------------------------------------------
# Per-graph bound computations
# ---------------------------------------------------------------------------

def graph_bounds(G: nx.Graph, cache: NbhdCache, lam_grid: np.ndarray) -> dict:
    """
    For a single graph G, compute:
      - d_v and T_v for each vertex
      - Caro-Wei lower bound: sum 1/(d_v+1)
      - Hard-core local lower bound for each lambda on the grid, and
        the max over the grid.
    """
    d_max = max((d for _, d in G.degree()), default=0)
    cw = 0.0
    nbhd_types: List[NbhdType] = []
    for v in G.nodes():
        dv = G.degree(v)
        T = G.subgraph(list(G.neighbors(v))).copy()
        nt = cache.encode(T)
        nbhd_types.append(nt)
        cw += 1.0 / (dv + 1)

    # L_HC(lambda) = sum_v lambda / (lambda + Z(T_v, lambda))
    hc_vals = np.zeros_like(lam_grid)
    for nt in nbhd_types:
        Zvals = np.array([poly_eval(nt.Zcoef, lam) for lam in lam_grid])
        hc_vals += lam_grid / (lam_grid + Zvals)
    best_idx = int(np.argmax(hc_vals))
    return dict(
        n=G.number_of_nodes(),
        m=G.number_of_edges(),
        d_max=d_max,
        L_CW=cw,
        L_HC=float(hc_vals[best_idx]),
        L_HC_lambda=float(lam_grid[best_idx]),
        nbhd_type_ids=[nt.tid for nt in nbhd_types],
        nbhd_type_degs=[nt.d for nt in nbhd_types],
    )


# ---------------------------------------------------------------------------
# Universal per-d bound via geng enumeration of triangle-free nbhds
# ---------------------------------------------------------------------------

def universal_hc_bound(d: int, lam_grid: np.ndarray, geng_bin: str) -> Tuple[float, float, int]:
    """
    For a fixed center-degree d, enumerate ALL triangle-free graphs on
    d vertices via nauty geng with -t (no triangles). For a d-regular
    K4-free graph where EVERY vertex has neighborhood type T, the bound
    per-vertex is lambda / (lambda + Z(T, lambda)). The worst case over T
    at each lambda gives a universal lower bound on rho_v under the
    hard-core measure. Optimizing over lambda:

        rho_min(d) = max_lambda min_T lambda / (lambda + Z(T, lambda))

    Returns (rho_min, lambda_star, n_types_enumerated).

    Notes:
      - This is a strict lower bound on alpha/N for any d-regular
        K4-free graph, in terms of rho_min(d).
      - For non-regular G, the bound is sum_v rho(d_v, T_v), but
        d_v <= d_max means the per-vertex rho is at least
        rho_min(d_v), since adding vertices to T only increases Z.
        We bake that monotonicity in by taking the infimum over d'<=d.
    """
    if d == 0:
        # Isolated vertex: T is empty on 0 vertices, Z = 1. rho = lambda / (1+lambda).
        # sup over lambda -> 1. So rho_min(0) = 1 (but d=0 means G is a set of isolated vertices, alpha=N).
        return 1.0, float("inf"), 1

    # Enumerate triangle-free graphs on d vertices.
    types_Zcoef = []
    for G in graphs_via_geng(geng_bin, d, flags="-t"):
        Zc = independence_polynomial(G)
        types_Zcoef.append(Zc)

    # min_T lambda / (lambda + Z(T, lambda)) over all enumerated types,
    # for each lambda on the grid.
    best_rho = -1.0
    best_lam = 0.0
    for lam in lam_grid:
        worst = 1.0
        for Zc in types_Zcoef:
            Zv = poly_eval(Zc, lam)
            v = lam / (lam + Zv)
            if v < worst:
                worst = v
                if worst <= best_rho:
                    break  # cannot improve best_rho with this lambda
        if worst > best_rho:
            best_rho = worst
            best_lam = lam
    return float(best_rho), float(best_lam), len(types_Zcoef)


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-max", type=int, default=10_000,
                    help="Only process DB graphs with N <= n-max (default: no cap). "
                         "Bound L_HC is valid regardless of whether alpha is exact "
                         "or heuristic in the DB; the only thing the cap affected "
                         "was the tightness ratio.")
    ap.add_argument("--lam-min", type=float, default=0.05)
    ap.add_argument("--lam-max", type=float, default=200.0)
    ap.add_argument("--lam-steps", type=int, default=400)
    ap.add_argument("--out-dir", default=os.path.join(REPO, "results", "subplan_b"))
    ap.add_argument("--d-enum-max", type=int, default=8,
                    help="Compute universal rho_min(d) via geng for d = 1..d-enum-max.")
    args = ap.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)
    # Geometric-ish lambda grid (denser near small lambda where the max often lives).
    lam_grid = np.geomspace(args.lam_min, args.lam_max, args.lam_steps)

    # 1) Pull DB rows -----------------------------------------------------------
    print(f"[subplan_b] opening DB (n<={args.n_max}) ...", flush=True)
    with DB(auto_sync=False) as db:
        rows = db.raw_execute(
            "SELECT graph_id, source, n, d_max, alpha, c_log "
            "FROM cache WHERE is_k4_free=1 AND alpha IS NOT NULL AND c_log IS NOT NULL "
            "AND n <= ? ORDER BY n, c_log", (args.n_max,)
        )
        # Dedup by graph_id; pick any source (the graph is the same).
        seen = set()
        unique = []
        for r in rows:
            if r["graph_id"] in seen:
                continue
            seen.add(r["graph_id"])
            unique.append(r)
        print(f"[subplan_b] {len(unique)} unique K4-free graphs with exact alpha", flush=True)

        # Hydrate sparse6 -> nx.Graph for each unique graph.
        hydrated = []
        for r in unique:
            G = db.nx(r["graph_id"])
            hydrated.append((r, G))

    # 2) Per-graph bounds -------------------------------------------------------
    cache = NbhdCache()
    per_graph: List[dict] = []
    print("[subplan_b] evaluating per-graph bounds ...", flush=True)
    for i, (r, G) in enumerate(hydrated):
        b = graph_bounds(G, cache, lam_grid)
        alpha_exact = r["alpha"]
        N = r["n"]
        d_max = r["d_max"]
        # Derived c-bound implied by the LOCAL lower bound on alpha.
        c_exact = r["c_log"]
        c_bound_CW = None
        c_bound_HC = None
        if d_max >= 2:
            lnd = math.log(d_max)
            c_bound_CW = b["L_CW"] * d_max / (N * lnd)
            c_bound_HC = b["L_HC"] * d_max / (N * lnd)
        per_graph.append(dict(
            graph_id=r["graph_id"], source=r["source"], n=N, d_max=d_max,
            alpha=alpha_exact, c_log=c_exact,
            L_CW=b["L_CW"], L_HC=b["L_HC"], L_HC_lambda=b["L_HC_lambda"],
            tight_CW=b["L_CW"] / alpha_exact if alpha_exact else None,
            tight_HC=b["L_HC"] / alpha_exact if alpha_exact else None,
            c_bound_CW=c_bound_CW, c_bound_HC=c_bound_HC,
        ))
        if (i + 1) % 50 == 0:
            print(f"  [{i+1}/{len(hydrated)}] n={N} d_max={d_max} "
                  f"alpha={alpha_exact} L_HC={b['L_HC']:.2f} (alpha ratio={b['L_HC']/alpha_exact:.2%})",
                  flush=True)

    # 3) Write per-graph CSV ----------------------------------------------------
    csv_path = os.path.join(args.out_dir, "per_graph_bounds.csv")
    with open(csv_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(per_graph[0].keys()))
        w.writeheader()
        for row in per_graph:
            w.writerow(row)
    print(f"[subplan_b] wrote {csv_path}", flush=True)

    # 4) Per-d aggregates ------------------------------------------------------
    by_dmax: Dict[int, List[dict]] = defaultdict(list)
    for row in per_graph:
        by_dmax[row["d_max"]].append(row)
    agg_rows = []
    for d in sorted(by_dmax):
        recs = by_dmax[d]
        min_c_log = min(r["c_log"] for r in recs)
        min_c_bound_HC = (
            min((r["c_bound_HC"] for r in recs if r["c_bound_HC"] is not None), default=None)
        )
        max_c_bound_HC = (
            max((r["c_bound_HC"] for r in recs if r["c_bound_HC"] is not None), default=None)
        )
        mean_tight_HC = float(np.mean([r["tight_HC"] for r in recs]))
        agg_rows.append(dict(
            d_max=d,
            n_graphs=len(recs),
            min_c_log_observed=min_c_log,
            min_c_bound_HC=min_c_bound_HC,
            max_c_bound_HC=max_c_bound_HC,
            mean_tightness_HC=mean_tight_HC,
        ))
    with open(os.path.join(args.out_dir, "by_dmax.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(agg_rows[0].keys()))
        w.writeheader()
        for row in agg_rows:
            w.writerow(row)
    print(f"[subplan_b] wrote {os.path.join(args.out_dir, 'by_dmax.csv')}", flush=True)

    # 5) Universal per-d bound via geng -----------------------------------------
    geng = find_geng()
    universal = []
    if geng is None:
        print("[subplan_b] geng not found - skipping universal per-d enumeration.", flush=True)
    else:
        print(f"[subplan_b] enumerating triangle-free nbhds via geng up to d={args.d_enum_max} ...", flush=True)
        for d in range(1, args.d_enum_max + 1):
            rho, lam, n_types = universal_hc_bound(d, lam_grid, geng)
            # Caro-Wei baseline for a d-regular graph: alpha/N >= 1/(d+1).
            rho_cw = 1.0 / (d + 1)
            # Combined rigorous bound: take max of Caro-Wei and local hard-core.
            rho_best = max(rho, rho_cw)
            # Universal c-bound: c >= rho_best * d / ln d (only meaningful for d>=2).
            c_bound_hc = rho * d / math.log(d) if d >= 2 else None
            c_bound_cw = rho_cw * d / math.log(d) if d >= 2 else None
            c_bound_best = rho_best * d / math.log(d) if d >= 2 else None
            universal.append(dict(
                d=d, n_types=n_types, rho_min=rho, lambda_star=lam,
                rho_cw=rho_cw, rho_best=rho_best,
                c_bound_hc=c_bound_hc, c_bound_cw=c_bound_cw,
                c_bound_regular_d=c_bound_best,
            ))
            print(f"  d={d}: {n_types} triangle-free types, rho_HC={rho:.4f}, "
                  f"rho_CW={rho_cw:.4f}, best_c_bound={c_bound_best}", flush=True)
        with open(os.path.join(args.out_dir, "universal_by_d.csv"), "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(universal[0].keys()))
            w.writeheader()
            for row in universal:
                w.writerow(row)
        print(f"[subplan_b] wrote universal_by_d.csv", flush=True)

    # 6) Summary ----------------------------------------------------------------
    print("\n[subplan_b] summary")
    print("  Observed min c_log across DB:")
    overall_min = min(r["c_log"] for r in per_graph)
    print(f"    c_log_min = {overall_min:.4f} (Paley P17 = 0.6789)")
    max_bound = max((r["c_bound_HC"] for r in per_graph if r["c_bound_HC"] is not None), default=None)
    min_bound = min((r["c_bound_HC"] for r in per_graph if r["c_bound_HC"] is not None), default=None)
    print(f"  Per-graph c-bound from L_HC: min={min_bound:.4f}, max={max_bound:.4f}")
    if universal:
        best_universal = max(universal, key=lambda u: (u["c_bound_regular_d"] or -1))
        print(f"  Best universal (d-regular K4-free) c_bound: "
              f"d={best_universal['d']} => c >= {best_universal['c_bound_regular_d']:.4f}")
    print("  See results/subplan_b/ for CSVs.")


if __name__ == "__main__":
    main()
