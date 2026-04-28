# SAT-based search for K₄-free graphs

A running specification for the `search/SAT/` solvers. This file starts
with the **naive formulation** — the most direct encoding, no
optimizations — and will grow as we layer accelerators on top.

---

## 1. Problem statement

Given integers $(n, \alpha, d)$ with $0 \le \alpha < n$ and
$0 \le d \le n-1$, decide whether there exists a simple undirected
graph $G = (V, E)$ on $|V| = n$ vertices satisfying

$$
\begin{aligned}
G \text{ is } K_4\text{-free}, \\
\alpha(G) \le \alpha, \\
\Delta(G) \le d,
\end{aligned}
$$

where $\alpha(G)$ is the independence number (size of the largest
vertex set with no internal edge) and $\Delta(G)$ is the maximum
degree. We call the triple $(n, \alpha, d)$ a **box** and the decision
problem the **box feasibility problem**.

The motivation is the extremal quantity

$$
c_{\log}(G) \;=\; \frac{\alpha(G)\,\Delta(G)}{n \,\ln \Delta(G)},
$$

whose infimum over $K_4$-free graphs is the object of study. By
sweeping boxes in increasing order of $c_{\log}$ and recording each
verdict, we accumulate either witnesses (SAT) or proofs of
nonexistence (UNSAT) along the frontier.

---

## 2. Naive CP-SAT encoding

Implemented in `search/SAT/sat.py`. Every clause maps one-to-one onto
the mathematical definition above; correctness is verifiable by
inspection, and the base class re-checks $K_4$-freeness on the
returned graph as an independent audit.

### 2.1 Decision variables

For each unordered pair $\{i, j\} \subseteq V$ with $i < j$ introduce a
Boolean

$$
x_{ij} \in \{0, 1\}, \qquad x_{ij} = 1 \iff \{i,j\} \in E.
$$

Total: $\binom{n}{2}$ variables.

### 2.2 Constraints

**(C1) $K_4$-free.**

A $K_4$ is a set of 4 vertices with **all 6 internal edges present**.
Equivalently, $G$ is $K_4$-free iff for every choice of 4 vertices, at
least one of the 6 edges between them is missing. The property thus
decomposes into one independent condition per 4-subset of $V$.

Fix a 4-subset $S = \{a, b, c, d\} \subseteq V$. The 6 potential edges
inside $S$ are

$$
\{a,b\},\ \{a,c\},\ \{a,d\},\ \{b,c\},\ \{b,d\},\ \{c,d\},
$$

each represented by an edge variable $x_{ab}, x_{ac}, \ldots, x_{cd}$.
The $2^6 = 64$ joint assignments to these 6 Booleans correspond
bijectively to the 64 possible induced subgraphs on $S$, of which:

- **63** are $K_4$-free on $S$ (at least one edge absent), and
- **1** is the all-ones assignment that induces a $K_4$.

We want a clause that excludes exactly the all-ones case. The
**cardinality cut**

$$
\sum_{\{i,j\} \subseteq S} x_{ij} \;\le\; 5
\qquad \forall\, S \in \binom{V}{4}
$$

does precisely this: the sum hits 6 only when every internal edge is
present, and is $\le 5$ in all 63 K₄-free configurations. The
constraint is therefore both necessary (any K₄ violates it) and
sufficient (any non-K₄ assignment on $S$ satisfies it). Quantifying
over every $S \in \binom{V}{4}$ yields $\binom{n}{4}$ clauses, and the
intersection of all those local conditions is exactly the global
K₄-free property.

Equivalent CNF form (consumed by pure SAT solvers):

$$
\neg x_{ab} \lor \neg x_{ac} \lor \neg x_{ad}
\lor \neg x_{bc} \lor \neg x_{bd} \lor \neg x_{cd},
$$

read as "at least one of these 6 edges is absent." CP-SAT accepts the
linear inequality directly and internally lifts it via cuts and
at-most-$k$ propagators, so we use that form for clarity. Both
encodings define the same feasible set.

Note: we forbid $K_4$ as a *subgraph*, not as an *induced subgraph* —
extra edges crossing into $S$ from outside are irrelevant. Since
"induced K₄" and "subgraph K₄" coincide for the complete graph (every
$K_4$ is automatically induced once all 6 edges are present), the
constraint exactly matches the standard K₄-free definition.

