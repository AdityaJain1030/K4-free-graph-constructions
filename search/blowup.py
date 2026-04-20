"""
search/blowup.py
================
Blow-up constructions: lex / tensor product of seed graphs from graph_db.

Probe 4 from the landscape study. Given a K4-free seed graph `G`
already in `graph_db`, produce structured large-N graphs by:

- **lex blow-up** — `G[I_k]`, replace each vertex of G with an
  independent set of size k. Preserves K4-freeness; α doubles per
  doubling of k; d_max scales linearly with k.
- **tensor blow-up** — `G × H` where H is another K4-free graph
  (typically small, from graph_db). Preserves K4-freeness
  (a K4 in the product projects to a K4 in each factor).

These aren't competitive as finished products — they're structured
seeds at large N that an edge-switch polish (chain with
`RandomRegularSwitchSearch`) can then try to improve.
"""

import os
import sys

import networkx as nx

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from graph_db import DB, sparse6_to_nx
from utils.graph_props import is_k4_free_nx

from .base import Search


def _relabel(G: nx.Graph) -> nx.Graph:
    """Relabel to 0..n-1 integer nodes (product ops return tuple nodes)."""
    mapping = {v: i for i, v in enumerate(sorted(G.nodes()))}
    H = nx.relabel_nodes(G, mapping)
    H.graph.clear()
    H.add_nodes_from(range(len(mapping)))
    return H


def _load_seed_from_db(
    db: DB,
    source: str | None,
    graph_id: str | None,
    n: int | None,
) -> tuple[nx.Graph, dict]:
    """
    Resolve a single seed graph from graph_db. Priority:
    graph_id > (source, n) match > (source) frontier min_c_log.
    """
    if graph_id is not None:
        s6 = db.sparse6(graph_id)
        if s6 is None:
            raise ValueError(f"graph_id {graph_id!r} not in store")
        rec = db.get(graph_id, source=source) or {}
        return sparse6_to_nx(s6), {
            "seed_id": graph_id,
            "seed_source": rec.get("source", source),
            "seed_n": rec.get("n"),
            "seed_c_log": rec.get("c_log"),
        }

    filters = {}
    if source is not None:
        filters["source"] = source
    if n is not None:
        filters["n"] = n
    rows = db.top("c_log", k=1, ascending=True, **filters)
    if not rows:
        raise ValueError(f"no seed matched source={source!r}, n={n!r}")
    rec = rows[0]
    return db.nx(rec["graph_id"]), {
        "seed_id": rec["graph_id"],
        "seed_source": rec["source"],
        "seed_n": rec["n"],
        "seed_c_log": rec.get("c_log"),
    }


class BlowupSearch(Search):
    """
    Build a K4-free graph on N vertices by blowing up a seed from graph_db.

    Constraints
    -----------
    mode : {"lex", "tensor"}
        Hard. "lex" → seed[I_k] with k = `k`; N = seed_n * k.
        "tensor" → seed × other; N = seed_n * other_n.
    k : int
        Required when mode == "lex". Size of the independent set each
        seed vertex is replaced by.
    seed_source, seed_id, seed_n : str | None
        Which seed to lift out of graph_db. seed_id wins; else
        (seed_source, seed_n) frontier-min by c_log; else overall
        frontier for seed_source; else error.
    other_source, other_id, other_n : str | None
        For mode == "tensor", the second factor. Same resolution order.
        Required when mode == "tensor".

    Notes
    -----
    - Base kwarg `n` is the *number of vertices* but this search
      ignores it when mode/k fully determines the product size.
      We reset self.n post-construction so base scoring is correct.
    - Product graphs from networkx use tuple labels; we relabel to
      0..N-1 and clear node/edge attributes before returning.
    """

    name = "blowup"

    def __init__(
        self,
        n: int,
        *,
        top_k: int = 1,
        verbosity: int = 0,
        parent_logger=None,
        mode: str = "lex",
        k: int | None = None,
        seed_source: str | None = None,
        seed_id: str | None = None,
        seed_n: int | None = None,
        other_source: str | None = None,
        other_id: str | None = None,
        other_n: int | None = None,
        **kwargs,
    ):
        if mode not in ("lex", "tensor"):
            raise ValueError(f"mode must be 'lex' or 'tensor', got {mode!r}")
        if mode == "lex" and (k is None or k < 2):
            raise ValueError("mode='lex' requires k >= 2")
        super().__init__(
            n,
            top_k=top_k,
            verbosity=verbosity,
            parent_logger=parent_logger,
            mode=mode,
            k=k,
            seed_source=seed_source,
            seed_id=seed_id,
            seed_n=seed_n,
            other_source=other_source,
            other_id=other_id,
            other_n=other_n,
            **kwargs,
        )

    def _lex_with_I_k(self, seed: nx.Graph, k: int) -> nx.Graph:
        """Lex product seed[I_k] — each vertex replaced by an independent set."""
        Ik = nx.empty_graph(k)
        P = nx.lexicographic_product(seed, Ik)
        return _relabel(P)

    def _tensor(self, seed: nx.Graph, other: nx.Graph) -> nx.Graph:
        """Tensor product seed × other."""
        P = nx.tensor_product(seed, other)
        return _relabel(P)

    def _run(self) -> list[nx.Graph]:
        with DB() as db:
            seed, seed_meta = _load_seed_from_db(
                db, self.seed_source, self.seed_id, self.seed_n
            )
            if self.mode == "lex":
                G = self._lex_with_I_k(seed, self.k)
                metadata = {
                    "mode": "lex",
                    "k": self.k,
                    **seed_meta,
                }
            else:
                other, other_meta = _load_seed_from_db(
                    db, self.other_source, self.other_id, self.other_n
                )
                G = self._tensor(seed, other)
                metadata = {
                    "mode": "tensor",
                    **seed_meta,
                    **{f"other_{k}": v for k, v in other_meta.items() if k != "seed_id"},
                    "other_id": other_meta["seed_id"],
                }

        self._stamp(G)
        # Report what actually came out — base scoring uses the real
        # vertex count, not whatever was passed as `n`.
        self.n = G.number_of_nodes()

        k4_free = is_k4_free_nx(G)
        self._log(
            "blowup",
            level=1,
            mode=self.mode,
            n_out=G.number_of_nodes(),
            m_out=G.number_of_edges(),
            is_k4_free=int(k4_free),
        )
        G.graph["metadata"] = metadata
        return [G]
