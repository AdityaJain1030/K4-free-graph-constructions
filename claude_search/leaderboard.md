# Leaderboard (110 evaluations)

## Family status (non-VT families are the target — VT is informational only)

```
# --- non-VT families ---
core_periphery         best=1.3049  attempts=58  stale=36  -> STALE  [gen_051_rr_multistart_best]
structure_plus_noise   best=2.4349  attempts=1   stale=0   -> ACTIVE (underexplored)  [gen_077_5partite_k4free]
asymmetric_lift        best=2.4377  attempts=9   stale=6   -> ACTIVE  [gen_024_full_crossedge_lift]
voltage_partial        best=2.6268  attempts=2   stale=0   -> ACTIVE (underexplored)  [gen_090_random_circulant_best]
srg_perturbed          best=2.6945  attempts=1   stale=0   -> ACTIVE (underexplored)  [gen_076_clebsch_perturb]
invented               best=2.8298  attempts=2   stale=1   -> ACTIVE (underexplored)  [gen_078_schrijver_kneser]
crossover              best=2.8410  attempts=1   stale=0   -> ACTIVE (underexplored)  [gen_018_er_lift_k4free_crossover]
two_orbit              best=3.1534  attempts=3   stale=1   -> ACTIVE  [gen_071_latin_square_graph]
perturbed_paley        (no attempts)                         -> UNEXPLORED
sat_seeded             (no attempts)                         -> UNEXPLORED
# --- VT families (historical; not to be targeted) ---
random_process         best=1.6320  attempts=9   stale=2   -> ACTIVE  [gen_050_degcap_large]
polarity               best=1.7264  attempts=12  stale=5   -> ACTIVE  [gen_029_er_polarity_q11]
incidence_bipartite    best=3.0463  attempts=3   stale=1   -> ACTIVE  [gen_014_two_orbit_bipartite]
srg_perturb            best=3.9548  attempts=1   stale=0   -> ACTIVE (underexplored)  [gen_017_srg_clebsch_perturb]
hermitian_pencil       best=4.5006  attempts=8   stale=0   -> ACTIVE  [gen_068_mv_multistart]
```

## Recent thoughts (last 10 candidates)

- **gen_089_n35_greedy_select** [core_periphery, best_c=1.1032]
    hyp: greedy IS proxies well for seed selection; top-1 by greedy at N=35 may have α≤9
    non-VT: random configuration model generically non-VT
- **gen_090_random_circulant_best** [voltage_partial, best_c=0.9658]
    hyp: right connection set S in C(N,S) gives K4-free with much smaller α than random RR
    non-VT: 5 random asymmetric edge swaps after best circulant found break all Aut
- **gen_091_n35_d7_sweep** [core_periphery, best_c=1.0580]
    hyp: at N=35 d=7, lucky seed achieves α=9 (c=0.925 < 0.9593 gen_037 best)
    non-VT: random regular construction generically non-VT
- **gen_092_graph_product_k4free** [invented, best_c=1.0011]
    hyp: Cartesian product of two K4-free graphs is K4-free; careful choice gives α improvement
    non-VT: product of non-VT graphs is non-VT; asymmetric random base factors
- **gen_091_n35_d7_sweep** [core_periphery, best_c=1.0580]
    hyp: at N=35 d=7, lucky seed achieves α=9 (c=0.925 < 0.9593 gen_037 best)
    non-VT: random regular construction generically non-VT
- **gen_093_edge_delete_alpha_stable** [core_periphery, best_c=1.0356]
    hyp: many edges in gen_037 N=30 graph are IS-irrelevant; removing them drops d_max→4 at α=8
    non-VT: original non-VT; edge deletion makes it more irregular
- **gen_094_gen037_edge_delete** [core_periphery, best_c=0.9593]
    hyp: gen_037(N=30) has α=8, d=7; deleting IS-irrelevant edges brings d→5, c→0.894
    non-VT: original non-VT; edge deletion makes it more irregular
- **gen_095_rr_d4_n30** [core_periphery, best_c=1.0356]
    hyp: d=4 random K4-free at N=30 has α≤9 with lucky seed; c=9*4/(30*1.386)=0.866<0.959
    non-VT: random configuration model generically non-VT
- **gen_096_rr_d3_all_n** [core_periphery, best_c=1.0356]
    hyp: K4-free 3-regular + saturation gives d_max=4 with lower α at large N
    non-VT: random configuration model generically non-VT
- **gen_037_random_regular_k4free** [core_periphery, best_c=0.9593]
    hyp: random d-regular starting point may have smaller α than greedy-built graph at same d
    non-VT: random regular graph plus K4 fixing destroys regularity → vertex-inhomogeneous degrees

## Top 20 by best_c

