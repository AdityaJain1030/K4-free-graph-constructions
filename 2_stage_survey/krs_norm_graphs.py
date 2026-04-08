"""
K4-free algebraic graph constructions and conjecture analysis.

Constructs several families of K4-free graphs with controlled independence
number and computes c = α / (n·log(d)/d) to test the conjecture.

Constructions:
  1. Triangle-free Cayley (norm graph on F_{q^2}): K3-free ⊂ K4-free
     - n = q^2, d = q+1 (for q ≡ 1 mod 4) or q (otherwise), symmetric
     - These are known to work: N(-1) = (-1)^{q+1} = 1 for odd q

  2. Polarity graph of PG(2,q): triangle-free, hence K4-free
     - n = q^2+q+1, d = q+1, triangle-free

  3. Paley-like subgraph extraction: take Paley graph, remove K4-creating edges
     - Various n and d, guaranteed K4-free

Usage:
  python krs_norm_graphs.py
  python krs_norm_graphs.py --primes 5 13 17 29 37
  python krs_norm_graphs.py --constructions cayley polarity
  python krs_norm_graphs.py --exact_limit 50 --approx_restarts 1000
"""

import argparse
import math
import random
import time

import numpy as np


# ─────────────────────────────────────────────────────────────────────────────
# Finite field F_{q^2} for prime q  (used by triangle-free Cayley graph)
# ─────────────────────────────────────────────────────────────────────────────

class GF_q2:
    """F_{q^2} = F_q[x] / (irr(x)), irr monic irreducible of degree 2."""

    def __init__(self, q):
        assert self._is_prime(q), f"{q} is not prime"
        self.q = q
        self.irr = self._find_irreducible()  # (a0, a1) for x^2 + a1*x + a0
        self.n = q ** 2
        self.zero = (0, 0)
        self.one = (1, 0)
        self._elements = None
        self._norm_cache = None

    @staticmethod
    def _is_prime(n):
        if n < 2: return False
        for d in range(2, int(n**0.5) + 1):
            if n % d == 0: return False
        return True

    def _find_irreducible(self):
        """Monic irreducible degree 2 over F_q: x^2 + a1*x + a0."""
        q = self.q
        for a0 in range(q):
            for a1 in range(q):
                has_root = False
                for x in range(q):
                    val = (x * x + a1 * x + a0) % q
                    if val == 0:
                        has_root = True
                        break
                if not has_root:
                    return (a0, a1)
        raise RuntimeError(f"No irreducible degree-2 poly over F_{q}")

    @property
    def elements(self):
        if self._elements is None:
            q = self.q
            self._elements = [(a, b) for a in range(q) for b in range(q)]
        return self._elements

    def sub(self, a, b):
        q = self.q
        return ((a[0] - b[0]) % q, (a[1] - b[1]) % q)

    def mul(self, a, b):
        q = self.q
        ir = self.irr
        # (a0 + a1*x)(b0 + b1*x) = a0*b0 + (a0*b1+a1*b0)*x + a1*b1*x^2
        c0 = a[0] * b[0]
        c1 = a[0] * b[1] + a[1] * b[0]
        c2 = a[1] * b[1]
        # x^2 = -ir[1]*x - ir[0]
        r0 = (c0 - c2 * ir[0]) % q
        r1 = (c1 - c2 * ir[1]) % q
        return (r0, r1)

    def power(self, a, exp):
        if exp == 0: return self.one
        result = self.one
        base = a
        while exp > 0:
            if exp & 1: result = self.mul(result, base)
            base = self.mul(base, base)
            exp >>= 1
        return result

    def norm(self, a):
        """N(a) = a^{q+1}. Result is in F_q."""
        if a == self.zero: return 0
        result = self.power(a, self.q + 1)
        if result[1] != 0:
            raise ValueError(f"Norm not in base field: {result}")
        return result[0]

    def precompute_norms(self):
        """Cache norms for all elements."""
        if self._norm_cache is None:
            self._norm_cache = {e: self.norm(e) for e in self.elements}
        return self._norm_cache


# ─────────────────────────────────────────────────────────────────────────────
# Construction 1: Triangle-free Cayley graph on F_{q^2}
# ─────────────────────────────────────────────────────────────────────────────

