# Next optimizations for `search/SAT/sat.py`

Forward plan informed by the empirical findings in `RESULTS_N20.md`
and the prior optimization log in
`docs/searches/sat/SAT_OPTIMIZATION.md`. The latter records every
accelerator that was tried on the (now-deprecated) `sat_exact.py`
predecessor — keep / discard verdicts and ablation timings.

The principle from §7 of that doc is the rubric for everything below:

> 1. Local beats global.
> 2. Bool comparisons beat totalizers.
> 3. Reification is expensive.
> 4. The headline metric and the hard proofs are decoupled.
> 5. Correctness is cheap; speed is earned one constraint at a time.

---

## What `sat.py` already has

- (C1) K₄-free as $\sum \le 5$ — linear inequality.
- (C2) α-bound as $\sum \ge 1$ — linear inequality.
- (C3) per-vertex degree ≤ $d_{\max}$ — linear inequality.
- `_ramsey_prune`: α=0, d=0, Caro–Wei, $R(4, α+1)$ upper bounds —
  pre-solve box rejection, sound.

What's still missing relative to the proven-good `sat_exact`
configuration:

| Accelerator                              | `sat_exact` default? | `sat.py` |
|------------------------------------------|:-------------------:|:--------:|
| (C1) and (C2) as `add_bool_or` clauses   | yes                 | **no**   |
| Per-vertex Ramsey min-degree clause      | yes                 | **no**   |
| `edge_lex` row-0 symmetry break          | yes                 | **no**   |
| Multi-worker (`num_search_workers`)      | implicit (4)        | **no**   |

Each of these has either a published ablation number or a clean
correctness argument. The next four sections turn each into a
concrete change.

---

## Priority 1 — `add_bool_or` for K₄ and α (free, ~9 %)

**Rationale.** `sum_{e ⊂ S} x_e ≤ 5` over six Booleans is logically
equivalent to the 6-literal clause $\bigvee_{e \subset S} \lnot x_e$
(at least one edge absent). Same shape for the α-clause: $\sum \ge 1$
↔ disjunction. CP-SAT routes linear inequalities through its
linear-cardinality reformulation; routing them through
`model.add_bool_or` keeps them in the SAT core directly, where unit
propagation fires the moment 5 of 6 are pinned.

**Ablation (from `SAT_OPTIMIZATION.md` §2.6):**

| Encoding                                       | n=17 scan | Δ          |
|------------------------------------------------|-----------|------------|
| linear `sum ≤ 5` (current `sat.py`)            | 37.80 s   | baseline   |
| `add_bool_or([¬x_e for e ⊂ S])`                | 34.52 s   | **−9 %**   |

**Risk.** None — pure encoding swap, equal logical content. Already
the default in `sat_exact.py`.

**Implementation.** ~10 lines: replace
`model.Add(sum(...) <= 5)` with
`model.add_bool_or([x[(a,b)].negated() for (a,b) in combinations(S,2)])`,
and the α-bound `≥ 1` with the un-negated disjunction.

---

## Priority 2 — `edge_lex` row-0 symmetry break (big, cheap, sound) ✅ implemented

**Status.** Implemented in `search/SAT/sat.py` and `sat_min_deg.py`
on 2026-04-26 as kwarg `edge_lex` (default `True`). Documented in
`experiments/SAT/SAT.md` §3.2.

**Rationale.** Without symmetry breaking, every $n!$ vertex-relabeling
of the same graph is a distinct solution; the solver can re-explore
isomorphic branches arbitrarily. `edge_lex` row-0 forces

$$
x_{0,1} \ge x_{0,2} \ge \ldots \ge x_{0,n-1},
$$

a single chain of $n - 2$ Boolean comparisons (no totalizers, no aux
vars). It quotients out the $S_{n-1}$ stabilizer of vertex 0 — a
large but soundly-removable subgroup, as adjacent transpositions
generate all of $S_n$.

**Why row-0 only is the empirical default.** Higher-row extensions
(`edge_lex_rows ≥ 1`) are sound but pathologically slow at boundary
boxes — `SAT_OPTIMIZATION.md` §8.3 documents a **2000× slowdown** at
$(n=19, α=4, d=6)$ going from $k_{\max} = 0$ to $k_{\max} = 3$ for
the same FEASIBLE verdict. Stick with row-0 unless explicit-box
profiling says otherwise.

**Ablation (from `SAT_OPTIMIZATION.md` §2.3 + §2.4):**

| Setting                                  | speedup vs no symmetry |
|------------------------------------------|------------------------|
| `chain` (degree-monotonic, totalizer)    | sometimes slower       |
| `anchor` (deg(0) ≥ deg(v))               | mild win               |
| `edge_lex` row-0 only                    | **3–5× at n=13, ~100× at n=12** |
| `edge_lex` row-0 + row-1 (n=16, α=3, d=7)| **40× on the boundary box** |

