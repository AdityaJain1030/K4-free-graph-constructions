# SAT Rebuild Plan — `SATExact`, `SATHeuristic`, `SATPipeline`

Design-only document. No code in this PR. Cloned and run on a
supercomputer (200 GB RAM, 16 CPUs), not this laptop.

---

## 1. Why rebuild

The `SAT_old/` stack works but tops out at:

- Modes 1 & 2 (`solve_k4free_direct` / `_lazy`): **fail at N ≥ 25**.
  Cause: `C(N, α+1)` independence clauses and `C(N, 4)` K₄ clauses
  are emitted eagerly; the clause database exceeds CP-SAT's working
  memory at N≈25 for useful α.
- Mode 4 (`regular_sat/solve_min_edges`): **fails at N ≥ 30**.
  Same clause-explosion for K₄; degree-pinning only narrows the
  search, not the model.

Additional inefficiencies noticed in recent reviews:

- Pareto scanner walks every α, ignoring the `c_log` objective.
  Most probed `(α, d)` pairs cannot beat the best circulant.
- Lazy α loop rebuilds the full model each iteration.
- Symmetry breaking is only degree ordering.
- The warm-start hint is a fixed Paley construction, independent
  of the target.

The rebuild split the work into three classes that each fix a subset
of these issues:

| Class          | Purpose                           | Target N       | Guarantee             |
| -------------- | --------------------------------- | -------------- | --------------------- |
| `SATExact`     | Certified optimality / infeasibility | 35–40 (small α) | Optimal for given box |
| `SATHeuristic` | Witness-finding at scale          | 50–80          | None                  |
| `SATPipeline`  | SAT-B seeds SAT-A, iterates       | see below      | Optimal for SAT-A box |

All three subclass `Search` (see `search/DESIGN.md`). Nothing in the
new code lives outside that contract.

---

## 2. Assumed hardware

- 200 GB RAM, 16 CPUs.
- No GPU requirement.
- Dense K₄ clause sets that OOM a 16 GB laptop (e.g., ~91K clauses at
  N=40) fit comfortably at 200 GB, but we still keep lazy modes — the
  bottleneck is solver *search*, not clause memory, past N≈35.
- CP-SAT solves configured with `num_workers=16` by default. pysat
  Glucose4 is single-threaded; for SAT-B where we use pysat, we
  parallelize *across seeds / ansatz choices*, not inside the solver.

---

## 3. `SATExact` — Certified mode

### Question it answers

Given `n`, target box `(α_max, d_max)` (or ranges), and optional
`c_bound`:

> *Does there exist a K₄-free graph on n vertices with α(G) ≤ α_max,
> d_max(G) ≤ d_max, and c_log(G) < c_bound?*

Returns: all such graphs found, **and** an INFEASIBLE certificate if
the solver proves the box empty. This is what guarantees optimality
when combined with `c_bound`.

### Core solver improvements over `SAT_old`

1. **Lazy K₄ constraints.** Do not emit `C(n, 4)` clauses up front.
   After each CP-SAT feasible solution, call `find_k4(adj)` (already
   in `utils/graph_props.py`), and add a clause forbidding that
   specific 4-clique. Most real iterations add <100 cuts, not 91K.
   This is the single biggest scaling improvement.

2. **Lazy α constraints with multi-cut-per-iteration.**
   Port the `max_cuts_per_iter > 1` path from `ilp_solver.py:228`
   but default it to *many*: run `alpha_exact` with a `k-best`
   enumerator (masking + re-run) to extract 4–8 disjoint violated
   independent sets per iteration. Collapses dozens of SAT rebuilds
   into a handful.

3. **Lex-leader symmetry breaking.** Replace the degree-ordering
   constraint `deg(i) ≥ deg(i+1)` with full lex-leader on adjacency
   rows under `S_n`. Generate it once from nauty orbits (we already
   have pynauty at `utils/pynauty.py`). Potentially N! factor
   reduction in the search tree.

