# SAT / ILP Solver for K₄-free Graph Optimization

> The full solver code and all results live in `SAT_old/`. This folder is the
> clean entry point — read this first, then navigate to `SAT_old/` to run or
> inspect anything.

---

## The problem

We want to find K₄-free graphs on N vertices that minimize the constant

```
c = α(G) · d_max / (N · ln(d_max))
```

where α(G) is the independence number and d_max is the maximum degree. A small
c is a near-counterexample to the conjecture that every K₄-free graph satisfies
α(G) ≥ c₀ · N · log(d) / d for some universal c₀ > 0.

For fixed N, we sweep over (α_target, d_max) pairs and ask for each one:
**does a K₄-free graph exist on N vertices with α ≤ α_target and max degree
≤ d_max?** The boundary between FEASIBLE and INFEASIBLE pairs traces out the
Pareto frontier, and the minimum c achieved on that frontier is recorded.

---

## Boolean variables

One binary variable per potential edge:

```
e_{ij} ∈ {0, 1}    for all 0 ≤ i < j < N
```

Total: C(N, 2) variables. A satisfying assignment is an adjacency matrix.

---

## Clauses

### 1. K₄-free  —  C(N, 4) clauses, 6 literals each

For every 4-tuple of vertices {a, b, c, d}, forbid all 6 edges being present:

```
¬e_ab ∨ ¬e_ac ∨ ¬e_ad ∨ ¬e_bc ∨ ¬e_bd ∨ ¬e_cd
```

Equivalently: `e_ab + e_ac + e_ad + e_bc + e_bd + e_cd ≤ 5`.
At N=20 this is 4,845 clauses. At N=30 it is 27,405. Each is cheap — just
one 6-literal OR.

### 2. Independence number  —  C(N, α+1) clauses (direct mode)

To enforce α(G) ≤ k, every (k+1)-subset of vertices must contain at least
one edge (otherwise it would be an independent set of size k+1):

```
e_{v0v1} ∨ e_{v0v2} ∨ … ∨ e_{v(k)v(k+1)}    for every (k+1)-subset
```

Each clause has C(k+1, 2) literals. There are C(N, k+1) such clauses.
This is the expensive part: C(30, 6) = 593,775 clauses with 15 literals each.

### 3. Degree bounds  —  cardinality constraints

For each vertex i, the sum of incident edge variables is bounded:

```
Σ_{j≠i} e_{ij} ≤ d_max        (upper bound)
Σ_{j≠i} e_{ij} ≥ d_min        (lower bound, from Ramsey theory — see below)
```

These are cardinality constraints, not unit clauses. CP-SAT encodes them
internally using a totalizer or BDD, introducing auxiliary variables so that
propagation is efficient without enumerating all C(N-1, d+1) subsets.

### 4. Symmetry breaking  —  N−1 cardinality constraints

Vertices are ordered by non-increasing degree:

```
deg(0) ≥ deg(1) ≥ … ≥ deg(N−1)
```

This eliminates all isomorphic relabellings of the vertex set, reducing the
search space by up to N! without changing the set of achievable (α, d) pairs.

---

## Two solver modes

The solver switches automatically based on C(N, α+1):

### Direct mode  (C(N, α+1) ≤ 5,000,000)

All independence clauses are added to the model upfront. The solver runs once
and returns FEASIBLE or INFEASIBLE.

### Lazy cutting-planes mode  (C(N, α+1) > 5,000,000)

Independence constraints are generated on demand:

```
repeat:
  1. Solve the model with only K₄-free + degree constraints (+ any cuts so far)
  2. If INFEASIBLE → done, no such graph exists
  3. If FEASIBLE   → compute α of the returned graph exactly (branch-and-bound)
  4. If α ≤ target → done, graph found
  5. Otherwise     → let S be the violating independent set of size α
                     add clause: (e_{uv} for all u<v in S must have ≥ 1 edge)
                     go to 1
```

Each cut strictly shrinks the feasible region, so the loop terminates.
In practice 5–20 iterations suffice because each cut eliminates a large
chunk of the space.

---

## Ramsey-theoretic degree bounds (pre-solve pruning)

Before building any model, the solver derives tight degree bounds from known
Ramsey numbers, which can prove infeasibility in O(1) without calling the SAT
solver at all.

For a K₄-free graph G with α(G) ≤ t and a vertex v:

| Neighbourhood | Property | Bound |
|---|---|---|
| N(v) | triangle-free (K₃-free), α ≤ t | `\|N(v)\| < R(3, t+1)` → **d ≤ R(3,t+1)−1** |
| V \ N(v) \ {v} | K₄-free, α ≤ t−1 | `\|V\N(v)\| < R(4, t)` → **d ≥ N−R(4,t)** |

If the resulting interval [d_min, d_max] is empty, the solver returns
INFEASIBLE immediately. This prunes large regions of the (N, α, d) parameter
space before any clause is written.

Ramsey numbers used:

```
R(3,3)=6   R(3,4)=9   R(3,5)=14  R(3,6)=18  R(3,7)=23  R(3,8)=28  R(3,9)=36
R(4,3)=9   R(4,4)=18  R(4,5)=25
```

---

## Warm-start hint

For N > 15, rather than starting from an empty graph, the solver is given a
hint: a Paley-like circulant on N vertices (vertex i connects to j when i−j
is a quadratic residue mod the largest prime p ≤ N). This is always K₄-free
for primes p ≡ 1 (mod 4) and gives CP-SAT a dense, structured starting point
that reduces time-to-first-solution significantly.

