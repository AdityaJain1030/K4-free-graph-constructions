# Cay(D_28, —) beating circulants at N=28

**Slug:** `D28_N28_win`
**Significance:** Dihedral group wins over cyclic on 28 vertices. c=0.7708 (was 0.7755 via circulant).

## Core properties

| key | value |
|---|---|
| N | 28 |
| m (edges) | 98 |
| d_max | 7 |
| d_min | 7 |
| regular | yes |
| α | 6 |
| c_log = α·d_max/(n·ln d_max) | **0.7708** |
| girth | 3 |
| triangles | 56 |
| spectral radius (λ_max) | 7.0000 |
| λ_min | -4.4058 |
| Hoffman H = n(-λ_min)/(d - λ_min) | 10.8158 |
| α / H (saturation ratio) | 0.5547 |

## Construction metadata

```json
{
  "group": "SG_28_3_D28",
  "connection_set": [
    12,
    20,
    25,
    7,
    19,
    10,
    22
  ],
  "surrogate_c_log": 0.7708475135546261,
  "tabu_n_iters": 300,
  "tabu_best_iter": 3
}
```

## Canonical sparse6

```
:[_____B_C_@ADEhGggIgHJhIhKLiJLMaF`FaEKLNO`DHJMPaCGLNOcEGKNOSbDIJMP`BHIMPUaCEGKLQ`BDHIJR`ABCOPbCDEOPY
```

([s6/D28_N28_win.s6](../s6/D28_N28_win.s6) has just the string.)

## Source

- DB source tag: `cayley_tabu_gap`
- graph_id (sha256[:16] of canonical sparse6): `1df3ee71678fac7d`
