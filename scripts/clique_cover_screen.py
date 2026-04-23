"""Clique-cover screen for MV-relevant structure on frontier graphs.

Background: Mattheus-Verstraete start with a graph whose max cliques
meet pairwise in ≤1 vertex ("spread" / "linear space") and satisfy an
O'Nan-style condition, then randomly bipartize each clique to kill K4
while keeping α small. Our catalog is already K4-free (cliques ≤ size 3),
so direct MV doesn't apply, but the clique-intersection fingerprint of
plateau-A and near-plateau graphs tells us whether the independence
structure admits any MV-analog decomposition.

For each screened graph compute:
- Max clique size ω
- Number of max cliques M
- Pairwise clique intersection histogram: how many pairs meet in 0, 1, 2 vertices
- Spread flag: all max cliques pairwise meet in ≤1 vertex
- Clique-cover density: fraction of edges in some max clique
- O'Nan flag (vacuous when ω≤3 and G is K4-free, but useful when ω grows)

Also run on the complement Ḡ (restricted to small graphs where Ḡ clique
enumeration is tractable) to see if Ḡ has MV-like structure — this tells
us whether the *independent set* side of G admits bipartization-style
splitting.
"""
import itertools
from collections import Counter
import sys

sys.path.insert(0, '.')
import networkx as nx
from graph_db.db import DB as GraphDB

PLATEAU_A = 0.678915

def clique_cover_stats(G):
    # All maximal cliques (may be mixed size; pick max-size ones)
    all_max = list(nx.find_cliques(G))
    if not all_max:
        return None
    omega = max(len(c) for c in all_max)
    max_cliques = [frozenset(c) for c in all_max if len(c) == omega]
    M = len(max_cliques)
    # Pairwise intersection histogram
    hist = Counter()
    if M >= 2:
        for a, b in itertools.combinations(max_cliques, 2):
            hist[len(a & b)] += 1
    spread = all(len(a & b) <= 1 for a, b in itertools.combinations(max_cliques, 2))
    # Clique-cover density: edges covered by some max clique / total edges
    covered = set()
    for c in max_cliques:
        c_list = list(c)
        for i in range(len(c_list)):
            for j in range(i+1, len(c_list)):
                u, v = c_list[i], c_list[j]
                covered.add((min(u,v), max(u,v)))
    e_total = G.number_of_edges()
    density = len(covered) / e_total if e_total else 0
    return dict(omega=omega, M=M, hist=dict(hist), spread=spread,
                density=density, n=G.number_of_nodes(), m=e_total)

def main():
    db = GraphDB()
    rows = db.query(
        where={'is_k4_free': 1},
        ranges={'c_log': (0.0, 0.72), 'n': (10, 100)},
        order_by='c_log',
    )
    # Dedup by graph_id (multiple sources may cache same graph)
    seen = set()
    unique = []
    for r in rows:
        if r['graph_id'] in seen: continue
        seen.add(r['graph_id'])
        unique.append(r)
    print(f"Near/at-plateau graphs to screen: {len(unique)}")

    results = []
    for r in unique:
        G = db.nx(r['graph_id'])
        if G is None:
            continue
        s = clique_cover_stats(G)
        if s is None:
            continue
        results.append((r['c_log'], r['n'], r['alpha'], r['d_max'], r['source'], r['graph_id'], s))

    # Report
    print()
    print(f"{'c_log':>7} {'N':>4} {'α':>3} {'d':>3} {'ω':>2} {'M':>5} {'dens':>5} {'spread':>7} {'source':<24} hist")
    for c, n, a, d, src, gid, s in results:
        hist_s = ",".join(f"{k}:{v}" for k, v in sorted(s['hist'].items())) or "-"
        print(f"{c:7.4f} {n:4d} {a:3d} {d:3d} {s['omega']:2d} {s['M']:5d} {s['density']:5.2f} {'Y' if s['spread'] else 'N':>7} {src:<24} {hist_s}")

    # Flag graphs with spread clique structure
    spreads = [r for r in results if r[6]['spread'] and r[6]['M'] >= 2 and r[6]['omega'] >= 3]
    print()
    print(f"Graphs with spread clique structure (all max cliques pairwise meet in ≤1 vtx, ω≥3): {len(spreads)}")
    for c, n, a, d, src, gid, s in spreads[:20]:
        print(f"  c={c:.4f} N={n} α={a} d={d} ω={s['omega']} M={s['M']} density={s['density']:.2f} src={src}")

    # Complement fingerprint on the plateau-A chain — limited to N ≤ 34 to
    # keep enumeration tractable; Ḡ of K4-free regular is dense and its
    # maximal-clique count can blow up exponentially at larger N.
    print()
    print("Complement clique structure (plateau-A chain only, N ≤ 34):")
    seen_pa = set()
    for c, n, a, d, src, gid, s in results:
        if c > PLATEAU_A + 1e-6: continue
        if n > 34: continue
        if (n, src) in seen_pa: continue
        seen_pa.add((n, src))
        G = db.nx(gid)
        if G is None: continue
        Gc = nx.complement(G)
        sc = clique_cover_stats(Gc)
        if sc is None: continue
        print(f"  G: N={n} α={a} d={d} src={src}  →  Ḡ: ω={sc['omega']} M={sc['M']} density={sc['density']:.3f} spread={sc['spread']}")

if __name__ == "__main__":
    main()
