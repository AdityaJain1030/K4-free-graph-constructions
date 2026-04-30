"""
utils/alpha_bounds.py
=====================
Bounds on the independence number α(G), consolidated.

Upper bounds (α ≤ B) implemented here:

    hoffman_bound(G)              — spectral; regular graphs only
    lovasz_theta(G)               — SDP; canonical Lovász θ
    schrijver_theta(G)            — Lovász θ + non-negativity (θ' ≤ θ)
    fractional_chromatic_complement(G) — LP clique cover (χ_f(Ḡ))
    greedy_clique_cover(G)        — combinatorial; thin re-export

Lower bound (α ≥ B), included for tightness benchmarking only:

    hardcore_alpha(G)             — exact global hard-core occupancy

Provenance of inequalities (any graph G, n = |V|):

    α(G) ≤ θ'(G) ≤ θ(G) ≤ χ_f(Ḡ) ≤ χ(Ḡ)
    α(G) ≤ H(G)              when G is regular   (no general comparison
                              between H and θ)
    α(G) ≤ greedy_clique_cover(G)               (any clique partition)

Every function accepts an `nx.Graph` (preferred) or an `np.ndarray`
adjacency matrix. SDP/LP routines depend on cvxpy; if cvxpy is missing
they return None rather than raising.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional, Sequence

import networkx as nx
import numpy as np

from utils.graph_props import lovasz_theta as _lovasz_theta_adj
from utils.alpha_surrogate import alpha_ub as _greedy_clique_cover_adj


# ---------------------------------------------------------------------------
# Adapters
# ---------------------------------------------------------------------------

def _as_adj(G) -> np.ndarray:
    if isinstance(G, np.ndarray):
        return G.astype(np.uint8, copy=False)
    return np.asarray(nx.to_numpy_array(G, dtype=np.uint8))


def _as_graph(G) -> nx.Graph:
    if isinstance(G, nx.Graph) and not G.is_directed():
        return G
    if isinstance(G, nx.Graph) and G.is_directed():
        return nx.Graph(G)
    return nx.from_numpy_array(np.asarray(G))


# ---------------------------------------------------------------------------
# 1. Hoffman ratio bound  (spectral)
# ---------------------------------------------------------------------------

def hoffman_bound(G, *, force_d_avg: bool = False) -> Optional[float]:
    """
    Hoffman ratio bound  H(G) = n · (-λ_min) / (d − λ_min).

    Valid for d-regular G. For non-regular G the inequality α ≤ H is
    *not* guaranteed by Hoffman's argument; we return None unless
    `force_d_avg=True`, in which case we substitute d_avg (a heuristic
    used elsewhere in this repo's exploratory scripts — sometimes
    loose, sometimes incorrect; never trust it as a certificate).

    For a connected non-empty regular graph, λ_min < d, so the
    denominator is strictly positive. A non-positive denominator
    therefore signals either a disconnected graph (where the
    per-component bound is the right object) or numerical garbage.
    We raise rather than silently returning None.
    """
    A = _as_adj(G).astype(float)
    n = A.shape[0]
    if n == 0:
        return 0.0
    deg = A.sum(axis=1)
    is_regular = bool(np.all(deg == deg[0]))
    if not is_regular and not force_d_avg:
        return None
    d = float(deg[0]) if is_regular else float(deg.mean())
    eigs = np.linalg.eigvalsh(A)
    lam_min = float(eigs[0])
    denom = d - lam_min
    if denom <= 0:
        raise ValueError(
            f"Hoffman: d − λ_min = {denom:.4g} ≤ 0 (d={d}, λ_min={lam_min}). "
            "This indicates a disconnected, edgeless, or numerically "
            "degenerate graph — call hoffman_bound on each component."
        )
    return float(n * (-lam_min) / denom)


# ---------------------------------------------------------------------------
# 2. Lovász θ  (SDP)  — re-export with both adj/Graph signatures
# ---------------------------------------------------------------------------

def lovasz_theta(G, solver: str = "SCS") -> Optional[float]:
    """
    Lovász ϑ(G) via   max ⟨J, X⟩  s.t.  X ⪰ 0, tr X = 1, X_ij = 0 for ij ∈ E.
    Always satisfies α(G) ≤ ϑ(G).

    Thin wrapper around utils.graph_props.lovasz_theta so we have a
    single canonical entry point. Returns None if cvxpy is missing.
    """
    A = _as_adj(G)
    return _lovasz_theta_adj(A, solver=solver)


# ---------------------------------------------------------------------------
# 3. Schrijver θ'  (SDP with non-negativity)
# ---------------------------------------------------------------------------

def schrijver_theta(G, solver: str = "SCS") -> Optional[float]:
    """
    Schrijver's ϑ'(G):  max ⟨J, X⟩  s.t.  X ⪰ 0, tr X = 1,
                                          X_ij = 0 for ij ∈ E,
                                          X_ij ≥ 0 for all i,j.

    Refines Lovász θ by forbidding the negative entries that ϑ may use.
    Always satisfies α(G) ≤ ϑ'(G) ≤ ϑ(G). Tightening is non-trivial on
    graphs that are not vertex-transitive; on Cayley/SRG graphs the
    symmetry typically forces ϑ' = ϑ.
    """
    try:
        import cvxpy as cp
    except ImportError:
        return None
    A = _as_adj(G)
    n = A.shape[0]
    if n == 0:
        return 0.0
    if n == 1:
        return 1.0
    X = cp.Variable((n, n), symmetric=True)
    cons = [X >> 0, cp.trace(X) == 1, X >= 0]
    iu, ju = np.where(np.triu(A, 1) > 0)
    for i, j in zip(iu, ju):
        cons.append(X[i, j] == 0)
    prob = cp.Problem(cp.Maximize(cp.sum(X)), cons)
    prob.solve(solver=solver, verbose=False)
    return float(prob.value) if prob.value is not None else None


# ---------------------------------------------------------------------------
# 4. Fractional chromatic of the complement   χ_f(Ḡ)  ≥ α(G)
# ---------------------------------------------------------------------------

def fractional_chromatic_complement(
    G,
    *,
    solver: str = "SCS",
    max_cliques: int = 200_000,
) -> Optional[float]:
    """
    Fractional clique cover number of G  =  χ_f(Ḡ),
    the fractional chromatic number of the complement, satisfying

        α(G)  ≤  χ_f(Ḡ)  ≤  χ(Ḡ).

    Two equivalent readings:

      • Cover the vertices of G fractionally by cliques of G; minimise
        total weight. Each clique C of G is an independent set in Ḡ,
        i.e. a colour class.
      • Equivalently, fractionally colour Ḡ with the same colour classes.

    LP formulation:

        min  Σ_C x_C        s.t.   x ≥ 0,
                                    Σ_{C ∋ v} x_C ≥ 1  for every v ∈ V,

    where C ranges over the cliques of G. The optimum is attained on
    maximal cliques, which we enumerate via networkx.

    Returns None if more than `max_cliques` are required (clique count
    can be combinatorially explosive on dense G). For the K4-free
    frontier this is manageable up to N ≈ 100; on dense graphs use the
    LP dual (column generation) instead.
    """
    try:
        import cvxpy as cp
    except ImportError:
        return None
    H = _as_graph(G)
    n = H.number_of_nodes()
    if n == 0:
        return 0.0
    nodes = list(H.nodes())
    idx = {v: i for i, v in enumerate(nodes)}

    sets: list[list[int]] = []
    for clique in nx.find_cliques(H):
        sets.append([idx[v] for v in clique])
        if len(sets) > max_cliques:
            return None
    if not sets:
        return None

    M = np.zeros((n, len(sets)), dtype=np.float64)
    for j, S in enumerate(sets):
        for i in S:
            M[i, j] = 1.0
    x = cp.Variable(len(sets), nonneg=True)
    prob = cp.Problem(cp.Minimize(cp.sum(x)), [M @ x >= 1])
    prob.solve(solver=solver, verbose=False)
    return float(prob.value) if prob.value is not None else None


# ---------------------------------------------------------------------------
# 5. Greedy clique cover (combinatorial, cheap)
# ---------------------------------------------------------------------------

def greedy_clique_cover(G, *, rng: np.random.Generator | None = None) -> int:
    """
    Single-pass greedy clique partition. Returns an integer ≥ α(G).
    Cheaper than B&B; loose but always finite. Re-exported from
    utils.alpha_surrogate.alpha_ub for convenience.
    """
    return int(_greedy_clique_cover_adj(_as_adj(G), rng=rng))


# ---------------------------------------------------------------------------
# 6. Hard-core occupancy  (LOWER bound, included for the tightness suite)
# ---------------------------------------------------------------------------

def _independence_polynomial(H: nx.Graph) -> list[int]:
    """Z(H, λ) = Σ a_k λ^k where a_k = #{indep sets of size k}."""
    nodes = list(H.nodes())
    if not nodes:
        return [1]
    nodes.sort(key=lambda v: -H.degree(v))
    index = {v: i for i, v in enumerate(nodes)}
    nbr = [0] * len(nodes)
    for i, v in enumerate(nodes):
        m = 0
        for u in H.neighbors(v):
            m |= 1 << index[u]
        nbr[i] = m
    n = len(nodes)
    coeffs = [0] * (n + 1)
    def dfs(start: int, allowed: int, size: int):
        coeffs[size] += 1
        i = start
        while i < n:
            bit = 1 << i
            if allowed & bit:
                dfs(i + 1, allowed & ~bit & ~nbr[i], size + 1)
            i += 1
    dfs(0, (1 << n) - 1, 0)
    while len(coeffs) > 1 and coeffs[-1] == 0:
        coeffs.pop()
    return coeffs


