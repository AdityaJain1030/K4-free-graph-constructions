# `SATMinDeg(n, α)` — fix $(n, \alpha)$, minimize $\Delta(G)$

Variant A from `OPTIMIZATION.md` §3.1. Where the joint
$\lambda \alpha + D$ formulation lost to the feasibility sweep
(it had to *prove* α-tightness, paying a full UNSAT certificate at
$\alpha - 1$), MinDeg keeps α **fixed** and optimizes a single integer
over a tight range — exactly the regime where CP-SAT's cumulative
learning, one-shot presolve, and active dual bounds pay off cleanly.

The asymmetry behind why this is the *cheap* reframe: $D$ is a max
over $n$ linear sums (one inequality per vertex), so promoting
$d_{\max}$ to a variable adds **1 integer var** and **0 new clauses**.
The existing degree family
$\sum_{u \ne v} x_{vu} \le d_{\max}$ becomes
$\sum_{u \ne v} x_{vu} \le D$ — same shape, $d_{\max}$ swapped for an
int var. Compare with Variant B (fix $d$, minimize α), which would
require a big-M family of size $\sum_{k=1}^{A_{\max}} \binom{n}{k}$ on
top of the existing model.

---

## 1. Decision variables

For each unordered pair $\{i, j\} \subseteq V$ with $i < j$, a Boolean
edge indicator

$$
x_{ij} \in \{0, 1\}, \qquad x_{ij} = 1 \iff \{i, j\} \in E,
$$

unchanged from the feasibility model — $\binom{n}{2}$ Booleans total.

Plus one new integer variable

$$
D \in [D_{\text{lo}},\ D_{\text{hi}}] \subset \mathbb{Z},
$$

bounding the maximum degree from above.

**Bounds.**

- $D_{\text{lo}} \;=\; \max\!\left(0,\ \left\lceil \tfrac{n}{\alpha} \right\rceil - 1\right).$
  By Caro–Wei,
  $\alpha(G) \ge \sum_{v} 1/(\deg(v)+1) \ge n/(\Delta(G) + 1)$, so any
  graph with $\alpha(G) \le \alpha$ satisfies $\Delta(G) \ge n/\alpha - 1$.
  Injecting this as the integer-variable lower bound is sound (no
  feasible witness is excluded) and saves the solver from rederiving
  it during search. The same Caro–Wei argument that prunes feasibility
  boxes outright (`_ramsey_prune` rule 3) is now a model-time
  tightening rather than an outer guard.

