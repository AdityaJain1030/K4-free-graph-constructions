"""
search/switch_tabu.py
======================
Tabu search on the edge space of K4-free graphs.

Move-set reference (do not confuse these three — they have different
preservation properties and different roles in the search)
------------------------------------------------------------------

    | move              | ΔE  | degree change           | multiset k |
    |-------------------|-----|--------------------------|------------|
    | 2-switch          |  0  | all four vertices fixed | invariant  |
    | edge-endpoint move|  0  | v: −1, w: +1            | ±0 or ±2   |
    | edge-bitvec flip  | ±1  | both endpoints ±1       | ±0 or ±2   |

* 2-switch: remove (a,b),(c,d); add (a,c),(b,d). Keeps the whole
  degree sequence exactly. Partitions the state space by degree
  multiset → each multiset is a separate search problem.
* edge-endpoint (see utils/edge_switch.random_walk_move): remove uv,
  add uw. Keeps edge count constant; changes which vertex is
  low-degree within the same edge count.
* edge-bitvec flip: toggle one edge on/off. **Only move that changes
  edge count**, so it's the one that crosses multiset classes at
  fixed n when the two frontiers differ in edge count (N=23: k=0→k=2
  means m=46→m=45, one deletion).

Chain variants
--------------
* `switch_tabu_chain` — pure 2-switch, within-multiset plateau search.
* `switch_tabu_chain_mixed` — 2-switch + edge-bitvec-flip, gated by a
  post-move spread cap. The operator that can actually cross multisets.

Design decisions
----------------
* Memory: a deque of recently-touched canonical edge ids. O(1)
  membership, no state hashing.
* Aspiration: a tabu move is accepted if it strictly improves the
  incumbent's c_log.
* Restart: on stagnation, perturb `best` by `perturb_swaps` random
  moves (iterated local search). Random re-init destroys the
  proximity-to-frontier earned earlier.
* Cost: predict-and-verify. alpha_lb ranks a pool cheaply; alpha_bb
  exact rescores the top-K to pick the accepted move.
* Ranking is by c_log (not α). Under 2-switch α-rank and c_log-rank
  coincide (d_max invariant), but under edge-bitvec-flip d_max can
  change, so α-rank would misprice moves that trade α for d_max.
* k-trajectory instrumentation: every accepted move logs the number
  of min-degree vertices in the resulting graph. This tells you
  whether a mixed-operator chain is *using* its k-crossing capability
  or just sitting in one multiset.
"""

from __future__ import annotations

import os
import sys
import time
from dataclasses import dataclass, field
from math import log
from collections import deque
from typing import Iterable

import numpy as np
import networkx as nx

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.graph_props import (
    alpha_bb_clique_cover,
    is_k4_free,
    find_k4,
    c_log_value,
)
from utils.alpha_surrogate import alpha_lb

from .base import Search


# ---------------------------------------------------------------------------
# Edge-id helpers
# ---------------------------------------------------------------------------

def _edge_id(u: int, v: int, n: int) -> int:
    """Canonical undirected edge id in [0, n*n). Use min-first ordering."""
    if u > v:
        u, v = v, u
    return u * n + v


def _edges_of(adj: np.ndarray) -> list[tuple[int, int]]:
    n = adj.shape[0]
    return [(i, j) for i in range(n) for j in range(i + 1, n) if adj[i, j]]


# ---------------------------------------------------------------------------
# One candidate 2-switch
# ---------------------------------------------------------------------------

@dataclass
class SwitchCandidate:
    new_adj: np.ndarray
    touched_ids: tuple[int, ...]  # length 4 for 2-switch, length 1 for flip
    is_tabu: bool
    move_kind: str = "swap"  # "swap" or "flip"
    surrogate_alpha: int = -1
    exact_alpha: int = -1
    c_log: float = float("inf")
    lookahead_c_log: float = float("inf")  # min c_log seen during rollouts; only set when lookahead_top_k>0


def _try_switch(
    adj: np.ndarray,
    a: int, b: int, c: int, d: int,
) -> np.ndarray | None:
    """
    Try swap (a,b),(c,d) → (a,c),(b,d). Returns the new adj if legal
    (all four distinct, new edges not already present, K4-free), else
    None. Does not mutate `adj`.

    Note on K4 check: we check on the graph with (a,b) already removed,
    because a K4 on {a,b,c,d} itself requires (a,b) present. Using
    find_k4 on the full new adj handles this correctly — the K4 check
    sees the final state.
    """
    if a == c or a == d or b == c or b == d:
        return None
    if adj[a, c] or adj[b, d]:
        return None
    new = adj.copy()
    new[a, b] = new[b, a] = 0
    new[c, d] = new[d, c] = 0
    new[a, c] = new[c, a] = 1
    new[b, d] = new[d, b] = 1
    if find_k4(new) is not None:
        return None
    return new


def _sample_candidates(
    adj: np.ndarray,
    *,
    target_pool: int,
    max_attempts: int,
    rng: np.random.Generator,
    tabu: Iterable[int],
) -> list[SwitchCandidate]:
    """
    Sample 2-switches, return the ones that pass legality + K4-freeness.
    Keep hunting until we either collect `target_pool` candidates or
    run out of `max_attempts`.

    Pre-filter on cheap legality (distinct endpoints, proposed new
    edges not already present) before running the K4 check, since at
    K4-saturated densities most random pairs fail those cheap tests.
    """
    n = adj.shape[0]
    tabu_set = set(tabu)
    edges = _edges_of(adj)
    m = len(edges)
    if m < 2:
        return []

    out: list[SwitchCandidate] = []
    attempts = 0
    while len(out) < target_pool and attempts < max_attempts:
        attempts += 1
        i = int(rng.integers(0, m))
        j = int(rng.integers(0, m))
        if i == j:
            continue
        a, b = edges[i]
        c, d = edges[j]
        if rng.random() < 0.5:
            a, b = b, a
        if rng.random() < 0.5:
            c, d = d, c

        # Cheap pre-filters before the O(n³) K4 test.
        if a == c or a == d or b == c or b == d:
            continue
        if adj[a, c] or adj[b, d]:
            continue

        new = _try_switch(adj, a, b, c, d)  # includes find_k4 on result
        if new is None:
            continue

        touched = (
            _edge_id(a, b, n),
            _edge_id(c, d, n),
            _edge_id(a, c, n),
            _edge_id(b, d, n),
        )
        is_tabu = any(t in tabu_set for t in touched)
        out.append(SwitchCandidate(
            new_adj=new,
            touched_ids=touched,
            is_tabu=is_tabu,
            move_kind="swap",
        ))
    return out


