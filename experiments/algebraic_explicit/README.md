# `experiments/algebraic_explicit/` — closed-form K₄-free constructions

## Compute

- **Environment:** k4free conda env (local).
- **Typical runtime:** graph construction is closed-form and instant
  (q ≤ ~50). The cost is α: cheap for `prime_circulants` (vertex-transitive,
  CP-SAT seconds-to-minutes up to p ≈ 200), heavier for `polarity` at large q
  (non-vertex-transitive, CP-SAT can hit the 300 s timeout per N), and
  expensive for `brown` (n = q³, α at n = 125 is minutes).
- **Memory:** modest; dominated by the dense adjacency matrix used for
  spectra (n × n doubles).
- **Parallelism:** single-threaded per N. CP-SAT inside `alpha_cpsat`
  uses one worker.

---

## Background

These are the **closed-form** algebraic families: given a set of parameters, the graph is defined by an explicit construction.
This is distinct from the algebraic *search* methods elsewhere in the repo
(`cayley_tabu`, `circulant_fast`, …) which search *over* algebraically
structured spaces. Theory references for each family live under
`docs/searches/algebraic/` (`POLARITY.md`, `NORM_GRAPH.md`, `BROWN.md`,
`MATTHEUS_VERSTRAETE.md`) and `docs/searches/CAYLEY.md` for the
power-residue Cayley graphs.

---

## Question

How well do the classical closed-form K₄-free constructions compete against
the P(17) `c_log ≈ 0.679` benchmark, and which (if any) push below it at
some N?

---

## Approach

For each construction the parameter q ranges over its eligible set (prime,
prime ≥ 5, prime power, …). The driver builds the graph from its formula,
verifies K₄-freeness, computes α via `alpha_cpsat`, and ingests the graph
into `graph_db` under the construction's source tag. The only "knob" is the
parameter range; there is no optimisation loop.

| Construction | Underlying object | N | Parameter range |
|---|---|---|---|
| Erdős–Rényi polarity ER(q) | PG(2, q), orthogonal polarity | q²+q+1 | any prime power q ∈ {2, 3, 4, 5, 7, 8, 9, 11, 13, 16, 17, 19, 23, …} via `utils.algebra.field` |
| Brown unit-sphere | F_q³ unit sphere | q³ | odd prime q ≥ 5 |
| Norm-kernel Cayley | F_{q²}* / F_q* | q²−1 | prime q |
| Power-residue Cayley | Cay(Z_p, k-th powers) | p | prime p, k ∈ divisors(p−1) |
| Mattheus–Verstraete H_q* | R(4,k) lower-bound family | q²(q²−q+1) | prime q ∈ {2, 3, 5, 7} |
| Folded (d+1)-cube | Cay(Z_2^d, {e_1, …, e_d, (1,…,1)}) | 2^d | d ≥ 3 (d=4 is Clebsch) |
| Hamming H(d, q) | Cay(Z_q^d, {±e_i}) | q^d | d ≥ 2, q ∈ {2, 3} (K₄-free) |
| Shrikhande | Cay(Z_4×Z_4, {±(1,0), ±(0,1), ±(1,1)}) | 16 | fixed |
| A_5 + double-transpositions | Cay(A_5, all 15 dt's) | 60 | fixed; **not K₄-free** |
| PSL(2, q) involutions | Cay(PSL(2, q), trace-0 involutions) | q(q²−1)/gcd(2, q−1) | prime power q; **K₄-free only at q = 2** |

**Limitation.** The current `prime_circulants` sweep only tries
k ∈ {2, 3, 6}. For p where p−1 has other divisors (e.g. k = 4, 5, 8, 10),
the corresponding power-residue Cayley graphs are not generated.

---

## Files

| File | Purpose |
|---|---|
| `run.py` | Unified driver. `--construction {polarity, brown, norm_graph, prime_circulants, mattheus_verstraete, folded_cube, hamming, shrikhande, a5_double_transpositions, psl_involutions}`. Standard knobs: `--ns`, `--min-n`, `--max-n`, `--top-k`, `--seed`, `--no-save`. Parameterized constructions add `--d` (Hamming, folded_cube) and `--q` (Hamming, polarity, PSL). Auto-generates eligible N from each formula. |

```bash
# All eligible N up to a cap
micromamba run -n k4free python experiments/algebraic_explicit/run.py \
    --construction polarity --max-n 200
micromamba run -n k4free python experiments/algebraic_explicit/run.py \
    --construction prime_circulants --max-n 500

# Specific N values
micromamba run -n k4free python experiments/algebraic_explicit/run.py \
    --construction brown --ns 125 343

# Parameterized — pick a single (d, q) instead of the auto-sweep
micromamba run -n k4free python experiments/algebraic_explicit/run.py \
    --construction folded_cube --d 4              # Clebsch
micromamba run -n k4free python experiments/algebraic_explicit/run.py \
    --construction hamming --d 3 --q 3            # H(3,3)
micromamba run -n k4free python experiments/algebraic_explicit/run.py \
    --construction psl_involutions --q 7          # PSL(2,7)

# Dry run (no write to graph_db)
micromamba run -n k4free python experiments/algebraic_explicit/run.py \
    --construction polarity --max-n 200 --no-save
```

Results land in `graphs/{polarity, brown, norm_graph, cayley, mattheus_verstraete, special_cayley}.json`
under each construction's source tag. (Power-residue Cayley shares
`graphs/cayley.json` with the residue-class search; folded cubes,
Hamming, Shrikhande, A_5, and PSL all share `graphs/special_cayley.json`
under `source="special_cayley"` and are distinguished by the per-graph
metadata `family` field.)

