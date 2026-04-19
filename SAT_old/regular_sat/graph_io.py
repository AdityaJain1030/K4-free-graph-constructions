import json
import numpy as np
import networkx as nx


def adj_to_g6(adj: np.ndarray) -> str:
    """Convert adjacency matrix to graph6 string using networkx."""
    G = nx.from_numpy_array(adj)
    return nx.to_graph6_bytes(G, header=False).decode('ascii').strip()


def adj_to_edge_list(adj: np.ndarray) -> list[tuple[int, int]]:
    """Return sorted list of (i,j) edges with i < j."""
    n = adj.shape[0]
    edges = []
    for i in range(n):
        for j in range(i + 1, n):
            if adj[i, j]:
                edges.append((i, j))
    return edges


def save_results(results: list[dict], path: str):
    """Save results list to JSON. numpy types must be converted to native Python types."""
    def convert(obj):
        if isinstance(obj, (np.integer,)):
            return int(obj)
        if isinstance(obj, (np.floating,)):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

    with open(path, 'w') as f:
        json.dump(results, f, indent=2, default=convert)
