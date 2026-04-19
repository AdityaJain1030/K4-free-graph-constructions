"""
search/random.py
==================
Random K4-free graph construction with a degree cap.

Ported from the `method1` baseline in
`funsearch/experiments/baselines/run_baselines.py`. Shuffles every pair,
tries to add each edge if both endpoints are below `d_max` and the add
stays K4-free. Two passes (a pair skipped due to the cap in pass 1 may
become addable later). Multiple independent trials; base class picks
the top_k by c_log across every candidate.
"""

import os
import random as _random
import sys

import networkx as nx
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.graph_props import is_k4_free

from .base import Search


_DEFAULT_CAPS = (3, 4, 5, 6, 8, 10, 12, 15, 20)


def _default_cap_sweep(n: int) -> list[int]:
    cap = min(20, max(3, n // 2))
    return [d for d in _DEFAULT_CAPS if d <= cap and d <= n - 1]


class RandomSearch(Search):
    """
    Random edge addition with degree cap and K4-free check.

    Constraints
    -----------
    d_max : int | None
        Soft (cap, not target). If set, every construction uses this as
        the per-vertex degree cap. If None, sweep a default list of caps
        and return candidates from each; the base class keeps the top_k
        by c_log.
    num_trials : int
        Independent random shuffles per cap. Default 3.
    seed : int
        Base RNG seed; trial t at cap d uses `seed*1000 + t*100 + d`.
    """

    name = "random"

    def __init__(
        self,
        n: int,
        *,
        top_k: int = 1,
        verbosity: int = 0,
        parent_logger=None,
        d_max: int | None = None,
        num_trials: int = 3,
        seed: int = 0,
        **kwargs,
    ):
        super().__init__(
            n,
            top_k=top_k,
            verbosity=verbosity,
            parent_logger=parent_logger,
            d_max=d_max,
            num_trials=num_trials,
            seed=seed,
            **kwargs,
        )

    def _build_one(self, d_cap: int, rng: _random.Random) -> np.ndarray:
        n = self.n
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

    def _run(self) -> list[nx.Graph]:
        caps = [self.d_max] if self.d_max is not None else _default_cap_sweep(self.n)

        out: list[nx.Graph] = []
        n_attempts = 0
        for d_cap in caps:
            for trial in range(self.num_trials):
                rng = _random.Random(self.seed * 1000 + trial * 100 + d_cap)
                adj = self._build_one(d_cap, rng)
                n_attempts += 1
                if adj.sum() == 0:
                    continue
                G = nx.from_numpy_array(adj)
                self._stamp(G)
                G.graph["metadata"] = {
                    "d_cap": d_cap,
                    "trial": trial,
                    "seed": self.seed,
                }
                out.append(G)

        self._log("attempt", level=1, n_attempts=n_attempts, n_candidates=len(out))
        return out