---

## Results

**Status:** open — `prime_circulants` k-sweep is incomplete (still
{2, 3, 6} only); prime-power polarity past q = 32 needs the
irreducibles table extended; `folded_cube` past d = 7 and `hamming`
past d = 4 still untouched.

**Best per family** (c_log, lower = better, P(17) = 0.679):

| Family | Best c_log | At |
|---|---|---|
| Power-residue Cayley | **0.6789** | P(17) |
| Shrikhande | 0.8372 | n=16 |
| Polarity | 0.9539 | ER(8), n=73 |
| Hamming | 0.9618 | H(2,3), n=9 |
| Norm-kernel Cayley | 0.9618 | q=2, n=3 (triangle; only K₄-free q) |
| Folded cube | 0.9708 | Clebsch, n=16, d=4 |
| PSL involutions | 1.3654 | PSL(2,2), n=6 |
| Mattheus–Verstraete | 1.3953 | n=12 |
| Brown | 1.4113 | n=125 |
| A_5 + double-transpositions | — | not K₄-free for any q |

### Power-residue Cayley (`prime_circulants` / `cayley`)

The strongest of the algebraic families. P(17) (k=2, p=17) is the overall
repo record. All 19 graphs ingested under the legacy `cayley` source
(the same family — `prime_circulants` is its renaming):

| n | k | c_log | α | d_max |
|---:|---:|---:|---:|---:|
| 17 | 2 (Paley) | **0.678915** | 3 | 8 |
| 19 | 3 (cubic) | 0.704982 | 4 | 6 |
| 13 | 2 (Paley) | 0.772769 | 3 | 6 |
| 37 | 6 (sextic) | 0.814540 | 9 | 6 |
| 31 | 3 (cubic) | 0.840570 | 6 | 10 |
| 67 | 3 (cubic) | 0.849832 | 8 | 22 |
| 43 | 3 (cubic) | 0.863592 | 7 | 14 |
| 61 | 3 (cubic) | 0.875562 | 8 | 20 |
| 13 | 3 (cubic) | 0.887812 | 4 | 4 |
| 79 | 3 (cubic) | 0.909128 | 9 | 26 |
| 37 | 3 (cubic) | 0.913624 | 7 | 12 |
| 127 | 3 (cubic) | 0.973279 | 11 | 42 |
| 61 | 6 (sextic) | 0.996741 | 14 | 10 |
| 73 | 6 (sextic) | 1.058445 | 16 | 12 |
| 97 | 6 (sextic) | 1.130359 | 19 | 16 |
| 109 | 6 (sextic) | 1.142674 | 20 | 18 |
| 5 | 2 (Paley) | 1.154156 | 2 | 2 |
| 7 | 3 (cubic) | 1.236596 | 3 | 2 |
| 13 | 6 (sextic) | 1.331718 | 6 | 2 |

