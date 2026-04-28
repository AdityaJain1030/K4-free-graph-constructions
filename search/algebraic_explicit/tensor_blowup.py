"""
search/algebraic_explicit/tensor_blowup.py
===========================================
Tensor (categorical / Kronecker) product `seed × other`:
  (u₁, v₁) ~ (u₂, v₂)  iff  u₁ ~_seed u₂  AND  v₁ ~_other v₂

Properties:
  * N      = seed.order * other.order
  * d_max  = d_max(seed) * d_max(other)        (degrees multiply)
  * α      ≥ max(α(seed)*other.order, α(other)*seed.order)
  * K4-free preserved if either factor is K4-free (the projection of a
    K4 to that factor must be a K4 itself, since two product vertices
    sharing a coordinate are non-adjacent)
  * Bipartite iff at least one factor is bipartite
  * Connected iff both factors are connected and at least one has an
    odd cycle (Weichsel's theorem)
  * Spectrum: eigenvalues of A(seed × other) are products λ_i(seed)·μ_j(other)

The two factors are interchangeable up to isomorphism (`seed × other`
≅ `other × seed`). The `seed` / `other` split exists only so the
output metadata records both factors' provenance under separate
`seed_*` and `other_*` prefixes.
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


class TensorBlowupSearch(Search):
    """
    Build seed × other for two `nx.Graph` factors.

    Constraints
    -----------
    seed, other : nx.Graph
        Both required. N = seed.order * other.order.
    seed_meta, other_meta : dict | None
        Optional provenance dicts; entries flow into the produced
        graph's metadata under `seed_*` and `other_*` prefixes.
        Pass-through.
    """

    name = "blowup"

    def __init__(
        self,
        *,
        top_k: int = 1,
        verbosity: int = 0,
        parent_logger=None,
        seed: nx.Graph,
        other: nx.Graph,
        seed_meta: dict | None = None,
        other_meta: dict | None = None,
        **kwargs,
    ):
        n = seed.number_of_nodes() * other.number_of_nodes()
        super().__init__(
            n,
            top_k=top_k,
            verbosity=verbosity,
            parent_logger=parent_logger,
            seed=seed,
            other=other,
            seed_meta=seed_meta or {},
            other_meta=other_meta or {},
            **kwargs,
        )

    def _run(self) -> list[nx.Graph]:
        G = _relabel(nx.tensor_product(self.seed, self.other))

        self._stamp(G)
        k4_free = is_k4_free_nx(G)
        self._log(
            "tensor_blowup",
            level=1,
            n_out=G.number_of_nodes(),
            m_out=G.number_of_edges(),
            is_k4_free=int(k4_free),
        )
        G.graph["metadata"] = {
            "mode": "tensor",
            **{f"seed_{key}": val for key, val in self.seed_meta.items()},
            **{f"other_{key}": val for key, val in self.other_meta.items()},
        }
        return [G]
