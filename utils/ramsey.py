"""
utils/ramsey.py
===============
Known Ramsey numbers and derived degree bounds for K4-free graphs.
Used by search/sat_exact.py and search/sat_regular.py.
"""

KNOWN_RAMSEY: dict[tuple[int, int], int] = {
    # Trivial: R(s, 1) = 1 (the one-vertex graph).
    (3, 1): 1, (4, 1): 1, (5, 1): 1, (6, 1): 1, (7, 1): 1, (8, 1): 1, (9, 1): 1,
    # Trivial: R(s, 2) = s (complete graph on s vertices contains either K_s or an edge between any two non-adjacent).
    (3, 2): 3, (4, 2): 4, (5, 2): 5, (6, 2): 6, (7, 2): 7, (8, 2): 8, (9, 2): 9,
    # Non-trivial known values.
    (3, 3): 6, (3, 4): 9, (3, 5): 14, (3, 6): 18, (3, 7): 23, (3, 8): 28, (3, 9): 36,
    (4, 3): 9, (4, 4): 18, (4, 5): 25,
}
# Fill symmetric entries: R(s,t) = R(t,s)
for (_s, _t), _v in list(KNOWN_RAMSEY.items()):
    KNOWN_RAMSEY[(_t, _s)] = _v


def degree_bounds(n: int, max_alpha: int) -> tuple[int, int]:
    """
    Ramsey-based vertex-degree bounds for a K4-free graph with α ≤ max_alpha.

    For any vertex v in such a graph:
      - Non-neighbourhood is K4-free with α ≤ max_alpha-1
          → size < R(4, max_alpha)  → deg(v) ≥ n - R(4, max_alpha)
      - Neighbourhood is triangle-free with α ≤ max_alpha
          → size < R(3, max_alpha+1) → deg(v) ≤ R(3, max_alpha+1) - 1

    Returns (min_degree, max_degree). -1 means the bound is unavailable.
    """
    r4t   = KNOWN_RAMSEY.get((4, max_alpha))
    r3tp1 = KNOWN_RAMSEY.get((3, max_alpha + 1))
    min_deg = max(0, n - r4t)   if r4t   is not None else -1
    max_deg = r3tp1 - 1         if r3tp1 is not None else -1
    return min_deg, max_deg
