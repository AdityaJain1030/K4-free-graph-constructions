# Leaderboard (20 evaluations)

## Top 20 by primary score

| rank | gen_id                     | score  | best_c | best_c_N | regularity | code_len |
|------|----------------------------|--------|--------|----------|------------|----------|
| 1    | gen_016_offset_1_2         | 1.2865 | 0.9618 | 30       | 0.4653     | 266      |
| 2    | gen_016_offset_1_2         | 1.2865 | 0.9618 | 21       | 0.4741     | 266      |
| 3    | gen_004_paley_cubic        | 1.3149 | 0.7050 | 19       | 1.0000     | 407      |
| 4    | gen_010_cubic_plus_offsets | 1.3609 | 0.7050 | 19       | 1.0000     | 453      |
| 5    | gen_018_offset_1_4         | 1.4620 | 1.1542 | 20       | 0.4573     | 266      |
| 6    | gen_017_offset_2_3         | 1.4945 | 1.1542 | 20       | 0.4368     | 266      |
| 7    | gen_003_paley_qr           | 1.6935 | 0.7728 | 13       | 0.8333     | 413      |
| 8    | gen_008_paley_quartic      | 1.6993 | 0.8977 | 30       | 0.7478     | 416      |
| 9    | gen_011_product_graph      | 1.6998 | 0.9618 | 30       | 0.7402     | 738      |
| 10   | gen_015_offset_1_3         | 1.7577 | 1.4427 | 20       | 0.4517     | 266      |
| 11   | gen_009_paley_sextic       | 1.8243 | 0.8145 | 37       | 0.7152     | 421      |
| 12   | gen_007_random_k4free      | 1.8684 | 1.0503 | 13       | 0.7877     | 687      |
| 13   | gen_014_greedy_high_degree | 2.1515 | 0.8812 | 19       | 0.9293     | 737      |
| 14   | gen_012_cartesian_product  | 2.2897 | 1.4427 | 30       | 0.3716     | 847      |
| 15   | gen_006_greedy_k4free      | 2.3790 | 0.7728 | 13       | 0.9942     | 857      |
| 16   | gen_001_dihedral_cayley    | inf    | inf    | -        | 0.0000     | 799      |
| 17   | gen_002_circulant_offsets  | inf    | inf    | -        | 0.0000     | 288      |
| 18   | gen_005_hamming            | inf    | inf    | -        | 0.0000     | 346      |
| 19   | gen_013_cubic_quad_union   | inf    | inf    | -        | 0.0000     | 471      |
| 20   | gen_019_offset_1_2_3       | inf    | inf    | -        | 0.0000     | 272      |

## Top 10 by regularity score

| rank | gen_id                     | regularity | score  | best_c |
|------|----------------------------|------------|--------|--------|
| 1    | gen_004_paley_cubic        | 1.0000     | 1.3149 | 0.7050 |
| 2    | gen_010_cubic_plus_offsets | 1.0000     | 1.3609 | 0.7050 |
| 3    | gen_006_greedy_k4free      | 0.9942     | 2.3790 | 0.7728 |
| 4    | gen_014_greedy_high_degree | 0.9293     | 2.1515 | 0.8812 |
| 5    | gen_003_paley_qr           | 0.8333     | 1.6935 | 0.7728 |
| 6    | gen_007_random_k4free      | 0.7877     | 1.8684 | 1.0503 |
| 7    | gen_008_paley_quartic      | 0.7478     | 1.6993 | 0.8977 |
| 8    | gen_011_product_graph      | 0.7402     | 1.6998 | 0.9618 |
| 9    | gen_009_paley_sextic       | 0.7152     | 1.8243 | 0.8145 |
| 10   | gen_016_offset_1_2         | 0.4741     | 1.2865 | 0.9618 |

## Per-N breakdown (top 5 by score)

