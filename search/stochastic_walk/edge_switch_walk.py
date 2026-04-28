"""
search/stochastic_walk/edge_switch_walk.py
==========================================
K4-free walk over the 2-switch (degree-preserving) moveset, built on Walk.

Move shape: (a, b, c, d, rewiring) where
  - (a, b) and (c, d) are two disjoint existing edges with a < b, c < d
  - {a, b, c, d} are four distinct vertices
  - rewiring ∈ {"ac_bd", "ad_bc"}

Application:
  ac_bd:  remove (a,b),(c,d); add (a,c),(b,d)
  ad_bc:  remove (a,b),(c,d); add (a,d),(b,c)

Every vertex's degree is preserved.

seed_graph is REQUIRED — degree-preserving switches need edges to switch.
Use EdgeFlipWalk first to build a seed graph, then hand it here.

Proposal
--------
The default _propose generates all disjoint edge pairs × 2 rewirings (O(m²),
no K4 check). _validate_move then filters out collisions and K4-creating
switches. Set n_candidates to limit how many raw pairs are sampled per step —
only those k are K4-checked, keeping the per-step cost at O(k × K4-check)
instead of O(m²). A custom propose_fn follows the same contract.

score_fn signature
------------------
score_fn(adj, move, info, context) -> float
  adj      — current adjacency (pre-move)
  move     — (a, b, c, d, rewiring) 5-tuple
  info     — live info dict
  context  — per-step cache dict, reset to {} each step
"""

from __future__ import annotations

import os
import sys
from typing import Callable

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from utils.graph_props import find_k4

from .walk import Walk

SwitchMove = tuple[int, int, int, int, str]  # (a, b, c, d, rewiring)


def _switch_is_valid(adj: np.ndarray, a: int, b: int, c: int, d: int,
                     rewiring: str) -> bool:
    """
    Mutate-and-restore K4 check. Returns True iff the switch is K4-safe.

    Accepts edge+non-edge pairs: removing a non-edge is a no-op, so the
    switch becomes a degree-non-preserving move (net +1 for c and d). This
    is intentional — the walk does not enforce degree preservation.

    Rejects non-edge+non-edge: no edges are removed, so both new edges are
    just added outright. This is not a switch at all.

    Restores adj exactly regardless of which inputs were edges or non-edges.
    """
    if rewiring == "ad_bc":
        c, d = d, c
    elif rewiring != "ac_bd":
        return False
    old_ab = int(adj[a, b])
    old_cd = int(adj[c, d])
    if not old_ab and not old_cd:
        return False  # non-edge + non-edge: not a real switch
    if adj[a, c] or adj[b, d]:
        return False
    adj[a, b] = adj[b, a] = 0
    adj[c, d] = adj[d, c] = 0
    adj[a, c] = adj[c, a] = 1
    adj[b, d] = adj[d, b] = 1
    safe = find_k4(adj) is None
    adj[a, c] = adj[c, a] = 0
    adj[b, d] = adj[d, b] = 0
    adj[a, b] = adj[b, a] = old_ab
    adj[c, d] = adj[d, c] = old_cd
    return safe


