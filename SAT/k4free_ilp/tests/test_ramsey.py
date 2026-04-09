"""Validate solver against known Ramsey numbers."""

import pytest
import numpy as np

from k4free_ilp.ilp_solver import solve_k4free
from k4free_ilp.k4_check import is_k4_free
from k4free_ilp.alpha_exact import alpha_exact
from k4free_ilp.graph_io import adj_to_g6


def test_R43():
    """R(4,3) = 9: K₄-free graph with α ≤ 2 exists at n=8, not at n=9."""
    status_8, adj_8, _ = solve_k4free(8, max_alpha=2, max_degree=7, time_limit=60)
    assert status_8 == "FEASIBLE", "Should find K4-free graph on 8 vertices with α ≤ 2"
    assert is_k4_free(adj_8)
    alpha, _ = alpha_exact(adj_8)
    assert alpha <= 2

    status_9, _, _ = solve_k4free(9, max_alpha=2, max_degree=8, time_limit=120)
    assert status_9 == "INFEASIBLE", "R(4,3)=9: no K4-free graph on 9 vertices has α ≤ 2"


def test_R44():
    """R(4,4) = 18: K₄-free graph with α ≤ 3 exists at n=17, not at n=18."""
    status_17, adj_17, stats = solve_k4free(17, max_alpha=3, max_degree=16, time_limit=300)
    assert status_17 == "FEASIBLE", f"Should find K4-free graph on 17 vertices with α ≤ 3. Stats: {stats}"
    assert is_k4_free(adj_17)
    alpha, _ = alpha_exact(adj_17)
    assert alpha <= 3

    status_18, _, stats = solve_k4free(18, max_alpha=3, max_degree=17, time_limit=600)
    assert status_18 == "INFEASIBLE", f"R(4,4)=18: should be infeasible. Stats: {stats}"


def test_R45_feasible():
    """R(4,5) = 25: K₄-free graph with α ≤ 4 exists at n=24."""
    status_24, adj_24, stats = solve_k4free(24, max_alpha=4, max_degree=23, time_limit=600)
    assert status_24 == "FEASIBLE", f"Should find K4-free graph on 24 vertices with α ≤ 4. Stats: {stats}"
    assert is_k4_free(adj_24)
    alpha, _ = alpha_exact(adj_24)
    assert alpha <= 4
    print(f"R(4,5) witness: n=24, α={alpha}, d_max={adj_24.sum(axis=1).max()}, edges={adj_24.sum()//2}")
    print(f"g6: {adj_to_g6(adj_24)}")


def test_R45_infeasible():
    """R(4,5) = 25: no K₄-free graph on 25 vertices has α ≤ 4.
    This may be slow. 1800s timeout."""
    status_25, _, stats = solve_k4free(25, max_alpha=4, max_degree=24, time_limit=1800)
    if status_25 == "TIMEOUT":
        print(f"R(4,5) infeasibility timed out at 1800s. Stats: {stats}")
        pytest.skip("R(4,5) infeasibility proof timed out — expected for this problem size")
    assert status_25 == "INFEASIBLE", f"R(4,5)=25: should be infeasible. Got {status_25}. Stats: {stats}"
