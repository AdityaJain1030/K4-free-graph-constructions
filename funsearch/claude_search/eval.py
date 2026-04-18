#!/usr/bin/env python3
"""Oracle for K4-free graph constructions.

Evaluates a candidate file's construct(N) function across a cascade of N values,
computes c = alpha*d_max/(N*ln(d_max)), and appends a full record to results.jsonl.

Never crashes on adversarial candidates: all execution is sandboxed via
multiprocessing with timeouts, and all exceptions produce a valid failure record.

Usage:
  python eval.py candidates/gen_001_paley_tiling.py
  python eval.py candidates/gen_001_paley_tiling.py --quick
  python eval.py candidates/gen_001_paley_tiling.py --full
"""

import argparse
import datetime as dt
import importlib.util
import json
import math
import multiprocessing as mp
import os
import sys
import time
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from graph_utils import (
    compute_alpha,
    compute_c_value,
    edges_to_adj,
    graph_metrics,
    is_k4_free,
)


RESULTS_PATH = HERE / "results.jsonl"

N_FAST = list(range(7, 61))  # every integer N in [7, 60]
N_ALL = [20, 21, 24, 25, 27, 30, 33, 35, 36, 39, 40, 42, 45, 48, 50,
         51, 54, 55, 57, 60, 63, 65, 66, 69, 70, 72, 75, 78, 80, 81,
         84, 85, 87, 90, 93, 95, 96, 99, 100]
STAGE1_THRESHOLD = 1.5
STAGE2_MAX_DEFAULT = 75
CONSTRUCT_TIMEOUT_S = 5.0
PALEY_17_BASELINE = 0.6789


def _alpha_timeout_for(N):
    if N <= 30:
        return 10
    if N <= 50:
        return 20
    if N <= 75:
        return 45
    return 60


