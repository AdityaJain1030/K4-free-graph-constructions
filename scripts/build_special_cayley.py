"""Construct hand-picked Cayley graphs from algebraic/spectral theory.

One graph per family, chosen at a concrete N, ingested under
source='special_cayley' for side-by-side comparison with the sweeps.
"""
from __future__ import annotations

import os, sys
from itertools import product, permutations
import numpy as np
import networkx as nx

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from graph_db import GraphStore, DEFAULT_GRAPHS, DB


# ---------- helpers ----------

def _cayley_from_elements(elements, mul, inv, S_names):
    """Generic Cayley: elements list, mul(a,b), inv(a); S is set of connection-set elements."""
    idx = {e: i for i, e in enumerate(elements)}
    G = nx.Graph()
    G.add_nodes_from(range(len(elements)))
    S = set(S_names)
    for e in S:
        assert inv(e) in S, f"connection set not symmetric: {e} missing inverse"
    for g in elements:
        i = idx[g]
        for s in S:
            h = mul(g, s)
            j = idx[h]
            if i < j:
                G.add_edge(i, j)
    return G


def is_k4_free(G):
    for u in G.nodes():
        nbrs = list(G.neighbors(u))
        for a in range(len(nbrs)):
            for b in range(a+1, len(nbrs)):
                if not G.has_edge(nbrs[a], nbrs[b]):
                    continue
                # triangle u, nbrs[a], nbrs[b]; check if any common neighbor
                common = set(G.neighbors(u)) & set(G.neighbors(nbrs[a])) & set(G.neighbors(nbrs[b]))
                common -= {u, nbrs[a], nbrs[b]}
                if common:
                    return False
    return True


def hoffman_and_spectrum(G):
    A = nx.to_numpy_array(G)
    eigs = np.linalg.eigvalsh(A)
    lam_min = float(eigs.min())
    d = max(dict(G.degree()).values())
    n = G.number_of_nodes()
    H = n * (-lam_min) / (d - lam_min) if d != lam_min else float("inf")
    return H, lam_min, d


# ---------- 1. Paley P(13) ----------

def paley(q):
    assert q % 4 == 1
    squares = {pow(i, 2, q) for i in range(1, q)}
    elements = list(range(q))
    return _cayley_from_elements(
        elements,
        mul=lambda a, b: (a + b) % q,
        inv=lambda a: (-a) % q,
        S_names=squares,
    )


# ---------- 2. Cyclotomic Cay(Z_17, 4th powers) ----------

def cyclotomic_k(q, k):
    """Cay(Z_q, S ∪ -S) where S = k-th powers in Z_q*."""
    kth = {pow(i, k, q) for i in range(1, q)}
    S = kth | {(-s) % q for s in kth}
    S.discard(0)
    elements = list(range(q))
    return _cayley_from_elements(
        elements,
        mul=lambda a, b: (a + b) % q,
        inv=lambda a: (-a) % q,
        S_names=S,
    ), S


# ---------- 3. Clebsch = Cay(Z_2^4, {e_1..e_4, 1111}) ----------

def clebsch():
    elements = [tuple(v) for v in product(range(2), repeat=4)]
    S = [(1,0,0,0), (0,1,0,0), (0,0,1,0), (0,0,0,1), (1,1,1,1)]
    add = lambda a, b: tuple((a[i]+b[i]) % 2 for i in range(4))
    return _cayley_from_elements(elements, mul=add, inv=lambda a: a, S_names=S)


# ---------- 4. Shrikhande = Cay(Z_4 x Z_4, {±(1,0), ±(0,1), ±(1,1)}) ----------

def shrikhande():
    elements = [tuple(v) for v in product(range(4), repeat=2)]
    S = [(1,0), (3,0), (0,1), (0,3), (1,1), (3,3)]
    add = lambda a, b: ((a[0]+b[0]) % 4, (a[1]+b[1]) % 4)
    inv = lambda a: ((-a[0]) % 4, (-a[1]) % 4)
    return _cayley_from_elements(elements, mul=add, inv=inv, S_names=S)


