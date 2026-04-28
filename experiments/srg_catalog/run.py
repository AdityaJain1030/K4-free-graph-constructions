#!/usr/bin/env python3
"""
experiments/srg_catalog/run.py
================================
Screen McKay's strongly-regular-graph enumeration for K₄-free members,
rank by `c = α · k / (v · ln k)`, and ingest survivors into graph_db
under `source="srg_catalog"`.

The SRG space is interesting because it contains *non-vertex-transitive*
graphs at orders our Cayley searches (circulant, cayley, cayley_tabu)
structurally can't reach. `docs/graphs/BEYOND_CAYLEY.md` §3 argues
non-VT space is where `c < 0.6789` can live: Lovász θ(G) = α(G) on every
VT graph, so VT sits *on* the θ-surface; non-VT can dip below.

Input: raw .g6 files under `experiments/srg_catalog/g6/`. One line per
graph, graph6-encoded. Sourced from
<https://users.cecs.anu.edu.au/~bdm/data/graphs.html>.

Usage::

    python experiments/srg_catalog/run.py                       # minimal tier
    python experiments/srg_catalog/run.py --tier exhaustive
    python experiments/srg_catalog/run.py --classes sr401224.g6
    python experiments/srg_catalog/run.py --no-ingest           # report only
"""

from __future__ import annotations

import argparse
import math
import os
import sys
import time
from typing import NamedTuple

import networkx as nx

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)

from graph_db import GraphStore, DEFAULT_GRAPHS
from graph_db.encoding import canonical_id
from utils.graph_props import (
    is_k4_free_nx,
    alpha_bb_clique_cover_nx,
    c_log_value,
)


class SRGClass(NamedTuple):
    file: str
    v: int
    k: int
    lam: int
    mu: int
    tier: str       # "minimal" | "exhaustive"


# McKay filename convention: sr{v}{k}{λ}{μ}.g6 (concatenated digits).
# Source: https://users.cecs.anu.edu.au/~bdm/data/graphs.html
SRG_CLASSES: list[SRGClass] = [
    SRGClass("sr401224.g6", 40, 12, 2, 4, "minimal"),
    SRGClass("sr361446.g6", 36, 14, 4, 6, "minimal"),
    SRGClass("sr351668.g6", 35, 16, 6, 8, "exhaustive"),
    SRGClass("sr351899.g6", 35, 18, 9, 9, "exhaustive"),
    SRGClass("sr271015.g6", 27, 10, 1, 5, "exhaustive"),
    SRGClass("sr281264.g6", 28, 12, 6, 4, "exhaustive"),
    SRGClass("sr261034.g6", 26, 10, 3, 4, "exhaustive"),
    SRGClass("sr291467.g6", 29, 14, 6, 7, "exhaustive"),
    SRGClass("sr25832.g6",  25,  8, 3, 2, "exhaustive"),
    SRGClass("sr251256.g6", 25, 12, 5, 6, "exhaustive"),
]

C_FLOOR = 0.6789  # Paley P(17) benchmark
MCKAY_BASE = "https://users.cecs.anu.edu.au/~bdm/data"
DEFAULT_SRC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "g6")


# ── SRG algebra ─────────────────────────────────────────────────────────────

def srg_eigenvalues(v: int, k: int, lam: int, mu: int) -> tuple[float, float]:
    """Non-trivial eigenvalues r ≥ s. r+s = λ−μ, rs = μ−k."""
    disc = (lam - mu) ** 2 + 4 * (k - mu)
    sq = math.sqrt(disc)
    r = ((lam - mu) + sq) / 2
    s = ((lam - mu) - sq) / 2
    return r, s


def hoffman_alpha_upper(v: int, k: int, s: float) -> float:
    """α(G) ≤ v·|s|/(k+|s|) for an SRG with smallest eigenvalue s."""
    return v * abs(s) / (k + abs(s))


def delsarte_omega_upper(k: int, s: float) -> float:
    """ω(G) ≤ 1 − k/s for an SRG with smallest eigenvalue s < 0."""
    return 1 - k / s