**(C2) Independence-number bound, $\alpha(G) \le \alpha$.**

An **independent set** of $G$ is a vertex subset $I \subseteq V$ with
no edges between any two of its members; the **independence number**
$\alpha(G)$ is the size of the largest such $I$. By definition,

$$
\alpha(G) \le \alpha
\quad\iff\quad
\text{no subset of size } \alpha + 1 \text{ is independent.}
$$

So the bound decomposes — exactly as the K₄-free property did — into
one independent local condition per $(\alpha+1)$-subset of $V$.

Fix a subset $T \subseteq V$ with $|T| = \alpha + 1$. The
$\binom{\alpha+1}{2}$ potential edges inside $T$ are represented by
edge variables $x_{ij}$ with $i, j \in T$. Of the
$2^{\binom{\alpha+1}{2}}$ joint assignments to those Booleans:

- **1** is the all-zeros assignment, in which $T$ has no internal
  edge and is therefore an independent set of size $\alpha + 1$ —
  precisely the configuration we must forbid.
- The remaining
  $2^{\binom{\alpha+1}{2}} - 1$ assignments contain at least one
  internal edge, breaking $T$'s independence and leaving the bound
  intact (at least *with respect to this particular T*).

The dual of (C1) handles this exactly: a **cardinality cut** that
forbids only the all-zeros case,

$$
\sum_{\{i,j\} \subseteq T} x_{ij} \;\ge\; 1
\qquad \forall\, T \in \binom{V}{\alpha + 1}.
$$

The sum is 0 iff $T$ is independent, and $\ge 1$ in every other case.
So the inequality rejects exactly the independent-$T$ assignments and
accepts the rest — necessary and sufficient *for that $T$*. Taking
the conjunction over every $(\alpha+1)$-subset gives the global bound:

$$
G \text{ has no independent set of size } \alpha + 1
\;\iff\;
\text{every } T \in \binom{V}{\alpha+1} \text{ contains an edge.}
$$

Equivalent CNF form (consumed by pure SAT solvers):

$$
\bigvee_{\{i,j\} \subseteq T} x_{ij},
$$

read as "at least one edge inside $T$ is present." Both encodings
define the same feasible set; CP-SAT handles the linear ≥1 inequality
directly.

There are $\binom{n}{\alpha + 1}$ such clauses — the dominant family
in the model whenever $\alpha + 1 \approx n / 2$, and the practical
bottleneck in scaling the naive solver.

**Edge cases.**

- If $\alpha + 1 > n$ the family is empty (no $(\alpha+1)$-subset
  exists) and the bound is vacuous: every graph on $n$ vertices
  satisfies $\alpha(G) \le n$ trivially.
- If $\alpha = 0$ the only $1$-subsets are individual vertices, and
  $\binom{1}{2} = 0$ — there are no edges to force. The clause
  family becomes $\sum_{\emptyset} x_{ij} \ge 1$, which is
  unsatisfiable (an empty sum cannot be $\ge 1$). This correctly
  reports $\alpha(G) \le 0$ as infeasible for any $n \ge 1$, since a
  single isolated vertex already gives $\alpha \ge 1$.
- Note that we bound $\alpha(G)$ from **above** only. Graphs with
  $\alpha(G) < \alpha$ also satisfy (C2). Forcing equality
  $\alpha(G) = \alpha$ requires an additional lower-bound clause
  family — see the pin-an-IS tightening (§3.1, forthcoming).

The asymmetry between (C1) and (C2) is worth noting: K₄-freeness
forbids the **all-ones** local configuration ($\le 5$), while the
α-bound forbids the **all-zeros** local configuration ($\ge 1$). Both
are cardinality cuts on the local edge-variable sum; they differ only
in which extreme is excluded.

**(C3) Maximum-degree bound, $\Delta(G) \le d$.**

The **degree** of a vertex $v$ is the number of edges incident to it,
$\deg(v) = |\{u : \{u, v\} \in E\}|$. The **maximum degree** is
$\Delta(G) = \max_{v \in V} \deg(v)$. By definition,

$$
\Delta(G) \le d
\quad\iff\quad
\deg(v) \le d \text{ for every } v \in V.
$$

