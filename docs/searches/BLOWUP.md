# `BlowupSearch` — lex / tensor product blow-ups of seed graphs

## What it does

Probe 4 from the landscape study. Lifts a small K₄-free seed graph
out of `graph_db` and produces a structured large-N graph via a
product:

- **Lex blow-up `G[I_k]`.** Each vertex of the seed is replaced by
  an independent set of size `k`. K₄-free because any K₄ in `G[I_k]`
  projects to a K₄ in `G`. `N = n_seed · k`; `α(G[I_k]) = k · α(G)`;
  `d_max = k · d_seed`.
- **Tensor blow-up `G × H`.** Both factors K₄-free; the product is
  K₄-free for the same projection argument. Useful for combining two
  different algebraic seeds.

## Why it exists

`c_log` of the lex blow-up is worse than the seed by a factor
`k · ln(d_seed) / ln(k · d_seed)` — for `k = 2, d = 8` that's ≈ 1.50.
So blow-ups are **not competitive on their own**. The point is to
produce *structured* starting points at large N for a downstream
edge-switch polish or SAT warm start. Comparing "blow-up + polish"
vs "random + polish" (Probe 1) at the same N is one of the cleanest
signals the landscape study needs.

## Kwargs

| kwarg                | hard/soft | meaning                                                 |
|----------------------|-----------|---------------------------------------------------------|
| `mode`               | hard      | `"lex"` or `"tensor"`                                   |
| `k`                  | hard      | Size of the independent set in lex mode                 |
| `seed_source`        | soft      | Restrict seed search to a graph_db source tag           |
| `seed_id`            | hard      | Pick a specific seed graph_id (overrides source/n)      |
| `seed_n`             | soft      | Restrict seed selection to graphs on `seed_n` vertices  |
| `other_source/id/n`  | —         | Same for the second factor when `mode == "tensor"`      |

Seed resolution (in order of priority): `seed_id` → frontier-min
`c_log` over `(seed_source, seed_n)` → overall frontier for
`seed_source`.

## Notes on the constructor `n`

The search is parameterised by `n` for API consistency, but the
output size is determined entirely by the seed and `k`/`other`.
After construction `self.n` is reset to the actual product size
so base-class scoring uses the real N.

## What to expect from it

- `BlowupSearch(n=0, mode="lex", seed_source="circulant",
  seed_n=17, k=2)` — P(17) lexed into 34 vertices. Resulting
  `c_log` ≈ 1.01 (worse than the seed's 0.68), but the graph has
  the Paley spectral structure preserved.
- Chain the output through `RandomRegularSwitchSearch` locally (not
  yet automated — ingest, pick by id, then feed as a seed with
  `num_switches=500`) to measure how much the polish recovers.

## When to reach for it

- Generating large-N structured seeds for downstream polish.
- Stress-testing the K₄-free scoring pipeline on big graphs
  (products easily push N above 100).

## When **not** to reach for it

- You want competitive `c_log` out of the box. Blow-ups alone
  don't cross the 0.68 benchmark.
- The seed is regular-graph-specific and the factor you want
  destroys vertex transitivity.