Concrete: $(n = 16, α = 3, d = 7)$ went from 28.3 s to 0.72 s in
the old `sat_exact` configuration (rows 0+1, `add_bool_or`, 4
workers).

**On-implementation benchmark (2026-04-26, single worker, linear
constraints, default everything else off):**

| Box                          | `edge_lex=False`  | `edge_lex=True`   | speedup     |
|------------------------------|------------------:|------------------:|------------:|
| $n=13, α=3, d=6$ (SAT)        | 0.083 s           | 0.046 s           | ~1.8×       |
| $n=14, α=3, d=7$ (SAT)        | 0.098 s           | 0.058 s           | ~1.7×       |
| **$n=15, α=3, d=6$ (UNSAT)**  | **60 s timeout**  | **8.5 s UNSAT**   | **> 7×**    |
| $n=16, α=3, d=7$ (UNSAT)      | 120 s timeout     | 120 s timeout     | (need P1+P4)|

Witness graphs returned with `edge_lex=True` have vertex 0's
adjacency row in the canonical "neighbors first" pattern
(`(1,...,1,0,...,0)`), confirming the constraint is wired correctly.

The headline is the n=15 row: a UNSAT proof the solver could not close
in 60 s without symmetry now closes in under 10 s. UNSAT direction is
exactly where row-0 lex pays off — the solver no longer re-closes
$S_{n-1}$-relabeled sub-trees of the same partial graph.

The n=16 boundary box still hits the 120 s wall both ways. The 28.3
s → 0.72 s figure cited in `SAT_OPTIMIZATION.md` §2.4 was achieved
with rows 0+1 + `add_bool_or` + 4 workers; closing this row needs P1
and P4 stacked on top of the row-0 break.

**Risk.** None on row-0. Higher rows: sound but punishing on
narrow-orbit instances. Future opt-in via an `edge_lex_rows` int
kwarg matching `sat_exact`.

---

## Priority 3 — Per-vertex Ramsey min-degree clause (cheap)

**Rationale.** From the `R(4, α + 1)` argument: a K₄-free graph on $n$
vertices with $\alpha(G) \le α$ must have *every vertex* of degree at
least $n - R(4, α)$ (else removing the vertex would give a smaller
Ramsey-violator). This is $n$ linear inequalities of the form
$\deg(v) \ge d_{\text{Ramsey}}$ — the dual of (C3) and the per-vertex
strengthening of the box-level Caro–Wei prune we already do.

**Soundness.** Same Ramsey numbers used by `_ramsey_prune` Rule 4
(`_R4_UB` table); kept inside the `ramsey_prune=True` flag so
ablations stay clean.

**Empirical gain (from `sat_exact`).** Closes UNSAT proofs faster on
small-α boundary boxes. Quantified ablation lives in
`logs/sat_exact_ablation.json`; rough order is **2–3× on the binding
INFEASIBLE box per row** at $n \le 17$.

**Risk.** Only fires when $n - R(4, α) > 0$, otherwise vacuous.
Cheap.

**Implementation.** ~10 lines: lookup `n - R(4, α)`; if positive,
add `model.Add(deg_expr(v) >= d_min)` for each vertex.

---

## Priority 4 — Multi-worker default (free)

**Rationale.** CP-SAT runs a portfolio of search strategies in
parallel; `num_search_workers = N` gives N times the diversity at $N$
times the CPU cost. Anecdotally, 4 workers ≈ 2–3× wall speedup on
hard UNSAT proofs (it's not a true 4× because the workers share work
and one usually closes the proof).

**Ablation context.** All `optimality_proofs.json` entries used 4
workers. The 1350 s UNSAT at $(n = 20, α = 4, d = 6)$ is a 4-worker
number; 1-worker would scale roughly to ~3000–4000 s for the same
proof.

**Risk.** None on a workstation; on the laptop, can starve other
processes. Make it a kwarg `workers: int = 4` with a runtime cap
guard.

**Implementation.** 1 line:
`solver.parameters.num_search_workers = self.workers`.

---

## Priority 5 — CEGAR α-clauses (big at large α, novel)

**Status:** never implemented in this codebase. Sketched in
`OPTIMIZATION.md` §4.3 as the highest-leverage uncharted optimization.

**Rationale.** The α family is $\binom{n}{α + 1}$ clauses — the
dominant part of the model for $α + 1 \approx n/2$, and the practical
scaling bottleneck. Most of those clauses are trivially satisfied at
runtime; only a few hundred actively bind. CEGAR exploits this:

```
1. Build model with K4 + degree only (no α clauses).
2. Solve. Get a candidate G.
3. Compute α(G) by an independent oracle.
4. If α(G) ≤ α: done, return G.
5. Else: extract a witness independent (α+1)-subset T.
        Add ONE clause: Σ_{e ⊂ T} x_e ≥ 1.
        Goto 2.
```

**Predicted reach.** From `OPTIMIZATION.md` §4.3:
- Effective α-clause count drops from $\binom{n}{α+1}$ to ~10–100.
- More effective as α grows (upfront family blows up binomially;
  separations grow ~$O(α)$ to $O(α^2)$).
- At the upper-frontier $α \approx n^{3/5}$, this is the difference
  between $10^7$ clauses and a few hundred.

**Risk.** Medium. Termination is guaranteed (each iteration adds a
clause not previously falsified), but the worst case adds the entire
α family. Empirically convergent on similar combinatorial-search
problems in 10–100 separations.

**Implementation cost.** ~30 lines for the basic loop + warm-start
between iterations. Highest leverage past $n \approx 22$.

---

## The n = 21 wall

The motivating problem behind P6–P8 below: even on the
**200 GB / 32-core cluster**, with the full `sat_exact` pipeline
(`add_bool_or` + `edge_lex` + Ramsey + `c_log_prune` + circulant seed
+ 4 workers), the binding box $(n=21, α=4, d=7)$ does **not** close
inside `timeout_s=1800`. From `logs/optimality_proofs.json`:

```
n=21, α=4, d_max=7, status=TIMEOUT, wall=1701s, edge_lex
n=21, α=4, d_max=7, status=TIMEOUT, wall=3398s, chain
```

So neither symmetry mode at the cluster's full compute closed the
proof. Every accelerator above (P1–P5) is either already deployed in
that pipeline or is a marginal additional gain at this scale. The
following options break with that pattern: they either **partition
the search across cores in a way the portfolio cannot** (P6, P7) or
**shrink the effective search tree by exploiting structure CP-SAT
cannot see** (P8, P5/CEGAR).

---

## Priority 6 — KISSAT external solver (cheapest experiment, ✅ wired up)

**Status.** Implemented in `search/SAT/sat_kissat.py` as
`SATKissat`. KISSAT is built into the conda env via
`scripts/setup_kissat.sh` (mirrors `setup_nauty.sh` — sources at
`$CONDA_PREFIX/src/kissat`, binary on PATH via the env activation
hook). Tested: returns correct SAT / UNSAT verdicts on the standard
sanity boxes (Paley-17, Ramsey/CW prunes, n=15 boundary UNSAT).

### How KISSAT works (the short version)

KISSAT (Armin Biere, multi-year SAT-Competition champion) is a pure
CDCL/inprocessing SAT solver:

- **CDCL loop.** Decide a variable → propagate via two-watched
  literals → on conflict, run **conflict analysis** to extract a
  1-UIP learned clause that captures *exactly* why the conflict
  happened → backjump non-chronologically and resume. Each conflict
  permanently rules out the same conflict pattern from recurring
  anywhere in the search.
- **Variable selection.** EVSIDS — exponentially-decayed activity
  score, bumped on appearance in learned clauses. Picks the most-
  contended variable to branch on.
- **Restarts.** Two-mode schedule: *focused* (frequent restarts,
  Glucose/LBD-driven — good for UNSAT) and *stable* (rare restarts,
  aggressive in one region — good for SAT). Switches dynamically.
- **Inprocessing.** Mid-search simplification: subsumption,
  vivification, bounded variable elimination. Actively shrinks the
  formula as the solve runs — crucial on hard instances where the
  initial encoding has slack.
- **LBD-based clause quality.** Learned clauses scored by their
  Literal Block Distance (number of distinct decision levels). Low
  LBD = "essential", kept; high LBD = forgettable.
- **Cache-tuned C.** Custom data structures, no STL overhead, hand-
  laid out around modern x86 cache lines.

**Why we'd want it.** Our boundary boxes are all UNSAT proofs.
KISSAT's CDCL machinery is purpose-built for exactly that — every
conflict produces a permanent learned-clause obstruction, and over
millions of conflicts the database becomes a precise summary of the
unsatisfiable parts of the search space. Where CP-SAT's strength is
its portfolio of mixed CP/SAT/LP strategies, KISSAT's strength is
running *one* strategy extremely well.

### Where KISSAT can lose

CP-SAT has machinery KISSAT doesn't:

1. **Native cardinality propagators** for $\sum x_i \le k$. Our
   degree constraint is exactly such a cardinality. CP-SAT propagates
   it natively in $O(1)$ amortized; KISSAT must expand it to clauses.
2. **LP relaxation cuts.** CP-SAT spawns LP solvers internally;
   KISSAT is pure CDCL.

