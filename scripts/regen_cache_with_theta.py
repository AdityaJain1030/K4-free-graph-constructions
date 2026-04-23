"""
Regenerate the property cache after adding the lovasz_theta column.

Calls DB.sync(recompute=True) with parallel workers and a per-record
timeout so a single pathological graph can't block the run. Existing
cache.db is ALTER'd to add lovasz_theta on first open.
"""
from __future__ import annotations

import os
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from graph_db import DB  # noqa: E402


def main():
    t0 = time.time()
    with DB(auto_sync=False) as db:
        print(f"[regen] cache before: {db.cache.count()} rows")
        summary = db.sync(
            recompute=True,
            verbose=True,
            workers=4,
            per_record_timeout_s=180.0,
        )
        print(f"[regen] summary: {summary}")
        print(f"[regen] cache after:  {db.cache.count()} rows")
        # quick sanity: how many have lovasz_theta filled?
        n_filled = db.cache.raw_execute(
            "SELECT COUNT(*) AS c FROM cache WHERE lovasz_theta IS NOT NULL"
        )[0]["c"]
        n_total = db.cache.count()
        print(f"[regen] lovasz_theta filled: {n_filled}/{n_total}")
    print(f"[regen] elapsed: {time.time()-t0:.1f}s")


if __name__ == "__main__":
    main()