### Erdős–Rényi polarity (`polarity`)

C₄-free (hence K₄-free) by construction. Competitive at small q, but c_log
plateaus around 1.0–1.1 and never approaches the Paley benchmark. All 13
ingested instances (q = 4 added on the prime-power-merged sweep):

| n | q | c_log | α | d_max |
|---:|---:|---:|---:|---:|
| 73 | 8 | 0.953881 | 17 | 9 |
| 57 | 7 | 1.012418 | 15 | 8 |
| 21 | 4 | 1.035558 | 7 | 5 |
| 91 | 9 | 1.049943 | 22 | 10 |
| 133 | 11 | 1.052974 | 29 | 12 |
| 273 | 16 | 1.076969 | 49 | 17 |
| 31 | 5 | 1.080214 | 10 | 6 |
| 381 | 19 | 1.086410 | 62 | 20 |
| 183 | 13 | 1.101569 | 38 | 14 |
| 13 | 3 | 1.109765 | 5 | 4 |
| 307 | 17 | 1.115689 | 55 | 18 |
| 553 | 23 | 1.147108 | 84 | 24 |
| 7 | 2 | 1.170308 | 3 | 3 |

All produced by `run.py --construction polarity --max-n …`. The driver
auto-iterates eligible q (prime + tabled prime-power) via
`utils.algebra.prime_power`.

### Mattheus–Verstraete (`mattheus_verstraete`)

Designed to prove R(4,k) lower bounds, not to minimise c_log. The
construction has random pencil choices, so multiple trials per q land in
the DB. All 6 instances:

| n | q | trial | c_log | α | d_max |
|---:|---:|---:|---:|---:|---:|
| 12 | 2 | 1 | 1.395277 | 5 | 6 |
| 12 | 2 | 0 | 1.498870 | 5 | 7 |
| 12 | 2 | 2 | 1.498870 | 5 | 7 |
| 63 | 3 | 0 | 1.920552 | 17 | 22 |
| 63 | 3 | 2 | 2.033526 | 18 | 22 |
| 63 | 3 | 1 | 2.219053 | 18 | 25 |

Not competitive — c_log grows with q. q ∈ {5, 7} were not run
(eligible N = 525, 2107).

### Brown unit-sphere (`brown`)

One instance in the DB. Large N and high degree make α expensive (n = q³),
so larger q has not been attempted.

| n | q | c_log | α | d_max |
|---:|---:|---:|---:|---:|
| 125 | 5 | 1.411268 | 20 | 30 |

Eligible q ∈ {7, 11, 13, …} would give N ∈ {343, 1331, 2197, …}.

### Norm-kernel Cayley (`norm_graph`)

`Cay(Z_{q²−1}, K)` where K is the image of the norm-1 subgroup of F_{q²}*
in Z_{q²−1}. Eligible N = q²−1 for prime q; N ∈ {3, 8, 24, 48, 120, 168,
…}. **Family is K₄-free only at q = 2.** For q ≥ 3 the connection set
is dense enough that K₄'s appear:

| n | q | c_log (apparent) | α | d_max | K₄-free |
|---:|---:|---:|---:|---:|:---:|
| 3 | 2 | 0.961797 | 1 | 2 | ✓ |
| 8 | 3 | 0.682679 | 2 | 3 | · |
| 24 | 5 | 0.517779 | 4 | 5 | · |
| 48 | 7 | 0.449661 | 6 | 7 | · |
| 120 | 11 | 0.382280 | 10 | 11 | · |
| 168 | 13 | 0.362023 | 12 | 13 | · |

The non-K₄-free rows look frontier-breaking on c_log alone (0.36–0.68
vs P(17) at 0.679) — but that's the whole problem, the construction
isn't K₄-free for q ≥ 3, so those c_log values aren't valid frontier
candidates. Only n = 3 (the triangle) is genuinely K₄-free, and it's
trivial. The family is closed.