So this property — unlike (C1) and (C2) — decomposes one condition
per **vertex** rather than per subset. Each vertex contributes one
local condition, independent of all the others.

Fix a vertex $v$. Its incident edges are
$\{v, u\}$ for $u \in V \setminus \{v\}$, represented by the $n - 1$
edge variables $\{x_{vu} : u \ne v\}$. The degree of $v$ in the
encoded graph is exactly the sum of those Booleans:

$$
\deg(v) \;=\; \sum_{u \ne v} x_{vu}.
$$

Bounding this by $d$ is therefore a single linear inequality:

$$
\sum_{u \ne v} x_{vu} \;\le\; d
\qquad \forall\, v \in V.
$$

The constraint is necessary and sufficient *for that $v$*: any
assignment with $\deg(v) > d$ violates it, and any assignment with
$\deg(v) \le d$ satisfies it. Quantifying over every vertex yields
$n$ such clauses, and their intersection is exactly $\Delta(G) \le d$.

Equivalent CNF form (consumed by pure SAT solvers): the at-most-$d$
constraint over the $n-1$ variables $\{x_{vu}\}$ expands to one
$(d+1)$-clause per choice of $d+1$ would-be neighbors of $v$,

$$
\bigvee_{w \in W} \neg x_{vw}
\qquad \forall\, W \in \binom{V \setminus \{v\}}{d+1},
$$

read as "v cannot be adjacent to all $d+1$ vertices of $W$
simultaneously." This expansion produces $n \cdot \binom{n-1}{d+1}$
clauses — much larger than the linear form. CP-SAT keeps the
inequality compact and uses a dedicated at-most-$k$ propagator, so we
never materialize the CNF expansion.

There are $n$ linear inequalities in (C3), independent of $d$ — by
far the smallest of the three constraint families and effectively
free in the model.

**Edge cases.**

- If $d \ge n - 1$ the bound is vacuous: every vertex has at most
  $n - 1$ neighbors anyway, so the inequality is automatically
  satisfied and propagates nothing.
- If $d = 0$ the constraint forces every $x_{vu} = 0$ — the empty
  graph is the unique feasible assignment for (C3) alone. Combined
  with (C2) for any $\alpha < n$, the model becomes infeasible: an
  edgeless graph on $n \ge \alpha + 1$ vertices has $\alpha(G) = n >
  \alpha$.
- We bound $\Delta(G)$ from **above** only. Graphs with smaller
  maximum degree also satisfy (C3); requiring a *minimum* degree (or
  exact regularity $\deg(v) = d$ for all $v$) is a separate
  tightening — see the regular / near-regular variants (§3.4,
  forthcoming).

**Symmetry tying (C3) back to (C1)–(C2).** Each edge variable
$x_{ij}$ appears in exactly two degree clauses (those for vertex $i$
and vertex $j$). It also appears in $\binom{n-2}{2}$ K₄-free clauses
(one per pair of additional vertices completing a 4-set) and in
$\binom{n-2}{\alpha-1}$ α-clauses (one per choice of $\alpha-1$ extra
vertices completing an $(\alpha+1)$-subset). The degree clauses are
the only ones that touch a single vertex's *entire* incidence list at
once, which is what makes them the natural place to inject
degree-banded or regularity tightenings later.

### 2.3 Output verdict

Pass the model to CP-SAT and read the status:

| CP-SAT status            | Returned verdict | Witness                      |
|--------------------------|------------------|------------------------------|
| `OPTIMAL` / `FEASIBLE`   | `SAT`            | edge set $\{x_{ij} = 1\}$           |
| `INFEASIBLE`             | `UNSAT`          | empty graph (proof of nonexistence) |
| `UNKNOWN` (time-out)     | `TIMED_OUT`      | empty graph (no information)        |

The empty graph is returned in the non-SAT cases so the verdict
survives the base class's scoring/persistence path; the meaningful
field is `metadata["status"]`.

### 2.4 Scaling of the naive model

| Family                   | Count                        |
|--------------------------|------------------------------|
| Boolean variables        | $\binom{n}{2}$               |
| (C1) $K_4$-free clauses  | $\binom{n}{4}$               |
| (C2) $\alpha$ clauses    | $\binom{n}{\alpha+1}$        |
| (C3) degree clauses      | $n$                          |

