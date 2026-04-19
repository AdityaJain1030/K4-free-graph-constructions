# SAT Optimization — K4-free Certified Search

Record of what made `search/sat_exact.py` fast, what hurt it, and what's
still open. Everything here comes from runs against the Pareto reference
baselines (n=12 → c_log 0.7767; n=15 → c_log 0.7195) and the per-box
diagnostic in `scripts/diag_sat_exact.py`.

---

## 1. Model

CP-SAT (OR-Tools). One bool `x[i,j]` per potential edge (i < j).

**Hard clauses (always on):**

- K4-free — for every 4-subset: `sum of 6 edges ≤ 5`. C(n,4) clauses.
- Max degree — for every v: `sum(x[v,*]) ≤ d_cap`.
- Independence — for every (α+1)-subset: `sum of edges ≥ 1`.
  C(n, α+1) clauses.
- Ramsey minimum degree — `deg(v) ≥ n − R(4, α)` when known.

Two run modes: single `(α, d)` box, or scan (returns one graph per α at
the smallest feasible d).

---

## 2. What worked — kept as default

### 2.1 `ramsey_prune` (free)

`utils.ramsey.degree_bounds(n, α)` returns `(d_min, d_max)` from known
Ramsey numbers. Any box with `d_cap < d_min` is INFEASIBLE-by-Ramsey
with zero SAT cost. Also used as a per-vertex lower-degree clause
inside the model.

Trivial table entries (`R(s,1)=1`, `R(s,2)=s`) were added so α=1 and
α=2 get pruned at every n ≥ 3 without a SAT call.

### 2.2 `scan_from_ramsey_floor` (free)

In scan mode, start the d-loop at `d_min` instead of 1. Skips
cheap-to-state but expensive-to-prove INFEASIBLE verdicts for
trivially-too-small d.

### 2.3 `symmetry_mode = "edge_lex"` (big, cheap)

Among the four modes tried:

| Mode     | Cost added                          | Verdict   |
|----------|-------------------------------------|-----------|
| none     | —                                   | baseline  |
| chain    | n−1 cardinality inequalities (totalizer aux vars) | slower than baseline at small N |
| anchor   | n−1 cardinality inequalities        | mild win  |
| edge_lex | n−2 pure bool comparisons           | big win   |

Takeaway: **cardinality-based symmetry (chain, anchor) costs a totalizer
reformulation that eats the gain**. Pure bool-order lex on vertex 0's
adjacency row is ~100× faster at n=12 and 3–5× at n=13 vs. no
symmetry.

### 2.4 Row-1 edge_lex, conditioned on row 0 (big, cheap)

Extension of edge_lex to vertex 1's adjacency row, but only valid when
row 0 is tied. Encoded as a single linear inequality per adjacent
(j, j+1) pair — no aux vars, no reification:

    x[1, j] + x[0, j] ≥ x[1, j+1] + x[0, j+1]

When `x[0, j] = x[0, j+1]` (same row-0 orbit) this forces row-1 lex.
When they differ, row-0 already fixed the order and the constraint is
trivially satisfied.

Result at n=16 α=3 d=7 (INFEASIBLE boundary box):
28.3s → **0.72s** (~40× speedup).
Kept in the default config.

### 2.5 c_log-bound pruning + circulant seed (huge, free)

Observation from principle #4 above: on the Pareto scan, the witness
for the smallest feasible d per α has α(G)=α and d_max(G)=d exactly
(see proof below), so its c_log equals the "target" bound
`α·d / (n · ln d)`. Any box whose target bound is ≥ the current best
c_log cannot improve c_log — we can skip it without a SAT call.

The bound is almost free to compute and the seed graph comes from a
live `CirculantSearchFast(n, top_k=1)` call. This DFS is sub-minute at
any `n` in the practical range (we've found it well under a minute
even for `n ≈ 50`), so the scan always starts with a tight `c*`. The
c_log prune then falls out of every dominated box at zero cost.

Correctness — witness is Pareto-tight:
* at the smallest feasible d for α, `α(G) = α`: otherwise
  `(α−1, d)` would be feasible, which would make `(α, d−1)` feasible
  and contradict d being smallest.
* `d_max(G) = d`: otherwise `(α, d−1)` would be feasible.

So the witness's c_log equals α·d / (n·ln d) — the "bound" is tight.

Full ablation at N=10..23 (laptop, timeout_s=60, workers=4):

| N  | pre-opt (sym=edge_lex, ramsey+floor) | + c_log_prune + catalog seed |
|----|---------------------------------------|-------------------------------|
| 14 | 0.56 s | 0.10 s |
| 15 | 1.11 s | 0.09 s |
| 16 | 17.50 s | 0.20 s |
| 17 | 119.73 s | 0.10 s |
| 18 | 405 s (from doc §3.1) | 15.65 s |
| 19 | >600 s (many timeouts) | 1.94 s |
| 20 | — | 61.16 s |
| 21 | — | 108.54 s |
| 22 | — | 67.90 s |
| 23 | — | 333.55 s |

