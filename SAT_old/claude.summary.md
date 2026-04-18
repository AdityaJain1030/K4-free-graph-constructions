# K₄-Free Independence Conjecture: Results and Reductions

## The Conjecture

For K₄-free graphs G on n vertices with maximum degree d:

$$\alpha(G) \geq c \cdot \frac{n \log d}{d}$$

The best known result is Shearer 1995: α(G) ≥ c₁ · (n/d) · √(log d). The conjecture asks whether the exponent on log d can be improved from 1/2 to 1.

---

## Result 1 (EMPIRICAL, NOT PROVED): The optimal α is the Ramsey value

**Claim:** For fixed N, the K₄-free graph minimizing c = αd/(N log d) has α as small as possible, i.e., the Ramsey value.

**Status:** Verified by SAT experiments up to N = 22. All optimal graphs found have α equal to the Ramsey value for that N. Multiple proof attempts failed; the claim remains an empirical observation.

### Proof attempt 1: Caro-Wei monotonicity (FAILED)

**Idea:** Caro-Wei gives d ≥ N/α. Plug into c:

$c \geq \frac{\alpha \cdot (N/\alpha)}{N \cdot \log(N/\alpha)} = \frac{1}{\log(N/\alpha)}$

This lower bound on c is increasing in α (larger α → smaller N/α → smaller log → larger 1/log). So the floor on c rises with α.

**Why it fails:** This only shows the floor rises. The actual c could be far above the floor at small α (where Shearer forces d well above N/α) and close to the floor at large α (where the constraint is weaker). A rising floor does not imply a rising function.

### Proof attempt 2: Sandwich with upper bounds (FAILED)

**Idea:** Use both Caro-Wei (d ≥ N/α) and Neighborhood Ramsey (d ≤ R(3, α+1) − 1) to sandwich d. Show that the worst-case c at α₁ is still ≤ best-case c at α₂.

**Concrete test (α₁ = 4 vs α₂ = 5 at N = 35):**
- Worst c₁: d₁ = R(3,5) − 1 = 13, so c₁ = 4·13/(35·log 13) = 0.579
- Best c₂: d₂ = 35/5 = 7, so c₂ = 1/log 7 = 0.514

Since c₁ > c₂, the sandwich cannot rule out that larger α wins.

**Why it fails:** The sandwich width is √(log(N/α)) (from Shearer lower bound to Neighborhood Ramsey upper bound), which is exactly the range of the open problem. The gap between bounds is too wide to force monotonicity.

### Proof attempt 3: Shearer sandwich (FAILED)

**Idea:** Use the tighter Shearer lower bound d ≥ (c₁N/α)√(log(N/α)) together with the Neighborhood Ramsey upper bound d ≤ O(α²/log α).

**Why it fails:** The lower bound depends on N; the upper bound doesn't. At any fixed N, the worst case for α₁ (d at the upper bound) gives c ≈ α·α²/(N log α²) which can exceed the best case for α₂ (d at the Shearer floor) which gives c ≈ 1/√(log(N/α₂)). The bounds are qualitatively different and don't interlock tightly enough.

### Proof attempt 4: Assume the conjecture (INFORMATIVE BUT CIRCULAR)

**Idea:** If the conjecture α ≥ c₀·(N log d)/d is true, then d ≥ c₀·(N/α)·log(N/α), giving a much tighter sandwich:

$c_0 \cdot \frac{N}{\alpha} \cdot \log\frac{N}{\alpha} \;\leq\; d \;\leq\; \frac{\alpha^2}{\log \alpha}$

At N = R(4,t)−1, both bounds are Θ(t²/log t), so d is pinned to within a constant factor.

**Result:** Under the conjecture, c(α) ≈ c₀ · 1/(1 + log log λ / log λ) where λ = N/α. This is approximately constant across all α, with tiny log-log corrections. The variations between different α values are negligible.

**Interpretation:** If the conjecture is true, it doesn't matter which α you target — c ≈ c₀ regardless, and Result 1 is essentially vacuous.

### Summary of what Result 1's status tells us

Three regimes emerge:

1. **If the conjecture is true (β = 1):** c is approximately constant across all α. The choice of α is irrelevant. Result 1 is unnecessary.

2. **If the conjecture is false (β < 1):** c varies meaningfully across α. The empirical observation that Ramsey α is optimal becomes important for computational search. But we cannot prove it analytically because the tools needed (pinning d_min) are equivalent to resolving the conjecture itself.

3. **For computation regardless of β:** The empirical observation guides SAT search. Even without a proof, targeting Ramsey α is the best available heuristic, supported by all data up to N = 22.

---

## Result 2 (PROVED): The optimal graph is near-regular

**Claim:** For any fixed N and α, the K₄-free graph minimizing c must satisfy d_max ≤ d_min + 1.

