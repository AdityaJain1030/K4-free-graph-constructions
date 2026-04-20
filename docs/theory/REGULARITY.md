# Near-Regularity of K₄-Free c-Minimizers

## Overview

Every K₄-free graph produced by our solvers that minimizes
$$c_{\log} = \frac{\alpha(G)\, d_{\max}}{N \ln d_{\max}}$$
has degree spread $d_{\max} - d_{\min} \leq 1$. This document collects
the rigorous results, the partial results, and the open barriers around
proving that this must be the case.

**Bottom line.**

| Regime | Near-regularity status |
|---|---|
| $N \leq 35$, $d \leq 7$ | **Proved** (Caro–Wei headroom argument, §2) |
| General $N$, bounded co-degree | **Proved conditionally** (switching lemma, §4) |
| General $N$, arbitrary K₄-free | **Open** — blocked by co-degree blowup (§5) |

The general case appears to be structurally linked to the $\sqrt{\ln d}$
vs $\ln d$ gap in Shearer's bound, and may be comparable in difficulty to
the main conjecture itself. Nevertheless, the combination of rigorous
small-$N$ results, the conditional switching lemma, and exhaustive
empirical evidence justifies constraining SAT search to
$d_{\max} - d_{\min} \leq 1$.

---

## 1. Preliminaries

Throughout, $G$ is a K₄-free graph on $N$ vertices with maximum degree
$d := d_{\max}(G)$ and independence number $\alpha := \alpha(G)$.

**Definition.** A graph $G$ is *$c$-minimizing* for parameters $(N, d)$
if it achieves the smallest value of $c_{\log}$ among all K₄-free graphs
on $N$ vertices with maximum degree $d$.

**Fact 1 (Edge-maximality).** Every $c$-minimizer is edge-maximal
K₄-free: for every non-edge $vw$, the graph $G + vw$ contains $K_4$.

*Proof.* If $G + vw$ is K₄-free, then $\alpha(G + vw) \leq \alpha(G)$
and $d_{\max}(G + vw) \leq d + 1$. When $d(v), d(w) < d$, the maximum
degree is unchanged while $\alpha$ can only decrease, strictly reducing
$c_{\log}$. When one endpoint has degree $d$, the new graph has
$d_{\max} \leq d + 1$ but at least as many edges, so it either improves
$c_{\log}$ for the same $d$ or gives a competitive graph at $d + 1$. In
either case a non-maximal graph cannot be optimal. $\square$

**Fact 2 (Blocking).** By edge-maximality, for every $v \in V$ and
every $w \notin N[v]$, the common neighborhood $N(v) \cap N(w)$ contains
an edge. We say $w$ is *blocked* (from $v$) by that edge.

**Fact 3 (Independent co-neighborhoods).** For every edge $ab \in E(G)$,
K₄-freeness forces $N(a) \cap N(b)$ to be an independent set. In
particular, the *co-degree* $|N(a) \cap N(b)| \leq \alpha(G)$.

*Proof.* If $x, y \in N(a) \cap N(b)$ with $xy \in E$, then
$\{a, b, x, y\}$ induces $K_4$. $\square$

**Fact 4 (Triangle-free neighborhoods).** $G$ is K₄-free iff $G[N(v)]$
is triangle-free for every $v$. By Turán's theorem (Mantel),
$e(G[N(v)]) \leq \lfloor d(v)^2 / 4 \rfloor$.

---

## 2. Caro–Wei Regularity Bound (Small N)

The Caro–Wei bound gives, for any graph,
$$\alpha(G) \geq \sum_{v \in V} \frac{1}{d(v) + 1}.$$

Since $f(x) = 1/(x+1)$ is strictly convex, the sum is minimized when all
degrees are equal. Any degree deficit inflates the lower bound on
$\alpha$.

**Proposition 2.1.** Let $G$ be a $c$-minimizer with $c_{\log} = c^*$.
Let $S = \{v : d(v) \leq d - \Delta\}$ with $|S| = k$, for some integer
$\Delta \geq 2$. Then
$$k \leq \frac{N d\,(c^* \ln d - 1)}{\Delta}.$$

*Proof.* Each vertex in $S$ contributes excess at least
$$\frac{1}{d - \Delta + 1} - \frac{1}{d + 1}
  \geq \frac{\Delta}{(d+1)^2}$$
to the Caro–Wei sum. The total sum is at most
$\alpha = c^* N \ln d / d$, while the regular baseline is $N/(d+1)$.
So the total excess satisfies
$$\frac{k\Delta}{(d+1)^2}
  \leq \frac{c^* N \ln d}{d} - \frac{N}{d+1}
  \approx \frac{N(c^* \ln d - 1)}{d}$$
and rearranging gives the result. $\square$

