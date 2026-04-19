"""
scripts/db_cli.py
=================
Command-line interface to the graph database.

    python scripts/db_cli.py sync   [options]
    python scripts/db_cli.py clean  [options]
    python scripts/db_cli.py add    [options]
    python scripts/db_cli.py query  [options]
    python scripts/db_cli.py rm     [options]
    python scripts/db_cli.py stats

Thin argparse wrappers over the DB methods — no business logic lives
here.
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from graph_db.db import DB, DEFAULT_CACHE, DEFAULT_GRAPHS


# ──────────────────────────────────────────────────────────────────────────────
# helpers
# ──────────────────────────────────────────────────────────────────────────────

def _parse_range(s: str) -> tuple:
    """
    'A..B'  → (A, B)
    '..B'   → (None, B)
    'A..'   → (A, None)
    'A'     → (A, A)
    """
    if ".." not in s:
        v = float(s) if "." in s else int(s)
        return (v, v)
    lo_str, hi_str = s.split("..", 1)
    def _cast(x: str):
        if not x:
            return None
        return float(x) if "." in x else int(x)
    return (_cast(lo_str), _cast(hi_str))


def _parse_kv_list(items: list[str]) -> dict:
    """['alpha=4', 'method=hand'] → {'alpha': 4, 'method': 'hand'} (ints coerced)."""
    out = {}
    for it in items or []:
        if "=" not in it:
            raise SystemExit(f"Bad --meta entry {it!r}, expected KEY=VALUE")
        k, v = it.split("=", 1)
        try:
            out[k] = int(v)
        except ValueError:
            try:
                out[k] = float(v)
            except ValueError:
                out[k] = v
    return out


# ──────────────────────────────────────────────────────────────────────────────
# subcommands
# ──────────────────────────────────────────────────────────────────────────────

def cmd_sync(args):
    with DB(args.graphs_dir, args.cache_path, auto_sync=False) as db:
        summary = db.sync(
            source=args.source,
            recompute=args.recompute,
            dry_run=args.dry_run,
            verbose=True,
        )
    if args.dry_run:
        print(json.dumps(summary, indent=2))


def cmd_clean(args):
    with DB(args.graphs_dir, args.cache_path, auto_sync=False) as db:
        report = db.clean(apply=args.apply, verbose=True)
    print(json.dumps(report.as_dict(), indent=2))


def cmd_add(args):
    from graph_db.encoding import edges_to_nx, sparse6_to_nx

    if args.sparse6:
        G = sparse6_to_nx(args.sparse6)
    elif args.g6:
        import networkx as nx
        G = nx.from_graph6_bytes(args.g6.encode("ascii"))
    elif args.edges:
        edges = json.loads(args.edges)
        if args.n is None:
            raise SystemExit("--edges requires --n")
        G = edges_to_nx(edges, args.n)
    else:
        raise SystemExit("Give one of --sparse6 / --g6 / --edges")

    metadata = _parse_kv_list(args.meta)
    with DB(args.graphs_dir, args.cache_path, auto_sync=False) as db:
        gid, was_new = db.add(G, source=args.source, filename=args.file, **metadata)
        if not was_new:
            print(f"already present: id={gid} source={args.source}")
            return
        print(f"added: id={gid} source={args.source}")
        if not args.no_sync:
            db.sync(source=args.source, verbose=True)


def cmd_query(args):
    filters = {}
    if args.source:
        filters["source"] = args.source
    if args.n:
        filters["n"] = _parse_range(args.n)
    if args.c_log:
        filters["c_log"] = _parse_range(args.c_log)
    if args.alpha:
        filters["alpha"] = _parse_range(args.alpha)
    if args.d_max:
        filters["d_max"] = _parse_range(args.d_max)
    if args.is_regular is not None:
        filters["is_regular"] = args.is_regular
    if args.is_k4_free is not None:
        filters["is_k4_free"] = args.is_k4_free

    order_by = args.order_by
    if order_by is None and args.top is not None:
        order_by = "c_log"

    with DB(args.graphs_dir, args.cache_path, auto_sync=False) as db:
        rows = db.query(
            order_by=order_by,
            limit=args.top or args.limit,
            **filters,
        )

    if not rows:
        print("(no rows)")
        return

    cols = args.columns.split(",") if args.columns else [
        "graph_id", "source", "n", "alpha", "d_max", "c_log", "is_regular",
    ]

    if args.json:
        thin = [{c: r.get(c) for c in cols} for r in rows]
        print(json.dumps(thin, indent=2))
        return

    # TSV output
    print("\t".join(cols))
    for r in rows:
        print("\t".join("" if r.get(c) is None else str(r.get(c)) for c in cols))


def cmd_rm(args):
    if args.graph_id is None and args.source is None:
        raise SystemExit("rm requires --graph-id and/or --source")
    if not args.yes:
        prompt = "Remove records where "
        parts = []
        if args.graph_id: parts.append(f"graph_id={args.graph_id}")
        if args.source:   parts.append(f"source={args.source}")
        prompt += " AND ".join(parts) + "? [y/N] "
        ans = input(prompt).strip().lower()
        if ans != "y":
            print("aborted")
            return
    with DB(args.graphs_dir, args.cache_path, auto_sync=False) as db:
        n = db.remove(graph_id=args.graph_id, source=args.source)
    print(f"removed {n} record(s)")


def cmd_stats(args):
    with DB(args.graphs_dir, args.cache_path, auto_sync=False) as db:
        s = db.stats()
        sources = db.sources()
        per_source = {
            src: db.count(source=src) for src in sources
        }
    print(json.dumps({**s, "per_source": per_source}, indent=2))


# ──────────────────────────────────────────────────────────────────────────────
# main
# ──────────────────────────────────────────────────────────────────────────────

def _add_common(p):
    p.add_argument("--graphs-dir", default=DEFAULT_GRAPHS)
    p.add_argument("--cache-path", default=DEFAULT_CACHE)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="graph_db")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("sync", help="Compute properties for any new (graph, source) pairs")
    _add_common(p)
    p.add_argument("--source", default=None, help="Restrict sync to one source tag")
    p.add_argument("--recompute", action="store_true",
                   help="Force-recompute rows that are already cached")
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(func=cmd_sync)

    p = sub.add_parser("clean", help="Repair canonical forms, dedup, prune cache orphans")
    _add_common(p)
    p.add_argument("--apply", action="store_true",
                   help="Actually rewrite the store (default is dry run)")
    p.set_defaults(func=cmd_clean)

    p = sub.add_parser("add", help="Append one graph to the store")
    _add_common(p)
    p.add_argument("--sparse6", default=None)
    p.add_argument("--g6",      default=None)
    p.add_argument("--edges",   default=None, help="JSON edge list, e.g. [[0,1],[1,2]]")
    p.add_argument("-n", type=int, default=None, help="vertex count (required with --edges)")
    p.add_argument("--source", required=True)
    p.add_argument("--file",   default=None, help="target batch file (defaults to {source}.json)")
    p.add_argument("--meta",   action="append", default=[],
                   help="metadata KEY=VALUE (repeatable)")
    p.add_argument("--no-sync", action="store_true",
                   help="skip cache sync after adding")
    p.set_defaults(func=cmd_add)

    p = sub.add_parser("query", help="Print matching cache rows")
    _add_common(p)
    p.add_argument("--source",      default=None)
    p.add_argument("--n",           default=None, help="scalar or A..B range")
    p.add_argument("--c-log",       default=None)
    p.add_argument("--alpha",       default=None)
    p.add_argument("--d-max",       default=None)
    p.add_argument("--is-regular",  type=int, default=None, choices=[0, 1])
    p.add_argument("--is-k4-free",  type=int, default=None, choices=[0, 1])
    p.add_argument("--order-by",    default=None, help="col (asc) or -col (desc)")
    p.add_argument("--limit",       type=int, default=None)
    p.add_argument("--top",         type=int, default=None,
                   help="shortcut: sort by c_log asc and take first N")
    p.add_argument("--columns",     default=None, help="comma-separated column list")
    p.add_argument("--json",        action="store_true")
    p.set_defaults(func=cmd_query)

    p = sub.add_parser("rm", help="Remove records from store and cache")
    _add_common(p)
    p.add_argument("--graph-id", default=None)
    p.add_argument("--source",   default=None)
    p.add_argument("-y", "--yes", action="store_true", help="skip confirmation")
    p.set_defaults(func=cmd_rm)

    p = sub.add_parser("stats", help="Summary of the database contents")
    _add_common(p)
    p.set_defaults(func=cmd_stats)

    return parser


def main(argv: list[str] | None = None):
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
