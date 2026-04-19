"""
graph_db/clean.py
=================
Repair-and-dedup pass over the graph store.

Unlike the old verify.py, clean() prefers to repair records rather than
drop them:

  * If a record's sparse6 is not canonical, it is re-encoded in place.
  * If a record's stored `id` doesn't match the canonical sparse6,
    the id is rewritten.

Drops happen only when sparse6 is unparseable, or when a later record
duplicates an already-seen (graph_id, source) pair. Dedup is global
across all files.

After rewriting the store, orphaned cache rows (i.e. (id, source) rows
that are no longer backed by any record in graphs/) are pruned.

Usage:
    python scripts/db_cli.py clean               # report only (dry run)
    python scripts/db_cli.py clean --apply       # actually rewrite
"""

import glob
import json
import os
from dataclasses import dataclass, field


@dataclass
class CleanReport:
    total:            int = 0              # records scanned
    repaired_ids:     int = 0              # canonical id differed from stored
    repaired_sparse6: int = 0              # sparse6 rewritten to canonical form
    duplicates:       int = 0              # (id, source) pairs dropped as duplicates
    unparseable:      list = field(default_factory=list)  # [{file, id, source, error}]
    files_rewritten:  int = 0
    files_removed:    list = field(default_factory=list)
    orphaned_cache:   int = 0

    def as_dict(self) -> dict:
        return {
            "total":            self.total,
            "repaired_ids":     self.repaired_ids,
            "repaired_sparse6": self.repaired_sparse6,
            "duplicates":       self.duplicates,
            "unparseable":      self.unparseable,
            "files_rewritten":  self.files_rewritten,
            "files_removed":    self.files_removed,
            "orphaned_cache":   self.orphaned_cache,
        }


def clean(
    graphs_dir: str,
    cache_path: str,
    apply: bool = False,
    verbose: bool = True,
) -> CleanReport:
    """
    Scan and (optionally) rewrite the graph store.

    apply=False (default): dry run. Report what would happen, write
    nothing.

    apply=True: rewrite the store's JSON files with repairs/dedups
    applied, remove any emptied files, and prune orphaned cache rows.
    """
    from graph_db.encoding import canonical_id, sparse6_to_nx

    report = CleanReport()

    files = sorted(glob.glob(os.path.join(graphs_dir, "*.json")))
    if not files:
        if verbose:
            print("No graph JSON files found.")
        return report

    seen: dict[tuple[str, str], tuple[str, int]] = {}  # (id, src) → (file, idx)
    per_file_kept: dict[str, list[dict]] = {}

    # ── pass 1: scan, repair, dedup ─────────────────────────────────────────
    for path in files:
        fname = os.path.basename(path)
        with open(path) as f:
            records = json.load(f)
        report.total += len(records)
        kept: list[dict] = []

        for rec in records:
            stored_id = rec.get("id", "")
            source    = rec.get("source", "")
            s6        = rec.get("sparse6", "")

            try:
                G = sparse6_to_nx(s6)
            except Exception as exc:
                report.unparseable.append({
                    "file":  fname,
                    "id":    stored_id,
                    "source": source,
                    "error": f"sparse6 parse: {exc}",
                })
                if verbose:
                    print(f"  [UNPARSEABLE] {fname}/{stored_id}: {exc}")
                continue

            canon_id, canon_s6 = canonical_id(G)

            if canon_s6 != s6:
                report.repaired_sparse6 += 1
                rec["sparse6"] = canon_s6
            if canon_id != stored_id:
                report.repaired_ids += 1
                rec["id"] = canon_id
                if verbose:
                    print(f"  [REPAIR ID] {fname}: {stored_id} → {canon_id}")

            key = (canon_id, source)
            if key in seen:
                report.duplicates += 1
                prev_file, _ = seen[key]
                if verbose:
                    print(f"  [DUPLICATE] {fname}: id={canon_id} source={source} "
                          f"(first seen in {prev_file})")
                continue

            seen[key] = (fname, len(kept))
            kept.append(rec)

        per_file_kept[path] = kept

    # ── summary ──────────────────────────────────────────────────────────────
    if verbose:
        print(f"\nStore: {report.total} records across {len(files)} file(s)")
        print(f"  repaired_ids     : {report.repaired_ids}")
        print(f"  repaired_sparse6 : {report.repaired_sparse6}")
        print(f"  duplicates       : {report.duplicates}")
        print(f"  unparseable      : {len(report.unparseable)}")

    if not apply:
        if verbose and (report.repaired_ids or report.repaired_sparse6
                        or report.duplicates or report.unparseable):
            print("Re-run with --apply to rewrite the store.")
        return report

    # ── pass 2: rewrite files ────────────────────────────────────────────────
    for path, kept in per_file_kept.items():
        fname = os.path.basename(path)
        with open(path) as f:
            before = json.load(f)
        if kept == before:
            continue
        if kept:
            with open(path, "w") as f:
                json.dump(kept, f, indent=2)
            report.files_rewritten += 1
            if verbose:
                print(f"  Rewrote {fname}: {len(before)} → {len(kept)} records")
        else:
            os.remove(path)
            report.files_removed.append(fname)
            if verbose:
                print(f"  Removed empty file {fname}")

    # ── pass 3: prune orphans from cache ────────────────────────────────────
    if os.path.exists(cache_path):
        from graph_db.cache import PropertyCache
        valid_pairs = set(seen.keys())
        with PropertyCache(cache_path) as cache:
            report.orphaned_cache = cache.prune_orphans(valid_pairs)
        if verbose and report.orphaned_cache:
            print(f"  Pruned {report.orphaned_cache} orphaned cache row(s)")

    return report
