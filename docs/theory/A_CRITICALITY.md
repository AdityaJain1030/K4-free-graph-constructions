# α-Criticality and the K₄-free $c_{\log}$ Problem

This document records the structural results on α-critical graphs that we
will exploit to attack the K₄-free $c_{\log}$-minimization problem. The
working objective is

$$
c_{\log}(G) \;=\; \frac{\alpha(G)\, \Delta(G)}{N \, \ln \Delta(G)},
\qquad N = |V(G)|, \quad \Delta(G) = d_{\max}(G).
$$

Every result is for finite simple graphs. Most lemmas are due to Zykov,
Hajnal, Andrásfai, Surányi, Lovász, Plummer, and Wessel; the
1-join-composition machinery is from Valencia–Leyva 2007
(`docs/papers/1-join composition for α-critical graphs.pdf`).

**Definitions.**

- A subset $S \subseteq V(G)$ is *stable* (independent) if no two vertices
  of $S$ are adjacent. The *stability number* (independence number) is
  $\alpha(G) = \max\{|S| : S \text{ stable}\}$.
- $G$ is **α-critical** if $\alpha(G \setminus e) > \alpha(G)$ for every
  edge $e \in E(G)$. Equivalently, every edge is α-critical.
- The **defect** is $\delta(G) = |V(G)| - 2\alpha(G) = \tau(G) - \alpha(G)$,
  where $\tau$ is the minimum vertex cover. Erdős–Gallai (1961) proved
  $\delta(G) \geq 0$ on every α-critical graph; the only connected
  α-critical graph with $\delta = 0$ is $K_2$.

The defect is the central invariant: it controls degrees (Hajnal),
classifies small α-critical graphs (Andrásfai, Surányi), and is preserved
or shifted predictably by all the basic constructions (subdivision,
splitting, duplication, edge-vertex composition, 1-join).

---

## 1. Reduction: an α-critical $c_{\log}$-minimizer exists at every $N \geq 10$

The reason α-criticality is worth a document is this reduction.

**Theorem 1.** For every $N \geq 10$, let

$$
c^*(N) \;=\; \min\{c_{\log}(G) : G \text{ K}_4\text{-free}, |V(G)| = N, \Delta(G) \geq 3\}.
$$

Then there is a K₄-free α-critical graph achieving $c^*(N)$.

The hypothesis $\Delta \geq 3$ is needed because $f(d) = d/\ln d$ is
not monotone on $[2, \infty)$ — $f(2) \approx 2.885 > 2.731 \approx f(3)$ —
so an edge whose removal drops $\Delta$ from $3$ to $2$ would *raise*
$c_{\log}$. The hypothesis $N \geq 10$ avoids small-$N$ edge cases
($N \leq 9$ can be checked by direct enumeration); it also keeps the
proof's $\alpha(G^*) \geq \lceil N/3 \rceil$ bound non-trivial.

**Lemma 1.1 (α-critical witness).** Let $S_6$ be the *one-edge odd
subdivision of $K_4$*: take $K_4$ on $\{u, v, w, x\}$ and replace
edge $uv$ with the path $u$–$a$–$b$–$v$. Then $S_6$ is α-critical
with $|V| = 6$, $\alpha = 2$, $\Delta = 3$ (Andrásfai 1967; see
Lemma 3 below). For $N \geq 10$, write $N = 3k + r$ with
$k = \lfloor N/3 \rfloor$ and $r \in \{0, 1, 2\}$, and define

$$
W_N \;=\; S_6 \,\sqcup\, (k - 2) \cdot K_3 \,\sqcup\, R_r,
\qquad R_0 = \emptyset,\ R_1 = K_1,\ R_2 = K_2.
$$

Then $W_N$ is K₄-free, α-critical, $\Delta(W_N) = 3$,
$\alpha(W_N) = \lceil N/3 \rceil$, and

$$
c_{\log}(W_N) \;=\; \frac{\lceil N/3 \rceil \cdot 3}{N \ln 3}.
$$

*Proof.* Each component ($S_6$, $K_3$, $K_2$, $K_1$) is α-critical;
disjoint unions of α-critical graphs are α-critical, since a maximum
stable set decomposes across components. K₄-freeness and
$\Delta(W_N) = 3$ are immediate from the components ($S_6$ has
$\Delta = 3$, all others have $\Delta \leq 2$). Vertex count:
$6 + 3(k-2) + r = N$. Independence number:
$\alpha(S_6) + (k-2)\alpha(K_3) + \alpha(R_r) = 2 + (k - 2) + \mathbb{1}_{r > 0} = k + \mathbb{1}_{r > 0} = \lceil N/3 \rceil$. $\square$

