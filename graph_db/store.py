"""
graph_db/store.py
=================
Graph store: the graphs/ folder of JSON batch files.

Each file is a JSON array of records of the form

    {"id": str, "sparse6": str, "source": str, "metadata": {...}?}

This is the *source of truth* for what graphs exist. The cache (cache.py)
is a derived SQLite layer and can be regenerated from the store at any
time.

Dedup key is (id, source): the same graph discovered by two different
sources produces two records, on purpose — see DESIGN.md for the
rationale around rediscovery tracking.
"""

import glob
import json
import os

from graph_db.encoding import canonical_id


class GraphStore:
    """
    Reads and writes the graphs/ folder.
    Each file is a JSON array of {id, sparse6, source, metadata?} records.
    """

    def __init__(self, graphs_dir: str):
        self.graphs_dir = graphs_dir
        os.makedirs(graphs_dir, exist_ok=True)

    # ── read ──────────────────────────────────────────────────────────────────

    def all_records(self) -> list[dict]:
        """Return every record across every batch file as a flat list."""
        records: list[dict] = []
        for path in sorted(glob.glob(os.path.join(self.graphs_dir, "*.json"))):
            with open(path) as f:
                batch = json.load(f)
            records.extend(batch)
        return records

    def all_id_source_pairs(self) -> set[tuple[str, str]]:
        return {(r["id"], r["source"]) for r in self.all_records()}

    def all_ids(self) -> set[str]:
        return {r["id"] for r in self.all_records()}

    def all_sources(self) -> list[str]:
        return sorted({r["source"] for r in self.all_records()})

    def sparse6_map(self) -> dict[str, str]:
        """Return {graph_id: sparse6} across all records (same graph → same sparse6)."""
        return {r["id"]: r["sparse6"] for r in self.all_records()}

    # ── write ─────────────────────────────────────────────────────────────────

    def write_batch(self, records: list[dict], filename: str) -> tuple[int, int]:
        """
        Append records to graphs/{filename}, creating the file if needed.
        Silently skips records whose (id, source) already exists anywhere
        in the store. Returns (written, skipped).
        """
        existing = self.all_id_source_pairs()
        new = [r for r in records if (r["id"], r["source"]) not in existing]
        skipped = len(records) - len(new)
        if new:
            path = os.path.join(self.graphs_dir, filename)
            if os.path.exists(path):
                with open(path) as f:
                    current = json.load(f)
                current.extend(new)
                with open(path, "w") as f:
                    json.dump(current, f, indent=2)
            else:
                with open(path, "w") as f:
                    json.dump(new, f, indent=2)
        return len(new), skipped

    def add_graph(self, G, source: str, filename: str, **metadata) -> tuple[str, bool]:
        """
        Compute id + sparse6 for G and append a single record.
        Returns (graph_id, was_new). was_new=False if (id, source) already exists.
        """
        gid, cs6 = canonical_id(G)
        if (gid, source) in self.all_id_source_pairs():
            return gid, False
        rec = {"id": gid, "sparse6": cs6, "source": source}
        if metadata:
            rec["metadata"] = metadata
        self.write_batch([rec], filename)
        return gid, True

    def remove(
        self,
        graph_id: str | None = None,
        source: str | None = None,
    ) -> int:
        """
        Delete records matching (graph_id, source). At least one must be
        given. Returns number of records removed. Empty files are
        removed from disk.
        """
        if graph_id is None and source is None:
            raise ValueError("remove(): provide graph_id or source (or both)")

        removed = 0
        for path in sorted(glob.glob(os.path.join(self.graphs_dir, "*.json"))):
            with open(path) as f:
                batch = json.load(f)

            kept = []
            for r in batch:
                hit = (
                    (graph_id is None or r["id"] == graph_id)
                    and (source is None or r["source"] == source)
                )
                if hit:
                    removed += 1
                else:
                    kept.append(r)

            if len(kept) == len(batch):
                continue
            if kept:
                with open(path, "w") as f:
                    json.dump(kept, f, indent=2)
            else:
                os.remove(path)
        return removed
