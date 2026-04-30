"""
experiments/graph_space_visualization/embed.py
==============================================
Projection wrappers. PCA runs on the raw vectors; t-SNE / UMAP / MDS run
on a precomputed dissimilarity matrix.

All optional deps are lazy-imported so this file imports cleanly on a
fresh checkout, and only fails when the user actually requests a method
whose backend isn't installed.
"""
from __future__ import annotations

import numpy as np


def embed_pca(X: np.ndarray, n_components: int = 2, seed: int = 0) -> tuple[np.ndarray, dict]:
    """PCA on the raw edge vectors. Returns (coords, info)."""
    from sklearn.decomposition import PCA

    pca = PCA(n_components=n_components, random_state=seed)
    coords = pca.fit_transform(X.astype(np.float32))
    info = {
        "explained_variance_ratio": pca.explained_variance_ratio_.tolist(),
        "cumulative_explained": float(pca.explained_variance_ratio_.sum()),
    }
    return coords, info


def embed_tsne(D: np.ndarray, n_components: int = 2,
               perplexity: float | None = None, seed: int = 0) -> tuple[np.ndarray, dict]:
    """t-SNE on a precomputed distance matrix."""
    from sklearn.manifold import TSNE

    K = D.shape[0]
    if perplexity is None:
        perplexity = max(5.0, min(30.0, K / 4.0))
    if K <= perplexity:
        perplexity = max(2.0, K / 3.0)
    tsne = TSNE(
        n_components=n_components,
        metric="precomputed",
        init="random",
        perplexity=perplexity,
        random_state=seed,
    )
    coords = tsne.fit_transform(D.astype(np.float32))
    return coords, {"perplexity": float(perplexity), "kl_divergence": float(tsne.kl_divergence_)}


def embed_umap(D: np.ndarray, n_components: int = 2,
               n_neighbors: int | None = None, seed: int = 0) -> tuple[np.ndarray, dict]:
    """UMAP on a precomputed distance matrix."""
    import umap

    K = D.shape[0]
    if n_neighbors is None:
        n_neighbors = max(2, min(15, K // 3))
    n_neighbors = min(n_neighbors, max(2, K - 1))
    reducer = umap.UMAP(
        n_components=n_components,
        metric="precomputed",
        n_neighbors=n_neighbors,
        random_state=seed,
    )
    coords = reducer.fit_transform(D.astype(np.float32))
    return coords, {"n_neighbors": int(n_neighbors)}


def embed_mds(D: np.ndarray, n_components: int = 2, seed: int = 0) -> tuple[np.ndarray, dict]:
    """Metric MDS on a precomputed distance matrix."""
    from sklearn.manifold import MDS

    mds = MDS(
        n_components=n_components,
        dissimilarity="precomputed",
        random_state=seed,
        normalized_stress="auto",
    )
    coords = mds.fit_transform(D.astype(np.float32))
    return coords, {"stress": float(mds.stress_)}


METHODS = {
    "pca": embed_pca,
    "tsne": embed_tsne,
    "umap": embed_umap,
    "mds": embed_mds,
}


def needs_distance_matrix(method: str) -> bool:
    return method in {"tsne", "umap", "mds"}
