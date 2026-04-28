# Optimization-mode SAT for K₄-free graphs

Companion to `SAT.md`. The naive solver (`search/SAT/sat.py`) is a
**feasibility oracle**: given a box $(n, \alpha, d)$, it returns
`SAT` / `UNSAT` / `TIMED_OUT`. This file records the brainstorm and
benchmark on whether reframing as **optimization** could be faster.

---

## 1. Feasibility vs. optimization — when each wins

CP-SAT is an ILP/CDCL hybrid built around branch-and-bound — it is
*literally designed* for minimization. So in principle the
optimization formulation has three real advantages over a feasibility
sweep:

1. **Cumulative learning.** A box-sweep over $(\alpha, d)$ pairs
   builds and tears down a fresh model per box; the solver discards
   every learned clause, no-good, and conflict cut at each boundary.
   An optimization run keeps all of it.
2. **One presolve.** Construction + presolve takes $10$ ms–$1$ s per
   box. A sweep of, say, 30 boxes pays that overhead 30 times;
   optimization pays once.
3. **Active dual bounds.** Once CP-SAT finds a feasible solution with
   objective $c^\star$, the constraint "objective $\le c^\star - 1$"
   immediately prunes huge regions. A sweep approximates this
   manually by walking $d$ downward, but each step is still a full
   re-solve.

But there are three costs:

1. **The natural objective $c_{\log} = \alpha \cdot d / (n \ln d)$ is
   nonlinear.** CP-SAT can't optimize it directly; you're forced to
   optimize a **proxy** (minimize edges, minimize $d_{\max}$ at fixed
   α, minimize α at fixed $d$). Each proxy can disagree with $c_{\log}$
   at the optimum.
2. **Optimization implicitly *proves* optimality.** Finding $\alpha=3$
   in optimization mode is fine; proving no $\alpha=2$ graph exists is
   a full UNSAT certificate at $\alpha=2$. Optimization cost ≈
   SAT-find + UNSAT-prove. Feasibility on the *correct* box only needs
   SAT-find. If you already conjecture the optimum, sweep is pure SAT
   — strictly cheaper.
3. **You lose box-specific tightenings.** With $\alpha$ as a variable
   rather than a constant, you can't pin-an-IS or apply Ramsey degree
   pruning — both depend on knowing $\alpha$ up front.

---

## 2. The joint formulation

Implemented in `search/SAT/sat_joint.py`. Minimizes
$\lambda \cdot \alpha(G) + \Delta(G)$ jointly with $\lambda$ defaulting
to $n$ (so $\alpha$ dominates the objective).

### 2.1 Encoding

Variables on top of the naive model:

- $A \in [0, \alpha_{\max}]$ — integer var equal to $\alpha(G)$.
- $D \in [0, n-1]$ — integer var equal to $\Delta(G)$.

Constraint additions:

- **Hard cap $\alpha(G) \le \alpha_{\max}$** via the original C2
  family on $(\alpha_{\max}+1)$-subsets.
- **Big-M lower bounds on $A$**: for each $k = 1, \ldots, \alpha_{\max}$
  and each subset $T$ of size $k$,
  $$
  A + k \cdot \sum_{\{i,j\} \subseteq T} x_{ij} \;\ge\; k.
  $$
  If $T$ is independent ($\sum = 0$) this forces $A \ge k$. Combined
  with the hard cap, $A = \alpha(G)$ exactly.
- **Per-vertex degree** $\sum_{u \ne v} x_{vu} \le D$.

Objective: $\min \, \lambda \cdot A + D$.

### 2.2 Benchmark

`experiments/SAT/bench_joint_vs_sweep.py`. Both modes given the same
$\alpha_{\max} = \max(4, \lceil n^{3/5} \rceil)$ budget; sweep walks
$(\alpha, d)$ in $c_{\log}$-ascending order with 3 s per box; joint
runs in single 60 s call.