def build_cayley_triangle_free(q):
    """
    Cayley graph on F_{q^2} with connection set C = {a : N(a) = 1}.
    
    N(a) = a^{q+1}. Since q+1 is even for odd q, N(-1) = (-1)^{q+1} = 1,
    so C = -C (symmetric). The graph is:
      - n = q^2 vertices
      - |C| = (q^2-1)/(q-1) = q+1 regular  
      - Triangle-free (proven), hence K4-free
      - α = Θ(q · log q) by Shearer/AKS bounds
    """
    F = GF_q2(q)
    elts = F.elements
    n = len(elts)
    norms = F.precompute_norms()

    # Connection set: elements with norm 1
    conn = {a for a in elts if a != F.zero and norms[a] == 1}
    
    # Verify symmetry: for each a in conn, -a should also be in conn
    neg_check = all(F.sub(F.zero, a) in conn for a in conn)
    
    print(f"  Cayley(F_{q}^2, norm=1): n={n}, |C|={len(conn)}, "
          f"expected={q+1}, symmetric={neg_check}")

    idx = {e: i for i, e in enumerate(elts)}
    adj = np.zeros((n, n), dtype=np.uint8)
    
    for i, x in enumerate(elts):
        for a in conn:
            y = F.sub(x, a)  # y = x - a, so x - y = a, N(a) = 1
            j = idx[y]
            if i != j:
                adj[i, j] = 1
                adj[j, i] = 1

    return adj, f"Cayley_TF(q={q})"


# ─────────────────────────────────────────────────────────────────────────────
# Construction 2: Polarity graph of PG(2,q)
# ─────────────────────────────────────────────────────────────────────────────

def build_polarity_graph(q):
    """
    Orthogonal polarity graph of PG(2,q).
    
    Vertices: points of PG(2,q) = nonzero vectors in F_q^3 up to scalar mult.
    Adjacency: [x] ~ [y] iff x·y = 0  (orthogonal under standard inner product)
    
    Properties:
      - n = q^2 + q + 1
      - Most vertices have degree q+1, some have degree q (self-orthogonal points)
      - Triangle-free (hence K4-free)
      - α ≈ q + 1 to q√q depending on structure
    
    For q prime, implementation is straightforward.
    """
    assert _is_prime(q), f"{q} must be prime"
    
    # Enumerate projective points: (a:b:c) normalized so first nonzero coord = 1
    points = []
    seen = set()
    for a in range(q):
        for b in range(q):
            for c in range(q):
                if a == 0 and b == 0 and c == 0:
                    continue
                # Normalize: divide by first nonzero coordinate
                vec = (a, b, c)
                first_nz = next(x for x in vec if x != 0)
                inv = pow(first_nz, q - 2, q)  # Fermat's little theorem
                canon = tuple((x * inv) % q for x in vec)
                if canon not in seen:
                    seen.add(canon)
                    points.append(canon)

    n = len(points)
    print(f"  Polarity(PG(2,{q})): n={n}, expected={q**2+q+1}")

    adj = np.zeros((n, n), dtype=np.uint8)
    for i in range(n):
        for j in range(i + 1, n):
            # Inner product mod q
            dot = sum(points[i][k] * points[j][k] for k in range(3)) % q
            if dot == 0:
                adj[i, j] = 1
                adj[j, i] = 1

    return adj, f"Polarity(PG(2,{q}))"


# ─────────────────────────────────────────────────────────────────────────────
# Construction 3: Cayley graph on Z_p with quadratic residue variants
# ─────────────────────────────────────────────────────────────────────────────

def build_paley_k4free(p):
    """
    Start from Paley graph on Z_p (connect i~j iff i-j is a QR mod p),
    then greedily remove edges that participate in K4s.
    
    For p ≡ 1 mod 4, the Paley graph is well-defined and self-complementary.
    It may contain K4s for larger p, so we strip them.
    """
    assert _is_prime(p) and p % 4 == 1, f"{p} must be prime ≡ 1 mod 4"

    # Quadratic residues mod p
    qr = set()
    for x in range(1, p):
        qr.add(pow(x, 2, p))

    adj = np.zeros((p, p), dtype=np.uint8)
    for i in range(p):
        for j in range(i + 1, p):
            if (i - j) % p in qr:
                adj[i, j] = 1
                adj[j, i] = 1

    # Check and remove K4s
    k4_count = 0
    while True:
        k4 = _find_one_k4(adj)
        if k4 is None:
            break
        k4_count += 1
        # Remove edge with highest degree sum (least damage heuristic)
        a, b, c, d = k4
        verts = [a, b, c, d]
        edges = [(verts[i], verts[j]) for i in range(4) for j in range(i+1, 4)
                 if adj[verts[i], verts[j]]]
        # Pick edge in most triangles
        best_edge = max(edges, key=lambda e: adj[e[0]].sum() + adj[e[1]].sum())
        adj[best_edge[0], best_edge[1]] = 0
        adj[best_edge[1], best_edge[0]] = 0

    if k4_count > 0:
        print(f"  Paley({p}) → K4-free: removed edges from {k4_count} K4s")

    return adj, f"Paley_K4free(p={p})"