### The cardinality-encoding problem

DIMACS has no native cardinality. Our current `SATKissat` uses the
**pairwise-blocking** encoding: for each vertex $v$ and each
$(d_{\max}+1)$-subset $W$ of its potential neighbors, add the clause
$\bigvee_{w \in W} \lnot x_{v,w}$ — "$v$ cannot be adjacent to all
$d_{\max}+1$ of these simultaneously." Sound but blows up:

| $n$ | $d_{\max}$ | degree clauses    | total clauses (n=15, α=3, d=6) |
|----:|-----------:|------------------:|-------------------------------:|
| 15  | 6          | $15 \cdot \binom{14}{7} = 51480$ | 54223                  |
| 20  | 7          | $20 \cdot \binom{19}{8} = 1.5 \times 10^6$ | ~1.5M       |
| 25  | 9          | $25 \cdot \binom{24}{10} = 5.4 \times 10^7$ | ~54M+       |

Compare CP-SAT's representation: 1 cardinality constraint per vertex.

**First experiment (pairwise-blocking encoding, 2026-04-26).**

| Box                          | CP-SAT (1 worker, edge_lex) | KISSAT (1 worker, pairwise card.) | KISSAT clauses |
|------------------------------|-----------------------------|-----------------------------------|---------------:|
| $n=15, α=3, d=6$ (UNSAT)     | **9.6 s**                   | 24 s                              | 54 223         |
| **$n=20, α=4, d=6$ (UNSAT)** | **1350 s** (4 workers)      | **TIMEOUT @ 1800 s**              | **1 028 127**  |

Pairwise blocking expansion of the degree constraint blew the model
up to 1.03 M clauses at $n=20$ — overwhelmingly dominated by the
$20 \cdot \binom{19}{7} \approx 1.008\,\mathrm{M}$ degree clauses,
vs CP-SAT's 20 native cardinality constraints. The encoding bloat
swallowed whatever CDCL learning would have bought.

**Sinz sequential-counter encoding (2026-04-26, ✅ implemented).**

Fix in `SATKissat`: `degree_encoding="sinz"` (now the default).
Encodes $\sum x_{vu} \le d_{\max}$ via Sinz's 2005 sequential counter
— $O(n d)$ aux variables and clauses per vertex instead of
$\binom{n-1}{d+1}$. Concretely:

| Setting (n=20, α=4, d=6) | Variables | Clauses     |
|---------------------------|----------:|------------:|
| Pairwise blocking         | 190       | 1 028 127   |
| **Sinz sequential**       | 2 470     | **25 067**  |

40× smaller model. Sanity-checked against CP-SAT on 7 small boxes —
all SAT/UNSAT verdicts match.

### Empirical scoreboard (after Sinz fix)

**UNSAT (Mode 2 — disprover):**

| Box                          | CP-SAT             | KISSAT-Sinz (1w)    | per-core winner |
|------------------------------|--------------------|---------------------|-----------------|
| $n=15, α=3, d=6$ (UNSAT)     | 9.6 s (1 worker)   | **3.4 s**           | **KISSAT 3×**   |
| **$n=20, α=4, d=6$ (UNSAT)** | **1350 s** (4 workers) | TIMEOUT @ 1800 s | CP-SAT (only via portfolio) |

**SAT-find (Mode 1 — searcher), 120 s budget, 1 worker each, KISSAT
with `--sat` preset:**

| Box                          | CP-SAT (1w) | KISSAT-Sinz (1w) | KISSAT speedup |
|------------------------------|------------:|-----------------:|---------------:|
| (13, 3, 6) SAT               | 0.029 s     | 0.018 s          | **1.66×**      |
| (15, 3, 7) SAT               | 0.045 s     | 0.024 s          | **1.85×**      |
| (17, 3, 8) SAT (Paley-17)    | 0.061 s     | 0.052 s          | **1.18×**      |
| (19, 4, 6) SAT               | 15.6 s      | 6.5 s            | **2.42×**      |
| (20, 4, 7) SAT               | 0.89 s      | 0.090 s          | **9.89×**      |
| (22, 4, 8) SAT               | TIMEOUT     | TIMEOUT          | tie (both fail cold-start) |

### Verdict (revised)

**Per-core, KISSAT-Sinz wins every measurable comparison** — Mode 1
SAT-find by 1.18–9.89×, Mode 2 single-thread UNSAT by 3×. CP-SAT's
only remaining win is on (20, 4, 6) UNSAT where its **4-worker
portfolio** beat single-thread KISSAT. CP-SAT 1-worker on that box
would presumably take 2000–5000 s — strictly worse than KISSAT 1
worker. So:

> **The right per-core engine for both SAT and UNSAT on this problem
> class is KISSAT-Sinz**, with `--sat` / `--unsat` presets covering
> the directional split. CP-SAT's place is now narrow: (a) Mode 3
> improver work, where its native cardinality + hints are genuinely
> cleaner; (b) multi-worker UNSAT *until* cube-and-conquer is wired
> up.

The (22, 4, 8) cold-start tie is the strongest argument yet for the
Mode 3 improver: graph_db already has a circulant witness at this
box ($c_{\log} = 0.6995$), but neither cold-start solver finds it in
120 s. A warm-start path that hints the circulant in and asks
"close the gap" would be sub-second.

### New deployment plan

1. **Default solver: `SATKissat(degree_encoding='sinz')`** with
   `extra_args=['--sat']` for SAT-find, `['--unsat']` for UNSAT.
2. **Keep `SAT` (CP-SAT) for the improver path** until KISSAT
   warm-start tooling is built.
3. **Cube-and-conquer (§P7) is now the highest-leverage open move.**
   Per-core KISSAT wins; the only thing missing is a parallelizer
   that beats CP-SAT's 4-worker portfolio on the boundary UNSAT
   boxes. CnC scales near-linearly to 32 cores, which is what the
   cluster needs.

### Open follow-ups

1. **Sequential-counter cardinality encoding (Sinz 2005).** Adds
   $O(n k)$ aux vars and clauses instead of $\binom{n}{k+1}$.
   Standard, well-understood. Should drop the n=15 model from 54k
   clauses to ~2k. Likely flips the head-to-head; high priority.
2. **Cardinality-network encoding (Eén–Sörensson).** $O(n \log^2 n)$
   clauses, asymptotically tighter; more aux vars, more overhead per
   conflict. Worth comparing against sequential counter.
3. **Run KISSAT on the n=21 box once the encoding is competitive.**
   Cheap experiment — if it cracks the box CP-SAT couldn't, the
   whole tooling investment paid off in one solve.
4. **Hybrid: KISSAT-as-CEGAR-leaf-solver.** Run a small CP-SAT solve
   to get a candidate witness, hand the harder UNSAT boundary
   verification to KISSAT.

---

## Priority 7 — Cube-and-conquer (parallel divide-and-conquer SAT) ⚠️ partial

**Status.** Wired up in `search/SAT/cube_and_conquer.py` as
`SATCubeAndConquer`. Orchestration validated; **algorithmic gap is
the cuber**, not the parallel infrastructure.

**Idea.** A pure-portfolio solver (CP-SAT, KISSAT, …) attacks a
single root formula with multiple workers. **Cube-and-conquer**
splits the formula into thousands of disjoint **cubes** — partial
assignments to a small set of carefully-chosen "branching" variables
— and solves each cube independently in parallel. The cubes are
chosen by a *lookahead* cuber, which probes each candidate branching
variable, measures how much propagation each branch triggers, and
picks the variable that best balances and shrinks the resulting
sub-formulas.

Standard pipeline:

```
DIMACS export  →  march_cu (lookahead cuber)  →  thousands of cubes
                                                       ↓
                       parallel array of leaf solvers (CaDiCaL/KISSAT)
                                                       ↓
                              if any cube is SAT, formula is SAT
                              if all cubes are UNSAT, formula is UNSAT
```

**Track record.** Cube-and-conquer is the technique that proved the
**Boolean Pythagorean Triples** conjecture — a 200 TB proof on 800
cores, where no single SAT solver could close the formula in any
reasonable time. The leaf cubes were each solved in seconds, but the
formula split itself was the leverage.

**Why it fits 32 CPUs.** Portfolio scaling is sub-linear (workers
share work, redundant proofs). Cube-and-conquer is **near-linear in
core count** as long as cubes are roughly balanced and there are
enough of them. 32 cores routinely yields 25–30× wall-clock speedup
over a 1-core baseline on hard instances.

**Effort.** Medium.
- DIMACS export: already implemented in `SATKissat._build_dimacs`.
- Cuber: `march_cu` from the SAT competition pipeline (separate
  binary, similar build pattern to KISSAT). Need to add a
  `setup_march.sh`.
- Glue: small Python orchestrator that runs `march_cu` for cube
  generation, then dispatches per-cube KISSAT (or CaDiCaL) calls
  across cores via subprocess Popen pool, collects results.
- Aggregation: collect proofs, return graph from any SAT cube.

**Risk.** Low. The pipeline is well-trodden; the engineering is in
plumbing rather than algorithm design. Estimated 1–2 days for a
working prototype.

### Empirical results (2026-04-26, naive row-0 cuber)