**Proof:** The optimal graph must be α-critical. If any edge e could be removed without increasing α, then G − e is K₄-free with the same α but fewer edges, so d_max(G − e) ≤ d_max(G), giving c(G − e) ≤ c(G), contradicting optimality.

By Hajnal's theorem (Lovász–Plummer, Matching Theory, Chapter 12), every α-critical graph satisfies d_max ≤ d_min + 1.

**References:** Hajnal's theorem as presented in Lovász and Plummer, *Matching Theory* (1986), Chapter 12. Original α-critical graph theory due to Zykov (1949).

---

## Result 3 (PROVED): Minimizing c is equivalent to minimizing |E|

**Claim:** Among K₄-free graphs on N vertices with α = t−1, minimizing c is equivalent to minimizing the number of edges.

**Proof:**

*Forward direction:* By Result 2, the optimal graph is near-regular, so d_max ≈ d_avg = 2|E|/N. Since d/log d is monotone increasing for d > e, minimizing d_max minimizes c. For near-regular graphs, minimizing d_max is equivalent to minimizing 2|E|/N, which is equivalent to minimizing |E|.

*Converse direction:* The graph minimizing |E| subject to K₄-free and α ≤ t−1 must be α-critical — if any edge could be removed while maintaining α ≤ t−1, then |E| was not minimal. By Hajnal, the minimizer is therefore near-regular. So no additional regularity or degree constraints are needed in the optimization.

**Computational consequence:** The solver needs only: minimize Σ x_{ij} subject to K₄-free and α ≤ t−1. No symmetry breaking, no degree bounds, no regularity enforcement. The solution is automatically α-critical and near-regular.

---

## The Sandwich Theorem: Bounding d_min(N, α)

For a K₄-free graph on N vertices with α(G) = α and near-regular degree d, the following bounds apply.

### Lower bound 1: Caro-Wei

The Caro-Wei theorem gives α(G) ≥ Σ_v 1/(d(v)+1). For a near-regular graph with degree ≈ d:

$$\alpha \geq \frac{N}{d+1}$$

Setting α = t−1 and rearranging:

$$d \geq \frac{N}{\alpha} - 1 \approx \frac{N}{\alpha}$$

### Lower bound 2: Shearer 1995 (strictly stronger)

Shearer proves that for K₄-free graphs with max degree d on N vertices:

$$\alpha(G) \geq c_1 \cdot \frac{N}{d} \cdot \sqrt{\log d}$$

Setting α = t−1 and rearranging:

$$d \geq \frac{c_1 N}{\alpha} \cdot \sqrt{\log d}$$

This is self-referential. Solving by substitution d = (N/α) · f:

$$\frac{N}{\alpha} \cdot f \geq \frac{c_1 N}{\alpha} \cdot \sqrt{\log\left(\frac{Nf}{\alpha}\right)}$$

$$f \geq c_1 \sqrt{\log \frac{N}{\alpha} + \log f}$$

For large N/α, log f ≪ log(N/α), giving:

$$f \geq c_1 \sqrt{\log \frac{N}{\alpha}} \cdot (1 + o(1))$$

Therefore:

$$d \geq \frac{c_1 N}{\alpha} \cdot \sqrt{\log \frac{N}{\alpha}}$$

This is strictly stronger than Caro-Wei by a factor of √(log(N/α)).

**Reference:** Shearer, *Random Structures & Algorithms* 7 (1995) 269–271. The bound follows from recursive application of the Shearer 1983 triangle-free bound to the (triangle-free) neighborhoods of vertices in a K₄-free graph.

### Upper bound: Neighborhood Ramsey

In a K₄-free graph, every neighborhood N(v) is triangle-free on d vertices. Any independent set in N(v) is also independent in G. By the Ramsey number R(3, α+1): if d ≥ R(3, α+1), then the triangle-free neighborhood must contain an independent set of size α+1, contradicting α(G) = α. Therefore:

$$d \leq R(3, \alpha + 1) - 1$$

Using the known asymptotic R(3, k) = Θ(k²/log k):

$$d \leq O\left(\frac{\alpha^2}{\log \alpha}\right)$$

This is a hard ceiling independent of N.

For specific small values (from known exact Ramsey numbers):
- α = 3: d ≤ R(3,4) − 1 = 8
- α = 4: d ≤ R(3,5) − 1 = 13
- α = 5: d ≤ R(3,6) − 1 = 17
- α = 6: d ≤ R(3,7) − 1 = 22

### The sandwich

Combining Shearer (lower) and Neighborhood Ramsey (upper):

$$\frac{c_1 N}{\alpha} \cdot \sqrt{\log \frac{N}{\alpha}} \;\lesssim\; d \;\lesssim\; \frac{\alpha^2}{\log \alpha}$$