# ---------------------------------------------------------------------------
# 3-switch candidates — vertex-disjoint 3-edge rotation
# ---------------------------------------------------------------------------
#
# A "3-switch" picks 3 vertex-disjoint edges {(a,b),(c,d),(e,f)} (six
# distinct vertices) and replaces them with a different perfect
# matching of those six vertices. There are 15 perfect matchings of 6
# labelled vertices into 3 pairs; excluding the original, 14 are
# distinct 3-switch results.
#
# Composition-redundancy classification:
#   * 1-step-equivalent: the new pairing keeps exactly one of the
#     original edges (e.g. preserves (a,b), rematches {c,d,e,f}). Any
#     such 3-switch is also a 2-switch on (c,d),(e,f) — so it adds no
#     reach beyond the 2-switch chain. There are 3 × 2 = 6 of these
#     among the 14 pairings (pick which original edge survives, then
#     1 of 2 non-original rematches of the remaining 4 vertices).
#   * Novel: the new pairing keeps 0 of the original edges. There are
#     14 - 6 = 8 such pairings. These are the ones that genuinely
#     expand the reachable set beyond 2-switch composition (modulo
#     possible 2-step-2-switch reachability, which we don't measure
#     here — see the redundancy diagnostic in the chain).
#
# `move_kind = "swap3"` for novel, `"swap3_equiv"` for 1-step-equiv.
# This is what shows up in `move_kind_counts`.

def _try_3switch_from_pairing(
    adj: np.ndarray,
    e1: tuple[int, int],
    e2: tuple[int, int],
    e3: tuple[int, int],
    pairing: list[tuple[int, int]],
) -> tuple[np.ndarray | None, bool]:
    """
    Apply a 3-switch on 3 vertex-disjoint edges. Returns (new_adj, is_novel).
    new_adj is None on failure (pairing == original, edge collision, K4).
    `is_novel` reflects classification of the *requested* pairing
    independent of legality, so the caller can attribute attempts.
    """
    a, b = e1
    c, d = e2
    e, f = e3
    if len({a, b, c, d, e, f}) != 6:
        return None, False
    orig_set = frozenset({frozenset(e1), frozenset(e2), frozenset(e3)})
    new_set = frozenset({frozenset(p) for p in pairing})
    if new_set == orig_set:
        return None, False
    n_orig_preserved = sum(1 for p in pairing if frozenset(p) in orig_set)
    is_novel = (n_orig_preserved == 0)

    # Edge-collision check: a "new edge" is only a real addition if it's
    # not one of the three originals. Originals that survive in the new
    # pairing are unchanged, not added — checking adj[u,v] on them
    # would always reject (correctly nonzero) and incorrectly mark the
    # 1-step-equivalent pairing infeasible.
    for u, v in pairing:
        if frozenset((u, v)) in orig_set:
            continue
        if adj[u, v]:
            return None, is_novel

    new = adj.copy()
    new[a, b] = new[b, a] = 0
    new[c, d] = new[d, c] = 0
    new[e, f] = new[f, e] = 0
    for u, v in pairing:
        new[u, v] = new[v, u] = 1
    if find_k4(new) is not None:
        return None, is_novel
    return new, is_novel


def _sample_3switch_candidates(
    adj: np.ndarray,
    *,
    target_pool: int,
    max_attempts: int,
    rng: np.random.Generator,
    tabu: Iterable[int],
    novel_only: bool = False,
) -> tuple[list[SwitchCandidate], dict[str, int]]:
    """
    Sample 3-switches. Returns (candidates, stats) where stats counts
    the *requested* (sampled-pairing) novelty distribution and the
    failure mode. Use stats to instrument symmetry/redundancy.

    `novel_only=True` rejects 1-step-equivalent pairings at sample
    time. Useful as an ablation: "what if we only let the chain
    consider truly-novel 3-switches?"

    Each successful candidate emits 6 touched edge ids (3 removed +
    3 added). Callers that pass these into a fixed-length tabu deque
    should scale the deque by ~1.5× compared to the 2-switch chain to
    preserve average edge-tabu memory.
    """
    n = adj.shape[0]
    tabu_set = set(tabu)
    edges = _edges_of(adj)
    m = len(edges)
    if m < 3:
        return [], {
            "n_attempts": 0,
            "n_novel_attempts": 0, "n_equiv_attempts": 0,
            "n_novel_accepted": 0, "n_equiv_accepted": 0,
            "n_disjoint_fail": 0,
        }

    out: list[SwitchCandidate] = []
    n_attempts = 0
    n_novel_attempts = 0
    n_equiv_attempts = 0
    n_novel_accepted = 0
    n_equiv_accepted = 0
    n_disjoint_fail = 0

    while len(out) < target_pool and n_attempts < max_attempts:
        n_attempts += 1
        i = int(rng.integers(0, m))
        j = int(rng.integers(0, m))
        kk = int(rng.integers(0, m))
        if i == j or i == kk or j == kk:
            continue
        e1 = edges[i]
        e2 = edges[j]
        e3 = edges[kk]
        verts = [e1[0], e1[1], e2[0], e2[1], e3[0], e3[1]]
        if len(set(verts)) != 6:
            n_disjoint_fail += 1
            continue

        # Pick a random non-trivial pairing of the 6 vertices.
        # Shuffling and pairing consecutively gives a uniform draw
        # over 15 pairings (each appearing with the same orbit size).
        perm = rng.permutation(verts)
        pairing = [
            (int(perm[0]), int(perm[1])),
            (int(perm[2]), int(perm[3])),
            (int(perm[4]), int(perm[5])),
        ]
        new, is_novel = _try_3switch_from_pairing(adj, e1, e2, e3, pairing)
        if is_novel:
            n_novel_attempts += 1
        else:
            n_equiv_attempts += 1
        if novel_only and not is_novel:
            continue
        if new is None:
            continue

        touched = (
            _edge_id(e1[0], e1[1], n),
            _edge_id(e2[0], e2[1], n),
            _edge_id(e3[0], e3[1], n),
            _edge_id(pairing[0][0], pairing[0][1], n),
            _edge_id(pairing[1][0], pairing[1][1], n),
            _edge_id(pairing[2][0], pairing[2][1], n),
        )
        is_tabu = any(t in tabu_set for t in touched)
        out.append(SwitchCandidate(
            new_adj=new,
            touched_ids=touched,
            is_tabu=is_tabu,
            move_kind="swap3" if is_novel else "swap3_equiv",
        ))
        if is_novel:
            n_novel_accepted += 1
        else:
            n_equiv_accepted += 1

    stats = {
        "n_attempts": n_attempts,
        "n_novel_attempts": n_novel_attempts,
        "n_equiv_attempts": n_equiv_attempts,
        "n_novel_accepted": n_novel_accepted,
        "n_equiv_accepted": n_equiv_accepted,
        "n_disjoint_fail": n_disjoint_fail,
    }
    return out, stats


