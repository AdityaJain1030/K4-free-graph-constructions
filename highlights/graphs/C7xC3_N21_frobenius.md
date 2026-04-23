# Cay(C_7 ⋊ C_3, —) — Frobenius F_21

**Slug:** `C7xC3_N21_frobenius`
**Significance:** The Frobenius group of order 21 gives c=0.7328 — tied, but it was entirely outside the hand-coded search space until the GAP extension.

## Core properties

| key | value |
|---|---|
| N | 21 |
| m (edges) | 84 |
| d_max | 8 |
| d_min | 8 |
| regular | yes |
| α | 4 |
| c_log = α·d_max/(n·ln d_max) | **0.7328** |
| girth | 3 |
| triangles | 77 |
| spectral radius (λ_max) | 8.0000 |
| λ_min | -2.7187 |
| Hoffman H = n(-λ_min)/(d - λ_min) | 5.3265 |
| α / H (saturation ratio) | 0.7510 |

## Construction metadata

```json
{
  "group": "SG_21_1_C7:C3",
  "connection_set": [
    2,
    17,
    4,
    12,
    7,
    20,
    8,
    11
  ],
  "surrogate_c_log": 0.7327974810864577,
  "tabu_n_iters": 300,
  "tabu_best_iter": 4
}
```

## Canonical sparse6

```
:T____B_@C_ABD_@B_ACFdEbCcDGHIbEFHIJ`FGHKaFGHJ`BFIMaCGIL`CDHLNOaBEHMNOP`AEIKLO`ADIJMNR
```

([s6/C7xC3_N21_frobenius.s6](../s6/C7xC3_N21_frobenius.s6) has just the string.)

## Source

- DB source tag: `cayley_tabu_gap`
- graph_id (sha256[:16] of canonical sparse6): `94aba0c67d46d31a`
