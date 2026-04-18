import numpy as np


def is_k4_free(adj: np.ndarray) -> bool:
    """Return True if the graph (given as n×n numpy adjacency matrix) contains no K₄."""
    return find_k4(adj) is None


def find_k4(adj: np.ndarray):
    """Return a tuple (a,b,c,d) forming a K₄, or None if K₄-free."""
    n = adj.shape[0]
    # Precompute neighbor bitmasks
    nbr = [0] * n
    for i in range(n):
        for j in range(n):
            if adj[i, j]:
                nbr[i] |= 1 << j

    for a in range(n):
        for b in range(a + 1, n):
            if not (nbr[a] >> b & 1):
                continue
            common_ab = nbr[a] & nbr[b]
            # Only consider c > b
            common_ab &= ~((1 << (b + 1)) - 1)
            tmp = common_ab
            while tmp:
                c = (tmp & -tmp).bit_length() - 1
                tmp &= tmp - 1
                common_abc = common_ab & nbr[c]
                # Only consider d > c
                common_abc &= ~((1 << (c + 1)) - 1)
                if common_abc:
                    d = (common_abc & -common_abc).bit_length() - 1
                    return (a, b, c, d)
    return None
