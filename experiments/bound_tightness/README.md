# `experiments/bound_tightness/` — how tight are α bounds on the frontier?

## Compute

- **Environment:** `k4free` conda env (cvxpy + SCS for SDP/LP, networkx, numpy).
- **Typical runtime:** ~7 s for the default benchmark (43 graphs, $n \le 25$, $c_{\log} \le 0.74$). Hard-core dominates as $n$ approaches 22.
- **Memory:** trivial (< 200 MB peak).
- **Parallelism:** single-threaded.

---

## Background

The whole repository is a hunt for $K_4$-free graphs that minimise

$$
c_{\log}(G) \;=\; \frac{\alpha(G)\,\Delta(G)}{N \,\ln \Delta(G)},
$$

so anything that bounds $\alpha(G)$ feeds directly into bounds on $c_{\log}$. We need both *upper* and *lower* bounds on $\alpha$:

- An upper bound $\alpha(G) \le B(G)$ gives a *lower* bound on $c_{\log}$ in the form $c_{\log}(G) \le B(G)\,\Delta(G) / (N\ln\Delta(G))$ — so the smaller $B$, the better the certificate.
- A lower bound $\alpha(G) \ge L(G)$ gives an *upper* bound on $c_{\log}$ — so a tight $L$ tells us the true $c_{\log}$ can't be much smaller than what we observe.

Every known method for bounding $\alpha$ on a general graph falls into one of four families:

| Family | Tool | Bound direction |
|---|---|---|
| Spectral | Hoffman ratio bound $H$ | upper |
| SDP | Lovász $\vartheta$, Schrijver $\vartheta'$ | upper |
| LP | fractional clique cover $= \chi_f(\bar G)$ | upper |
| Probabilistic | hard-core occupancy $\mathbb{E}_\mu[\lvert I\rvert]$ | lower |

For any graph,

$$
\alpha(G) \;\le\; \vartheta'(G) \;\le\; \vartheta(G) \;\le\; \chi_f(\bar G) \;\le\; \chi(\bar G),
$$

and additionally $\alpha(G) \le H(G)$ when $G$ is regular. There is no general inequality between $H$ and $\vartheta$ — they coincide on vertex-transitive graphs and can split either way otherwise.

The frontier of $K_4$-free graphs in `graph_db` is small enough to score every method against the exact $\alpha$ (computed via CP-SAT and cached) and report tightness ratios. **The point of this benchmark:** for any method that proves a lower bound on $c_{\log}$ universally, the proof on a *specific* graph $G$ cannot do better than $B(G)\,\Delta(G)/(N\ln\Delta(G))$, so if every $B/\alpha$ on the frontier is bounded below by some $\rho > 1$, no proof in that family can beat $\rho \cdot c_{\log}(G^*)$ on the leader $G^* =$ Paley(17).

The bound chain and individual proofs are derived in `docs/theory/SUBPLAN_B.md` (rungs 0–3) and `docs/theory/HARDCORE_TIGHTNESS.md`.

---

## Question

For each $\alpha$ bound in the four families above (and the cheap greedy clique cover), how close to the exact $\alpha$ does it land on the lowest-$c_{\log}$ $K_4$-free graphs in the DB?

---

## Approach

1. Pull every $K_4$-free graph from `graph_db` with $c_{\log} \le c_{\max}$ and $n \le n_{\max}$ (defaults $0.74$ and $25$ — covers Paley(17), the lifted Paley plateau chain, all SAT-certified optima up to $n = 25$, and the dihedral / circulant frontier).
2. Run all six bounds on each graph using `utils.alpha_bounds`.
3. Score by $B / \alpha$ (upper) or $\alpha / L$ (lower). Both are $\ge 1$; closer to $1$ = tighter.
4. Aggregate per-method statistics and a per-graph table go to `results.csv`; the human-readable digest lands in `results.md`.

The benchmark is read-only — graphs come from `graph_db`, no producer is involved.

---

## The bounds

### 1. Hoffman ratio bound

