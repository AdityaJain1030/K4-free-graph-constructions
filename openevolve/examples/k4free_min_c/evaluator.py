"""
Evaluator for k4free_min_c.

Runs the evolved `construct(N)` a few times (it is stochastic), takes
the best c_log across trials, and returns a higher-is-better score.

Adapted from the AlphaEvolve-Ramsey scoring of the Nagda et al. paper,
but simplified per the MVP spec:
  - N is fixed per run (via K4FREE_N env var, read by initial_program).
  - No "prospect graph G2" bonus — scalar reward from the single graph.
  - Piecewise boost kept: matching / beating the known optimum earns a
    step jump, so the landscape has a cliff the LLM can actually target.
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

# Make the vendored graph helpers importable regardless of how the
# evaluator is invoked (openevolve worker processes cwd-hop).
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from graph_utils import alpha_bb_clique_cover, is_k4_free, c_log_value


# Known SAT-certified optima (from graph_db). Used only for the step
# bonus, not for the primary gradient.
KNOWN_OPTIMUM_C_LOG = {
    14: 0.717571,
    15: 0.719458,
}

NUM_TRIALS = 3              # construct() is stochastic; best-of-k
PER_TRIAL_TIMEOUT = 20.0    # seconds
EVAL_TIMEOUT = 60.0         # overall


def _run_with_timeout(func, timeout):
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
        fut = ex.submit(func)
        return fut.result(timeout=timeout)


def _score_graph(adj: np.ndarray) -> tuple[dict, dict]:
    """Return (metrics, artifacts) for one constructed graph."""
    n = int(adj.shape[0])

    # Symmetrise / sanitise.
    adj = np.asarray(adj, dtype=np.uint8)
    if adj.shape != (n, n):
        return {"valid": 0.0, "combined_score": 0.0}, {
            "error_type": "BadShape",
            "error_message": f"adj shape {adj.shape} != ({n},{n})",
        }
    adj = ((adj + adj.T) > 0).astype(np.uint8)
    np.fill_diagonal(adj, 0)

    if not is_k4_free(adj):
        return {"valid": 0.0, "combined_score": 0.0}, {
            "error_type": "NotK4Free",
            "error_message": "constructed graph contains a K4",
        }

    d_max = int(adj.sum(axis=1).max()) if adj.any() else 0
    alpha, _ = alpha_bb_clique_cover(adj)
    c_log = c_log_value(alpha, n, d_max)

    if c_log is None:
        # d_max <= 1 — degenerate; penalise.
        return {
            "valid": 1.0,
            "alpha": float(alpha),
            "d_max": float(d_max),
            "c_log": float("nan"),
            "combined_score": 0.0,
        }, {"note": "d_max <= 1, c_log undefined"}

    # Primary signal: higher-is-better reward that grows as c_log shrinks.
    # c_log lives in ~[0.67, 1.5] for these N, so `2 - c_log` keeps the
    # score positive and roughly in [0.5, 1.3].
    score = max(0.0, 2.0 - float(c_log))

    # Step bonus near the known optimum (AlphaEvolve-style cliff).
    optimum = KNOWN_OPTIMUM_C_LOG.get(n)
    if optimum is not None:
        if c_log < optimum - 1e-6:
            score *= 4.0   # would beat a SAT-certified optimum — impossible,
                            #   but keeps the gradient well-defined just in case.
        elif c_log <= optimum + 1e-6:
            score *= 2.0   # matched the optimum.

    return {
        "valid": 1.0,
        "alpha": float(alpha),
        "d_max": float(d_max),
        "c_log": float(c_log),
        "combined_score": float(score),
    }, {
        "c_log": f"{c_log:.6f}",
        "alpha": str(alpha),
        "d_max": str(d_max),
        "edges": str(int(adj.sum() // 2)),
    }


def _load_program(program_path: str):
    spec = importlib.util.spec_from_file_location("program", program_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _eval_impl(program_path: str, num_trials: int) -> EvaluationResult:
    try:
        program = _load_program(program_path)
    except Exception as e:
        return EvaluationResult(
            metrics={"valid": 0.0, "combined_score": 0.0, "error": str(e)},
            artifacts={
                "error_type": type(e).__name__,
                "error_message": str(e),
                "full_traceback": traceback.format_exc(),
                "suggestion": "Syntax or import error in the evolved program.",
            },
        )

    if not hasattr(program, "run_search"):
        return EvaluationResult(
            metrics={"valid": 0.0, "combined_score": 0.0, "error": "missing run_search"},
            artifacts={
                "error_type": "MissingFunction",
                "error_message": "program must expose run_search() returning an adjacency matrix",
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
        metrics, artifacts = _score_graph(adj)
        per_trial.append(
            f"trial {t}: c_log={metrics.get('c_log', float('nan')):.4f} "
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
                "suggestion": "construct(N) must return an N x N numpy adjacency matrix.",
            },
        )

    best_metrics["reliability"] = float((num_trials - failures) / num_trials)
    best_artifacts = dict(best_artifacts or {})
    best_artifacts["trials"] = "\n".join(per_trial)
    return EvaluationResult(metrics=best_metrics, artifacts=best_artifacts)


# --- public entry points -----------------------------------------------------

def evaluate(program_path: str) -> EvaluationResult:
    """Full evaluation — best of NUM_TRIALS."""
    return _eval_impl(program_path, NUM_TRIALS)


def evaluate_stage1(program_path: str) -> EvaluationResult:
    """Cascade stage 1 — single trial, fast reject of broken programs."""
    return _eval_impl(program_path, 1)


def evaluate_stage2(program_path: str) -> EvaluationResult:
    return evaluate(program_path)