def _try_3switch_random(
    adj: np.ndarray,
    rng: np.random.Generator,
    *,
    max_attempts: int = 60,
) -> np.ndarray | None:
    """
    Sample one legal 3-switch (any pairing — novel or equivalent).
    Used inside random rollouts. Returns None on failure.
    """
    n = adj.shape[0]
    edges = _edges_of(adj)
    m = len(edges)
    if m < 3:
        return None
    for _ in range(max_attempts):
        i = int(rng.integers(0, m))
        j = int(rng.integers(0, m))
        kk = int(rng.integers(0, m))
        if i == j or i == kk or j == kk:
            continue
        e1 = edges[i]
        e2 = edges[j]
        e3 = edges[kk]
        verts = [e1[0], e1[1], e2[0], e2[1], e3[0], e3[1]]
        if len(set(verts)) != 6:
            continue
        perm = rng.permutation(verts)
        pairing = [
            (int(perm[0]), int(perm[1])),
            (int(perm[2]), int(perm[3])),
            (int(perm[4]), int(perm[5])),
        ]
        new, _ = _try_3switch_from_pairing(adj, e1, e2, e3, pairing)
        if new is not None:
            return new
    return None


# ---------------------------------------------------------------------------
# One-run tabu chain
# ---------------------------------------------------------------------------

@dataclass
class SwitchTabuResult:
    best_adj: np.ndarray
    best_alpha: int
    best_c_log: float
    best_iter: int
    n_iters: int
    n_accepted: int
    n_aspiration: int
    n_restarts: int
    trajectory: list[float]  # c_log of current state (not best) each iter
    # instrumentation (post-accepted-move)
    k_trajectory: list[int] = field(default_factory=list)  # #min-degree verts
    m_trajectory: list[int] = field(default_factory=list)  # edge count
    move_kind_counts: dict[str, int] = field(default_factory=dict)
    pool_sizes: list[int] = field(default_factory=list)  # feasible swap count per iter
    alpha_first_reached: dict[int, int] = field(default_factory=dict)  # α → first iter
    # lookahead instrumentation (mixed chain only; zero when disabled)
    n_lookahead_iters: int = 0      # iters that ran lookahead (had >=1 non-tabu cand)
    n_lookahead_disagree: int = 0   # iters where lookahead changed the pick
    n_lookahead_evals: int = 0      # total lookahead score evaluations
    lookahead_min_c_log: float = float("inf")  # best c_log probed during rollouts
    # 3-switch instrumentation (mixed chain only; zero when disabled)
    swap3_stats: dict[str, int] = field(default_factory=dict)   # cumulative sampler stats across iters
    swap3_accepted_novel: int = 0   # accepted moves of move_kind="swap3"
    swap3_accepted_equiv: int = 0   # accepted moves of move_kind="swap3_equiv"


def _multiset_k(adj: np.ndarray) -> int:
    """Number of vertices at the minimum degree. Proxy for 'which multiset'."""
    degs = adj.sum(axis=1)
    return int((degs == degs.min()).sum())


def _perturb(
    adj: np.ndarray,
    n_swaps: int,
    rng: np.random.Generator,
    max_attempts_per_swap: int = 20,
) -> np.ndarray:
    """Apply up to n_swaps random legal 2-switches. Skip on failure."""
    cur = adj.copy()
    for _ in range(n_swaps):
        for _ in range(max_attempts_per_swap):
            edges = _edges_of(cur)
            if len(edges) < 2:
                return cur
            i = int(rng.integers(0, len(edges)))
            j = int(rng.integers(0, len(edges)))
            if i == j:
                continue
            a, b = edges[i]
            c, d = edges[j]
            if rng.random() < 0.5:
                a, b = b, a
            if rng.random() < 0.5:
                c, d = d, c
            new = _try_switch(cur, a, b, c, d)
            if new is not None:
                cur = new
                break
    return cur