For a $d$-regular graph $G$ with adjacency-matrix eigenvalues $\lambda_1 = d \ge \lambda_2 \ge \dots \ge \lambda_N = \lambda_{\min}$,

$$
H(G) \;=\; \frac{N \cdot (-\lambda_{\min})}{d - \lambda_{\min}}, \qquad \alpha(G) \;\le\; H(G).
$$

**Derivation sketch.** Let $S$ be an independent set with indicator vector $\mathbf{1}_S$ and write $\mathbf{1}_S = \tfrac{|S|}{N}\mathbf{1} + w$, where $w \perp \mathbf{1}$. Independence gives $\mathbf{1}_S^\top A \mathbf{1}_S = 0$. Decomposing along the eigenbasis of $A$, the all-ones direction contributes $\tfrac{|S|^2}{N} \cdot d$ and the orthogonal complement contributes at least $\lambda_{\min} \|w\|^2$. Setting the sum to zero and rearranging yields the bound. Equality holds precisely when $w$ lies in the $\lambda_{\min}$-eigenspace.

**Why useful:**
- $\mathcal{O}(N^3)$ — diagonalise $A$ once, plug into the formula.
- Saturated by every graph whose adjacency-matrix structure projects an MIS cleanly onto the bottom eigenspace. **Strongly regular graphs always saturate this bound**: for an SRG with parameters $(v, k, \lambda, \mu)$ and smallest non-trivial eigenvalue $s$, the bound $\alpha(G) \le v\lvert s\rvert / (k + \lvert s\rvert)$ is exact.
- The Hoffman saturation ratio $\alpha/H$ is the standard "is this graph spectrum-extremal?" diagnostic — surfaced in the visualizer and `highlights/`.
- For Paley graphs $P_q$ with $q \equiv 1 \pmod 4$ prime, $\lambda_{\min} = -\tfrac{1+\sqrt q}{2}$ and $H(P_q) = \sqrt q$.

**Limitation.** Strictly defined for regular graphs. For non-regular $G$ the orthogonalisation step breaks (no single eigenvector dominated by $\mathbf{1}_S$). Substituting $d_{\text{avg}}$ is a heuristic that several scripts in the repo use, but the inequality is no longer guaranteed; we don't do that by default. `hoffman_bound(G, force_d_avg=True)` is available for diagnostic purposes only.

### 2. Lovász theta

$$
\vartheta(G) \;=\; \max\, \langle J, X\rangle \quad \text{s.t.}\quad X \succeq 0,\; \operatorname{tr}(X) = 1,\; X_{ij} = 0 \text{ for } ij \in E(G).
$$

(Here $J$ is the all-ones matrix, so $\langle J, X\rangle = \sum_{ij} X_{ij}$.) Always satisfies $\alpha(G) \le \vartheta(G)$.

**Derivation sketch.** For any independent set $S$, the rank-1 PSD matrix $X = \tfrac{1}{|S|}\mathbf{1}_S \mathbf{1}_S^\top$ is feasible (it has $X_{ij} = 1/|S|$ for $i, j \in S$ and zero elsewhere — in particular zero on edges) with objective value $\langle J, X\rangle = |S|^2 / |S| = |S|$. Maximising over $S$ gives $\vartheta(G) \ge \alpha(G)$.

**Why useful:**
- Polynomial-time SDP (cvxpy + SCS — a few ms per call up to $N \approx 50$).
- Equal to $H$ on vertex-transitive graphs (Lovász); strictly stronger than $H$ on most other graphs.
- Tight on perfect graphs ($\vartheta = \alpha$).
- Lovász's identity for self-complementary SRGs: $\vartheta(P_q) = \sqrt{q}$ for the Paley graph at prime $q \equiv 1 \pmod 4$. This is precisely the slack that keeps any $\vartheta$-method from beating Paley(17)'s plateau:
  $$
  \frac{\vartheta(P_{17}) \cdot \Delta}{N \ln \Delta} \;=\; \frac{\sqrt{17}\cdot 8}{17 \ln 8} \;\approx\; 0.933,
  $$
  while $c_{\log}(P_{17}) \approx 0.679$. So no SDP-relaxation argument can certify a $c_{\log}$ lower bound below $\approx 0.933$ on Paley(17).
