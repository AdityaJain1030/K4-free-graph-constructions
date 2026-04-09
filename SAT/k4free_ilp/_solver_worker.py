"""Subprocess worker: runs a single solve_k4free call and writes JSON to stdout.

Usage:
    python -m k4free_ilp._solver_worker <n> <max_alpha> <max_degree> <time_limit>

Output (JSON on stdout):
    {"status": str, "edges": list[list[int]] | null, "stats": dict, "peak_rss_mb": float}
"""

import json
import sys

import psutil


def main():
    n, max_alpha, max_degree, time_limit = (
        int(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]),
    )

    # Redirect stdout to stderr so solver diagnostic prints don't mix with
    # our JSON output.  We restore stdout at the end to emit the result.
    real_stdout = sys.stdout
    sys.stdout = sys.stderr

    from k4free_ilp.ilp_solver import solve_k4free

    status, adj, stats = solve_k4free(n, max_alpha, max_degree, time_limit)

    sys.stdout = real_stdout

    edges = None
    if adj is not None:
        edges = [
            [int(i), int(j)]
            for i in range(n)
            for j in range(i + 1, n)
            if adj[i, j]
        ]

    peak_rss_mb = psutil.Process().memory_info().rss / (1024 ** 2)

    result = {
        "status": status,
        "edges": edges,
        "n": n,
        "stats": stats,
        "peak_rss_mb": round(peak_rss_mb, 1),
    }
    sys.stdout.write(json.dumps(result) + "\n")


if __name__ == "__main__":
    main()