def alpha_threshold(v: int, k: int, c_floor: float) -> float:
    """Largest α making c < c_floor. c = α·k/(v·ln k) < c_floor ⇒ α < v·ln(k)·c_floor/k."""
    return c_floor * v * math.log(k) / k


# ── IO ──────────────────────────────────────────────────────────────────────

def load_g6(path: str) -> list[nx.Graph]:
    graphs = []
    with open(path, "rb") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            graphs.append(nx.from_graph6_bytes(line))
    return graphs


# ── Per-class screen ────────────────────────────────────────────────────────

def screen_class(cls: SRGClass, src_dir: str, c_floor: float, verbose: bool) -> dict:
    path = os.path.join(src_dir, cls.file)
    r, s = srg_eigenvalues(cls.v, cls.k, cls.lam, cls.mu)
    rep = {
        "cls": cls,
        "r": r, "s": s,
        "hoffman_alpha": hoffman_alpha_upper(cls.v, cls.k, s),
        "delsarte_omega": delsarte_omega_upper(cls.k, s),
        "alpha_thresh": alpha_threshold(cls.v, cls.k, c_floor),
        "file_found": os.path.exists(path),
        "n_graphs": 0,
        "n_k4_free": 0,
        "n_below_floor": 0,
        "survivors": [],      # sorted list[(alpha, c, idx, G)]
        "elapsed_s": 0.0,
    }
    if not rep["file_found"]:
        return rep

    t0 = time.monotonic()
    graphs = load_g6(path)
    rep["n_graphs"] = len(graphs)

    for idx, G in enumerate(graphs):
        if verbose and (idx + 1) % 500 == 0:
            print(f"  [{cls.file}] {idx+1}/{len(graphs)} ...", flush=True)
        if not is_k4_free_nx(G):
            continue
        rep["n_k4_free"] += 1
        alpha, _ = alpha_bb_clique_cover_nx(G)
        c = c_log_value(alpha, cls.v, cls.k)
        if c is None:
            continue
        rep["survivors"].append((alpha, c, idx, G))
        if c <= c_floor + 1e-9:
            rep["n_below_floor"] += 1

    rep["survivors"].sort(key=lambda x: x[1])
    rep["elapsed_s"] = time.monotonic() - t0
    return rep


# ── Reporting ───────────────────────────────────────────────────────────────

def print_class_table(reports: list[dict]) -> None:
    print()
    header = (
        f"{'class':<14} {'(v,k,λ,μ)':<14} {'eigvals':<16} "
        f"{'Hα':>5} {'Dω':>5} {'αthr':>5} "
        f"{'N':>5} {'K4-free':>8} {'<flr':>5} {'bestC':>7}  {'t':>5}"
    )
    print(header)
    print("-" * len(header))
    for rep in reports:
        cls = rep["cls"]
        best_c = rep["survivors"][0][1] if rep["survivors"] else None
        bc = f"{best_c:.4f}" if best_c is not None else "—"
        miss = "" if rep["file_found"] else "*"
        params = f"({cls.v},{cls.k},{cls.lam},{cls.mu})"
        eig = f"r={rep['r']:+.2f} s={rep['s']:+.2f}"
        print(
            f"{cls.file+miss:<14} {params:<14} {eig:<16} "
            f"{rep['hoffman_alpha']:>5.1f} {rep['delsarte_omega']:>5.1f} "
            f"{rep['alpha_thresh']:>5.1f} "
            f"{rep['n_graphs']:>5} {rep['n_k4_free']:>8} "
            f"{rep['n_below_floor']:>5} {bc:>7}  {rep['elapsed_s']:>4.1f}s"
        )


