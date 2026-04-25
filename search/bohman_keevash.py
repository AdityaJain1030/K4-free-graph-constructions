"""
search/bohman_keevash.py
========================
Bohman-Keevash random K4-free process.

Start with the empty graph on n vertices. At each step, pick a pair (u, v)
uniformly at random from the set of currently *open* pairs — pairs whose
addition does not create a K4 — and add it. Stop when no open pair remains
(K4-saturated).

Adding edge u-v creates a K4 iff there exist w1, w2 with all of
u-w1, u-w2, v-w1, v-w2, w1-w2. Equivalently: the induced subgraph on
N(u) ∩ N(v) contains an edge. That is the criterion this implementation
maintains incrementally.

Bohman-Keevash (2010+) showed this process produces a K4-free graph with
m = N^(8/5+o(1)) edges and α = O(N^(3/5) log^(8/5) N), which is
tight asymptotically against the conjectured c_log scaling. Constants
are not asymptotic; finite-N c_log of B-K outputs is the empirical
question this search lets you measure.
"""

import os
import random as _random
import sys

import networkx as nx
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from .base import Search


class BohmanKeevashSearch(Search):
    """
    Bohman-Keevash random K4-free saturation process.

    Constraints
    -----------
    num_trials : int
        Independent random runs. Default 5.
    seed : int
        Base RNG seed; trial t uses seed*1000 + t.
    """

    name = "bohman_keevash"

    def __init__(
        self,
        n: int,
        *,
        top_k: int = 1,
        verbosity: int = 0,
        parent_logger=None,
        num_trials: int = 5,
        seed: int = 0,
        **kwargs,
    ):
        super().__init__(
            n,
            top_k=top_k,
            verbosity=verbosity,
            parent_logger=parent_logger,
            num_trials=num_trials,
            seed=seed,
            **kwargs,
        )

    def _build_one(self, rng: _random.Random) -> nx.Graph:
        n = self.n
        nbr: list[set[int]] = [set() for _ in range(n)]

        # Open pair structure: O(1) sample + remove.
        cand_list: list[tuple[int, int]] = []
        cand_idx: dict[tuple[int, int], int] = {}
        for u in range(n):
            for v in range(u + 1, n):
                p = (u, v)
                cand_idx[p] = len(cand_list)
                cand_list.append(p)

        def _drop(p: tuple[int, int]) -> None:
            i = cand_idx.pop(p, None)
            if i is None:
                return
            last = cand_list.pop()
            if i < len(cand_list):
                cand_list[i] = last
                cand_idx[last] = i

        steps = 0
        while cand_list:
            (u, v) = cand_list[rng.randrange(len(cand_list))]
            _drop((u, v))
            nbr[u].add(v)
            nbr[v].add(u)
            steps += 1

            common_uv = nbr[u] & nbr[v]
            # case 1: pairs (a,b) with a,b in N(u) ∩ N(v) — new edge u-v
            # is now inside their common neighborhood → close them.
            if common_uv:
                cu = sorted(common_uv)
                for i in range(len(cu)):
                    a = cu[i]
                    for j in range(i + 1, len(cu)):
                        b = cu[j]
                        _drop((a, b))

            # case 2: pairs (u, w) where w ∈ N(v), w ≠ u, (u,w) not in G:
            # v is now a new common neighbor of u and w. The induced
            # subgraph on N(u) ∩ N(w) gains an edge iff there is some
            # x ∈ N(u) ∩ N(v) ∩ N(w) (since (v,x) ∈ E for x ∈ N(v)).
            for w in nbr[v]:
                if w == u or w in nbr[u]:
                    continue
                p = (u, w) if u < w else (w, u)
                if p not in cand_idx:
                    continue
                if common_uv & nbr[w]:
                    _drop(p)

            # case 3: symmetric — pairs (v, w) where w ∈ N(u), w ≠ v.
            for w in nbr[u]:
                if w == v or w in nbr[v]:
                    continue
                p = (v, w) if v < w else (w, v)
                if p not in cand_idx:
                    continue
                if common_uv & nbr[w]:
                    _drop(p)

        G = nx.Graph()
        G.add_nodes_from(range(n))
        for u in range(n):
            for v in nbr[u]:
                if u < v:
                    G.add_edge(u, v)
        G.graph["metadata"] = {"steps": steps}
        return G

    def _run(self) -> list[nx.Graph]:
        out: list[nx.Graph] = []
        for trial in range(self.num_trials):
            rng = _random.Random(self.seed * 1000 + trial)
            G = self._build_one(rng)
            self._stamp(G)
            md = dict(G.graph.get("metadata", {}))
            md.update({"trial": trial, "seed": self.seed})
            G.graph["metadata"] = md
            out.append(G)
            self._log(
                "trial_done",
                level=1,
                trial=trial,
                m=G.number_of_edges(),
                d_max=max((d for _, d in G.degree()), default=0),
            )
        return out
