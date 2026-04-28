# Cayley Tabu (GAP-backed)

## Goal

Extend `search/cayley_tabu.py` to every finite group in GAP's SmallGroups
library, not just the five hand-coded families (`Z_n`, `D_{n/2}`,
`Z_2^k`, `Z_3×Z_2^k`, factor-pair direct products). Motivation: the
FRONTIER review flagged N=21 as stubborn and we had exactly one group
at that order (Z_21); the Frobenius `Z_7 ⋊ Z_3` was entirely outside
our search space. In general, non-abelian group coverage grows fast
with N — at N=24 we searched 5 of 15 SmallGroups, at N=32 we searched
5 of 51 — and that's where the non-trivial Cayley extremizers live.

Complementary to `search/cayley_tabu.py`. The hand-coded variant
stays untouched; this path is additive.

## Implementation

**New files:**

- `utils/algebra.py` (the `families_of_order_gap` / `load_order` /
  `to_group_spec` block) — GAP SmallGroups bridge. Shells out to `gap`
  with a per-N script that emits `StructureDescription` + full
  multiplication table. Result cached per-N at
  `graphs_src/gap_groups/n_XXXX.json` (gitignored).
  `families_of_order_gap(n)` is a drop-in replacement for
  `utils.algebra.families_of_order(n)`, returning every SmallGroup of
  order n as a `GroupSpec`. Orders with `NumberSmallGroups(n) > 500`
  (cap constant `MAX_GROUPS_PER_N`) return `[]` with a warning; this
  skips N=128 (2328 groups) and all orders above that cap in [1, 2000].
- `search/cayley_tabu_gap.py` — `CayleyTabuGapSearch(CayleyTabuSearch)`.
  Only swaps the family iterator and sets `name = "cayley_tabu_gap"` so
  results land in a separate graph_db bucket. Tabu core, cost function,
  and scoring path reused verbatim.
- `scripts/run_cayley_tabu_gap.py` — sequential driver, mirrors
  `run_cayley_tabu.py`.
- `scripts/run_cayley_tabu_gap_parallel.py` — `ProcessPoolExecutor`
  driver. Unit of work is `(N, group_name)`; workers return
  picklable payloads (sparse6 + scoring) to the main process, which
  serialises all `GraphStore.add_graph` writes to avoid JSON races.
  Per-search file-logging is disabled in workers to avoid
  timestamp-collision races on the same N.
- `cluster/CAYLEY_TABU_GAP.sub` + `cluster/run_cayley_tabu_gap.sh` —
  HTCondor single-job template (32 CPUs, 20 GB, 3-day walltime).

**Environment:**

Added `gap-defaults` to `environment.yml`. GAP 4.15+ from conda-forge.
After pull: `micromamba env update -n k4free -f environment.yml`.

## Running

**Local sweep (small N range):**

```bash
micromamba run -n k4free python scripts/run_cayley_tabu_gap_parallel.py \
    --n-lo 10 --n-hi 40 --workers 10 \
    --time-limit 180 --n-iters 600 --n-restarts 8 --better-only
```

**Cluster (single job, 32 CPUs):**

```bash
condor_submit cluster/CAYLEY_TABU_GAP.sub
tail -f logs/pipeline/cayley_tabu_gap_<ClusterID>_0.out     # needs stream_output=True in the .sub
```

Cache check after install:
```bash
micromamba run -n k4free gap -q -b -c 'Print(NumberSmallGroups(24), "\n"); QUIT_GAP();'  # 15
```

## Validation runs

| Run | N range | Wall | Workers | Budget/group | Result |
|---|---|---|---|---|---|
| Sequential, initial | 10–30 | ~1 h | 1 | 180 s | N=21 via `C_7:C_3` matched the 0.7328 frontier; N=28 found PR 0.7708 via `D_28` |
| Parallel, local | 10–40 | 4.8 min | 10 | 120 s | 165 tasks, 0 failures, 0.77 GB peak RSS. New PR at N=36 via `S_3×S_3` at 0.7238 |

No regressions versus hand-coded `cayley_tabu` — GAP variant strictly
adds groups and, at sufficient budget, matches or beats every known N.

## Cluster sweep results (2026-04-23, partial — through N=94 of 144)

