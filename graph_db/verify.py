"""
graph_db/verify.py
==================
Verify canonical-form integrity and deduplication of the graph store.

Duplicate = same (graph_id, source) pair appearing more than once.
Same graph from different sources is NOT a duplicate — that is intentional.

Usage:
    python -m graph_db.verify               # report only
    python -m graph_db.verify --fix         # report + remove bad entries
    python -m graph_db.verify --fix --quiet # fix silently
"""

import argparse
import glob
import json
import os
import sys

REPO_ROOT      = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_GRAPHS = os.path.join(REPO_ROOT, "graphs")
DEFAULT_CACHE  = os.path.join(REPO_ROOT, "cache.db")


def verify_and_fix(
    graphs_dir: str = DEFAULT_GRAPHS,
    cache_path: str = DEFAULT_CACHE,
    fix: bool = False,
    verbose: bool = True,
) -> dict:
    """
    For every record in the store:
      1. Reconstruct the graph from its sparse6.
      2. Recompute canonical_id.
      3. Flag the record if the stored ID doesn't match.
      4. Flag (id, source) duplicates — same graph same source appearing twice.
         Same graph from different sources is fine and left untouched.

    If fix=True:
      - Rewrite store JSON files removing bad / duplicate records.
      - Drop orphaned cache rows (id+source no longer in the store).

    Returns summary dict:
      total, invalid_id, duplicate, removed, orphaned_cache
    """
    sys.path.insert(0, REPO_ROOT)
    from graph_db.store import canonical_id, sparse6_to_nx

    store_files = sorted(glob.glob(os.path.join(graphs_dir, "*.json")))
    if not store_files:
        if verbose:
            print("No graph JSON files found.")
        return {"total": 0, "invalid_id": 0, "duplicate": 0, "removed": 0, "orphaned_cache": 0}

    # (canonical_id, source) → first file that contained it
    seen: dict[tuple[str, str], str] = {}
    invalid_ids: list[tuple[str, str, str]] = []    # (file, stored_id, issue)
    # Records to remove: set of (file, stored_id, source) — identifying a specific record
    to_remove: list[tuple[str, str, str]] = []

    total = 0

    # ── pass 1: scan ─────────────────────────────────────────────────────────
    for path in store_files:
        with open(path) as f:
            records = json.load(f)
        fname = os.path.basename(path)
        total += len(records)

        for rec in records:
            stored_id = rec["id"]
            source    = rec.get("source", "")
            s6        = rec.get("sparse6", "")

            try:
                G       = sparse6_to_nx(s6)
                real_id, _ = canonical_id(G)
            except Exception as exc:
                if verbose:
                    print(f"  [ERROR] {fname}/{stored_id}: cannot parse sparse6 ({exc})")
                invalid_ids.append((fname, stored_id, "<parse error>"))
                to_remove.append((fname, stored_id, source))
                continue

            if real_id != stored_id:
                if verbose:
                    print(f"  [INVALID ID] {fname}: stored={stored_id} "
                          f"recomputed={real_id} source={source}")
                invalid_ids.append((fname, stored_id, f"should be {real_id}"))
                to_remove.append((fname, stored_id, source))
                # Use the real id for duplicate tracking
                key = (real_id, source)
            else:
                key = (stored_id, source)

            if key in seen:
                if verbose:
                    print(f"  [DUPLICATE] {fname}: id={stored_id} source={source} "
                          f"(already in {seen[key]})")
                to_remove.append((fname, stored_id, source))
            else:
                seen[key] = fname

    n_invalid   = len(invalid_ids)
    n_duplicate = len(to_remove) - n_invalid  # duplicates beyond invalid

    summary = {
        "total":          total,
        "invalid_id":     n_invalid,
        "duplicate":      max(0, n_duplicate),
        "removed":        0,
        "orphaned_cache": 0,
    }

    if verbose:
        print(f"\nStore: {total} records across {len(store_files)} file(s)")
        print(f"  Invalid IDs : {n_invalid}")
        print(f"  Duplicates  : {max(0, n_duplicate)}")
        print("  (same graph, different source = OK — not flagged)")

    if not fix:
        if verbose and to_remove:
            print("Re-run with --fix to remove bad entries.")
        return summary

    # ── pass 2: rewrite files ─────────────────────────────────────────────────
    # Build set of (fname, stored_id, source) to drop
    drop_set = {(fname, sid, src) for fname, sid, src in to_remove}

    removed = 0
    for path in store_files:
        fname = os.path.basename(path)
        with open(path) as f:
            records = json.load(f)
        clean = [
            r for r in records
            if (fname, r["id"], r.get("source", "")) not in drop_set
        ]
        removed += len(records) - len(clean)
        if len(clean) != len(records):
            with open(path, "w") as f:
                json.dump(clean, f, indent=2)
            if verbose:
                print(f"  Rewrote {fname}: {len(records)} → {len(clean)} records")

    summary["removed"] = removed

    # ── pass 3: drop orphaned cache rows ─────────────────────────────────────
    if os.path.exists(cache_path):
        import sqlite3
        # Build set of valid (id, source) pairs remaining in store
        valid_pairs: set[tuple[str, str]] = set()
        for path in store_files:
            with open(path) as f:
                for r in json.load(f):
                    valid_pairs.add((r["id"], r.get("source", "")))

        conn = sqlite3.connect(cache_path)
        cached_pairs = {(r[0], r[1]) for r in conn.execute(
            "SELECT graph_id, source FROM cache"
        )}
        orphaned = cached_pairs - valid_pairs
        if orphaned:
            for gid, src in orphaned:
                conn.execute(
                    "DELETE FROM cache WHERE graph_id = ? AND source = ?", (gid, src)
                )
            conn.commit()
            summary["orphaned_cache"] = len(orphaned)
            if verbose:
                print(f"  Removed {len(orphaned)} orphaned cache row(s)")
        conn.close()

    if verbose:
        print(f"\nFixed: removed {summary['removed']} store record(s), "
              f"{summary['orphaned_cache']} cache row(s)")

    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--fix",    action="store_true", help="Remove invalid/duplicate entries")
    parser.add_argument("--quiet",  action="store_true", help="Suppress per-entry output")
    parser.add_argument("--graphs", default=DEFAULT_GRAPHS, dest="graphs_dir")
    parser.add_argument("--cache",  default=DEFAULT_CACHE,  dest="cache_path")
    args = parser.parse_args()

    verify_and_fix(
        graphs_dir=args.graphs_dir,
        cache_path=args.cache_path,
        fix=args.fix,
        verbose=not args.quiet,
    )
