"""
Evaluator for k4free_min_c_alpha.

Fixed alpha budget (ALPHA_MAX), variable N. Runs the evolved
construct() a few times (stochastic), takes the best c_log across
trials, returns a higher-is-better score. Invalid graphs (K4 present,
or alpha > ALPHA_MAX) score 0.

Paper-style piecewise bonus against the known-best c_log at the
specified ALPHA_MAX, so the landscape has a cliff to target.
"""

from __future__ import annotations

import concurrent.futures
import importlib.util
import os
import sys
import time
import traceback

import numpy as np

from openevolve.evaluation_result import EvaluationResult

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from graph_utils import (
    alpha_bb_clique_cover,
    c_log_value,
    has_independent_set,
    is_k4_free,
)


# Known-best c_log per ALPHA_MAX value (from graph_db). Used only for the
# step bonus on matching / beating these targets. Update if new bests
# land in graph_db.
KNOWN_BEST_C_LOG = {
    3: 0.679078,   # Paley(17): N=17, d_max=8
    4: 0.699523,   # N=22, d_max=8 (circulant / Cayley-tabu-gap)
    5: 0.750000,   # placeholder; query graph_db for the real best
    6: 0.800000,   # placeholder
}

# Ramsey-derived hard upper bound on N for each ALPHA_MAX: R(4, s) - 1,
# where s = ALPHA_MAX + 1. Any graph the LLM returns above this MUST
# contain an independent set of size >= ALPHA_MAX + 1 (we'll catch it
# in validation, but knowing the cap is useful for context).
RAMSEY_N_UPPER = {
    3: 17,   # R(4, 4) = 18
    4: 24,   # R(4, 5) = 25
    5: 39,   # R(4, 6) ∈ [35, 41]; 35 is conservative SoTA upper
    6: 57,
}

NUM_TRIALS = 3
PER_TRIAL_TIMEOUT = 30.0
EVAL_TIMEOUT = 120.0


def _run_with_timeout(func, timeout):
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
        fut = ex.submit(func)
        return fut.result(timeout=timeout)


def _alpha_max_from_env() -> int:
    return int(os.environ.get("K4FREE_ALPHA", "4"))


def _score_graph(adj: np.ndarray, alpha_max: int) -> tuple[dict, dict]:
    adj = np.asarray(adj, dtype=np.uint8)
    if adj.ndim != 2 or adj.shape[0] != adj.shape[1] or adj.shape[0] == 0:
        return {"valid": 0.0, "combined_score": 0.0}, {
            "error_type": "BadShape",
            "error_message": f"adj shape {adj.shape}",
        }

    adj = ((adj + adj.T) > 0).astype(np.uint8)
    np.fill_diagonal(adj, 0)
    n = int(adj.shape[0])

    if not is_k4_free(adj):
        return {"valid": 0.0, "combined_score": 0.0, "n": float(n)}, {
            "error_type": "NotK4Free",
            "error_message": "constructed graph contains a K4",
        }

    # Cheap threshold check before computing alpha exactly.
    if has_independent_set(adj, alpha_max + 1):
        return {"valid": 0.0, "combined_score": 0.0, "n": float(n)}, {
            "error_type": "AlphaExceedsBudget",
            "error_message": f"graph has an independent set of size >= {alpha_max + 1}",
        }

    alpha, _ = alpha_bb_clique_cover(adj)
    d_max = int(adj.sum(axis=1).max()) if adj.any() else 0
    c_log = c_log_value(alpha, n, d_max)

    if c_log is None:
        return {
            "valid": 1.0,
            "n": float(n),
            "alpha": float(alpha),
            "d_max": float(d_max),
            "c_log": float("nan"),
            "combined_score": 0.0,
        }, {"note": "d_max <= 1, c_log undefined"}

    # Primary signal: higher is better, shrinks as c_log grows.
    score = max(0.0, 2.0 - float(c_log))

    # Step bonus against the known best for this ALPHA_MAX.
    best = KNOWN_BEST_C_LOG.get(alpha_max)
    if best is not None:
        if c_log < best - 1e-6:
            score *= 4.0   # would break past the literature best
        elif c_log <= best + 1e-6:
            score *= 2.0

    return {
        "valid": 1.0,
        "n": float(n),
        "alpha": float(alpha),
        "d_max": float(d_max),
        "c_log": float(c_log),
        "combined_score": float(score),
    }, {
        "n": str(n),
        "alpha": str(alpha),
        "d_max": str(d_max),
        "c_log": f"{c_log:.6f}",
        "edges": str(int(adj.sum() // 2)),
    }


def _load_program(path):
    spec = importlib.util.spec_from_file_location("program", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _eval_impl(program_path: str, num_trials: int) -> EvaluationResult:
    alpha_max = _alpha_max_from_env()

    try:
        program = _load_program(program_path)
    except Exception as e:
        return EvaluationResult(
            metrics={"valid": 0.0, "combined_score": 0.0, "error": str(e)},
            artifacts={
                "error_type": type(e).__name__,
                "error_message": str(e),
                "full_traceback": traceback.format_exc(),
            },
        )

    if not hasattr(program, "run_search"):
        return EvaluationResult(
            metrics={"valid": 0.0, "combined_score": 0.0, "error": "missing run_search"},
            artifacts={
                "error_type": "MissingFunction",
                "error_message": "program must expose run_search() -> np.ndarray",
            },
        )

    best_metrics = None
    best_artifacts = None
    best_score = -float("inf")
    per_trial = []
    failures = 0

    for t in range(num_trials):
        try:
            start = time.time()
            adj = _run_with_timeout(program.run_search, PER_TRIAL_TIMEOUT)
            elapsed = time.time() - start
        except concurrent.futures.TimeoutError:
            failures += 1
            per_trial.append(f"trial {t}: TIMEOUT")
            continue
        except Exception as e:
            failures += 1
            per_trial.append(f"trial {t}: {type(e).__name__}: {e}")
            continue

        adj = np.asarray(adj)
        metrics, artifacts = _score_graph(adj, alpha_max)
        per_trial.append(
            f"trial {t}: N={int(metrics.get('n', 0))} "
            f"c_log={metrics.get('c_log', float('nan')):.4f} "
            f"score={metrics['combined_score']:.4f} "
            f"({elapsed:.2f}s)"
        )
        if metrics["combined_score"] > best_score:
            best_score = metrics["combined_score"]
            best_metrics = metrics
            best_artifacts = artifacts

    if best_metrics is None:
        return EvaluationResult(
            metrics={"valid": 0.0, "combined_score": 0.0, "error": "all trials failed"},
            artifacts={
                "error_type": "AllTrialsFailed",
                "trials": "\n".join(per_trial),
                "suggestion": "construct(alpha_max) must return an N x N numpy adjacency matrix.",
            },
        )

    best_metrics["reliability"] = float((num_trials - failures) / num_trials)
    best_metrics["alpha_max"] = float(alpha_max)
    best_artifacts = dict(best_artifacts or {})
    best_artifacts["trials"] = "\n".join(per_trial)
    best_artifacts["alpha_max"] = str(alpha_max)
    best_artifacts["ramsey_n_cap"] = str(RAMSEY_N_UPPER.get(alpha_max, "?"))
    return EvaluationResult(metrics=best_metrics, artifacts=best_artifacts)


def evaluate(program_path: str) -> EvaluationResult:
    return _eval_impl(program_path, NUM_TRIALS)


def evaluate_stage1(program_path: str) -> EvaluationResult:
    return _eval_impl(program_path, 1)


def evaluate_stage2(program_path: str) -> EvaluationResult:
    return evaluate(program_path)