| rank | gen_id                       | family         | best_c | best_c_N | beats_P17 | valid_N | code_len |
|------|------------------------------|----------------|--------|----------|-----------|---------|----------|
| 1    | gen_051_rr_multistart_best   | core_periphery | 1.0259 | 30       |           | 71      | 279      |
| 2    | gen_055_targeted_n35         | core_periphery | 0.9893 | 35       |           | 11      | 362      |
| 3    | gen_055_targeted_n35         | core_periphery | 0.9893 | 35       |           | 11      | 362      |
| 4    | gen_038_multistart_hillclimb | core_periphery | 1.0117 | 32       |           | 71      | 502      |
| 5    | gen_050_degcap_large         | random_process | 1.0240 | 32       |           | 71      | 608      |
| 6    | gen_026_bohman_degree_cap    | random_process | 1.0117 | 32       |           | 71      | 664      |
| 7    | gen_026_bohman_degree_cap    | random_process | 1.0117 | 32       |           | 71      | 664      |
| 8    | gen_089_n35_greedy_select    | core_periphery | 1.1032 | 34       |           | 3       | 594      |
| 9    | gen_079_n35_intensive_sweep  | core_periphery | 1.0834 | 34       |           | 9       | 636      |
| 10   | gen_029_er_polarity_q11      | polarity       | 1.0124 | 57       |           | 2       | 714      |
| 11   | gen_059_k4free_nocap         | random_process | 1.2924 | 30       |           | 71      | 464      |
| 12   | gen_025_er_polarity_twisted  | polarity       | 1.0124 | 57       |           | 2       | 894      |
| 13   | gen_013_bohman_keevash       | random_process | 1.3111 | 38       |           | 71      | 625      |
| 14   | gen_043_rr_no_resaturation   | core_periphery | 1.0802 | 31       |           | 71      | 999      |
| 15   | gen_072_ramsey_greedy_k4     | random_process | 1.0444 | 31       |           | 71      | 1100     |
| 16   | gen_027_antiIS_process       | random_process | 1.0278 | 35       |           | 71      | 1251     |
| 17   | gen_066_dense_k4removal_only | core_periphery | 1.0992 | 35       |           | 71      | 1224     |
| 18   | gen_056_er_local_improve     | polarity       | 1.0462 | 57       |           | 2       | 1278     |
| 19   | gen_056_er_local_improve     | polarity       | 1.0462 | 57       |           | 2       | 1278     |
| 20   | gen_085_n30_intensive        | core_periphery | 1.0792 | 30       |           | 1       | 1268     |

## Per-N breakdown (top 5 by best_c, showing N=[17, 30, 34, 40, 51, 60, 68, 85, 100])

| gen_id                       | N=17 | N=30   | N=34   | N=40   | N=51   | N=60   | N=68   | N=85   | N=100  |
|------------------------------|------|--------|--------|--------|--------|--------|--------|--------|--------|
| gen_051_rr_multistart_best   | -    | 1.0259 | 1.1315 | 1.2288 | 1.1070 | 1.1581 | 1.1468 | 1.1931 | 1.1657 |
| gen_055_targeted_n35         | -    | 1.0259 | 1.1315 | 1.0240 | -      | -      | -      | -      | -      |
| gen_055_targeted_n35         | -    | 1.0259 | 1.1315 | 1.0240 | -      | -      | -      | -      | -      |
| gen_038_multistart_hillclimb | -    | 1.0792 | 1.0580 | 1.0580 | 1.1244 | 1.0923 | 1.1496 | 1.1873 | 1.2073 |
| gen_050_degcap_large         | -    | 1.2288 | 1.0843 | 1.0857 | 1.1693 | 1.1468 | 1.1363 | 1.1925 | 1.1671 |

## Frontier: best c at each N across all evaluations

