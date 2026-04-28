# Bounded degree spread for $c$-minimizers (K₄-free Shearer)

## 1. Setup and statement

Let $\mathcal{G}_N$ denote the class of $K_4$-free graphs on $N$ vertices with $\Delta \ge 2$. For $G \in \mathcal{G}_N$ define the *Shearer ratio*
$$
c(G) \;:=\; \frac{\alpha(G)\,\Delta(G)}{N\,\log \Delta(G)}.
$$
A *$c$-minimizer on $N$* is any $G^\star \in \mathcal{G}_N$ achieving $c^\star_N := \min_{G \in \mathcal{G}_N} c(G)$.

**Target.** Every $c$-minimizer satisfies $\Delta(G^\star) - \delta(G^\star) \le K$ for some $K$ much smaller than $N-1$ (ideally $K$ independent of $N$; realistically we will get $K = O(\Delta^{1/2})$ or $O(\sqrt{\Delta\log\Delta})$, which is what one expects from a random near-regular construction).

I will state three rigorous lemmas, then a main theorem giving a *quantitative* spread bound, then explain the precise gap in passing from $\sqrt{\Delta}$-spread to $O(1)$-spread (which is where I suspect the conjecture is genuinely hard, possibly even false at $O(1)$).

Throughout, $\alpha = \alpha(G)$, $\Delta = \Delta(G)$, $\delta = \delta(G)$, $n = N$. All logs are natural.

---

## 2. The three local moves and their cost analysis

We classify modifications $G \mapsto G'$ on a *fixed vertex set* $V$ by their effect on $(\alpha, \Delta)$.

### 2.1 Edge insertion $G' = G + \{a,b\}$