# ---------- 5. Hamming H(3,3) = Cay(Z_3^3, {±e_i}) ----------

def hamming_3_3():
    elements = [tuple(v) for v in product(range(3), repeat=3)]
    S = [(1,0,0), (2,0,0), (0,1,0), (0,2,0), (0,0,1), (0,0,2)]
    add = lambda a, b: ((a[0]+b[0]) % 3, (a[1]+b[1]) % 3, (a[2]+b[2]) % 3)
    inv = lambda a: ((-a[0]) % 3, (-a[1]) % 3, (-a[2]) % 3)
    return _cayley_from_elements(elements, mul=add, inv=inv, S_names=S)


# ---------- 6. Cay(A_5, double-transpositions) ----------

def _perm_mul(p, q_):
    return tuple(p[q_[i]] for i in range(len(p)))

def _perm_inv(p):
    inv = [0]*len(p)
    for i, x in enumerate(p):
        inv[x] = i
    return tuple(inv)

def _parity(p):
    n = len(p); inv = 0
    for i in range(n):
        for j in range(i+1, n):
            if p[i] > p[j]:
                inv += 1
    return inv % 2

def _is_double_transposition(p):
    n = len(p)
    if _parity(p) != 0:
        return False
    fixed = sum(1 for i in range(n) if p[i] == i)
    if fixed != n - 4:
        return False
    # check every moved element cycles in 2
    for i in range(n):
        if p[i] != i and p[p[i]] != i:
            return False
    return True

def A5_double_transpositions():
    A5 = [p for p in permutations(range(5)) if _parity(p) == 0]
    S = [p for p in A5 if _is_double_transposition(p)]
    return _cayley_from_elements(A5, mul=_perm_mul, inv=_perm_inv, S_names=S), S


# ---------- 7. PSL(2, q) Cayley ----------

def _matmul_mod(A, B, q):
    """2x2 matrix multiplication mod q; matrices as ((a,b),(c,d))."""
    (a, b), (c, d) = A
    (e, f), (g, h) = B
    return (((a*e + b*g) % q, (a*f + b*h) % q),
            ((c*e + d*g) % q, (c*f + d*h) % q))

def _matinv_mod(A, q):
    """Inverse of a det=1 matrix mod q."""
    (a, b), (c, d) = A
    return ((d % q, (-b) % q), ((-c) % q, a % q))

def _det_mod(A, q):
    (a, b), (c, d) = A
    return (a*d - b*c) % q

def _canonical_psl(A, q):
    """Canonical form of A in PSL: min(A, -A) lex."""
    (a, b), (c, d) = A
    negA = (((-a) % q, (-b) % q), ((-c) % q, (-d) % q))
    return min(A, negA)

def psl2_elements(q):
    """Enumerate PSL(2, q) elements as canonical 2x2 matrices mod q."""
    seen = set()
    elts = []
    for a, b, c, d in product(range(q), repeat=4):
        if (a*d - b*c) % q != 1:
            continue
        M = ((a, b), (c, d))
        C = _canonical_psl(M, q)
        if C in seen:
            continue
        seen.add(C)
        elts.append(C)
    return elts

def psl2_involutions_cayley(q):
    """Cay(PSL(2, q), involutions). Involutions = trace-0 elements."""
    elts = psl2_elements(q)
    idx = {e: i for i, e in enumerate(elts)}
    # Connection set = non-identity elements of order 2 = trace 0 (for q odd)
    S = []
    for M in elts:
        (a, b), (c, d) = M
        if (a + d) % q == 0 and M != ((1, 0), (0, 1)):
            S.append(M)
    # sanity: each involution is its own inverse (mod ±I)
    assert len(S) > 0
    # Build Cayley
    G = nx.Graph()
    G.add_nodes_from(range(len(elts)))
    for g in elts:
        i = idx[g]
        for s in S:
            h = _matmul_mod(g, s, q)
            hc = _canonical_psl(h, q)
            j = idx[hc]
            if i < j:
                G.add_edge(i, j)
    return G, S