4. **Ramsey-tight `(α, d)` pruning at every layer.** Before any SAT
   call, check `utils/ramsey.py::degree_bounds` and a new
   `ramsey_alpha_bounds` helper: many `(n, α, d)` triples are
   INFEASIBLE by a one-line theorem check and never reach CP-SAT.

5. **Warm start from the best known graph.** `__init__` accepts
   `hint_graph: nx.Graph | None`. The hint is converted to edge
   values via `model.add_hint`. Replaces the fixed Paley circulant
   in `ilp_solver.py:_generate_hint`. When called from `SATPipeline`,
   this is fed the best SAT-B output.

6. **`c_bound` pruning in Pareto mode.** When `enumerate_pareto=True`
   is set, iterate `(α, d)` integer lattice points in order of
   `α·d/(n·ln d)` ascending, and stop as soon as that lower bound
   reaches `c_bound`. In practice this probes O(√n) points instead
   of O(n log n).

7. **Monotone staircase mode.** When `enumerate_pareto=True` without
   `c_bound`, use the monotonicity of `d_min(α)` in α to walk the
   frontier in O(n) probes, not O(n log n).

### `search/sat_exact.py` skeleton

```python
class SATExact(Search):
    """
    CP-SAT certified solver for K4-free graphs.

    Modes (selected by kwarg combination):
      - single (α, d) feasibility          : alpha + d_max both set
      - α range, d_max fixed               : alpha_max, d_max set
      - full Pareto with c_bound pruning   : enumerate_pareto=True
      - near-regular (degree-pinned D)     : is_regular=True + D=...

    Constraints
    -----------
    alpha        : int  | None  — hard, α(G) ≤ alpha
    alpha_max    : int  | None  — hard upper bound if alpha is None
    d_max        : int  | None  — hard, d_max(G) ≤ d_max
    d_max_max    : int  | None  — hard upper bound if d_max is None
    is_regular   : bool         — hard, deg(v) ∈ {D, D+1}
    D            : int  | None  — required when is_regular=True
    c_bound      : float | None — soft; prunes Pareto candidates above
    hint_graph   : nx.Graph | None — warm start
    enumerate_pareto : bool     — return full frontier below c_bound
    timeout_s    : float        — per SAT solve call
    total_budget_s : float      — total wall clock, across all solves
    workers      : int          — num_workers for CP-SAT (default 16)
    """
    name = "sat_exact"
```

Internal structure:

- `_solve_box(alpha_cap, d_cap, hint)` — one CP-SAT call with lazy
  K₄ + lazy α + lex-leader. Returns
  `("FEASIBLE"|"INFEASIBLE"|"TIMEOUT", adj|None, stats)`.
- `_enumerate_pareto(c_bound)` — iterates candidate `(α, d)` points
  filtered by Ramsey and `c_bound`, calls `_solve_box`, yields
  graphs.
- `_run()` — routes to one of the two above based on kwargs, wraps
  each returned adjacency in `nx.Graph`, stamps, attaches metadata:
  `{"alpha_target": ..., "d_max_target": ..., "solver_stats": ...,
   "status": "OPTIMAL"|"FEASIBLE"|"INFEASIBLE"|"TIMEOUT"}`.

### What `SATExact` reuses from `SAT_old/`

- `k4_check.find_k4` (already generalized into
  `utils/graph_props.find_k4`) — used for lazy K₄ cuts.
- `alpha_exact.alpha_exact` (already in `utils/graph_props`) — used
  for lazy α cuts.
- `utils/ramsey.degree_bounds` — used for pre-solve pruning.
- Nothing else. `ilp_solver.py` is *not* imported; its logic is
  rewritten inside `sat_exact.py` because (a) it's >300 LOC and
  tangled, (b) lazy K₄ is a fundamental change to `_build_model`,
  (c) `search/` is supposed to be self-contained per DESIGN.md.

---

## 4. `SATHeuristic` — Scale mode

### Question it answers

Given `n` and a search budget, find the best K₄-free graph(s)
achievable on `n` vertices within an ansatz (symmetry restriction).
**No optimality guarantee** — but runs at N values where `SATExact`
never returns.