The first prototype (`SATCubeAndConquer`) ships a **naive Python
cuber** — branches on the first $k$ row-0 edge variables, generating
$k+1$ monotone-prefix cubes when `edge_lex=True`. Crucially, the
real *lookahead-style* cuber (`march_cu`) was not deployed because
its bundled Makefile fails to link with our gcc 14 toolchain
(missing references to `fixEq`, `restore_big_clauses`,
`look_fix_binary_implications`, etc — looks like a stale upstream
build).

**Orchestration sanity (16-core WSL2 box, KISSAT-Sinz per cube):**

| Box | Direction | Baseline (1 worker) | CnC best | Speedup | Verdict |
|---|---|---:|---:|---:|---|
| n=15, α=3, d=6 | UNSAT | 3.4 s | 2.4 s (d=4)  | 1.4× | ⚠️ marginal |
| n=19, α=4, d=5 | UNSAT | 39.5 s | 39.1 s (d=10) | ~1× | ⚠️ no win |
| n=19, α=4, d=6 | SAT | 4.7 s | 0.17 s (d=4) | **27×** | ✅ big win |
| n=20, α=4, d=7 | SAT | 0.89 s | 0.09 s (earlier) | **9.9×** | ✅ big win |

**Direction asymmetry.** SAT-direction CnC wins enormously because
the first cube to find a witness short-circuits everything. UNSAT
direction barely moves the needle.

**Why UNSAT loses with naive cubing.** The cube walls show a
brutal imbalance:

```
n=19 α=4 d=5 UNSAT, depth=10 (11 cubes), sorted descending:
  [39.07, 31.80, 18.60, 2.60, 2.40, 1.70, 0.51, 0.30, 0.18, 0.05, 0.04]
```

One cube does ~99 % of the work. Branching on row-0 monotone
prefixes means each cube fixes a specific "$\deg(0) = k$" sub-case,
and the K₄-free constraint concentrates the proof work in 1–2
specific $k$ values (typically near the Caro–Wei floor, where the
boundary of the proof lives). Going deeper in the cube tree
(d = 4, 8, 14, 18) doesn't redistribute the work — the same hard
$k$ stays hard, the new sub-cubes just re-split it without
balancing.

So **naive row-0 cubing is mechanically equivalent to a structural
$\deg(0)$ case-split** (the §P8 idea in disguise). Both face the
same problem: one branch contains nearly all the proof work, and
parallelism caps at the slowest branch.

### What's missing — a real cuber

A production lookahead cuber (`march_cu` family) does what our
naive cuber doesn't:

1. **Lookahead variable selection.** For each candidate branching
   variable $v$, temporarily propagate $v=0$ and $v=1$, count BCP
   fixed-point propagations, score by "balanced shrinkage." Picks
   the variable that maximally evens out the two sub-formulas.
2. **Beyond row 0.** Considers all $\binom{n}{2}$ edge variables
   plus Sinz aux vars, not just row-0 incident edges.
3. **Recursive splitting** until every cube is heuristically "easy
   enough" (e.g. estimated solver time below threshold).
4. **Equivalence reasoning + binary-implication closure** between
   cubes (march's specialty), which our naive cuber doesn't do at
   all.

With a real cuber, the n=19 UNSAT box that currently has its 39 s
work concentrated in one cube would split into ~hundreds of cubes
of roughly equal difficulty, and 16 cores would give close to 16×
wall-clock speedup. That's the move that actually breaks the n=21
wall.

### Open follow-ups

1. **Fix `march_cu`'s build** — the bundled Makefile references
   functions in `.o` files that don't exist (suggests a missing
   source file or a Makefile typo). Patch and add `setup_march.sh`
   following the `setup_kissat.sh` pattern.
2. **Alternative: implement a Python lookahead cuber.** Less
   sophisticated than march, but tractable: ~150 LOC for variable
   probing + balanced binary-tree splitting.
3. **Use kissat's own lookahead.** KISSAT has internal lookahead
   reasoning during inprocessing; could be called in a "cube only"
   mode if we patch the source. More invasive but stays within one
   tool.

### What's salvageable today

Even with the naive cuber, there are deployment-ready wins:

- **SAT-find at large $n$**: 10–30× speedup on cluster cores. Use
  `SATCubeAndConquer` with `cube_depth=4, edge_lex=True,
  extra_args=['--sat']` as the searcher mode for any unknown box.
- **UNSAT-direction cubing is currently no better than serial**
  with our cuber, so don't deploy it for the disprover until a
  real lookahead is in place.

---

## Priority 8 — Degree case-split (the structural "nuclear option")

**Idea.** Listed in `SAT_OPTIMIZATION.md` §6.4 but never
implemented. For a candidate K₄-free graph $G$ on $n$ vertices with
$\alpha(G) \le \alpha,\ \Delta(G) \le d_{\max}$, branch on
$\deg(0) = k$ for each $k$ in the feasible range. For each branch,
the problem **factors structurally**:

