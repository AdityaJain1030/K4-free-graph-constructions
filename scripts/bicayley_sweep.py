#!/usr/bin/env python3
"""
scripts/bicayley_sweep.py
==========================
Enumerate BiCay(Z_p; R, L) for a prime p over every pair of
symmetric subsets of Z_p*, collect canonical_ids + c_log, and
compare against the exhaustive Cay(Z_{2p}) / Cay(D_p) closures to
find bi-Cayleys that live *outside* the Cayley-on-order-2p families.

Per prime p:
  * |symmetric subsets of Z_p*| = 2^{(p-1)/2}
  * total (R, L) pairs = 4^{(p-1)/2}
  * for each: build G on 2p vertices, canonical_id, filter K4-free,
    compute c_log.
  * dedupe by canonical_id → distinct bi-Cayley iso-classes.

Then enumerate:
  * Cay(Z_{2p}, S) for every symmetric S ⊆ Z_{2p}\\{0}: 2^p iso-classes.
  * Cay(D_p, S) for every symmetric S ⊆ D_p\\{e}: 2^{(p-1)/2 + p} iso-classes
    (restricted to K4-free + d ≤ 12 to keep tractable).

Output:
  * rows:   (bi-cayley canonical_id, c_log, α, d_max, R, L)
  * marks:  is it in Cay(Z_{2p})? in Cay(D_p)? -> "novel" if neither.
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from itertools import chain, combinations
from math import log

import numpy as np
import networkx as nx

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from utils.graph_props import is_k4_free_nx, alpha_exact
from graph_db.encoding import canonical_id


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def symmetric_subsets_Zp(p: int):
    """All symmetric subsets S ⊆ Z_p \\ {0}: S closed under -. Returns sorted tuples."""
    # Z_p \\ {0} has (p-1)/2 unordered {a, -a} pairs (p odd prime).
    pairs = [(i, p - i) for i in range(1, (p + 1) // 2)]
    for mask in range(1 << len(pairs)):
        S = []
        for k, (a, b) in enumerate(pairs):
            if (mask >> k) & 1:
                S.extend([a, b])
        yield tuple(sorted(S))


def cay_Zn(n: int, S):
    G = nx.Graph()
    G.add_nodes_from(range(n))
    for u in range(n):
        for s in S:
            G.add_edge(u, (u + s) % n)
    return G


def bicayley(p: int, R, L):
    """Sheet 0 = 0..p-1, sheet 1 = p..2p-1. R stays on-sheet, L crosses."""
    G = nx.Graph()
    G.add_nodes_from(range(2 * p))
    for u in range(p):
        for r in R:
            v = (u + r) % p
            G.add_edge(u, v)
            G.add_edge(p + u, p + v)
        for l in L:
            G.add_edge(u, p + (u + l) % p)
    return G


def graph_props(G: nx.Graph):
    A = nx.adjacency_matrix(G).toarray()
    d_max = int(A.sum(axis=1).max())
    n = G.number_of_nodes()
    if d_max < 2:
        return None
    if not is_k4_free_nx(G):
        return None
    alpha, _ = alpha_exact(A.astype(np.uint8))
    c_log = alpha * d_max / (n * log(d_max))
    return {"alpha": alpha, "d_max": d_max, "c_log": c_log, "n": n}


def _cid(G: nx.Graph) -> str:
    v = canonical_id(G)
    return v[0] if isinstance(v, tuple) else v


# ---------------------------------------------------------------------------
# Enumerate Cay(Z_n) canonical ids (full)
# ---------------------------------------------------------------------------


def enumerate_Zn_cayley_cids(n: int, max_d: int | None = None) -> set[str]:
    """
    Every symmetric S ⊆ Z_n\\{0} (up to the Z_n* multiplier action would
    dedupe, but we canonical_id each graph so the set is correct without
    that).
    """
    ids: set[str] = set()
    # Orbits under the involution x ↔ n-x
    pairs = []
    involutions = []
    for x in range(1, n):
        if x < n - x:
            pairs.append((x, n - x))
        elif x == n - x:
            involutions.append(x)
    orbs = pairs + [(i,) for i in involutions]
    L = len(orbs)
    print(f"  Cay(Z_{n}) orbits: {L} → 2^{L} = {1<<L} subsets", flush=True)

    t0 = time.monotonic()
    count = 0
    for mask in range(1 << L):
        S = []
        for k in range(L):
            if (mask >> k) & 1:
                S.extend(orbs[k])
        if not S:
            continue
        if max_d is not None and len(S) > max_d:
            continue
        G = cay_Zn(n, S)
        ids.add(_cid(G))
        count += 1
        if count % 500 == 0:
            print(f"    Z_{n} mask {count}: ids so far = {len(ids)} "
                  f"({time.monotonic()-t0:.1f}s)", flush=True)
    print(f"  Cay(Z_{n}) done: {count} enumerated, {len(ids)} distinct iso-classes "
          f"({time.monotonic()-t0:.1f}s)", flush=True)
    return ids


# ---------------------------------------------------------------------------
# Enumerate Cay(D_p) canonical ids (involution-orbit restricted)
# ---------------------------------------------------------------------------


def enumerate_Dp_cayley_cids(p: int, max_d: int | None = None) -> set[str]:
    """
    D_p = ⟨r, s | r^p = s^2 = e, srs = r^-1⟩, order 2p.
    Elements: (0, k) rotations and (1, k) reflections for k ∈ Z_p.
    Non-identity inversion orbits:
        (p-1)/2 rotation pairs {(0,k), (0,-k)}
        p reflection singletons (1, k) (each is its own inverse)
    Total orbits = (p-1)/2 + p.
    """
    rot_pairs = [((0, i), (0, p - i)) for i in range(1, (p + 1) // 2)]
    refls = [((1, k),) for k in range(p)]
    orbs = rot_pairs + refls
    L = len(orbs)
    print(f"  Cay(D_{p}) orbits: {L} → 2^{L} = {1<<L} subsets", flush=True)

    # Multiplication on D_p (as defined): (0,a)·(0,b)=(0,a+b); (0,a)·(1,b)=(1,a+b);
    # (1,a)·(0,b)=(1,a-b); (1,a)·(1,b)=(0,a-b).
    def mul(x, y):
        a, ax = x; b, bx = y
        if a == 0:
            return (b, (ax + bx) % p)
        return (1 - b, (ax - bx) % p)

    elts = [(t, k) for t in (0, 1) for k in range(p)]
    idx = {e: i for i, e in enumerate(elts)}

    def build_cayley(S):
        G = nx.Graph()
        G.add_nodes_from(range(2 * p))
        for g in elts:
            i = idx[g]
            for s in S:
                h = mul(g, s)
                j = idx[h]
                if i < j:
                    G.add_edge(i, j)
        return G

    ids: set[str] = set()
    t0 = time.monotonic()
    count = 0
    total = 1 << L
    for mask in range(total):
        S = []
        for k in range(L):
            if (mask >> k) & 1:
                S.extend(orbs[k])
        if not S:
            continue
        if max_d is not None and len(S) > max_d:
            continue
        G = build_cayley(S)
        ids.add(_cid(G))
        count += 1
        if count % 2000 == 0:
            print(f"    D_{p} mask {count}/{total}: ids = {len(ids)} "
                  f"({time.monotonic()-t0:.1f}s)", flush=True)
    print(f"  Cay(D_{p}) done: {count} enumerated, {len(ids)} distinct iso-classes "
          f"({time.monotonic()-t0:.1f}s)", flush=True)
    return ids


# ---------------------------------------------------------------------------
# Main sweep
# ---------------------------------------------------------------------------


def sweep_bicayley(p: int, *, skip_dp: bool, max_d: int | None):
    print(f"\n========================================")
    print(f"BiCay sweep at p={p}  (graphs on 2p = {2*p} vertices)")
    print(f"========================================\n")

    subs = list(symmetric_subsets_Zp(p))
    print(f"{len(subs)} symmetric subsets of Z_{p}* → {len(subs)**2} (R, L) pairs\n")

    # --- enumerate BiCay(Z_p; R, L) ---
    t0 = time.monotonic()
    bi_rows = []  # (cid, c_log, alpha, d_max, R, L)
    bi_cids = set()
    total_pairs = len(subs) ** 2
    scanned = 0
    k4_ok = 0
    for R in subs:
        for L in subs:
            scanned += 1
            if not R and not L:
                continue
            G = bicayley(p, R, L)
            props = graph_props(G)
            if props is None:
                continue
            cid = _cid(G)
            k4_ok += 1
            bi_cids.add(cid)
            bi_rows.append({
                "cid": cid, "c_log": props["c_log"],
                "alpha": props["alpha"], "d_max": props["d_max"],
                "R": R, "L": L,
            })
            if k4_ok % 200 == 0:
                print(f"  bicayley scanned {scanned}/{total_pairs}  "
                      f"k4_free={k4_ok}  distinct_cids={len(bi_cids)}  "
                      f"({time.monotonic()-t0:.1f}s)", flush=True)
    print(f"\nbicayley finished: {k4_ok} K4-free (out of {total_pairs} pairs), "
          f"{len(bi_cids)} distinct iso-classes ({time.monotonic()-t0:.1f}s)\n",
          flush=True)

    # --- enumerate Cay(Z_{2p}) ---
    print(f"Enumerating Cay(Z_{2*p}) canonical_ids...")
    zn_cids = enumerate_Zn_cayley_cids(2 * p, max_d=max_d)

    # --- enumerate Cay(D_p) (optional; can be big) ---
    if skip_dp:
        print(f"\nSkipping Cay(D_{p}) enumeration (--skip-dp).")
        dp_cids = set()
    else:
        print(f"\nEnumerating Cay(D_{p}) canonical_ids "
              f"(max_d={max_d})...")
        dp_cids = enumerate_Dp_cayley_cids(p, max_d=max_d)

    # --- classify ---
    print(f"\n--- classification at p={p} ---")
    print(f"  bi-Cayley distinct iso-classes (K4-free):  {len(bi_cids)}")
    print(f"  also Cay(Z_{2*p}):                         "
          f"{len(bi_cids & zn_cids)}")
    print(f"  also Cay(D_{p}):                           "
          f"{len(bi_cids & dp_cids)}")
    print(f"  also Cay(Z_{2*p}) or Cay(D_{p}):           "
          f"{len(bi_cids & (zn_cids | dp_cids))}")
    novel = bi_cids - (zn_cids | dp_cids)
    print(f"  NOT Cayley on any order-{2*p} group:       {len(novel)}  ← the prize")

    # --- per bi-Cayley, tag novelty, report best c_log in each bucket ---
    rows_by_cid: dict[str, dict] = {}
    for row in bi_rows:
        cid = row["cid"]
        if cid not in rows_by_cid or row["c_log"] < rows_by_cid[cid]["c_log"]:
            rows_by_cid[cid] = row
    tagged = []
    for cid, row in rows_by_cid.items():
        row["in_Zn"] = cid in zn_cids
        row["in_Dp"] = cid in dp_cids
        row["novel"] = cid not in (zn_cids | dp_cids)
        tagged.append(row)
    tagged.sort(key=lambda r: r["c_log"])

    print(f"\n--- top 10 bi-Cayley iso-classes by c_log (p={p}) ---")
    print(f"{'rank':>4}  {'c_log':>8}  {'α':>3} {'d':>3}  novel?  in_Z{2*p}  in_D{p}  cid  (sample R, L)")
    for i, r in enumerate(tagged[:10], 1):
        print(f"{i:>4}  {r['c_log']:>8.4f}  {r['alpha']:>3} {r['d_max']:>3}  "
              f"{'YES' if r['novel'] else '  '}     {'Y' if r['in_Zn'] else ' '}        "
              f"{'Y' if r['in_Dp'] else ' '}       {r['cid'][:12]}  R={r['R']}  L={r['L']}")

    print(f"\n--- top 10 NOVEL (non-Cayley-on-order-{2*p}) bi-Cayleys ---")
    novel_rows = [r for r in tagged if r["novel"]]
    for i, r in enumerate(novel_rows[:10], 1):
        print(f"{i:>4}  {r['c_log']:>8.4f}  {r['alpha']:>3} {r['d_max']:>3}  "
              f"cid={r['cid'][:12]}  R={r['R']}  L={r['L']}")
    if not novel_rows:
        print(f"  (none — every K4-free BiCay(Z_{p}) iso-class reduces to "
              f"a Cayley on Z_{2*p} or D_{p})")

    return tagged, zn_cids, dp_cids


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--p", type=int, nargs="+", default=[11, 17],
                    help="prime(s) p for BiCay(Z_p; R, L) sweep")
    ap.add_argument("--skip-dp", action="store_true",
                    help="skip Cay(D_p) enumeration (too expensive at p=17)")
    ap.add_argument("--max-d", type=int, default=12,
                    help="cap on |S| for Cayley enumerations")
    args = ap.parse_args()

    for p in args.p:
        sweep_bicayley(p, skip_dp=args.skip_dp, max_d=args.max_d)


if __name__ == "__main__":
    main()
