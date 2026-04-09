"""Memory profiler for CP-SAT model: measures peak RSS during actual solving.

Each case runs in a fresh subprocess. A monitor thread polls RSS every 50ms
during a short solver run (10s) to capture the peak after CP-SAT linearizes
constraints into its internal SAT representation.
"""

import gc
import json
import subprocess
import sys
import threading
import time
from itertools import combinations
from math import comb

import numpy as np
import psutil
from ortools.sat.python import cp_model

from k4free_ilp.ilp_solver import _effective_degree_bounds

MEMORY_LIMIT_BYTES = 12 * 1024**3  # 12 GB
SOLVE_SECONDS = 60  # default; overridden per-case for larger instances


def get_rss_mb():
    return psutil.Process().memory_info().rss / (1024**2)


class RSSMonitor:
    """Background thread that polls peak RSS."""
    def __init__(self, interval=0.05):
        self.interval = interval
        self.peak_mb = get_rss_mb()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self):
        self._thread.start()

    def stop(self):
        self._stop.set()
        self._thread.join()
        return self.peak_mb

    def _run(self):
        proc = psutil.Process()
        while not self._stop.is_set():
            rss = proc.memory_info().rss / (1024**2)
            if rss > self.peak_mb:
                self.peak_mb = rss
            if rss > MEMORY_LIMIT_BYTES / (1024**2):
                print(f"KILLED: RSS = {rss:.0f} MB exceeds 12 GB limit",
                      file=sys.stderr, flush=True)
                import os
                os._exit(1)
            self._stop.wait(self.interval)


def _build_model_stages(n, max_alpha, max_degree):
    """Build the CP-SAT model, returning (model, x, edge_vars, stage_rss, metadata)."""
    k = max_alpha + 1
    eff_min, eff_max = _effective_degree_bounds(n, max_alpha, max_degree)

    gc.collect()
    rss_baseline = get_rss_mb()

    model = cp_model.CpModel()

    x = {}
    edge_vars = []
    for i in range(n):
        for j in range(i + 1, n):
            x[(i, j)] = model.new_bool_var(f"x_{i}_{j}")
            edge_vars.append(x[(i, j)])

    rss_after_vars = get_rss_mb()

    num_k4 = comb(n, 4)
    for a, b, c, d in combinations(range(n), 4):
        model.add(
            x[(a, b)] + x[(a, c)] + x[(a, d)]
            + x[(b, c)] + x[(b, d)] + x[(c, d)] <= 5
        )

    rss_after_k4 = get_rss_mb()

    for i in range(n):
        incident = [x[(min(i, j), max(i, j))] for j in range(n) if j != i]
        model.add(sum(incident) <= eff_max)
        if eff_min > 0:
            model.add(sum(incident) >= eff_min)

    if n <= 15:
        for i in range(n - 1):
            inc_i = [x[(min(i, j), max(i, j))] for j in range(n) if j != i]
            inc_next = [x[(min(i + 1, j), max(i + 1, j))] for j in range(n) if j != i + 1]
            model.add(sum(inc_i) >= sum(inc_next))

    rss_after_deg = get_rss_mb()

    num_alpha = comb(n, k) if k <= n else 0
    if k <= n:
        for subset in combinations(range(n), k):
            edges_in_subset = []
            for ii in range(len(subset)):
                for jj in range(ii + 1, len(subset)):
                    edges_in_subset.append(x[(subset[ii], subset[jj])])
            model.add(sum(edges_in_subset) >= 1)

    rss_after_alpha = get_rss_mb()

    model.add_decision_strategy(
        edge_vars, cp_model.CHOOSE_FIRST, cp_model.SELECT_MAX_VALUE,
    )

    stages = {
        "baseline": rss_baseline,
        "after_vars": rss_after_vars,
        "after_k4": rss_after_k4,
        "after_deg": rss_after_deg,
        "after_alpha": rss_after_alpha,
    }
    meta = {
        "num_k4": num_k4,
        "num_alpha": num_alpha,
        "num_constraints": len(model.proto.constraints),
    }
    return model, x, edge_vars, stages, meta


