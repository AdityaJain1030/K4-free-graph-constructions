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
import signal
import traceback
from typing import Any, Iterable

import numpy as np
import networkx as nx

from graph_db.cache import PropertyCache
from graph_db.encoding import canonical_id, graph_to_sparse6, sparse6_to_nx
from graph_db.store import GraphStore

REPO_ROOT      = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_GRAPHS = os.path.join(REPO_ROOT, "graphs")
DEFAULT_CACHE  = os.path.join(REPO_ROOT, "cache.db")


# Module-level worker so multiprocessing can pickle it. Returns a tuple of
# (graph_id, source, metadata, props_or_None, error_or_None). Workers handle
# their own timeout via SIGALRM so a single pathological graph can't block
# the pool forever.
def _sync_worker(args):
    graph_id, source, sparse6, metadata, timeout_s = args
    try:
        if timeout_s and timeout_s > 0:
            class _Timeout(Exception):
                pass
            def _handler(signum, frame):
                raise _Timeout()
            signal.signal(signal.SIGALRM, _handler)
            signal.alarm(int(timeout_s))
        from graph_db.properties import compute_properties
        G = sparse6_to_nx(sparse6)
        props = compute_properties(G)
        if timeout_s and timeout_s > 0:
            signal.alarm(0)
        return (graph_id, source, metadata, props, None)
    except KeyboardInterrupt:
        # Let Ctrl+C propagate so the sync actually stops. In pool mode this
        # path is unreachable (the parent handles SIGINT and terminates the
        # pool); in serial mode we want the interrupt to bubble up.
        if timeout_s and timeout_s > 0:
            try:
                signal.alarm(0)
            except Exception:
                pass
        raise
    except BaseException as exc:  # catches our _Timeout + anything else
        if timeout_s and timeout_s > 0:
            try:
                signal.alarm(0)
            except Exception:
                pass
        tag = "timeout" if exc.__class__.__name__ == "_Timeout" else type(exc).__name__
        return (graph_id, source, metadata, None, f"{tag}: {exc}")


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
        """Summary numbers for `scripts/db_cli.py stats` and quick sanity checks."""
        rows = self.cache.raw_execute(
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
        )
        return rows[0] if rows else {}

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
        workers: int = 1,
        per_record_timeout_s: float | None = None,
    ) -> dict:
        """
        Bring the cache in line with the store.

        source    — restrict work to one source tag.
        recompute — if True, recompute properties even for rows that
                    already exist in the cache (use after properties.py
                    gains a new column, or to force a refresh).
        dry_run   — report what would be done, don't write.
        workers   — number of worker processes for property computation.
                    1 = run serially in-process (old behaviour).
        per_record_timeout_s — if set, a worker that exceeds this wall-clock
                    limit on a single graph raises SIGALRM inside itself,
                    returns a timeout marker, and sync moves on. No single
                    pathological graph can block the pool.

        Returns summary dict: {added, updated, skipped, errors, source}.
        """
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
            "errors":  0,
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
                + (f" [workers={workers}]" if workers > 1 else "")
                + (f" [timeout={per_record_timeout_s}s]" if per_record_timeout_s else "")
                + (" [dry-run]" if dry_run else "")
            )

        if dry_run:
            return summary

        total = len(work)
        tasks = [
            (rec["id"], rec["source"], rec["sparse6"],
             rec.get("metadata", {}), per_record_timeout_s)
            for rec, _ in work
        ]

        def _ingest(result, idx):
            gid, src, meta, props, err = result
            if err is not None:
                summary["errors"] += 1
                if verbose:
                    print(f"  [{idx}/{total}] id={gid} source={src} "
                          f"SKIP ({err})")
                return
            self.cache.insert(
                graph_id=gid, source=src, props=props, metadata=meta,
            )
            if verbose:
                c = props.get("c_log")
                c_str = f"{c:.4f}" if c is not None else "  —  "
                print(f"  [{idx}/{total}] id={gid} source={src} "
                      f"n={props['n']} c_log={c_str}")

        if workers <= 1 or total == 1:
            for i, task in enumerate(tasks, 1):
                _ingest(_sync_worker(task), i)
        else:
            # Pool processes tasks in any order; we count completions for
            # progress display. chunksize=1 because per-task runtime varies
            # by orders of magnitude on this workload.
            import multiprocessing as mp
            ctx = mp.get_context("spawn")  # clean slate per worker, avoids
                                           # inheriting tk/SAT/numba state
            with ctx.Pool(processes=workers) as pool:
                done = 0
                for result in pool.imap_unordered(_sync_worker, tasks, chunksize=1):
                    done += 1
                    _ingest(result, done)

        if verbose:
            print(f"Done. Cache now has {self.cache.count()} entries "
                  f"(errors: {summary['errors']}).")
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

    # ── clean ─────────────────────────────────────────────────────────────────

    def clean(self, apply: bool = False, verbose: bool = True):
        """
        Repair-and-dedup pass over the store, optionally pruning orphaned
        cache rows. Returns a CleanReport.

        apply=False (default): dry run, report only.
        apply=True: rewrite graphs/ JSON files and prune cache orphans.
        """
        from graph_db.clean import clean as _clean
        report = _clean(
            graphs_dir=self.store.graphs_dir,
            cache_path=self.cache.db_path,
            apply=apply,
            verbose=verbose,
        )
        if apply:
            self._invalidate_sparse6_cache()
        return report

    # ── schema introspection ─────────────────────────────────────────────────

    def schema_columns(self) -> set[str]:
        """Return the set of cache columns usable in query()/top()/frontier()."""
        return self.cache.schema_columns()

    # ── raw SQL escape hatch ─────────────────────────────────────────────────

    def raw_execute(self, sql: str, params: tuple = ()) -> list[dict]:
        """
        Run an arbitrary SELECT against the cache. Rows come back as dicts
        with JSON columns already deserialised. Use this only when the
        typed query helpers (`query`, `top`, `frontier`) can't express
        what you need — e.g. aggregations or window functions.
        """
        return self.cache.raw_execute(sql, params)


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
