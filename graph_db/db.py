"""
graph_db/db.py
==============
The single public class for the graph database. Combines GraphStore
(graphs/ folder) with PropertyCache (cache.db) and exposes the read,
write, sync, and query API described in DESIGN.md.

Typical usage:

    from graph_db import DB

    with DB() as db:
        db.sync()
        for rec in db.query(source="sat_pareto", ranges={"c_log": (0, 0.75)}):
            print(rec["graph_id"], rec["c_log"])
"""

import os
from typing import Any, Iterable

import numpy as np
import networkx as nx

from graph_db.cache import PropertyCache
from graph_db.encoding import canonical_id, graph_to_sparse6, sparse6_to_nx
from graph_db.store import GraphStore

REPO_ROOT      = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_GRAPHS = os.path.join(REPO_ROOT, "graphs")
DEFAULT_CACHE  = os.path.join(REPO_ROOT, "cache.db")


class DB:
    """
    Combined graph store + property cache. The only class most callers
    need. Context-manager capable.

    Parameters
    ----------
    graphs_dir  Path to the graphs/ folder (defaults to repo-root/graphs).
    cache_path  Path to cache.db (defaults to repo-root/cache.db).
    auto_sync   If True, compute properties for any store records missing
                from the cache when the DB is opened.
    """

    def __init__(
        self,
        graphs_dir: str = DEFAULT_GRAPHS,
        cache_path: str = DEFAULT_CACHE,
        auto_sync: bool = True,
    ):
        self.store = GraphStore(graphs_dir)
        self.cache = PropertyCache(cache_path)
        self._sparse6_cache: dict[str, str] | None = None
        if auto_sync:
            self.sync(verbose=False)

    def close(self):
        self.cache.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    # ── reads ─────────────────────────────────────────────────────────────────

    def get(self, graph_id: str, source: str | None = None) -> dict | None:
        return self.cache.get(graph_id, source)

    def get_all(self, graph_id: str) -> list[dict]:
        return self.cache.get_all(graph_id)

    def sources(self) -> list[str]:
        return self.cache.all_sources()

    def query(
        self,
        where:    dict | None = None,
        ranges:   dict | None = None,
        isin:     dict | None = None,
        order_by: str | list[str] | None = None,
        limit:    int | None = None,
        **kwargs,
    ) -> list[dict]:
        """
        Flexible SELECT over the cache.

        where    — equality filters {col: val}. Example: {'n': 17}.
        ranges   — inclusive range filters {col: (min, max)}.
                   Either bound may be None (open-ended).
        isin     — membership filters {col: [val, ...]}.
        order_by — 'col' (asc) or '-col' (desc); or a list for multi-sort.
        limit    — max rows.
        **kwargs — shorthand: scalar values go to `where`, tuple values
                   go to `ranges`, list values go to `isin`. Lets callers
                   write db.query(n=17, c_log=(0, 1), source=['a','b']).

        All column names are validated against the cache schema, so no
        SQL injection surface.
        """
        where  = dict(where  or {})
        ranges = dict(ranges or {})
        isin   = dict(isin   or {})

        for k, v in kwargs.items():
            if isinstance(v, tuple):
                ranges[k] = v
            elif isinstance(v, list):
                isin[k] = v
            else:
                where[k] = v

        allowed = self.cache.schema_columns()

        def _validate(col: str):
            if col not in allowed:
                raise ValueError(f"unknown column {col!r}")

        clauses: list[str] = []
        params:  list[Any] = []

        for col, val in where.items():
            _validate(col)
            clauses.append(f"{col} = ?")
            params.append(val)

        for col, bounds in ranges.items():
            _validate(col)
            lo, hi = bounds if isinstance(bounds, tuple) else (bounds, bounds)
            if lo is not None:
                clauses.append(f"{col} >= ?"); params.append(lo)
            if hi is not None:
                clauses.append(f"{col} <= ?"); params.append(hi)

        for col, values in isin.items():
            _validate(col)
            if not values:
                return []
            placeholders = ",".join("?" for _ in values)
            clauses.append(f"{col} IN ({placeholders})")
            params.extend(values)

        sql = "SELECT * FROM cache"
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)

        if order_by is not None:
            cols = [order_by] if isinstance(order_by, str) else list(order_by)
            terms = []
            for c in cols:
                desc = c.startswith("-")
                name = c[1:] if desc else c
                _validate(name)
                terms.append(f"{name} {'DESC' if desc else 'ASC'}")
            sql += " ORDER BY " + ", ".join(terms)

        if limit is not None:
            sql += f" LIMIT {int(limit)}"

        return self.cache.raw_execute(sql, tuple(params))

    def top(
        self,
        column: str,
        k: int = 10,
        ascending: bool = True,
        **filters,
    ) -> list[dict]:
        """Top-k rows by `column`. Forwards **filters to query()."""
        return self.query(
            order_by=column if ascending else f"-{column}",
            limit=k,
            **filters,
        )

    def frontier(
        self,
        by: str = "n",
        minimize: str = "c_log",
        **filters,
    ) -> list[dict]:
        """
        Best row per distinct value of `by`, where "best" = min of
        `minimize`. Used by the visualizer's "only show min c_log per n"
        toggle and by leaderboard code.

        `by` and `minimize` are whitelisted against the cache schema.
        """
        allowed = self.cache.schema_columns()
        if by not in allowed:
            raise ValueError(f"unknown column {by!r}")
        if minimize not in allowed:
            raise ValueError(f"unknown column {minimize!r}")

        # Pull all matching rows filtered, then bucket in Python. Cheaper
        # and more predictable than window functions across SQLite versions.
        rows = self.query(**filters)
        best: dict[Any, dict] = {}
        for r in rows:
            v = r.get(minimize)
            if v is None:
                continue
            key = r.get(by)
            if key not in best or v < best[key][minimize]:
                best[key] = r
        return sorted(best.values(), key=lambda r: (r.get(by) is None, r.get(by)))

    def count(self, **filters) -> int:
        return len(self.query(**filters))

    def stats(self) -> dict:
        """Summary numbers for `scripts.py stats` and quick sanity checks."""
        row = self.cache._conn.execute(
            """
            SELECT COUNT(*)                       AS n_pairs,
                   COUNT(DISTINCT graph_id)       AS n_graphs,
                   COUNT(DISTINCT source)         AS n_sources,
                   MIN(n)                         AS n_min,
                   MAX(n)                         AS n_max,
                   MIN(c_log)                     AS c_min,
                   MAX(c_log)                     AS c_max,
                   SUM(is_k4_free)                AS n_k4_free,
                   SUM(is_regular)                AS n_regular
            FROM cache
            """
        ).fetchone()
        return dict(row) if row else {}

    # ── graph access ──────────────────────────────────────────────────────────

    def _ensure_sparse6_cache(self) -> dict[str, str]:
        if self._sparse6_cache is None:
            self._sparse6_cache = self.store.sparse6_map()
        return self._sparse6_cache

    def _invalidate_sparse6_cache(self):
        self._sparse6_cache = None

    def sparse6(self, graph_id: str) -> str | None:
        return self._ensure_sparse6_cache().get(graph_id)

    def nx(self, graph_id: str) -> nx.Graph | None:
        s6 = self.sparse6(graph_id)
        return sparse6_to_nx(s6) if s6 else None

    def adj(self, graph_id: str) -> np.ndarray | None:
        G = self.nx(graph_id)
        if G is None:
            return None
        return np.array(nx.to_numpy_array(G, dtype=np.uint8))

    def hydrate(self, records: Iterable[dict]) -> list[dict]:
        """
        Attach `sparse6`, `G` (nx.Graph), and `adj` (uint8 ndarray) to
        each record in `records`. One pass over the store's sparse6 map.
        """
        s6_map = self._ensure_sparse6_cache()
        out = []
        for rec in records:
            s6 = s6_map.get(rec["graph_id"])
            if s6 is None:
                continue
            G = sparse6_to_nx(s6)
            adj = np.array(nx.to_numpy_array(G, dtype=np.uint8))
            out.append({**rec, "sparse6": s6, "G": G, "adj": adj})
        return out

    # ── writes ────────────────────────────────────────────────────────────────

    def add(
        self,
        G,
        source: str,
        filename: str | None = None,
        **metadata,
    ) -> tuple[str, bool]:
        """
        Compute id + sparse6 for G and append to graphs/{filename}.
        If filename is None, defaults to f'{source}.json'.
        Returns (graph_id, was_new).
        """
        fn = filename or f"{source}.json"
        gid, was_new = self.store.add_graph(G, source=source, filename=fn, **metadata)
        if was_new:
            self._invalidate_sparse6_cache()
        return gid, was_new

    def add_batch(self, records: list[dict], filename: str) -> tuple[int, int]:
        """Bulk ingest pre-built records. Returns (added, skipped)."""
        added, skipped = self.store.write_batch(records, filename)
        if added:
            self._invalidate_sparse6_cache()
        return added, skipped

    def remove(
        self,
        graph_id: str | None = None,
        source: str | None = None,
    ) -> int:
        """Remove matching records from both store and cache."""
        if graph_id is None and source is None:
            raise ValueError("remove(): provide graph_id or source (or both)")
        n_store = self.store.remove(graph_id=graph_id, source=source)
        self.cache.delete(graph_id=graph_id, source=source)
        self._invalidate_sparse6_cache()
        return n_store

    # ── sync ──────────────────────────────────────────────────────────────────

    def sync(
        self,
        source: str | None = None,
        recompute: bool = False,
        dry_run: bool = False,
        verbose: bool = True,
    ) -> dict:
        """
        Bring the cache in line with the store.

        source    — restrict work to one source tag.
        recompute — if True, recompute properties even for rows that
                    already exist in the cache (use after properties.py
                    gains a new column, or to force a refresh).
        dry_run   — report what would be done, don't write.

        Returns summary dict: {added, updated, skipped, source}.
        """
        from graph_db.properties import compute_properties

        store_recs = self.store.all_records()
        if source is not None:
            store_recs = [r for r in store_recs if r["source"] == source]

        cached_pairs = self.cache.cached_pairs()
        work: list[tuple[dict, bool]] = []
        for rec in store_recs:
            key = (rec["id"], rec["source"])
            if key not in cached_pairs:
                work.append((rec, False))       # add
            elif recompute:
                work.append((rec, True))        # update

        summary = {
            "added":   sum(1 for _, upd in work if not upd),
            "updated": sum(1 for _, upd in work if upd),
            "skipped": len(store_recs) - len(work),
            "source":  source,
        }

        if not work:
            if verbose:
                print("Cache up to date.")
            return summary

        if verbose:
            print(
                f"sync: {summary['added']} new, {summary['updated']} to update, "
                f"{summary['skipped']} already cached"
                + (f" (source={source})" if source else "")
                + (" [dry-run]" if dry_run else "")
            )

        if dry_run:
            return summary

        for i, (rec, _upd) in enumerate(work, 1):
            G = sparse6_to_nx(rec["sparse6"])
            props = compute_properties(G)
            self.cache.insert(
                graph_id=rec["id"],
                source=rec["source"],
                props=props,
                metadata=rec.get("metadata", {}),
            )
            if verbose:
                c = props.get("c_log")
                c_str = f"{c:.4f}" if c is not None else "  —  "
                print(f"  [{i}/{len(work)}] id={rec['id']} "
                      f"source={rec['source']} n={props['n']} c_log={c_str}")

        if verbose:
            print(f"Done. Cache now has {self.cache.count()} entries.")
        return summary

    def recompute(
        self,
        graph_id: str | None = None,
        source: str | None = None,
    ) -> int:
        """
        Force-refresh cache rows matching (graph_id, source).
        Returns number of rows updated.
        """
        from graph_db.properties import compute_properties

        store_recs = self.store.all_records()
        if graph_id is not None:
            store_recs = [r for r in store_recs if r["id"] == graph_id]
        if source is not None:
            store_recs = [r for r in store_recs if r["source"] == source]

        for rec in store_recs:
            G = sparse6_to_nx(rec["sparse6"])
            props = compute_properties(G)
            self.cache.insert(
                graph_id=rec["id"],
                source=rec["source"],
                props=props,
                metadata=rec.get("metadata", {}),
            )
        return len(store_recs)


# ── module-level convenience ──────────────────────────────────────────────────

def open_db(
    graphs_dir: str = DEFAULT_GRAPHS,
    cache_path: str = DEFAULT_CACHE,
    auto_sync: bool = True,
) -> DB:
    """Open and return a DB instance (remember to .close() it or use as context manager)."""
    return DB(graphs_dir, cache_path, auto_sync)


def load_all_graphs(**filters) -> list[dict]:
    """One-shot: open DB, hydrate every matching record with G + adj, close."""
    with open_db() as db:
        return db.hydrate(db.query(**filters))