| $n$ | Mode  | $\alpha$ | $d$ | $c_{\log}$ | Wall  | Status                  |
|----:|-------|---------:|----:|-----------:|------:|-------------------------|
|  10 | sweep |        3 |   4 |     0.866  | **1.3 s** | found, proven       |
|  10 | joint |        3 |   4 |     0.866  |   1.8 s   | OPTIMAL (proven)    |
|  13 | sweep |        3 |   6 |     0.773  | **5.7 s** | found, proven       |
|  13 | joint |        3 |   6 |     0.773  |  60 s     | FEASIBLE (timeout)  |
|  15 | sweep |        3 |   7 |     0.720  | **9.2 s** | found, proven       |
|  15 | joint |        3 |   7 |     0.720  |  60 s     | FEASIBLE (timeout)  |
|  17 | sweep |        3 |   8 |     0.679  | **19 s**  | found (Paley-17)    |
|  17 | joint |        3 |   8 |     0.679  |  60 s     | FEASIBLE (timeout)  |

**Verdict.** Sweep wins 3–10×. Both modes converge on the same
configuration — the Paley-family optimum $(\alpha = 3, d \approx n/2)$
— but joint times out trying to *prove* optimality, exactly the cost
flagged in §1. In $c_{\log}$-ordered sweep mode, that boundary closure
happens implicitly via the previous UNSAT verdicts; joint has to
re-derive it from scratch in objective space.

---

## 3. The natural reframe — fix one, minimize the other

### 3.1 Variant A — given $(n, \alpha)$, minimize $d_{\max}$

CNF additions over the feasibility model:

- $+1$ integer variable $D \in [0, n-1]$
- The fixed degree clauses become $\sum_u x_{vu} \le D$ — same $n$
  constraints, $d$ is now a variable
- Linear objective: $\min D$

**Net cost: essentially zero.** Same K₄ family $\binom{n}{4}$, same
α family $\binom{n}{\alpha+1}$, one extra int var, $n$ inequalities
re-shaped. Should be cheaper than the sweep because cumulative
learning + single presolve actually pays off — the optimization is
over a single integer with very tight bounds.

### 3.2 Variant B — given $(n, d)$, minimize $\alpha$

CNF additions:

- $+1$ integer variable $A \in [0, A_{\max}]$ (need a cap to keep
  CNF finite)
- α upper-cap family $\binom{n}{A_{\max}+1}$ (same as feasibility)
- α lower-bound family for each $k = 1, \ldots, A_{\max}$:
  $\sum_{k=1}^{A_{\max}} \binom{n}{k}$ extra constraints — adds an
  entire binomial layered family on top of the cap
- Linear objective: $\min A$

**Net cost: roughly 2× the CNF** of feasibility for the same
$A_{\max}$. The α-LB family is unavoidable: α is a max-over-
exponentially-many-subsets quantity, and the only way to encode
"$A \ge \alpha(G)$" in pure ILP is one big-M constraint per (small)
subset. Exactly the bloat in `SATJoint`, and exactly why the joint
version timed out.

### 3.3 The asymmetry

- $d_{\max}$ is a **max over $n$ linear sums**: encode with $n$
  inequalities + 1 var. Cheap.
- $\alpha(G)$ is a **max over $2^n$ subsets**: encode with
  $\sum_k \binom{n}{k}$ inequalities + 1 var. Expensive.

| Reframe                       | CNF size         | Predicted speed vs sweep |
|-------------------------------|------------------|--------------------------|
| Fix α, minimize $d$ (Var. A) | ≈ feasibility    | **Faster** (2–3×)        |
| Fix $d$, minimize α (Var. B) | ≈ 2× feasibility | Slower                   |

Variant A is the right reframe and is exactly what `sat_regular.py`
already targets in its phase-2.

---

## 4. Pruning the α-clause family

The α family $\binom{n}{\alpha+1}$ dominates the model and is the
practical scaling bottleneck (see SAT.md §2.4). Three levels of
pruning, in increasing power.

