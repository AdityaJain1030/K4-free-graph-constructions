import numpy as np


def alpha_exact(adj: np.ndarray) -> tuple[int, list[int]]:
    """
    Exact maximum independent set via bitmask branch-and-bound.
    Returns (alpha_value, list_of_vertices_in_max_independent_set).
    """
    n = adj.shape[0]
    # Precompute neighbor bitmasks
    nbr = [0] * n
    for i in range(n):
        for j in range(n):
            if adj[i, j]:
                nbr[i] |= 1 << j

    best_size = 0
    best_set = 0  # bitmask of best independent set

    def popcount(x):
        return bin(x).count('1')

    def branch(candidates, current_set, current_size):
        nonlocal best_size, best_set

        if current_size + popcount(candidates) <= best_size:
            return

        if candidates == 0:
            if current_size > best_size:
                best_size = current_size
                best_set = current_set
            return

        # Pick lowest-bit vertex
        v = (candidates & -candidates).bit_length() - 1

        # Include v
        branch(candidates & ~nbr[v] & ~(1 << v), current_set | (1 << v), current_size + 1)
        # Exclude v
        branch(candidates & ~(1 << v), current_set, current_size)

    all_bits = (1 << n) - 1
    branch(all_bits, 0, 0)

    # Extract vertex list from bitmask
    result = []
    tmp = best_set
    while tmp:
        v = (tmp & -tmp).bit_length() - 1
        result.append(v)
        tmp &= tmp - 1
    return best_size, result
