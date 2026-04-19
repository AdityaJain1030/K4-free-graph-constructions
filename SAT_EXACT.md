# SAT_EXACT — pipeline overview

`search/sat_exact.py` started as a single CP-SAT model that asks "is there a
K4-free graph on `n` vertices with `α(G) ≤ α_cap` and `d_max(G) ≤ d_cap`?" It
has since grown into a pruned Pareto scan with warm-start seeding and a
certified-optimal verifier. This document is a walkthrough of the pipeline as
it exists now, and what each piece is for.

For the "why each optimization" ablation numbers, see `SAT_OPTIMIZATION.md`
and `logs/sat_exact_ablation.json`.

---

## 1. What the core model looks like

For a single `(α_cap, d_cap)` box, `_build_model` produces a CP-SAT
satisfaction problem:

| constraint   | encoding                                                                      | purpose                    |
| ------------ | ----------------------------------------------------------------------------- | -------------------------- |
| edge vars    | bool `x[i,j]` for every `i < j`                                               | the graph                  |
| K4-free      | for every 4-set `{a,b,c,d}`: `¬x_ab ∨ ¬x_ac ∨ ¬x_ad ∨ ¬x_bc ∨ ¬x_bd ∨ ¬x_cd` | no K4                      |
| max-degree   | `Σ_u x[v,u] ≤ d_cap` per vertex                                               | `d_max(G) ≤ d_cap`         |
| min-degree   | `Σ_u x[v,u] ≥ d_min` per vertex (from Ramsey)                                 | tightens the model         |
| independence | for every `(α_cap+1)`-subset: `∨ x_ij`                                        | `α(G) ≤ α_cap`             |

CP-SAT then returns:

- **FEASIBLE** + a witness graph, or
- **INFEASIBLE** (a real proof, inside the per-box time limit), or
- **TIMEOUT** (`UNKNOWN` — we didn't finish proving either way).

The K4 and independence constraints are written as pure disjunctions rather
than as `sum ≤ k` cardinalities. Unit propagation fires the instant all but
one of the literals in the clause are fixed — empirically this is faster than
the linear reformulation CP-SAT would pick otherwise.

---

## 2. The scan around the model

A **Pareto scan**: for each `α`, find the smallest feasible `d_max`. The
witness at that smallest d has `α(G) = α` and `d_max(G) = d` exactly, so its
`c_log = α·d/(n·ln d)` is the minimum c_log inside that α-track.

```
for α in 1..n-1:
    for d in d_lo(α) .. n-1:
        solve box (α, d)
            FEASIBLE   → record witness, break out of d-loop
            INFEASIBLE → next d
            TIMEOUT    → next d (leaves an open cell in the proof)
```

Best witness across all α-tracks is `c*`, the optimum c_log for this `n`.

---

## 3. The five accelerators layered on top

Each is an independent flag, so `scripts/ablate_sat_exact.py` can measure
exactly how much each one buys you.

### (a) Ramsey pruning (`ramsey_prune=True`)

Every K4-free graph with `α(G) ≤ α` has

```
n − R(4, α+1)   ≤   deg(v)   ≤   R(3, α+1) − 1
```

for every vertex. Boxes where `d_cap` violates this — on either side — are
skipped at zero SAT cost. When the flag is on, the derived `d_min ≥ 1` is
also added to the CP-SAT model as a min-degree constraint, which tightens the
LP relaxation even on boxes that aren't skipped.

### (b) Ramsey floor (`scan_from_ramsey_floor=True`)

Start the d-loop at `d_lo(α) = max(1, n − R(4, α+1))` instead of 1. Skips the
cheap-to-state but expensive-to-prove INFEASIBLE cells at the bottom of the
d-axis. Only does anything when `ramsey_prune` is on.

### (c) Edge-lex symmetry break (`symmetry_mode="edge_lex"`)

Adds

```
Σ_{k ≤ 3} 2^k · x[k, j]   ≥   Σ_{k ≤ 3} 2^k · x[k, j+1]
```

for column pairs `j, j+1`. The exponential weights make the comparison
behave numerically like a lex comparison on the first 4 rows: row 0
dominates, ties break into row 1, and so on. Row `k` is included in a pair
only when `k < j` — the swap `σ = (j, j+1)` only touches row `k` at columns
`j, j+1` when `k < j`, so including it later would over-constrain.

Kills most of the `n!` labelling symmetry at the cost of `n − 2` linear
inequalities. Alternatives:

- `symmetry_mode="anchor"`: single constraint `deg(0) ≥ deg(v)` for every
  `v > 0`. Cheap, breaks most labelling symmetry with one anchor.
- `symmetry_mode="chain"`: `deg(0) ≥ deg(1) ≥ … ≥ deg(n−1)`. Stronger but
  pays `n−1` cardinality inequalities; not always a net win at small N.
- `symmetry_mode="none"`: baseline for the ablation.

### (d) c_log-bound pruning (`c_log_prune=True`)

The central accelerator. For a Pareto-scan witness at the smallest feasible
d, `c_log(G) = α·d/(n·ln d)` exactly. Define

```
c_bound(α, d) = α·d / (n · ln d)            (for d ≥ 2; +∞ for d ≤ 1)
```

Two prune forms:

- **Box-level.** Before solving box `(α, d)`, compute `c_bound(α, d)`. If
  `c_bound ≥ c*`, skip the box — any witness from it has `c_log ≥ c*` and
  cannot improve c*. Emits a `SKIP_C_BOUND` event. `c_bound` is monotone ↑ in
  d for `d ≥ 3`, so once it crosses `c*` the rest of that α-track is dead
  and we break.

- **Track-level.** Define `c_min(α) = min_d c_bound(α, d)` subject to
  `d ≥ d_lo(α)`. If `c_min(α) ≥ c*`, skip the whole α-track. Emits a
  `SKIP_ALPHA` event.

On every n from 10 upwards this is the prune that collapses the high-α
tracks to zero SAT calls.

### (e) Circulant seeding (`seed_from_catalog=True`, `seed_from_circulant_search=True`)

Before the scan starts, seed `c*` and emit the witness as the first result.
Two sources tried in order:

1. `seed_from_catalog`: read the best K4-free circulant for this `n` from
   `graphs/circulant.json`. Verified K4-free before use.
2. `seed_from_circulant_search`: if the catalog has no entry for this `n`,
   run `search.CirculantSearch` live — enumerate K4-free `C(n, S)` for
   `S ⊆ {1..n//2}` via a bitmask K4 check. `O(2^(n/2))` subsets, seconds up
   to n≈40.

Both are valid K4-free witnesses, so their c_log is achievable. Emitting the
witness as a result is what lets us:

- Seed `c_log_prune` — the very first α-track can skip most of its boxes
  before any SAT call.
- Avoid the SAT re-solve of the seed's own box (which at n ≥ 19 CP-SAT can
  still take minutes to reproduce, even though we already have the answer).