### Three ansätze, one class

The ansatz is a kwarg. Each restricts the variable set so the SAT
model is tractable even at N=80+.

#### 4a. Cayley ansatz (`ansatz="cayley"`)

- Parameter: connection set `S ⊆ {1, …, n//2}` (size ≤ n/2 vars).
- Edge `{i, j}` present iff `(j-i) mod n ∈ S`.
- Vertex-transitive and regular → `d_max = 2|S|` (or `2|S|-1` if
  `n/2 ∈ S` and `n` even). Independence number can be computed
  exactly on the quotient for small |S|.
- K₄-free constraints reduce to: for each 4-subset of `Z_n`,
  if its pairwise differences form a set that would be entirely
  selected, forbid. Typically ~`C(n,3)` clauses (not `C(n,4)`),
  and the solver never sees edge variables.
- **N=50–80 is routinely feasible** this way. Limitation: we're
  searching only Cayley graphs on `Z_n`; many optima (e.g., all
  Paley graphs, generalized Paley) *are* Cayley, but some aren't.

#### 4b. Block decomposition (`ansatz="block"`)

- Parameter: `n = k · b`. Vertices partitioned into `k` blocks of
  `b` each.
- Search variables:
  - Intra-block edge pattern per block (small: `C(b, 2)` per
    block, or 1 shared pattern if blocks are forced equal).
  - Inter-block adjacency matrix: a bipartite pattern per
    (block_i, block_j) pair. Often constrained to be a matching
    or a regular bipartite graph → O(b) choices per pair, not
    `2^{b^2}`.
- K₄-free becomes a local condition on each triple of blocks.
  For `k=5, b=6` (N=30): ~few hundred variables.
- Useful for N=40–60 where we suspect decomposition.

#### 4c. Perturbation ansatz (`ansatz="perturb"`)

- Takes a seed graph (e.g., from `CirculantSearch` or a Paley
  graph) and searches for small perturbations: flip up to `k`
  edges, keep K₄-free, minimize `c_log`.
- Variables: `O(n^2)` binary edge-flip vars constrained to sum
  ≤ `k`. K₄-free enforced lazily.
- Local search in SAT clothing. Good at polishing a near-optimal
  seed at N=40–60.

### Incremental SAT via pysat

For ansätze (a) and (c), the inner loop is a feasibility check with
repeated tightening of an α or c bound. pysat `Glucose4` supports
assumption literals, so the model stays loaded and we only push/pop
one literal per iteration. Empirically 5–10× faster than CP-SAT for
this pattern. Already available — `funsearch/claude_search/graph_utils.py`
wraps it.

Ansatz (b) uses CP-SAT because block inter-edge patterns are
counted-cardinality constraints CP-SAT handles natively.

### Parallelism

Single 16-CPU job = 16 parallel seed trials (different RNG seeds,
different Cayley connection-set initializations, different block
partitions). Coordinate via `multiprocessing.Pool`; aggregate the
best into `_run()`'s return list.

### `search/sat_heuristic.py` skeleton

```python
class SATHeuristic(Search):
    """
    SAT-driven search under a symmetry ansatz. Not complete; returns
    the best K4-free graphs found within the budget.

    Constraints
    -----------
    ansatz       : "cayley" | "block" | "perturb"
    alpha_target : int | None    — soft; scoring target, not clause
    d_max_target : int | None    — soft
    c_target     : float | None  — soft; tighten until reached
    seed_graph   : nx.Graph | None — for ansatz="perturb"
    flip_budget  : int           — for ansatz="perturb"
    block_k, block_b : int       — for ansatz="block"; n == block_k*block_b
    timeout_s    : float
    n_seeds      : int = 16      — parallel RNG seeds
    workers_per_seed : int = 1   — CP-SAT workers inside each seed
    """
    name = "sat_heuristic"
```

---

## 5. `SATPipeline` — Combination

### What it does