- $N(0)$ is **triangle-free** on $k$ vertices (since $G$ is K₄-free,
  any triangle on three neighbors of 0 plus 0 itself would form
  $K_4$).
- $V \setminus N[0]$ is **K₄-free** on $n - 1 - k$ vertices, with
  $\alpha \le \alpha - 1$ (because adding 0 to any IS in
  $V \setminus N[0]$ gives an IS in $G$, so the IS-cap there is
  one less).

Both factors are *strictly easier* than the parent box (smaller $n$,
smaller $\alpha$, restricted graph class). One hard $(n, \alpha)$
problem becomes $O(d_{\max})$ much-easier sub-problems.

**Concrete on $(n=21, α=4)$.** The Ramsey min-degree bound is
$\deg(v) \ge n - R(4, α) = 21 - 18 = 3$, so $\deg(0) \in \{3, 4, 5,
6, 7\}$. For each $k$:

- $k = 3$: $V \setminus N[0]$ is K₄-free on 17 vertices with $α \le
  3$. *We have a complete frontier proof for n=17, α=3*. So $k=3$
  closes immediately by lookup.
- $k = 4$: 16 vertices, $α \le 3$ — boundary box already proven
  in `optimality_proofs.json`.
- $k = 5, 6, 7$: smaller $n$ at the same $α$, plus the
  triangle-free $N(0)$ which is *also* a K₄-free constraint.

**Why CP-SAT can't see this.** The decomposition is a global
structural fact about how K₄ and α interact across the
$N(0)$ vs $V \setminus N[0]$ partition. The SAT/CP encoding sees only
clauses; it cannot infer "if I fix vertex 0's neighborhood, the rest
of the problem becomes a strictly smaller version of itself." Forcing
the case-split externally exploits structure CP-SAT cannot.

**Effort.** Medium-high (~80 lines).
- For each $k$: build a sub-model that pins $\deg(0) = k$ and runs
  the full feasibility solve on the residual graph.
- Run sub-problems in parallel (one per CPU).
- Aggregate UNSAT certificates into a single proof for the parent.

**Risk.** Medium. The case-split is sound by construction (it's just
case enumeration), but the per-branch encoding requires care —
specifically, the triangle-free constraint on $N(0)$ is its own
clause family.

**Combination with P5–P7.** All compose. Each branch is itself a
SAT box that can be (a) sent to CP-SAT, (b) sent to KISSAT, (c)
solved with cube-and-conquer, or (d) further case-split. Branches
that close fast via Ramsey/Caro–Wei lookup are essentially free.

---

## Recommended order (revised)

1. **Adopt P1 + P2 + P3 immediately.** Cheap, proven, orthogonal.
2. **Add P4 as a kwarg** with a sensible default (4 workers).
3. **Add a sequential-counter cardinality encoding to `SATKissat`.**
   Low effort, expected to flip the head-to-head against CP-SAT on
   UNSAT-heavy boundary boxes.
4. **Run KISSAT (with the better encoding) on the n=21 box.** If it
   closes, document the win and move on to the next $n$.
5. **If P6 doesn't crack n=21, implement P8 (degree case-split).**
   The $k=3$ branch closes by lookup. Even if the harder branches
   tax the solver, parallelizing them across 32 cores splits the
   wall-clock budget five ways.
6. **Cube-and-conquer (P7) is the long-term move past n=23.**
   Highest infrastructure cost, highest leverage at extreme $n$,
   best treated as a follow-up project.
7. **CEGAR (P5) composes with everything.** Implement when the α
   family becomes the dominant clause count — i.e. at $α \ge 5,\ n
   \ge 22$ on the upper-frontier band.

What we are explicitly **not** doing yet:

- ❌ Global edge-count bounds (Turán + cover) — `SAT_OPTIMIZATION.md`
  §3.1 documents +5 % to +11 % regression past $n = 17$.
- ❌ Codegree ≤ α reified clauses — §3.2: net slower, $O(n^3)$ aux
  vars.
- ❌ Custom CP-SAT search params (`PORTFOLIO_WITH_QUICK_RESTART`,
  `linearization_level=2`) — §3.3: regresses several easy boxes.
- ❌ Higher `edge_lex_rows` — §8.3 / §8.4: sound but pathological.
- ❌ Joint $\lambda α + d$ optimization — `OPTIMIZATION.md` §2.2:
  strictly dominated by the sweep.
- ❌ Variant B ("fix d, minimize α") — `OPTIMIZATION.md` §3.2: roughly
  2× the CNF for no payoff.

---

## What the Anders–Brenner–Rattan complexity paper tells us

