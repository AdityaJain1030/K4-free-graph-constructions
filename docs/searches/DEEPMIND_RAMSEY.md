# DeepMind Ramsey lower-bound catalog

Written 2026-04-24. Documents the ingest of K₄-free graphs from
<https://github.com/google-research/google-research/tree/master/ramsey_number_bounds/improved_bounds>
as `source="deepmind_ramsey"` in graph_db.

## What's ingested

Seven adjacency matrices from the `improved_bounds/` directory, each a
K₄-free graph whose independence number matches the claimed Ramsey
lower bound R(4, s) ≥ n (i.e. n = bound − 1, α = s − 1).

| Ramsey claim    | n   | m    | d_max | α  | c_log  |
|-----------------|-----|------|-------|----|--------|
| R(4,13) ≥ 139   | 138 | 3011 | 45    | 12 | 1.028  |
| R(4,14) ≥ 148   | 147 | 3087 | 42    | 13 | 0.994  |
| R(4,15) ≥ 159   | 158 | 3742 | 51    | 14 | 1.149  |
| R(4,16) ≥ 174   | 173 | 4152 | 48    | 15 | 1.075  |
| R(4,18) ≥ 209   | 208 | 5724 | 58    | 17 | 1.167  |
| R(4,19) ≥ 219   | 218 | 6104 | 56    | 18 | 1.149  |
| R(4,20) ≥ 237   | 236 | 7552 | 64    | 19 | 1.239  |

All graphs verified:

- Symmetric 0/1 adjacency matrix
- K₄-free (explicit triangle-sharing-common-vertex check)
- Dimensions match the filename claim (n-by-n)
- α (via CP-SAT sync) tight at s − 1, confirming the Ramsey claim

## Ingest pipeline

`scripts/ingest_deepmind_ramsey.py`:

1. Parses the NumPy-printed 2D array text format (strips `[]`,
   splits on whitespace, reshapes to n×n).
2. Validates K4-freeness (reject on any K₄ found).
3. Adds to graph_db with metadata: `origin`, `ramsey_claim`,
   `ramsey_s`, `ramsey_bound_n`, `alpha_upper_bound_claimed`.
4. Syncs cache (CP-SAT α computation, eigenvalues, etc.).

Files downloaded to `/tmp/deepmind_ramsey/` (not checked in); rerun
with `--dir <path>` if needed.

## Why c_log is high for all of them

These constructions minimise α/n to push R(4, s) bounds up; they do
not minimise c_log. The formula `c_log = α · d_max / (n · ln d_max)`
weights α against d/ln(d). DeepMind's R(4,s) constructions are dense
(d = 42–64) because density lets α stay small — at the cost of
c_log.

Rough comparison at n=236:

- DeepMind R(4,20): α=19, d=64 → c ≈ 1.24
- Hypothetical 3×P(17) lift on 51 vertices × extension: irrelevant at
  this n, but for context, the c_log floor at n ≤ 120 is 0.6789 (via
  P(17) copies).

So these seven graphs are **not frontier candidates** for c_log. They
are a separate regime: **α/n minimisers, not c_log minimisers**. Keep
them in the DB as a reference catalogue of dense K₄-free extremal
constructions. The α/n ratios (0.080–0.088) are notably lower than
typical Cayley-class K₄-free extremals (≈ 0.176 at Paley-17).

## Potential uses of the catalog

- **Edge-deletion / trimming experiments**: start from a dense DeepMind
  graph and delete edges to drop d_max, watching α. Each deletion
  can only increase α (K4-free property). Trade-off curve would tell
  us whether any subset of these graphs has a sparsified version
  competitive at its n. (Prior MV analysis in
  `MATTHEUS_VERSTRAETE.md` argued this is fundamentally unlikely
  because MV-style graphs are α-tight by construction — deleting
  edges only raises α.)
- **Spectral / structural comparison**: these graphs have known SDP
  (Lovász θ) values. Comparing α/θ tightness here to the Cayley
  frontier would tell us whether they're spectrum-saturated in the
  way Paley-17 is.
- **Reference points for the 200k+ catalog screens** in
  `FRONTIER_REVIEW.md`.

## Source provenance

The `improved_bounds/` directory also includes R(3, 13) and R(3, 18)
files, which are triangle-free (K₃-free) — not K₄-free. These are NOT
ingested here; they'd fail our K₄-free check trivially (they have
triangles' complement structure, not relevant to our project).