| gen_id                     | N=20   | N=25   | N=30   | N=40   | N=50   | N=60   |
|----------------------------|--------|--------|--------|--------|--------|--------|
| gen_016_offset_1_2         | 1.0099 | 1.0387 | 0.9618 | 1.0099 | 0.9810 | 0.9618 |
| gen_016_offset_1_2         | 1.0099 | 1.0387 | 0.9618 | 1.0099 | 0.9810 | 0.9618 |
| gen_004_paley_cubic        | -      | -      | -      | -      | -      | -      |
| gen_010_cubic_plus_offsets | -      | -      | -      | -      | -      | -      |
| gen_018_offset_1_4         | 1.1542 | 1.1542 | 1.1542 | 1.1542 | 1.1542 | 1.1542 |

## Frontier: best c at each N across all evaluations

| N  | best_c | gen_id                     |
|----|--------|----------------------------|
| 7  | 0.8244 | gen_006_greedy_k4free      |
| 11 | 0.9133 | gen_006_greedy_k4free      |
| 13 | 0.7728 | gen_003_paley_qr           |
| 19 | 0.7050 | gen_004_paley_cubic        |
| 20 | 1.0046 | gen_014_greedy_high_degree |
| 21 | 0.9618 | gen_016_offset_1_2         |
| 23 | 1.0036 | gen_016_offset_1_2         |
| 24 | 0.9618 | gen_016_offset_1_2         |
| 25 | 1.0387 | gen_016_offset_1_2         |
| 27 | 0.9618 | gen_016_offset_1_2         |
| 29 | 0.9950 | gen_016_offset_1_2         |
| 30 | 0.8977 | gen_008_paley_quartic      |
| 31 | 0.8406 | gen_004_paley_cubic        |
| 33 | 0.9618 | gen_016_offset_1_2         |
| 35 | 0.9893 | gen_016_offset_1_2         |
| 36 | 0.9618 | gen_016_offset_1_2         |
| 37 | 0.8145 | gen_009_paley_sextic       |
| 39 | 0.9618 | gen_016_offset_1_2         |
| 40 | 0.9893 | gen_009_paley_sextic       |
| 41 | 0.9853 | gen_016_offset_1_2         |
| 42 | 0.9618 | gen_016_offset_1_2         |
| 43 | 0.8636 | gen_004_paley_cubic        |
| 45 | 0.9618 | gen_016_offset_1_2         |
| 47 | 0.9823 | gen_016_offset_1_2         |
| 48 | 0.9618 | gen_016_offset_1_2         |
| 50 | 0.9810 | gen_016_offset_1_2         |
| 51 | 0.9618 | gen_016_offset_1_2         |
| 53 | 0.9799 | gen_016_offset_1_2         |
| 54 | 0.9618 | gen_016_offset_1_2         |
| 55 | 0.9968 | gen_016_offset_1_2         |
| 57 | 0.9618 | gen_016_offset_1_2         |
| 59 | 0.9781 | gen_016_offset_1_2         |
| 60 | 0.9618 | gen_011_product_graph      |
| 63 | 0.9618 | gen_016_offset_1_2         |
| 65 | 0.9766 | gen_016_offset_1_2         |
| 66 | 0.9618 | gen_016_offset_1_2         |
| 69 | 0.9618 | gen_016_offset_1_2         |
| 70 | 0.9893 | gen_016_offset_1_2         |
| 72 | 0.9618 | gen_016_offset_1_2         |
| 75 | 0.9618 | gen_016_offset_1_2         |

## Summary stats

- Total evaluations: **20**
- Stage 1 passed: **14**
- Achieved best_c < 1.0: **10**
- Timestamp range: 2026-04-17T20:46:06.244416+00:00 → 2026-04-17T20:55:20.732828+00:00

## Failure analysis

| reason              | count | % of all per-N evals |
|---------------------|-------|----------------------|
| not_k4_free         | 137   | 34.2%                |
| d_max_too_low       | 48    | 12.0%                |
| invalid_edge_format | 5     | 1.2%                 |