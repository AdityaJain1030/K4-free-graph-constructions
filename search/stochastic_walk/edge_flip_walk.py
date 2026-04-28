"""
search/stochastic_walk/edge_flip_walk.py
=========================================
K4-free walk over the edge-flip moveset.

Move shape: (u, v, is_add) with u < v.
  - add  (is_add=True):  valid iff edge absent and adding stays K4-free.
  - remove (is_add=False): valid iff edge present.

The full moveset (n(n-1) tuples) is enumerated once at construction.
Proposal mode is determined by which hook is supplied at init:

  propose_fn               Raw proposals, no validity assumed. Walk rechecks
                           each via _validate_move (K4 check). No mask built.

  propose_from_valid_moves_fn
                           Caller receives the pre-filtered valid set at each
                           step. Mask is built and maintained incrementally.

  (neither)                Default: uniform sampling from the valid set.
                           Mask is built and maintained incrementally.
"""

from __future__ import annotations

import os
import sys
from typing import Callable

import networkx as nx
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from utils.graph_props import adding_induces_k4, get_neighborhood

from .walk import Walk

EdgeMove = tuple[int, int, bool]  # (u, v, is_add), u < v


class EdgeFlipWalk(Walk[EdgeMove]):
    """
    K4-free walk over single edge-flip (add/remove) moves.

    Proposal mode is chosen by which hook is supplied — see module docstring
    for the tradeoffs between propose_fn, propose_from_valid_moves_fn, and
    the default.

    Args:
        n:
            Number of vertices.
        stop_fn:
            Halt condition: (adj, info) -> bool.
            None → walk runs until max_steps or max_consecutive_failures.
        score_fn:
            Per-candidate score: (adj, u, v, is_add, info, context) -> float.
            None → uniform 0.0 for all moves.
        batch_score_fn:
            Batch scorer: (adj, moves, info) -> np.ndarray.
            Takes precedence over score_fn when set.
        propose_fn:
            Raw proposer: (adj, info, rng, k) -> list[(u, v, is_add)].
            Moves are not assumed valid — each is rechecked via _validate_move.
            No mask is built or maintained. Use when sampling from a custom
            distribution and invalid proposals can be discarded cheaply.
        propose_from_valid_moves_fn:
            Valid-set sampler: (adj, valid_moves, info, rng, k) -> list[(u, v, is_add)].
            Receives the pre-filtered valid moveset at each step, so the
            sample distribution support matches the valid moveset exactly.
            An incremental mask is built and maintained for this path.
            Moves are still rechecked. Ignored if propose_fn is set.
        beta:
            Softmax temperature over scores. float('inf') → greedy argmax.
        n_candidates:
            Number of proposals requested per step. None → walk decides
            (all valid moves for propose_from_valid_moves_fn; full moveset
            for the default path).
        num_trials:
            Independent walk restarts.
        seed:
            RNG base seed. Trial t uses seed*1000+t.
        max_steps:
            Hard ceiling on total steps per trial. None → no limit.
        max_consecutive_failures:
            Halt after this many consecutive failed steps. None → no limit.
        seed_graph:
            Starting graph (nx.Graph or np.ndarray). None → empty graph.
    """

    name = "edge_flip_walk"

    def __init__(
        self,
        n: int,
        *,
        stop_fn: Callable[[np.ndarray, dict], bool] | None = None,
        score_fn: Callable[..., float] | None = None,
        batch_score_fn: Callable[..., np.ndarray] | None = None,
        propose_fn: Callable[..., list] | None = None,
        propose_from_valid_moves_fn: Callable[..., list] | None = None,
        beta: float = 1.0,
        n_candidates: int | None = None,
        num_trials: int = 3,
        seed: int = 0,
        max_steps: int | None = 50_000,
        max_consecutive_failures: int | None = 500,
        seed_graph=None,
        **kwargs,
    ):
        super().__init__(
            n,
            score_fn_name=score_fn.__name__ if score_fn is not None else "uniform",
            stop_fn_name=stop_fn.__name__ if stop_fn is not None else "never",
            beta=beta,
            n_candidates=n_candidates,
            num_trials=num_trials,
            seed=seed,
            max_steps=max_steps,
            max_consecutive_failures=max_consecutive_failures,
            seed_graph=seed_graph,
            **kwargs,
        )
        self._stop_fn = stop_fn
        self._score_fn = score_fn
        self._batch_score_fn = batch_score_fn
        self._propose_fn = propose_fn
        self._propose_from_valid_moves_fn = propose_from_valid_moves_fn

        # Static moveset: all (u, v, is_add) with u < v, length n(n-1).
        # Layout: pair (u,v) → indices 2*pair_idx (add) and 2*pair_idx+1 (remove).
        self._all_moves: list[EdgeMove] = []
        self._move_idx: dict[EdgeMove, int] = {}
        for u in range(n):
            for v in range(u + 1, n):
                for is_add in (True, False):
                    self._move_idx[(u, v, is_add)] = len(self._all_moves)
                    self._all_moves.append((u, v, is_add))

        self._valid_mask: np.ndarray | None = None

    # ── mask helpers ──────────────────────────────────────────────────────────

    def _recompute_pair(self, adj: np.ndarray, u: int, v: int) -> None:
        """Recompute valid_mask entries for both (u,v,True) and (u,v,False)."""
        add_idx = self._move_idx[(u, v, True)]
        rem_idx = self._move_idx[(u, v, False)]
        if adj[u, v]:
            self._valid_mask[add_idx] = False
            self._valid_mask[rem_idx] = True
        else:
            self._valid_mask[add_idx] = not adding_induces_k4(adj, u, v)
            self._valid_mask[rem_idx] = False

    def _init_mask(self, adj: np.ndarray) -> None:
        """Build a fresh valid_mask from the current adjacency matrix."""
        self._valid_mask = np.zeros(len(self._all_moves), dtype=bool)
        for u in range(self.n):
            for v in range(u + 1, self.n):
                self._recompute_pair(adj, u, v)

    def _update_mask(self, adj: np.ndarray, a: int, b: int) -> None:
        """
        Incrementally update valid_mask after flipping edge (a, b).
        Only pairs with at least one endpoint in N(a) ∪ N(b) ∪ {a,b} need
        recomputation — the rest of the graph is unchanged.
        """
        interesting = (
            set(get_neighborhood(adj, a).tolist())
            | set(get_neighborhood(adj, b).tolist())
            | {a, b}
        )
        seen: set[tuple[int, int]] = set()
        for c in interesting:
            for w in range(self.n):
                if w == c:
                    continue
                u, v = (c, w) if c < w else (w, c)
                if (u, v) in seen:
                    continue
                seen.add((u, v))
                self._recompute_pair(adj, u, v)

    # ── Walk interface ────────────────────────────────────────────────────────

    def _initial_adj(self) -> np.ndarray:
        self._valid_mask = None
        return super()._initial_adj()

    def _propose(
        self,
        adj: np.ndarray,
        info: dict,
        rng: np.random.Generator,
        k: int | None,
    ) -> list[EdgeMove]:
        # propose_fn: raw proposer, no mask — Walk's _filter rechecks via _validate_move
        if self._propose_fn is not None:
            return self._propose_fn(adj, info, rng, k)

        # mask path: used for both propose_from_valid_moves_fn and default
        if self._valid_mask is None:
            self._init_mask(adj)
        valid_indices = np.where(self._valid_mask)[0]
        if len(valid_indices) == 0:
            return []
        valid_moves = [self._all_moves[i] for i in valid_indices]

        # propose_from_valid_moves_fn: caller samples from the valid set
        if self._propose_from_valid_moves_fn is not None:
            return self._propose_from_valid_moves_fn(adj, valid_moves, info, rng, k)

        # default: uniform sample of k from valid set
        if k is None or k >= len(valid_moves):
            return valid_moves
        chosen = rng.choice(len(valid_moves), size=k, replace=False)
        return [valid_moves[i] for i in chosen]

    def _validate_move(self, adj: np.ndarray, move: EdgeMove, info: dict, context: dict) -> bool:
        u, v, is_add = move
        if u > v:
            u, v = v, u
        if is_add:
            return not adj[u, v] and not adding_induces_k4(adj, u, v)
        return bool(adj[u, v])

    def _apply(self, adj: np.ndarray, move: EdgeMove) -> None:
        u, v, is_add = move
        if u > v:
            u, v = v, u
        adj[u, v] = adj[v, u] = int(is_add)
        if self._propose_fn is None:
            self._update_mask(adj, u, v)

    def _on_move(self, adj: np.ndarray, move: EdgeMove | None, accepted: bool, info: dict) -> None:
        if accepted and move is not None:
            _, _, is_add = move
            if is_add:
                info["added"] = info.get("added", 0) + 1
            else:
                info["removed"] = info.get("removed", 0) + 1

    def _stop(self, adj: np.ndarray, info: dict) -> bool:
        if self._stop_fn is None:
            return False
        return self._stop_fn(adj, info)

    def _score(self, adj: np.ndarray, move: EdgeMove, info: dict, context: dict) -> float:
        if self._score_fn is None:
            return 0.0
        u, v, is_add = move
        return float(self._score_fn(adj, u, v, is_add, info, context))

    def _score_batch(self, adj: np.ndarray, moves: list[EdgeMove], info: dict) -> np.ndarray:
        if self._batch_score_fn is not None:
            return np.asarray(self._batch_score_fn(adj, moves, info), dtype=np.float64)
        return super()._score_batch(adj, moves, info)
