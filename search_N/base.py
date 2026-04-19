"""
search_N/base.py
================
Abstract base class for per-N K4-free graph search algorithms.

Every concrete searcher inherits Search, sets a `name` class attribute,
and implements `_run()`, which returns a list of K4-free graphs found on
self.n vertices (empty list if the search fails / times out).

Algorithms that are only designed to find one best graph set multi_result=False
(the default); those that can meaningfully return several good candidates set
multi_result=True.  Either way, run() always returns list[nx.Graph].

Minimal example::

    class MySearch(Search):
        name = "my_search"

        def _run(self):
            G = ...  # find a good K4-free graph on self.n vertices
            return [G]

    results = MySearch(n=20).run()
    for G in results:
        print(Search.c_log(G))
    MySearch(n=20).save_all(results)
"""

import os
import sys
import time
from abc import ABC, abstractmethod

import networkx as nx

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from graph_db import GraphStore
from utils.graph_props import alpha_exact_nx, is_k4_free_nx, c_log_value
from search_N.logger import SearchLogger

_GRAPHS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "graphs"
)


class Search(ABC):
    """
    Base class for K4-free graph search algorithms parameterized by N.

    Subclass contract
    -----------------
    - Set class attribute `name` (str) — used as the source tag in graph_db.
    - Set `multi_result = True` if the algo is designed to yield several graphs.
    - Implement `_run() -> list[nx.Graph]`.

    Provided helpers
    ----------------
    c_log(G)        — compute the extremal metric for any graph.
    is_valid(G)     — True iff G is K4-free.
    save(G)         — persist one graph to the graph store.
    save_all(graphs) — persist a list of graphs, returns list of (id, was_new).
    """

    name: str = "search"       # subclasses must override
    multi_result: bool = False  # True for algos that return multiple candidates

    def __init__(self, n: int, **kwargs):
        self.n = n
        self._logger = SearchLogger(self.name, n)
        self._start_time: float | None = None

    @abstractmethod
    def _run(self) -> list[nx.Graph]:
        """
        Search for K4-free graphs on self.n vertices that minimise
        c_log = alpha * d_max / (n * ln(d_max)).

        Returns a list of nx.Graph (empty if no valid result found).
        Single-result algos return a one-element list or [].
        """

    def run(self) -> list[nx.Graph]:
        """Logging wrapper around _run(). Emits search_start/search_end/error."""
        self._start_time = time.time()
        self._log("search_start", multi_result=self.multi_result)
        results = []
        try:
            results = self._run() or []
        except Exception as exc:
            self._log("error", exc=str(exc))
            self._logger.close()
            raise
        c_logs = [v for G in results if (v := self.c_log(G)) is not None]
        self._log(
            "search_end",
            status="ok",
            n_results=len(results),
            best_c_log=min(c_logs) if c_logs else None,
            elapsed_s=self._elapsed(),
        )
        self._logger.close()
        return results

    # ── logging helpers ───────────────────────────────────────────────────────

    def _log(self, event: str, **data):
        """Write a structured log event. Subclasses call this for algo-specific events."""
        self._logger.write(event, **data)

    def _elapsed(self) -> float | None:
        """Seconds since run() was entered, or None if not started."""
        return round(time.time() - self._start_time, 4) if self._start_time is not None else None

    # ── static helpers ────────────────────────────────────────────────────────

    @staticmethod
    def c_log(G: nx.Graph) -> float | None:
        """Return c_log for G, or None when d_max <= 1."""
        n = G.number_of_nodes()
        if n == 0:
            return None
        d_max = max((d for _, d in G.degree()), default=0)
        alpha, _ = alpha_exact_nx(G)
        return c_log_value(alpha, n, d_max)

    @staticmethod
    def is_valid(G: nx.Graph) -> bool:
        """Return True iff G is K4-free."""
        return is_k4_free_nx(G)

    # ── instance helpers ──────────────────────────────────────────────────────

    def save(
        self,
        G: nx.Graph,
        filename: str | None = None,
        **metadata,
    ) -> tuple[str, bool]:
        """Persist G to the graph store under source=self.name."""
        if filename is None:
            filename = f"{self.name}.json"
        store = GraphStore(_GRAPHS_DIR)
        return store.add_graph(G, source=self.name, filename=filename, **metadata)

    def save_all(
        self,
        graphs: list[nx.Graph],
        filename: str | None = None,
        **metadata,
    ) -> list[tuple[str, bool]]:
        """Persist every graph in the list; returns [(graph_id, was_new), ...]."""
        return [self.save(G, filename=filename, **metadata) for G in graphs]