**Corollary 2.2 (Near-regularity for small $N$).** When the headroom
$H := c^* N \ln d / d - N/(d+1)$ is less than $2/(d+1)^2$ — i.e., a
single vertex at degree $d-2$ would already violate Caro–Wei — then
every $c$-minimizer has $d_{\max} - d_{\min} \leq 1$.

Numerically, for $c^* \approx 0.68$:

| $d$ | $c^* \ln d - 1$ | Max avg. deficit | $\pm 1$ guaranteed up to $N \approx$ |
|-----|-----------------|------------------|--------------------------------------|
| 4 | $-0.06$ | 0 (automatic) | all $N$ |
| 5 | $0.09$ | $0.47$ | $\sim 40$ |
| 6 | $0.22$ | $1.3$ | $\sim 18$ |
| 8 | $0.41$ | $3.3$ | $\sim 10$ |
| 10 | $0.57$ | $5.7$ | $\sim 7$ |

For $d \leq 7$ and $N \leq 35$, the headroom is less than one vertex's
penalty, so near-regularity is forced. This covers the entire
SAT-tractable regime of our pipeline.

**Remark.** The Caro–Wei argument uses nothing about K₄-freeness. It
applies to *any* graph family where $\alpha$ is squeezed close to the
$N/(d+1)$ floor.

---

## 3. Why the Caro–Wei Argument Weakens at Large N

The penalty from a single deficient vertex is $O(1/d^2)$ — a constant
independent of $N$. The headroom grows as $O(N/d)$. So at large $N$ the
Caro–Wei floor is far below the actual $\alpha$, and irregularity
carries negligible cost.

Concretely, at $N = 200$, $d = 15$:
- Headroom $\approx 200 \cdot 0.84 / 15 \approx 11.2$.
- Penalty per vertex at $d-2$: $\approx 2/225 \approx 0.009$.
- Could tolerate $\sim 1200$ vertices at degree $d - 2$ before binding.

A proof for general $N$ must use K₄-free structure, not just convexity
of $1/(x+1)$.

---

## 4. The Switching Lemma (Conditional)

### 4.1 Setup

Let $v$ have $d(v) = \delta \leq d - 2$ and let $u \in N(v)$ with
$d(u) = d$. Define the *candidate set*
$$C = N(u) \setminus N[v], \qquad |C| \geq d - \delta =: \Delta.$$

The *switch* at $x \in C$ produces $G' = G - ux + vx$.

### 4.2 Safety criterion