### Folded (d+1)-cube (`folded_cube`)

`Cay(Z_2^d, {e_1, …, e_d, (1,…,1)})`. K₄-free for all d ≥ 3 (no three
connection elements sum to 0 in Z_2^d). Bipartite for odd d, non-bipartite
for even d. d = 4 reproduces the Clebsch graph.

| n | d | c_log | α | d_max | bipartite |
|---:|---:|---:|---:|---:|:---:|
| 16 | 4 | **0.970836** | 5 | 5 | · |
| 64 | 6 | 1.236568 | 22 | 7 | · |
| 8 | 3 | 1.442695 | 4 | 4 | ✓ (= K_{4,4}) |
| 32 | 5 | 1.674332 | 16 | 6 | ✓ |
| 128 | 7 | 1.923593 | 64 | 8 | ✓ |

Bipartite cases have α = N/2 by construction and are useless for the
objective. Among non-bipartite cases (even d), Clebsch (d=4) is by far
the strongest hit; the family rapidly degrades as d grows.

### Hamming H(d, q) (`hamming`)

`Cay(Z_q^d, {±e_i})`. K₄-free precisely when q ≤ 3 (each maximal clique
sits along a single axis, so size = q). Default sweep covers q ∈ {2, 3}
and d ∈ [2, 6]. Cases with q ≥ 4 skip with "not K₄-free".

| n | d | q | c_log | α | d_max | notes |
|---:|---:|---:|---:|---:|---:|---|
| 9 | 2 | 3 | **0.961797** | 3 | 4 | rook K_3 □ K_3 |
| 27 | 3 | 3 | 1.116221 | 9 | 6 | |
| 81 | 4 | 3 | 1.282396 | 27 | 8 | |
| 8 | 3 | 2 | 1.365359 | 4 | 3 | 3-cube |
| 4 | 2 | 2 | 1.442695 | 2 | 2 | C_4 |
| 16 | 4 | 2 | 1.442695 | 8 | 4 | 4-cube |
| 32 | 5 | 2 | 1.553337 | 16 | 5 | 5-cube |
| 64 | 6 | 2 | 1.674332 | 32 | 6 | 6-cube |

H(d, 2) is just the d-cube — bipartite, α = 2^(d-1). H(d, 3) is the more
interesting branch; H(2,3) (the K_3 □ K_3 rook) is the best Hamming hit.

### Shrikhande (`special_cayley`, family `SRG`)

`Cay(Z_4 × Z_4, {±(1,0), ±(0,1), ±(1,1)})`. The cospectral mate of
the 4×4 rook graph (same parameters srg(16, 6, 2, 2), non-isomorphic).

| n | c_log | α | d_max |
|---:|---:|---:|---:|
| 16 | **0.837166** | 4 | 6 |

### Cay(A_5, double-transpositions) (`a5_double_transpositions`)

60 vertices, 15-regular. Skipped by the search — **not K₄-free**
(15-regular at α = 60/4 = 15 is too dense for K₄-freeness; concrete K₄
witnesses come from the cosets of a Klein-four subgroup of A_5).
Same outcome as `build_special_cayley.py`'s historical run.

### PSL(2, q) involutions (`psl_involutions`)

`Cay(PSL(2, q), trace-0 involutions)`. The connection set is the unique
conjugacy class of involutions in PSL(2, q) for q odd; for q even it is
the SL(2, q) elements with trace 0 (excluding identity). Only the
smallest case is K₄-free:

| n | q | c_log | α | d_max | notes |
|---:|---:|---:|---:|---:|---|
| 6 | 2 | 1.365359 | 3 | 3 | PSL(2,2) ≅ S_3 |
| 12 | 3 | — | — | — | skipped (K₄ present) |
| 60 | 4 (≅5) | — | — | — | skipped (K₄ present) |
| 168 | 7 | — | — | — | skipped (K₄ present) |
| 360 | 9 | — | — | — | skipped (K₄ present) |
| 504 | 8 | — | — | — | skipped (K₄ present) |
| 660 | 11 | — | — | — | skipped (K₄ present) |
| 1092 | 13 | — | — | — | skipped (K₄ present) |