Every reported c_log matches or beats the pareto reference baselines
(`reference/pareto/pareto_n*.json` → `min_c_log`). For n=22
the circulant seed (c=0.6995, α=4 d=8) is strictly better than the
old reference (0.7447); the scan emits the seed and prunes the rest.

Flags controlling this (all default True, ablate cleanly):
* `c_log_prune` — skip (α, d) boxes with bound ≥ c*
* `seed_from_circulant` — seed c* from `CirculantSearchFast(n)`

The seed is also emitted as a first-class result so SAT's job is only
to *improve* on it. This matters at n=19: the actual optimal box
(α=4, d=6) times out past 30 s under SAT alone even though the
circulant search already has a witness for it — returning the seed
directly bypasses the redundant re-solve entirely.

### 2.6 Rows 0..3 edge_lex via exponential weights (big, cheap)

Extending the idea to rows 2 and 3 is valuable but needs care — the
obvious prefix-sum generalisation **over-constrains** (it implies
strictly more than lex and rules out valid graphs). Counter-example
at n=17 α=3 d=8: the reference baseline has a witness with c_log=0.6789, but the
prefix-sum form reports INFEASIBLE in 0.04 s.

The correct single-linear form uses powers of two for weights, making
the inequality behave numerically like a lex comparison:

    8·x[0, j] + 4·x[1, j] + 2·x[2, j] + x[3, j]
  ≥ 8·x[0, j+1] + 4·x[1, j+1] + 2·x[2, j+1] + x[3, j+1]

Row-k is included only for k < j (the swap σ=(j, j+1) only touches
row-k at columns j, j+1 when k < j).

Ablation at n=17 (scan, 30 s/box timeout):

| k_max (rows broken) | time |
|---------------------|------|
| 1 (rows 0, 1)       | 74.80 s |
| 2 (rows 0..2)       | 66.56 s |
| 3 (rows 0..3)       | 38.72 s |
| 4 (rows 0..4)       | 41.11 s |

k_max = 3 is the current default. k_max = 4 is slightly slower
(extra propagator weight exceeds the symmetry gain). All four values
produce the same c_log; the differences are purely solve time.

### 2.6 K4 and independence as pure disjunctions (small, free)

The K4 constraint `x1 + x2 + … + x6 ≤ 5` on six Boolean variables is
equivalent to the single 6-literal clause
`¬x1 ∨ ¬x2 ∨ … ∨ ¬x6` (at least one edge absent). Same shape for
the independence clause `sum ≥ 1` ↔ `x1 ∨ … ∨ xm`. Both now go through
`model.add_bool_or(...)` rather than the linear form, so CP-SAT treats
them as clauses in the SAT core directly instead of routing through
its linear-inequality reformulation.

Clean A/B at n=17 (scan, 30 s/box timeout, 4 workers):

| K4 encoding | time |
|-------------|------|
| linear `sum ≤ 5`       | 37.80 s |
| `add_bool_or(¬x_i)`    | 34.52 s |

~9 % faster with no downside — kept as default.

---

## 3. What didn't work — rejected

### 3.1 Global edge-count bounds

Added two linear cuts on `sum(all_edges)`:
- Turán upper: `≤ ⌊n²/3⌋` (max edges in K4-free).
- Cover lower: `≥ ⌈C(n, α+1) / C(n-2, α-1)⌉` (fractional cover of
  forbidden independent sets).

Result:

| N  | v1 (no bounds) | v3 (bounds on) | Δ    |
|----|----------------|----------------|------|
| 16 | 110.3s         | 92.8s          | -16% |
| 17 | 196.6s         | 219.0s         | +11% |
| 18 | 405.9s         | 425.3s         | +5%  |

Helps n=16 (cracks α=3 d=7 from 28s → 11.7s), hurts n≥17. One
constraint spanning C(n,2) vars is cheap to state but the propagator
overhead on FEASIBLE solves at larger N outweighs the pruning.

**Net finding: global-cardinality constraints scale badly with N.**

### 3.2 Codegree ≤ α (structural but heavy)

For every edge (i, j), `|N(i) ∩ N(j)| ≤ α` (common neighbours form an
independent set — otherwise K4). Encoded with O(n³) auxiliary bool
vars + channeling + `only_enforce_if`.

Result: net slower everywhere. At n=18: 405.9s → 465.4s (+15%). The
reified constraints cost more than the long-resolution chains through
the K4 clauses they were meant to short-circuit.

**Net finding: no reified / channeled encodings.** CP-SAT overhead
per auxiliary bool grows faster than the added reasoning pays off.

### 3.3 PORTFOLIO_WITH_QUICK_RESTART_SEARCH + linearization_level=2

Intent: force CP-SAT's 4 workers into diverse strategies and turn up
LP cuts to help prove tight INFEASIBLE at the boundary.

Result: cracked n=16 α=3 d=7 (28s → 14.9s) but regressed several
previously-easy boxes (e.g. n=18 α=5 d=3 went 0.87s → 28s TIMEOUT).
Net slower than baseline. The default CP-SAT portfolio is tuned and
overriding it costs more than the extra diversity earns.