- Sandwich: $\alpha \le \vartheta \le \chi_f(\bar G)$, so $\vartheta$ is squeezed between $\alpha$ and the LP clique cover number.
- Lovász's product identity: $\vartheta(G)\cdot\vartheta(\bar G) \ge N$, with equality for vertex-transitive graphs. Useful for sanity-checking computed values.

**Limitation.** Worst-case $\mathcal{O}(N^6)$ SDP. For $N > 100$, start chunking or caching. SCS solver tolerance is $\sim 10^{-5}$; the canonical implementation in `utils.graph_props.lovasz_theta` no longer rounds (the `bound_tightness` review on 2026-04-29 caught this — earlier it rounded to 6 dp, hiding $\vartheta' < \vartheta$ signal).

### 3. Schrijver theta prime

$$
\vartheta'(G) \;=\; \max\, \langle J, X\rangle \quad \text{s.t.}\quad X \succeq 0,\; \operatorname{tr}(X) = 1,\; X_{ij} = 0 \text{ for } ij \in E(G),\; X_{ij} \ge 0 \text{ for all } i, j.
$$

The non-negativity constraint $X_{ij} \ge 0$ is the only difference from $\vartheta$. Always satisfies

$$
\alpha(G) \;\le\; \vartheta'(G) \;\le\; \vartheta(G).
$$

**Why useful:**
- Same algorithm class as $\vartheta$; the extra $\binom{N}{2}$ inequalities are cheap.
- On vertex-transitive graphs (Cayley, SRG) symmetry forces $\vartheta' = \vartheta$ — both objectives are achieved by the symmetric optimum, which already has $X_{ij} \ge 0$.
- On *irregular* graphs $\vartheta'$ can be strictly tighter — exactly where the SAT-certified non-regular optima live, and where it's worth the extra solve.

**What we observed (post-rounding-fix, 2026-04-29):** $\vartheta' < \vartheta$ strictly on 33/43 frontier graphs, with gaps up to $0.032$. The remaining 10 (where $\vartheta' = \vartheta$) are exactly the vertex-transitive ones. So Schrijver does pick up information on the irregular frontier, even if the absolute improvement is small relative to $\alpha$.

**Limitation.** Same SDP cost as $\vartheta$, plus a constant factor for the extra constraints. Never lifts the bound below the $\vartheta'(G^*) / \alpha(G^*) \ge \rho$ floor on Paley-like leaders.

### 4. Fractional chromatic of the complement

$$
\chi_f(\bar G) \;=\; \min \sum_C x_C \quad \text{s.t.}\quad x_C \ge 0,\; \sum_{C \ni v} x_C \ge 1 \text{ for every } v \in V,
$$

where $C$ ranges over the **cliques of $G$** (each is an independent set in $\bar G$, i.e. a colour class). Equivalently the fractional chromatic number of $\bar G$, satisfying

$$
\alpha(G) \;\le\; \chi_f(\bar G) \;\le\; \chi(\bar G).
$$

**Derivation sketch.** $\chi(\bar G) \ge \omega(\bar G) = \alpha(G)$ trivially; the fractional version $\chi_f$ sits between by LP duality. The dual problem is fractional clique number of $\bar G$, which equals $\omega(\bar G) = \alpha(G)$ for perfect graphs and exceeds it otherwise. The integrality gap $\chi_f \ge \alpha$ is the slack between fractional and integral colouring of $\bar G$.

**Why useful:**
- Pure LP — faster than SDP at moderate $N$.
- Sandwiches $\vartheta$ from above: $\vartheta(G) \le \chi_f(\bar G)$. So if $\vartheta < \chi_f$, the gap is purely *LP-derivable* structure that the SDP $\vartheta$ already discounts via positive semidefiniteness.
- Tight on perfect graphs (where $\chi_f = \chi = \omega(\bar G) = \alpha$).
- For self-complementary vertex-transitive graphs (Paley): $\chi_f(\bar G) = N / \alpha(G)$ — every colour class has full weight $\alpha$.

