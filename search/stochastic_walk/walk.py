"""
search/stochastic_walk/walk.py
================================
Abstract base class for stochastic walks over K4-free graphs.

A Walk is a Search that advances by repeatedly proposing, validating,
scoring, and applying moves to a graph state (adjacency matrix).
Subclasses define:

  1. The move shape  — by subclassing Walk[MoveT]
  2. _propose        — generate candidate moves (may include invalid ones)
  3. _validate_move  — whether a single candidate is legal right now
  4. _score          — per-candidate score (required)
  5. _apply          — apply a move to adj in-place

Everything else — filtering, softmax selection, termination,
multi-trial loop — is shared here.

Subclass contract
-----------------

    EdgeMove = tuple[int, int, bool]   # (u, v, is_add)

    class MyWalkSearch(Walk[EdgeMove]):
        name = "my_walk"

        def __init__(self, n, *, target_edges, beta=2.0, **kwargs):
            super().__init__(n, **kwargs)
            self.beta = beta          # override Walk default
            self._target = target_edges

        def _stop(self, adj, info) -> bool:
            return info["edges"] >= self._target

        def _propose(self, adj, info, rng, k) -> list[EdgeMove]:
            ...

        def _score(self, adj, move, info, context) -> float:
            ...

        def _apply(self, adj, move: EdgeMove) -> None:
            ...

Propose / validate separation
------------------------------
_propose is responsible for generating candidates — it may return moves
that turn out to be invalid (e.g. random proposals that land on existing
edges, or switches that create K4). _validate_move is responsible for
filtering them. This separation lets proposers be cheap and dumb (just
sample from the candidate space) while validity logic lives in one place.

_validate_move has a batch analogue (_validate_move_batch) for when
validating all candidates at once is cheaper than one-by-one (e.g.
vectorised K4 checks). If _validate_move_batch is overridden it takes
precedence. If neither is overridden, all proposals are accepted.

context
-------
Both _validate_move and _score receive a `context` dict that is reset
to {} once per step and shared across all per-candidate calls within
that step. Use it to cache work that is the same for every candidate
(e.g. the current neighbourhood structure, the current α). For batch
variants no context is needed — a batch call is one-shot per step.

Walk knobs
----------
All knobs have sensible defaults on Walk. Subclasses may expose any
subset as __init__ parameters and override the defaults after calling
super().__init__().

beta                    float     Softmax temperature. inf → greedy argmax.
                                  Default 1.0.
n_candidates            int|None  k passed to _propose each step.
                                  None → walk decides. Default None.
num_trials              int       Independent walk restarts. Default 3.
seed                    int       Trial t uses seed*1000+t. Default 0.
max_steps               int|None  Hard ceiling on steps per trial.
                                  None → no limit. Default 50_000.
max_consecutive_failures int|None Hard ceiling on consecutive failed steps.
                                  None → no limit. Default 500.

seed_graph is not a Walk-level knob. Subclasses that need a starting graph
should expose it as their own __init__ parameter and call
self._load_seed_graph(seed_graph) to set self._seed_adj.

Termination
-----------
The walk terminates when the FIRST of these fires:

  1. _stop(adj, info) returns True            → info["stopped"] = True
  2. max_consecutive_failures consecutive     → info["saturated"] = True
     failed steps
  3. max_steps steps taken                    → info["max_steps_reached"] = True

info keys available in _stop:

    info["consecutive_failures"]  — steps since last accepted move
    info["total_failures"]        — total failed steps in this trial
    info["steps"]                 — total steps (accepted + failed)
    info["accepted"]              — total accepted moves
"""

from __future__ import annotations

import os
import sys
from abc import abstractmethod
from typing import Generic, TypeVar

import networkx as nx
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from ..base import Search

MoveT = TypeVar("MoveT")


def _select(scores: np.ndarray, beta: float,
            rng: np.random.Generator) -> int | None:
    """
    Softmax index selection over `scores`. Returns None if no finite
    score exists.

    beta=inf  → greedy argmax; ties broken uniformly via rng.
    beta<inf  → softmax weights; -inf scores are excluded.
    """
    finite = np.isfinite(scores)
    if not finite.any():
        return None
    if np.isinf(beta) and beta > 0:
        best = scores[finite].max()
        tied = np.where(np.isclose(scores, best))[0]
        return int(rng.choice(tied))
    logits = beta * scores
    logits[~finite] = float("-inf")
    logits -= logits[finite].max()
    weights = np.exp(logits)
    weights[~finite] = 0.0
    total = weights.sum()
    if total <= 0.0:
        return None
    return int(rng.choice(len(scores), p=weights / total))


