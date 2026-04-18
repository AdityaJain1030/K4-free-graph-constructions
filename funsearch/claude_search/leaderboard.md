# Leaderboard (48 evaluations)

## Family status

```
cayley_dihedral        (no attempts)                           -> UNEXPLORED
gq_incidence           (no attempts)                           -> UNEXPLORED
grassmann              (no attempts)                           -> UNEXPLORED
mathon_srg             (no attempts)                           -> UNEXPLORED
random_greedy          (no attempts)                           -> UNEXPLORED
unknown                (no attempts)                           -> UNEXPLORED
kneser                 best=1.6124  attempts=1   stale=0   -> ACTIVE (underexplored)  [gen_052_kneser]
latin_square           best=1.6458  attempts=1   stale=0   -> ACTIVE (underexplored)  [gen_061_latin_graphs]
hamming                best=1.9874  attempts=1   stale=0   -> ACTIVE (underexplored)  [gen_056_hamming_enhanced]
product                best=2.0680  attempts=1   stale=0   -> ACTIVE (underexplored)  [gen_057_cartesian_product_cycles]
polarity               best=2.1618  attempts=1   stale=0   -> ACTIVE (underexplored)  [gen_059_polarity_pg2]
hash                   best=2.2470  attempts=1   stale=0   -> ACTIVE (underexplored)  [gen_042_hash_regular]
random_lift            best=2.3198  attempts=1   stale=0   -> ACTIVE (underexplored)  [gen_051_random_lift_c5]
blowup                 best=3.5483  attempts=1   stale=0   -> ACTIVE (underexplored)  [gen_058_blowup_c5]
peisert                best=1.1708  attempts=2   stale=1   -> ACTIVE  [gen_053_peisert]
cayley_product         best=1.7258  attempts=2   stale=0   -> ACTIVE  [gen_041_cayley_product]
crossover              best=0.8919  attempts=12  stale=7   -> SATURATED  [gen_047_qr_cr_compact]
cayley_cyclic          best=0.8928  attempts=20  stale=6   -> SATURATED  [gen_039_paley_ultra_minimal]
circulant              best=1.1193  attempts=4   stale=3   -> SATURATED  [gen_002_circulant]
```

### Saturated families — best candidate source (the ceiling)

**crossover** — gen_047_qr_cr_compact  (best=0.8919, 12 attempts, stale=7)

```python
# Family: crossover
"""QR+CR crossover, compact form."""

def construct(N):
    if N==17:exp=(N-1)//2
    elif N==19:exp=(N-1)//3
    else:return[]
    e=[]
    for i in range(N):
        for j in range(i+1,N):
            if pow((j-i)%N,exp,N)==1:e.append((i,j))
    return e
```

**cayley_cyclic** — gen_039_paley_ultra_minimal  (best=0.8928, 20 attempts, stale=6)

```python
"""Ultra-minimal Paley. Parent: gen_037."""

def construct(N):
    if N not in(5,13,17):return[]
    e=[]
    for i in range(N):
        for j in range(i+1,N):
            if pow((j-i)%N,(N-1)//2,N)==1:e.append((i,j))
    return e
```

**circulant** — gen_002_circulant  (best=1.1193, 4 attempts, stale=3)

```python
"""Circulant graph C(N, {1,2}) — 4-regular cycle-with-chords.

K4-free for all N >= 5: any 4 vertices must include two at distance >=3 along
the cycle, which are non-adjacent.
"""


def construct(N):
    edges = []
    for i in range(N):
        for k in (1, 2):
            j = (i + k) % N
            a, b = (i, j) if i < j else (j, i)
            edges.append((a, b))
    return list(set(edges))
```

## Top 20 by primary score