The seed witness also emits a synthetic `ATTEMPT … status=FEASIBLE_SEED`
event so the optimality verifier can treat that box as covered without
re-parsing the witness graph.

---

## 4. The hard-box path

At the feasibility boundary, some boxes can't be solved by CP-SAT in the
60 s per-box budget used during a scan. Closing those cells is what moves
the result from "best-found" to "certified optimal".

Three flags take CP-SAT off its easy-box presets:

- `hard_box_params=True` →
  - `linearization_level = 2` (more LP cuts seen)
  - `cp_model_probing_level = 3` (deeper probing at presolve)
  - `symmetry_level = 4` (max built-in symmetry inference on top of our
    manual edge_lex break)
- `solver_log=True` → `log_search_progress` so the `#Model` / `#Bound` lines
  surface for monitoring.
- `random_seed=N` → portfolio diversification if we want to launch several
  parallel seeds.

`scripts/prove_box.py` is the driver. It takes `(n, α, d_max)`, runs one
SAT solve with extended timeout (default 1800 s), and appends the verdict
to `logs/optimality_proofs.json`. The scan pruning flags are all turned
off in single-box mode — there's no scan to prune.

Typical budgets at the boundary (from measured runs):

- N=20 α=4 d=6 INFEASIBLE: **1350.76 s** on 4 workers with `hard_box_params`.
- Smaller N boundary boxes (N=18 α=4 d=5, N=19 α=4 d=5): closed inside the
  60 s per-box scan budget once `hard_box_params` is off but edge_lex + the
  min-degree constraint are on.

---

## 5. Parallel-α mode (server-only, `parallel_alpha=True`)

Dispatches each α-track to its own worker process via
`ProcessPoolExecutor`. Each worker holds its own CP-SAT model, so memory
scales linearly in the number of tracks — at `n ≥ 20`, one model is ~400 MB
RSS, and running `n` of them concurrently pushes you into the 200 GB box.
Only intended for the 32-core server; the local laptop runs sequentially.

The worker function `_scan_one_alpha_worker` is a module-level function so
`ProcessPoolExecutor` can pickle it.

---

## 6. The optimality verifier

