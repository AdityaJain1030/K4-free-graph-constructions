"""
search/tabu.py
================
Generic tabu search on boolean vectors.

Implements Parczyk et al. (arXiv:2206.04036) Algorithm 2 — at each
step pick the lowest-cost Hamming-1 neighbour whose flipped bit is
not in the tabu list. The tabu list stores the **last ℓ modified
bit indices**, not the last ℓ states, so membership testing is O(1)
and there is no need to hash or store full states.

The module is domain-agnostic: it takes a length `L`, a cost function
`cost(state: np.ndarray) -> float`, and runs. Cayley-graph search,
circulant search, or any other bitvector-parametrised search can plug
in by providing the cost.

Returns the best state seen plus a short trajectory so callers can
decide whether to continue, restart, or SAT-verify.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Callable

import numpy as np


@dataclass
class TabuResult:
    """Return value of `tabu_search`."""
    best_state: np.ndarray
    best_cost: float
    best_iter: int
    n_iters: int
    trajectory: list[float] = field(default_factory=list)


def tabu_search(
    *,
    L: int,
    cost: Callable[[np.ndarray], float],
    init_state: np.ndarray | None = None,
    n_iters: int = 1000,
    tabu_len: int | None = None,
    rng: np.random.Generator | None = None,
    record_every: int = 1,
    patience: int | None = None,
    time_limit_s: float | None = None,
) -> TabuResult:
    """
    Tabu search over {0,1}^L with Hamming-1 moves.

    Parameters
    ----------
    L : int
        Length of the boolean state vector.
    cost : callable
        cost(state) -> float. Lower is better. May return +inf for
        infeasible states.
    init_state : optional np.ndarray of dtype bool/uint8 and shape (L,)
        Starting state. Random if omitted.
    n_iters : int
        Number of tabu iterations to run.
    tabu_len : int, default L // 4
        Length of the modified-bits tabu list.
    rng : np.random.Generator, optional
        Source of randomness (used for init and tie-breaking).
    record_every : int
        Store current cost in `trajectory` every K iterations.
    patience : int, optional
        Early-stop if `best_cost` has not improved for this many
        iterations. None disables.
    time_limit_s : float, optional
        Wall-clock cap.

    Returns
    -------
    TabuResult
    """
    import time

    if tabu_len is None:
        tabu_len = max(1, L // 4)
    if rng is None:
        rng = np.random.default_rng()

    if init_state is None:
        # Sparse random init: pick 1-3 bits. Dense random starts (~L/2 bits)
        # tend to be K4-full for Cayley-graph cost functions, leaving every
        # Hamming-1 neighbour also K4-full and stalling the search.
        state = np.zeros(L, dtype=np.uint8)
        k0 = int(rng.integers(1, min(4, L) + 1))
        idx = rng.choice(L, size=k0, replace=False)
        state[idx] = 1
    else:
        state = np.asarray(init_state, dtype=np.uint8).copy()
        if state.shape != (L,):
            raise ValueError(f"init_state shape {state.shape} != ({L},)")

    best_state = state.copy()
    best_cost = cost(state)
    best_iter = 0

    tabu: deque[int] = deque(maxlen=tabu_len)
    trajectory: list[float] = [best_cost]

    start = time.monotonic()
    since_improve = 0

    for it in range(1, n_iters + 1):
        if time_limit_s is not None and (time.monotonic() - start) > time_limit_s:
            break

        allowed = [b for b in range(L) if b not in tabu]
        if not allowed:
            tabu.clear()
            allowed = list(range(L))

        # Find the lowest-cost neighbour over allowed flips.
        # Evaluate cost(flip(state, b)) for each b; break ties randomly.
        best_b = -1
        best_b_cost = np.inf
        rng.shuffle(allowed)
        for b in allowed:
            state[b] ^= 1
            c = cost(state)
            state[b] ^= 1
            if c < best_b_cost:
                best_b_cost = c
                best_b = b

        if best_b < 0:
            # All allowed flips are +inf (infeasible). Take a random kick
            # so the search doesn't freeze in an infeasible pocket.
            best_b = int(rng.choice(allowed))
            best_b_cost = np.inf

        state[best_b] ^= 1
        tabu.append(best_b)
        cur_cost = best_b_cost

        if cur_cost < best_cost:
            best_cost = cur_cost
            best_state = state.copy()
            best_iter = it
            since_improve = 0
        else:
            since_improve += 1

        if it % record_every == 0:
            trajectory.append(cur_cost)

        if patience is not None and since_improve >= patience:
            break

    return TabuResult(
        best_state=best_state,
        best_cost=best_cost,
        best_iter=best_iter,
        n_iters=it,
        trajectory=trajectory,
    )


def multi_restart_tabu(
    *,
    L: int,
    cost: Callable[[np.ndarray], float],
    n_restarts: int = 4,
    n_iters: int = 1000,
    tabu_len: int | None = None,
    rng: np.random.Generator | None = None,
    time_limit_s: float | None = None,
    **kwargs,
) -> TabuResult:
    """
    Run `n_restarts` independent tabu searches from random starts,
    return the best. Wall-clock is shared across restarts via
    `time_limit_s` (soft).
    """
    import time

    if rng is None:
        rng = np.random.default_rng()

    start = time.monotonic()
    best: TabuResult | None = None
    for r in range(n_restarts):
        remaining = None
        if time_limit_s is not None:
            remaining = max(0.0, time_limit_s - (time.monotonic() - start))
            if remaining <= 0:
                break
        res = tabu_search(
            L=L,
            cost=cost,
            n_iters=n_iters,
            tabu_len=tabu_len,
            rng=rng,
            time_limit_s=remaining,
            **kwargs,
        )
        if best is None or res.best_cost < best.best_cost:
            best = res
    assert best is not None
    return best