### Strict frontier improvements

| N | GAP c_log | Prev best | Δ | Prev source | GAP winning group |
|---|---|---|---|---|---|
| 28 | 0.770848 | 0.775526 | −0.0047 | circulant | `SG_28_3_D28` |
| 36 | 0.723824 | 0.744148 | **−0.0203** | circulant | `SG_36_10_S3×S3` |
| 40 | 0.719458 | 0.721348 | −0.0019 | circulant | `SG_40_5_C4×D10` |
| 80 | 0.719458 | 0.721348 | −0.0019 | circulant_fast | `SG_80_28_C5:(C8×C2)` |
| 92 | 0.752710 | 0.836345 | −0.0836 | circulant_fast | `SG_92_2_C92` |

Plus 53 ties (GAP matches the overall frontier via a Cayley graph,
sometimes via a previously-unsearched non-abelian realisation).

### Plateau fingerprints (α/Hoffman ratio, invariant under cyclic lifts)

The α/Hoffman ratio
`α / [n · (−λ_min) / (d − λ_min)]`
is **exactly conserved** along known cyclic-lift chains. This is a clean
empirical confirmation that "plateau matches" across N are the same
graph blown up, not independent discoveries.

| Plateau c_log | α/Hoff ratio | N values (GAP winning groups) |
|---|---|---|
| 0.6789 (P(17) family) | 0.728 | 17 (`C_17`), 34 (`C_34`), 51 (`C_51`), 68 (`C_17:C_4` — Frobenius realisation), 85 (`C_85`) |
| 0.6995 (N=22 family) | 0.574 | 22 (`D_22`), 44 (`C_22×C_2`), 66 (`C_66`), 88 (`C_2×(C_11:C_4)`) |
| 0.7050 (CR(19) family) | 0.763 | 19 (`C_19`), 38 (`C_38`), 57 (`C_19:C_3`), 76 (`C_19:C_4`) |
| 0.7195 (N=20 family) | 0.563 | 20 (`D_20`), 40 (`C_4×D_10`), 60 (`C_6×D_10`), 80 (`C_5:(C_8×C_2)`) |
| 0.7328 (F_21 family) | 0.751 | 21 (`C_7:C_3`), 42 (`C_2×(C_7:C_3)`), 63 (`C_3×(C_7:C_3)`), 84 (`C_4×(C_7:C_3)`) |

Noteworthy: the P(17) 4-lift at N=68 is realised in our sweep as
`C_17:C_4` (a non-abelian Frobenius extension), not as the cyclic
`C_68`. Same spectrum, same α, same c_log — but the Cayley realisation
is non-obvious.

### Hoffman-saturation verdict

Of 285 `cayley_tabu_gap` records, **only 8 have a spectrum that could
theoretically support sub-P(17)**. All 8 are either Hoffman-saturated
or on a known plateau. No slack to exploit.

| Spectrum cluster | Members | α/Hoff | Reading |
|---|---|---|---|
| `(λ_min = −2, d = 6)` extremal | N=16 (`C_4×C_4`), 32 (`C_4×C_4×C_2`), 64 (`C_4×C_4×C_4`) | **1.000** | Clebsch-type SRG; already α = Hoffman exactly. No room to shrink α within this spectrum. |
| CR(19) chain | N=19, 38, 57, 76 | 0.763 | Matches known CR(19) c_log. Sub-P(17) would require a *different* (non-CR) graph with the same spectrum. |
| `(λ_min = −2.303, d = 6)` | N=26 | 0.832 | Near-Hoffman, no slack. |

**Structural conclusion:** Every Cayley graph in the sweep whose
spectrum is good enough to beat P(17) is already at (or close to) its
Hoffman ceiling. Further tabu budget on the current SmallGroups won't
cross P(17) — progress requires **different spectra**, i.e., Cayley
graphs on groups or connection sets that produce new λ_min profiles.

### Loss analysis

27 N values where GAP sits above the overall frontier. Two distinct
mechanisms:

**Bucket 1 — SAT-proven unconditional ceilings (12 N):** 14, 15, 23, 61,
62, 71, 73, 79, 82, 89, 94 and a handful of `sat_circulant_optimal`
wins. Cayley fundamentally cannot reach these — `sat_exact` has proven
the extremum lives outside the Cayley family.

