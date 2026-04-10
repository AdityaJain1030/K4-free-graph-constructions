"""Validate scan results and produce comparison table + validation report."""

import json
import os
import sys
import numpy as np

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from k4free_ilp.k4_check import is_k4_free
from k4free_ilp.alpha_exact import alpha_exact

RESULTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")

# Old solver results (exact regularity)
OLD_RESULTS = {
    12: {"d_max": 5, "edges": 30},
    13: {"d_max": 6, "edges": 39},
    14: {"d_max": 6, "edges": 42},
    15: {"d_max": 7, "edges": 52},
    16: {"d_max": 8, "edges": 64},
    17: {"d_max": 8, "edges": 68},
    18: {"d_max": 6, "edges": 54},
    19: {"d_max": 6, "edges": 57},
    20: {"d_max": 7, "edges": 70},
    21: {"d_max": 8, "edges": 84},
    22: {"d_max": 9, "edges": 99},
}


def _edges_to_adj(n, edges):
    """Reconstruct adjacency matrix from edge list."""
    adj = np.zeros((n, n), dtype=np.uint8)
    for i, j in edges:
        adj[i, j] = adj[j, i] = 1
    return adj


def validate_result(r):
    """Validate a single enriched result dict. Returns (ok, errors) tuple."""
    errors = []
    n = r["n"]
    max_alpha = r["max_alpha"]

    if r["edges"] is None:
        return True, []

    adj = _edges_to_adj(n, r["edges"])

    # K₄-free
    if not is_k4_free(adj):
        errors.append(f"n={n}: graph contains K₄!")

    # α bound
    actual_alpha, _ = alpha_exact(adj)
    if actual_alpha > max_alpha:
        errors.append(f"n={n}: α={actual_alpha} > max_alpha={max_alpha}")

    # Near-regularity
    degrees = adj.sum(axis=1).astype(int)
    d_min, d_max = int(degrees.min()), int(degrees.max())
    if d_max - d_min > 1:
        errors.append(f"n={n}: not near-regular, d_min={d_min}, d_max={d_max}")

    # Edge count consistency
    actual_edges = int(adj.sum()) // 2
    if actual_edges != r["num_edges"]:
        errors.append(f"n={n}: reported {r['num_edges']} edges but adjacency has {actual_edges}")

    return len(errors) == 0, errors


def load_results():
    """Load all individual result JSONs from results dir."""
    results = {}
    for fname in sorted(os.listdir(RESULTS_DIR)):
        if fname.startswith("n") and fname.endswith(".json") and "_a" in fname:
            path = os.path.join(RESULTS_DIR, fname)
            with open(path) as f:
                r = json.load(f)
            results[(r["n"], r["max_alpha"])] = r
    return results


def main():
    results = load_results()

    if not results:
        print("No results found in", RESULTS_DIR)
        return

    # Validate all results
    validation = []
    all_ok = True
    print("Validation:")
    print("-" * 60)
    for key in sorted(results.keys()):
        r = results[key]
        ok, errors = validate_result(r)
        entry = {
            "n": r["n"], "max_alpha": r["max_alpha"],
            "status": r["status"], "valid": ok, "errors": errors,
        }
        if r["num_edges"] is not None:
            entry["num_edges"] = r["num_edges"]
            entry["d_min"] = r["d_min"]
            entry["d_max"] = r["d_max"]
        validation.append(entry)

        status_sym = "OK" if ok else "FAIL"
        if r["edges"] is None:
            print(f"  n={r['n']:>2} α≤{r['max_alpha']}: {r['status']:>10} -- skip (no graph)")
        else:
            print(f"  n={r['n']:>2} α≤{r['max_alpha']}: {status_sym:>4}  "
                  f"|E|={r['num_edges']:>4}, d=[{r['d_min']},{r['d_max']}]")
            if not ok:
                all_ok = False
                for e in errors:
                    print(f"    ERROR: {e}")

    print(f"\nAll valid: {all_ok}\n")

    # Comparison table: old vs new
    print("Old (exact-regular) vs New (near-regular) solver:")
    print(f"{'N':>3} {'α':>2} | {'old_d':>5} {'old_E':>5} | "
          f"{'new_d_min':>8} {'new_d_max':>8} {'new_E':>5} | {'delta_E':>7} {'note':>12}")
    print("-" * 80)

    comparisons = []
    for n in sorted(OLD_RESULTS.keys()):
        old = OLD_RESULTS[n]
        # Find the matching new result
        new = None
        for key, r in results.items():
            if r["n"] == n and r["edges"] is not None:
                new = r
                break

        if new is None:
            print(f"{n:>3} {'':>2} | {old['d_max']:>5} {old['edges']:>5} | "
                  f"{'—':>8} {'—':>8} {'—':>5} | {'—':>7} {'no result':>12}")
            comparisons.append({
                "n": n, "old_d_max": old["d_max"], "old_edges": old["edges"],
                "new_d_min": None, "new_d_max": None, "new_edges": None,
                "delta_edges": None,
            })
            continue

        delta = new["num_edges"] - old["edges"]
        delta_str = f"{delta:+d}"
        note = ""
        if delta < 0:
            note = "IMPROVED"
        elif delta == 0:
            note = "same"
        else:
            note = "worse"

        print(f"{n:>3} {new['max_alpha']:>2} | {old['d_max']:>5} {old['edges']:>5} | "
              f"{new['d_min']:>8} {new['d_max']:>8} {new['num_edges']:>5} | "
              f"{delta_str:>7} {note:>12}")

        comparisons.append({
            "n": n, "old_d_max": old["d_max"], "old_edges": old["edges"],
            "new_d_min": new["d_min"], "new_d_max": new["d_max"],
            "new_edges": new["num_edges"], "delta_edges": delta,
        })

    # Save validation report
    report = {
        "all_valid": all_ok,
        "validation": validation,
        "comparisons": comparisons,
    }
    out_path = os.path.join(RESULTS_DIR, "validation.json")
    with open(out_path, "w") as f:
        json.dump(report, f, indent=2)
    print(f"\nSaved {out_path}")


if __name__ == "__main__":
    main()