def switch_tabu_chain(
    init_adj: np.ndarray,
    *,
    n_iters: int,
    sample_size: int,
    top_k: int,
    lb_restarts: int,
    tabu_len: int,
    patience: int,
    perturb_swaps: int,
    rng: np.random.Generator,
    time_limit_s: float | None = None,
    sample_max_attempts_mul: int = 20,
    use_exact_score: bool = False,
    composite_score: bool = False,
) -> SwitchTabuResult:
    """
    One tabu chain with iterated-local-search restarts on stagnation.
    """
    start = time.monotonic()

    n = init_adj.shape[0]
    state = init_adj.copy()

    def _score_exact(adj: np.ndarray) -> tuple[int, float]:
        alpha, _ = alpha_bb_clique_cover(adj)
        d_max = int(adj.sum(axis=1).max())
        cl = c_log_value(alpha, n, d_max)
        return alpha, (cl if cl is not None else float("inf"))

    best_alpha, best_c = _score_exact(state)
    best_adj = state.copy()
    best_iter = 0

    tabu: deque[int] = deque(maxlen=tabu_len)
    trajectory: list[float] = [best_c]
    k_trajectory: list[int] = [_multiset_k(state)]
    m_trajectory: list[int] = [int(state.sum() // 2)]
    move_kind_counts: dict[str, int] = {"swap": 0, "flip": 0}
    pool_sizes: list[int] = []
    alpha_first_reached: dict[int, int] = {best_alpha: 0}

    since_improve = 0
    n_accepted = 0
    n_aspiration = 0
    n_restarts = 0

    for it in range(1, n_iters + 1):
        if time_limit_s is not None and (time.monotonic() - start) > time_limit_s:
            break

        pool = _sample_candidates(
            state,
            target_pool=sample_size,
            max_attempts=sample_size * sample_max_attempts_mul,
            rng=rng,
            tabu=tabu,
        )
        pool_sizes.append(len(pool))
        if not pool:
            # near-K4-saturated: no legal swap found within budget.
            # Perturb best and restart rather than give up on the chain.
            state = _perturb(best_adj, perturb_swaps, rng)
            tabu.clear()
            since_improve = 0
            n_restarts += 1
            continue

        rng.shuffle(pool)  # random tie-break order

        if use_exact_score or composite_score:
            # Rank every candidate by exact α. Two modes:
            #   use_exact_score: exact α is the sole key (random tie-break).
            #   composite_score: (exact α, α_lb) lexicographic — α_lb
            #     breaks exact-α ties. At N=23 the plateau diagnostic
            #     showed 94% of feasible swaps are exact-α-tied, so the
            #     surrogate tiebreaker is load-bearing.
            for cand in pool:
                a_ex, c_ex = _score_exact(cand.new_adj)
                cand.exact_alpha = a_ex
                cand.c_log = c_ex
                if composite_score:
                    cand.surrogate_alpha = alpha_lb(
                        cand.new_adj, restarts=lb_restarts, rng=rng,
                    )
                else:
                    cand.surrogate_alpha = a_ex
            if composite_score:
                pool.sort(key=lambda c: (c.exact_alpha, c.surrogate_alpha))
                non_tabu_topk = [c for c in pool if not c.is_tabu][:top_k]
                tabu_topk = [c for c in pool if c.is_tabu][:max(2, top_k // 2)]
            else:
                non_tabu_topk = [c for c in pool if not c.is_tabu]
                tabu_topk = [c for c in pool if c.is_tabu]
        else:
            # Surrogate-rank the full pool, exact-rescore top-K.
            for cand in pool:
                cand.surrogate_alpha = alpha_lb(
                    cand.new_adj, restarts=lb_restarts, rng=rng,
                )
            pool.sort(key=lambda c: c.surrogate_alpha)
            non_tabu_topk = [c for c in pool if not c.is_tabu][:top_k]
            tabu_topk = [c for c in pool if c.is_tabu][:max(2, top_k // 2)]
            for cand in non_tabu_topk + tabu_topk:
                a_ex, c_ex = _score_exact(cand.new_adj)
                cand.exact_alpha = a_ex
                cand.c_log = c_ex

        # Pick accepted move. Preference order:
        #   1) any tabu candidate with c_log < best_c  (aspiration)
        #   2) lowest-c non-tabu candidate
        #   3) fall through to lowest-c tabu (should be rare)
        aspiration_pick = None
        best_asp_c = best_c
        for cand in tabu_topk:
            if cand.c_log < best_asp_c:
                aspiration_pick = cand
                best_asp_c = cand.c_log

        accepted = None
        if aspiration_pick is not None:
            accepted = aspiration_pick
            n_aspiration += 1
        else:
            non_tabu_topk.sort(key=lambda c: c.c_log)
            if non_tabu_topk:
                accepted = non_tabu_topk[0]
            else:
                tabu_topk.sort(key=lambda c: c.c_log)
                if tabu_topk:
                    accepted = tabu_topk[0]

        if accepted is None:
            break

        state = accepted.new_adj
        for tid in accepted.touched_ids:
            tabu.append(tid)
        n_accepted += 1
        move_kind_counts[accepted.move_kind] = (
            move_kind_counts.get(accepted.move_kind, 0) + 1
        )

        if accepted.exact_alpha not in alpha_first_reached:
            alpha_first_reached[accepted.exact_alpha] = it

        if accepted.c_log < best_c:
            best_c = accepted.c_log
            best_alpha = accepted.exact_alpha
            best_adj = state.copy()
            best_iter = it
            since_improve = 0
        else:
            since_improve += 1

        trajectory.append(accepted.c_log)
        k_trajectory.append(_multiset_k(state))
        m_trajectory.append(int(state.sum() // 2))

        if since_improve >= patience:
            # ILS restart: perturb best, clear tabu.
            state = _perturb(best_adj, perturb_swaps, rng)
            tabu.clear()
            since_improve = 0
            n_restarts += 1

    return SwitchTabuResult(
        best_adj=best_adj,
        best_alpha=best_alpha,
        best_c_log=best_c,
        best_iter=best_iter,
        n_iters=it,
        n_accepted=n_accepted,
        n_aspiration=n_aspiration,
        n_restarts=n_restarts,
        trajectory=trajectory,
        k_trajectory=k_trajectory,
        m_trajectory=m_trajectory,
        move_kind_counts=move_kind_counts,
        pool_sizes=pool_sizes,
        alpha_first_reached=alpha_first_reached,
    )


# ---------------------------------------------------------------------------
# Mixed-operator tabu chain (2-switch + edge-bitvec-flip)
# ---------------------------------------------------------------------------

def switch_tabu_chain_mixed(
    init_adj: np.ndarray,
    *,
    n_iters: int,
    sample_size_swap: int,
    sample_size_flip: int,
    top_k: int,
    lb_restarts: int,
    tabu_len: int,
    patience: int,
    perturb_swaps: int,
    spread_cap: int,
    rng: np.random.Generator,
    time_limit_s: float | None = None,
    sample_max_attempts_mul: int = 20,
    sample_size_swap3: int = 0,
    swap3_novel_only: bool = False,
    lookahead_top_k: int = 0,
    lookahead_h: int = 4,
    lookahead_M: int = 5,
    lookahead_p_flip: float = 0.5,
    lookahead_p_swap3: float = 0.0,
) -> SwitchTabuResult:
    """
    Mixed 2-switch + edge-bitvec-flip tabu chain. Both move types are
    sampled each iteration and ranked by the same c_log surrogate, so
    the search self-selects when to stay within a multiset (2-switch)
    vs. cross to a neighbouring one (flip). Spread cap gates every
    candidate — swap automatically preserves spread, flip may not.

    k-trajectory and m-trajectory log the chain's path through
    multiset space; move_kind_counts shows how often each move type
    was actually accepted.

    Three-layer ranking when `lookahead_top_k > 0`:
      1. surrogate α_lb on the full pool (cheap rank).
      2. exact α + c_log on top-K_lookahead non-tabu and top-K/2 tabu.
      3. lookahead score on top-`lookahead_top_k` non-tabu after
         step 2: M random rollouts of length h from each candidate,
         re-rank by min c_log seen. Captures "this candidate sits
         near low-α graphs even if it isn't one itself".
    Aspiration (a tabu candidate strictly improving best c_log) is
    decided one-step — lookahead doesn't gate aspiration.
    """
    start = time.monotonic()

    n = init_adj.shape[0]
    state = init_adj.copy()

    def _score_exact(adj: np.ndarray) -> tuple[int, float]:
        alpha, _ = alpha_bb_clique_cover(adj)
        d_max = int(adj.sum(axis=1).max())
        cl = c_log_value(alpha, n, d_max)
        return alpha, (cl if cl is not None else float("inf"))

    best_alpha, best_c = _score_exact(state)
    best_adj = state.copy()
    best_iter = 0

    tabu: deque[int] = deque(maxlen=tabu_len)
    trajectory: list[float] = [best_c]
    k_trajectory: list[int] = [_multiset_k(state)]
    m_trajectory: list[int] = [int(state.sum() // 2)]
    move_kind_counts: dict[str, int] = {"swap": 0, "flip": 0}
    pool_sizes: list[int] = []

    since_improve = 0
    n_accepted = 0
    n_aspiration = 0
    n_restarts = 0
    n_lookahead_iters = 0
    n_lookahead_disagree = 0
    n_lookahead_evals = 0
    lookahead_min_c = float("inf")
    swap3_stats_total: dict[str, int] = {
        "n_attempts": 0,
        "n_novel_attempts": 0, "n_equiv_attempts": 0,
        "n_novel_accepted": 0, "n_equiv_accepted": 0,
        "n_disjoint_fail": 0,
    }
    swap3_accepted_novel = 0
    swap3_accepted_equiv = 0

    for it in range(1, n_iters + 1):
        if time_limit_s is not None and (time.monotonic() - start) > time_limit_s:
            break

        swap_pool = _sample_candidates(
            state,
            target_pool=sample_size_swap,
            max_attempts=sample_size_swap * sample_max_attempts_mul,
            rng=rng, tabu=tabu,
        )
        flip_pool = _sample_flip_candidates(
            state,
            target_pool=sample_size_flip,
            max_attempts=sample_size_flip * sample_max_attempts_mul,
            rng=rng, tabu=tabu, spread_cap=spread_cap,
        )
        if sample_size_swap3 > 0:
            swap3_pool, sw3_stats = _sample_3switch_candidates(
                state,
                target_pool=sample_size_swap3,
                max_attempts=sample_size_swap3 * sample_max_attempts_mul,
                rng=rng, tabu=tabu, novel_only=swap3_novel_only,
            )
            for k, v in sw3_stats.items():
                swap3_stats_total[k] += v
            # Spread cap on 3-switch results: 3-switches preserve the
            # whole multiset (vertex-disjoint endpoints retain degree),
            # so spread is invariant — no extra filter needed.
        else:
            swap3_pool = []
        pool = swap_pool + flip_pool + swap3_pool
        pool_sizes.append(len(pool))

        if not pool:
            state = _perturb(best_adj, perturb_swaps, rng)
            tabu.clear()
            since_improve = 0
            n_restarts += 1
            continue

        for cand in pool:
            cand.surrogate_alpha = alpha_lb(
                cand.new_adj, restarts=lb_restarts, rng=rng,
            )

        rng.shuffle(pool)
        pool.sort(key=lambda c: c.surrogate_alpha)
        non_tabu_topk = [c for c in pool if not c.is_tabu][:top_k]
        tabu_topk = [c for c in pool if c.is_tabu][:max(2, top_k // 2)]
        for cand in non_tabu_topk + tabu_topk:
            a_ex, c_ex = _score_exact(cand.new_adj)
            cand.exact_alpha = a_ex
            cand.c_log = c_ex

        aspiration_pick = None
        best_asp_c = best_c
        for cand in tabu_topk:
            if cand.c_log < best_asp_c:
                aspiration_pick = cand
                best_asp_c = cand.c_log

        accepted = None
        if aspiration_pick is not None:
            accepted = aspiration_pick
            n_aspiration += 1
        else:
            non_tabu_topk.sort(key=lambda c: c.c_log)
            if non_tabu_topk:
                # Layer 3: rollout-based lookahead on the lookahead_top_k
                # lowest-c_log non-tabu candidates. Re-rank by lookahead.
                if lookahead_top_k > 0 and len(non_tabu_topk) >= 1:
                    head = non_tabu_topk[: lookahead_top_k]
                    onestep_pick = head[0]
                    for cand in head:
                        score, n_ev = _lookahead_score(
                            cand.new_adj,
                            h=lookahead_h,
                            M=lookahead_M,
                            spread_cap=spread_cap,
                            rng=rng,
                            p_flip=lookahead_p_flip,
                            p_swap3=lookahead_p_swap3,
                        )
                        # Stash on the candidate so logs/diagnostics
                        # can recover it; reuse `surrogate_alpha`'s
                        # role with a synthetic field on the dataclass.
                        cand.lookahead_c_log = score  # type: ignore[attr-defined]
                        n_lookahead_evals += n_ev
                        if score < lookahead_min_c:
                            lookahead_min_c = score
                    head.sort(key=lambda c: c.lookahead_c_log)  # type: ignore[attr-defined]
                    accepted = head[0]
                    n_lookahead_iters += 1
                    if accepted is not onestep_pick:
                        n_lookahead_disagree += 1
                else:
                    accepted = non_tabu_topk[0]
            else:
                tabu_topk.sort(key=lambda c: c.c_log)
                if tabu_topk:
                    accepted = tabu_topk[0]

        if accepted is None:
            break

        state = accepted.new_adj
        for tid in accepted.touched_ids:
            tabu.append(tid)
        n_accepted += 1
        move_kind_counts[accepted.move_kind] = (
            move_kind_counts.get(accepted.move_kind, 0) + 1
        )
        if accepted.move_kind == "swap3":
            swap3_accepted_novel += 1
        elif accepted.move_kind == "swap3_equiv":
            swap3_accepted_equiv += 1

        if accepted.c_log < best_c:
            best_c = accepted.c_log
            best_alpha = accepted.exact_alpha
            best_adj = state.copy()
            best_iter = it
            since_improve = 0
        else:
            since_improve += 1

        trajectory.append(accepted.c_log)
        k_trajectory.append(_multiset_k(state))
        m_trajectory.append(int(state.sum() // 2))

        if since_improve >= patience:
            state = _perturb(best_adj, perturb_swaps, rng)
            tabu.clear()
            since_improve = 0
            n_restarts += 1

    return SwitchTabuResult(
        best_adj=best_adj,
        best_alpha=best_alpha,
        best_c_log=best_c,
        best_iter=best_iter,
        n_iters=it,
        n_accepted=n_accepted,
        n_aspiration=n_aspiration,
        n_restarts=n_restarts,
        trajectory=trajectory,
        k_trajectory=k_trajectory,
        m_trajectory=m_trajectory,
        move_kind_counts=move_kind_counts,
        pool_sizes=pool_sizes,
        n_lookahead_iters=n_lookahead_iters,
        n_lookahead_disagree=n_lookahead_disagree,
        n_lookahead_evals=n_lookahead_evals,
        lookahead_min_c_log=lookahead_min_c,
        swap3_stats=swap3_stats_total,
        swap3_accepted_novel=swap3_accepted_novel,
        swap3_accepted_equiv=swap3_accepted_equiv,
    )


# ---------------------------------------------------------------------------
# Search subclass
# ---------------------------------------------------------------------------

def _random_nearreg_k4free(
    n: int, d_target: int, rng: np.random.Generator,
) -> np.ndarray:
    """Shuffled-greedy random K4-free build with degree cap d_target."""
    adj = np.zeros((n, n), dtype=np.uint8)
    degs = np.zeros(n, dtype=int)
    pairs = [(u, v) for u in range(n) for v in range(u + 1, n)]
    rng.shuffle(pairs)
    for _pass in range(2):
        for u, v in pairs:
            if adj[u, v] or degs[u] >= d_target or degs[v] >= d_target:
                continue
            adj[u, v] = adj[v, u] = 1
            if is_k4_free(adj):
                degs[u] += 1
                degs[v] += 1
            else:
                adj[u, v] = adj[v, u] = 0
    return adj


def _build_multiset_init(
    n: int, target_degrees: list[int], rng: np.random.Generator,
    max_attempts: int = 8,
) -> np.ndarray | None:
    """
    Shuffled-greedy K4-free build with *per-vertex* degree caps.

    `target_degrees[v]` is the hard cap for vertex v. If the build
    can't fill to every cap (K4 walls), we retry up to `max_attempts`
    with new shuffles and keep the attempt that matched the most
    vertices' targets. Returns None only if every attempt produced an
    empty or wildly-off graph.

    Used for the k-fixed cold-start ablation: pass the frontier's
    degree sequence (shuffled per-seed to get different labelings)
    and the search starts inside the correct multiset basin.
    """
    best = None
    best_match_score = -1
    for _ in range(max_attempts):
        targets = list(target_degrees)
        rng.shuffle(targets)
        adj = np.zeros((n, n), dtype=np.uint8)
        degs = np.zeros(n, dtype=int)
        pairs = [(u, v) for u in range(n) for v in range(u + 1, n)]
        rng.shuffle(pairs)
        for _pass in range(3):
            for u, v in pairs:
                if adj[u, v]:
                    continue
                if degs[u] >= targets[u] or degs[v] >= targets[v]:
                    continue
                adj[u, v] = adj[v, u] = 1
                if is_k4_free(adj):
                    degs[u] += 1
                    degs[v] += 1
                else:
                    adj[u, v] = adj[v, u] = 0
        score = int(sum(degs[v] == targets[v] for v in range(n)))
        if score > best_match_score:
            best_match_score = score
            best = adj
            if score == n:
                break
    return best


# ---------------------------------------------------------------------------
# Edge-bitvec-flip candidates (multiset-crossing moves)
# ---------------------------------------------------------------------------

def _sample_flip_candidates(
    adj: np.ndarray,
    *,
    target_pool: int,
    max_attempts: int,
    rng: np.random.Generator,
    tabu: Iterable[int],
    spread_cap: int,
) -> list["SwitchCandidate"]:
    """
    Sample random edge-bitvec flips (toggle one edge). Accept iff:
      * K4-free after the toggle
      * post-move degree spread (d_max - d_min) ≤ spread_cap

    touched_ids is length-1 (the toggled edge id) to distinguish from
    2-switch candidates which touch 4 edge ids.
    """
    n = adj.shape[0]
    tabu_set = set(tabu)
    out: list[SwitchCandidate] = []
    attempts = 0
    while len(out) < target_pool and attempts < max_attempts:
        attempts += 1
        u = int(rng.integers(0, n))
        v = int(rng.integers(0, n))
        if u == v:
            continue
        if u > v:
            u, v = v, u
        new = adj.copy()
        if adj[u, v]:
            new[u, v] = new[v, u] = 0
            # removal can't create a K4
        else:
            new[u, v] = new[v, u] = 1
            if find_k4(new) is not None:
                continue
        degs = new.sum(axis=1)
        spread = int(degs.max()) - int(degs.min())
        if spread > spread_cap:
            continue
        eid = _edge_id(u, v, n)
        touched = (eid,)
        is_tabu = eid in tabu_set
        out.append(SwitchCandidate(
            new_adj=new,
            touched_ids=touched,
            is_tabu=is_tabu,
            move_kind="flip",
        ))
    return out


def _adj_to_nx(adj: np.ndarray) -> nx.Graph:
    n = adj.shape[0]
    G = nx.Graph()
    G.add_nodes_from(range(n))
    for i in range(n):
        for j in range(i + 1, n):
            if adj[i, j]:
                G.add_edge(i, j)
    return G


# ---------------------------------------------------------------------------
# Rollout-based lookahead (used as the third ranking layer in the mixed chain)
# ---------------------------------------------------------------------------

def _random_legal_move_mixed(
    adj: np.ndarray,
    *,
    rng: np.random.Generator,
    spread_cap: int,
    p_flip: float = 0.5,
    p_swap3: float = 0.0,
    max_attempts: int = 200,
) -> np.ndarray | None:
    """
    Sample one legal mixed move (flip / 2-switch / 3-switch), apply
    it, return the resulting adj. None if `max_attempts` exhausted.

    Move type picked per attempt:
      r ∈ [0, p_flip)                  → flip
      r ∈ [p_flip, p_flip + p_swap3)   → 3-switch (any pairing)
      r ∈ [p_flip + p_swap3, 1)        → 2-switch

    `p_flip + p_swap3` should be ≤ 1. With `p_swap3 = 0` the
    distribution reduces to the 2-switch + flip mix used by the
    no-3-switch lookahead.

    Used inside lookahead rollouts. Rollouts are *random walks on the
    legal-move graph*, so the sampling rule is unbiased; the caller
    decides ranking via `_lookahead_score`.
    """
    n = adj.shape[0]
    edges = _edges_of(adj)
    m = len(edges)
    for _ in range(max_attempts):
        r = rng.random()
        if r < p_flip or m < 2:
            # flip attempt
            u = int(rng.integers(0, n))
            v = int(rng.integers(0, n))
            if u == v:
                continue
            if u > v:
                u, v = v, u
            new = adj.copy()
            if adj[u, v]:
                new[u, v] = new[v, u] = 0
            else:
                new[u, v] = new[v, u] = 1
                if find_k4(new) is not None:
                    continue
            degs = new.sum(axis=1)
            spread = int(degs.max()) - int(degs.min())
            if spread > spread_cap:
                continue
            return new
        elif r < p_flip + p_swap3 and m >= 3:
            # 3-switch attempt
            new = _try_3switch_random(adj, rng, max_attempts=8)
            if new is not None:
                return new
        else:
            # 2-switch attempt
            i = int(rng.integers(0, m))
            j = int(rng.integers(0, m))
            if i == j:
                continue
            a, b = edges[i]
            c, d = edges[j]
            if rng.random() < 0.5:
                a, b = b, a
            if rng.random() < 0.5:
                c, d = d, c
            new = _try_switch(adj, a, b, c, d)
            if new is not None:
                return new
    return None


def _lookahead_score(
    adj: np.ndarray,
    *,
    h: int,
    M: int,
    spread_cap: int,
    rng: np.random.Generator,
    p_flip: float = 0.5,
    p_swap3: float = 0.0,
) -> tuple[float, int]:
    """
    Rollout-based lookahead score. Returns (min_c_log_seen, n_evals).

    Idea: the score for a candidate G' is "the lowest c_log reachable
    by random walk in M independent rollouts of length h from G',
    inclusive of G' itself". This probes whether the *region* around
    G' contains low-α graphs, not just whether G' itself is good.
    Random rollouts (rather than greedy) ensure the probe spreads out
    instead of always heading where the one-step ranker already
    points.

    Cost: at most M * h legal-move samples and α-evaluations. Run only
    on the small lookahead_top_k set after composite ranking.
    """
    n = adj.shape[0]
    a0, _ = alpha_bb_clique_cover(adj)
    d0 = int(adj.sum(axis=1).max())
    c0 = c_log_value(a0, n, d0)
    best_c = c0 if c0 is not None else float("inf")
    n_evals = 1

    for _ in range(M):
        cur = adj
        for _ in range(h):
            new = _random_legal_move_mixed(
                cur, rng=rng, spread_cap=spread_cap,
                p_flip=p_flip, p_swap3=p_swap3,
            )
            if new is None:
                break
            cur = new
            ca, _ = alpha_bb_clique_cover(cur)
            cd = int(cur.sum(axis=1).max())
            cc = c_log_value(ca, n, cd)
            n_evals += 1
            if cc is not None and cc < best_c:
                best_c = cc
    return best_c, n_evals


class SwitchTabuSearch(Search):
    """
    2-switch tabu on the full near-regular K4-free edge space.

    Constraints
    -----------
    d_target : int | None
        Soft. Target vertex degree for random init. If None, defaults
        to round(n ** (2/3)).
    n_restarts : int
        Soft. Independent chain restarts (each from a fresh random init
        OR from a provided warm_start_adj, perturbed). Default 3.
    n_iters : int
        Soft. Tabu iterations per chain. Default 300.
    sample_size : int
        Soft. Candidate 2-switches sampled per iteration. Default 120.
    top_k_verify : int
        Soft. Top-K by surrogate alpha to exact-verify each iter. Default 6.
    lb_restarts : int
        Soft. alpha_lb restarts per surrogate call. Default 12.
    tabu_len : int | None
        Soft. Length of touched-edge tabu deque. Default = 2·d_target.
    patience : int
        Soft. Iters without improvement before ILS restart. Default 40.
    perturb_swaps : int
        Soft. Random swaps applied to best on ILS restart. Default 5.
    warm_start_adj : np.ndarray | None
        Soft. If given, use as init state for chain 0 instead of random.
    time_limit_s : float | None
        Soft. Wall-clock cap per chain. Default None.
    random_seed : int | None
        Soft. Base RNG seed. Default None.
    """

    name = "switch_tabu"

    def __init__(
        self,
        n: int,
        *,
        top_k: int = 1,
        verbosity: int = 0,
        parent_logger=None,
        d_target: int | None = None,
        n_restarts: int = 3,
        n_iters: int = 300,
        sample_size: int = 120,
        top_k_verify: int = 6,
        lb_restarts: int = 12,
        tabu_len: int | None = None,
        patience: int = 40,
        perturb_swaps: int = 5,
        warm_start_adj: np.ndarray | None = None,
        time_limit_s: float | None = None,
        random_seed: int | None = None,
        **kwargs,
    ):
        super().__init__(
            n,
            top_k=top_k,
            verbosity=verbosity,
            parent_logger=parent_logger,
            d_target=d_target,
            n_restarts=n_restarts,
            n_iters=n_iters,
            sample_size=sample_size,
            top_k_verify=top_k_verify,
            lb_restarts=lb_restarts,
            tabu_len=tabu_len,
            patience=patience,
            perturb_swaps=perturb_swaps,
            time_limit_s=time_limit_s,
            random_seed=random_seed,
            **kwargs,
        )
        # keep warm_start outside kwargs (arrays aren't JSON-friendly)
        self._warm_start_adj = warm_start_adj

    def _alpha_of(self, G: nx.Graph):
        adj = np.array(nx.to_numpy_array(G, dtype=np.uint8))
        return alpha_bb_clique_cover(adj)

    def _run(self) -> list[nx.Graph]:
        rng = np.random.default_rng(self.random_seed)
        d_target = self.d_target
        if d_target is None:
            d_target = max(3, round(self.n ** (2 / 3)))
        tabu_len = self.tabu_len or max(4, 2 * d_target)

        out: list[nx.Graph] = []
        for r in range(self.n_restarts):
            if r == 0 and self._warm_start_adj is not None:
                init = self._warm_start_adj.copy()
            else:
                init = _random_nearreg_k4free(self.n, d_target, rng)
            if init.sum() == 0:
                continue

            t0 = time.monotonic()
            res = switch_tabu_chain(
                init,
                n_iters=self.n_iters,
                sample_size=self.sample_size,
                top_k=self.top_k_verify,
                lb_restarts=self.lb_restarts,
                tabu_len=tabu_len,
                patience=self.patience,
                perturb_swaps=self.perturb_swaps,
                rng=rng,
                time_limit_s=self.time_limit_s,
            )
            elapsed = time.monotonic() - t0

            degs = res.best_adj.sum(axis=1)
            self._log(
                "chain_done",
                level=1,
                restart=r,
                d_target=d_target,
                d_min=int(degs.min()),
                d_max=int(degs.max()),
                best_alpha=res.best_alpha,
                best_c_log=round(float(res.best_c_log), 6),
                best_iter=res.best_iter,
                n_iters=res.n_iters,
                n_accepted=res.n_accepted,
                n_aspiration=res.n_aspiration,
                n_ils_restarts=res.n_restarts,
                elapsed_s=round(elapsed, 2),
            )

            if not np.isfinite(res.best_c_log):
                continue

            G = _adj_to_nx(res.best_adj)
            self._stamp(G)
            G.graph["metadata"] = {
                "restart": int(r),
                "d_target": int(d_target),
                "d_min": int(degs.min()),
                "d_max": int(degs.max()),
                "tabu_best_iter": int(res.best_iter),
                "tabu_n_iters": int(res.n_iters),
                "tabu_n_accepted": int(res.n_accepted),
                "tabu_n_aspiration": int(res.n_aspiration),
                "tabu_n_ils_restarts": int(res.n_restarts),
                "warm_started": bool(r == 0 and self._warm_start_adj is not None),
            }
            out.append(G)
        return out


# ---------------------------------------------------------------------------
# Mixed-operator + lookahead Search subclass
# ---------------------------------------------------------------------------

class SwitchTabuMixedLookaheadSearch(Search):
    """
    Mixed 2-switch + edge-bitvec-flip tabu chain with rollout-based
    lookahead as the third ranking layer.

    Constraints
    -----------
    d_target : int | None
        Soft. Target vertex degree for random init. Default round(n^(2/3)).
    n_restarts : int
        Soft. Independent chain restarts. Default 3.
    n_iters : int
        Soft. Tabu iterations per chain. Default 300.
    sample_size_swap : int
        Soft. Number of 2-switch candidates sampled per iter. Default 80.
    sample_size_flip : int
        Soft. Number of edge-flip candidates sampled per iter. Default 40.
    top_k_verify : int
        Soft. Top-K by surrogate to exact-verify each iter. Default 6.
    lookahead_top_k : int
        Soft. Top-K (after exact-rerank) to lookahead-rerank. 0 disables
        lookahead and the chain reduces to plain mixed tabu. Default 5.
    lookahead_h : int
        Soft. Rollout horizon. Default 4.
    lookahead_M : int
        Soft. Rollouts per candidate. Default 5.
    lookahead_p_flip : float
        Soft. Probability of attempting a flip vs. a 2-switch in
        rollouts. Default 0.5.
    lb_restarts : int
        Soft. α-surrogate restarts. Default 12.
    tabu_len : int | None
        Soft. Edge-id tabu deque length. Default = 2·d_target.
    patience : int
        Soft. Iters without improvement before ILS restart. Default 40.
    perturb_swaps : int
        Soft. ILS-restart perturbation size. Default 5.
    spread_cap : int
        Soft. Post-move (d_max - d_min) cap on flip moves. Default 1.
    warm_start_adj : np.ndarray | None
        Soft. If given, init chain 0 from this adj.
    time_limit_s : float | None
        Soft. Wall-clock cap per chain.
    random_seed : int | None
        Soft. Base RNG seed.
    """

    name = "switch_tabu_mixed_lookahead"

    def __init__(
        self,
        n: int,
        *,
        top_k: int = 1,
        verbosity: int = 0,
        parent_logger=None,
        d_target: int | None = None,
        n_restarts: int = 3,
        n_iters: int = 300,
        sample_size_swap: int = 80,
        sample_size_flip: int = 40,
        sample_size_swap3: int = 0,
        swap3_novel_only: bool = False,
        top_k_verify: int = 6,
        lookahead_top_k: int = 5,
        lookahead_h: int = 4,
        lookahead_M: int = 5,
        lookahead_p_flip: float = 0.5,
        lookahead_p_swap3: float = 0.0,
        lb_restarts: int = 12,
        tabu_len: int | None = None,
        patience: int = 40,
        perturb_swaps: int = 5,
        spread_cap: int = 1,
        warm_start_adj: np.ndarray | None = None,
        time_limit_s: float | None = None,
        random_seed: int | None = None,
        **kwargs,
    ):
        super().__init__(
            n,
            top_k=top_k,
            verbosity=verbosity,
            parent_logger=parent_logger,
            d_target=d_target,
            n_restarts=n_restarts,
            n_iters=n_iters,
            sample_size_swap=sample_size_swap,
            sample_size_flip=sample_size_flip,
            sample_size_swap3=sample_size_swap3,
            swap3_novel_only=swap3_novel_only,
            top_k_verify=top_k_verify,
            lookahead_top_k=lookahead_top_k,
            lookahead_h=lookahead_h,
            lookahead_M=lookahead_M,
            lookahead_p_flip=lookahead_p_flip,
            lookahead_p_swap3=lookahead_p_swap3,
            lb_restarts=lb_restarts,
            tabu_len=tabu_len,
            patience=patience,
            perturb_swaps=perturb_swaps,
            spread_cap=spread_cap,
            time_limit_s=time_limit_s,
            random_seed=random_seed,
            **kwargs,
        )
        self._warm_start_adj = warm_start_adj

    def _alpha_of(self, G: nx.Graph):
        adj = np.array(nx.to_numpy_array(G, dtype=np.uint8))
        return alpha_bb_clique_cover(adj)

    def _run(self) -> list[nx.Graph]:
        rng = np.random.default_rng(self.random_seed)
        d_target = self.d_target
        if d_target is None:
            d_target = max(3, round(self.n ** (2 / 3)))
        # Tabu length scales with the chain's average move size to keep
        # edge-tabu memory parity. 2-switch touches 4 ids, flip 1, and
        # 3-switch 6. With swap3 enabled we lift the deque by 1.5×.
        base_tabu_len = self.tabu_len or max(4, 2 * d_target)
        if self.sample_size_swap3 > 0 and self.tabu_len is None:
            tabu_len = int(round(base_tabu_len * 1.5))
        else:
            tabu_len = base_tabu_len

        out: list[nx.Graph] = []
        for r in range(self.n_restarts):
            if r == 0 and self._warm_start_adj is not None:
                init = self._warm_start_adj.copy()
            else:
                init = _random_nearreg_k4free(self.n, d_target, rng)
            if init.sum() == 0:
                continue

            t0 = time.monotonic()
            res = switch_tabu_chain_mixed(
                init,
                n_iters=self.n_iters,
                sample_size_swap=self.sample_size_swap,
                sample_size_flip=self.sample_size_flip,
                sample_size_swap3=self.sample_size_swap3,
                swap3_novel_only=self.swap3_novel_only,
                top_k=self.top_k_verify,
                lb_restarts=self.lb_restarts,
                tabu_len=tabu_len,
                patience=self.patience,
                perturb_swaps=self.perturb_swaps,
                spread_cap=self.spread_cap,
                rng=rng,
                time_limit_s=self.time_limit_s,
                lookahead_top_k=self.lookahead_top_k,
                lookahead_h=self.lookahead_h,
                lookahead_M=self.lookahead_M,
                lookahead_p_flip=self.lookahead_p_flip,
                lookahead_p_swap3=self.lookahead_p_swap3,
            )
            elapsed = time.monotonic() - t0

            degs = res.best_adj.sum(axis=1)
            self._log(
                "chain_done",
                level=1,
                restart=r,
                d_target=d_target,
                d_min=int(degs.min()),
                d_max=int(degs.max()),
                best_alpha=res.best_alpha,
                best_c_log=round(float(res.best_c_log), 6),
                best_iter=res.best_iter,
                n_iters=res.n_iters,
                n_accepted=res.n_accepted,
                n_aspiration=res.n_aspiration,
                n_ils_restarts=res.n_restarts,
                n_lookahead_iters=res.n_lookahead_iters,
                n_lookahead_disagree=res.n_lookahead_disagree,
                n_lookahead_evals=res.n_lookahead_evals,
                lookahead_min_c_log=(
                    None
                    if not np.isfinite(res.lookahead_min_c_log)
                    else round(float(res.lookahead_min_c_log), 6)
                ),
                swap3_stats=dict(res.swap3_stats),
                swap3_accepted_novel=res.swap3_accepted_novel,
                swap3_accepted_equiv=res.swap3_accepted_equiv,
                tabu_len=tabu_len,
                move_kind_counts=dict(res.move_kind_counts),
                elapsed_s=round(elapsed, 2),
            )

            if not np.isfinite(res.best_c_log):
                continue

            G = _adj_to_nx(res.best_adj)
            self._stamp(G)
            G.graph["metadata"] = {
                "restart": int(r),
                "d_target": int(d_target),
                "d_min": int(degs.min()),
                "d_max": int(degs.max()),
                "spread_cap": int(self.spread_cap),
                "sample_size_swap3": int(self.sample_size_swap3),
                "swap3_novel_only": bool(self.swap3_novel_only),
                "lookahead_top_k": int(self.lookahead_top_k),
                "lookahead_h": int(self.lookahead_h),
                "lookahead_M": int(self.lookahead_M),
                "lookahead_p_swap3": float(self.lookahead_p_swap3),
                "tabu_len": int(tabu_len),
                "tabu_best_iter": int(res.best_iter),
                "tabu_n_iters": int(res.n_iters),
                "tabu_n_accepted": int(res.n_accepted),
                "tabu_n_aspiration": int(res.n_aspiration),
                "tabu_n_ils_restarts": int(res.n_restarts),
                "lookahead_n_iters": int(res.n_lookahead_iters),
                "lookahead_n_disagree": int(res.n_lookahead_disagree),
                "lookahead_n_evals": int(res.n_lookahead_evals),
                "lookahead_min_c_log_seen": (
                    None
                    if not np.isfinite(res.lookahead_min_c_log)
                    else float(res.lookahead_min_c_log)
                ),
                "swap3_stats": dict(res.swap3_stats),
                "swap3_accepted_novel": int(res.swap3_accepted_novel),
                "swap3_accepted_equiv": int(res.swap3_accepted_equiv),
                "move_kind_counts": dict(res.move_kind_counts),
                "warm_started": bool(r == 0 and self._warm_start_adj is not None),
            }
            out.append(G)
        return out