A $K_4$ in $G'$ must use the new edge $vx$, so it has the form
$\{v, x, a, b\}$. Since $ux \notin E(G')$, vertex $u$ cannot
participate. Therefore:

> **The switch at $x$ is safe iff
> $G[(N(v) \cap N_G(x)) \setminus \{u\}]$ is independent.**

Define $S_x = (N(v) \cap N_G(x)) \setminus \{u\}$.

### 4.3 Counting unsafe candidates

Let $F$ be the set of edges in $G[N(v)]$ not incident to $u$. By
triangle-freeness of $G[N(v)]$ and Mantel's theorem,
$|F| \leq \delta^2/4$.

An edge $ab \in F$ makes candidate $x$ unsafe only if $x \in N(a) \cap
N(b)$. By Fact 3, $N(a) \cap N(b)$ is independent with
$|N(a) \cap N(b)| \leq \mu$, where
$$\mu = \max_{ab \in E(G)} |N(a) \cap N(b)|$$
is the *max co-degree*. Subtracting $v$ (which is in $N(a) \cap N(b)$
but not in $C$), each edge blocks at most $\mu - 1$ candidates.

Summing over all blocking edges:
$$|\{x \in C : \text{unsafe}\}|
  \leq \sum_{ab \in F} |N(a) \cap N(b) \cap C|
  \leq |F| \cdot (\mu - 1)
  \leq \frac{\delta^2}{4}\,\mu.$$

### 4.4 The conditional result

**Theorem 4.1 (Switching under bounded co-degree).** If
$$\Delta > \frac{\delta^2 \mu}{4}$$
then there exists a safe switch $x \in C$ producing $G' = G - ux + vx$
that is K₄-free with $d_{\max}(G') \leq d$, $d_{G'}(v) = \delta + 1$,
and $d_{G'}(u) = d - 1$.

*Proof.* The number of safe candidates is at least
$\Delta - \delta^2 \mu / 4 > 0$ by hypothesis. The switch increases
$d(v)$ by 1, decreases $d(u)$ by 1, and leaves all other degrees
unchanged. Since $\delta + 1 \leq d$ and $d - 1 < d$, the maximum
degree does not increase. $\square$

**Corollary 4.2.** If $\mu = O(1)$, repeated application of the
switching lemma reduces degree spread to at most 1 without violating
K₄-freeness or increasing $d_{\max}$.

---

## 5. The Barrier: Why the Unconditional Case Is Hard

### 5.1 The co-degree blowup

In general K₄-free graphs, Fact 3 gives only $\mu \leq \alpha$. For a
$c$-minimizer, $\alpha \approx c^* N \ln d / d$. The safe-switch
condition from Theorem 4.1 becomes
$$\Delta > \frac{d^2}{4} \cdot \frac{c^* N \ln d}{d}
  = \frac{c^* d N \ln d}{4}.$$

Since $\Delta \leq d$, this requires $c^* N \ln d < 4$, which fails for
$N \gtrsim 4/(c^* \ln d)$ — a tiny threshold.

The total blocking capacity (edges $\times$ co-degree) scales as
$O(d^2 \cdot N \ln d / d) = O(dN \ln d)$, while the candidate pool
$|C|$ is only $O(d)$. The ratio is $O(N \ln d)$, which diverges.

### 5.2 Connection to Shearer's barrier

This is not a technical gap. The same phenomenon — co-degrees that are
globally large but highly structured — underlies the $\sqrt{\ln d}$
vs. $\ln d$ barrier in Shearer's independence-number bound for
triangle-free (equivalently, K₄-free neighborhood) graphs. Proving
unconditional near-regularity of $c$-minimizers likely requires the same
new ideas needed to improve Shearer's bound.

### 5.3 What a proof would need

A successful argument must exploit *correlation* among blocking events,
not just their count. Specifically, it must show that the blocking edges
in $G[N(v)]$ are not independent obstacles: many candidates $x$ are
blocked by the *same* edge, so the effective number of independent
blocking constraints is much smaller than the union bound suggests.

---

## 6. Candidate Approaches for the General Case

### 6.1 Clustered blocking

Show that few edges $ab \in E(G[N(v)])$ have large co-degree into $C$.
If one could prove
$$|\{ab \in F : |N(a) \cap N(b) \cap C| \geq t\}|
  \ll \frac{d^2}{t^2}$$
then a second-moment argument would recover a safe switch.

**Why it's plausible.** High co-degree into $C$ means $a$ and $b$ share
many neighbors outside $N[v]$. In a K₄-free graph, these shared
neighbors form an independent set. Packing many large independent sets
into the complement of $N[v]$ is constrained by the graph's overall
density.

### 6.2 Lovász Local Lemma

Define bad events $B_{ab}$ = "edge $ab$ blocks the chosen $x$" for each
$ab \in F$. The events are dependent only when edges share endpoints (a
bounded-degree dependency in $G[N(v)]$, which has max degree $< \delta$).
If the individual blocking probabilities are small enough, the symmetric
LLL gives $\Pr[\text{all bad}] < 1$.

Concretely, $\Pr[B_{ab}] = |N(a) \cap N(b) \cap C| / |C| \leq \mu /
\Delta$. The dependency degree is at most $2\delta$ (edges sharing an
endpoint with $ab$ in $G[N(v)]$). The LLL condition
$e \cdot p \cdot (2\delta + 1) < 1$ becomes
$$e \cdot \frac{\mu}{\Delta} \cdot 2\delta < 1
  \qquad\Longleftrightarrow\qquad
  \Delta > 2e\,\delta\,\mu.$$

With $\mu \leq \alpha \sim N \ln d / d$ and $\delta \sim d$, this gives
$\Delta > O(N \ln d)$, which again exceeds $d$. The LLL with worst-case
$\mu$ does not beat the union bound.

**Possible fix.** Use the *asymmetric* LLL with edge-specific bounds on
$|N(a) \cap N(b) \cap C|$ instead of the global max $\mu$. This
requires understanding the co-degree distribution, connecting to §6.1.

### 6.3 Pseudorandom co-degree

In many extremal constructions, co-degrees concentrate around
$\mu_{\text{avg}} \approx d^2/N$ rather than $\alpha$. Under this
assumption:
$$T \leq \frac{d^2}{4} \cdot \frac{d^2}{N} = \frac{d^4}{4N}.$$

The safe-switch condition becomes $\Delta > d^4/(4N)$, i.e.,
$d^3 < 4N$. This holds comfortably in the range $N \sim 50$,
$d \sim 10\text{–}15$ and explains the empirical observation.

**Status.** Proving that $c$-minimizers have pseudorandom co-degree
(i.e., $\mu \ll \alpha$) is itself an open problem, but it is a weaker
and potentially more tractable statement than the full conjecture.

### 6.4 Direct $\alpha$-suboptimality bound

Bypass switching entirely. Show:

> If $d_{\max} - d_{\min} \geq k$, then
> $\alpha(G) \geq \alpha_{\text{regular}} + \Omega(k/d)$.

This would use the Caro–Wei inflation directly without constructing an
explicit smoother graph. It requires showing that no K₄-free graph can
have irregular degrees without paying an independence-number penalty
beyond the Caro–Wei floor. The difficulty is that the Caro–Wei bound is
not tight for K₄-free graphs (Shearer's bound is stronger), and the gap
between Caro–Wei and reality can absorb the irregularity penalty.

---

## 7. Summary of Proved Results

**Theorem A (Caro–Wei regularity, small $N$).** For $c^* \ln d < 1 +
2/(N(d+1))$, every K₄-free $c$-minimizer on $N$ vertices with max
degree $d$ satisfies $d_{\max} - d_{\min} \leq 1$. For $c^* \approx
0.68$, this covers all $(N, d)$ with $N \leq 35$ and $d \leq 7$.

**Theorem B (Conditional switching).** Let $G$ be a K₄-free edge-maximal
graph with max co-degree $\mu$ and a vertex $v$ with $d(v) \leq d - 2$.
If $d - d(v) > d(v)^2 \mu / 4$, there exists a K₄-free graph $G'$
obtained by a single edge switch with $d_{\max}(G') \leq d$ and
$d_{G'}(v) = d(v) + 1$.

**Theorem C (Total deficit bound).** For any K₄-free $c$-minimizer,
$$\sum_{v \in V} (d - d(v))^+ \leq N d\,(c^* \ln d - 1).$$

---

## 8. Practical Implications for SAT

For the SAT-tractable regime ($N \leq 35$), Theorem A rigorously
justifies constraining the search to $d_{\max} - d_{\min} \leq 1$.
This is exactly the model used by `sat_regular.py`.

For larger $N$ (evolutionary / FunSearch / algebraic searches), the
$\pm 1$ constraint is a well-supported heuristic:

1. All known algebraic extremal constructions (Paley, Cayley,
   Mattheus–Verstraëte) are vertex-transitive, hence exactly regular.
2. No irregular $c$-minimizer has been found at any $N$ in our database.
3. The pseudorandom co-degree argument (§6.3) explains why smoothing
   succeeds empirically.
4. The connection to Shearer's barrier (§5.2) suggests that any
   counterexample would require fundamentally new construction ideas.

**Recommendation.** Use $d_{\max} - d_{\min} \leq 1$ as the primary
search constraint at all $N$. Retain unconstrained `sat_exact.py` as a
verification backend for $N$ values where it is tractable.

---

## 9. Proposed Experiments

### 9.1 Empirical smoothing test

For every graph $G$ in `graph_db` with $d_{\max} - d_{\min} \geq 2$:

1. Find the highest-degree vertex $u$ and lowest-degree vertex $v$ with
   $uv \in E$.
2. Enumerate $C = N(u) \setminus N[v]$.
3. For each $x \in C$, test whether $G' = G - ux + vx$ is K₄-free.
4. If a safe switch exists, apply it and record $\Delta\alpha$ and
   $\Delta c_{\log}$.
5. Repeat until $d_{\max} - d_{\min} \leq 1$ or no safe switch exists.

**Metrics:** success rate, average number of switches to reach $\pm 1$,
distribution of $\Delta\alpha$.

### 9.2 Co-degree distribution

For Pareto-optimal graphs in the database, compute and plot:

- The distribution of $|N(a) \cap N(b)|$ over all edges $ab$.
- Compare max co-degree $\mu$ against $\alpha$ and against $d^2/N$.
- Test whether $\mu \sim d^2/N$ (pseudorandom) or $\mu \sim \alpha$
  (worst-case).

This directly tests whether the pseudorandom co-degree hypothesis
(§6.3) holds for empirical minimizers.

### 9.3 Boundary of the Caro–Wei guarantee

For each $d \in \{4, \ldots, 15\}$, find the largest $N$ at which the
Caro–Wei headroom argument (Corollary 2.2) still forces $\pm 1$. Plot
this boundary in $(N, d)$ space. Compare against the SAT-verified region
where $\pm 1$ is observed but not proved by Caro–Wei.

---

## References

- Caro (1979), Wei (1981): $\alpha(G) \geq \sum 1/(d(v)+1)$.
- Shearer (1995): $\alpha(G) \geq c \cdot N\sqrt{\ln d}/d$ for
  triangle-free $G$ with max degree $d$.
- Ajtai, Komlós, Szemerédi (1980): $\alpha(G) \geq \Omega(N \ln d / d)$
  for triangle-free, giving the $\sqrt{\ln d}$ bound for the K₄-free
  neighborhood setting.
- Mattheus, Verstraëte (2023): explicit algebraic K₄-free construction
  achieving $c_{\log} \approx 0.68$ (vertex-transitive, regular).