def _poly_eval(c: Sequence[int], lam: float) -> float:
    """Direct Horner. Used only where overflow is impossible (small n)."""
    s = 0.0
    for x in reversed(c):
        s = s * lam + x
    return s


def _log_poly_eval(coeffs: Sequence[int], lam: float) -> float:
    """
    log Z(λ) where Z(λ) = Σ a_k λ^k, all a_k ≥ 0.

    Independence-polynomial coefficients can grow like 2^n and Z(λ)
    grows like λ^n, so direct evaluation overflows float64 around
    n · log10(λ) ≈ 308. We fold every term to log scale and sum via
    log-sum-exp so the result is robust for any n we will plausibly
    enumerate (capped by the 2^n cost of computing the polynomial
    itself, not by float dynamic range).

    log(Σ a_k λ^k) = max_k {log a_k + k log λ}
                     + log Σ_k exp(log a_k + k log λ − max).
    Returns -inf if the polynomial is identically zero.
    """
    if lam <= 0:
        # Z(0) = a_0 (the empty independent set count, always 1 here).
        a0 = coeffs[0] if coeffs else 0
        return math.log(a0) if a0 > 0 else -math.inf
    log_lam = math.log(lam)
    log_terms: list[float] = []
    for k, a in enumerate(coeffs):
        if a > 0:
            # math.log accepts arbitrary-precision ints; converts via
            # the int's bit length, so no overflow up to truly huge a_k.
            log_terms.append(math.log(a) + k * log_lam)
    if not log_terms:
        return -math.inf
    m = max(log_terms)
    return m + math.log(sum(math.exp(t - m) for t in log_terms))