class Walk(Search, Generic[MoveT]):
    """
    Abstract stochastic walk. Subclass with Walk[YourMoveType].

    Abstract methods  (must implement both)
    ----------------
    _propose(adj, info, rng, k) -> list[MoveT]
        Generate up to k candidate moves. May include invalid ones —
        _validate_move / _validate_move_batch will filter them.

    _apply(adj, move) -> None
        Apply move to adj in-place. Only called on the selected move.

    Overridable with defaults
    -------------------------
    _stop(adj, info) -> bool
        Return True to halt the walk. Default: never stop (rely on
        max_steps / max_consecutive_failures).

    _validate_move(adj, move, info, context) -> bool
        Return True iff move is legal. Default: True (trust proposer).

    _validate_move_batch(adj, moves, info) -> np.ndarray[bool]
        Validate all candidates at once. Default: delegates to
        _validate_move with a shared context dict.

    _score(adj, move, info, context) -> float
        Per-candidate score. Default: 0.0 (uniform). Override this OR
        _score_batch — at least one should be non-default.

    _score_batch(adj, moves, info) -> np.ndarray
        Batch score all candidates. Default: delegates to _score.
        Takes precedence over _score when overridden.
    """

    def __init__(
        self,
        n: int,
        *,
        score_fn_name: str,
        stop_fn_name: str,
        beta: float = 1.0,
        n_candidates: int | None = None,
        num_trials: int = 3,
        seed: int = 0,
        max_steps: int | None = 50_000,
        max_consecutive_failures: int | None = 500,
        seed_graph: "nx.Graph | np.ndarray | None" = None,
        **kwargs,
    ):
        """
        Args:
            n:                        Number of vertices.
            score_fn_name:            Human-readable name for the scoring logic.
                                      Logged in search_start. Required — subclasses
                                      hardcode or re-expose as they see fit.
            stop_fn_name:             Human-readable name for the stopping logic.
                                      Logged in search_start. Required — same pattern.
            beta:                     Softmax temperature over candidate scores.
                                      float('inf') → greedy argmax with uniform tie-breaking.
            n_candidates:             Number of proposals requested from _propose per step.
                                      None → walk decides (e.g. enumerate all valid moves).
            num_trials:               Number of independent walk restarts.
            seed:                     RNG base seed. Trial t uses seed*1000+t.
            max_steps:                Hard ceiling on total steps per trial.
                                      None → no limit.
            max_consecutive_failures: Halt after this many consecutive failed steps
                                      (steps where no move was applied).
                                      None → no limit.
            seed_graph:               Starting adjacency matrix or graph. None → empty graph.
        """
        super().__init__(
            n,
            score_fn_name=score_fn_name,
            stop_fn_name=stop_fn_name,
            beta=beta,
            n_candidates=n_candidates,
            num_trials=num_trials,
            seed=seed,
            max_steps=max_steps,
            max_consecutive_failures=max_consecutive_failures,
            **kwargs,
        )
        if seed_graph is None:
            self._seed_adj: np.ndarray | None = None
        elif isinstance(seed_graph, np.ndarray):
            self._seed_adj = seed_graph.astype(np.uint8).copy()
        else:
            self._seed_adj = np.array(nx.to_numpy_array(seed_graph), dtype=np.uint8)

    # ── subclass contract ─────────────────────────────────────────────────────

    @abstractmethod
    def _propose(
        self,
        adj: np.ndarray,
        info: dict,
        rng: np.random.Generator,
        k: int | None,
    ) -> list[MoveT]:
        """
        Generate up to k candidate moves. May return invalid moves —
        the framework filters them via _validate_move[_batch].

        k=None  → no budget; walk decides how many to propose.
        k=int   → propose at most k candidates.
        []      → no candidates this step (counts as a failure).
        """

    @abstractmethod
    def _apply(self, adj: np.ndarray, move: MoveT) -> None:
        """Apply move to adj in-place. Only called on the selected move."""

    # ── overridable with defaults ─────────────────────────────────────────────

    def _stop(self, adj: np.ndarray, info: dict) -> bool:
        """
        Return True to halt the walk. Called at the start of each step.
        Default: never stop (walk runs until max_steps or
        max_consecutive_failures is hit).
        """
        return False

    def _on_move(
        self,
        adj: np.ndarray,
        move: MoveT | None,
        accepted: bool,
        info: dict,
    ) -> None:
        """
        Called after every step attempt, after info has been updated.

        adj      — current adjacency (post-move if accepted, unchanged if not)
        move     — the move that was selected, or None if no move was produced
        accepted — True if the move was applied via _apply
        info     — the live info dict (not a copy — mutations persist)

        Default: no-op. Override to inject extra fields into info, track
        per-step statistics, or emit debug output.
        """

    def _validate_move(
        self,
        adj: np.ndarray,
        move: MoveT,
        info: dict,
        context: dict,
    ) -> bool:
        """
        Return True iff move is valid in the current state.

        `context` is reset to {} once per step and shared across all
        per-candidate calls — cache expensive shared work here.

        Default: True (proposer is trusted to return only valid moves).
        Override when _propose may return invalid candidates.
        """
        return True

    def _validate_move_batch(
        self,
        adj: np.ndarray,
        moves: list[MoveT],
        info: dict,
    ) -> np.ndarray:
        """
        Validate all candidates at once. Returns a bool array of length
        len(moves). Overrides _validate_move when defined.

        Default: delegates to per-candidate _validate_move with a shared
        context dict.
        """
        context: dict = {}
        return np.array(
            [self._validate_move(adj, m, info, context) for m in moves],
            dtype=bool,
        )

    def _score(
        self,
        adj: np.ndarray,
        move: MoveT,
        info: dict,
        context: dict,
    ) -> float:
        """
        Score a single candidate move. Higher is better. Return float('-inf')
        to exclude a candidate from selection.

        `context` is reset to {} once per step and shared across all
        per-candidate calls — cache expensive shared work here.

        Default: 0.0 (uniform selection). Override this OR _score_batch —
        at least one should be overridden. _score_batch takes precedence
        when overridden.
        """
        return 0.0

    def _score_batch(
        self,
        adj: np.ndarray,
        moves: list[MoveT],
        info: dict,
    ) -> np.ndarray:
        """
        Score all candidates at once. Returns a float64 array of length
        len(moves).

        Default: delegates to per-candidate _score with a shared context dict.
        Override for vectorised scoring — takes precedence over _score when
        overridden.
        """
        context: dict = {}
        scores = np.empty(len(moves), dtype=np.float64)
        for i, move in enumerate(moves):
            scores[i] = float(self._score(adj, move, info, context))
        return scores

    # ── shared walk machinery ─────────────────────────────────────────────────

    def _initial_adj(self) -> np.ndarray:
        if self._seed_adj is not None:
            return self._seed_adj.copy()
        return np.zeros((self.n, self.n), dtype=np.uint8)

    def _filter(
        self, adj: np.ndarray, candidates: list[MoveT], info: dict
    ) -> list[MoveT]:
        """Filter candidates through _validate_move_batch."""
        if not candidates:
            return []
        mask = self._validate_move_batch(adj, candidates, info)
        return [m for m, ok in zip(candidates, mask) if ok]

    def _compute_scores(
        self, adj: np.ndarray, candidates: list[MoveT], info: dict
    ) -> np.ndarray:
        """Score candidates via _score_batch (which defaults to per-candidate _score)."""
        return np.asarray(self._score_batch(adj, candidates, info), dtype=np.float64)

    def _step(
        self, adj: np.ndarray, rng: np.random.Generator, info: dict
    ) -> tuple[bool, MoveT | None]:
        """
        One walk step: propose → validate → score → select → apply.
        Returns (executed, move). executed=False means no move was made.
        """
        candidates = self._propose(adj, info, rng, self.n_candidates)
        if not candidates:
            return False, None

        valid = self._filter(adj, candidates, info)
        if not valid:
            return False, None

        scores = self._compute_scores(adj, valid, info)
        idx = _select(scores, self.beta, rng)
        if idx is None:
            return False, None

        move = valid[idx]
        self._apply(adj, move)
        return True, move

    def _run_one_walk(
        self, rng: np.random.Generator
    ) -> tuple[np.ndarray, dict]:
        adj = self._initial_adj()
        info: dict = {
            "steps": 0,
            "accepted": 0,
            "total_failures": 0,
            "consecutive_failures": 0,
            "stopped": False,
            "saturated": False,
            "max_steps_reached": False,
        }

        step = 0
        while True:
            if self.max_steps is not None and step >= self.max_steps:
                info["max_steps_reached"] = True
                return adj, info

            if self._stop(adj, info):
                info["stopped"] = True
                return adj, info

            executed, move = self._step(adj, rng, info)
            info["steps"] += 1
            step += 1

            if not executed:
                info["total_failures"] += 1
                info["consecutive_failures"] += 1
            else:
                info["consecutive_failures"] = 0
                info["accepted"] += 1

            self._on_move(adj, move, executed, info)

            if not executed and (
                self.max_consecutive_failures is not None
                and info["consecutive_failures"] >= self.max_consecutive_failures
            ):
                info["saturated"] = True
                return adj, info

    def _run(self) -> list[nx.Graph]:
        out: list[nx.Graph] = []
        for trial in range(self.num_trials):
            rng = np.random.default_rng(self.seed * 1000 + trial)
            adj, info = self._run_one_walk(rng)
            G = nx.from_numpy_array(adj)
            self._stamp(G)
            G.graph["metadata"] = {
                "trial": trial,
                "seed": self.seed,
                "edges": int(adj.sum()) // 2,
                **info,  # includes base keys + anything injected via _on_move
            }
            out.append(G)
            self._log(
                "trial", level=1,
                trial=trial,
                edges=int(adj.sum()) // 2,
                stopped=info["stopped"],
                saturated=info["saturated"],
                max_steps_reached=info["max_steps_reached"],
                accepted=info["accepted"],
                steps=info["steps"],
                total_failures=info["total_failures"],
            )
        return out
