# Certified-optimal K4-free graph, N=20

**Slug:** `sat_exact_N20`
**Significance:** CP-SAT-proven minimum c_log over ALL K4-free graphs on 20 vertices.

## Core properties

| key | value |
|---|---|
| N | 20 |
| m (edges) | 70 |
| d_max | 7 |
| d_min | 7 |
| regular | yes |
| α | 4 |
| c_log = α·d_max/(n·ln d_max) | **0.7195** |
| girth | 3 |
| triangles | 48 |
| spectral radius (λ_max) | 7.0000 |
| λ_min | -3.1739 |
| Hoffman H = n(-λ_min)/(d - λ_min) | 6.2393 |
| α / H (saturation ratio) | 0.6411 |

## Construction metadata

```json
{
  "alpha_target": 4,
  "d_max_target": 7,
  "status": "FEASIBLE",
  "solve_s": 16.011
}
```

## Canonical sparse6

```
:S__@_@___ACD_BCDd`A`BH`DGIcDGHaFHIKcEGIKLcFGJMbEIJL`ABGJKOaCEHNObDFGHNQ
```

([s6/sat_exact_N20.s6](../s6/sat_exact_N20.s6) has just the string.)

## Source

- DB source tag: `sat_exact`
- graph_id (sha256[:16] of canonical sparse6): `d76f4a61474cfb29`