@dataclass(frozen=True)
class HardcoreResult:
    e_max: float
    lam_star: float


def hardcore_local(
    G,
    *,
    lam_min: float = 0.05,
    lam_max: float = 200.0,
    lam_steps: int = 400,
) -> Optional[HardcoreResult]:
    """
    Local hard-core lower bound on α.

    Replaces the *global* marginal ρ_v(G,λ) = λ Z(G−N[v],λ) / Z(G,λ) with
    a *local* lower bound that depends only on the open-neighbourhood
    subgraph T_v = G[N(v)]:

        ρ_v(G,λ)  ≥  λ / (λ + Z(T_v, λ)),

    derived from the partition inequality
    Z(G,λ) ≤ Z(G[N[v]],λ) · Z(G − N[v],λ) and Z(G[N[v]],λ) = λ + Z(T_v,λ).
    Summing over v:

        α(G)  ≥  L_HC(G)  =  max_λ Σ_v  λ / (λ + Z(T_v,λ)).

    Always satisfies α(G) ≥ E_max(G) ≥ L_HC(G); equality with E_max
    requires the partition inequality to be tight at every vertex,
    which empirically is not the case.

    Cost: O(n · 2^{d_max}) per graph — only depends on the *neighbourhood*
    sizes, so this scales to graphs of arbitrary n provided the maximum
    degree stays moderate (vs hardcore_alpha which is O(n · 2^n)).
    """
    H = _as_graph(G)
    n = H.number_of_nodes()
    if n == 0:
        return HardcoreResult(0.0, 0.0)
    lam_grid = np.geomspace(lam_min, lam_max, lam_steps)
    log_lam = np.log(lam_grid)
    E_vals = np.zeros_like(lam_grid)
    for v in H.nodes():
        Tv = H.subgraph(list(H.neighbors(v))).copy()
        Z_Tv = _independence_polynomial(Tv)
        log_Z_Tv = np.array([_log_poly_eval(Z_Tv, lam) for lam in lam_grid])
        # ρ_v ≥ λ / (λ + Z(T_v, λ));   log(λ + Z) = logaddexp(log λ, log Z)
        log_denom = np.logaddexp(log_lam, log_Z_Tv)
        E_vals += np.exp(log_lam - log_denom)
    j = int(np.argmax(E_vals))
    return HardcoreResult(float(E_vals[j]), float(lam_grid[j]))


