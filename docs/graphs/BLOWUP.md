# `LexBlowupSearch` / `TensorBlowupSearch` — graph-product blow-ups

## What they do

Lift a small K₄-free seed graph (typically pulled from `graph_db`)
into a structured large-N graph via a graph product. Two distinct
classes for two distinct products:

- **`LexBlowupSearch`** — `seed[I_k]`. Each seed vertex is replaced by
  an independent set of size `k`; every seed-edge becomes a complete
  bipartite `K_{k,k}` between the corresponding blobs. K₄-free
  preserved (a K₄ in the product needs four distinct blobs ⇒ K₄ in
  the seed). `N = n_seed · k`, `α = k · α_seed`, `d_max = k · d_seed`.
- **`TensorBlowupSearch`** — `seed × other` (Kronecker / categorical
  product). `(u₁, v₁) ~ (u₂, v₂)` iff *both* `u₁ ~_seed u₂` and
  `v₁ ~_other v₂`. K₄-free preserved if either factor is K₄-free.
  `N = n_seed · n_other`, `d_max = d_seed · d_other`,
  `α ≥ max(α_seed · n_other, α_other · n_seed)`.

The two classes share `name = "blowup"` so their outputs land in the
same `graphs/blowup.json` under `source = "blowup"`. The `mode` field
in the per-graph metadata (`"lex"` vs `"tensor"`) distinguishes them
at query time.

## Why they exist

Lex blow-up's `c_log` strictly grows by a factor of
`k · ln(d_seed) / ln(k · d_seed)` — for `k = 2, d = 8` that's ≈ 1.50.
Tensor blow-up is similarly bad. Neither is competitive on its own.
The point is to produce *structured* starting points at large N for a
downstream edge-switch polish or SAT warm start. Comparing
"blow-up + polish" vs "random + polish" at the same N is one of the
cleanest signals the landscape study needs.

## Kwargs

`LexBlowupSearch`:

| kwarg        | required | meaning                                          |
|--------------|----------|--------------------------------------------------|
| `seed`       | yes      | `nx.Graph` factor                                |
| `k`          | yes      | Independent-set size; must be ≥ 2                |
| `seed_meta`  | no       | Optional provenance dict (`id`, `source`, …); flows into output metadata under `seed_*` |

`TensorBlowupSearch`:

| kwarg        | required | meaning                                          |
|--------------|----------|--------------------------------------------------|
| `seed`       | yes      | First `nx.Graph` factor                          |
| `other`      | yes      | Second `nx.Graph` factor                         |
| `seed_meta`  | no       | Provenance for `seed`; output prefix `seed_*`    |
| `other_meta` | no       | Provenance for `other`; output prefix `other_*`  |

Neither class accepts `n`: the output vertex count is fully
determined by the seeds (and `k` for lex).

Resolving seeds out of `graph_db` is a caller concern — see
`scripts/run_blowup.py` for the canonical pattern.

## What to expect from them

- `LexBlowupSearch(seed=P(17), k=2)` — Paley P(17) lexed into 34
  vertices. Resulting `c_log ≈ 1.01` (worse than P(17)'s 0.68), but
  the graph has the Paley spectral structure preserved.
- `TensorBlowupSearch(seed=circulant_n13, other=cayley_n7)` — 91-vertex
  product, `c_log ≈ 2.07`. Useful as a high-N regular structured seed.
- Chain the output through `RandomRegularSwitchSearch` locally (not
  yet automated — ingest, pick by id, then feed as a seed with
  `num_switches=500`) to measure how much the polish recovers.

## When to reach for them

- Generating large-N structured seeds for downstream polish.
- Stress-testing the K₄-free scoring pipeline on big graphs
  (products easily push N above 100).

## When **not** to reach for them

- You want competitive `c_log` out of the box. Blow-ups alone don't
  cross the 0.68 benchmark.
- The seed is regular-graph-specific and the factor you want
  destroys vertex transitivity.