def profile_single(n, max_alpha, max_degree, solve_time=None):
    """Profile one case. Prints JSON result to stdout."""
    if solve_time is None:
        solve_time = SOLVE_SECONDS

    model, x, edge_vars, stages, meta = _build_model_stages(n, max_alpha, max_degree)

    rss_baseline = stages["baseline"]
    k4_model_mb = stages["after_k4"] - stages["after_vars"]
    alpha_model_mb = stages["after_alpha"] - stages["after_deg"]
    model_total_mb = stages["after_alpha"] - rss_baseline

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = solve_time
    solver.parameters.num_workers = 8

    monitor = RSSMonitor(interval=0.05)
    monitor.start()
    solver.solve(model)
    peak_solve_mb = monitor.stop()

    solve_peak_mb = peak_solve_mb - rss_baseline
    overhead = solve_peak_mb / model_total_mb if model_total_mb > 0 else 0

    result = {
        "n": n,
        "alpha_target": max_alpha,
        "D": max_degree,
        "num_k4": meta["num_k4"],
        "num_alpha": meta["num_alpha"],
        "num_constraints": meta["num_constraints"],
        "k4_model_MB": round(k4_model_mb, 1),
        "alpha_model_MB": round(alpha_model_mb, 1),
        "model_MB": round(model_total_mb, 1),
        "peak_solve_MB": round(solve_peak_mb, 1),
        "overhead_x": round(overhead, 1),
    }
    print(json.dumps(result))


def timeseries_single(n, max_alpha, max_degree, solve_time):
    """Run solver and print RSS every 5 seconds to stderr."""
    model, x, edge_vars, stages, meta = _build_model_stages(n, max_alpha, max_degree)

    rss_baseline = stages["baseline"]
    model_mb = stages["after_alpha"] - rss_baseline
    print(f"n={n} α≤{max_alpha} D={max_degree}  model={model_mb:.0f} MB  "
          f"constraints={meta['num_constraints']}  solving for {solve_time}s ...",
          file=sys.stderr, flush=True)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = solve_time
    solver.parameters.num_workers = 8

    # Monitor with time-stamped output
    samples = []
    stop_event = threading.Event()
    t0 = time.time()

    def monitor_loop():
        proc = psutil.Process()
        while not stop_event.is_set():
            elapsed = time.time() - t0
            rss = proc.memory_info().rss / (1024**2) - rss_baseline
            samples.append((round(elapsed, 1), round(rss, 1)))
            print(f"  t={elapsed:6.1f}s  rss={rss:8.1f} MB ({rss/1024:.2f} GB)",
                  file=sys.stderr, flush=True)
            if rss > MEMORY_LIMIT_BYTES / (1024**2):
                print(f"KILLED at t={elapsed:.0f}s: {rss:.0f} MB", file=sys.stderr)
                import os
                os._exit(1)
            stop_event.wait(2.0)

    t = threading.Thread(target=monitor_loop, daemon=True)
    t.start()
    status = solver.solve(model)
    wall = time.time() - t0
    stop_event.set()
    t.join()
    status_name = {0: "UNKNOWN", 1: "MODEL_INVALID", 2: "FEASIBLE",
                   3: "INFEASIBLE", 4: "OPTIMAL"}.get(status, str(status))
    print(f"\nSolver returned {status_name} after {wall:.1f}s", file=sys.stderr)

    # Print time series
    print(f"\n{'time_s':>7} {'rss_MB':>10} {'rss_GB':>8}", file=sys.stderr)
    for elapsed, rss in samples:
        print(f"{elapsed:>7.1f} {rss:>10.1f} {rss/1024:>8.2f}", file=sys.stderr)

    peak = max(rss for _, rss in samples)
    print(f"\nPeak: {peak:.0f} MB ({peak/1024:.2f} GB)", file=sys.stderr)
    # Output JSON for parsing
    print(json.dumps({"n": n, "peak_MB": round(peak, 1), "samples": samples}))


def run_in_subprocess(n, max_alpha, max_degree, solve_time=None):
    """Run profile_single in a fresh subprocess for clean memory measurement."""
    cmd = [
        sys.executable, "-m", "k4free_ilp.memory_profile",
        "--single", str(n), str(max_alpha), str(max_degree),
    ]
    if solve_time is not None:
        cmd += ["--solve-time", str(solve_time)]
    timeout = (solve_time or SOLVE_SECONDS) + 120
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if proc.returncode != 0:
        stderr = proc.stderr.strip().split("\n")[-3:]
        print(f"  FAILED (exit {proc.returncode}): {'  '.join(stderr)}", flush=True)
        return None
    lines = [l for l in proc.stdout.strip().split("\n") if l.strip()]
    return json.loads(lines[-1])