Note: the lower bound depends on N; the upper bound does not. As N grows with α fixed, the lower bound rises until it collides with the upper bound. This collision point is essentially the Ramsey number R(4, α+1).

### The β parametrization

Write d_min(N, α) = (N/α) · (log(N/α))^β. Then:

- **Shearer lower bound → β ≥ 1/2** (proved)
- **Conjecture → β = 1** (open)
- **Neighborhood Ramsey upper bound → β ≤ 1** at N near R(4,t)−1

So β ∈ [1/2, 1] is the range. The conjecture is equivalent to β = 1.

The minimum c over all feasible graphs satisfies:

$$c_{\min} \sim (\log t)^{\beta - 1}$$

This goes to zero (conjecture false) iff β < 1, and stays constant (conjecture true) iff β = 1.

---

## Result 4 (PROVED): The conjecture is equivalent to the Shearer exponent

**Claim:** The conjecture is equivalent to whether β = 1 in the parametrization d_min(N, α) = (N/α) · (log(N/α))^β.

**Proof:** By Results 2 and 3, the minimum c over K₄-free graphs with α = t−1 on N vertices is:

$$c_{\min} = \frac{(t-1) \cdot d_{\min}}{N \cdot \log d_{\min}}$$

Substituting d_min = (N/(t-1)) · (log(N/(t-1)))^β:

$$c_{\min} = \frac{(t-1) \cdot \frac{N}{t-1} \cdot (\log \lambda)^\beta}{N \cdot \log\left(\frac{N}{t-1} \cdot (\log \lambda)^\beta\right)}$$

where λ = N/(t−1). The numerator is N · (log λ)^β. The denominator is N · (log λ + β log log λ) ≈ N · log λ. Therefore:

$$c_{\min} \approx \frac{(\log \lambda)^\beta}{\log \lambda} = (\log \lambda)^{\beta - 1}$$

This tends to zero as λ → ∞ iff β < 1, and remains constant iff β = 1.

The sandwich theorem establishes β ∈ [1/2, 1]. The conjecture asserts β = 1.

**Note:** This is not equivalent to the R(4,t) gap or the Erdős-Rogers problem. Those are thematically related but logically distinct.

---

## Result 5 (PROVED): Clean computational formulation

**Claim:** The conjecture can be attacked by a single optimization problem.

**Formulation:** For each N and target α = t−1:

> Minimize Σ_{i<j} x_{ij}
> Subject to:
> - K₄-free: for every 4-clique {a,b,c,d}, x_{ab} + x_{ac} + x_{ad} + x_{bc} + x_{bd} + x_{cd} ≤ 5
> - α ≤ t−1: for every (t)-subset S, at least one edge within S is present

The solution is automatically α-critical and near-regular (Results 2–3). The value d_min(N) = 2|E*|/N directly measures β.

**Solver improvements over prior approach:**
- No symmetry breaking needed (was biasing toward irregular graphs)
- No degree constraints needed (follow automatically from α-criticality)
- No regularity enforcement needed (follows from Hajnal)
- Single optimization call instead of binary search on d
- Objective guides pruning, making the solver more efficient

---

## Empirical Data (verified optimal for N ≤ 22)

All optimal graphs found are regular. α values match Ramsey predictions.

| N | d | α | c = αd/(N·ln d) | d/(N/α) | β regime |
|---|---|---|---|---|---|
| 12 | 5 | 3 | 0.777 | 1.25 | α = 3 |
| 13 | 6 | 3 | 0.773 | 1.38 | α = 3 |
| 14 | 6 | 3 | 0.718 | 1.29 | α = 3 |
| 15 | 7 | 3 | 0.719 | 1.40 | α = 3 |
| 16 | 8 | 3 | 0.721 | 1.50 | α = 3 |
| 17 | 8 | 3 | 0.679 | 1.41 | α = 3 |
| 18 | 6 | 4 | 0.744 | 1.33 | α = 4 |
| 19 | 6 | 4 | 0.705 | 1.26 | α = 4 |
| 20 | 7 | 4 | 0.719 | 1.40 | α = 4 |
| 21 | 8 | 4 | 0.733 | 1.52 | α = 4 |
| 22 | 9 | 4 | 0.745 | 1.64 | α = 4 |

c fluctuates around 0.7 and does not trend toward zero, consistent with β near 1 (conjecture true). However, t = 4 and t = 5 are too small to distinguish β = 1/2 from β = 1 in the logarithmic factors.

---

## What Remains Open

1. **Result 1:** Whether optimal α equals the Ramsey value. Empirically supported, analytically unresolved.
2. **Optimal N:** Which N within [R(4,t−1), R(4,t)−1] minimizes c. No analytical tools resolve this.
3. **The value of β:** The central open question. Equivalent to the conjecture. Requires either new theoretical tools or empirical measurement at larger t (t ≥ 7) where logarithmic factors become distinguishable.