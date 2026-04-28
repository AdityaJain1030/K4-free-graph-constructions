"""
search/alpha_targeted.py
========================
Method 2: stochastic local search with α-targeting.

Start from a random near-regular K4-free graph (same construction as
RandomRegularSwitchSearch). Repeatedly:

    1. Compute a greedy MIS I.
    2. Propose an α-reducing move: pick u, v ∈ I, add edge uv, remove a
       compensating edge xy to keep the graph near-regular.
    3. Accept iff K4-free, degree spread ≤ cap, and greedy α strictly
       decreased.

Stop after `num_steps` total move attempts or `stall_cap` consecutive
failures. Final α is scored exactly by the base class (CP-SAT override,
same choice as RandomRegularSwitchSearch).
"""

import os
import random as _random
import sys

import networkx as nx
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from utils.alpha_targeted import alpha_approx_set, alpha_targeted_move
from utils.graph_props import alpha_cpsat, is_k4_free

from ..base import Search


def _random_kfree_with_cap(n: int, d_cap: int, rng: _random.Random) -> np.ndarray:
    """Two-pass shuffled-greedy build toward d-regular (hard cap `d_cap`).

    Duplicated from random_regular_switch to avoid coupling the two searches.
    """
    adj = np.zeros((n, n), dtype=np.uint8)
    degs = [0] * n
    pairs = [(u, v) for u in range(n) for v in range(u + 1, n)]
    rng.shuffle(pairs)
    for _pass in range(2):
        for u, v in pairs:
            if adj[u, v] or degs[u] >= d_cap or degs[v] >= d_cap:
                continue
            adj[u, v] = adj[v, u] = 1
            if is_k4_free(adj):
                degs[u] += 1
                degs[v] += 1
            else:
                adj[u, v] = adj[v, u] = 0
    return adj


class AlphaTargetedSearch(Search):
    """
    α-targeted local search on random near-regular K4-free graphs.

    Constraints
    -----------
    d : int | None
        Target degree (soft cap). If None, sweeps a small band near
        n^{2/3} (same default as RandomRegularSwitchSearch).
    num_trials : int
        Independent random seeds per d.
    num_steps : int
        Max α-reducing move attempts per trial.
    stall_cap : int
        Early-stop after this many consecutive failed moves.
    alpha_restarts : int
        Greedy-α restarts used inside the move proposer.
    pair_attempts, remove_attempts : int
        Per-step attempt budgets for `alpha_targeted_move`.
    max_degree_spread : int
        Hard cap on d_max − d_min (relaxed to initial spread if exceeded).
    seed : int
        Base RNG seed; trial t at degree d uses seed*1000 + t*100 + d.
    """

    name = "alpha_targeted"

    def __init__(
        self,
        n: int,
        *,
        top_k: int = 1,
        verbosity: int = 0,
        parent_logger=None,
        d: int | None = None,
        num_trials: int = 4,
        num_steps: int = 200,
        stall_cap: int = 30,
        alpha_restarts: int = 64,
        pair_attempts: int = 40,
        remove_attempts: int = 30,
        max_degree_spread: int = 2,
        seed: int = 0,
        **kwargs,
    ):
        super().__init__(
            n,
            top_k=top_k,
            verbosity=verbosity,
            parent_logger=parent_logger,
            d=d,
            num_trials=num_trials,
            num_steps=num_steps,
            stall_cap=stall_cap,
            alpha_restarts=alpha_restarts,
            pair_attempts=pair_attempts,
            remove_attempts=remove_attempts,
            max_degree_spread=max_degree_spread,
            seed=seed,
            **kwargs,
        )

    def _default_degrees(self) -> list[int]:
        n = self.n
        target = max(3, round(n ** (2 / 3)))
        band = sorted({
            max(3, target - 1),
            target,
            target + 1,
        })
        return [d for d in band if d <= n - 1]

    def _descend(
        self, adj: np.ndarray, rng: _random.Random,
    ) -> tuple[np.ndarray, int, dict]:
        """
        Greedy α-targeted descent. Returns (final_adj, n_accepted, trace_meta).
        """
        cur = adj.copy()
        alpha_cur, indep_cur = alpha_approx_set(
            cur, restarts=self.alpha_restarts, rng=rng,
        )
        initial_alpha = alpha_cur

        accepted = 0
        stalls = 0
        trajectory = [alpha_cur]
        for step in range(self.num_steps):
            move = alpha_targeted_move(
                cur, rng,
                alpha_restarts=self.alpha_restarts,
                pair_attempts=self.pair_attempts,
                remove_attempts=self.remove_attempts,
                max_degree_spread=self.max_degree_spread,
                known_indep=indep_cur,
                known_alpha=alpha_cur,
            )
            if move is None:
                stalls += 1
                if stalls >= self.stall_cap:
                    break
                continue
            stalls = 0
            cur, alpha_cur, indep_cur = move
            accepted += 1
            trajectory.append(alpha_cur)

        return cur, accepted, {
            "initial_alpha_approx": initial_alpha,
            "final_alpha_approx": alpha_cur,
            "alpha_trajectory": trajectory,
            "steps_taken": step + 1 if accepted or stalls else 0,
        }

    def _alpha_of(self, G: nx.Graph) -> tuple[int, list[int]]:
        """
        Exact α via CP-SAT; matches RandomRegularSwitchSearch so the two
        methods are comparable on the same scoring rule.
        """
        adj = np.array(nx.to_numpy_array(G, dtype=np.uint8))
        return alpha_cpsat(adj, time_limit=60.0)

    def _run(self) -> list[nx.Graph]:
        degrees = [self.d] if self.d is not None else self._default_degrees()

        out: list[nx.Graph] = []
        for d in degrees:
            for trial in range(self.num_trials):
                rng = _random.Random(self.seed * 1000 + trial * 100 + d)
                adj = _random_kfree_with_cap(self.n, d, rng)
                if adj.sum() == 0:
                    continue
                final, accepted, meta = self._descend(adj, rng)

                G = nx.from_numpy_array(final)
                self._stamp(G)
                degs = final.sum(axis=1)
                G.graph["metadata"] = {
                    "d_target": int(d),
                    "d_min_final": int(degs.min()),
                    "d_max_final": int(degs.max()),
                    "trial": trial,
                    "seed": self.seed,
                    "num_steps": self.num_steps,
                    "steps_accepted": accepted,
                    **meta,
                }
                out.append(G)
                self._log(
                    "trial",
                    level=1,
                    d_target=int(d),
                    trial=trial,
                    d_min=int(degs.min()),
                    d_max=int(degs.max()),
                    steps_accepted=accepted,
                    alpha_initial=meta["initial_alpha_approx"],
                    alpha_final=meta["final_alpha_approx"],
                )

        self._log("attempt", level=1, n_candidates=len(out))
        return out
