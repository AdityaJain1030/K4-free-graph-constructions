# `experiments/graph_space_visualization/` — projecting graph_db rows into 2D for family inspection

## Compute

- **Environment:** `k4free` env, plus `scikit-learn` and `umap-learn` (added to `environment.yml`; install with `micromamba env update -f environment.yml`).
- **Typical runtime:** N=17 with ~50 graphs ≈ 5 s end-to-end. N=20 with ~200 graphs ≈ 30 s. Scales as O(K² · C(N,2)) for the distance matrix and as the underlying embedder for the projection.
- **Memory:** Negligible (vectors are <1 KB each at N≤100; K×K int32 distance matrix is 4·K² bytes).
- **Parallelism:** Single-process. The bottleneck is the embedder, not the distance matrix.

---

## Background

Each K₄-free graph in `graph_db` has a canonical sparse6 (computed via nauty's `labelg` — see `graph_db/encoding.py`). Decoding that sparse6 produces the canonical adjacency matrix. The upper-triangle bits, read row-major, give a deterministic vector

```
v(G) ∈ {0, 1}^(N choose 2)
```

that is the same for every isomorphic copy of G. So at fixed N, every isomorphism class is one point in a fixed bit-cube. The Hamming distance between two such vectors is then a deterministic dissimilarity between graphs.

**Caveat — canonical Hamming is not graph edit distance.** Two graphs that differ by a single edge can have very different canonical labelings under `labelg`, and therefore large canonical Hamming distance. The distance is *deterministic* (same graph → same vector → same distance) and *isomorphism-invariant* (isomorphic graphs collapse to one point), but it is **not** a metric on graph isomorphism classes in the way graph edit distance is. Cluster boundaries in the projections should be read as "graphs with similar canonical structure," not as "graphs that are close under any natural graph edit." For small N (≤ 12) `--metric ged` swaps in true graph edit distance via `networkx.graph_edit_distance` with a per-pair time budget; defer to that mode if the cluster geometry under canonical Hamming looks suspicious.

---

## Question

> At a fixed N, where do graphs from each producer family (`cayley`, `sat_exact`, `circulant`, `brown`, …) sit in {0,1}^(N choose 2) edge-vector space, and do PCA / t-SNE / UMAP / MDS projections reveal a coherent family geometry?

---

## Approach

```
graph_db.query(n=N, source=…, c_log≤…)
  → for each row: db.adj(graph_id) → upper-triangle bit vector  ∈ {0,1}^(N choose 2)
  → stack into X ∈ {0,1}^(K × C(N,2))
  → distance matrix D ∈ ℤ^(K × K)
  → embed: PCA on X, or {t-SNE, UMAP, MDS} on D (metric='precomputed')
  → plot: matplotlib PNG and/or plotly HTML, color by source, size by 1/c_log
```

Per-N, per-(source-set) caches under `cache/` keyed by hash of sorted graph_ids; embeddings keyed by `(distance-cache-key, method, params, seed)`. Re-runs hit cache; new methods or seeds trigger only the affected stage.

Default highlights: P(17), CR(19), C(22), Brown, Mattheus–Verstraete, plus the SAT-certified optimum at the requested N if one exists. `--highlight <graph_id|slug>` adds custom emphatic markers.

---

## Files

| File | Purpose |
|---|---|
| `run.py` | CLI driver. Pulls rows, builds vectors, computes distances, embeds, plots. |
| `vectorize.py` | `adj_to_edge_vector`, `stack_edge_vectors` — canonical adjacency → upper-triangle bit vector. |
| `distance.py` | `pairwise_hamming` — vectorized K×K Hamming via Gram-trick. `pairwise_ged` — small-N exact graph edit distance. |
| `embed.py` | `embed_pca`, `embed_tsne`, `embed_umap`, `embed_mds`. Lazy imports so missing optional deps fail loudly only when invoked. |
| `plot.py` | `scatter_png` (matplotlib), `scatter_html` (plotly). Color by source, size by 1/c_log, hover with id/α/d_max/c_log. |
| `cache/` | Distance matrices and embeddings, gitignored. |
| `results/` | Generated PNGs and HTMLs, committed. |

---

## CLI

```bash
micromamba run -n k4free python experiments/graph_space_visualization/run.py \
    --n 17 --method pca,tsne,umap --metric hamming-canonical \
    --sources cayley,sat_exact,circulant,sat_circulant_optimal \
    --color-by source --size-by c_log --html --png --seed 0
```

| Flag | Default | Notes |
|---|---|---|
| `--n` | required | Vertex count to project. |
| `--method` | `pca` | Comma list of `pca,tsne,umap,mds`. |
| `--metric` | `hamming-canonical` | `hamming-canonical` (default, scales) or `ged` (exact, N ≤ 12). |
| `--sources` | all | Comma list of source tags; pass `all` to include everything. |
| `--c-log-max` | None | Cap on `c_log` to filter the corpus. |
| `--max-per-source` | 50 | Subsample large sources at large N to keep figures legible. |
| `--color-by` | `source` | `source`, `c_log`, `regular`, `d_max`. |
| `--size-by` | `c_log` | Smaller c_log → larger marker. |
| `--highlight` | — | Comma list of `graph_id` prefixes or `highlights/` slugs to emphasize. |
| `--seed` | `0` | RNG seed for stochastic embedders. |
| `--png` / `--html` | both | Output formats. |
| `--out` | `results/` | Output directory. |

---

## Results

**Status:** open — first deliverables are N=17, N=20 panels under `results/`.

The validation expectations at N=17 (sanity checks before publishing the first plot):

- Distinct clusters per source.
- P(17) co-located with its rediscoveries across sources (single point).
- SAT-certified optima close to circulants of the same `(α, d_max)`.
- Random / Brown isolates well-separated from algebraic clusters.

If the layout fails one of these at N=17, that is itself a finding — the canonical-Hamming projection is misleading at this N and the `--metric ged` fallback (or a different distance) is warranted.

---

## Open questions

- [ ] Does cluster proximity correlate with c_log proximity? Hypothesis: weakly. Verify by computing Spearman ρ between projection-distance and c_log-distance at N=17, 20.
- [ ] Trajectory overlay — render `random_regular_switch` / `mcmc` / `cayley_tabu` step sequences as paths through the embedding. Requires producers to log per-step graphs, not just the final.
- [ ] Cross-N embedding via shared canonical-form features (e.g. degree-sequence-augmented encoding) — currently a fixed-N tool only.
- [ ] At small N (≤ 10) where `brute_force` enumerates the full lattice, plot the *entire* K₄-free isomorphism-class lattice and overlay the producers. Tells us how much of the landscape each search actually visits.

---

## Theorems that would be nice to prove

- **Conjecture:** Within each producer family, canonical-Hamming clusters at fixed N correspond to orbits of an explicit symmetry group acting on the construction parameters (e.g. `(Z_N)*` for circulants, group automorphisms for Cayley).
  *Why it matters:* if true, the visualization is reading off algebraic structure directly, and the projection is interpretable as a parameter-space view of each family.