def main():
    solve_time_override = None
    if "--solve-time" in sys.argv:
        idx = sys.argv.index("--solve-time")
        solve_time_override = int(sys.argv[idx+1])

    if "--single" in sys.argv:
        idx = sys.argv.index("--single")
        n, alpha, D = int(sys.argv[idx+1]), int(sys.argv[idx+2]), int(sys.argv[idx+3])
        profile_single(n, alpha, D, solve_time=solve_time_override)
        return

    if "--timeseries" in sys.argv:
        idx = sys.argv.index("--timeseries")
        n, alpha, D = int(sys.argv[idx+1]), int(sys.argv[idx+2]), int(sys.argv[idx+3])
        st = solve_time_override or 300
        timeseries_single(n, alpha, D, st)
        return

    # (n, alpha, D, solve_seconds) — longer solves for bigger instances
    cases = [
        (15, 4,  7,  60),
        (17, 4,  8,  60),
        (19, 4, 10,  60),
        (20, 5, 10,  60),
        (21, 5, 11,  60),
        (22, 5, 11,  60),
        (23, 5, 11, 120),
        (25, 4, 13, 300),
        (28, 5, 14, 120),
        (30, 5, 15, 120),
        (32, 5, 16, 180),
    ]

    results = []
    for n, alpha, D, st in cases:
        print(f"Profiling n={n}, α≤{alpha}, D={D} (build + {st}s solve) ...",
              flush=True)
        r = run_in_subprocess(n, alpha, D, solve_time=st)
        if r is None:
            continue
        results.append(r)
        print(f"  model={r['model_MB']:.0f} MB  peak_solve={r['peak_solve_MB']:.0f} MB  "
              f"overhead={r['overhead_x']:.1f}x", flush=True)

    # Print table
    print()
    hdr = (f"{'n':>3} {'α':>3} {'D':>3} {'C(n,4)':>8} {'C(n,k+1)':>10} "
           f"{'k4_MB':>7} {'α_MB':>7} {'model_MB':>9} {'peak_MB':>9} {'overhead':>8}")
    print(hdr)
    print("-" * len(hdr))
    for r in results:
        print(f"{r['n']:>3} {r['alpha_target']:>3} {r['D']:>3} "
              f"{r['num_k4']:>8} {r['num_alpha']:>10} "
              f"{r['k4_model_MB']:>7.1f} {r['alpha_model_MB']:>7.1f} "
              f"{r['model_MB']:>9.1f} {r['peak_solve_MB']:>9.1f} "
              f"{r['overhead_x']:>7.1f}x")

    if len(results) < 3:
        print("Not enough data points for fitting.")
        return

    # Fit models to PEAK solve memory (the real bottleneck)
    print("\n=== Memory Scaling Models (peak RSS during solve) ===\n")

    ns = np.array([r["n"] for r in results], dtype=float)
    peaks = np.array([r["peak_solve_MB"] for r in results], dtype=float)

    # Polynomial fit (degree 3)
    poly_coeffs = np.polyfit(ns, peaks, 3)
    poly = np.poly1d(poly_coeffs)
    print(f"Polynomial (deg 3): {poly}")

    # Exponential fit: log(peak) = a*n + b
    log_peaks = np.log(peaks)
    exp_coeffs = np.polyfit(ns, log_peaks, 1)
    a_exp, b_exp = exp_coeffs
    print(f"Exponential: peak_MB = {np.exp(b_exp):.6f} * exp({a_exp:.4f} * n)")

    # Residuals
    print(f"\nFit residuals (actual vs predicted):")
    print(f"{'n':>3} {'actual_MB':>10} {'poly_MB':>10} {'exp_MB':>10}")
    for i, r in enumerate(results):
        n_i = r["n"]
        actual = r["peak_solve_MB"]
        p = poly(n_i)
        e = np.exp(b_exp) * np.exp(a_exp * n_i)
        print(f"{n_i:>3} {actual:>10.1f} {p:>10.1f} {e:>10.1f}")

    # Extrapolate
    targets = [23, 25, 28, 30, 35]
    print(f"\n{'n':>3} {'poly_GB':>10} {'exp_GB':>10}")
    print("-" * 27)
    for nt in targets:
        p_mb = poly(nt)
        e_mb = np.exp(b_exp) * np.exp(a_exp * nt)
        print(f"{nt:>3} {p_mb/1024:>10.2f} {e_mb/1024:>10.2f}")

    # Max n for 100 GB (peak solve RSS must fit in 100 GB)
    budget_mb = 100 * 1024
    print(f"\nMax n for 100 GB RAM (peak solve RSS):")
    for label, model_fn in [("Polynomial", lambda n: poly(n)),
                             ("Exponential", lambda n: np.exp(b_exp) * np.exp(a_exp * n))]:
        n_test = float(ns[-1])
        while model_fn(n_test) < budget_mb and n_test < 200:
            n_test += 0.5
        n_test -= 0.5
        n_int = int(n_test)
        peak_at_n = model_fn(n_int)
        print(f"  {label}: max n ≈ {n_int}  (peak ≈ {peak_at_n/1024:.1f} GB)")


if __name__ == "__main__":
    main()
