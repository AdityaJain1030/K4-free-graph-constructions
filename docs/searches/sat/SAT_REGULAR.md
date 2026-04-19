# SAT_REGULAR — degree-pinned feasibility scan

`search/sat_regular.py` is the simpler, faster cousin of `sat_exact`.
Instead of scanning `(α, d_max)` across the whole Pareto frontier, it
*pins* each vertex's degree to `{D, D+1}` and walks `D` upward from
the Ramsey floor, solving a pure feasibility model at each step. The
first feasible `D` gives the min-edge K4-free witness for that `(n, α)`.

Ports the original reference `regular_sat` solver logic into the
`Search` framework. It is *not* a reimplementation of `sat_exact` — it assumes
the optimum is near-regular. That assumption is justified by
Hajnal's theorem (see `SAT.md` Results 2–3: α-critical ⇒ near-regular,
min `c` ⇔ min `|E|`), but it is *assumed*, not enforced. If the
assumption fails for some `(n, α)` you care about, this solver will
return INFEASIBLE where `sat_exact` would find a witness.

---

## When to reach for it

- You want the min-edge K4-free graph at a fixed `(n, α)` and trust
  the Hajnal reduction.
- You're porting a cluster run and want a smaller CP-SAT model than
  `sat_exact` produces (no `α`-scan, degrees pinned rather than
  bounded, feasibility only, no objective).
- You want a sanity reference to cross-check `sat_exact` output at
  small `n`.

## When *not* to reach for it

- You want certified optimality across the full Pareto frontier — use
  `sat_exact` + `prove_box.py` + `verify_optimality.py`.
- You want to scan over multiple `α` — this solver takes a single
  `alpha` kwarg by design. Wrap it in a script loop if you need to.

---

## The model at fixed D

| constraint     | encoding                                                                      | purpose                    |
| -------------- | ----------------------------------------------------------------------------- | -------------------------- |
| edge vars      | bool `x[i,j]` for every `i < j`                                               | the graph                  |
| K4-free        | for every 4-set `{a,b,c,d}`: `Σ x ≤ 5`                                        | no K4                      |
| near-regular   | `D ≤ Σ_u x[v,u] ≤ D+1` per vertex                                             | `deg(v) ∈ {D, D+1}`        |
| independence   | for every `(α+1)`-subset: `Σ x_ij ≥ 1` (direct) *or* lazy cuts (see below)    | `α(G) ≤ α`                 |

No max-degree bound: `D+1` already caps it. No objective: edge count
is pinned by `D` (each witness has `D·n ≤ 2|E| ≤ (D+1)·n`), and edge
ranges for consecutive `D` don't overlap, so the first feasible `D` is
optimal.

---

## The D scan

```
d_lo, d_hi = degree_bounds(n, α)   # Ramsey
for D in d_lo .. d_hi:
    solve feasibility at D
        FEASIBLE   → return witness (first feasible D wins)
        INFEASIBLE → next D
        TIMEOUT    → next D (leaves a hole in the proof)
INFEASIBLE                         # exhausted all D
```

Time budget is split evenly across remaining `D` values as the scan
progresses.

---

## Direct vs lazy α enforcement

The `α ≤ α_cap` constraint has `C(n, α+1)` disjunctions. For small
`(n, α)` the direct encoding is fine. When `C(n, α+1) > 5_000_000`
the model switches to **lazy α cuts**:

1. Solve feasibility with only the cuts collected so far.
2. If the witness has actual `α > α_cap`, extract an α-witnessing
   independent set `S` and add `Σ_{i<j ∈ S} x_ij ≥ 1` as a new cut.
3. Loop. Cap at 500 iterations.

This is a classic cut-generation loop: you pay a solve per
iteration, but you never materialise the exponentially many
independence clauses up front.

The threshold `5_000_000` is a copy of the reference solver's
heuristic and hasn't been tuned.

---

## What it returns

0 or 1 graphs. Either:

- 1 graph at the first feasible `D`, with metadata
  `{"D": D, "alpha_cap": α, "method": "cpsat_direct" | "cpsat_lazy",
  "iterations": k}`, scored by the base class like any other search.
- 0 graphs, meaning INFEASIBLE (Ramsey or exhausted `D`-scan) or
  TIMEOUT.

Compared to `sat_exact`:

| aspect                  | `sat_regular`                           | `sat_exact`                            |
| ----------------------- | --------------------------------------- | -------------------------------------- |
| α enforcement           | direct or lazy cuts                     | direct (disjunction form)              |
| degree                  | pinned `deg(v) ∈ {D, D+1}`              | bounded `deg(v) ≤ d_cap`               |
| scan                    | 1-D over `D`                            | 2-D over `(α, d_max)`                  |
| objective               | none (feasibility)                      | none per box (Pareto scan)             |
| certified optimality    | assumes Hajnal                          | yes (via `prove_box` + `verify`)       |
| symmetry breaking       | none                                    | `anchor` / `chain` / `edge_lex`        |
| warm starts             | none                                    | circulant seeding                      |

---

## Why it's kept around

`SAT.md` Result 3 is a proved equivalence, so at the optimum
`sat_regular` and `sat_exact` agree. But the reference `regular_sat`
solver is what produced most of the baseline numbers in
`reference/pareto/` and `reference/regular_sat/`, and reproducing it
in the `Search` framework means:

- a smaller CP-SAT model for quick local checks,
- a smoke reference for `sat_exact` (if they disagree, something's
  wrong),
- a baseline that ports cleanly onto the cluster when the full
  Pareto proof is overkill.

The reference JSONs under `reference/` are kept only until
`sat_regular` + `sat_exact` have been validated against them at every
`(n, α)` they cover; after that, everything flows through `graph_db`
instead.
