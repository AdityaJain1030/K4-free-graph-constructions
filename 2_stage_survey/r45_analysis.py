"""
Analyse R(4,5) extremal graphs from McKay's g6 database.
Usage: python r45_analysis.py r45_24.g6

Outputs everything needed to decide how to seed Axplorer:
  - Basic stats (count, N, regularity, degree sequence)
  - Edge density and degree distribution across all graphs
  - Independence number verification (should be 4)
  - Clique number verification (should be ≤ 3, i.e. K4-free)
  - Triangle counts and local clustering
  - Eigenvalue spectrum (algebraic structure fingerprint)
  - Automorphism group size (symmetry level)
  - Pairwise isomorphism check (how many distinct graphs?)
  - Diameter, girth, connectivity
  - Degree-degree correlation (assortativity)
  - Common neighbor statistics (λ and μ for near-SRG detection)
"""

import sys
import numpy as np
import networkx as nx
from collections import Counter

try:
    from networkx.algorithms.isomorphism import GraphMatcher
except ImportError:
    GraphMatcher = None


def load_g6(path):
    """Load all graphs from a g6 file."""
    graphs = []
    with open(path, "r") as f:
        for line in f:
            line = line.strip()
            if line:
                graphs.append(nx.from_graph6_bytes(line.encode("ascii")))
    return graphs


def alpha_exact(G):
    """Exact independence number via networkx complement clique."""
    Gc = nx.complement(G)
    cliques = nx.find_cliques(Gc)
    return max(len(c) for c in cliques)


def clique_number(G):
    """Exact clique number."""
    return max(len(c) for c in nx.find_cliques(G))


def triangle_count(G):
    """Total number of triangles."""
    return sum(nx.triangles(G).values()) // 3


def common_neighbor_stats(G):
    """
    For all pairs (u,v), compute |common neighbors|.
    Split by adjacent vs non-adjacent pairs.
    Returns (lambda_stats, mu_stats) where each is (min, max, mean, std).
    """
    adj_cn = []   # common neighbors for adjacent pairs
    nonadj_cn = []  # common neighbors for non-adjacent pairs

    nodes = list(G.nodes())
    nbr = {v: set(G.neighbors(v)) for v in nodes}

    for i, u in enumerate(nodes):
        for v in nodes[i+1:]:
            cn = len(nbr[u] & nbr[v])
            if G.has_edge(u, v):
                adj_cn.append(cn)
            else:
                nonadj_cn.append(cn)

    def stats(arr):
        if not arr:
            return (0, 0, 0.0, 0.0)
        a = np.array(arr)
        return (int(a.min()), int(a.max()), float(a.mean()), float(a.std()))

    return stats(adj_cn), stats(nonadj_cn)


def eigenvalue_summary(G):
    """Adjacency matrix eigenvalues, sorted descending."""
    A = nx.to_numpy_array(G)
    eigs = np.linalg.eigvalsh(A)
    return np.sort(eigs)[::-1]


