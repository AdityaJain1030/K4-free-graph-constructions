# Orphaned graph data

Records in this table were produced under a source tag that no longer matches
any active search class. They are still valid graphs but won't be updated by
future runs and sit outside the normal source→class mapping.

| File | Old source tag | New source tag | Reason |
|---|---|---|---|
| `graphs/cayley.json` | `cayley` | `prime_circulants` | `CayleyResidueSearch` renamed to `PrimeCirculantSearch`; `name` attribute changed from `"cayley"` to `"prime_circulants"` |
| `graphs/cayley_tabu_gap.json` | `cayley_tabu_gap` | — | Not orphaned; `CayleyTabuGapSearch.name` unchanged |

**To regenerate:** run `scripts/run_cayley.py` — new results land in
`graphs/prime_circulants.json` under source tag `prime_circulants`. The old
`graphs/cayley.json` can be deleted once you're satisfied the new run covers
the same parameter space.