def hardcore_alpha(
    G,
    *,
    lam_min: float = 0.05,
    lam_max: float = 200.0,
    lam_steps: int = 400,
) -> Optional[HardcoreResult]:
    """
    Exact global hard-core occupancy lower bound on α.

    For each vertex v, the marginal of the hard-core measure at fugacity
    λ is  ρ_v(λ) = λ · Z(G − N[v], λ) / Z(G, λ).  Since the expected
    independent-set size cannot exceed the maximum,

        α(G)  ≥  E_μ[|I|](λ)  =  Σ_v ρ_v(λ)        for every λ > 0,

    so taking the max over a geometric λ grid gives the tightest
    bound this single-fugacity method offers; the limit λ → ∞ recovers
    α exactly.

    Numerics: ρ_v is evaluated as exp(log Z(G−N[v]) + log λ − log Z(G))
    via log-sum-exp, so the n ≈ 20 → 2^n overflow regime that direct
    Horner evaluation would hit is no longer a problem. The cost
    ceiling is the polynomial enumeration itself, not float range —
    O(n · 2^n) per graph, in practice n ≤ ~22 is comfortable.
    """
    H = _as_graph(G)
    n = H.number_of_nodes()
    if n == 0:
        return HardcoreResult(0.0, 0.0)
    lam_grid = np.geomspace(lam_min, lam_max, lam_steps)
    log_lam = np.log(lam_grid)
    Z_G = _independence_polynomial(H)
    log_Z_G = np.array([_log_poly_eval(Z_G, lam) for lam in lam_grid])
    E_vals = np.zeros_like(lam_grid)
    for v in H.nodes():
        Hv = H.copy()
        Hv.remove_nodes_from({v, *H.neighbors(v)})
        Z_v = _independence_polynomial(Hv)
        log_Z_v = np.array([_log_poly_eval(Z_v, lam) for lam in lam_grid])
        # ρ_v(λ) = exp(log Z_v + log λ − log Z_G); always in [0, 1).
        E_vals += np.exp(log_Z_v + log_lam - log_Z_G)
    j = int(np.argmax(E_vals))
    return HardcoreResult(float(E_vals[j]), float(lam_grid[j]))


# ---------------------------------------------------------------------------
# Bundle
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class AlphaBoundReport:
    n: int
    alpha: Optional[int]
    hoffman: Optional[float]
    lovasz_theta: Optional[float]
    schrijver_theta: Optional[float]
    chi_f_complement: Optional[float]
    greedy_clique_cover: Optional[int]
    hardcore_e_max: Optional[float]


def all_alpha_bounds(G, alpha: Optional[int] = None) -> AlphaBoundReport:
    """Run every bound in this module on G. Skipped components return None."""
    H = _as_graph(G)
    n = H.number_of_nodes()
    return AlphaBoundReport(
        n=n,
        alpha=alpha,
        hoffman=hoffman_bound(H),
        lovasz_theta=lovasz_theta(H),
        schrijver_theta=schrijver_theta(H),
        chi_f_complement=fractional_chromatic_complement(H),
        greedy_clique_cover=greedy_clique_cover(H),
        hardcore_e_max=hardcore_alpha(H).e_max if n <= 22 else None,
    )
