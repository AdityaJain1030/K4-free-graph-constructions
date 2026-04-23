# Pareto-optimal circulant Cay(Z_73, —)

**Slug:** `satcopt_N73`
**Significance:** UNIQUE-frontier at N=73 (prime). Beats polarity ER(8) same N.

## Core properties

| key | value |
|---|---|
| N | 73 |
| m (edges) | 365 |
| d_max | 10 |
| d_min | 10 |
| regular | yes |
| α | 15 |
| c_log = α·d_max/(n·ln d_max) | **0.8924** |
| girth | 3 |
| triangles | 365 |
| spectral radius (λ_max) | 10.0000 |
| λ_min | -4.2106 |
| Hoffman H = n(-λ_min)/(d - λ_min) | 21.6300 |
| α / H (saturation ratio) | 0.6935 |

## Construction metadata

```json
{
  "connection_set": [
    1,
    2,
    4,
    8,
    9
  ],
  "degree": 10,
  "method": "sat_hoffman_warm",
  "n_sat_calls": 15
}
```

## Canonical sparse6

```
:~?@H_GA?_?M?@G?B@W?A@g?@@W?A?oa??OOFAWsJbH?Nb?sNCGkMBpAKB`AJBO{RbO{Pb`?QaooMBpCQDGkKBP?PC`MTdgoYapeJCPSVb@GUEGkNC@OTEPuKBp?RD`g]aosOC`S[FwoMBpCUEqALB_{QCpOWGgsMC@CRD@[`b?wZFgkLF@uLD@SXFAYMCpWYEqUdIIWfe`k_GaUXF@{`HhSVF@s`HA]UE@k]GaKgea_heQ[id@s^HAWfJAsocpw_GqSgIqwnaAcjJa{q`qgkJR?p_`SXFQWiJBQ@D`g]HQcjKwWFFAgkLGSGEqcjKwGBEQooLwCCEaknMGGEFAWiKB[x_OSZHQcnMBi@A@gZFawnKrW{__[XF@slKBOtMwKEAOgvMWODAOgwMgKC@_[iKCAB@?SGIQ{~_OSEAac{Ns@A__SEAQgzNs@@_OOGA`ghLb_yOgGB@ocXIbSvMSE@?o_HJrKyOCHB__OFAb?sMR|@PN
```

([s6/satcopt_N73.s6](../s6/satcopt_N73.s6) has just the string.)

## Source

- DB source tag: `sat_circulant_optimal`
- graph_id (sha256[:16] of canonical sparse6): `54acdb1a1d0b1313`
