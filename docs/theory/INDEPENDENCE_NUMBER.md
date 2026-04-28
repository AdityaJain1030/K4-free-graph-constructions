# Independence Number Solvers — Mathematical Foundations

This document describes each α solver implemented in `utils/graph_props.py`
at the level of the underlying algorithms and the mathematical ideas that
make them work. It is intended to be self-contained for a reader familiar
with graph theory but not necessarily with the implementation.

**Note on runtimes.** Big-$O$ complexities given throughout this document are
asymptotic worst-case bounds. They describe how algorithms scale in the limit
and are useful for understanding *why* one solver beats another structurally,
but they say nothing about constants, cache behaviour, or how a particular
graph family triggers or avoids the worst case. Empirical wall-clock times and
peak RSS on the graphs that actually arise in this project are in
`experiments/alpha/ALPHA_PERFORMANCE.md` and `experiments/alpha/ALPHA_ACCURACY.md`.

---

## The Problem

Given a graph $G = (V, E)$ with $|V| = n$, the **independence number** $\alpha(G)$
is the size of the largest independent set — a subset $S \subseteq V$ such that
no two vertices in $S$ are adjacent. Computing $\alpha(G)$ is NP-hard in general
(equivalent to maximum clique on the complement), but the graphs arising in this
project (sparse, $K_4$-free, max degree $\leq 10$) admit practical exact algorithms
at $n \leq 1000$ and beyond.

---

# Part I — Exact Algorithms

The following solvers return a certified optimal independent set. They always
find the true $\alpha(G)$, regardless of graph structure. They differ only in
which upper-bounding argument they use to prune the search tree, which
determines how fast they run in practice.

---

## 1. Branch-and-Bound with Popcount Bound (`alpha_exact`)

### What "popcount" means

The candidate set $C$ (the vertices still eligible to join the IS) is stored as
a single integer in which bit $j$ is 1 if vertex $j$ is still a candidate. The
**popcount** of $C$ is the number of 1-bits — i.e., $|C|$. It is a trivial upper
bound on $\alpha(G[C])$: you cannot have more independent vertices than there are
vertices. The bound ignores all edges.

Concretely: if $C = \texttt{0b00101101}$ then $\text{popcount}(C) = 4$, meaning
four vertices remain as candidates, so $\alpha(G[C]) \leq 4$.

### Algorithm

Recursive branch-and-bound over the vertex set:
1. Pick the lowest-indexed vertex $v$ in $C$.
2. **Include** $v$: recurse on $C' = C \setminus (\{v\} \cup N(v))$.
3. **Exclude** $v$: recurse on $C' = C \setminus \{v\}$.
4. **Prune**: if $\text{current\_size} + |C| \leq \text{best}$, abandon the branch.

**Correctness.** The search exhausts every include/exclude assignment, and the
pruning condition is sound because $\alpha(G[C]) \leq |C|$.

**Runtime.**

$$T(n) = O\!\left(2^n\right) \quad \text{worst case}$$

Bitmask operations are $O(1)$ per node (single machine-word AND/OR/NOT).
In practice competitive up to $n \approx 40$ on sparse $K_4$-free graphs;
beyond that the popcount bound is too weak and the tree explodes.

**Implementation note.** The neighbor set of vertex $v$ is stored as an integer
`nbr[v]` where bit $j$ is set iff $(v,j) \in E$. Set intersection, difference,
and cardinality reduce to single machine-word operations.

---

## 2. Branch-and-Bound with Clique-Cover Bound (`alpha_bb_clique_cover`)

### What "clique cover" means

A **clique cover** of a graph $H$ is a partition of $V(H)$ into groups where
every group is a clique (every pair of vertices in the group is adjacent). The
**clique cover number** $\text{cc}(H)$ is the minimum number of such groups needed.

The key observation: an independent set can contain **at most one vertex from
each clique**, because any two vertices in the same clique are adjacent.
Therefore if you cover $H$ with $k$ cliques:

$$\alpha(H) \leq \text{cc}(H) \leq k$$