For $n = 17,\ \alpha = 3$ (the Paley-17 box) this is
$136$ Booleans, $2{,}380$ K₄-clauses, $2{,}380$ α-clauses, $17$ degree
clauses. CP-SAT's presolve and solve are sub-second on this size.

**Where the clauses peak.** The K₄ family $\binom{n}{4}$ and the
degree family $n$ depend only on $n$. The α family
$\binom{n}{\alpha+1}$ depends on $\alpha$ and behaves as a binomial
ridge in $\alpha$, peaking at $\alpha + 1 = \lfloor n/2 \rfloor$. The
table below fixes $n = 20$ and tracks the α-family count as $\alpha$
sweeps the range:

| $\alpha$ | $\alpha + 1$ | $\binom{20}{\alpha+1}$ | Regime                       |
|---------:|-------------:|-----------------------:|------------------------------|
|        2 |            3 |                  1 140 | c_log-frontier (sparse)      |
|        3 |            4 |                  4 845 | c_log-frontier               |
|        4 |            5 |                 15 504 | c_log-frontier               |
|        5 |            6 |                 38 760 | mid                          |
|        7 |            8 |                125 970 | mid                          |
|        9 |           10 |            **184 756** | **peak** ($\alpha+1 = n/2$)  |
|       11 |           12 |                125 970 | post-peak (mirror of 7)      |
|       14 |           15 |                 15 504 | post-peak (mirror of 4)      |
|       18 |           19 |                     20 | trivial                      |

For comparison, at $n = 20$ the K₄ family is fixed at
$\binom{20}{4} = 4{,}845$, so the α family overtakes it once
$\alpha + 1 \ge 5$ and dominates the model size everywhere up to
$\alpha + 1 \le n - 4$.

**The good news.** The c_log frontier sits in the sparse regime, not
the dense one. Empirically, the best known K₄-free constructions on
the frontier have

$$
\alpha(G) \;\in\; \big[\,\Theta(\sqrt{n}),\ \Theta(n^{3/5})\,\big],
$$

with the lower end set by the Paley / polarity families ($\alpha
\approx \sqrt n$, e.g. Paley $P(17)$ with $n=17,\ \alpha=3 \approx
\sqrt{17}$) and the upper end set by Mattheus–Verstraete-style
constructions ($\alpha \approx n^{3/5}$). In both regimes $\alpha + 1$
stays well below the binomial ridge at $n/2$.

At $n = 20,\ \alpha = 4 \approx \sqrt{n}$ the α family is $15{,}504$
clauses — an order of magnitude below the worst-case $184{,}756$. At
$n = 20,\ \alpha = \lceil n^{3/5}\rceil = 7$ it is $77{,}520$ — still
under half the peak. The naive encoding becomes clause-bottlenecked
only when $\alpha + 1$ approaches $n/2$, which is the *dense*-graph
regime and is not where extremal $c_{\log}$ candidates live.

**Predicted scaling ceiling.** Walking the c_log-frontier band
$\alpha \in [\Theta(\sqrt{n}), \Theta(n^{3/5})]$, the α family is
$\binom{n}{\alpha + 1}$. At the lower end ($\alpha \approx \sqrt{n}$):

| $n$ | $\alpha$ ($\approx\!\sqrt{n}$) | $\binom{n}{\alpha+1}$ |
|----:|------:|--------------:|
|  17 |     3 |         2 380 |
|  20 |     4 |        15 504 |
|  25 |     5 |       177 100 |
|  30 |     6 |     2 035 800 |
|  35 |     6 |     6 724 520 |
|  40 |     7 |    76 904 685 |

At the upper end ($\alpha \approx n^{3/5}$) clause counts blow up
several rows faster — e.g. $n = 30,\ \alpha = \lceil 30^{3/5}\rceil = 8$
gives $\binom{30}{9} \approx 1.4 \times 10^7$, and
$n = 40,\ \alpha = \lceil 40^{3/5}\rceil = 10$ gives
$\binom{40}{11} \approx 2.3 \times 10^9$.

Three compounding factors set the practical wall:

1. **Clause-count memory.** CP-SAT is comfortable up to roughly
   $10^6$–$10^7$ constraints; beyond that, model construction itself
   becomes a bottleneck and presolve slows sharply.
2. **No symmetry breaking.** The naive model treats all $n!$ vertex
   labelings as distinct, so isomorphic search-tree branches are
   re-explored. This is the dominant slowdown for *finding* a SAT
   witness on hard boxes.
3. **UNSAT is harder than SAT.** A SAT verdict only needs one path
   to a witness; an UNSAT proof needs the solver to close every
   branch. Without Ramsey-style pruning (§3.3) the solver brute-forces
   each $(\alpha, d)$ box.

Putting the three together, the predicted ceiling for the naive
encoding is:

| Regime              | $n$       | Notes                                                                      |
|---------------------|-----------|----------------------------------------------------------------------------|
| Sub-second          | $\le 17$  | Paley-17 box solves instantly                                              |
| Minutes per box     | $18$–$22$ | Frontier-$\alpha$ SAT queries tractable; UNSAT slower                       |
| Tens of minutes     | $23$–$27$ | Practical edge for SAT witnesses; UNSAT proofs become unreliable            |
| Memory/CPU wall     | $28$–$32$ | α-clause count at $n^{3/5}$-band crosses $10^7$; presolve dominates        |
| Hard wall           | $\ge 35$  | Naive encoding is no longer competitive — accelerators (§3) become required |

**Bottom line:** the naive solver should comfortably handle the
c_log-frontier boxes up to $n \approx 22$ on a laptop and to
$n \approx 27$ on a workstation, with SAT direction extending a few
$n$ further than UNSAT. Anything beyond that needs the §3 accelerators.

### 2.5 Search modes (decision-only)

The naive solver is **purely a feasibility oracle** — no objective is
imposed. To find graphs minimizing $c_{\log}$ we drive it externally:
sweep boxes $(n, \alpha, d)$ in $c_{\log}$-ascending order and collect
the first SAT witness in each row of $n$. Optimization-style
formulations (minimize edges, minimize $\Delta$, etc.) belong in
later, separate files.

---

## 3. Accelerators

### 3.3 Ramsey box pruning

Implemented in `search/SAT/ramsey_prune.py` and called from
`SAT._run` before any model construction. The pre-check rejects boxes
that **no** $K_4$-free graph on $n$ vertices can satisfy, returning
`UNSAT` with `metadata["pruned_by"]` set to the firing rule and the
solver never invoked.

**Rule 1 — trivial $\alpha = 0$.** A single vertex is an independent
set of size 1, so $\alpha(G) \ge 1$ for any $G$ on $n \ge 1$ vertices.
Any box with $\alpha = 0,\ n \ge 1$ is infeasible.

**Rule 2 — trivial $d = 0$.** $\Delta(G) = 0$ forces $G$ edgeless, in
which case $\alpha(G) = n$. Box infeasible whenever $n > \alpha$.

**Rule 3 — Caro–Wei.** For any graph $G$,
$$
\alpha(G) \;\ge\; \sum_{v \in V} \frac{1}{\deg(v) + 1}
\;\ge\; \frac{n}{\Delta(G) + 1}.
$$
Combined with $\alpha(G) \le \alpha$ and $\Delta(G) \le d$, feasibility
requires $\alpha (d + 1) \ge n$. Any box violating this is infeasible.

**Rule 4 — Ramsey $R(4, \alpha + 1)$.** By definition, every
$K_4$-free graph on $n \ge R(4, k)$ vertices has $\alpha(G) \ge k$.
So if $n \ge U_{R(4, \alpha + 1)}$ for any known upper bound $U$, the
box $(n, \alpha, \cdot)$ is infeasible. The module hard-codes
Radziszowski's published bounds (exact for $k \le 5$):

| $k$ | $R(4, k)$ upper bound |
|----:|----------------------:|
|  2  |  4 (exact)            |
|  3  |  9 (exact)            |
|  4  | 18 (exact)            |
|  5  | 25 (exact)            |
|  6  | 36                    |
|  7  | 58                    |
|  8  | 79                    |
|  9  | 106                   |
| 10  | 136                   |

These four rules are cheap (constant time each) and cover the bulk of
what is provably impossible from elementary arguments alone — the
solver is now spared every Caro–Wei-violating box and every box past
the Ramsey wall. Anything that survives is genuinely model-territory.