One `Search` subclass that runs SAT-B → SAT-A with feedback, plus
optional iteration. Embodies the "circulants give a free c*,
SAT only explores below the isoquant" idea end-to-end.

### Flow

```
┌──────────────────────────────────────────────────────────────────┐
│  SATPipeline._run(n)                                             │
│                                                                  │
│  Stage 0 (optional): seed scan                                   │
│    CirculantSearch(n=n, top_k=5)                                 │
│    → c_best, best_seed_graph                                     │
│                                                                  │
│  Stage 1: SAT-B (scale witness)                                  │
│    SATHeuristic(n=n, ansatz="cayley", c_target=c_best,           │
│                 timeout_s=heuristic_budget_s)                    │
│    → possibly better c_best, new seed graph                      │
│                                                                  │
│  Stage 2: SAT-A (certified refinement)                           │
│    SATExact(n=n, enumerate_pareto=True,                          │
│             c_bound=c_best, hint_graph=seed,                     │
│             total_budget_s=exact_budget_s,                       │
│             workers=16)                                          │
│    → either (a) improves c_best with a certified graph,          │
│             (b) proves INFEASIBLE for all points below c_best    │
│                 → c_best is now the **proven** minimum for the   │
│                 reachable Pareto lattice                          │
│                                                                  │
│  Stage 3 (optional): iterate                                     │
│    If SAT-A improved c_best, feed the new graph back as seed     │
│    and loop to Stage 1 with a smaller c_target.                  │
│                                                                  │
│  Return merged graphs: {best seed, SAT-B finds, SAT-A finds}.    │
└──────────────────────────────────────────────────────────────────┘
```

### `search/sat_pipeline.py` skeleton

```python
class SATPipeline(Search):
    """
    End-to-end pipeline: seed → SAT heuristic → SAT exact, with the
    heuristic's best c_log feeding SAT exact as a pruning bound and
    its best graph feeding it as a warm start.

    Constraints
    -----------
    heuristic_budget_s  : float = 600
    exact_budget_s      : float = 1800
    workers             : int = 16
    include_circulant_seed : bool = True
    ansatz              : forwarded to SATHeuristic
    max_iterations      : int = 2   — loops stage 1→2 this many times
    """
    name = "sat_pipeline"
```

Uses `parent_logger=self._logger` on the nested `Search` instances
so every inner event appears in the pipeline's aggregate log.

---

## 6. File layout

```
search/
├── sat_exact.py         new     — SATExact class
├── sat_heuristic.py     new     — SATHeuristic class
├── sat_pipeline.py      new     — SATPipeline class
├── SAT_EXACT.md         new     — user-facing doc, per ADDING_A_SEARCH.md
├── SAT_HEURISTIC.md     new     — user-facing doc
├── SAT_PIPELINE.md      new     — user-facing doc
└── __init__.py          edit    — export three new classes

utils/
├── sat_build.py         new     — shared CP-SAT model builders:
│                                   _lazy_k4_callback, _lex_leader,
│                                   _ramsey_alpha_bounds
└── graph_props.py       unchanged

scripts/
├── run_sat_exact.py     new     — CLI driver
├── run_sat_heuristic.py new     — CLI driver
└── run_sat_pipeline.py  new     — CLI driver (main entry for N runs)
```

No changes to `SAT_old/`. That stack is kept as a reference and for
reproducing old Pareto results.

---

## 7. Phasing

Implementation order (each phase independently shippable, each
adds measurable capability):

**Phase 1 — `SATExact` with lazy K₄ and lazy α only.**
No lex-leader yet, no `c_bound` pruning. Verifies the scaffolding
and the ABC integration. Measured goal: recover all `SAT_old`
results for N ≤ 24 at ≤ 2× speed (i.e., no regression).

**Phase 2 — Add lex-leader and Ramsey-tight pruning to `SATExact`.**
Measured goal: first feasible / first infeasible at N=28 within
the supercomputer's 4-hour wall clock.

**Phase 3 — `SATHeuristic` with Cayley ansatz.**
Measured goal: a K₄-free Cayley graph on N=50 with c_log below the
best N=50 circulant.

