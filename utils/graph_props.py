"""
utils/graph_props.py
====================
Canonical graph property utilities shared across search/ and graph_db.
Do not import funsearch here; funsearch keeps its own copies.
"""

from collections import deque
from math import log

import numpy as np
import networkx as nx


# ---------------------------------------------------------------------------
# Independence number
# ---------------------------------------------------------------------------

def alpha_exact(adj: np.ndarray) -> tuple[int, list[int]]:
    """
    Exact maximum independent set via bitmask branch-and-bound.
    Returns (alpha_value, sorted_vertex_list).
    """
    n = adj.shape[0]
    nbr = [0] * n
    for i in range(n):
        for j in range(n):
            if adj[i, j]:
                nbr[i] |= 1 << j

    best_size = 0
    best_set  = 0

    def popcount(x):
        return bin(x).count("1")

    def branch(candidates, current_set, current_size):
        nonlocal best_size, best_set
        if current_size + popcount(candidates) <= best_size:
            return
        if candidates == 0:
            if current_size > best_size:
                best_size = current_size
                best_set  = current_set
            return
        v = (candidates & -candidates).bit_length() - 1
        branch(candidates & ~nbr[v] & ~(1 << v), current_set | (1 << v), current_size + 1)
        branch(candidates & ~(1 << v), current_set, current_size)

    branch((1 << n) - 1, 0, 0)

    result, tmp = [], best_set
    while tmp:
        v = (tmp & -tmp).bit_length() - 1
        result.append(v)
        tmp &= tmp - 1
    return best_size, sorted(result)


def alpha_exact_nx(G: nx.Graph) -> tuple[int, list[int]]:
    """Convenience wrapper: accepts nx.Graph instead of np.ndarray."""
    adj = np.array(nx.to_numpy_array(G, dtype=np.uint8))
    return alpha_exact(adj)