---

## 4. The stubborn boxes

Four boxes still TIMEOUT at 30s (and don't finish at 300s either):

- n=16 α=5 d=3
- n=17 α=4 d=5
- n=17 α=5 d=3
- n=18 α=4 d=5

All are INFEASIBLE proofs just below the feasibility boundary. They
**do not affect the reported c_log** — the scan moves on to d+1 on
timeout, and at d+1 a FEASIBLE witness is found in under 1s. Even if
the stubborn boxes were feasible, their c_log is worse than the
current best for that n. They are purely certification of "this d is
tight".

Row-1 edge_lex cracked n=16 α=3 d=7 but didn't touch these four —
they have different hard structure (small d, moderate α) where row
symmetry isn't the binding cost.

---

## 5. Winning configuration (current default)

```python
SATExact(
    symmetry_mode="edge_lex",            # rows 0..3 lex via exponential weights
    ramsey_prune=True,                   # degree bounds from known R(s,t)
    scan_from_ramsey_floor=True,         # start d at Ramsey d_min
    c_log_prune=True,                    # skip (α, d) with bound ≥ c*
    seed_from_circulant=True,            # seed c* from CirculantSearchFast(n)
    # K4 and independence are encoded as add_bool_or clauses by default
)
```

Opt-in flags (off by default; kept around for the server or ablations):

- `circulant_hints=True` — seed CP-SAT with the best K4-free circulant
  for n (from `CirculantSearchFast`), cyclically rotated so row 0 is
  lex-largest. Neutral at n=17 (66 s with, 66 s without) on the
  laptop; left in for large-N FEASIBLE boxes where warm-start can
  matter.
- `branch_on_v0=True` — adds a FIXED_SEARCH decision strategy on the
  vertex-0 row. Only one portfolio worker uses it, so the rest stay
  free. Complements edge_lex, which already pins row 0's ordering.
- `parallel_alpha=True`, `parallel_alpha_tracks=N` — dispatches each
  α-track to its own worker process. Server-only: each track keeps
  its own CP-SAT model, so memory scales linearly in the number of
  α values. Intended for a box with ~32 cores / 200 GB. Do not
  enable on the laptop.

All accelerators are flags on the class so they ablate cleanly via
`scripts/ablate_sat_exact.py`. Raw ablation numbers live in
`logs/sat_exact_ablation.json`.

---

## 6. Open ideas for larger N

Not yet tried; ranked by expected payoff at n ≥ 20.

### 6.1 Incremental solve across the d-scan (medium effort)

Build K4 + independence + symmetry clauses once per `(n, α)`. Use
CP-SAT assumptions to toggle the degree cap across the d-loop. Saves
the `C(n,4)` model-build cost across ~n d-values per α. Cost scales
as n⁵; payoff grows with N.

### 6.2 Row-2 edge_lex (cheap)

Extend the row-1 technique to vertex 2, conditioned on rows 0 and 1
both being tied. Each added row cuts a factorial chunk of the
relabeling group. Expected to compound the row-1 win at larger N
where (n−1)! is astronomical.

### 6.3 Circulant-restricted mode (high variance)

Add a flag forcing `x[i, j] = x[(i+k) mod n, (j+k) mod n]`. Reduces
C(n,2) bool vars to ~n/2 gap indicators. Many known K4-free extremals
are circulants (Paley, certain Cayley graphs). If the optimum is
circulant at n ≥ 20, this is 100× speedup; otherwise we get a weaker
bound but at negligible cost. Low-risk ablation.

### 6.4 Degree decomposition (structural, nuclear)

Case-split on `deg(0) = k`. `N(0)` is then triangle-free on k vertices
with α ≤ α_cap; the rest is K4-free on n−1−k vertices with
α ≤ α_cap−1. One hard box becomes O(n) easier sub-boxes. Exactly the
move that cracks boundary INFEASIBLE proofs when symmetry breaks
can't reach them.

---

## 7. Principles learned

1. **Local beats global.** Per-vertex constraints (O(n) each) scale;
   global cardinality cuts (one constraint over C(n,2) vars) don't.
2. **Bool comparisons beat totalizers.** `x[i,j] ≥ x[i,k]` is free;
   `deg(i) ≥ deg(j)` is not.
3. **Reification is expensive.** Every `only_enforce_if` and every aux
   bool with channeling is a cost the propagator pays every decision.
   The break-even for reified structure is high and we rarely cleared
   it.
4. **The headline metric and the hard proofs are decoupled.** Boxes
   that take 300s to certify INFEASIBLE are often irrelevant to
   c_log — their feasible counterparts at d+1 are instant and give
   the same bound. Don't spend budget on certification the answer
   doesn't need.
5. **Correctness is cheap; speed is earned one constraint at a
   time.** Every accelerator in `sat_exact.py` paid rent against the
   Pareto reference baselines before being kept.