**Why we still bother computing it.** The gap $\chi_f - \vartheta$ is structural, not solver noise. On the Paley(17) chain $\chi_f / \vartheta \approx (17/3) / \sqrt{17} = \sqrt{17}/3 \approx 1.37$ — so any LP-based proof is strictly weaker than $\vartheta$, and that gap is universal over the chain.

**Limitation.** Cost scales with the maximal-clique count of $G$. $K_4$-free implies cliques are $K_3$ or smaller, so the LP has $\mathcal{O}(N^2)$ columns and runs in single-digit milliseconds up to $N \approx 100$. We cap at 200k cliques and return `None` past that; on dense $G$ use the LP dual (column generation) instead.

### 5. Greedy clique cover

A single-pass randomised partition of $V(G)$ into cliques. The number of cliques is an integer $\ge \alpha(G)$ because each clique contributes at most one vertex to any independent set:

$$
\alpha(G) \;\le\; \#\bigl\{\text{cliques in the partition}\bigr\}.
$$

**Why useful:**
- Cheap: $\mathcal{O}(N + |E|)$ time per pass, no LP/SDP.
- Used as a prune inside the default exact $\alpha$ solver (`utils.graph_props.alpha_bb_clique_cover`).
- Sets a "free" loose ceiling; useful as a sanity check for the more expensive bounds.

**Limitation.** Typically $30$–$100\%$ over $\alpha$. Single-pass is order-dependent; the randomised version reduces variance but doesn't tighten the worst case. Strictly weaker than $\chi_f(\bar G)$ on every graph (the greedy clique cover is an integral feasible solution to the LP that defines $\chi_f$).

### 6. Hard-core occupancy (the lower-bound counterpart)

For fugacity $\lambda > 0$, the hard-core distribution on independent sets of $G$ is

$$
\mu_{G,\lambda}(I) \;=\; \frac{\lambda^{|I|}}{Z(G,\lambda)}, \qquad Z(G,\lambda) \;=\; \sum_{I \text{ indep}} \lambda^{|I|}.
$$

The marginal of vertex $v$ being in the random independent set is

$$
\rho_v(G,\lambda) \;=\; \mathbb{P}_\mu(v \in I) \;=\; \frac{\lambda \cdot Z(G - N[v],\lambda)}{Z(G,\lambda)},
$$

and the expected size of a $\mu$-distributed independent set is $\mathbb{E}_\mu[\lvert I\rvert](\lambda) = \sum_v \rho_v(G,\lambda)$. Since $\alpha(G) = \max_I \lvert I\rvert$ and the maximum dominates the expectation, for every $\lambda > 0$,

$$
\alpha(G) \;\ge\; \mathbb{E}_\mu[\lvert I\rvert](\lambda).
$$

We optimise the bound over $\lambda$ by evaluating on a geometric grid and taking the max:

$$
E_{\max}(G) \;=\; \max_{\lambda \in [\lambda_{\min}, \lambda_{\max}]} \,\mathbb{E}_\mu[\lvert I\rvert](\lambda) \;\le\; \alpha(G),
$$

with $E_{\max}(G) \to \alpha(G)$ as $\lambda \to \infty$ (the measure concentrates on maximum-size independent sets).