**Proof of Theorem 1.** $c^*(N)$ is a minimum over a finite set, so
attained. Among minimizers, pick one with the **smallest number of
edges**; call it $G^*$. We show $G^*$ is α-critical.

Suppose not: some edge $e \in E(G^*)$ has $\alpha(G^* \setminus e) = \alpha(G^*)$.
Write $G' = G^* \setminus e$; let $d = \Delta(G^*) \geq 3$ and
$d' = \Delta(G') \in \{d, d-1\}$. Three cases.

*$d' = d$:* $c_{\log}(G') = c_{\log}(G^*)$ and $|E(G')| < |E(G^*)|$,
$G'$ feasible — contradicts edge-minimality.

*$d' = d - 1 \geq 3$:* $f(x) = x/\ln x$ is strictly increasing on
$[3, \infty)$, so $c_{\log}(G') < c_{\log}(G^*)$, $G'$ feasible —
contradicts $c^*(N)$.

*$d' = 2$ (so $d = 3$):* Now $G'$ has $\Delta \leq 2$, hence is a
disjoint union of paths, cycles, and isolated vertices. Every such
component has $\alpha / |V| \geq 1/3$, with equality only for
triangles ($K_3$). Triangles tile $N$ only at $3 \mid N$; otherwise
the residue $N \bmod 3$ forces a non-triangle component, raising
$\alpha / N$. The minimum over all tilings is $\alpha(G') = \lceil N/3 \rceil$
(achieved by $\lfloor N/3 \rfloor$ triangles + $R_r$). Hence

$$
c_{\log}(G^*) \;=\; \frac{\alpha(G^*) \cdot 3}{N \ln 3}
\;\geq\; \frac{\lceil N/3 \rceil \cdot 3}{N \ln 3}
\;=\; c_{\log}(W_N).
$$

But $W_N$ is feasible, so $c^*(N) \leq c_{\log}(W_N) \leq c_{\log}(G^*) = c^*(N)$.
Equality throughout: $W_N$ is also a minimizer, and $W_N$ is α-critical.
$\square$

**Operational consequence.** Any SAT / CP-SAT search for the K₄-free
$c_{\log}$ frontier at $N \geq 10$ may add the constraint "$G$ is
α-critical" — equivalently "for every $e$, $\alpha(G \setminus e) > \alpha(G)$" —
without losing any optimum. Combined with Hajnal (Lemma 2) this also
caps $\Delta \leq N - 2\alpha + 1$, narrowing the box scan.

**Remark (sharpness at $3 \mid N$).** When $3 \mid N$ the third case's
lower bound is tight: $\lfloor N/3 \rfloor$ triangles + 1 bridge edge
is a *non-*α-critical minimizer with $c_{\log} = 1/\ln 3$, and $W_N$
is an α-critical minimizer at the same value. The theorem says
α-critical minimizers exist — not that they are unique.

---

## 2. Lemma (Hajnal, 1965): the α-critical degree bound

**Lemma 2 (Hajnal).** If $G$ is α-critical, then for every $v \in V(G)$,

$$
\deg(v) \;\leq\; \delta(G) + 1 \;=\; N - 2\alpha(G) + 1.
$$

In particular, $\Delta(G) \leq N - 2\alpha + 1$.

This is the most directly useful lemma for our problem. Together with
Theorem 1, it gives a closed-form upper bound on $c_{\log}$ over the
α-critical class:

$$
c^*(N) \;\leq\; \min_{\alpha} \frac{\alpha (N - 2\alpha + 1)}{N \, \ln(N - 2\alpha + 1)},
$$

ranging over $\alpha$ for which the box is non-empty
(i.e., $\alpha \cdot (N - 2\alpha + 2) \geq N$ by Caro–Wei). It also
gives a *prune* for SAT search: at fixed $\alpha$ we can cap the
degree variable at $N - 2\alpha + 1$.

**Application to the SAT pipeline.** In `search/sat_exact.py` and
`search/sat_regular.py`, the box scan currently caps $\Delta$ at
$R(3, \alpha+1) - 1$ (the triangle-free-neighborhood Ramsey wall, see
`utils/ramsey.degree_bounds`). Under an α-critical restriction, we can
add the strictly tighter cap $\Delta \leq N - 2\alpha + 1$. For the
regime $N \in [10, 30]$ and $\alpha \approx \sqrt{N}$, the Hajnal cap
is typically smaller than the Ramsey cap by a multiplicative factor.

---

## 3. Lemma (Andrásfai, 1967): defect 2 is rigid

**Lemma 3 (Andrásfai).** If $G$ is a connected α-critical graph with
$\delta(G) = 2$, then $G$ is the *odd subdivision of $K_4$* — i.e.,
obtained from $K_4$ by replacing each edge with an odd-length path.

This is a complete classification at defect 2. Combined with the
defect-1 result (only odd subdivisions of $K_3 = C_3$ — i.e. odd
cycles), it tells us that "thin" α-critical graphs are tree-like
subdivisions of small complete graphs. Any α-critical K₄-free
candidate with $\delta \leq 2$ is therefore either an odd cycle
($\delta = 1$) or an odd subdivision of $K_4$ ($\delta = 2$). In
particular every odd subdivision of $K_4$ contains a $K_4$-minor but
is itself K₄-*free*, so this case is genuinely populated for K₄-free
graphs.

Surányi (1975) extended the classification to defect 3: only odd
subdivisions of $K_5$ plus three specific exceptional graphs (drawn in
the paper). Lovász (1978) proved that for any fixed defect $\delta$,
all α-critical graphs of that defect are obtained from finitely many
"basic" graphs by odd subdivision — a finite-basis theorem.

**Why this matters for $c_{\log}$.** Low-defect α-critical graphs are
sparse subdivisions; their $\Delta$ is small (bounded by $\delta + 1$
via Hajnal) but so is their $\alpha$ relative to $N$. Plugging into
$c_{\log}$ shows they are *bad* for our objective at large $N$
(roughly $c_{\log} \to \infty$), confirming that the interesting
α-critical minimizers live at large defect. Combined with Hajnal, this
isolates the regime to scan: $\delta = N - 2\alpha$ should be of order
$N$, i.e., $\alpha \approx N/2 - O(1)$ is *not* where the minimum is;
the minimum is at $\alpha \approx \sqrt{N}$ or so, which corresponds
to $\delta \approx N - 2\sqrt{N}$ — the high-defect regime where the
basis theorems give no easy classification.

---

## 4. Lemma (Plummer / Theorem 3.4 + Corollary 3.5 in Valencia–Leyva): closed-neighborhood characterization

**Lemma 4 (closed-neighborhood test for α-criticality).** A graph $G$
is α-critical if and only if for every $v \in V(G)$,

$$
G_v \;:=\; G \setminus N[v]
$$

is a *maximal* induced subgraph of $G$ with $\alpha(G_v) = \alpha(G) - 1$.
("Maximal" means: no induced subgraph of $G$ strictly containing $V(G_v)$
also has $\alpha$ equal to $\alpha(G) - 1$.)

Equivalently (Theorem 3.4): every edge of $G$ incident to $v$ is
α-critical iff $G \setminus N[v]$ is a maximal induced subgraph with
$\alpha$ dropped by exactly 1.

This gives a **vertex-local** test for α-criticality: instead of
checking $\alpha(G \setminus e) > \alpha(G)$ for every edge $e$ (an
$O(|E|)$ outer loop, each costing a fresh α-computation), we can check
the closed-neighborhood condition once per vertex. There is also a
nice reformulation: $G$ is α-critical iff for every $v$,
$\alpha(G \setminus v) = \alpha(G)$ AND every maximum stable set of
$G \setminus v$ contains $v$'s entire complement-orbit (informally).

**Algorithmic use.** This underwrites the polynomial-time recognition
algorithm for α-critical graphs of *bounded* α (the Leyva-Barrita 2008
master thesis, ref [12] in the paper, gives complexity $O(|V|^a)$ for
recognizing α-critical graphs with $\alpha = a$ fixed). For our
project, where every α in the cache is exact (CP-SAT-certified), we
already have $\alpha(G)$ and $\alpha(G \setminus N[v])$ cheaply for
every $v$ — so the test reduces to one comparison per vertex.

---

## 5. Lemma (Wessel; Proposition 2.1 + Theorem 3.1 in Valencia–Leyva): 1-join composition for α-critical graphs

**Setup.** Given graphs $G$ and $H$ with induced subgraphs $G_0 \subseteq G$
and $H_0 \subseteq H$, the **1-join composition**
$j(G, G_0, H, H_0)$ has vertex set $V(G) \sqcup V(H)$ and edges

$$
E(j) \;=\; E(G) \cup E(H) \cup \{ \{u, v\} : u \notin V(G_0),\ v \notin V(H_0)\}.
$$

That is: keep both graphs, then add **all** edges between
"$V(G) \setminus V(G_0)$" and "$V(H) \setminus V(H_0)$".

**Lemma 5 (1-join α-additivity).** If $\alpha(G_0) = \alpha(G) - 1$ and
$\alpha(H_0) = \alpha(H) - 1$, then

$$
\alpha\big(j(G, G_0, H, H_0)\big) \;=\; \alpha(G) + \alpha(H) - 1.
$$

Moreover, $j(G, G_0, H, H_0)$ is α-critical iff:

1. $G_0$ and $H_0$ are *maximal* induced subgraphs of $G, H$ with
   $\alpha(G_0) = \alpha(G) - 1$ and $\alpha(H_0) = \alpha(H) - 1$;
2. every edge in $E(G) \setminus E(G_0)$ is α-critical in $G$, and
   symmetrically for $H$;
3. every edge in $E(G_0)$ is either α-critical in $G$ *or* α-critical
   in $G_0$, and symmetrically for $H_0$.

**Why this is useful.** The 1-join is a **construction**, not a
recognition test. It lets us build new α-critical graphs from two
smaller α-critical graphs (or from graphs that are α-critical
"relative to" their distinguished subgraphs). Iterating gives
families of α-critical graphs of arbitrary size — and in particular,
arbitrary α — which we can then test for K₄-freeness (the 1-join
introduces a complete bipartite block between $V(G) \setminus V(G_0)$
and $V(H) \setminus V(H_0)$, so K₄-freeness imposes nontrivial
constraints on the sizes of those sets and the local structure of
$G_0, H_0$).

For our problem, the key calculation is: if $|V(G)| = n_1$,
$|V(H)| = n_2$, $\alpha(G) = a_1$, $\alpha(H) = a_2$, then
$j$ has $N = n_1 + n_2$ vertices and $\alpha(j) = a_1 + a_2 - 1$.
This is **sub-additive** in $\alpha$: stacking blocks via 1-join
*saves* one unit of α per join, which lowers $c_{\log}$ relative to
disjoint union (which is α-additive). The trade-off is that
$\Delta(j) \geq |V(G) \setminus V(G_0)| + \deg_G(v)$ for any
$v \notin V(G_0)$, so naive joining inflates $\Delta$ — the
construction must keep $|V(G) \setminus V(G_0)|$ small.

The block-decomposition experiments in
`funsearch/experiments/block_decomposition/` are an instance of this
strategy: take small α-critical K₄-free blocks, compose via 1-joins
that respect K₄-freeness, and SAT-verify.

---

## 6. Lemma (basic operations preserving α-criticality)

Three elementary operations preserve α-criticality and let us
manipulate witnesses without re-verifying:

**(a) Odd edge subdivision.** Given $G$ α-critical and an edge
$e = \{u, v\}$, the *odd subdivision* $s(G, e)$ replaces $e$ by a
length-3 path $u - u' - v' - v$ (introducing two new vertices). Then
$s(G, e)$ is α-critical with $\alpha$ increased by $1$ and defect
unchanged.

**(b) Vertex splitting.** Given $G$ α-critical and a vertex $v$ with
$N(v) = N_{v'} \sqcup N_{v''}$ (a non-trivial bipartition of the
neighborhood), the *split* $s(G, v)$ replaces $v$ by a path
$v' - u - v''$, with $v'$ adjacent to $N_{v'}$ and $v''$ adjacent to
$N_{v''}$, and $u$ a new vertex of degree 2. Vertex splitting
generalizes odd edge subdivision (taking $N_{v'} = N(v) \setminus \{w\}$,
$N_{v''} = \{w\}$ recovers $s(G, e)$). Splitting preserves
α-criticality, increases $\alpha$ by 1, defect unchanged.

**(c) Vertex duplication.** Given $G$ α-critical and a vertex $v$,
the *duplicate* $d(G, v)$ adds a twin $v'$ with
$N(v') = N(v) \cup \{v\}$. Then $d(G, v)$ is α-critical with $\alpha$
unchanged and defect increased by $1$. Note $K_n = d(K_{n-1}, v)$ for
any $v$, so the complete graphs are exactly the iterated duplications
of $K_1$.

**Definition.** An α-critical graph is **basic** if it is splitting-free
(equivalently, every vertex has degree $\geq 3$) AND duplication-free.
It is **strongly basic** if additionally it is edge-vertex-composition-free
and 1-join-composition-free. Theorem 5.1 in the paper characterizes when
the 1-join of two graphs is splitting-free, odd-subdivision-free, and
duplication-free.

**Why this matters.** Subdivision *increases* $\alpha$ but also
*increases* $N$ by 2 per edge subdivided, and *cannot decrease*
$\Delta$. So subdivision moves a K₄-free α-critical graph along a
trajectory in the $(N, \alpha, \Delta)$ space whose effect on
$c_{\log}$ is computable: $\alpha \to \alpha + 1$, $N \to N + 2$,
$\Delta$ unchanged, so

$$
c_{\log}(s(G,e)) = \frac{(\alpha+1) \Delta}{(N+2) \ln \Delta}
\;=\; c_{\log}(G) \cdot \frac{(\alpha+1) N}{\alpha (N+2)},
$$

which is $> c_{\log}(G)$ iff $(\alpha+1)N > \alpha(N+2)$, i.e.,
iff $N > 2\alpha$, i.e., iff $\delta(G) > 0$. Since defect zero means
$G = K_2$, every non-trivial subdivision *worsens* $c_{\log}$. So
subdivision moves us *away* from the frontier; the interesting
α-critical K₄-free witnesses are subdivision-irreducible (basic).
This narrows the search to *basic* α-critical K₄-free graphs.

Duplication is more subtle: it preserves $\alpha$, increases $N$ by
1, and can increase $\Delta$ by 1 (the duplicated vertex itself has
the same degree as the original plus the new edge to its twin).
Numerically duplication tends to *worsen* $c_{\log}$ as well — but
duplicating a low-degree vertex of an α-critical graph is the only
way to keep the K₄-free property in many constructions, so it must
be checked case by case.

---

## What to use, where

| Result | Use in the pipeline |
|---|---|
| Theorem 1 | Restrict any optimum search to α-critical K₄-free graphs without loss. |
| Hajnal (Lemma 2) | Add $\Delta \leq N - 2\alpha + 1$ as a SAT prune at every $(N, \alpha)$ box. |
| Andrásfai / Surányi / Lovász basis (Lemma 3 + remarks) | Rule out low-defect graphs as $c_{\log}$ candidates; focus high-defect. |
| Closed-neighborhood test (Lemma 4) | Vertex-local α-criticality verification using the cached α values. |
| 1-join composition (Lemma 5) | Construct new α-critical K₄-free witnesses from blocks; α adds sub-additively. |
| Basic operations (Lemma 6) | Restrict to *basic* α-critical graphs (subdivision-, splitting-, duplication-free); subdivision provably worsens $c_{\log}$. |

---

## References

- Valencia, C.E., Leyva, M.I. *1-join composition for α-critical
  graphs*. arXiv:0707.4085v2, 27 Jul 2007.
  (`docs/papers/1-join composition for α-critical graphs.pdf`)
- Erdős, P., Gallai, T. *On the minimal number of vertices
  representing the edges of a graph*. Magyar Tud. Akad. Mat. Kut.
  Int. Közl. 6 (1961), 181–203.
- Hajnal, A. *A theorem on $k$-saturated graphs*. Canad. J. Math.
  17 (1965), 720–724.
- Andrásfai, B. *On critical graphs*. In: *Theory of Graphs*
  (Internat. Sympos., Rome 1966), Gordon and Breach (1967), 9–19.
- Surányi, L. *On line critical graphs*. In: *Infinite and Finite
  Sets* (Coll. Math. Soc. J. Bolyai 10), North-Holland (1975),
  1411–1444.
- Lovász, L. *Some finite basis theorems in graph theory*. In:
  *Combinatorics* (Proc. Fifth Hungarian Colloq., Keszthely 1976),
  Colloq. Math. Soc. J. Bolyai 18, vol. II, North-Holland (1978),
  717–729.
- Plummer, M.D. *On a family of line-critical graphs*. Monatsh.
  Math. 71 (1967), 40–48.
- Wessel, W. *Kanten-kritische Graphen mit der Zusammenhangszahl 2*.
  Manuscripta Math. 2 (1970), 309–334.
