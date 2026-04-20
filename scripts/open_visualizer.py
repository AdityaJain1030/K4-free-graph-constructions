"""
scripts/open_visualizer.py
==========================
Launch the graph explorer visualizer.

Usage:
    python scripts/open_visualizer.py
    python scripts/open_visualizer.py --source sat_pareto
    python scripts/open_visualizer.py --sync   # sync cache first, then open
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main():
    parser = argparse.ArgumentParser(description="Open the K₄-free graph explorer")
    parser.add_argument("--source", default=None,
                        help="Only show graphs from this source tag")
    parser.add_argument("--sync", action="store_true",
                        help="Sync the property cache before opening (kept for compat; "
                             "sync now runs by default — use --no-sync to skip)")
    parser.add_argument("--no-sync", action="store_true",
                        help="Skip all sync work; open with whatever is already cached")
    parser.add_argument("--workers", type=int, default=8,
                        help="Worker processes for property computation (default 8)")
    parser.add_argument("--alpha-timeout", type=float, default=None,
                        help="Per-graph wall-clock cap (seconds) — records that exceed "
                             "it are logged and skipped so sync never stalls")
    args = parser.parse_args()

    if not args.no_sync:
        from graph_db import DB
        with DB(auto_sync=False) as db:
            db.sync(
                source=args.source,
                verbose=True,
                workers=args.workers,
                per_record_timeout_s=args.alpha_timeout,
            )

    from visualizer.visualizer import App
    App(source_filter=args.source).mainloop()


if __name__ == "__main__":
    main()