---

## Output: Pareto frontier

For each N, the outer loop (`run_production.py`) sweeps over all feasible
(α_target, d_max) pairs and records FEASIBLE / INFEASIBLE / TIMEOUT for each.
The result is stored as `pareto_n{N}.json` in `SAT_old/k4free_ilp/results/`.

The Pareto frontier is the set of (α, d) pairs where:
- (α, d) is FEASIBLE
- (α−1, d) and (α, d−1) are both INFEASIBLE

The minimum c on this frontier is:

```
c_min = min over Pareto pairs of  α · d / (N · ln(d))
```

Results are verified: every returned graph is checked for K₄-freeness and
correct α before being accepted.

---

## Degree-pinning: why fixing d makes SAT tractable

The base SAT formulation has C(N,2) free edge variables with degree only
bounded above. Propagation is weak: knowing one edge exists tells you almost
nothing about other edges. This is why the unconstrained solver stalls at
N≈35.

**Pinning d to a fixed value D** (requiring every degree to equal exactly D,
or {D, D+1} for near-regular) transforms the problem fundamentally:

- Every vertex has exactly D neighbours. Adding one edge forces the degrees of
  both endpoints up by 1, which immediately constrains what other edges can
  exist around those endpoints. CP-SAT propagates this cascade across the whole
  graph — one branching decision fans out into hundreds of forced assignments.
- The feasible region shrinks from "any graph with d ≤ d_max" (exponentially
  large) to "graphs where every vertex has degree exactly D" (much smaller and
  more constrained). For a D-regular graph on N vertices, the number of edges
  is fixed at N·D/2 — there is no slack in the edge count at all.
- The independence clauses become far more powerful. With free degrees, a
  clause saying "this (k+1)-subset must contain an edge" might be satisfiable
  many ways. With degree pinned, most of those ways are already ruled out by
  degree propagation, so each clause eliminates a much larger fraction of the
  remaining search space.

In practice, pinning D reduces solver time from hours to seconds for the same
N and α — the difference between feasible and infeasible at large N.

### The D-sweep strategy (SAT_old/regular_sat)

Rather than a 2D sweep over (α, d_max), `regular_sat` does a **linear scan**:
iterate D upward from the Ramsey lower bound and call the degree-pinned solver
for each D. The first feasible D terminates the search.

This works because near-regular graphs with consecutive base degrees D and D+1
have non-overlapping edge counts (~N·D/2 vs ~N·(D+1)/2, differing by N/2).
So the first feasible D is provably minimum-edge — no backtracking needed.

Number of solver calls: at most d_hi − d_lo + 1 ≈ 10–20, versus hundreds for
the full Pareto sweep.

---

## Assumptions and their status

The `regular_sat` approach bakes in two structural assumptions. Both are
**empirically supported but unproven** — they are heuristics that make the
search cheaper, not theorems that guarantee correctness.

### 1. Near-regularity of optimal graphs

The code enforces deg(v) ∈ {D, D+1} based on the idea that the minimum-c
graph should be near-regular. This is observed to hold for all SAT-verified
optima at N ≤ 22, and is plausible because irregular graphs waste edges
(a high-degree vertex contributes disproportionately to d_max without
proportionally reducing α). However:

- **There is no proof** that the true minimum-c graph over all K₄-free graphs
  is near-regular for all N.
- Restricting to near-regular graphs means the solver can return INFEASIBLE at
  a given (N, α, D) even though a non-regular graph achieving that (α, d_max)
  exists. The result is a valid near-regular graph or a proof that no
  near-regular one exists — not a proof about all graphs.

To run without this assumption, use `SAT_old/k4free_ilp/ilp_solver.py`
directly with `max_degree=d` and no lower-bound constraint.

### 2. α = Ramsey floor

The CLI automatically sets α = R(4, k) − 1, the minimum α achievable by any
K₄-free graph of that size. The motivation is that smaller α gives smaller c,
so the Ramsey floor is the hardest and most interesting case.

However:

- **This is not proven to give the minimum c.** It is possible (and has been
  observed at some N) that a graph with α slightly above the Ramsey floor but
  much lower d achieves a smaller c than the Ramsey-floor graph.
- Setting α = Ramsey floor explores one slice of the (α, d) space, not the
  full Pareto frontier.

To run a full sweep over all α values, use `run_production.py` in
`SAT_old/k4free_ilp/`, which queries every feasible (α, d_max) pair.

---

## Complexity summary

| N | K₄ clauses | Indep. clauses (α=5) | Regime |
|---|---|---|---|
| 20 | 4,845 | C(20,6)=38,760 | direct |
| 25 | 12,650 | C(25,6)=177,100 | direct |
| 30 | 27,405 | C(30,6)=593,775 | direct |
| 35 | 52,360 | C(35,6)=1,623,160 | direct |
| 40 | 91,390 | C(40,6)=3,838,380 | direct/lazy boundary |
| 50 | 230,300 | C(50,6)≈15.9M | lazy |

The solver runs 8 parallel workers (CP-SAT's portfolio search) with a
configurable time limit (default 300–600 s per query).

Degree-pinned runs are typically 10–100× faster than unconstrained runs at the
same N, making N=50–80 feasible under the near-regularity assumption where the
unconstrained solver times out.