Being able to find a witness is not the same as proving it's optimal. The
verifier closes that loop.

### Script: `scripts/verify_optimality.py`

Inputs:

- `--n`: vertex count.
- `--c-star`: the current best c_log for this `n`.
- `--proofs`: `logs/optimality_proofs.json` (hard-box results).
- `--scan-logs`: `logs/search/` (normal scan logs).

It aggregates every `ATTEMPT` line across every scan log for that n
(with a rank — `INFEASIBLE` / `FEASIBLE` / `FEASIBLE_SEED` win over
`TIMEOUT`), merges in the hard-box verdicts, then enumerates every `(α, d)`
box and classifies:

| verdict             | meaning                                             |
| ------------------- | --------------------------------------------------- |
| `RAMSEY_INFEASIBLE` | proved infeasible by the Ramsey degree bounds      |
| pruned              | `c_bound(α, d) ≥ c*` — cannot improve                |
| `PROVED_INFEASIBLE` | SAT proof                                            |
| `PROVED_FEASIBLE`   | witness known (scan or hard-box)                     |
| `FEASIBLE_SEED`     | witness from the circulant seed                      |
| `OPEN`              | c_bound < c*, not yet resolved — **needs a proof**  |

**c\* is certified optimal iff every box with `c_bound < c*` is either
`PROVED_INFEASIBLE` or covered by a `FEASIBLE`/`FEASIBLE_SEED` witness.**
Exit code = number of open boxes (0 means proved).

### Script: `scripts/proof_report.py`

Runs the verifier across a range of n and prints a one-line status per n.
Exit code = number of unproved n values.

Current status (from the last run):

```
  N          c*  status    open boxes
----------------------------------------------------------------------
 10    0.865617  PROVED    ✓
 11    0.786925  PROVED    ✓
 12    0.776669  PROVED    ✓
 13    0.772769  PROVED    ✓
 14    0.717571  PROVED    ✓
 15    0.719458  PROVED    ✓
 16    0.721348  PROVED    ✓
 17    0.678915  PROVED    ✓
 18    0.744148  PROVED    ✓
 19    0.704982  PROVED    ✓
 20    0.719458  PROVED    ✓
 21    0.732797  OPEN      α=4 d=7
 22    0.699489  OPEN      α=4 d=7
 23    0.752710  OPEN      α=4 d=7, α=4 d=8, α=4 d=9, α=5 d=5, α=5 d=6
```

---

## 7. End-to-end flow at `n = 20` (worked example)

1. Seed `c*` from `graphs/circulant.json`: the 8-regular circulant on 20
   vertices is K4-free with α = 4, giving `c_log = 4·8/(20·ln 8) = 0.7694`.
   Emit it as the first result with metadata `source=circulant_seed`.
2. α-track loop:
   - α = 1, 2, 3: Ramsey-infeasible → skip.
   - α = 4: scan d from the Ramsey floor upward.
     - d = 2, 3, 4, 5: SAT proves INFEASIBLE (sub-second each).
     - d = 6: TIMEOUT in the 60 s scan budget. Closed *later* by
       `prove_box.py` with `hard_box_params=True`, timeout 1800 s →
       **INFEASIBLE in 1350.76 s**.
     - d = 7: SAT finds a K4-free graph with `α = 4, d_max = 7`, degree
       sequence `[6, 6, 7, 7, …, 7]`. `c_log = 0.7195`. Update `c*`.
   - α = 5: `c_min(5) = c_bound(5, d_lo(5)) = 0.6826 < c*` — track not
     pruneable. Scan: d = 3 INFEASIBLE; d = 2 and d = 4 box-pruned
     (c_bound ≥ c*); break.
   - α ≥ 6: `c_min(α) > c*` for every α — whole tracks pruned.
3. Final: `c* = 0.7195`, certified optimal.

---

## 8. File map

```
search/sat_exact.py            — the pipeline above
search/base.py                 — base class with logging / verification
search/circulant.py            — live circulant search for seed fallback
scripts/ablate_sat_exact.py    — ablation harness (each accelerator's effect)
scripts/prove_box.py           — hard-box driver with aggressive CP-SAT params
scripts/verify_optimality.py   — per-n certified-optimal check
scripts/proof_report.py        — range-wide summary
logs/search/                   — per-n scan logs
logs/sat_exact_ablation.json   — raw ablation numbers
logs/optimality_proofs.json    — hard-box verdicts
graphs/circulant.json          — committed circulant catalog
SAT_OPTIMIZATION.md            — deeper derivation of c_log_prune + seeding
```