def analyse_graph(G, idx, verbose=True):
    """Full analysis of a single graph."""
    n = G.number_of_nodes()
    m = G.number_of_edges()
    max_edges = n * (n - 1) // 2

    degrees = sorted([d for _, d in G.degree()], reverse=True)
    deg_arr = np.array(degrees)
    deg_counter = Counter(degrees)

    # Regularity check
    is_regular = (deg_arr.min() == deg_arr.max())
    d_min, d_max = int(deg_arr.min()), int(deg_arr.max())
    d_mean = float(deg_arr.mean())
    d_var = float(deg_arr.var())

    result = {
        "idx": idx,
        "n": n,
        "m": m,
        "density": m / max_edges,
        "degrees": degrees,
        "deg_distribution": dict(deg_counter),
        "is_regular": is_regular,
        "d_min": d_min,
        "d_max": d_max,
        "d_mean": d_mean,
        "d_var": d_var,
    }

    # Independence and clique numbers
    alpha = alpha_exact(G)
    omega = clique_number(G)
    result["alpha"] = alpha
    result["omega"] = omega
    result["k4_free"] = (omega <= 3)

    # Triangles
    result["triangles"] = triangle_count(G)

    # Connectivity
    result["is_connected"] = nx.is_connected(G)
    if result["is_connected"]:
        result["diameter"] = nx.diameter(G)
        result["radius"] = nx.radius(G)
        result["girth"] = min(
            (len(c) for c in nx.cycle_basis(G)), default=None
        )
    else:
        result["diameter"] = None
        result["radius"] = None
        result["girth"] = None

    # Assortativity
    try:
        result["assortativity"] = nx.degree_assortativity_coefficient(G)
    except Exception:
        result["assortativity"] = None

    # Common neighbor stats (SRG detection)
    lambda_stats, mu_stats = common_neighbor_stats(G)
    result["lambda_cn"] = lambda_stats  # (min, max, mean, std)
    result["mu_cn"] = mu_stats

    # Check if strongly regular
    # SRG iff lambda and mu are both constant (std = 0)
    result["is_srg"] = (lambda_stats[3] == 0.0 and mu_stats[3] == 0.0)
    if result["is_srg"]:
        result["srg_params"] = (n, d_max, lambda_stats[0], mu_stats[0])

    # Eigenvalues
    eigs = eigenvalue_summary(G)
    result["eigenvalues"] = eigs
    unique_eigs = np.unique(np.round(eigs, 6))
    result["n_distinct_eigenvalues"] = len(unique_eigs)

    # Automorphism group size (via nauty if available, else skip)
    try:
        import pynauty
        # If pynauty available, use it
        pass
    except ImportError:
        pass
    # Fallback: count via networkx (slow but works for small graphs)
    # Skip for now — too slow for large batches

    if verbose:
        print(f"\n{'='*60}")
        print(f"Graph {idx}: n={n}, m={m}, density={result['density']:.4f}")
        print(f"  Degree: min={d_min}, max={d_max}, mean={d_mean:.2f}, var={d_var:.4f}")
        print(f"  Regular: {is_regular}")
        print(f"  Degree distribution: {dict(deg_counter)}")
        print(f"  alpha={alpha}, omega={omega}, K4-free={result['k4_free']}")
        print(f"  Triangles: {result['triangles']}")
        print(f"  Connected: {result['is_connected']}, "
              f"Diameter: {result['diameter']}, Girth: {result['girth']}")
        print(f"  Assortativity: {result['assortativity']}")
        print(f"  Common nbrs (adj pairs):    min={lambda_stats[0]}, max={lambda_stats[1]}, "
              f"mean={lambda_stats[2]:.2f}, std={lambda_stats[3]:.4f}")
        print(f"  Common nbrs (nonadj pairs): min={mu_stats[0]}, max={mu_stats[1]}, "
              f"mean={mu_stats[2]:.2f}, std={mu_stats[3]:.4f}")
        print(f"  Strongly regular: {result['is_srg']}", end="")
        if result["is_srg"]:
            print(f"  params={result['srg_params']}")
        else:
            print()
        eig_rounded = np.round(eigs, 3)
        print(f"  Eigenvalues (top 5): {eig_rounded[:5]}")
        print(f"  Eigenvalues (bot 5): {eig_rounded[-5:]}")
        print(f"  Distinct eigenvalues: {result['n_distinct_eigenvalues']}")

    return result


def pairwise_isomorphism(graphs, max_check=50):
    """Check how many non-isomorphic graphs in the set."""
    n = min(len(graphs), max_check)
    unique = [graphs[0]]
    iso_classes = [0] * n

    for i in range(1, n):
        found = False
        for j, rep in enumerate(unique):
            if nx.is_isomorphic(graphs[i], rep):
                iso_classes[i] = j
                found = True
                break
        if not found:
            iso_classes[i] = len(unique)
            unique.append(graphs[i])

    return len(unique), iso_classes[:n]