Concrete example: if $G[C]$ has 12 vertices partitioned into 4 triangles ($K_3$'s),
then $\alpha(G[C]) \leq 4$, not 12. The popcount bound gives 12 — three times weaker.

### Why this is tight on $K_4$-free graphs

On a $K_4$-free graph every clique has size at most 3. A $d$-regular $K_4$-free
graph on $n$ vertices can typically be covered by $\approx n/3$ triangles, and
$\alpha \approx n/3$ on well-structured graphs — so the clique cover bound is
nearly tight. The popcount bound is $n$, a factor of 3 off. That 3× tighter
pruning threshold is what takes the solver from timing out at $n=60$ to solving
$n=1000$.

### Algorithm

Same B&B structure as `alpha_exact`, with the pruning condition replaced:

$$\text{current\_size} + \text{cc}(G[C]) \leq \text{best} \implies \text{prune}$$

**Greedy clique cover procedure.** Given candidate set $C$:
1. Pick the lowest-indexed vertex $v \in C$.
2. Initialise the current clique as $\{v\}$.
3. Extend: repeatedly pick any $w \in C$ adjacent to *all* current clique
   members (intersect neighbor bitmasks), add $w$.
4. Remove the clique from $C$. Increment the clique count.
5. Repeat until $C = \emptyset$.

This is greedy maximal-clique extension — not provably optimal, but in practice
yields a cover close to minimum on sparse $K_4$-free graphs.

**Runtime.**

$$T(n) = O\!\left(1.1996^n\right) \quad \text{worst case (Robson 1986)}$$

On sparse $K_4$-free graphs the practical runtime is near-linear in $n$ due to
aggressive pruning. Empirically: $n=1000$ in 130 ms at 38 MB RSS.

**Note on the dual.** A clique cover of $G$ is a proper colouring of the
complement $\bar{G}$. The fractional clique cover number equals the Lovász theta
$\vartheta(\bar{G})$, which upper-bounds $\alpha(G)$ by the sandwich theorem
$\alpha(G) \leq \vartheta(\bar{G}) \leq \chi(\bar{G})$. The greedy integer cover
is a coarser bound, but still dramatically sharper than popcount.

---

## 3. CP-SAT (`alpha_cpsat`)

**Formulation.** Maximum Independent Set encoded as a binary integer program:

$$
\begin{aligned}
\text{maximize} \quad & \sum_{v \in V} x_v \\
\text{subject to} \quad & x_u + x_v \leq 1 && \forall\, (u,v) \in E \\
& x_v \in \{0, 1\} && \forall\, v \in V
\end{aligned}
$$

Each binary variable $x_v$ indicates whether vertex $v$ is in the IS. The edge
constraints enforce that no two adjacent vertices are both selected.

**Solver.** OR-Tools CP-SAT combines:
- **CDCL SAT** for propositional clause learning
- **LP relaxation** for continuous upper bounds on the objective
- **Large neighbourhood search** for feasibility
- **Branch-and-bound** with the LP relaxation as the bounding function

The LP relaxation of the MIS program has a known integrality gap of up to
$\Theta(\sqrt{n})$ in the worst case, but on sparse structured graphs (circulants,
Cayley graphs) it is typically tight.

**Vertex-transitive pin.** For vertex-transitive graphs (every vertex equivalent
under automorphism — e.g., circulants), any maximum IS can be mapped to one
containing vertex 0. The constraint $x_0 = 1$ is sound and reduces the search
space by a factor proportional to the automorphism group size.

**Runtime.**

$$T = \underbrace{O(1)}_{\text{model build}} + \underbrace{O\!\left(2^n\right)}_{\text{worst-case B\&B}}$$

The model build and OR-Tools initialisation cost $\approx 200$–$400$ ms
regardless of $n$. This fixed overhead dominates at small $n$; for large or
structurally hard graphs CP-SAT's CDCL and LP machinery pull ahead of hand-rolled
B&B. Preferred for $n \geq 500$ or when graph structure is unknown/dense.

---

## 4. MaxSAT via RC2 (`alpha_maxsat`)

### From MIS to MaxSAT

Maximum Weighted Satisfiability (MaxSAT) asks: given a CNF formula with weighted
clauses, find the truth assignment maximising total satisfied weight. Clauses
come in two flavours:

- **Hard clauses** must be satisfied — violation makes the solution infeasible.
- **Soft clauses** carry weight $w_i \geq 0$ — the solver maximises $\sum_i w_i \cdot \mathbf{1}[\text{clause}_i \text{ satisfied}]$.

MIS maps onto MaxSAT as follows. For each vertex $v \in V$ introduce a Boolean
variable $x_v$ ($x_v = 1$ means $v$ is included in the IS).

**Hard clauses** (one per edge): for each $(u, v) \in E$,

$$(\neg x_u \vee \neg x_v)$$

This is satisfied iff at least one of $u, v$ is excluded — exactly the IS constraint.

**Soft clauses** (one per vertex): for each $v \in V$,

$$(x_v) \quad \text{with weight } 1$$

Satisfying this clause means including $v$. The MaxSAT objective is then:

$$\text{maximize} \sum_{v \in V} \mathbf{1}[x_v = 1] \quad \text{subject to all hard clauses}$$

which is exactly $\alpha(G)$.

### RC2 — how it works

RC2 (Relaxation-Cardinality, Rounds 2; Ignatiev et al. 2019) is a **core-guided**
algorithm. Rather than searching directly for a large IS, it iteratively finds
*reasons the IS cannot be any larger* and accumulates them into a proof.

A **core** is a minimal set of soft clauses $\{(x_{v_1}), \ldots, (x_{v_k})\}$
that cannot all be satisfied simultaneously with the hard clauses — i.e., a set
of vertices $\{v_1, \ldots, v_k\}$ that contains no independent set of size $k$
(they might span a clique, an odd cycle, or a more complex dependent structure).
At least one vertex in each core must be excluded, so the core certifies that
the optimum decreases by at least 1.

RC2 proceeds:

1. **Assume all soft clauses are satisfied** (optimistically try to include every vertex).
2. **Find a core**: call a SAT solver to find a minimal infeasible subset of
   the active soft assumptions. This is a set of vertices that cannot all belong
   to any IS simultaneously.
3. **Relax the core**: introduce the cardinality constraint

$$\sum_{i=1}^{k} x_{v_i} \leq k - 1$$

   as a new hard clause (at most $k-1$ of the $k$ core vertices can be included).
   Replace the $k$ unit soft clauses with a single soft clause asserting
   $\sum x_{v_i} = k - 1$, costing exactly 1 unit of objective.

4. **Repeat** from step 2 until no core exists. The current assignment is
   then certifiably optimal.

The number of rounds equals $n - \alpha(G)$ in the worst case (one vertex
excluded per round). The name "Rounds 2" refers to each core contributing
exactly one unit of cost. The total number of SAT calls is $O(n - \alpha(G))$,
each of which runs a CDCL SAT solver over the augmented formula.

**Runtime.**

$$T = O\!\left((n - \alpha(G)) \cdot T_{\text{SAT}}\right)$$

where $T_{\text{SAT}}$ is the cost of one SAT call. On easy $K_4$-free instances
the SAT calls are trivial and the overall cost is flat $\approx 40$ ms regardless
of $n$, making RC2 an efficient independent cross-check.

### Why it's a useful cross-check

RC2 is a completely different code path from every B&B solver: different
paradigm (clause learning vs. bitmask enumeration), different library (python-sat
vs. hand-rolled B&B), different internal representation. When B&B and RC2 agree
on $\alpha$, the result is highly reliable. Cost on easy $K_4$-free instances:
flat $\approx 40$ ms, $\approx 45$ MB RSS, essentially independent of $n$.

---

## 5. Max Clique on the Complement (`alpha_clique_complement`)

**Reduction.** An independent set in $G$ is a clique in the complement
$\bar{G} = (V, \bar{E})$ where $(u,v) \in \bar{E}$ iff $(u,v) \notin E$.
Therefore $\alpha(G) = \omega(\bar{G})$.

**Algorithm.** Bron–Kerbosch with Tomita pivoting on $\bar{G}$:
- Maintain $R$ (current clique), $P$ (candidate extensions), $X$ (processed vertices).
- Pick pivot $u \in P \cup X$ maximising $|P \cap N_{\bar{G}}(u)|$, minimising
  the branching factor.
- Branch on each $v \in P \setminus N_{\bar{G}}(u)$: recurse on
  $R \cup \{v\}$, $P \cap N_{\bar{G}}(v)$, $X \cap N_{\bar{G}}(v)$.

**Runtime.**

$$T(n) = O\!\left(3^{n/3}\right) \quad \text{(Tomita et al. 2006, on the complement)}$$

On sparse $K_4$-free graphs $\bar{G}$ is near-complete, so $\omega(\bar{G}) \approx n$
and the algorithm degenerates to near-exhaustive enumeration. Times out at
$n \geq 80$ on the sparse $K_4$-free test family. Included for completeness;
natural use case is dense graphs where $\bar{G}$ is sparse.

---

# Part II — Approximate Algorithms

The following solvers do not certify optimality. They return a valid independent
set that may be smaller than the maximum. They are useful when $n$ is large, when
exact computation is too slow for an inner loop, or when a ranking signal (rather
than a certified value) is sufficient.

---

## 6. Randomised Greedy MIS (`alpha_lb` / `alpha_approx`)

**Algorithm.** Single restart: repeatedly select a random vertex $v$ from the
remaining graph, add $v$ to the IS, remove $v$ and $N(v)$, repeat until no
vertices remain. Run $R$ restarts, return the largest IS found.

**Runtime per restart.**

$$T = O(n + m) \quad \text{where } m = |E|$$

Each vertex is processed at most once (removed when a neighbor is selected).
Total for $R$ restarts: $O(R(n + m))$. With $R = 20$ and $m = O(dn)$ for
$d$-regular graphs: $O(20 \cdot dn)$, easily sub-millisecond at $n \leq 1000$.

**Approximation guarantee.** No worst-case guarantee on the IS size. On random
$d$-regular graphs, the greedy IS has expected size $\approx \frac{2 \ln d}{d} \cdot n$,
which matches the Shearer bound asymptotically. On structured $K_4$-free graphs
with $R=20$ restarts, Spearman $\rho = 0.988$–$0.992$ against true $\alpha$
(see `experiments/alpha/ALPHA_ACCURACY.md`).

**Caro-Wei lower bound.** A deterministic lower bound on $\alpha(G)$:

$$\alpha(G) \geq \sum_{v \in V} \frac{1}{d(v) + 1}$$

**Proof.** Assign each vertex a uniform random priority in $[0,1]$, independently.
Include vertex $v$ in the IS iff $v$ has the highest priority in its closed
neighbourhood $N[v] = \{v\} \cup N(v)$. Vertex $v$ is included with probability
$\frac{1}{|N[v]|} = \frac{1}{d(v)+1}$. The events are non-negatively correlated
across non-adjacent vertices, so by linearity of expectation the expected IS size
is at least $\sum_v \frac{1}{d(v)+1}$.

This bound depends only on the degree sequence and ignores all global structure —
hence its poor ranking correlation ($\rho \approx 0.52$) on $K_4$-free graphs
where the IS structure is non-trivial.

---

## 7. Greedy Clique-Cover Upper Bound (`alpha_ub`)

**Algorithm.** Run the same greedy clique-cover procedure used inside
`alpha_bb_clique_cover` (Section 2) on the full graph — not as a B&B pruning
tool, but as a standalone upper bound. Returns a value $\geq \alpha(G)$.

**Runtime.**

$$T = O(n \cdot d) \quad \text{where } d = \text{max degree}$$

Each clique-extension step intersects neighbour bitmasks. On $d$-regular graphs
with $n$ vertices this is $O(nd)$ total.

**Guarantee.**

$$\alpha(G) \leq \text{cc}(G) \leq \alpha\_\text{ub}(G)$$

The greedy cover is not provably minimal, so the bound can be loose on
irregular or dense graphs. On sparse $K_4$-free graphs (max clique size 3)
it is typically within 1–2 of $\alpha$.

**Use case.** Paired with `alpha_lb` to form the `AlphaBracket` (lb, ub) in
`utils/alpha_surrogate.py`. When lb == ub the bracket certifies the exact
value without a SAT call. Used as a ranking signal in tabu/SA inner loops
where the bracket width is more informative than either bound alone.

---

## When to use each solver

For sparse $K_4$-free graphs ($\deg \leq 15$), use `alpha_bb_clique_cover` — it runs in under a millisecond on most instances and is the project default. For dense $K_4$-free graphs (e.g. polarity graphs) or unknown structure, fall back to `alpha_cpsat`; add `vertex_transitive=True` only when the graph is provably vertex-transitive (circulants, Cayley graphs), as it will silently under-count on irregular graphs. For a quick approximate bound without an exact solve, pair `alpha_lb` + `alpha_ub` as an `AlphaBracket` — when `lb == ub` you have the exact value for free.

---

## Summary

### Exact solvers

| Solver | Pruning bound | Paradigm | Worst-case runtime | Practical regime |
|---|---|---|---|---|
| `alpha_exact` | $\lvert C \rvert$ (popcount) | B&B bitmask | $O(2^n)$ | $n \leq 40$ |
| `alpha_bb_clique_cover` | $\text{cc}(G[C])$ (clique cover) | B&B bitmask | $O(1.1996^n)$ | sparse $K_4$-free (any $n$) |
| `alpha_cpsat` | LP relaxation | CDCL + LNS | $O(2^n)$ + 400 ms init | dense / unknown / large |
| `alpha_maxsat` | RC2 core-guided | MaxSAT | $O((n-\alpha) \cdot T_\text{SAT})$ | cross-check, any $n$ |
| `alpha_clique_complement` | Tomita pivot | Bron–Kerbosch on $\bar{G}$ | $O(3^{n/3})$ | dense graphs, $\bar{G}$ sparse |

### Approximate solvers

| Solver | Output | Runtime | Accuracy on $K_4$-free |
|---|---|---|---|
| `alpha_lb` (greedy MIS, $R$ restarts) | lower bound $\leq \alpha$ | $O(R(n+m))$ | $\rho = 0.99$ vs true $\alpha$ |
| `alpha_ub` (greedy clique cover) | upper bound $\geq \alpha$ | $O(nd)$ | tight within 1–2 on sparse $K_4$-free |
| Caro-Wei | lower bound $\leq \alpha$ | $O(n)$ | $\rho = 0.52$ vs true $\alpha$ |
