"""Spectrum-balance screen for tensor-derived compositions.

Computes the Hoffman-predicted c_log of G1 ⊗ G2 for every pair of
regular K4-free graphs in the DB, asks whether any pair's predicted
c_log drops below plateau A (0.6789). If the whole basin is above
plateau, the tensor-Hoffman direction is closed; if any pair dips
below, we have a concrete target to try constructing.

For regular d-regular factors:
  λ_min(G1⊗G2) = min(λi·μj) over eigenvalue pairs
  d(G1⊗G2)    = d1·d2
  N(G1⊗G2)    = N1·N2
  Hoffman α ≤ N · (-λ_min)/(d - λ_min)
  c_log       = α·d / (N · ln d)

The real tensor product has α ≥ max(α1·N2, α2·N1), far above Hoffman,
but the Hoffman floor tells us the best case attainable by any
pseudorandom-composition scheme that preserves the tensor spectrum.
"""
import sqlite3
import json
import math
from itertools import combinations_with_replacement

DB = "cache.db"
PLATEAU_A = 0.678915

def tensor_lam_min(eigs1, eigs2):
    # min of products — eigenvalues are real, so min over pairs
    mn = math.inf
    for a in eigs1:
        for b in eigs2:
            p = a * b
            if p < mn:
                mn = p
    return mn

def hoffman_c_log(N, d, lam_min):
    if d - lam_min <= 0 or d <= 1:
        return None
    alpha_hoff = N * (-lam_min) / (d - lam_min)
    if alpha_hoff <= 0:
        return None
    return alpha_hoff * d / (N * math.log(d))

def main():
    conn = sqlite3.connect(DB)
    q = """
      SELECT graph_id, n, d_max, alpha, c_log, eigenvalues_adj, source
      FROM cache
      WHERE is_k4_free=1 AND is_regular=1 AND n BETWEEN 10 AND 100
    """
    graphs = []
    for gid, n, d, a, c, evs, src in conn.execute(q):
        eigs = json.loads(evs)
        graphs.append((gid, n, d, a, c, eigs, src))

    # Dedup by (n, sorted spectrum rounded) — different sources of same graph
    seen = {}
    for g in graphs:
        key = (g[1], g[2], tuple(round(x, 6) for x in sorted(g[5])))
        if key not in seen or g[4] < seen[key][4]:
            seen[key] = g
    graphs = list(seen.values())
    print(f"De-duplicated regular K4-free graphs in DB: {len(graphs)}")

    # Pairwise tensor Hoffman
    best = []
    n_pairs = 0
    below_plateau = []
    for i in range(len(graphs)):
        for j in range(i, len(graphs)):
            g1, g2 = graphs[i], graphs[j]
            N = g1[1] * g2[1]
            d = g1[2] * g2[2]
            if d < 2:
                continue
            lm = tensor_lam_min(g1[5], g2[5])
            c = hoffman_c_log(N, d, lm)
            if c is None:
                continue
            n_pairs += 1
            rec = (c, g1[1], g1[2], g1[6], g2[1], g2[2], g2[6], N, d, lm)
            if c < PLATEAU_A:
                below_plateau.append(rec)
            if len(best) < 20 or c < best[-1][0]:
                best.append(rec)
                best.sort()
                best = best[:20]

    print(f"Pairs screened: {n_pairs}")
    print(f"Pairs with tensor-Hoffman c_log < {PLATEAU_A}: {len(below_plateau)}")
    print()
    print("Top-20 lowest tensor-Hoffman c_log (predicted):")
    print(f"{'c_pred':>8}  {'N1':>4} {'d1':>3} {'src1':<22}  {'N2':>4} {'d2':>3} {'src2':<22}  {'N':>6} {'d':>5} {'λmin':>8}")
    for c, n1, d1, s1, n2, d2, s2, N, d, lm in best:
        print(f"{c:8.4f}  {n1:4d} {d1:3d} {s1:<22}  {n2:4d} {d2:3d} {s2:<22}  {N:6d} {d:5d} {lm:8.3f}")

    # Also: if pair is (P(17) × G), what's the prediction? — most revealing
    paley17 = [g for g in graphs if g[1] == 17 and g[2] == 8]
    if paley17:
        p17 = paley17[0]
        print()
        print(f"Using P(17) (N=17, d=8, λ=[{min(p17[5]):.3f}..{max(p17[5]):.3f}]) as G1:")
        p_best = []
        for g2 in graphs:
            N = p17[1] * g2[1]
            d = p17[2] * g2[2]
            lm = tensor_lam_min(p17[5], g2[5])
            c = hoffman_c_log(N, d, lm)
            if c is None: continue
            p_best.append((c, g2[1], g2[2], g2[6]))
        p_best.sort()
        print(f"Top-10 partners for P(17) ⊗ G2:")
        for c, n2, d2, s2 in p_best[:10]:
            print(f"  c_pred={c:.4f}  G2: N={n2} d={d2} {s2}")

if __name__ == "__main__":
    main()
