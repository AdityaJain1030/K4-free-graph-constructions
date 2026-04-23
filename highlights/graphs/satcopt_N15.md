# Pareto-optimal circulant Cay(Z_15, —)

**Slug:** `satcopt_N15`
**Significance:** Best circulant at N=15. The SAT-certified overall extremum is *non-Cayley* here — this is the cyclic-group best, weaker than sat_exact.

## Core properties

| key | value |
|---|---|
| N | 15 |
| m (edges) | 45 |
| d_max | 6 |
| d_min | 6 |
| regular | yes |
| α | 4 |
| c_log = α·d_max/(n·ln d_max) | **0.8930** |
| girth | 3 |
| triangles | 15 |
| spectral radius (λ_max) | 6.0000 |
| λ_min | -3.7834 |
| Hoffman H = n(-λ_min)/(d - λ_min) | 5.8007 |
| α / H (saturation ratio) | 0.6896 |

## Construction metadata

```json
{
  "connection_set": [
    1,
    2,
    6
  ],
  "degree": 6,
  "method": "sat_hoffman_warm",
  "n_sat_calls": 5
}
```

## Canonical sparse6

```
:N`ACGB_OkbPJCXRqGXAXBG\AWbG\AgaGS{PBK`n
```

([s6/satcopt_N15.s6](../s6/satcopt_N15.s6) has just the string.)

## Source

- DB source tag: `sat_circulant_optimal`
- graph_id (sha256[:16] of canonical sparse6): `7b179f6998a7ad13`