def print_top_survivors(reports: list[dict], top_n: int, c_floor: float) -> None:
    flat = []
    for rep in reports:
        cls = rep["cls"]
        for alpha, c, idx, _G in rep["survivors"]:
            flat.append((c, alpha, cls, idx))
    flat.sort()
    if not flat:
        print("\nNo K₄-free survivors found.")
        return
    print(f"\nTop {min(top_n, len(flat))} K₄-free survivors (by c):")
    print(f"{'c':>8} {'α':>4} {'v':>3} {'k':>3} {'(λ,μ)':<8} {'class':<14} {'idx':>5}")
    print("-" * 55)
    for c, alpha, cls, idx in flat[:top_n]:
        marker = " ← BEATS FLOOR" if c <= c_floor + 1e-9 else ""
        print(
            f"{c:>8.4f} {alpha:>4} {cls.v:>3} {cls.k:>3} "
            f"({cls.lam},{cls.mu})   {cls.file:<14} {idx:>5}{marker}"
        )


# ── Ingest ──────────────────────────────────────────────────────────────────

def ingest(reports: list[dict], store: GraphStore, only_beaters: bool, c_floor: float) -> tuple[int, int]:
    records = []
    for rep in reports:
        cls = rep["cls"]
        for alpha, c, idx, G in rep["survivors"]:
            if only_beaters and c > c_floor + 1e-9:
                continue
            gid, cs6 = canonical_id(G)
            records.append({
                "id": gid,
                "sparse6": cs6,
                "source": "srg_catalog",
                "metadata": {
                    "srg_v": cls.v,
                    "srg_k": cls.k,
                    "srg_lambda": cls.lam,
                    "srg_mu": cls.mu,
                    "mckay_file": cls.file,
                    "mckay_index": idx,
                    "n": cls.v,
                    "alpha": int(alpha),
                    "d_max": cls.k,
                    "c_log": float(c),
                },
            })
    return store.write_batch(records, "srg_catalog.json")


# ── Main ────────────────────────────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tier", choices=["minimal", "exhaustive"], default="minimal")
    ap.add_argument("--classes", nargs="*", default=None,
                    help="Explicit .g6 filenames (overrides --tier).")
    ap.add_argument("--src-dir", default=DEFAULT_SRC_DIR)
    ap.add_argument("--c-floor", type=float, default=C_FLOOR)
    ap.add_argument("--top-n", type=int, default=20)
    ap.add_argument("--no-ingest", action="store_true",
                    help="Report only; do not write graph_db.")
    ap.add_argument("--only-beaters", action="store_true",
                    help="Ingest only c ≤ floor (default: ingest all K₄-free survivors).")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    if args.classes:
        wanted = set(args.classes)
        classes = [c for c in SRG_CLASSES if c.file in wanted]
        unknown = wanted - {c.file for c in classes}
        if unknown:
            print(f"Unknown class files: {sorted(unknown)}", file=sys.stderr)
            return 2
    else:
        classes = [c for c in SRG_CLASSES
                   if args.tier == "exhaustive" or c.tier == "minimal"]

    print(f"Screening {len(classes)} SRG class(es) from {args.src_dir}")
    print(f"c-floor = {args.c_floor} (Paley P(17) c ≈ 0.6789)")

    missing = [c.file for c in classes
               if not os.path.exists(os.path.join(args.src_dir, c.file))]
    if missing:
        print(f"\nMissing {len(missing)} file(s). Download with:")
        print(f"  mkdir -p {args.src_dir} && cd {args.src_dir}")
        for m in missing:
            print(f"  curl -O {MCKAY_BASE}/{m}")
        print()

    reports = [screen_class(c, args.src_dir, args.c_floor, args.verbose) for c in classes]

    print_class_table(reports)
    print_top_survivors(reports, args.top_n, args.c_floor)

    total_below = sum(rep["n_below_floor"] for rep in reports)
    if total_below > 0:
        print(f"\n*** {total_below} graph(s) beat c = {args.c_floor} — verify with CP-SAT before celebrating. ***")

    if not args.no_ingest:
        store = GraphStore(DEFAULT_GRAPHS)
        new, skipped = ingest(reports, store, args.only_beaters, args.c_floor)
        kind = "beaters" if args.only_beaters else "K₄-free survivors"
        print(f"\nIngested {new} new {kind} into graph_db under source='srg_catalog' "
              f"(skipped {skipped} duplicates).")

    return 0


if __name__ == "__main__":
    sys.exit(main())