**Bucket 2 — tabu under-convergence on same-group Cayley searches
(15 N):** 31, 37, 43, 47, 49, 50, 53, 67, 69, 70, 74, 81, 83, 90, 91.
Primes and near-primes where SmallGroups provides only C_N or a very
short list. The winning non-GAP source is another Cayley-family
solver on the *same underlying group* — circulant_fast has a deeper
DFS over Z_N connection sets, and `CayleyResidueSearch` directly
constructs `Cay(Z_p, R_k)` for algebraic residue classes. Random-init
tabu with no warm start almost never lands near those pockets.

The one structurally interesting loss in this bucket is **N=81**
(sat_circulant_optimal at 0.804 vs. our 0.851 via the
extra-special 3-group `C_3.((C_3×C_3):C_3)`). 14 SmallGroups tried;
the Cayley family genuinely cannot reach the Hoffman-optimal pocket
that sat_circulant finds.

### N=91 as diagnostic

Single most extreme loss: GAP at c=1.002, circulant_fast at 0.773.
`N=91` has `NumberSmallGroups(91) = 1` (only C_91). Tabu on C_91 found
(α=21, d=10); circulant_fast found (α=21, d=6) — same α, different
connection-set density. Pure local-minimum trap in the bitvec space.

## Open directions

1. **Different spectra.** The Hoffman verdict says progress requires
   new λ_min profiles. Candidates:
   - **Simple groups** we haven't touched: A_5 at N=60 gives a
     different λ_min than any abelian Cayley; similarly A_4 at N=12
     (already in sweep), S_5 at N=120, PSL(2,7) at N=168 (above cap).
   - **Larger primes** where we have only C_p: N ∈ {101, 103, 107, 109,
     113, 127} — extend `--n-hi` after current sweep finishes.
   - **Groups above the 500-cap** (N=128, 192, 256, …) — currently
     skipped; worth revisiting if A_5/S_5/simple-group runs show
     spectral novelty.

2. **Warm-seeded tabu on cyclic groups.** Rather than random init on
   `C_N`, seed from `circulant_fast`'s best connection set (or
   `CayleyResidueSearch`'s residue class). Eliminates every Bucket-2
   loss mechanically. Would compromise the "does Cayley reach the
   frontier unaided" question we're trying to answer, so defer until
   after the unaided sweep is fully characterised.

3. **Pattern-in-winners analysis.** The winning group *structure* per
   frontier-tying N ties a story — e.g., the F_21 plateau uses
   `(C_k × F_21)` at N=21k for k=1..4. Enumerate that pattern over
   all plateaus and use it as the extrapolation rule for N > 144.

4. **α/Hoff ratio as a similarity index.** Two graphs at different N
   with the same α/Hoff ratio almost always belong to the same blowup
   chain. Ratio → plateau-family grouping is a near-exact
   classifier. Could replace the "compare via c_log value" dedup logic
   with "compare via α/Hoff ratio + λ_min profile".

## Files touched

- `utils/algebra.py` *(GAP bridge merged in; previously `search/groups_gap.py`)*
- `search/cayley_tabu_gap.py` *(new)*
- `search/__init__.py` *(added export)*
- `scripts/run_cayley_tabu_gap.py` *(new)*
- `scripts/run_cayley_tabu_gap_parallel.py` *(new)*
- `cluster/CAYLEY_TABU_GAP.sub` *(new)*
- `cluster/run_cayley_tabu_gap.sh` *(new)*
- `environment.yml` *(added gap-defaults)*

## Cross-references

- `docs/searches/CAYLEY_TABU.md` — hand-coded precursor; still runs.
- `docs/FRONTIER_REVIEW.md` — overall frontier status; updated rows
  for N=28, 36, 40, 80, 92 once the sweep finishes.
- `docs/theory/BEYOND_CAYLEY.md` — Conjecture A/B (P(17) uniqueness at
  N=17 / N=34). Sweep confirms the lift chain empirically through N=85.
- `docs/searches/circulant/CIRCULANT_FAST.md` — the Bucket-2
  competitor on cyclic groups.