### 4.1 Solver-internal (free)

CP-SAT already does this. Once any edge $x_{ij} = 1$ is forced during
search, every α-clause containing $\{i,j\}$ is **immediately satisfied**
and can be skipped. Even though we encode $\binom{n}{\alpha+1}$
clauses, the solver only actively reasons about the small fraction
that aren't yet trivially closed. This is what CP-SAT's
two-watched-literal scheme buys you. No code changes needed.

### 4.2 Cross-α subsumption (sweep over α)

Going from $\alpha = k$ to $\alpha = k+1$ in a sweep:

> **The $\alpha = k$ model strictly implies the $\alpha = k+1$ model.**
> Any $(k+2)$-subset contains a $(k+1)$-subset; if that smaller subset
> has an edge (α=k clause), the larger one does too. So the α=k+1
> clause family is **logically redundant** given the α=k clauses.

Practical consequence: if you've already proven UNSAT at $\alpha = k$,
the verdict at every $\alpha < k$ is also UNSAT (no need to re-solve).
Conversely, a SAT witness at $\alpha = k$ is automatically a witness
at all larger $\alpha$. Most of the sweep is *implicit*. Only invest
solve-time at the **boundary** where the verdict flips.

### 4.3 CEGAR / lazy α-clause generation (the big win)

Within a single α value, drop the α family from the upfront model
entirely and add clauses on demand:

```
1. Build model with K4 + degree only (no α clauses).
2. Solve. Get a candidate G.
3. Compute α(G) by an independent oracle (e.g. utils.alpha_nx).
4. If α(G) ≤ α: done, return G as SAT witness.
5. Else: extract a witness independent (α+1)-subset T from the oracle.
        Add ONE clause:  Σ_{e ⊂ T} x_e ≥ 1.
        Goto 2.
```

Classic counterexample-guided abstraction refinement (CEGAR).
Empirically on similar combinatorial-search problems, you converge
after **10–100 separations** even when the full clause family is
$10^4$–$10^7$. So the effective α-clause count drops from
$\binom{n}{\alpha+1}$ down to a small constant times the boundary
depth of the box.

CEGAR also gets *more* effective as α grows: the upfront family
blows up binomially, but the number of separations needed seems to
grow much more slowly (rough heuristic: $O(\alpha)$ to $O(\alpha^2)$
in practice). At the upper-frontier $\alpha \approx n^{3/5}$ — exactly
where the naive encoding breaks at $n \approx 30$ — CEGAR is the
difference between $10^7$ clauses and a few hundred.

### 4.4 Ranking

| Pruning              | Where it lives    | Effort           | Speedup                    |
|----------------------|-------------------|------------------|----------------------------|
| Solver-internal      | CP-SAT internals  | free             | 2–5× (already on)          |
| Cross-α subsumption  | sweep wrapper     | trivial bookkeeping | up to ~α× (skip verdicts) |
| **CEGAR α-separation** | model construction | ~30 lines      | **10–1000× at large α**    |

CEGAR is the technique that lets the naive solver scale past
$n \approx 25$ without buying any of the SAT.md §3 algebraic
accelerators. Listed as §3.6 in the SAT.md roadmap; honestly it
should probably be §3.1 — it's the cheapest to implement and gives
the biggest reach.

---

## 5. Recommended path forward

1. **Build `SATMinDeg(n, alpha)`** implementing Variant A (fix α,
   minimize $d_{\max}$). Predicted to beat the sweep 2–3× on hard
   per-row queries while reusing the same K₄ + α + degree clause
   structure.
2. **Promote CEGAR to §3.1.** Implement lazy α-clause separation as
   the first accelerator — applies to both feasibility and Variant A.
   Combined, these should push the naive ceiling from $n \approx 22$
   up to $n \approx 30$ without algebraic structure.
3. **Don't bother with joint $\lambda \cdot \alpha + d$.** The
   benchmark in §2.2 shows it's strictly dominated by the sweep on
   this objective.