def alpha_cpsat(
    adj: np.ndarray,
    time_limit: float = 60.0,
    vertex_transitive: bool = False,
) -> tuple[int, list[int]]:
    """
    Exact α via OR-Tools CP-SAT. Faster than `alpha_exact` past n ≈ 40 on
    sparse graphs but pays ~100 ms solver-init overhead and allocates
    ~400 MB RSS per model — prefer `alpha_exact` on small n.

    Set `vertex_transitive=True` to pin x[0]=1 (sound only when some MIS
    contains vertex 0, i.e. vertex-transitive graphs like circulants).
    Returns (0, []) if the solver neither finds nor proves optimum inside
    `time_limit`.
    """
    import os
    from ortools.sat.python import cp_model

    n = adj.shape[0]
    model = cp_model.CpModel()
    x = [model.new_bool_var(f"x_{i}") for i in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            if adj[i, j]:
                model.add(x[i] + x[j] <= 1)
    if vertex_transitive and n > 0:
        model.add(x[0] == 1)
    model.maximize(sum(x))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit
    solver.parameters.num_search_workers = min(8, (os.cpu_count() or 4))
    solver.parameters.log_search_progress = False

    status = solver.solve(model)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return 0, []
    alpha = int(round(solver.objective_value))
    indep = [i for i in range(n) if solver.value(x[i])]
    return alpha, indep


def alpha_cpsat_nx(
    G: nx.Graph,
    time_limit: float = 60.0,
    vertex_transitive: bool = False,
) -> tuple[int, list[int]]:
    """Convenience wrapper: accepts nx.Graph instead of np.ndarray."""
    adj = np.array(nx.to_numpy_array(G, dtype=np.uint8))
    return alpha_cpsat(adj, time_limit=time_limit, vertex_transitive=vertex_transitive)


# ---------------------------------------------------------------------------
# B&B with greedy-clique-cover upper bound
# ---------------------------------------------------------------------------

def alpha_bb_clique_cover(adj: np.ndarray) -> tuple[int, list[int]]:
    """
    Exact α via bitmask B&B with a greedy clique-cover upper bound.

    θ(G) ≥ α(G), so a greedy partition of the candidate subgraph into
    cliques bounds α in that subgraph by the number of cliques. Tighter
    than `alpha_exact`'s popcount bound, typically 2–5× faster on sparse
    graphs. Same memory profile as `alpha_exact`.

    (Greedy *colouring* of the candidate subgraph would bound ω, not α —
    that mistake is easy to make. The MIS-correct analogue is the
    clique cover.)
    """
    n = adj.shape[0]
    nbr = [0] * n
    for i in range(n):
        for j in range(n):
            if adj[i, j]:
                nbr[i] |= 1 << j

    def popcount(x):
        return bin(x).count("1")

    def clique_cover_bound(candidates: int) -> int:
        """Greedy clique partition of the subgraph induced by `candidates`."""
        cliques = 0
        remaining = candidates
        while remaining:
            cliques += 1
            v = (remaining & -remaining).bit_length() - 1
            # grow a clique containing v by intersecting neighbourhoods
            clique_mask = 1 << v
            extendable = remaining & nbr[v]
            while extendable:
                w = (extendable & -extendable).bit_length() - 1
                clique_mask |= 1 << w
                extendable &= nbr[w]
                extendable &= ~(1 << w)
            remaining &= ~clique_mask
        return cliques

    best_size = 0
    best_set = 0

    def branch(candidates: int, current_set: int, current_size: int):
        nonlocal best_size, best_set
        if candidates == 0:
            if current_size > best_size:
                best_size = current_size
                best_set = current_set
            return
        if current_size + popcount(candidates) <= best_size:
            return
        if current_size + clique_cover_bound(candidates) <= best_size:
            return
        v = (candidates & -candidates).bit_length() - 1
        branch(candidates & ~nbr[v] & ~(1 << v), current_set | (1 << v), current_size + 1)
        branch(candidates & ~(1 << v), current_set, current_size)

    branch((1 << n) - 1, 0, 0)
    result, tmp = [], best_set
    while tmp:
        v = (tmp & -tmp).bit_length() - 1
        result.append(v)
        tmp &= tmp - 1
    return best_size, sorted(result)


def alpha_bb_clique_cover_nx(G: nx.Graph) -> tuple[int, list[int]]:
    """Convenience wrapper: accepts nx.Graph instead of np.ndarray."""
    adj = np.array(nx.to_numpy_array(G, dtype=np.uint8))
    return alpha_bb_clique_cover(adj)


# ---------------------------------------------------------------------------
# Default α — thin aliases
# ---------------------------------------------------------------------------
#
# `alpha` / `alpha_nx` are the project default. They resolve to
# `alpha_bb_clique_cover`, which beats every other exact solver we ship on
# sparse K4-free graphs (the workload here) and is competitive elsewhere —
# see docs/ALPHA_SOLVERS.md. Use the named variants (`alpha_exact`,
# `alpha_cpsat`, `alpha_maxsat`, `alpha_approx`, …) only when a caller has
# a specific reason to pick a different method.

alpha = alpha_bb_clique_cover
alpha_nx = alpha_bb_clique_cover_nx


# ---------------------------------------------------------------------------
# Numba-jitted B&B
# ---------------------------------------------------------------------------

_numba_alpha_impl = None  # lazy cache


def _get_numba_alpha():
    """Build and cache the jitted kernel on first call; import is lazy."""
    global _numba_alpha_impl
    if _numba_alpha_impl is not None:
        return _numba_alpha_impl

    import numba
    from numba import njit, types
    from numba.typed import List as NumbaList

    @njit(cache=True)
    def _popcount64(x):
        x = x - ((x >> 1) & 0x5555555555555555)
        x = (x & 0x3333333333333333) + ((x >> 2) & 0x3333333333333333)
        x = (x + (x >> 4)) & 0x0F0F0F0F0F0F0F0F
        return (x * 0x0101010101010101) >> 56

    @njit(cache=True)
    def _popcount_many(words):
        s = 0
        for w in words:
            s += _popcount64(np.uint64(w))
        return s

    @njit(cache=True)
    def _low_bit_index(words):
        # return index of lowest set bit across the word array, or -1
        for i in range(words.shape[0]):
            w = words[i]
            if w != 0:
                # position within word
                v = np.int64(w & -w)
                # bit_length via shifts
                pos = 0
                vv = v
                while vv > 1:
                    vv >>= 1
                    pos += 1
                return i * 64 + pos
        return -1

    @njit(cache=True)
    def _clear_bit(words, bit):
        i = bit // 64
        j = bit % 64
        words[i] &= ~(np.int64(1) << j)

    @njit(cache=True)
    def _set_bit(words, bit):
        i = bit // 64
        j = bit % 64
        words[i] |= (np.int64(1) << j)

    @njit(cache=True)
    def _has_bit(words, bit):
        i = bit // 64
        j = bit % 64
        return (words[i] >> j) & 1

    @njit(cache=True)
    def _and_not_into(dst, src_and, src_not):
        for i in range(dst.shape[0]):
            dst[i] = src_and[i] & ~src_not[i]

    @njit(cache=True)
    def _copy_into(dst, src):
        for i in range(dst.shape[0]):
            dst[i] = src[i]

    @njit(cache=True)
    def _alpha_numba_kernel(nbr_flat, n, W):
        """
        nbr_flat: (n * W) int64 array holding neighbour bitmask of each vertex.
        W = ceil(n / 64).
        """
        # Initial candidate mask: all n bits set
        cand = np.zeros(W, dtype=np.int64)
        for b in range(n):
            _set_bit(cand, b)

        best_size = np.int64(0)
        best_set = np.zeros(W, dtype=np.int64)

        # Work stack — avoid recursion in njit land.
        # Each frame: (cand_copy, cur_set_copy, cur_size, phase)
        # phase 0 = about to pick vertex; phase 1 = include branch done, do exclude branch.
        # Preallocate stacks big enough: depth ≤ n.
        stack_cand = np.zeros((n + 1, W), dtype=np.int64)
        stack_cur = np.zeros((n + 1, W), dtype=np.int64)
        stack_size = np.zeros(n + 1, dtype=np.int64)
        stack_phase = np.zeros(n + 1, dtype=np.int64)
        stack_v = np.zeros(n + 1, dtype=np.int64)

        depth = 0
        _copy_into(stack_cand[0], cand)
        # stack_cur[0] already zero, stack_size[0] = 0, stack_phase[0] = 0

        while depth >= 0:
            if stack_phase[depth] == 0:
                cand = stack_cand[depth]
                cur_size = stack_size[depth]
                # popcount of cand
                pc = 0
                for i in range(W):
                    pc += _popcount64(np.uint64(cand[i]))
                if cur_size + pc <= best_size:
                    depth -= 1
                    continue
                # check empty
                empty = True
                for i in range(W):
                    if cand[i] != 0:
                        empty = False
                        break
                if empty:
                    if cur_size > best_size:
                        best_size = cur_size
                        _copy_into(best_set, stack_cur[depth])
                    depth -= 1
                    continue
                v = _low_bit_index(cand)
                stack_v[depth] = v
                stack_phase[depth] = 1
                # Push include-branch frame
                new_cand = stack_cand[depth + 1]
                new_cur = stack_cur[depth + 1]
                # new_cand = cand & ~nbr[v] & ~{v}
                for i in range(W):
                    new_cand[i] = cand[i] & ~nbr_flat[v * W + i]
                _clear_bit(new_cand, v)
                _copy_into(new_cur, stack_cur[depth])
                _set_bit(new_cur, v)
                stack_size[depth + 1] = cur_size + 1
                stack_phase[depth + 1] = 0
                depth += 1
            else:
                # Exclude-branch: reuse current frame's cand with v cleared
                v = stack_v[depth]
                _clear_bit(stack_cand[depth], v)
                stack_phase[depth] = 0

        return best_size, best_set

    def alpha_numba(adj: np.ndarray) -> tuple[int, list[int]]:
        n = int(adj.shape[0])
        if n == 0:
            return 0, []
        W = (n + 63) // 64
        nbr_flat = np.zeros(n * W, dtype=np.int64)
        for i in range(n):
            row = adj[i]
            for j in range(n):
                if row[j]:
                    word = j // 64
                    bit = j % 64
                    nbr_flat[i * W + word] |= np.int64(1) << bit
        best_size, best_words = _alpha_numba_kernel(nbr_flat, n, W)
        indep = []
        for b in range(n):
            word = b // 64
            bit = b % 64
            if (best_words[word] >> bit) & 1:
                indep.append(b)
        return int(best_size), indep

    _numba_alpha_impl = alpha_numba
    return alpha_numba


def alpha_bb_numba(adj: np.ndarray) -> tuple[int, list[int]]:
    """
    Exact α via a Numba-jitted bitmask B&B.

    Same algorithm as `alpha_exact` but with native-speed 64-bit word
    operations. First call pays the JIT-compile cost (~1–3 s); subsequent
    calls use the cached kernel. Memory is O(n·W) for neighbour masks
    plus O(n·W) for the iterative stack, where W = ceil(n / 64). At
    n=300 that's ~60 KB — orders of magnitude less than CP-SAT.
    """
    impl = _get_numba_alpha()
    return impl(adj)


# ---------------------------------------------------------------------------
# MaxSAT via python-sat RC2
# ---------------------------------------------------------------------------

def alpha_maxsat(
    adj: np.ndarray,
    time_limit: float | None = None,
) -> tuple[int, list[int]]:
    """
    Exact α via MaxSAT (RC2) over a cardinality-maximising encoding.

    For each vertex i a soft unit clause [x_i] with weight 1; for each
    edge (i, j) a hard clause [¬x_i ∨ ¬x_j]. Maximising satisfied softs
    = maximising the independent set.

    `time_limit` is advisory — RC2 doesn't expose a hard wallclock, so
    this implementation lets the solver run to completion. Returns
    (0, []) if the solver raises or yields no model.
    """
    from pysat.examples.rc2 import RC2
    from pysat.formula import WCNF

    n = adj.shape[0]
    wcnf = WCNF()
    for i in range(n):
        wcnf.append([i + 1], weight=1)  # soft: prefer including vertex
    for i in range(n):
        for j in range(i + 1, n):
            if adj[i, j]:
                wcnf.append([-(i + 1), -(j + 1)])  # hard

    try:
        with RC2(wcnf) as solver:
            model = solver.compute()
    except Exception:
        return 0, []
    if model is None:
        return 0, []
    indep = [v - 1 for v in model if 0 < v <= n]
    return len(indep), sorted(indep)


def alpha_maxsat_nx(G: nx.Graph, time_limit: float | None = None) -> tuple[int, list[int]]:
    """Convenience wrapper: accepts nx.Graph instead of np.ndarray."""
    adj = np.array(nx.to_numpy_array(G, dtype=np.uint8))
    return alpha_maxsat(adj, time_limit=time_limit)


# ---------------------------------------------------------------------------
# Max clique on the complement (Bron–Kerbosch with pivot)
# ---------------------------------------------------------------------------

def alpha_clique_complement(adj: np.ndarray) -> tuple[int, list[int]]:
    """
    Exact α via max clique on the graph complement using Bron–Kerbosch
    with Tomita pivoting. On dense-complement (i.e. sparse-original)
    K4-free graphs α is large, so the complement is nearly complete and
    BK can be slow — use as a benchmark comparison, not a production path.
    """
    n = adj.shape[0]
    comp_nbr = [0] * n
    for i in range(n):
        mask = 0
        for j in range(n):
            if j != i and not adj[i, j]:
                mask |= 1 << j
        comp_nbr[i] = mask

    best_size = 0
    best_set = 0

    def bk(R: int, P: int, X: int, r_size: int):
        nonlocal best_size, best_set
        if P == 0 and X == 0:
            if r_size > best_size:
                best_size = r_size
                best_set = R
            return
        # pick pivot u from P ∪ X maximising |P ∩ N(u)|
        PX = P | X
        u = -1
        best_overlap = -1
        tmp = PX
        while tmp:
            v = (tmp & -tmp).bit_length() - 1
            tmp &= tmp - 1
            overlap = bin(P & comp_nbr[v]).count("1")
            if overlap > best_overlap:
                best_overlap = overlap
                u = v
        candidates = P & ~comp_nbr[u] if u >= 0 else P
        while candidates:
            v = (candidates & -candidates).bit_length() - 1
            candidates &= candidates - 1
            Nv = comp_nbr[v]
            bk(R | (1 << v), P & Nv, X & Nv, r_size + 1)
            P &= ~(1 << v)
            X |= 1 << v

    bk(0, (1 << n) - 1, 0, 0)
    result, tmp = [], best_set
    while tmp:
        v = (tmp & -tmp).bit_length() - 1
        result.append(v)
        tmp &= tmp - 1
    return best_size, sorted(result)


# ---------------------------------------------------------------------------
# K4-free checking
# ---------------------------------------------------------------------------

def find_k4(adj: np.ndarray) -> tuple | None:
    """Return (a, b, c, d) witnessing a K4, or None if the graph is K4-free."""
    n = adj.shape[0]
    nbr = [0] * n
    for i in range(n):
        for j in range(n):
            if adj[i, j]:
                nbr[i] |= 1 << j

    for a in range(n):
        for b in range(a + 1, n):
            if not (nbr[a] >> b & 1):
                continue
            common_ab = nbr[a] & nbr[b] & ~((1 << (b + 1)) - 1)
            tmp = common_ab
            while tmp:
                c = (tmp & -tmp).bit_length() - 1
                tmp &= tmp - 1
                common_abc = common_ab & nbr[c] & ~((1 << (c + 1)) - 1)
                if common_abc:
                    d = (common_abc & -common_abc).bit_length() - 1
                    return (a, b, c, d)
    return None


def is_k4_free(adj: np.ndarray) -> bool:
    """Return True if the graph (n×n numpy adjacency matrix) contains no K4."""
    return find_k4(adj) is None


def is_k4_free_nx(G: nx.Graph) -> bool:
    """Convenience wrapper: accepts nx.Graph instead of np.ndarray."""
    adj = np.array(nx.to_numpy_array(G, dtype=np.uint8))
    return is_k4_free(adj)


# ---------------------------------------------------------------------------
# Girth
# ---------------------------------------------------------------------------

def girth(G: nx.Graph) -> int | None:
    """Shortest cycle length via BFS from each vertex. Returns None if acyclic."""
    g = float("inf")
    for v in G.nodes():
        dist = {v: 0}
        q    = deque([(v, -1)])
        while q:
            u, par = q.popleft()
            for w in G.neighbors(u):
                if w == par:
                    continue
                if w in dist:
                    g = min(g, dist[u] + dist[w] + 1)
                else:
                    dist[w] = dist[u] + 1
                    q.append((w, u))
            if g == 3:
                return 3
    return int(g) if g < float("inf") else None


# ---------------------------------------------------------------------------
# Triangle sets
# ---------------------------------------------------------------------------

def triangle_sets(G: nx.Graph) -> tuple[list, list]:
    """
    Return (triangle_edges, triangle_vertices).
    triangle_edges: sorted list of [u, v] pairs that lie in at least one triangle.
    triangle_vertices: sorted list of vertex indices that lie in at least one triangle.
    """
    adj   = {v: set(G.neighbors(v)) for v in G.nodes()}
    edges = set()
    verts = set()
    for u in G.nodes():
        for v in adj[u]:
            if v <= u:
                continue
            for w in adj[u] & adj[v]:
                if w <= v:
                    continue
                edges |= {(min(u, v), max(u, v)),
                          (min(u, w), max(u, w)),
                          (min(v, w), max(v, w))}
                verts |= {u, v, w}
    return sorted(edges), sorted(verts)


# ---------------------------------------------------------------------------
# High-degree vertices
# ---------------------------------------------------------------------------

def high_degree_verts(G: nx.Graph) -> list[int]:
    """Return sorted list of vertices with maximum degree."""
    if G.number_of_nodes() == 0:
        return []
    d_max = max(d for _, d in G.degree())
    return sorted(int(v) for v, d in G.degree() if d == d_max)


# ---------------------------------------------------------------------------
# Independence number (approximate)
# ---------------------------------------------------------------------------

def alpha_approx(adj: np.ndarray, restarts: int = 400) -> int:
    """
    Random greedy MIS approximation via repeated random-order greedy.
    Faster than alpha_exact for large n; use as a lower bound.
    """
    n = adj.shape[0]
    nbr = [0] * n
    for i in range(n):
        for j in range(n):
            if adj[i, j]:
                nbr[i] |= 1 << j
    import random
    best = 0
    verts = list(range(n))
    for _ in range(restarts):
        random.shuffle(verts)
        avail = (1 << n) - 1
        size = 0
        for v in verts:
            if avail >> v & 1:
                size += 1
                avail &= ~nbr[v] & ~(1 << v)
        if size > best:
            best = size
    return best


# ---------------------------------------------------------------------------
# Extremal metric
# ---------------------------------------------------------------------------

def c_log_value(alpha: int, n: int, d_max: int) -> float | None:
    """Compute alpha * d_max / (n * ln(d_max)). Returns None if d_max <= 1."""
    if d_max <= 1:
        return None
    return alpha * d_max / (n * log(d_max))