| N   | best_c | gen_id                         |
|-----|--------|--------------------------------|
| 30  | 0.9593 | gen_037_random_regular_k4free  |
| 31  | 0.9722 | gen_094_gen037_edge_delete     |
| 32  | 1.0117 | gen_026_bohman_degree_cap      |
| 33  | 0.9811 | gen_030_exact_alpha_hillclimb  |
| 34  | 1.0184 | gen_045_rr_mcmc_swaps          |
| 35  | 0.9893 | gen_040_rr_greedy_hillclimb    |
| 36  | 1.0194 | gen_083_circulant_perturb      |
| 37  | 1.0036 | gen_083_circulant_perturb      |
| 38  | 1.0575 | gen_082_rr_d5_large_n          |
| 39  | 1.0356 | gen_096_rr_d3_all_n            |
| 40  | 1.0240 | gen_055_targeted_n35           |
| 41  | 0.9889 | gen_090_random_circulant_best  |
| 42  | 1.0728 | gen_045_rr_mcmc_swaps          |
| 43  | 1.0736 | gen_026_bohman_degree_cap      |
| 44  | 1.0240 | gen_045_rr_mcmc_swaps          |
| 45  | 1.0616 | gen_040_rr_greedy_hillclimb    |
| 46  | 1.0685 | gen_040_rr_greedy_hillclimb    |
| 47  | 1.0641 | gen_033_IS_aware_construction  |
| 48  | 1.0240 | gen_063_rr_many_seeds          |
| 49  | 1.0011 | gen_092_graph_product_k4free   |
| 50  | 0.9970 | gen_083_circulant_perturb      |
| 51  | 1.1070 | gen_040_rr_greedy_hillclimb    |
| 52  | 1.0857 | gen_045_rr_mcmc_swaps          |
| 53  | 1.0653 | gen_040_rr_greedy_hillclimb    |
| 54  | 1.0194 | gen_083_circulant_perturb      |
| 55  | 1.0959 | gen_082_rr_d5_large_n          |
| 56  | 1.0764 | gen_082_rr_d5_large_n          |
| 57  | 1.0124 | gen_008_er_polarity            |
| 58  | 1.0486 | gen_083_circulant_perturb      |
| 59  | 1.1041 | gen_064_rr_exact_select        |
| 60  | 1.0857 | gen_063_rr_many_seeds          |
| 61  | 1.0679 | gen_064_rr_exact_select        |
| 62  | 1.1024 | gen_095_rr_d4_n30              |
| 63  | 1.0922 | gen_050_degcap_large           |
| 64  | 1.0857 | gen_033_IS_aware_construction  |
| 65  | 1.1144 | gen_045_rr_mcmc_swaps          |
| 66  | 1.0528 | gen_027_antiIS_process         |
| 67  | 1.1004 | gen_044_circulant_perturbed    |
| 68  | 1.0857 | gen_027_antiIS_process         |
| 69  | 1.0637 | gen_048_rr_mindeg_resaturation |
| 70  | 1.1003 | gen_082_rr_d5_large_n          |
| 71  | 1.0883 | gen_051_rr_multistart_best     |
| 72  | 1.0770 | gen_090_random_circulant_best  |
| 73  | 1.1246 | gen_040_rr_greedy_hillclimb    |
| 74  | 1.1094 | gen_042_rr_higher_degree       |
| 75  | 1.1002 | gen_027_antiIS_process         |
| 76  | 1.1037 | gen_095_rr_d4_n30              |
| 77  | 1.1280 | gen_026_bohman_degree_cap      |
| 78  | 1.1136 | gen_026_bohman_degree_cap      |
| 79  | 1.1404 | gen_096_rr_d3_all_n            |
| 80  | 1.0752 | gen_044_circulant_perturbed    |
| 81  | 1.1123 | gen_096_rr_d3_all_n            |
| 82  | 1.1126 | gen_042_rr_higher_degree       |
| 83  | 1.1054 | gen_027_antiIS_process         |
| 84  | 1.1095 | gen_095_rr_d4_n30              |
| 85  | 1.1330 | gen_096_rr_d3_all_n            |
| 86  | 1.1202 | gen_027_antiIS_process         |
| 87  | 1.1069 | gen_083_circulant_perturb      |
| 88  | 1.1416 | gen_082_rr_d5_large_n          |
| 89  | 1.0911 | gen_082_rr_d5_large_n          |
| 90  | 1.1214 | gen_033_IS_aware_construction  |
| 91  | 1.1090 | gen_033_IS_aware_construction  |
| 92  | 1.1284 | gen_082_rr_d5_large_n          |
| 93  | 1.1345 | gen_027_antiIS_process         |
| 94  | 1.1224 | gen_027_antiIS_process         |
| 95  | 1.1183 | gen_051_rr_multistart_best     |
| 96  | 1.1242 | gen_076_clebsch_perturb        |
| 97  | 1.1350 | gen_033_IS_aware_construction  |
| 98  | 1.1095 | gen_095_rr_d4_n30              |
| 99  | 1.1297 | gen_096_rr_d3_all_n            |
| 100 | 1.1184 | gen_095_rr_d4_n30              |
| 110 | 1.1853 | gen_030_exact_alpha_hillclimb  |
| 120 | 1.2073 | gen_030_exact_alpha_hillclimb  |
| 133 | 1.1813 | gen_037_random_regular_k4free  |
| 150 | 1.2024 | gen_037_random_regular_k4free  |

## Summary stats

- Total evaluations: **110**
- Non-VT candidates: **77** / 110
- Stage 2 triggered (best_c<1.0 in Stage 1): **20**
- Achieved best_c < 1.0: **20**
- **Beat P(17) (best_c < 0.6789): 0**
- Timestamp range: 2026-04-22T04:59:16.858035+00:00 → 2026-04-22T07:40:51.049939+00:00

## Failure analysis

| reason        | count | % of all per-N evals |
|---------------|-------|----------------------|
| d_max_too_low | 3166  | 40.5%                |
| crash         | 218   | 2.8%                 |
| timeout       | 98    | 1.3%                 |
| not_k4_free   | 23    | 0.3%                 |