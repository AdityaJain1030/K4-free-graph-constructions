"""
search/random_regular_switch.py
================================
Random near-regular K4-free construction + edge-switch hill-climb.

Probe 1 from the landscape study: for each target degree `d`, build a
random K4-free graph by uniform rejection sampling up to degree cap `d`,
then run `num_switches` rebalancing / alpha-reducing edge-switches to
polish it. Degree-preserving switches keep every vertex near `d` while
we try to push α(G) down.

Base-class scoring uses exact α (CP-SAT via alpha_cpsat, like
`graph_db.properties`). Inside the switch loop we use `alpha_approx`
because exact α per-step would dominate runtime — a 10–15% greedy α
ranking is fine for picking between candidate switches.
"""

import os
import random as _random
import sys

import networkx as nx
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.edge_switch import rebalancing_switch
from utils.graph_props import (
    alpha_approx,
    alpha_cpsat,
    is_k4_free,
)

from .base import Search


def _random_kfree_with_cap(n: int, d_cap: int, rng: _random.Random) -> np.ndarray:
    """Two-pass shuffled-greedy build toward d-regular (hard cap `d_cap`)."""
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


def _greedy_alpha_count(adj: np.ndarray, restarts: int) -> int:
    """Thin wrapper to keep the scoring signature local to this module."""
    return alpha_approx(adj, restarts=restarts)


class RandomRegularSwitchSearch(Search):
    """
    Random near-regular K4-free graph + edge-switch polish.

    Constraints
    -----------
    d : int | None
        Soft (cap/target). Per-trial target degree; if None, sweep a
        default list near the Turán density (d ≈ n^{2/3}).
    num_trials : int
        Independent random seeds per d. Default 8.
    num_switches : int
        Hill-climb iterations per trial. Default 200.
    switch_alpha_restarts : int
        Greedy-α restarts used to rank candidate switches. Default 64.
    seed : int
        Base RNG seed; trial t at degree d uses `seed*1000 + t*100 + d`.
    """

    name = "random_regular_switch"

    def __init__(
        self,
        n: int,
        *,
        top_k: int = 1,
        verbosity: int = 0,
        parent_logger=None,
        d: int | None = None,
        num_trials: int = 8,
        num_switches: int = 200,
        switch_alpha_restarts: int = 64,
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
            num_switches=num_switches,
            switch_alpha_restarts=switch_alpha_restarts,
            seed=seed,
            **kwargs,
        )

    def _default_degrees(self) -> list[int]:
        n = self.n
        target = max(3, round(n ** (2 / 3)))
        candidates = sorted({
            max(3, target - 2),
            max(3, target - 1),
            target,
            target + 1,
            target + 2,
        })
        return [d for d in candidates if d <= n - 1]

    def _polish(self, adj: np.ndarray, rng: _random.Random) -> tuple[np.ndarray, int]:
        """
        num_switches iterations of greedy hill-climb on greedy α.
        Accept a switch iff it does not increase the greedy α estimate
        and does not widen degree spread.
        """
        restarts = self.switch_alpha_restarts
        best_adj = adj.copy()
        best_alpha_est = _greedy_alpha_count(best_adj, restarts)
        d_best = best_adj.sum(axis=1)
        best_spread = int(d_best.max() - d_best.min())

        accepted = 0
        for _ in range(self.num_switches):
            cand = rebalancing_switch(best_adj, rng)
            if cand is None:
                continue
            d_cand = cand.sum(axis=1)
            spread = int(d_cand.max() - d_cand.min())
            if spread > best_spread:
                continue
            est = _greedy_alpha_count(cand, restarts)
            if est < best_alpha_est or (est == best_alpha_est and spread < best_spread):
                best_adj = cand
                best_alpha_est = est
                best_spread = spread
                accepted += 1
        return best_adj, accepted

    def _alpha_of(self, G: nx.Graph) -> tuple[int, list[int]]:
        """
        Override: the clique-cover B&B default can time out past n≈80 on
        the random-regular graphs this search produces. Use CP-SAT for
        every final scoring call, same choice as graph_db.properties.
        """
        adj = np.array(nx.to_numpy_array(G, dtype=np.uint8))
        return alpha_cpsat(adj, time_limit=60.0)

    def _run(self) -> list[nx.Graph]:
        degrees = [self.d] if self.d is not None else self._default_degrees()

        out: list[nx.Graph] = []
        n_attempts = 0
        for d in degrees:
            for trial in range(self.num_trials):
                rng = _random.Random(self.seed * 1000 + trial * 100 + d)
                adj = _random_kfree_with_cap(self.n, d, rng)
                n_attempts += 1
                if adj.sum() == 0:
                    continue
                polished, accepted = self._polish(adj, rng)
                G = nx.from_numpy_array(polished)
                self._stamp(G)
                degs = polished.sum(axis=1)
                G.graph["metadata"] = {
                    "d_target": int(d),
                    "d_min_final": int(degs.min()),
                    "d_max_final": int(degs.max()),
                    "trial": trial,
                    "seed": self.seed,
                    "num_switches": self.num_switches,
                    "switches_accepted": accepted,
                }
                out.append(G)
                self._log(
                    "trial",
                    level=1,
                    d_target=int(d),
                    trial=trial,
                    d_min=int(degs.min()),
                    d_max=int(degs.max()),
                    switches_accepted=accepted,
                )

        self._log("attempt", level=1, n_attempts=n_attempts, n_candidates=len(out))
        return out
