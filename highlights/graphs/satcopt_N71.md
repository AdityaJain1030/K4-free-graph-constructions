# Pareto-optimal circulant Cay(Z_71, —)

**Slug:** `satcopt_N71`
**Significance:** UNIQUE-frontier at N=71 (prime; only C_71 available, tabu can't compete).

## Core properties

| key | value |
|---|---|
| N | 71 |
| m (edges) | 426 |
| d_max | 12 |
| d_min | 12 |
| regular | yes |
| α | 13 |
| c_log = α·d_max/(n·ln d_max) | **0.8842** |
| girth | 3 |
| triangles | 355 |
| spectral radius (λ_max) | 12.0000 |
| λ_min | -4.7171 |
| Hoffman H = n(-λ_min)/(d - λ_min) | 20.0343 |
| α / H (saturation ratio) | 0.6489 |

## Construction metadata

```json
{
  "connection_set": [
    1,
    2,
    4,
    11,
    18,
    22
  ],
  "degree": 12,
  "method": "sat_hoffman_warm",
  "n_sat_calls": 14
}
```

## Canonical sparse6

```
:~?@F_G?@_G?B_GA??oU?@?Y??W?AAW?DA?e?@_[IcPANCW{Qc@EMCPKSbPGRDGWMBp?R`OsNC@OVapIKCW_LDW[MDgGCCpWXEgCBD@SXEgGBC@CYFPy@@?{QEPs]_OSRDP]A@`OUEGGDBpCQEaE@@`?PC`ca_oSLCPSZ`?WMC`W[_Ok[GWGKEqIBAPgZFaaCA`c[FQ[h_ogVFqCfIQiCAP__Ga_hIgKKBqCbIwOJCAGcJGGFBP?QEp{bIGCGB_{PFA?cHwCFBPKSD`w`Gq}AA?wRD@S\GaOo_o[NC@OVFASl`?_NC@KWEqWm`OcOEp{`IAss`_gNFA?aHqwr`_oMCp[YFQ?kJbYDAosSE@c]FqklLWSFC`KWFASeIaos`__PD@[ZHQWhIrMIB@SYFa?`Hq_uaOkUEPs^Ga[gLW_HBOwUEASkKBqFA_sMDP[eIq{z`ooLBpCTE`k[JR?}a?kMC@GUEPk[Ja{|_oOEB?wXHa[iJRqB@?SJBPgdIAcmMwCAA_oLEQOgJbCwOgCAAOkMEaKfJRGvOWSFAOgbHacpLBSyNgWGAOgcHQgqKrWxN^
```

([s6/satcopt_N71.s6](../s6/satcopt_N71.s6) has just the string.)

## Source

- DB source tag: `sat_circulant_optimal`
- graph_id (sha256[:16] of canonical sparse6): `a303322b3821ca1c`
