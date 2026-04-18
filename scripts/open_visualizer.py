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
                        help="Sync the property cache before opening")
    args = parser.parse_args()

    if args.sync:
        from graph_db.store import GraphDB
        REPO_ROOT  = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        db = GraphDB(
            os.path.join(REPO_ROOT, "graphs"),
            os.path.join(REPO_ROOT, "cache.db"),
        )
        db.sync(show_progress=True)
        db.close()

    from visualizer.visualizer import App
    App(source_filter=args.source).mainloop()


if __name__ == "__main__":
    main()