The family is exhausted from a K₄-free standpoint at the smallest
non-trivial q. Larger q is verifiably *not* K₄-free, so additional q
won't help.

---

## Resolved

- [x] ~~**`polarity`: prime-power q.**~~ Folded into `run.py` via
      `utils.algebra.field`; the auto-iteration covers q ∈ {2, 3, 4, 5, 7,
      8, 9, 11, 13, 16, 17, 19, 23} in one pass. Old separate driver
      `run_polarity_extended.py` deleted. The 13th polarity instance
      (q=4, n=21) was added in the merged sweep.
- [x] ~~**Cross-construction frontier comparison.**~~ The "Best per
      family" table under Status now lists the c_log floor of every
      eligible family side by side; rank order is power-residue Cayley
      (0.679) ≪ Shrikhande (0.837) < polarity ER(8) (0.954) < Hamming
      H(2,3) (0.962) < Clebsch (0.971) < the rest.
- [x] ~~**PSL(2, q) Cayley as a missing family.**~~ Now in
      `search/algebraic_explicit/psl_involutions.py`. Result: only
      PSL(2,2) at n=6 is K₄-free; q ∈ {3, 4, 5, 7, 8, 9, 11, 13} all
      contain K₄. Family is closed from a K₄-free standpoint *for this
      connection set*.
- [x] ~~**`norm_graph`: run the driver.**~~ Swept q ∈ {2, 3, 5, 7, 11, 13}.
      Only q = 2 (the triangle, n = 3) is K₄-free; q ≥ 3 all contain K₄.
      Apparent c_log values (e.g. 0.36 at n = 168) are spurious — they
      reflect the dense norm-kernel connection set, which loses
      K₄-freeness once q ≥ 3. Family closed.

## Open questions

- [ ] **`prime_circulants`: extend k-sweep.** Try every k ∈ divisors(p−1)
      rather than just {2, 3, 6}. The current data already disproves the
      "smallest k is best" intuition (p = 37: k=6 beats k=3, c_log
      0.815 vs 0.913), so other primes likely have similar surprises.
- [ ] **`polarity`: extend the prime-power irreducibles table.**
      `utils.algebra.field` currently tables q ∈ {4, 8, 9, 16, 25, 27, 32}.
      Adding 49, 64, 81, 121, 125 covers q = 7², 2⁶, 3⁴, 11², 5³. The q²
      cases are the interesting cross-check vs prime q at the same N
      (e.g. 49 vs prime 7 — same q²+q+1 = N? No, different N; but the
      "non-prime q at sub-N" question stands).
- [ ] **`folded_cube`: explore d ≥ 8.** d=8 (n=256, 9-regular) is
      non-bipartite and might give a useful c_log; α at that scale will
      need an α timeout. Bipartite odd-d cases can be skipped.
- [ ] **`hamming`: q=3 frontier extension.** H(d, 3) at d ∈ {5, 6, …}
      gives larger N at fixed q; α scales as 3^(d-1) so it stays cheap.
- [ ] **`a5_double_transpositions` / `psl_involutions`: alternate
      connection sets.** Both groups admit other natural conjugacy classes
      (3-cycles in A_5; non-involution conjugacy classes in PSL). The
      involution Cayley is closed; alternate connection sets aren't.

---

## Theorems that would be nice to prove

- ~~**Conjecture:** for every prime p, the minimum c_log over the
  power-residue Cayley graphs `Cay(Z_p, R_k)`, k ∈ divisors(p−1), is
  achieved at the smallest k that gives a K₄-free graph.~~
  **Disproved by the existing data:** at p = 37 the smallest K₄-free k
  is 3 (cubic), giving c_log = 0.913, but k = 6 (sextic) gives 0.815.
  A weaker form may still hold (e.g. "the optimal k is bounded by some
  function of p"), but the simple "smallest works" claim is false.

- **Conjecture:** no closed-form algebraic family in this folder beats
  P(17) for any N > 17.
  *Why it matters:* would explain the 30-year stagnation around the Paley
  bound from the construction side and redirect effort toward
  search-based or non-algebraic families.
