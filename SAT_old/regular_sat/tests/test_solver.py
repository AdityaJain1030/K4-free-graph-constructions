"""Validation tests for the minimum-edge K₄-free solver."""

import sys
import os
import pytest
import numpy as np

# Ensure repo root and SAT_old/ are on path
_HERE = os.path.dirname(os.path.abspath(__file__))
_SAT_OLD = os.path.dirname(os.path.dirname(_HERE))
_REPO_ROOT = os.path.dirname(_SAT_OLD)
for _p in (_REPO_ROOT, _SAT_OLD):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from regular_sat.solver import solve_min_edges
from utils.graph_props import is_k4_free, alpha_exact


def _validate_solution(result, n, max_alpha):
    """Validate structural properties of any returned solution."""
    assert result["status"] in ("OPTIMAL", "FEASIBLE"), (
        f"n={n}, α≤{max_alpha}: expected feasible, got {result['status']}"
    )

    adj = np.array(result["adjacency"])

    # K₄-free
    assert is_k4_free(adj), f"n={n}: returned graph contains K₄!"

    # Alpha bound
    actual_alpha, _ = alpha_exact(adj)
    assert actual_alpha <= max_alpha, f"n={n}: α={actual_alpha} > {max_alpha}"

    # Near-regularity (Hajnal)
    degrees = adj.sum(axis=1)
    assert int(degrees.max()) - int(degrees.min()) <= 1, (
        f"n={n}: not near-regular, degrees {sorted(set(int(d) for d in degrees))}"
    )

    # Edge count consistency
    assert result["num_edges"] == int(adj.sum()) // 2


class TestKnownOptima:
    """Test against known optimal minimum-edge K₄-free graphs.

    Expected values are upper bounds from known regular constructions.
    The solver may find better (fewer-edge) near-regular solutions.
    """

    @pytest.mark.parametrize("n, max_alpha, expected_edges, expected_d", [
        (13, 3, 39, 6),
        (17, 3, 68, 8),
        (18, 4, 54, 6),
        (19, 4, 57, 6),
    ])
    def test_known_optimum(self, n, max_alpha, expected_edges, expected_d):
        result = solve_min_edges(n, max_alpha, time_limit=300)
        _validate_solution(result, n, max_alpha)

        # Solution should be at most as many edges as the known regular construction
        assert result["num_edges"] <= expected_edges, (
            f"n={n}: got {result['num_edges']} edges, expected ≤ {expected_edges}"
        )

    @pytest.mark.slow
    def test_n22_alpha4(self):
        """n=22, α≤4: known 9-regular construction has 99 edges."""
        n, max_alpha, expected_edges = 22, 4, 99
        result = solve_min_edges(n, max_alpha, time_limit=600)
        _validate_solution(result, n, max_alpha)

        assert result["num_edges"] <= expected_edges, (
            f"n={n}: got {result['num_edges']} edges, expected ≤ {expected_edges}"
        )


class TestTightRamseyBounds:
    """Test cases where Ramsey bounds force a unique D, giving exact edge counts."""

    def test_n17_alpha3_exact(self):
        """n=17, α≤3: Ramsey forces D=8 exactly, so 8-regular with 68 edges."""
        result = solve_min_edges(17, 3, time_limit=120)
        _validate_solution(result, 17, 3)
        assert result["num_edges"] == 68, (
            f"n=17: expected exactly 68 edges (D forced to 8), got {result['num_edges']}"
        )
        assert all(d == 8 for d in result["degree_sequence"]), (
            f"n=17: expected 8-regular, got {sorted(set(result['degree_sequence']))}"
        )


class TestInfeasibility:
    """Test Ramsey-based infeasibility."""

    def test_R43_feasible(self):
        """R(4,3)=9: α≤2 feasible at n=8."""
        result_8 = solve_min_edges(8, 2, time_limit=60)
        _validate_solution(result_8, 8, 2)

    def test_R44_infeasible(self):
        """R(4,4)=18: no K₄-free graph on 18 vertices has α≤3."""
        result = solve_min_edges(18, 3, time_limit=120)
        assert result["status"] == "INFEASIBLE"
