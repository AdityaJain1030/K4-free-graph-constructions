# Cay(S_3 × S_3, —)

**Slug:** `S3xS3_N36_win`
**Significance:** Non-abelian group beats every abelian Cayley and circulant at N=36. Δ=−0.0203 — biggest win of the GAP sweep at small N.

## Core properties

| key | value |
|---|---|
| N | 36 |
| m (edges) | 180 |
| d_max | 10 |
| d_min | 10 |
| regular | yes |
| α | 6 |
| c_log = α·d_max/(n·ln d_max) | **0.7238** |
| girth | 3 |
| triangles | 156 |
| spectral radius (λ_max) | 10.0000 |
| λ_min | -3.7321 |
| Hoffman H = n(-λ_min)/(d - λ_min) | 9.7840 |
| α / H (saturation ratio) | 0.6132 |

## Construction metadata

```json
{
  "group": "SG_36_10_S3xS3",
  "connection_set": [
    2,
    13,
    23,
    35,
    19,
    29,
    21,
    22,
    27,
    33
  ],
  "surrogate_c_log": 0.7238241365054197,
  "tabu_n_iters": 600,
  "tabu_best_iter": 65
}
```

## Canonical sparse6

```
:c_OG?I@?AO?c?B?@@w?CEG_@Oo[RDdO`?mCCEOOOuCEDbg__WLFopGwbBBaphIIHDcASKGKFBqHIGFEB`xCf@BApg{hEDB@h?eSJoogk_RIdrCSKIDb@xSlAAa@x?aSKoOOOWLFDr[CMGHCqheEEBcAPOkVMoo_cWRIDb`s|@A``?ooYMp?gWSJFCQQAAFCa`gw]OLfGGGEFCAPXh?`
```

([s6/S3xS3_N36_win.s6](../s6/S3xS3_N36_win.s6) has just the string.)

## Source

- DB source tag: `cayley_tabu_gap`
- graph_id (sha256[:16] of canonical sparse6): `36f64e06d3c7c839`