def _find_one_k4(adj):
    """Find one K4, return (a,b,c,d) or None."""
    N = adj.shape[0]
    nbr = [0] * N
    for i in range(N):
        for j in range(N):
            if adj[i, j]:
                nbr[i] |= 1 << j
    for a in range(N):
        for b in range(a + 1, N):
            if not (nbr[a] >> b & 1):
                continue
            c_bits = nbr[a] & nbr[b] & ~((1 << (b + 1)) - 1)
            while c_bits:
                lsb = c_bits & -c_bits
                c = lsb.bit_length() - 1
                c_bits ^= lsb
                d_bits = nbr[a] & nbr[b] & nbr[c] & ~((1 << (c + 1)) - 1)
                if d_bits:
                    d = (d_bits & -d_bits).bit_length() - 1
                    return (a, b, c, d)
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _is_prime(n):
    if n < 2: return False
    for d in range(2, int(n**0.5) + 1):
        if n % d == 0: return False
    return True


def has_k4(adj):
    return _find_one_k4(adj) is not None


def alpha_exact(adj):
    N = adj.shape[0]
    nbr = [0] * N
    for i in range(N):
        for j in range(N):
            if adj[i, j]:
                nbr[i] |= 1 << j
    best = [0]
    def bb(candidates, size):
        if candidates == 0:
            best[0] = max(best[0], size)
            return
        if size + bin(candidates).count('1') <= best[0]:
            return
        v = (candidates & -candidates).bit_length() - 1
        bb(candidates & ~nbr[v] & ~(1 << v), size + 1)
        bb(candidates & ~(1 << v), size)
    bb((1 << N) - 1, 0)
    return best[0]


def alpha_approx(adj, n_restarts=500):
    N = adj.shape[0]
    nbr = [0] * N
    for i in range(N):
        for j in range(N):
            if adj[i, j]:
                nbr[i] |= 1 << j
    best = 0
    verts = list(range(N))
    for _ in range(n_restarts):
        random.shuffle(verts)
        avail = (1 << N) - 1
        size = 0
        for v in verts:
            if avail & (1 << v):
                size += 1
                avail &= ~nbr[v] & ~(1 << v)
        best = max(best, size)
    return best


# ─────────────────────────────────────────────────────────────────────────────
# Analysis
# ─────────────────────────────────────────────────────────────────────────────

def analyse_graph(adj, name, exact_limit=50, approx_restarts=500):
    """Full analysis of a single constructed graph."""
    n = adj.shape[0]
    degrees = adj.sum(axis=1)
    d_min, d_max = int(degrees.min()), int(degrees.max())
    d_mean = float(degrees.mean())
    d_var = float(degrees.var())
    edges = int(adj.sum()) // 2
    is_regular = (d_min == d_max)

    print(f"\n{'='*70}")
    print(f"{name}")
    print(f"{'='*70}")
    print(f"  n={n}, edges={edges}, density={edges/(n*(n-1)//2):.4f}")
    print(f"  Degree: min={d_min}, max={d_max}, mean={d_mean:.2f}, var={d_var:.4f}")
    print(f"  Regular: {is_regular}")

    # K4 check
    print(f"  K4-free: ", end="", flush=True)
    t0 = time.time()
    k4 = has_k4(adj)
    print(f"{'NO — K4 found!' if k4 else 'Yes ✓'} ({time.time()-t0:.1f}s)")
    if k4:
        print(f"  SKIPPING — graph contains K4")
        return None

    # Triangle check
    tri = 0
    nbr_sets = [set(np.where(adj[i])[0]) for i in range(n)]
    for i in range(n):
        for j in range(i+1, n):
            if adj[i, j]:
                common = nbr_sets[i] & nbr_sets[j]
                tri += sum(1 for k in common if k > j)
    print(f"  Triangles: {tri} ({'triangle-free' if tri == 0 else 'has triangles'})")

    # Independence number
    if n <= exact_limit:
        print(f"  Computing exact α (n={n})...", end=" ", flush=True)
        t0 = time.time()
        alpha = alpha_exact(adj)
        method = "exact"
        print(f"α = {alpha} ({time.time()-t0:.1f}s)")
    else:
        print(f"  Computing approx α ({approx_restarts} restarts)...", end=" ", flush=True)
        t0 = time.time()
        alpha = alpha_approx(adj, n_restarts=approx_restarts)
        method = "approx"
        print(f"α ≥ {alpha} ({time.time()-t0:.1f}s)")

    # Conjecture ratios
    d = d_max
    if d <= 1:
        print(f"  d_max too small, skipping ratio computation")
        return None

    f_val = n * math.log(d) / d
    c_log = alpha / f_val
    ratio = f_val / alpha

    f_sqrt = n * math.sqrt(math.log(d)) / d
    c_sqrt = alpha / f_sqrt

    print(f"\n  ── Conjecture: α ≥ c · n·log(d)/d ──")
    print(f"  d_max        = {d}")
    print(f"  n·log(d)/d   = {f_val:.4f}")
    print(f"  α            = {alpha} ({method})")
    print(f"  f(d)/α       = {ratio:.4f}")
    print(f"  c_log        = {c_log:.4f}")

    print(f"\n  ── Comparison: α ≥ c · n·√(log d)/d ──")
    print(f"  n·√(log d)/d = {f_sqrt:.4f}")
    print(f"  c_sqrt       = {c_sqrt:.4f}")

    return {
        "name": name, "n": n, "d": d, "edges": edges,
        "is_regular": is_regular, "d_var": d_var,
        "triangles": tri,
        "alpha": alpha, "method": method,
        "f_val": f_val, "ratio": ratio,
        "c_log": c_log, "c_sqrt": c_sqrt,
    }