### 3.2 Row-0 lex symmetry break

Implemented in `search/SAT/sat.py` and `sat_min_deg.py` as the kwarg
`edge_lex` (default `True`). The constraint added to the model is

$$
x_{0,1} \;\ge\; x_{0,2} \;\ge\; \ldots \;\ge\; x_{0,n-1},
$$

i.e. **vertex 0's adjacency row is non-increasing**: all neighbors of
vertex 0 are labelled before all non-neighbors. This is a single chain
of $n-2$ Boolean comparisons — no totalizer, no auxiliary variables,
no reification.

**Why it works.** Without symmetry breaking, every $n!$ vertex
relabeling of the same graph appears as a distinct assignment to the
edge variables. CP-SAT cannot tell two relabelings apart, so it
re-explores isomorphic sub-trees once per labeling. For UNSAT proofs
this is brutal: every branch must close, and each isomorphism class
of partial graph gets re-closed $|\mathrm{Aut}(\cdot)|$ times.

The lex constraint picks one canonical representative per orbit by
forcing the labeling to put neighbors of vertex 0 first. Pseudocode:

```python
for j in range(1, n - 1):
    model.Add(x[(0, j)] >= x[(0, j + 1)])
```

**Soundness.** For any graph $G$ on $n$ vertices and any labeling
$\pi$, hold vertex 0 fixed and permute $\{1, \ldots, n-1\}$ so all
neighbors of vertex 0 land in positions $\{1, \ldots, \deg(0)\}$ and
non-neighbors fill the rest. After this relabel, vertex 0's row is
$(1, \ldots, 1, 0, \ldots, 0)$, satisfying every chain inequality.
So every K₄-free graph admits a labeling that survives the
constraint, and we lose no solutions. The constraint quotients out
the $S_{n-1}$ stabilizer of vertex 0 — at $n = 20$, that is a
$1.2 \times 10^{17}$-fold reduction in label-space.

**Why row-0 only.** Higher-row extensions (rows 1, 2, 3 conditioned
on earlier rows being tied) are sound but punishing on
narrow-orbit instances: `docs/searches/sat/SAT_OPTIMIZATION.md` §8.3
documents a **2000× slowdown** at $(n=19, α=4, d=6)$ when
`edge_lex_rows` is raised from 0 to 3, for the same FEASIBLE verdict.
We default to row-0 only and leave higher rows as a future opt-in.

**Why edge-lex over the obvious alternatives.**

| Mode       | Cost added                                   | Verdict in `SAT_OPTIMIZATION.md` §2.3 |
|------------|----------------------------------------------|---------------------------------------|
| `chain`    | $n-1$ cardinality inequalities (totalizers)  | Sometimes slower than no symmetry     |
| `anchor`   | $n-1$ cardinality inequalities (totalizers)  | Mild win                              |
| `edge_lex` | $n-2$ pure Bool comparisons                  | **3–100× win, kept as default**       |

The cardinality forms (`chain`, `anchor`) bound *degrees* (sums of
$n-1$ Booleans), forcing CP-SAT to introduce totalizer aux variables
and propagators. That overhead eats the symmetry gain. `edge_lex` is
all bool-vs-bool, lives directly in the SAT core, and unit propagation
fires the moment one side of any pair is fixed.

**Empirical wins** (from `SAT_OPTIMIZATION.md` §2.3):

- ~100× speedup at $n = 12$.
- 3–5× speedup at $n = 13$.
- 40× speedup on the boundary box $(n=16, α=3, d=7)$:
  $28.3\,\mathrm{s} \to 0.72\,\mathrm{s}$.

### Roadmap (remaining)

- **3.1** Pin-an-IS tightening (force $\alpha(G) = \alpha$ on the
  optimum boundary by fixing a witness IS).
- **3.4** Degree-banded / regularity restrictions.
- **3.5** Circulant restriction (vertex-transitive subset).
- **3.6** CEGAR refinement on the α-clauses (lazy generation by
  separation).

Each will state the formal addition to the base model, prove that the
new clauses preserve the relevant solution set, and report empirical
speedups against the naive baseline on a fixed benchmark set of boxes.