def _construct_worker(module_path, N, q):
    """Subprocess worker: import the candidate and call construct(N)."""
    try:
        spec = importlib.util.spec_from_file_location("_cand", module_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        if not hasattr(mod, "construct"):
            q.put(("error", "construct_not_found: module has no construct()"))
            return
        edges = mod.construct(N)
        # Normalize to list of 2-tuples of ints (serializable across pipe).
        if isinstance(edges, (list, tuple)):
            norm = []
            for e in edges:
                try:
                    i, j = e
                    norm.append((int(i), int(j)))
                except Exception:
                    q.put(("error", f"invalid_edge_format: element {e!r} is not a 2-tuple of ints"))
                    return
            q.put(("ok", norm))
        else:
            q.put(("error", f"invalid_edge_format: return type {type(edges).__name__}"))
    except Exception as e:
        tb = traceback.format_exc(limit=3)
        q.put(("error", f"crash: {type(e).__name__}: {e}\n{tb}"))


def run_construct(module_path, N, timeout=CONSTRUCT_TIMEOUT_S):
    """Run construct(N) in a subprocess. Returns (edges_or_None, failure_reason_or_None)."""
    ctx = mp.get_context("spawn")
    q = ctx.Queue()
    p = ctx.Process(target=_construct_worker, args=(str(module_path), N, q))
    p.start()
    p.join(timeout)
    if p.is_alive():
        p.terminate()
        p.join(1.0)
        if p.is_alive():
            p.kill()
            p.join()
        return None, "timeout"
    try:
        status, payload = q.get_nowait()
    except Exception:
        return None, f"crash: no result returned (exitcode={p.exitcode})"
    if status == "ok":
        return payload, None
    return None, payload


def evaluate_at_N(module_path, N):
    """Evaluate construct(N) and compute all metrics. Returns per-N dict."""
    rec = {
        "N": N,
        "d_max": None,
        "d_min": None,
        "d_mean": None,
        "degree_variance": None,
        "regularity_score": None,
        "alpha": None,
        "alpha_exact": None,
        "c": float("inf"),
        "edge_count": None,
        "triangle_count": None,
        "is_connected": None,
        "failure_reason": None,
        "eval_time_s": None,
        "degree_sequence": None,
    }
    t0 = time.time()
    edges, reason = run_construct(module_path, N)
    if reason is not None:
        rec["failure_reason"] = reason
        rec["eval_time_s"] = round(time.time() - t0, 3)
        return rec

    # Validate format + build metrics
    try:
        metrics = graph_metrics(edges, N)
    except ValueError as e:
        rec["failure_reason"] = f"invalid_edge_format: {e}"
        rec["eval_time_s"] = round(time.time() - t0, 3)
        return rec
    except Exception as e:
        rec["failure_reason"] = f"crash: {type(e).__name__}: {e}"
        rec["eval_time_s"] = round(time.time() - t0, 3)
        return rec

    for k in ("d_max", "d_min", "d_mean", "degree_variance", "regularity_score",
              "edge_count", "triangle_count", "is_connected", "degree_sequence"):
        rec[k] = metrics[k]

    if metrics["d_max"] < 2:
        rec["failure_reason"] = "d_max_too_low"
        rec["eval_time_s"] = round(time.time() - t0, 3)
        return rec

    try:
        adj = edges_to_adj(edges, N)
        if not is_k4_free(adj):
            rec["failure_reason"] = "not_k4_free"
            rec["eval_time_s"] = round(time.time() - t0, 3)
            return rec
    except Exception as e:
        rec["failure_reason"] = f"crash_in_k4_check: {type(e).__name__}: {e}"
        rec["eval_time_s"] = round(time.time() - t0, 3)
        return rec

    # Compute alpha
    try:
        alpha, exact, _ = compute_alpha(edges, N, timeout=_alpha_timeout_for(N))
    except Exception as e:
        rec["failure_reason"] = f"alpha_crash: {type(e).__name__}: {e}"
        rec["eval_time_s"] = round(time.time() - t0, 3)
        return rec

    rec["alpha"] = int(alpha)
    rec["alpha_exact"] = bool(exact)
    rec["c"] = float(compute_c_value(alpha, N, metrics["d_max"]))
    rec["eval_time_s"] = round(time.time() - t0, 3)
    return rec


def extract_gen_id(path):
    name = Path(path).stem
    return name


def extract_construct_body_length(source):
    """Character count of the construct() function body (signature excluded)."""
    try:
        import ast
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "construct":
                lines = source.splitlines()
                first = node.body[0].lineno - 1
                last = node.body[-1].end_lineno
                body = "\n".join(lines[first:last])
                return len(body)
    except Exception:
        pass
    return len(source)


def format_table(rows, headers):
    widths = [len(h) for h in headers]
    str_rows = []
    for r in rows:
        cells = []
        for v, h in zip(r, headers):
            if v is None:
                s = "-"
            elif isinstance(v, float):
                if math.isinf(v):
                    s = "inf"
                else:
                    s = f"{v:.4f}"
            else:
                s = str(v)
            cells.append(s)
        str_rows.append(cells)
        for i, s in enumerate(cells):
            widths[i] = max(widths[i], len(s))
    lines = []
    lines.append("  ".join(h.ljust(widths[i]) for i, h in enumerate(headers)))
    lines.append("  ".join("-" * widths[i] for i in range(len(headers))))
    for r in str_rows:
        lines.append("  ".join(r[i].ljust(widths[i]) for i in range(len(headers))))
    return "\n".join(lines)


def print_per_N_table(per_N, N_list, title):
    print(f"\n{title}")
    rows = []
    for N in N_list:
        r = per_N.get(str(N)) or per_N.get(N)
        if r is None:
            continue
        rows.append([
            N, r["d_max"], r["d_min"], r["regularity_score"],
            r["alpha"], r["alpha_exact"], r["c"],
        ])
    print(format_table(rows, ["N", "d_max", "d_min", "regularity", "alpha", "exact", "c"]))


def main():
    parser = argparse.ArgumentParser(description="Evaluate a K4-free graph construction.")
    parser.add_argument("candidate", help="Path to candidate .py file with construct(N)")
    parser.add_argument("--quick", action="store_true", help="Only Stage 1 (N_FAST)")
    parser.add_argument("--full", action="store_true", help="Force Stage 2 up to N=100")
    parser.add_argument("--stage2-max", type=int, default=STAGE2_MAX_DEFAULT,
                        help="Max N for Stage 2 (default 75; --full overrides to 100)")
    parser.add_argument("--threshold", type=float, default=STAGE1_THRESHOLD,
                        help="Mean c threshold to trigger Stage 2 (default 1.5)")
    args = parser.parse_args()

    record = _run(args)
    # Always append
    try:
        with open(RESULTS_PATH, "a") as f:
            f.write(json.dumps(record, default=_json_default) + "\n")
    except Exception as e:
        print(f"WARNING: could not append to {RESULTS_PATH}: {e}", file=sys.stderr)


def _json_default(o):
    if isinstance(o, float) and math.isinf(o):
        return "Infinity" if o > 0 else "-Infinity"
    return str(o)


def _run(args):
    path = Path(args.candidate)
    gen_id = extract_gen_id(path)
    timestamp = dt.datetime.now(dt.timezone.utc).isoformat()

    # Read source; never crash on missing file
    source_code = ""
    code_length = 0
    try:
        source_code = path.read_text()
        code_length = extract_construct_body_length(source_code)
    except Exception as e:
        source_code = ""
        code_length = 0
        print(f"FAIL: could not read {path}: {e}")
        return {
            "gen_id": gen_id, "timestamp": timestamp, "source_code": "",
            "code_length": 0, "score": float("inf"), "score_regularity": 0.0,
            "score_full": None, "best_c": float("inf"), "best_c_N": None,
            "stage1_passed": False, "per_N": {},
            "failure_reason": f"read_error: {e}",
        }

    # Syntax check early
    try:
        compile(source_code, str(path), "exec")
    except SyntaxError as e:
        print(f"FAIL: SyntaxError in {path}: {e}")
        record = _build_record(gen_id, timestamp, source_code, code_length,
                               per_N={}, stage1_passed=False, stage2_ran=False,
                               global_failure=f"syntax_error: {e}")
        _print_summary(record, stage1_ran=False, stage2_ran=False)
        return record

    # Stage 1
    per_N = {}
    print(f"Evaluating {gen_id} (Stage 1: N={N_FAST})...")
    stage1_ran = True
    for N in N_FAST:
        print(f"  N={N}...", end=" ", flush=True)
        r = evaluate_at_N(path, N)
        per_N[str(N)] = r
        c = r["c"]
        fr = r["failure_reason"]
        print(f"c={c:.4f}" if math.isfinite(c) else f"FAIL({fr})")

    stage1_finite_c = [per_N[str(N)]["c"] for N in N_FAST
                       if math.isfinite(per_N[str(N)]["c"])]
    mean_stage1 = sum(stage1_finite_c) / len(stage1_finite_c) if stage1_finite_c else float("inf")
    stage1_passed = math.isfinite(mean_stage1) and mean_stage1 < args.threshold

    # Stage 2 decision
    stage2_N = []
    if args.quick:
        stage2_ran = False
    elif args.full:
        stage2_N = [N for N in N_ALL if N not in N_FAST and N <= 100]
        stage2_ran = True
    elif stage1_passed:
        stage2_N = [N for N in N_ALL if N not in N_FAST and N <= args.stage2_max]
        stage2_ran = True
    else:
        stage2_ran = False

    if stage2_ran and stage2_N:
        print(f"\nStage 2 triggered (mean Stage1 c={mean_stage1:.4f}). Evaluating N={stage2_N}...")
        for N in stage2_N:
            print(f"  N={N}...", end=" ", flush=True)
            r = evaluate_at_N(path, N)
            per_N[str(N)] = r
            c = r["c"]
            fr = r["failure_reason"]
            print(f"c={c:.4f}" if math.isfinite(c) else f"FAIL({fr})")

    record = _build_record(gen_id, timestamp, source_code, code_length,
                           per_N=per_N, stage1_passed=stage1_passed,
                           stage2_ran=stage2_ran)
    _print_summary(record, stage1_ran=True, stage2_ran=stage2_ran)
    return record


def _build_record(gen_id, timestamp, source_code, code_length,
                  per_N, stage1_passed, stage2_ran, global_failure=None):
    stage1_cs = [per_N[str(N)]["c"] for N in N_FAST
                 if str(N) in per_N and math.isfinite(per_N[str(N)]["c"])]
    all_cs = [(int(k), v["c"]) for k, v in per_N.items() if math.isfinite(v["c"])]
    regularities = [v["regularity_score"] for v in per_N.values()
                    if v.get("regularity_score") is not None
                    and math.isfinite(v["c"])]

    if stage1_cs:
        score = sum(stage1_cs) / len(stage1_cs) + 0.001 * code_length
    else:
        score = float("inf")

    if len(per_N) > len(N_FAST) and all_cs:
        full_cs = [c for _, c in all_cs]
        score_full = sum(full_cs) / len(full_cs) + 0.001 * code_length
    else:
        score_full = None

    score_regularity = sum(regularities) / len(regularities) if regularities else 0.0

    if all_cs:
        best_N, best_c = min(all_cs, key=lambda x: x[1])
    else:
        best_N, best_c = None, float("inf")

    rec = {
        "gen_id": gen_id,
        "timestamp": timestamp,
        "source_code": source_code,
        "code_length": code_length,
        "score": score,
        "score_regularity": score_regularity,
        "score_full": score_full,
        "best_c": best_c,
        "best_c_N": best_N,
        "stage1_passed": stage1_passed,
        "stage2_ran": stage2_ran,
        "per_N": per_N,
    }
    if global_failure is not None:
        rec["failure_reason"] = global_failure
    return rec


def _print_summary(record, stage1_ran, stage2_ran):
    print()
    s = record["score"]
    bc = record["best_c"]
    bN = record["best_c_N"]
    verdict = "PASS" if math.isfinite(s) else "FAIL"
    print(f"=== {verdict} | {record['gen_id']} | score={s if not math.isfinite(s) else f'{s:.4f}'} | best_c={bc if not math.isfinite(bc) else f'{bc:.4f}'} @ N={bN} ===")

    per_N = record["per_N"]
    if stage1_ran and per_N:
        print_per_N_table(per_N, N_FAST, "Stage 1:")
    if stage2_ran:
        stage2_N = sorted(int(k) for k in per_N.keys() if int(k) not in N_FAST)
        if stage2_N:
            print_per_N_table(per_N, stage2_N, "Stage 2:")

    # Failure diagnostics
    fails = [(int(N), r["failure_reason"]) for N, r in per_N.items()
             if r.get("failure_reason")]
    if fails:
        print("\nFailures:")
        for N, fr in sorted(fails):
            print(f"  N={N}: {fr.splitlines()[0] if fr else '?'}")

    # Baseline comparison
    if math.isfinite(bc):
        pct = 100.0 * bc / PALEY_17_BASELINE
        print(f"\nP(17) achieves c={PALEY_17_BASELINE}. Your best c={bc:.4f} at N={bN} ({pct:.1f}% of baseline).")
    else:
        print("\nNo finite c achieved. (P(17) baseline: 0.6789)")

    # Regularity summary
    regs = [r["regularity_score"] for r in per_N.values()
            if r.get("regularity_score") is not None and math.isfinite(r["c"])]
    if regs:
        mean_reg = sum(regs) / len(regs)
        perfect = sum(1 for x in regs if x >= 0.999)
        print(f"Regularity: mean={mean_reg:.3f}, perfectly regular at {perfect}/{len(regs)} valid N values.")


if __name__ == "__main__":
    main()
