"""
search/algebraic_explicit/lex_blowup.py
========================================
Lex blow-up `seed[I_k]`: replace each vertex of `seed` with an
independent set of size k, and put a complete bipartite K_{k,k}
across every seed-edge.

Properties (for any K4-free `seed`):
  * N      = seed.order * k
  * α      = k * α(seed)        (each MIS vertex pulls in its full blob)
  * d_max  = k * d_max(seed)
  * K4-free preserved (a K4 in the product needs 4 distinct blobs ⇒ K4 in seed)
  * Bipartite iff `seed` is bipartite

Not competitive as a finished product — c_log strictly grows by a
factor of k·ln(d_max)/ln(k·d_max). Useful as a structured seed for
edge-switch polish.
"""

import os
import sys

import networkx as nx

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from utils.graph_props import is_k4_free_nx

from ..base import Search


def _relabel(G: nx.Graph) -> nx.Graph:
    """Relabel to 0..n-1 integer nodes (product ops return tuple nodes)."""
    mapping = {v: i for i, v in enumerate(sorted(G.nodes()))}
    H = nx.relabel_nodes(G, mapping)
    H.graph.clear()
    H.add_nodes_from(range(len(mapping)))
    return H


class LexBlowupSearch(Search):
    """
    Build seed[I_k] for an `nx.Graph` seed and integer k ≥ 2.

    Constraints
    -----------
    seed : nx.Graph
        Seed graph; produced graph has N = seed.order * k.
    k : int
        Required, ≥ 2. Size of the independent set each seed vertex is
        replaced by.
    seed_meta : dict | None
        Optional provenance dict; entries flow into the produced
        graph's metadata under the `seed_*` prefix. Pass-through.
    """

    name = "blowup"

    def __init__(
        self,
        *,
        top_k: int = 1,
        verbosity: int = 0,
        parent_logger=None,
        seed: nx.Graph,
        k: int,
        seed_meta: dict | None = None,
        **kwargs,
    ):
        if k is None or k < 2:
            raise ValueError("LexBlowupSearch requires k >= 2")
        n = seed.number_of_nodes() * k
        super().__init__(
            n,
            top_k=top_k,
            verbosity=verbosity,
            parent_logger=parent_logger,
            seed=seed,
            k=k,
            seed_meta=seed_meta or {},
            **kwargs,
        )

    def _run(self) -> list[nx.Graph]:
        Ik = nx.empty_graph(self.k)
        G = _relabel(nx.lexicographic_product(self.seed, Ik))

        self._stamp(G)
        k4_free = is_k4_free_nx(G)
        self._log(
            "lex_blowup",
            level=1,
            n_out=G.number_of_nodes(),
            m_out=G.number_of_edges(),
            is_k4_free=int(k4_free),
        )
        G.graph["metadata"] = {
            "mode": "lex",
            "k": self.k,
            **{f"seed_{key}": val for key, val in self.seed_meta.items()},
        }
        return [G]