def summary_table(results):
    print(f"\n{'='*70}")
    print(f"SUMMARY TABLE")
    print(f"{'='*70}")
    print(f"{'name':<25} {'n':>5} {'d':>4} {'α':>4} {'meth':>6} "
          f"{'f/α':>7} {'c_log':>7} {'c_sqrt':>7}")
    print("-" * 70)
    for r in results:
        print(f"{r['name']:<25} {r['n']:>5} {r['d']:>4} {r['alpha']:>4} "
              f"{r['method']:>6} {r['ratio']:>7.4f} {r['c_log']:>7.4f} "
              f"{r['c_sqrt']:>7.4f}")

    # Sort by n for trend
    by_n = sorted(results, key=lambda r: r['n'])
    if len(by_n) >= 2:
        print(f"\n  c_log values sorted by n:")
        for r in by_n:
            print(f"    n={r['n']:>5}  c_log={r['c_log']:.4f}  c_sqrt={r['c_sqrt']:.4f}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--primes", type=int, nargs="+", default=[5, 7, 11, 13, 17],
                        help="Primes q for Cayley and polarity constructions")
    parser.add_argument("--paley_primes", type=int, nargs="+", default=[],
                        help="Primes p ≡ 1 mod 4 for Paley K4-free extraction")
    parser.add_argument("--constructions", nargs="+",
                        default=["cayley", "polarity"],
                        choices=["cayley", "polarity", "paley"],
                        help="Which constructions to run")
    parser.add_argument("--exact_limit", type=int, default=50)
    parser.add_argument("--approx_restarts", type=int, default=500)
    args = parser.parse_args()

    results = []

    for q in args.primes:
        if "cayley" in args.constructions:
            print(f"\n--- Building Cayley triangle-free graph for q={q} ---")
            try:
                adj, name = build_cayley_triangle_free(q)
                r = analyse_graph(adj, name, args.exact_limit, args.approx_restarts)
                if r: results.append(r)
            except Exception as e:
                print(f"  ERROR: {e}")

        if "polarity" in args.constructions:
            print(f"\n--- Building polarity graph for q={q} ---")
            try:
                adj, name = build_polarity_graph(q)
                r = analyse_graph(adj, name, args.exact_limit, args.approx_restarts)
                if r: results.append(r)
            except Exception as e:
                print(f"  ERROR: {e}")

    if "paley" in args.constructions:
        paley_ps = args.paley_primes or [p for p in [5, 13, 17, 29, 37, 41]
                                          if p % 4 == 1 and _is_prime(p)]
        for p in paley_ps:
            print(f"\n--- Building Paley K4-free graph for p={p} ---")
            try:
                adj, name = build_paley_k4free(p)
                r = analyse_graph(adj, name, args.exact_limit, args.approx_restarts)
                if r: results.append(r)
            except Exception as e:
                print(f"  ERROR: {e}")

    if results:
        summary_table(results)


if __name__ == "__main__":
    main()