import numpy as np
import networkx as nx
from k4free_ilp.k4_check import is_k4_free, find_k4
from k4free_ilp.alpha_exact import alpha_exact


def test_k4_check():
    # K4: complete graph on 4 vertices — should NOT be K4-free
    K4 = np.ones((4, 4), dtype=np.uint8)
    np.fill_diagonal(K4, 0)
    assert not is_k4_free(K4)
    assert find_k4(K4) is not None

    # C5: cycle on 5 vertices — should be K4-free
    C5 = np.zeros((5, 5), dtype=np.uint8)
    for i in range(5):
        C5[i, (i + 1) % 5] = C5[(i + 1) % 5, i] = 1
    assert is_k4_free(C5)

    # K3 + isolated vertex — K4-free
    G = np.zeros((4, 4), dtype=np.uint8)
    G[0, 1] = G[1, 0] = G[0, 2] = G[2, 0] = G[1, 2] = G[2, 1] = 1
    assert is_k4_free(G)


def test_alpha():
    # C5: α = 2
    C5 = np.zeros((5, 5), dtype=np.uint8)
    for i in range(5):
        C5[i, (i + 1) % 5] = C5[(i + 1) % 5, i] = 1
    alpha, indep_set = alpha_exact(C5)
    assert alpha == 2
    assert len(indep_set) == 2
    # verify it's actually independent
    for u in indep_set:
        for v in indep_set:
            if u != v:
                assert C5[u, v] == 0

    # Petersen graph: α = 4
    P = nx.to_numpy_array(nx.petersen_graph(), dtype=np.uint8)
    alpha, indep_set = alpha_exact(P)
    assert alpha == 4

    # K4-free graph on 4 vertices (triangle + isolate): α = 2
    G = np.zeros((4, 4), dtype=np.uint8)
    G[0, 1] = G[1, 0] = G[0, 2] = G[2, 0] = G[1, 2] = G[2, 1] = 1
    alpha, _ = alpha_exact(G)
    assert alpha == 2  # vertex 3 + any non-adjacent vertex


def test_petersen_k4free():
    P = nx.to_numpy_array(nx.petersen_graph(), dtype=np.uint8)
    assert is_k4_free(P)
