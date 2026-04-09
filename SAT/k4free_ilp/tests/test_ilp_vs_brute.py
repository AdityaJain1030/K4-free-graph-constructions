"""Validate ILP Pareto frontiers match brute force results for n=4..10."""

import json
import os

from k4free_ilp.pareto_scanner import scan_pareto_frontier


def load_brute_force_results(n: int) -> dict:
    path = f"k4free_ilp/results/brute_force_n{n}.json"
    with open(path) as f:
        return json.load(f)


def test_pareto_agreement():
    """
    For n = 4 through 10, verify the ILP Pareto frontier matches
    the brute force Pareto frontier exactly.
    """
    for n in range(4, 11):
        print(f"\n--- Testing n={n} ---", flush=True)
        bf = load_brute_force_results(n)
        ilp = scan_pareto_frontier(n, time_limit_per_query=60)

        bf_points = {(p["alpha"], p["d_max"]) for p in bf["pareto_frontier"]}
        ilp_points = {(p["alpha"], p["d_max"]) for p in ilp}

        assert bf_points == ilp_points, (
            f"n={n}: brute force has {bf_points}, ILP has {ilp_points}"
        )
        print(f"n={n}: PASS — {len(bf_points)} Pareto points match")
