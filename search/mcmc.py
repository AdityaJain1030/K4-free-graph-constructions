"""
search/mcmc.py
===============
Metropolis-Hastings on the K4-free near-regular graph space.

Same move semantics as `search.switch_tabu` (2-switch on the edge bitvec),
but ranking and acceptance are replaced with a temperature-controlled MH
step: propose one move, accept with probability  min(1, exp(-β·Δc_log)).
The chain has no tabu memory and no top-K filtering.

Why 2-switch only, symmetric acceptance
---------------------------------------
Under 2-switch the entire degree sequence is preserved, so d_max is
invariant and Δc_log is `Δα · d_max / (N · ln(d_max))`. The proposal
"sample an ordered pair of distinct edges and an orientation, attempt
the swap" is symmetric: for the forward swap (a,b)(c,d) → (a,c)(b,d)
and the reverse (a,c)(b,d) → (a,b)(c,d), both ends sample from the
same-size edge set with the same orientation rules, so q(G'|G) =
q(G|G'). The standard reject-on-invalid (illegal endpoints, edge
collision, K4 violation) preserves detailed balance against the target
density restricted to K4-free graphs (Cooper–Dyer–Greenhill, McKay–
Wormald).  Adding edge-bitvec flip would break this symmetry and
require a proper q(G|G')/q(G'|G) correction; we keep it 2-switch only
in this first cut.

What MH gives over the tabu chain
---------------------------------
* Plateau navigation is principled: α-tied moves have Δc_log = 0, so
  A = 1, every plateau neighbour is equally accepted. The chain does a
  uniform random walk on the plateau and accepts α-improving moves
  with probability 1.
* Worsening moves are accepted with probability that decays smoothly
  with the magnitude of the worsening. β controls the trade-off.

What it doesn't give
--------------------
* Cross-multiset moves (Δm ≠ 0). The 2-switch chain is partitioned by
  degree multiset; a single chain cannot leave its starting multiset.
  Multi-multiset exploration is the parallel-tempering / flip-with-
  correction extension we'll layer on later if the simple version
  underperforms.
"""

from __future__ import annotations

import os
import sys
import time
from dataclasses import dataclass, field
from math import exp, log
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

from .base import Search


# ---------------------------------------------------------------------------
# Move proposal — one 2-switch attempt
# ---------------------------------------------------------------------------

def _edges_of(adj: np.ndarray) -> list[tuple[int, int]]:
    n = adj.shape[0]
    return [(i, j) for i in range(n) for j in range(i + 1, n) if adj[i, j]]


def _propose_switch(
    adj: np.ndarray,
    edges: list[tuple[int, int]],
    rng: np.random.Generator,
) -> np.ndarray | None:
    """
    Sample one 2-switch attempt. Returns the resulting adj if the move
    is legal + K4-free, else None.

    The proposal is symmetric on the K4-free 2-switch chain: pick an
    ordered pair of distinct edges, a random orientation per edge,
    swap. The reverse move samples from the same distribution so
    q(G'|G) = q(G|G'); rejection-on-invalid then preserves detailed
    balance.
    """
    m = len(edges)
    if m < 2:
        return None
    i = int(rng.integers(0, m))
    j = int(rng.integers(0, m))
    if i == j:
        return None
    a, b = edges[i]
    c, d = edges[j]
    if rng.random() < 0.5:
        a, b = b, a
    if rng.random() < 0.5:
        c, d = d, c

    # Cheap pre-filters.
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


# ---------------------------------------------------------------------------
# One-chain Metropolis-Hastings
# ---------------------------------------------------------------------------

@dataclass
class MCMCResult:
    best_adj: np.ndarray
    best_alpha: int
    best_c_log: float
    best_iter: int
    n_iters: int
    n_proposed: int
    n_accepted: int          # incl. plateau / improving moves
    n_accepted_worse: int    # accepted with α going up
    n_rejected_invalid: int  # K4 / edge collision / endpoint
    n_rejected_metropolis: int  # legal but failed the MH coin flip
    trajectory: list[float] = field(default_factory=list)  # current c_log per iter
    alpha_trajectory: list[int] = field(default_factory=list)
    alpha_first_reached: dict[int, int] = field(default_factory=dict)


