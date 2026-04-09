"""Subprocess worker: runs a single solve_k4free call and writes JSON to stdout.

Usage:
    python -m k4free_ilp._solver_worker <n> <max_alpha> <max_degree> <time_limit> [--workers N]

Output (JSON on stdout):
    {"status": str, "edges": list[list[int]] | null, "stats": dict, "peak_rss_mb": float}
"""

import json
import sys

import psutil


def main():
    args = sys.argv[1:]

    workers = 8
    if "--workers" in args:
        idx = args.index("--workers")
        workers = int(args[idx + 1])
        args = args[:idx] + args[idx + 2:]

    n, max_alpha, max_degree, time_limit = (
        int(args[0]), int(args[1]), int(args[2]), int(args[3]),
    )

    # Redirect stdout to stderr so solver diagnostic prints don't mix with
    # our JSON output.  We restore stdout at the end to emit the result.
    real_stdout = sys.stdout
    sys.stdout = sys.stderr

    # Patch solver worker count before importing solve_k4free
    import k4free_ilp.ilp_solver as _solver_mod
    _orig = _solver_mod._solve_and_extract

    def _patched(model, x, n_inner, tl):
        from ortools.sat.python import cp_model as cpm
        solver = cpm.CpSolver()
        solver.parameters.max_time_in_seconds = tl
        solver.parameters.num_workers = workers
        import time as _t
        t0 = _t.time()
        result_status = solver.solve(model)
        solve_time = _t.time() - t0
        if result_status in (cpm.OPTIMAL, cpm.FEASIBLE):
            import numpy as _np
            adj_inner = _np.zeros((n_inner, n_inner), dtype=_np.uint8)
            for (i, j), var in x.items():
                if solver.value(var):
                    adj_inner[i, j] = adj_inner[j, i] = 1
            return "FEASIBLE", adj_inner, solve_time
        elif result_status == cpm.INFEASIBLE:
            return "INFEASIBLE", None, solve_time
        else:
            return "TIMEOUT", None, solve_time

    _solver_mod._solve_and_extract = _patched

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
