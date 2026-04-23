# Pareto-optimal circulant Cay(Z_14, —)

**Slug:** `satcopt_N14`
**Significance:** Best circulant at N=14. Matches the SAT-certified overall optimum; the circulant extremum *is* the extremum.

## Core properties

| key | value |
|---|---|
| N | 14 |
| m (edges) | 28 |
| d_max | 4 |
| d_min | 4 |
| regular | yes |
| α | 4 |
| c_log = α·d_max/(n·ln d_max) | **0.8244** |
| girth | 3 |
| triangles | 14 |
| spectral radius (λ_max) | 4.0000 |
| λ_min | -2.2470 |
| Hoffman H = n(-λ_min)/(d - λ_min) | 5.0357 |
| α / H (saturation ratio) | 0.7943 |

## Construction metadata

```json
{
  "connection_set": [
    1,
    2
  ],
  "degree": 4,
  "method": "sat_hoffman_warm",
  "n_sat_calls": 5
}
```

## Canonical sparse6

```
:M`A?g@FWlRTLS{RGc\KQGTGYT~
```

([s6/satcopt_N14.s6](../s6/satcopt_N14.s6) has just the string.)

## Source

- DB source tag: `sat_circulant_optimal`
- graph_id (sha256[:16] of canonical sparse6): `e822613277e729b5`