def mcmc_chain(
    init_adj: np.ndarray,
    *,
    n_iters: int,
    beta: float,
    rng: np.random.Generator,
    time_limit_s: float | None = None,
    log_every: int = 0,
    logger=None,
) -> MCMCResult:
    """
    Run a single Metropolis-Hastings chain on the K4-free 2-switch
    graph at fixed degree multiset (the 2-switch's invariant).

    Parameters
    ----------
    beta : float
        Inverse temperature in the target π(G) ∝ exp(-β · c_log(G)).
        β = 0 → uniform sampling over the K4-free 2-switch class.
        β → ∞ → greedy descent.
    n_iters : int
        Number of proposals (one MH step per iter).
    """
    start = time.monotonic()
    n = init_adj.shape[0]
    state = init_adj.copy()
    edges = _edges_of(state)

    # d_max invariant under 2-switch — compute once for cheap c_log.
    d_max = int(state.sum(axis=1).max())
    log_d = log(d_max) if d_max > 1 else None

    def _c_of(alpha: int) -> float:
        if log_d is None:
            return float("inf")
        return alpha * d_max / (n * log_d)

    cur_alpha, _ = alpha_bb_clique_cover(state)
    cur_c = _c_of(cur_alpha)
    best_alpha, best_c = cur_alpha, cur_c
    best_adj = state.copy()
    best_iter = 0

    n_proposed = 0
    n_accepted = 0
    n_accepted_worse = 0
    n_rejected_invalid = 0
    n_rejected_metropolis = 0

    trajectory = [cur_c]
    alpha_trajectory = [cur_alpha]
    alpha_first_reached: dict[int, int] = {cur_alpha: 0}

    for it in range(1, n_iters + 1):
        if time_limit_s is not None and (time.monotonic() - start) > time_limit_s:
            break

        n_proposed += 1
        new = _propose_switch(state, edges, rng)
        if new is None:
            n_rejected_invalid += 1
            trajectory.append(cur_c)
            alpha_trajectory.append(cur_alpha)
            continue

        new_alpha, _ = alpha_bb_clique_cover(new)
        new_c = _c_of(new_alpha)

        delta = new_c - cur_c
        if delta <= 0.0:
            accept = True
        else:
            accept = rng.random() < exp(-beta * delta)

        if accept:
            state = new
            edges = _edges_of(state)  # rebuild — could be incrementalised
            cur_alpha = new_alpha
            cur_c = new_c
            n_accepted += 1
            if delta > 0:
                n_accepted_worse += 1
            if cur_alpha not in alpha_first_reached:
                alpha_first_reached[cur_alpha] = it
            if cur_c < best_c:
                best_c = cur_c
                best_alpha = cur_alpha
                best_adj = state.copy()
                best_iter = it
        else:
            n_rejected_metropolis += 1

        trajectory.append(cur_c)
        alpha_trajectory.append(cur_alpha)

        if log_every and logger is not None and it % log_every == 0:
            logger(
                "mcmc_progress",
                iter=it,
                cur_alpha=cur_alpha,
                cur_c_log=round(cur_c, 6),
                best_alpha=best_alpha,
                best_c_log=round(best_c, 6),
                n_accepted=n_accepted,
                n_rejected_invalid=n_rejected_invalid,
                n_rejected_metropolis=n_rejected_metropolis,
            )

    return MCMCResult(
        best_adj=best_adj,
        best_alpha=best_alpha,
        best_c_log=best_c,
        best_iter=best_iter,
        n_iters=it,
        n_proposed=n_proposed,
        n_accepted=n_accepted,
        n_accepted_worse=n_accepted_worse,
        n_rejected_invalid=n_rejected_invalid,
        n_rejected_metropolis=n_rejected_metropolis,
        trajectory=trajectory,
        alpha_trajectory=alpha_trajectory,
        alpha_first_reached=alpha_first_reached,
    )


# ---------------------------------------------------------------------------
# Random near-regular K4-free init (same as switch_tabu)
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
# Search subclass
# ---------------------------------------------------------------------------

class MCMCSearch(Search):
    """
    Single-chain Metropolis-Hastings search on the K4-free 2-switch graph.

    Constraints
    -----------
    d_target : int | None
        Soft. Target vertex degree for random init. If None, defaults to
        round(n ** (2/3)).
    n_restarts : int
        Soft. Independent chain restarts (each from a fresh random init OR
        from `warm_start_adj` perturbed). Default 3.
    n_iters : int
        Soft. MH proposals per chain. Default 5000.
    beta : float
        Soft. Inverse temperature. Default 20.0.
    warm_start_adj : np.ndarray | None
        Soft. Use as init for chain 0 instead of random.
    time_limit_s : float | None
        Soft. Wall-clock cap per chain. Default None.
    random_seed : int | None
        Soft. Base RNG seed.
    log_every : int
        Soft. If > 0, emit a progress log every K iters at verbosity ≥ 2.
    """

    name = "mcmc"

    def __init__(
        self,
        n: int,
        *,
        top_k: int = 1,
        verbosity: int = 0,
        parent_logger=None,
        d_target: int | None = None,
        n_restarts: int = 3,
        n_iters: int = 5000,
        beta: float = 20.0,
        warm_start_adj: np.ndarray | None = None,
        time_limit_s: float | None = None,
        random_seed: int | None = None,
        log_every: int = 0,
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
            beta=beta,
            time_limit_s=time_limit_s,
            random_seed=random_seed,
            log_every=log_every,
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

        out: list[nx.Graph] = []
        for r in range(self.n_restarts):
            if r == 0 and self._warm_start_adj is not None:
                init = self._warm_start_adj.copy()
            else:
                init = _random_nearreg_k4free(self.n, d_target, rng)
            if init.sum() == 0:
                continue

            t0 = time.monotonic()
            res = mcmc_chain(
                init,
                n_iters=self.n_iters,
                beta=self.beta,
                rng=rng,
                time_limit_s=self.time_limit_s,
                log_every=self.log_every,
                logger=(lambda ev, **kv: self._log(ev, level=2, restart=r, **kv)),
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
                n_proposed=res.n_proposed,
                n_accepted=res.n_accepted,
                n_accepted_worse=res.n_accepted_worse,
                n_rejected_invalid=res.n_rejected_invalid,
                n_rejected_metropolis=res.n_rejected_metropolis,
                accept_rate_legal=(
                    round(res.n_accepted / max(1, res.n_proposed - res.n_rejected_invalid), 4)
                ),
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
                "beta": float(self.beta),
                "mcmc_best_iter": int(res.best_iter),
                "mcmc_n_iters": int(res.n_iters),
                "mcmc_n_proposed": int(res.n_proposed),
                "mcmc_n_accepted": int(res.n_accepted),
                "mcmc_n_accepted_worse": int(res.n_accepted_worse),
                "mcmc_n_rejected_invalid": int(res.n_rejected_invalid),
                "mcmc_n_rejected_metropolis": int(res.n_rejected_metropolis),
                "warm_started": bool(r == 0 and self._warm_start_adj is not None),
            }
            out.append(G)
        return out
