# Pareto-optimal circulant Cay(Z_61, —)

**Slug:** `satcopt_N61`
**Significance:** UNIQUE-frontier: at N=61 no other source (Cayley, polarity, GAP, etc.) reaches this c_log. c=0.8544.

## Core properties

| key | value |
|---|---|
| N | 61 |
| m (edges) | 305 |
| d_max | 10 |
| d_min | 10 |
| regular | yes |
| α | 12 |
| c_log = α·d_max/(n·ln d_max) | **0.8544** |
| girth | 3 |
| triangles | 183 |
| spectral radius (λ_max) | 10.0000 |
| λ_min | -5.3758 |
| Hoffman H = n(-λ_min)/(d - λ_min) | 21.3272 |
| α / H (saturation ratio) | 0.5627 |

## Construction metadata

```json
{
  "connection_set": [
    1,
    2,
    15,
    21,
    22
  ],
  "degree": 10,
  "method": "sat_hoffman_warm",
  "n_sat_calls": 13
}
```

## Canonical sparse6

```
:|_OGCA@?_@g?U?CA`w?KKGCrp[qULeBhg}[Oeb`xMYMGDH_s[NHQpgw_PidypaeTKtApiYNHCqx_xMGCQ`[oZMorHkzCLFBsGUNGCQPKn@EBq@CcSKGWg_e^b@qaAGHFEcALHBDBRH|Ec_a@Wo]PHeWO[UKGCa`iCDJDra@J@BDR@k}e_`PXGeTKfs{GKKGdAph?g`AbQHGk_aRIDEj_a`Ws_ZRidsGQKFBra`Ql`@@_wcRJFBrAABDbQHOiZMjwWSKTOGssOIEJFsaUACCBrH|EmXo_W[_YOHDjQEDCA`Yh[ta@_wcWhUle{OIGCeRaPes``_wgsZPkubeABBaAHlKiVLwOOMGHFCidYw
```

([s6/satcopt_N61.s6](../s6/satcopt_N61.s6) has just the string.)

## Source

- DB source tag: `sat_circulant_optimal`
- graph_id (sha256[:16] of canonical sparse6): `306c877214cbce07`