`docs/papers/The Complexity of Symmetry Breaking Beyond Lex-Leader.pdf`
(Anders, Brenner, Rattan; TU Darmstadt + Twente, 2024) is a
complexity-theoretic study of symmetry breaking predicates (SBPs).
Three results bear directly on the priorities above.

### The hardness barrier

Computing a polynomial-size **complete** SBP for the full
edge-variable symmetry of our problem is hard:

- $S_n$ acting on $n$ vertices induces a permutation action on the
  $\binom{n}{2}$ edge variables. That action is the **Johnson group
  $S_n^{(2)}$**.
- Theorem 1.2 of the paper: a polynomial-time complete-SBP algorithm
  for any proper Johnson group $S_k^{(t)}$ ($t \notin \{1, k-1\}$)
  would imply $\mathrm{GI} \in \mathrm{coNP}$ — a long-standing open
  problem.

So a complete polynomial-size symmetry break for our K₄-free model is
**complexity-theoretically barred**, not merely "we haven't found
one yet." Searching for such a break is wasted effort.

The bright side: this barrier applies only to *complete* SBPs.
Incomplete SBPs (which is what `edge_lex` is) sidestep the result
entirely. The paper repeatedly notes that incomplete lex-leader SBPs
remain the dominant practical approach.

### Validates Priority 2 (row-0 lex)

The paper's "easy" column (poly-time complete SBPs exist) includes
$S_n$ itself. Our row-0 lex break quotients out the $S_{n-1}$
stabilizer of vertex 0, which is in this easy column — that is
precisely why a tiny chain of $n-2$ Bool comparisons suffices.
Theory confirms what the ablation already showed: row-0 is the
right cheap move, and trying to break the *full* edge-variable
symmetry is structurally pointless.

### Explains the higher-row pathology (Theorem 1.5)

The paper's wreath-product composition theorem says: given complete
SBPs for groups $G$ and $H$ separately, you can combine them into
a complete SBP for $G \wr H$ by canonicalizing inside each part with
$G$'s SBP and ordering the parts with $H$'s. The exponential-weight
row-0 + row-1 + ... constraint in `sat_exact.py` is **exactly** this
composition:

- Row-0 partitions vertices into $N(0)$ vs. $V \setminus N[0]$.
- Inside each block, row-1 lex breaks
  $S_{|N(0)|} \times S_{|V \setminus N[0]|}$.
- The "ordering of parts" comes from row-0 dominance.

The 2000× slowdown at $(n=19, α=4, d=6)$ when raising
`edge_lex_rows` from 0 to 3 is **not** the constraint being unsound
— per Theorem 1.5 the composition is sound. It is the orbit wedge
collapsing to something narrow that CP-SAT's heuristic cannot
navigate. So when we eventually want higher-row gains, the path is
**structure-aware composition** (specific group decompositions where
the wreath structure aligns with where CP-SAT branches), not naive
extension of the linear inequality.

### Promotes the circulant-restricted mode (§3.5 in the SAT.md roadmap)

Section 5 of the paper proves polynomial complete SBPs exist for
**cyclic and dihedral groups**. Concretely: when we restrict the
search to circulant graphs ($\mathbb{Z}_n$ or $D_n$ acting on
vertices), the paper's theorems give a complete poly-size SBP — no
hardness barrier, no incompleteness compromise. The search collapses
to ~$n/2$ gap-indicator variables with a fully canonical encoding.

This makes the §3.5 circulant-restricted mode a strictly stronger
case than the row-lex extensions of §3.2:

- Row-lex on the full edge model: incomplete forever (provably).
- Cyclic-group complete SBP on the circulant model: poly-size,
  complete, sound.

The catch is the modeling restriction (circulants miss
non-vertex-transitive optima), which `OPTIMIZATION.md` §3.5 already
flags. But where it applies, the symmetry break is *as strong as
mathematically possible*.

### Practical takeaways

1. **Stop looking for stronger generic edge-variable SBPs.** Theorem
   1.2 says you can't get a poly-size complete one without resolving
   GI ∈ coNP. Effort is better spent elsewhere.
2. **The wreath-product framework is the principled way to extend
   row-lex.** If we ever revisit higher rows, frame the constraint
   in those terms — soundness is automatic, but tightness against
   CP-SAT's branching heuristic still has to be checked.
3. **Circulant restriction (§3.5) gets a theoretical promotion.** It
   is the one place in the roadmap where complete polynomial SBPs
   exist by theorem, making it the highest-leverage symmetry move
   per added line of code at large $n$ — assuming the optimum stays
   in the circulant family for that $n$.
4. **Negation symmetries (paper §2.1) are not directly usable.** The
   K₄-free predicate is not preserved under graph complementation, so
   literal-level symmetries don't apply to our problem.