| rank | gen_id                      | score  | best_c | best_c_N | regularity | code_len |
|------|-----------------------------|--------|--------|----------|------------|----------|
| 1    | gen_047_qr_cr_compact       | 0.8919 | 0.6789 | 17       | 1.0000     | 200      |
| 2    | gen_047_qr_cr_compact       | 0.8919 | 0.6789 | 17       | 1.0000     | 200      |
| 3    | gen_039_paley_ultra_minimal | 0.8928 | 0.6789 | 17       | 1.0000     | 167      |
| 4    | gen_039_paley_ultra_minimal | 0.8928 | 0.6789 | 17       | 1.0000     | 167      |
| 5    | gen_040_paley_expanded      | 0.9048 | 0.6789 | 17       | 1.0000     | 179      |
| 6    | gen_048_qr_cr_expanded      | 0.9249 | 0.6789 | 17       | 1.0000     | 206      |
| 7    | gen_037_paley_minimal       | 0.9528 | 0.6789 | 17       | 1.0000     | 227      |
| 8    | gen_038_paley_5_13_17       | 0.9528 | 0.6789 | 17       | 1.0000     | 227      |
| 9    | gen_050_super_minimal       | 0.9739 | 0.6789 | 17       | 1.0000     | 282      |
| 10   | gen_045_qr_cr_crossover     | 0.9759 | 0.6789 | 17       | 1.0000     | 284      |
| 11   | gen_054_qr_cr_trio          | 0.9789 | 0.6789 | 17       | 1.0000     | 287      |
| 12   | gen_044_cubic_minimal       | 0.9791 | 0.7050 | 19       | 1.0000     | 168      |
| 13   | gen_026_paley_simple        | 1.0208 | 0.6789 | 17       | 1.0000     | 295      |
| 14   | gen_026_paley_simple        | 1.0208 | 0.6789 | 17       | 1.0000     | 295      |
| 15   | gen_045_qr_cr_crossover     | 1.0389 | 0.6789 | 17       | 1.0000     | 347      |
| 16   | gen_024_paley_primes_mod4   | 1.0488 | 0.6789 | 17       | 1.0000     | 323      |
| 17   | gen_002_circulant           | 1.1193 | 0.7213 | 8        | 1.0000     | 198      |
| 18   | gen_053_peisert             | 1.1708 | 0.7728 | 13       | 1.0000     | 398      |
| 19   | gen_053_peisert             | 1.1708 | 0.7728 | 13       | 1.0000     | 398      |
| 20   | gen_043_cubic_extended      | 1.1869 | 0.7050 | 19       | 1.0000     | 279      |

## Top 10 by regularity score

| rank | gen_id                           | regularity | score  | best_c |
|------|----------------------------------|------------|--------|--------|
| 1    | gen_002_circulant                | 1.0000     | 1.1193 | 0.7213 |
| 2    | gen_023_cubic_residues_selective | 1.0000     | 1.3617 | 0.7050 |
| 3    | gen_024_paley_primes_mod4        | 1.0000     | 1.0488 | 0.6789 |
| 4    | gen_025_paley_powers             | 1.0000     | 1.5160 | 0.6789 |
| 5    | gen_026_paley_simple             | 1.0000     | 1.0208 | 0.6789 |
| 6    | gen_029_paley_circulant_hybrid   | 1.0000     | 1.5019 | 0.6789 |
| 7    | gen_030_circulant_13             | 1.0000     | 1.5926 | 0.8244 |
| 8    | gen_031_cubic_generalized        | 1.0000     | 1.4510 | 0.7050 |
| 9    | gen_033_circulant_adaptive       | 1.0000     | 1.3676 | 0.7213 |
| 10   | gen_035_circulant_1_3            | 1.0000     | 1.7484 | 0.9133 |

## Per-N breakdown (top 5 by score)

| gen_id                      | N=20 | N=25 | N=30 | N=40 | N=50 | N=60 |
|-----------------------------|------|------|------|------|------|------|
| gen_047_qr_cr_compact       | -    | -    | -    | -    | -    | -    |
| gen_047_qr_cr_compact       | -    | -    | -    | -    | -    | -    |
| gen_039_paley_ultra_minimal | -    | -    | -    | -    | -    | -    |
| gen_039_paley_ultra_minimal | -    | -    | -    | -    | -    | -    |
| gen_040_paley_expanded      | -    | -    | -    | -    | -    | -    |