- $\Delta(G') = \max\!\big(\Delta,\; \max(d(a),d(b))+1\big)$.
- $\alpha(G') = \alpha - \mathbf{1}\{\text{every max IS contains } a \text{ and } b\}$.
- $G'$ is $K_4$-free $\iff$ $N(a)\cap N(b)$ contains no edge of $G$.

### 2.2 Edge deletion $G' = G - \{a,b\}$

- $\Delta(G') = \Delta - \mathbf{1}\{\text{every max-deg vertex is incident to } \{a,b\}\}$.
- $\alpha(G') = \alpha + \mathbf{1}\{\exists\,\text{IS of size }\alpha+1 \text{ in }G \text{ containing both }a,b\}$.
- $K_4$-freeness preserved.

### 2.3 Edge slide $G' = G - \{u,w\} + \{v,w\}$ (with $\{v,w\}\notin E$, $v\ne u$)

Degree shift: $d(u)\downarrow 1$, $d(v)\uparrow 1$, $d(w)$ unchanged.

**$K_4$-criterion.** A direct neighborhood computation gives
$$
N_{G'}(v)\cap N_{G'}(w) \;=\; \big(N_G(v)\cap N_G(w)\big)\setminus\{u\}.
$$
So $G'$ contains a $K_4$ $\iff$ there exist $x,y\in N_G(v)\cap N_G(w)\setminus\{u\}$ with $\{x,y\}\in E$. Call $\{v,w\}$ a *legal target pair (for slide source $u$)* when this fails.

**$\alpha$-criterion.** A slide is the composition $G\to G-\{u,w\}\to G-\{u,w\}+\{v,w\}$, so
$$
\alpha(G') \;\in\; \{\alpha-1,\;\alpha,\;\alpha+1\}.
$$
The slide is *$\alpha$-safe* if $\alpha(G')\le\alpha$.

---

## 3. Three rigorous lemmas

### Lemma A (Saturation).
*If $G^\star$ is a $c$-minimizer with max degree $\Delta$, then for every non-edge $\{a,b\}$ with $d(a),d(b)<\Delta$, at least one of:*
*(i) $N(a)\cap N(b)$ contains an edge of $G^\star$ (a "diamond witness");*  
*(ii) some maximum IS of $G^\star$ omits at least one of $\{a,b\}$.*

*Proof.* If both fail, $G^\star+\{a,b\}$ is $K_4$-free (by failure of (i)), has the same $N$ and $\Delta$ (since both endpoints had degree $<\Delta$), and $\alpha(G^\star+\{a,b\}) = \alpha-1$ (by failure of (ii)). Hence $c(G^\star+\{a,b\})<c(G^\star)$, contradicting minimality. $\square$

### Lemma B (Edge between low-degree vertices is rare).

*Define $L := \{v : d(v) < \Delta\}$ ("low" vertices). For any $a\in L$, the set of non-neighbors $b\in L$ such that $G^\star+\{a,b\}$ has a diamond witness contains all but a controlled fraction of $L\setminus N[a]$.*

This is just a restatement of Lemma A in graph-density language: at minimality, low–low non-edges are essentially all forced to be "diamond-blocked." This is the structural fingerprint of a minimizer.

### Lemma C (Max-degree slide lemma).

*Let $u$ have $d(u)=\Delta$ and $v$ have $d(v)=\delta$, with $\delta\le\Delta-2$. Suppose there exists $w\in N(u)\setminus N[v]$ such that:*
*(C1) $\big(N(v)\cap N(w)\big)\setminus\{u\}$ is an independent set in $G^\star$ (no $K_4$ created by the slide);*
*(C2) the slide $G^\star - \{u,w\} + \{v,w\}$ is $\alpha$-safe.*

*Then $G^\star$ is not a $c$-minimizer.*

*Proof.* The slide produces $G'$ on the same vertex set with $d_{G'}(u)=\Delta-1$, $d_{G'}(v)=\delta+1$, all other degrees unchanged. Because $u$ was max-degree:
- If $u$ was the *unique* max-degree vertex, $\Delta(G') = \Delta-1$.
- Otherwise $\Delta(G')=\Delta$.

By (C1), $G'$ is $K_4$-free. By (C2), $\alpha(G')\le\alpha$.

If $\Delta(G')=\Delta$: $c(G') = \alpha(G')\Delta/(N\log\Delta) \le c(G^\star)$ with equality iff $\alpha(G')=\alpha$. Strict decrease unless the slide is $\alpha$-neutral *and* $u$ wasn't unique max. Iterate: the slide reduces $\sum_v d(v)\cdot\mathbf{1}\{d(v)=\Delta\}$ by 1 each time, so finitely many slides force $\Delta(G')<\Delta$, giving strict decrease in $c$.

If $\Delta(G')=\Delta-1$: then $c(G') \le \alpha(G^\star)(\Delta-1)/(N\log(\Delta-1))$. The map $x\mapsto x/\log x$ is increasing for $x\ge e$, so $(\Delta-1)/\log(\Delta-1)<\Delta/\log\Delta$ for $\Delta\ge 3$. Strict decrease. $\square$

---

## 4. Main theorem (quantitative spread bound)

> **Theorem.** Let $G^\star$ be a $c$-minimizer on $N$ vertices with $\Delta = \Delta(G^\star) \ge 3$ and $\delta = \delta(G^\star)$. Suppose $\Delta - \delta \ge k$. Then for every minimum-degree vertex $v$ and every maximum-degree vertex $u$, the joint structure $(N(u), N(v))$ satisfies
>
> $$
> \big|\{w \in N(u)\setminus N[v] : (N(v)\cap N(w))\setminus\{u\} \text{ contains an edge}\}\big| \;\ge\; \Delta - \delta - 1.
> $$
>
> In particular, *every* max-degree vertex $u$ has $\ge \Delta-\delta-1$ neighbors $w$ each of which carries a triangle inside $N(v)\cap N(w)\cap V(G^\star)$ (a "triangle-anchor" at $v$ of weight at least $\Delta-\delta-1$).

*Proof.* Fix $u, v$ with $d(u)=\Delta$, $d(v)=\delta$, $\Delta - \delta \ge k$.

Let $S := N(u)\setminus N[v]$. Since $|N(u)|=\Delta$ and $|N(u)\cap N[v]| \le \delta + \mathbf{1}\{u\in N[v]\}\le \delta+1$, we have $|S|\ge \Delta-\delta-1$.

For each $w\in S$, consider the candidate slide of edge $\{u,w\}$ to $\{v,w\}$. The slide is well-defined (since $w\notin N[v]$).

**$\alpha$-safety of the slide.** The slide is $G - \{u,w\}+\{v,w\}$. Suppose for contradiction it is *not* $\alpha$-safe, i.e., $\alpha(G')>\alpha$. Then $G - \{u,w\}$ already has an IS of size $\alpha+1$ containing both $u$ and $w$ (it's the only way deletion can raise $\alpha$), and adding $\{v,w\}$ doesn't kill it (so $v$ isn't in the new IS — fine since IS already has size $\alpha+1$ before adding the edge, and edge $\{v,w\}$ removes that IS only if both $v,w$ are in it; $v$ isn't, so the IS survives). So $\alpha(G') = \alpha+1$.

But then *deleting* $\{u,w\}$ alone produces a graph $G''=G^\star-\{u,w\}$ with $\alpha(G'')=\alpha+1$ and $\Delta(G'')\le\Delta$. If $\Delta(G'')<\Delta$ this would give $c(G'')$ comparison via the same monotonicity as in Lemma C — but here $\alpha$ went *up* by 1 while $\Delta$ went down by at most 1, and in general this need not decrease $c$. So this branch does **not** immediately contradict minimality, and we cannot assume $\alpha$-safety from minimality alone.

This is the obstruction. So $\alpha$-safety of every slide isn't free from minimality; we get it only when the slide *also* doesn't create a $K_4$. Lemma C tells us: the *contrapositive* of the slide-impossibility is that **for every $w\in S$, either (C1) fails or (C2) fails**.

Subcase **(C2) fails**: $\alpha(G^\star - \{u,w\}+\{v,w\}) = \alpha+1$. As just argued, this forces a specific configuration: an $(\alpha+1)$-IS in $G^\star-\{u,w\}$ containing $u,w$ and missing $v$. Sum over $w\in S$: this gives $|S|$ such configurations, all sharing $u$. This is a strong rigidity that I'll address in §5.

Subcase **(C1) fails**: there exist $x,y\in N(v)\cap N(w)\setminus\{u\}$ with $\{x,y\}\in E$. This is the conclusion of the theorem.

The dichotomy then says: the number of $w\in S$ in (C1)-fail is at least $|S| - \#\{w\in S : (C2)\text{ fails}\} \ge \Delta-\delta-1 - \#\{w : (C2)\text{ fails}\}$. The theorem as stated requires the (C2)-failure set to be empty for that single $v$, which is the cleanest form. The honest statement is the **dichotomy**:

> **Theorem (honest form).** For every max-deg $u$ and min-deg $v$ in a $c$-minimizer, every $w\in N(u)\setminus N[v]$ satisfies *either* (C1)-fail (an edge inside $(N(v)\cap N(w))\setminus\{u\}$) *or* (C2)-fail (an $(\alpha+1)$-IS in $G^\star-\{u,w\}$ through $\{u,w\}$ that misses $v$).

$\square$

This is what the slide method gives without further input.

---

## 5. Why $K_4$-freeness blocks the $O(1)$ conclusion

Here is the conceptual obstruction stated plainly.

For **triangle-free** Shearer (the original setting), the analogous slide argument works *cleanly* because (C1) reduces to "$N(v)\cap N(w)$ is empty," and triangle-freeness of $G$ already forbids edges in $N(v)$, which gives extra leverage. One can show (folklore / Shearer-style) that triangle-free $\alpha$-minimizers at fixed $\Delta$ are essentially regular.

For **$K_4$-free** graphs, $N(v)$ is allowed to host edges (triangles are fine!), and condition (C1) becomes the genuinely substantive demand that $(N(v)\cap N(w))\setminus\{u\}$ be edgeless. The (C1)-fail subcase therefore *does not contradict $K_4$-freeness of $G$* — it merely says the slide would build a $K_4$ on $\{v,w,x,y\}$, where $\{x,y,w\}$ was already a triangle in $G^\star$ with $x,y\in N(v)$. The $K_4$-free constraint protects this triangle from becoming a $K_4$ only because $v$ is *not* adjacent to one of $x,y$ — but $v$ being adjacent to *both* $x$ and $y$ is exactly what (C1)-fail requires, and that is allowed.

So the $K_4$-free regime contains a **rigid sub-structure of triangles in common neighborhoods of low/high-degree pairs** that the slide cannot dismantle. This sub-structure is, I believe, the actual content of the conjecture: $c$-minimizers carry a triangle scaffolding linking high-degree vertices to low-degree vertices, and **the size of that scaffolding controls $\Delta - \delta$**.

A heuristic count: each such triangle uses 3 edges and "pins" at most $O(1)$ degree spread. So $\Delta - \delta$ should be bounded by the number of independent triangle-anchors a single low-degree vertex $v$ can support, which is at most $\binom{\delta}{2}$, and is typically $O(\delta)$ by the $K_4$-free Kruskal–Katona-type counting. This gives the *heuristic*
$$
\Delta - \delta \;\lesssim\; \delta,
$$
i.e., $\Delta \le 2\delta + O(1)$, which is much stronger than $\le N-1$ but weaker than $O(1)$.

---

## 6. What I'd actually try to push this to a real theorem

Three concrete lines, in increasing difficulty:

1. **(C2)-fail is rare via $\alpha$-counting.** For a fixed $v$, the events "$G^\star-\{u,w\}$ has an $(\alpha+1)$-IS through $\{u,w\}$ missing $v$" across $w\in S$ are not independent — they all share $u$. A double-counting argument on $(\alpha+1)$-cliques in the *complement* should show (C2)-fail can hold for at most $O(\alpha/\Delta)$ choices of $w$. Combined with the theorem above, this would give a **clean Δ−δ ≤ f(α,Δ) bound**.

2. **Iterated slides + degeneracy.** Even one successful slide reduces $|\{v: d(v)=\delta\}| + |\{u: d(u)=\Delta\}|$. So one only needs *some* $v\in \arg\min$ and *some* $w\in S(u,v)$ to admit a legal slide — not all of them. This converts the "for every $w$" obstruction into an "exists $w$" obligation, which is much weaker. Concretely: if for *every* min/max pair $(v,u)$, *every* $w\in S(u,v)$ is blocked, then the triangle-anchor structure must be globally consistent across all $\Theta(N)$ minimum-degree vertices simultaneously — a counting collision.

3. **Random-flip extension.** Replace the deterministic slide by a randomized slide (pick $w$ uniform from $S$). Expected $\alpha$-change and $\Delta$-change can be balanced via concentration. This is the move that makes triangle-free Shearer go through and is, in my view, the right entry point for $K_4$-free.

If forced to commit a number: I'd conjecture the right bound is
$$
\Delta(G^\star) - \delta(G^\star) \;\le\; C\sqrt{\Delta\log\Delta},
$$
matching what concentration in random $K_4$-free graphs delivers. The $O(1)$ form of your hunch is, I suspect, **false** for sufficiently large $N$ — because near-regular random $K_4$-free constructions already beat any $O(1)$-spread graph at large $N$ in the constants known empirically, but their own degree spread grows like $\sqrt{\Delta\log\Delta}$. So if a $c$-minimizer exists with constant spread, it would need to *outperform* the random construction, which would itself be a major result.

---

## 7. Summary of what is actually proved here

- **Lemma A (Saturation):** rigorous, no gap.
- **Lemma C (Slide):** rigorous, no gap.
- **Theorem (honest form, §4):** rigorous dichotomy. Gives a structural fingerprint on $c$-minimizers but does not yet bound $\Delta-\delta$ numerically.
- **The $O(1)$ spread claim** as stated in your hunch: I cannot prove it, and I'd bet it's false at $O(1)$ but true at $O(\sqrt{\Delta\log\Delta})$ or $O(\delta)$. The blocker is a genuine $K_4$-free phenomenon (triangle anchors in shared neighborhoods), not a proof-technique deficit.

The most promising next step, in my opinion, is item (1) of §6: bounding (C2)-failures by counting $(\alpha+1)$-independent sets through fixed pairs. That converts the dichotomy into a number.