- $D_{\text{hi}} \;=\; n - 1$ default; caller may pass a tighter cap
  (e.g. *"we already have a witness at $d^\star$ — prove $\Delta < d^\star$
  for the next row"*).

If the caller supplies $D_{\text{hi}} < D_{\text{lo}}$ the box is
trivially infeasible without invoking the solver.

---

## 2. Constraints

| Family       | Form                                                                              | Count                  | vs feasibility            |
|--------------|-----------------------------------------------------------------------------------|-----------------------:|---------------------------|
| (C1) K₄-free | $\sum_{e \subset S} x_e \le 5\ \forall S \in \binom{V}{4}$                        | $\binom{n}{4}$         | none                      |
| (C2) α-bound | $\sum_{e \subset T} x_e \ge 1\ \forall T \in \binom{V}{\alpha + 1}$               | $\binom{n}{\alpha+1}$  | none                      |
| (C3′) Degree | $\sum_{u \ne v} x_{vu} \le D\ \forall v \in V$                                    | $n$                    | $d_{\max} \to D$ (var)    |

Total CNF size ≈ feasibility model + 1 integer variable. No big-M
family. The K₄ family and the α family are *unchanged* — they don't
involve degree at all, so every clause type from the feasibility
encoding is reused verbatim.

---

## 3. Objective

$$
\min D.
$$

At optimum, $D = \Delta(G^\star)$ exactly. The solver pushes $D$ down
until further reductions become incompatible with (C1) + (C2): no
graph can be K₄-free, $\alpha$-capped, *and* have any smaller maximum
degree. Optimality of $D$ therefore certifies optimality of
$\Delta(G^\star)$ over the K₄-free, α-capped feasible region.

---

## 4. Pre-solve pruning

The existing `_ramsey_prune(n, α, d_max)` rules carry over, but with
the $d$-dependent rules dropped or repurposed:

| Rule                | Status in MinDeg                                                |
|---------------------|-----------------------------------------------------------------|
| α = 0, n ≥ 1        | ✅ kept — infeasibility is independent of $d$                    |
| $n \ge R(4,\alpha+1)$ UB | ✅ kept — Ramsey wall on $(n, \alpha)$, no $d$ dependence    |
| Caro–Wei            | ❌ no longer a prune — promoted to $D_{\text{lo}}$               |
| $d = 0$             | ❌ no longer a prune — $D$ is variable, absorbed by $D_{\text{lo}} \ge 1$ when $\alpha < n$ |

A small `_ramsey_prune_no_d(n, α)` companion is sufficient (or just
calling the existing function with a sentinel $d_{\max} = n-1$ that
guarantees rules 2 and 3 don't fire).

---

## 5. Status mapping

| CP-SAT status | Verdict      | Witness   | Meaning                                                                                                       |
|---------------|--------------|-----------|---------------------------------------------------------------------------------------------------------------|
| `OPTIMAL`     | `SAT`        | best $G$  | $\Delta(G^\star) = D^\star$ is the **proven minimum** at this $(n, \alpha)$.                                  |
| `FEASIBLE`    | `SAT`        | best $G$  | Witness with $D = v$ found, but optimality not proven inside budget.                                          |
| `INFEASIBLE`  | `UNSAT`      | empty     | **No K₄-free graph on $n$ vertices has $\alpha(G) \le \alpha$ at any $d$** — entire row $(n, \alpha)$ is empty. |
| `UNKNOWN`     | `TIMED_OUT`  | empty     | No feasible solution found in budget; no information.                                                         |

INFEASIBLE is a strictly stronger signal here than in feasibility
mode: a single solve closes the whole $(n, \alpha)$ row, equivalent to
a sweep that reported UNSAT at every $d$ from $D_{\text{lo}}$ to $n-1$.

---

## 6. Edge cases

- $\alpha + 1 > n$: (C2) family is empty, the bound is vacuous, and
  $G = \overline{K_n}$ (empty graph, $\Delta = 0$) is the trivial
  optimum. Return early without invoking the solver.
- $\alpha = 0,\ n \ge 1$: pruned as infeasible.
- $D_{\text{lo}} > D_{\text{hi}}$: caller asked for an impossible
  $d$-range; return UNSAT without invoking the solver.

---

## 7. Comparison to the feasibility sweep

A box-sweep at fixed $(n, \alpha)$ walks $d$ from $D_{\text{lo}}$
upward and calls `SAT(n, α, d)` per box, discarding all learned
clauses at each boundary. MinDeg keeps the same model in memory and
optimizes once. The three benefits flagged in `OPTIMIZATION.md` §1
apply directly:

1. **Cumulative learning.** Conflict cuts and no-goods derived at
   $D = v$ remain valid at $D = v - 1$ (any feasible solution at
   smaller $D$ is also feasible at larger $D$). The sweep loses all of
   them.
2. **One presolve.** A sweep over a $\sim 5$-wide $d$-range pays
   construction + presolve five times; MinDeg pays it once.
3. **Active dual bounds.** Once CP-SAT finds a feasible solution with
   objective $D = v$, the constraint $D \le v - 1$ is active for the
   rest of the search and prunes whole regions. The sweep approximates
   this manually by walking $d$ downward, but each step is a full
   re-solve from scratch.

Crucially, MinDeg avoids the α-proof tax that killed the joint
formulation: α is **fixed**, so we never need to certify "no graph at
$\alpha - 1$". The optimization happens over a single integer in a
narrow range.

**Predicted speedup over sweep: 2–3×** on hard per-row queries, with
the gap widening as the $d$-range gets wider. Anti-prediction: on
trivial rows (sweep finds SAT at the first $d \approx D_{\text{lo}}$
in milliseconds) the optimization-mode overhead is wasted and MinDeg
might lose by a small constant.

---

## 8. Output schema

`SATMinDeg.run()` returns `[G]` (length-1 list) with
`G.graph["metadata"]` carrying:

| Field           | Meaning                                                                |
|-----------------|------------------------------------------------------------------------|
| `status`        | `"SAT"` / `"UNSAT"` / `"TIMED_OUT"`                                    |
| `optimality`    | `"proven"` (CP-SAT `OPTIMAL`) / `"unverified"` (CP-SAT `FEASIBLE`)     |
| `alpha_bound`   | the fixed $\alpha$                                                     |
| `d_lower`       | $D_{\text{lo}}$ used in the model                                      |
| `d_upper`       | $D_{\text{hi}}$ used in the model                                      |
| `d_min`         | solver's $D$ at termination (= $\Delta(G^\star)$ if `optimality="proven"`) |
| `objective`     | CP-SAT's reported objective value                                      |
| `best_bound`    | CP-SAT's lower bound on the objective (useful on timeout)              |
| `wall_time_s`   | CP-SAT wall time                                                       |
| `pruned_by`     | (only on UNSAT-via-prune) firing rule from `_ramsey_prune`             |

`metadata["best_bound"]` is the live underrun: on `FEASIBLE` (timeout
without proof of optimality), if `objective - best_bound = 0` the
witness is in fact optimal — CP-SAT just didn't get to mark it as
such. Worth surfacing.

---

## 9. Class shape

```python
class SATMinDeg(Search):
    name = "sat_min_deg"

    def __init__(
        self, n, *,
        alpha,                       # required
        d_lower=None,                # default: Caro-Wei floor
        d_upper=None,                # default: n - 1
        time_limit_s=60.0,
        ramsey_prune=True,
        **kwargs,
    ): ...
```

Same kwarg discipline as `SAT`: required `alpha`, optional everything
else, `ramsey_prune` defaults to `True`.

---

## 10. Future tightenings (deferred)

These compose cleanly with MinDeg and are slated for later sections:

- **Pin-an-IS** (`SAT.md` §3.1): fix vertices $0, \ldots, \alpha - 1$
  to be pairwise non-adjacent. Compatible — kills $\sim \alpha!$ of
  the $n!$ vertex-relabel symmetries without touching $D$.
- **CEGAR α-clauses** (`SAT.md` §3.6): the highest-leverage tightening
  per `OPTIMIZATION.md` §4.3. Compatible — α is fixed in MinDeg, so
  lazy generation of $(\alpha+1)$-subset clauses works exactly as in
  feasibility mode.
- **Edge-lex symmetry** (`SAT.md` §3.2): row-0 lexicographic ordering
  of the adjacency matrix. Compatible.

None of these are needed for the first cut — they're orthogonal
accelerators that can be layered on once MinDeg's baseline is in.