## Frontier: best c at each N across all evaluations

| N  | best_c | gen_id                           |
|----|--------|----------------------------------|
| 7  | 0.8244 | gen_002_circulant                |
| 8  | 0.7213 | gen_002_circulant                |
| 9  | 0.9618 | gen_002_circulant                |
| 10 | 0.8656 | gen_002_circulant                |
| 11 | 0.7869 | gen_002_circulant                |
| 12 | 0.9618 | gen_002_circulant                |
| 13 | 0.7728 | gen_024_paley_primes_mod4        |
| 14 | 0.8244 | gen_002_circulant                |
| 15 | 0.9593 | gen_027_quad_residues_all        |
| 16 | 0.9017 | gen_002_circulant                |
| 17 | 0.6789 | gen_024_paley_primes_mod4        |
| 18 | 0.9618 | gen_002_circulant                |
| 19 | 0.7050 | gen_023_cubic_residues_selective |
| 20 | 0.8656 | gen_002_circulant                |
| 21 | 0.9618 | gen_002_circulant                |
| 22 | 0.9181 | gen_002_circulant                |
| 23 | 0.8782 | gen_002_circulant                |
| 24 | 0.9618 | gen_002_circulant                |
| 25 | 0.9233 | gen_002_circulant                |
| 26 | 0.8878 | gen_002_circulant                |
| 27 | 0.9618 | gen_002_circulant                |
| 28 | 0.9274 | gen_002_circulant                |
| 29 | 0.8955 | gen_002_circulant                |
| 30 | 0.9618 | gen_002_circulant                |
| 31 | 0.8406 | gen_023_cubic_residues_selective |
| 32 | 0.9017 | gen_002_circulant                |
| 33 | 0.9618 | gen_002_circulant                |
| 34 | 0.9335 | gen_002_circulant                |
| 35 | 0.9068 | gen_002_circulant                |
| 36 | 0.9618 | gen_002_circulant                |
| 37 | 0.9136 | gen_023_cubic_residues_selective |
| 38 | 0.9112 | gen_002_circulant                |
| 39 | 0.9618 | gen_002_circulant                |
| 40 | 0.9378 | gen_002_circulant                |
| 41 | 0.9149 | gen_002_circulant                |
| 42 | 0.9618 | gen_002_circulant                |
| 43 | 0.8636 | gen_031_cubic_generalized        |
| 44 | 0.9181 | gen_002_circulant                |
| 45 | 0.9618 | gen_002_circulant                |
| 46 | 0.9409 | gen_002_circulant                |
| 47 | 0.9209 | gen_002_circulant                |
| 48 | 0.9618 | gen_002_circulant                |
| 49 | 0.9422 | gen_002_circulant                |
| 50 | 0.9233 | gen_002_circulant                |
| 51 | 0.9618 | gen_002_circulant                |
| 52 | 0.9433 | gen_002_circulant                |
| 53 | 0.9255 | gen_002_circulant                |
| 54 | 0.9618 | gen_002_circulant                |
| 55 | 0.9443 | gen_002_circulant                |
| 56 | 0.9274 | gen_002_circulant                |
| 57 | 0.9618 | gen_002_circulant                |
| 58 | 0.9452 | gen_002_circulant                |
| 59 | 0.9292 | gen_002_circulant                |
| 60 | 0.9618 | gen_002_circulant                |

## Summary stats

- Total evaluations: **48**
- Stage 1 passed: **41**
- Achieved best_c < 1.0: **36**
- Timestamp range: 2026-04-18T01:55:24.606052+00:00 → 2026-04-18T06:39:20.198604+00:00

## Failure analysis

| reason        | count | % of all per-N evals |
|---------------|-------|----------------------|
| d_max_too_low | 2007  | 77.0%                |
| not_k4_free   | 127   | 4.9%                 |