class EdgeSwitchWalk(Walk[SwitchMove]):
    """
    K4-free walk over the 2-switch (degree-preserving) moveset.

    Args:
        n:
            Number of vertices.
        seed_graph:
            Required starting graph (nx.Graph or np.ndarray). Must have
            edges — empty graphs have no switches available.
        stop_fn:
            Halt condition: (adj, info) -> bool.
            None → walk runs until max_steps or max_consecutive_failures.
        score_fn:
            Per-candidate score: (adj, move, info, context) -> float.
            move is the full (a, b, c, d, rewiring) 5-tuple.
            None → uniform 0.0 for all moves.
        batch_score_fn:
            Batch scorer: (adj, moves, info) -> np.ndarray.
            Takes precedence over score_fn when set.
        propose_fn:
            Raw proposer: (adj, info, rng, k) -> list[SwitchMove].
            Proposals need not be valid — each is checked via _validate_move.
            None → default: enumerate all valid switches each step, then
            uniform-sample k from them (or return all if k is None).
        beta:
            Softmax temperature. float('inf') → greedy argmax.
        n_candidates:
            Number of proposals per step. None → all valid switches.
        num_trials:
            Independent walk restarts.
        seed:
            RNG base seed. Trial t uses seed*1000+t.
        max_steps:
            Hard ceiling on total steps per trial. None → no limit.
        max_consecutive_failures:
            Halt after this many consecutive failed steps. None → no limit.
    """

    name = "edge_switch_walk"

    def __init__(
        self,
        n: int,
        *,
        seed_graph,
        stop_fn: Callable[[np.ndarray, dict], bool] | None = None,
        score_fn: Callable[..., float] | None = None,
        batch_score_fn: Callable[..., np.ndarray] | None = None,
        propose_fn: Callable[..., list] | None = None,
        beta: float = 1.0,
        n_candidates: int | None = None,
        num_trials: int = 3,
        seed: int = 0,
        max_steps: int | None = 50_000,
        max_consecutive_failures: int | None = 500,
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

    # ── Walk interface ────────────────────────────────────────────────────────

    def _propose(
        self,
        adj: np.ndarray,
        info: dict,
        rng: np.random.Generator,
        k: int | None,
    ) -> list[SwitchMove]:
        if self._propose_fn is not None:
            return self._propose_fn(adj, info, rng, k)

        # Build all disjoint edge pairs × 2 rewirings — no K4 check here.
        # _validate_move filters out anything that creates a K4 or collides.
        edges: list[tuple[int, int]] = [
            (i, j) for i in range(self.n) for j in range(i + 1, self.n) if adj[i, j]
        ]
        m = len(edges)
        if m < 2:
            return []
        candidates: list[SwitchMove] = []
        for i in range(m):
            a, b = edges[i]
            for j in range(i + 1, m):
                c, d = edges[j]
                if a == c or a == d or b == c or b == d:
                    continue
                candidates.append((a, b, c, d, "ac_bd"))
                candidates.append((a, b, c, d, "ad_bc"))

        if not candidates:
            return []
        if k is None or k >= len(candidates):
            return candidates
        chosen = rng.choice(len(candidates), size=k, replace=False)
        return [candidates[i] for i in chosen]

    def _validate_move(
        self, adj: np.ndarray, move: SwitchMove, info: dict, context: dict
    ) -> bool:
        a, b, c, d, rewiring = move
        return _switch_is_valid(adj, a, b, c, d, rewiring)

    def _apply(self, adj: np.ndarray, move: SwitchMove) -> None:
        a, b, c, d, rewiring = move
        if rewiring == "ad_bc":
            c, d = d, c
        adj[a, b] = adj[b, a] = 0
        adj[c, d] = adj[d, c] = 0
        adj[a, c] = adj[c, a] = 1
        adj[b, d] = adj[d, b] = 1

    def _stop(self, adj: np.ndarray, info: dict) -> bool:
        if self._stop_fn is None:
            return False
        return self._stop_fn(adj, info)

    def _score(
        self, adj: np.ndarray, move: SwitchMove, info: dict, context: dict
    ) -> float:
        if self._score_fn is None:
            return 0.0
        return float(self._score_fn(adj, move, info, context))

    def _score_batch(
        self, adj: np.ndarray, moves: list[SwitchMove], info: dict
    ) -> np.ndarray:
        if self._batch_score_fn is not None:
            return np.asarray(self._batch_score_fn(adj, moves, info), dtype=np.float64)
        return super()._score_batch(adj, moves, info)

    def _on_move(
        self,
        adj: np.ndarray,
        move: SwitchMove | None,
        accepted: bool,
        info: dict,
    ) -> None:
        if accepted:
            info["switches"] = info.get("switches", 0) + 1
