"""
search_N/base.py
================
Abstract base class for per-N K4-free graph search algorithms.

Every concrete searcher inherits `Search`, sets a `name` class attribute,
declares any algorithm-specific constraints as kwargs on __init__, and
implements `_run() -> list[nx.Graph]`. Everything else — timing, scoring
(alpha, d_max, c_log, is_k4_free), logging, persistence — is the base
class's job.

Minimal example::

    class MySearch(Search):
        name = "my_search"

        def _run(self):
            G = ...                       # produce one or more nx.Graph
            self._stamp(G)                # optional: record exact discovery time
            G.graph["metadata"] = {...}   # optional: algo-specific payload
            return [G]

    results = MySearch(n=20, top_k=3).run()
    MySearch(n=20).save(results)
"""

import os
import sys
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone

import networkx as nx

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from graph_db import GraphStore, DEFAULT_GRAPHS
from utils.graph_props import alpha_exact_nx, is_k4_free_nx, c_log_value
from search_N.logger import SearchLogger, AggregateLogger


@dataclass(frozen=True)
class SearchResult:
    """
    One candidate graph returned by a search, with every scoring field
    computed by the base class.
    """
    G:            nx.Graph
    n:            int
    algo:         str
    c_log:        float | None
    alpha:        int
    d_max:        int
    is_k4_free:   bool
    time_to_find: float
    timestamp:    str
    metadata:     dict = field(default_factory=dict)


class Search(ABC):
    """
    Base class for K4-free graph search algorithms parameterized by N.

    Subclass contract
    -----------------
    - Set class attribute `name` (str) — used as the source tag in graph_db.
    - Declare any algorithm-specific constraints as kwargs on __init__
      (see DESIGN.md for the shared vocabulary — `alpha`, `d_max`,
      `is_regular`, `seed`, ...). Mark each hard or soft in the docstring.
    - Implement `_run() -> list[nx.Graph]`.

    Universal kwargs (on every subclass, via super().__init__)
    ----------------------------------------------------------
    top_k          : keep the top_k results by c_log (ascending).
    verbosity      : int; gates `self._log(event, level=N, ...)` calls.
    parent_logger  : AggregateLogger, if running under a sweep.
    """

    name: str = "search"

    def __init__(
        self,
        n: int,
        *,
        top_k: int = 1,
        verbosity: int = 0,
        parent_logger: "AggregateLogger | None" = None,
        **kwargs,
    ):
        self.n = n
        self.top_k = top_k
        self.verbosity = verbosity
        # subclass-declared kwargs auto-become attributes AND get logged
        # in the `search_start` event so every run is self-describing.
        self._extra_kwargs = dict(kwargs)
        for k, v in kwargs.items():
            setattr(self, k, v)
        self._logger = SearchLogger(self.name, n, parent_logger=parent_logger)
        self._start_time: float | None = None
        self._stamps: dict[int, float] = {}

    # ── subclass entrypoint ──────────────────────────────────────────────────

    @abstractmethod
    def _run(self) -> list[nx.Graph]:
        """
        Produce up to self.top_k graphs on self.n vertices. Base handles
        scoring, sorting, truncation, logging, and persistence.
        """

    # ── run wrapper (the only public entrypoint) ─────────────────────────────

    def run(self) -> list[SearchResult]:
        self._start_time = time.monotonic()
        self._log(
            "search_start",
            top_k=self.top_k,
            verbosity=self.verbosity,
            **self._extra_kwargs,
        )
        try:
            graphs = self._run() or []
        except Exception as exc:
            self._log("error", exc=repr(exc))
            self._log(
                "search_end",
                status="error",
                n_results=0,
                best_c_log=None,
                elapsed_s=self._elapsed(),
            )
            self._logger.close()
            raise

        results = [self._wrap(G) for G in graphs]
        results.sort(key=lambda r: (r.c_log is None, r.c_log))
        results = results[: self.top_k]

        for r in results:
            self._log(
                "new_best",
                c_log=_fmt(r.c_log),
                alpha=r.alpha,
                d_max=r.d_max,
                time_to_find=round(r.time_to_find, 4),
                is_k4_free=int(r.is_k4_free),
            )

        best = results[0].c_log if results else None
        self._log(
            "search_end",
            status="ok",
            n_results=len(results),
            best_c_log=_fmt(best),
            elapsed_s=self._elapsed(),
        )
        self._logger.close()
        return results

    # ── logging / timing helpers used by subclasses ──────────────────────────

    def _log(self, event: str, level: int = 0, **kv):
        """Subclass-facing log call. Filtered by verbosity (unconditional base events pass level=0)."""
        if level <= self.verbosity:
            self._logger.write(event, **kv)

    def _stamp(self, G: nx.Graph) -> None:
        """Record time_to_find for G at the moment of discovery."""
        self._stamps[id(G)] = self._elapsed() or 0.0

    def _elapsed(self) -> float | None:
        if self._start_time is None:
            return None
        return round(time.monotonic() - self._start_time, 4)

    # ── internals ────────────────────────────────────────────────────────────

    def _wrap(self, G: nx.Graph) -> SearchResult:
        """Compute every SearchResult field for one candidate graph."""
        n = G.number_of_nodes()
        d_max = max((d for _, d in G.degree()), default=0)
        alpha, _ = alpha_exact_nx(G) if n > 0 else (0, [])
        c = c_log_value(alpha, n, d_max) if n > 0 else None
        ttf = self._stamps.get(id(G))
        if ttf is None:
            ttf = self._elapsed() or 0.0
        metadata = dict(G.graph.get("metadata", {}))
        return SearchResult(
            G=G,
            n=n,
            algo=self.name,
            c_log=c,
            alpha=alpha,
            d_max=d_max,
            is_k4_free=is_k4_free_nx(G) if n > 0 else True,
            time_to_find=ttf,
            timestamp=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            metadata=metadata,
        )

    # ── persistence (opt-in) ─────────────────────────────────────────────────

    def save(
        self,
        results: "SearchResult | list[SearchResult]",
        filename: str | None = None,
    ) -> list[tuple[str, bool]]:
        """
        Persist one or more SearchResult into graph_db under source=self.name.
        Returns a list of (graph_id, was_new) per result.
        """
        if isinstance(results, SearchResult):
            results = [results]
        fn = filename or f"{self.name}.json"
        store = GraphStore(DEFAULT_GRAPHS)
        out: list[tuple[str, bool]] = []
        for r in results:
            out.append(
                store.add_graph(r.G, source=self.name, filename=fn, **r.metadata)
            )
        return out


def _fmt(x: float | None) -> str | None:
    """Compact float formatting for log lines; leaves None alone."""
    return None if x is None else round(x, 6)