**Why useful:**
- This is the tightest single-fugacity occupancy bound — the **Davies–Jenssen–Perkins–Roberts ceiling**. No tree-recursion, flag-algebra, or correlation-inequality trick built on hard-core marginals can exceed it.
- Memory `2026-04-21` and `docs/theory/HARDCORE_TIGHTNESS.md` find it within $0.3\%$ of $\alpha$ on every $K_4$-free graph in the DB. It's the closest "lower-bound counterpart" of $\alpha$ we have.
- Including it lets us answer: how much room is there *between* the best lower bound (hard-core) and the best upper bound ($\vartheta'$ or $\vartheta$) for the graphs we care about?

**Numerics.** Independence-polynomial coefficients can grow like $\Theta(2^N)$ and $Z(G,\lambda)$ as $\Theta(\lambda^N)$, so direct Horner evaluation overflows float64 around $N\log_{10}\lambda \approx 308$. We evaluate $\rho_v$ as $\exp(\log Z(G - N[v]) + \log\lambda - \log Z(G))$ via log-sum-exp, so dynamic range is no longer the limit; the cost ceiling is the polynomial enumeration itself.

**Limitation.** $\mathcal{O}(N \cdot 2^N)$ per graph (independence-polynomial enumeration runs once for $G$ and once per vertex). Cap usage at $N \le \sim 22$. **Lower bound, not upper** — included for benchmarking only.

---

## Files

| File | Purpose |
|---|---|
| `run_tightness.py` | Driver — pulls graphs from `graph_db`, runs every bound in `utils.alpha_bounds`, writes per-graph CSV. CLI: `--c-max`, `--n-max`, `--out`. |
| `results.csv` | Per-graph table: graph_id, source, $n$, $\Delta$, $\alpha$, $c_{\log}$, every bound value, every bound's wall time, every tightness ratio. |
| `results.md` | Human-readable digest — aggregate stats, plateau-A row, headline takeaways. |

The bounds themselves live in `utils/alpha_bounds.py`. Re-implementations elsewhere in the repo (six different `lovasz_theta` calls, four different inline `hoffman_bound` formulas) should be migrated to the canonical module — see the script-cleanup pass.

---

## Results

See `results.md` for the digest. One-line headline: every $\alpha$ upper bound on the $c_{\log} \le 0.74$ frontier overestimates $\alpha$ by $\ge 17\%$, so SDP-relaxation arguments cannot prove a $c_{\log}$ lower bound below $\approx 0.79$ on these graphs. Hard-core captures $\alpha$ to within $0.3\%$ — the lower-bound side has essentially zero slack.

**Status:** active (initial scan; ready to extend to the full DB and to add Szegedy $\vartheta^+$ / Cvetković inertia).

---

## Open questions

- [ ] How does the gap $\vartheta' - \vartheta$ behave on a wider sample of irregular graphs — does it ever grow with $N$, or stay bounded by SCS solver tolerance?
- [ ] Run the same benchmark restricted to `is_regular = 1` to compare $H$ vs $\vartheta$ where $H$ is defined.
- [ ] Extend to $N \le 100$ once the $N \le 22$ hard-core cap is removed (skip hard-core, keep the four upper bounds).
- [ ] Add Szegedy's $\vartheta^+$ (Lovász $\vartheta$ with a different relaxation direction) to see if it differs from $\vartheta'$ on irregular graphs.
- [ ] Add Cvetković's inertia bound $\alpha(G) \le \min(n_+, n_-)$, where $n_\pm$ count non-negative / non-positive eigenvalues of $A$, as a non-SDP spectral comparator.

---

## Theorems that would be nice to prove

- **Conjecture (SDP plateau).** For every $K_4$-free $G$ with $c_{\log}(G) \le 0.7$,
  $$
  \frac{\vartheta(G)}{\alpha(G)} \;\ge\; 1 + \varepsilon
  $$
  for some universal $\varepsilon > 0$ independent of $N$.
  *Why it matters:* if true, no SDP-relaxation method can certify a $c_{\log}$ lower bound below $(1+\varepsilon) \cdot c_{\log}(G^*)$, formalising the empirical observation that all SDP bounds plateau $\sim 17\%$ above $\alpha$ on the frontier.

- **Conjecture (hard-core saturation on $K_4$-free).** For every $K_4$-free $G$,
  $$
  E_{\max}(G) \;\ge\; \Bigl(1 - \tfrac{C}{\Delta(G)}\Bigr) \cdot \alpha(G)
  $$
  for some absolute constant $C$.
  *Why it matters:* combined with a uniform Caro–Wei lower bound on $\alpha/N$, this would give a tight occupancy-method derivation of $c(G) \ge c^*$ — the path that closed the analogous result for triangle-free graphs.