def aggregate_summary(results):
    """Print aggregate stats across all graphs."""
    print(f"\n{'='*60}")
    print(f"AGGREGATE SUMMARY ({len(results)} graphs)")
    print(f"{'='*60}")

    alphas = Counter(r["alpha"] for r in results)
    omegas = Counter(r["omega"] for r in results)
    regulars = sum(1 for r in results if r["is_regular"])
    srgs = sum(1 for r in results if r["is_srg"])
    k4free = sum(1 for r in results if r["k4_free"])

    d_maxes = [r["d_max"] for r in results]
    d_mins = [r["d_min"] for r in results]
    d_means = [r["d_mean"] for r in results]
    d_vars = [r["d_var"] for r in results]
    densities = [r["density"] for r in results]
    tri_counts = [r["triangles"] for r in results]

    print(f"  K4-free: {k4free}/{len(results)}")
    print(f"  Alpha distribution: {dict(alphas)}")
    print(f"  Omega distribution: {dict(omegas)}")
    print(f"  Regular: {regulars}/{len(results)}")
    print(f"  Strongly regular: {srgs}/{len(results)}")
    print()
    print(f"  d_max:    min={min(d_maxes)}, max={max(d_maxes)}, "
          f"mean={np.mean(d_maxes):.2f}")
    print(f"  d_min:    min={min(d_mins)}, max={max(d_mins)}, "
          f"mean={np.mean(d_mins):.2f}")
    print(f"  d_mean:   min={min(d_means):.2f}, max={max(d_means):.2f}, "
          f"mean={np.mean(d_means):.2f}")
    print(f"  d_var:    min={min(d_vars):.4f}, max={max(d_vars):.4f}, "
          f"mean={np.mean(d_vars):.4f}")
    print(f"  density:  min={min(densities):.4f}, max={max(densities):.4f}, "
          f"mean={np.mean(densities):.4f}")
    print(f"  triangles: min={min(tri_counts)}, max={max(tri_counts)}, "
          f"mean={np.mean(tri_counts):.1f}")

    # Eigenvalue consistency
    if len(results) > 1:
        eig_stacks = np.array([r["eigenvalues"] for r in results])
        eig_std = eig_stacks.std(axis=0)
        print(f"\n  Eigenvalue variation across graphs (std per position):")
        print(f"    max std: {eig_std.max():.4f}, mean std: {eig_std.mean():.4f}")

    # Lambda/mu spread
    lambda_stds = [r["lambda_cn"][3] for r in results]
    mu_stds = [r["mu_cn"][3] for r in results]
    print(f"\n  Lambda (adj CN) std: min={min(lambda_stds):.4f}, "
          f"max={max(lambda_stds):.4f}")
    print(f"  Mu (nonadj CN) std: min={min(mu_stds):.4f}, "
          f"max={max(mu_stds):.4f}")


def main():
    if len(sys.argv) < 2:
        print("Usage: python r45_analysis.py <file.g6> [--max N] [--quiet]")
        sys.exit(1)

    path = sys.argv[1]
    max_graphs = None
    verbose = True
    for i, arg in enumerate(sys.argv[2:], 2):
        if arg == "--max" and i + 1 < len(sys.argv):
            max_graphs = int(sys.argv[i + 1])
        if arg == "--quiet":
            verbose = False

    print(f"Loading graphs from {path}...")
    graphs = load_g6(path)
    print(f"Loaded {len(graphs)} graphs")

    if max_graphs:
        graphs = graphs[:max_graphs]
        print(f"Analysing first {max_graphs}")

    # Analyse each graph
    results = []
    for i, G in enumerate(graphs):
        r = analyse_graph(G, i, verbose=verbose)
        results.append(r)

    # Aggregate
    aggregate_summary(results)

    # Isomorphism classes (up to 50 graphs)
    if len(graphs) > 1:
        print(f"\nChecking isomorphism classes (up to {min(len(graphs), 50)})...")
        n_classes, classes = pairwise_isomorphism(graphs, max_check=50)
        print(f"  Found {n_classes} non-isomorphic graphs "
              f"(among first {min(len(graphs), 50)})")

    # Seeding relevance summary
    print(f"\n{'='*60}")
    print("SEEDING RELEVANCE SUMMARY")
    print(f"{'='*60}")
    r0 = results[0]
    print(f"  These are n={r0['n']} K4-free graphs with alpha={r0['alpha']}")
    print(f"  To seed n=35 Axplorer run:")
    print(f"    - Need to add {35 - r0['n']} vertices + edges, maintaining K4-free")
    print(f"    - Core has degree ~{r0['d_mean']:.0f}, target regime unclear")
    print(f"    - If extensions keep alpha=5, ideal seeds")
    print(f"    - If alpha inflates to 6-7, still better than random greedy")
    print(f"    - Regularity of core: {'YES' if r0['is_regular'] else 'NO'} "
          f"(var={r0['d_var']:.4f})")
    print(f"    - SRG structure: {'YES' if r0['is_srg'] else 'NO'}")


if __name__ == "__main__":
    main()