# ---------- build + verify + ingest ----------

def build_all():
    specs = []

    # 1. P(13)
    G = paley(13)
    specs.append(dict(G=G, family="Paley", name="P(13)",
                      meta={"group": "Z_13", "connection_set": "quadratic_residues"}))

    # 2. Cyclotomic k=4 at q=17
    G, S = cyclotomic_k(17, 4)
    specs.append(dict(G=G, family="Cyclotomic", name="Cay(Z_17, 4th_powers)",
                      meta={"group": "Z_17", "connection_set": sorted(list(S)),
                            "k": 4}))

    # 3. Clebsch
    G = clebsch()
    specs.append(dict(G=G, family="SRG", name="Clebsch (Z_2^4)",
                      meta={"group": "Z_2^4",
                            "connection_set": "{e_1,e_2,e_3,e_4,1111}"}))

    # 4. Shrikhande
    G = shrikhande()
    specs.append(dict(G=G, family="SRG", name="Shrikhande (Z_4xZ_4)",
                      meta={"group": "Z_4xZ_4",
                            "connection_set": "{±(1,0),±(0,1),±(1,1)}"}))

    # 5. Hamming H(3,3)
    G = hamming_3_3()
    specs.append(dict(G=G, family="Hamming", name="H(3,3) (Z_3^3)",
                      meta={"group": "Z_3^3", "connection_set": "{±e_i}"}))

    # 6. A_5 x double-transpositions
    G, S = A5_double_transpositions()
    specs.append(dict(G=G, family="Simple", name="Cay(A_5, double-transpositions)",
                      meta={"group": "A_5",
                            "connection_set": "all_15_double_transpositions"}))

    # 7. PSL(2, 7) x involutions
    G, S = psl2_involutions_cayley(7)
    specs.append(dict(G=G, family="PSL", name="Cay(PSL(2,7), involutions)",
                      meta={"group": "PSL(2,7)",
                            "connection_set": "trace0_involutions",
                            "connection_set_size": len(S)}))

    return specs


def main():
    specs = build_all()

    print(f"{'#':>2}  {'name':42}  {'n':>3} {'d':>3}  {'K4-free':>8}  {'λ_min':>8}  {'H':>7}")
    print("-" * 90)
    accepted = []
    for i, s in enumerate(specs, 1):
        G = s["G"]
        k4 = is_k4_free(G)
        H, lam, d = hoffman_and_spectrum(G)
        n = G.number_of_nodes()
        print(f"{i:>2}  {s['name']:42}  {n:>3} {d:>3}  {str(k4):>8}  {lam:>8.3f}  {H:>7.3f}")
        if not k4:
            print(f"     ^^^ SKIPPING — not K4-free")
            continue
        s["H_prelim"] = H
        s["lam_min_prelim"] = lam
        accepted.append(s)

    print(f"\nAccepted {len(accepted)} / {len(specs)}")

    # Ingest via GraphStore
    store = GraphStore(DEFAULT_GRAPHS)
    added_ids = []
    for s in accepted:
        gid, was_new = store.add_graph(
            s["G"], source="special_cayley",
            filename="special_cayley.json",
            family=s["family"],
            name=s["name"],
            **s["meta"],
        )
        added_ids.append((gid, was_new, s["name"]))
        tag = "new" if was_new else "dup"
        print(f"  [{tag}] {gid[:12]}  {s['name']}")

    # Sync cache so α and c_log get computed
    print("\nSyncing DB (computes α exact — this may take a moment)...")
    with DB() as db:
        db.sync(verbose=True)

    return added_ids


if __name__ == "__main__":
    main()