**Phase 4 — `SATPipeline` stitching phases 2 and 3.**
Measured goal: one combined job on N=30 beats either class alone in
total wall clock to equivalent certified c_log.

**Phase 5 — Block ansatz and perturbation ansatz in `SATHeuristic`.**
Opportunistic. Only pursue if Cayley hits a ceiling.

---

## 8. What stays in `SAT_old/`

- `run_production.py` and `pareto_scanner.py` stay as reference.
- Their results (`SAT_old/k4free_ilp/results/pareto_n{N}.json`) are
  the validation set for Phase 1: any graph they found should also
  be found (or beaten) by `SATExact` at the same `(n, α, d)`.
- Once `SATPipeline` is proven on N=20…30, `SAT_old/` can be
  archived. Not deleted — the Pareto JSONs are data.

---

## 9. Risks / open questions

1. **Lex-leader is expensive to generate.** Nauty orbits take a few
   seconds per N, but the resulting lex clauses can number in the
   thousands. If the clause overhead exceeds the symmetry-breaking
   benefit, fall back to the existing degree-ordering constraint
   and a vertex-0-has-max-degree anchor.

2. **Lazy K₄ can thrash.** If the solver keeps producing graphs
   with K₄ because the rest of the model under-constrains, we
   pay a rebuild per iteration. Mitigation: add a K₄-density
   scoring clause (sum of candidate triangles ≤ bound) to steer
   CP-SAT away from K₄-dense regions even before we've cut them.

3. **Cayley restriction may be too tight.** Some known near-optimal
   graphs are Cayley over non-cyclic groups. If N=50 Cayley-on-`Z_n`
   can't beat the best circulant, add Cayley-on-`Z_p × Z_q` as a
   sub-ansatz. Pre-work: enumerate which composite `n` values admit
   non-trivial factorizations.

4. **pysat incremental vs CP-SAT portfolio.** pysat is single-threaded
   but genuinely incremental. CP-SAT is multi-worker but rebuilds. On
   16 CPUs, the break-even is surprisingly close — needs an
   experiment at Phase 1 exit to decide which engine SAT-B uses.

5. **Memory at N=40 with lazy K₄.** If the accumulated lazy cuts
   exceed ~5 GB per CP-SAT process, and we run 16 of them… we use
   60 GB for SAT-A and leave 140 GB headroom. Fine. Only flag if
   we push to N=50 exact mode, which we don't plan to.

6. **OOM in `alpha_exact` on large graphs.** The branch-and-bound
   MIS is fine to N=50 but bitmask arithmetic on N≥64 needs
   `int` rather than a fixed-width mask — already how it's
   written in `utils/graph_props.py`, but verify at Phase 3.

---

## 10. Not in scope

- LLM-driven proposal (FunSearch). Lives in `funsearch/`, integrated
  separately. `SATPipeline` doesn't depend on it.
- MaxSAT formulation (optimization-variant SAT). The pipeline's
  Pareto-with-`c_bound` achieves the same effect with less framework
  churn; revisit only if CP-SAT consistently times out.
- GPU / CUDA-based SAT. Not a thing for this problem class.
- Cross-N sweeps. That's `scripts/run_sweep_*.py`'s job; each SAT
  class stays per-N per the ABC contract.

---

## 11. Summary

Three classes, one pipeline, slot into the existing `Search` ABC:

- **`SATExact`** — fixes the `SAT_old` solver's scaling bottlenecks
  (lazy K₄, lex-leader, Ramsey pruning, c_log pruning) to push
  *certified* N from 25 → ~35–40.
- **`SATHeuristic`** — trades optimality for reach via symmetry
  ansätze (Cayley / block / perturb), targets N=50–80.
- **`SATPipeline`** — runs B first to establish `c_best` and a warm
  start, then A to certify / improve, with optional iteration.

Work is phased so each phase is independently usable. Nothing runs
on the laptop; the supercomputer sees its first job at Phase 1 end.
