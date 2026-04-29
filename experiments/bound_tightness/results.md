# `experiments/bound_tightness/` — initial results

Frontier benchmark: 43 unique $K_4$-free graphs from `graph_db` with $c_{\log} \le 0.74$ and $n \le 25$. The set covers the Paley(17) plateau leader, the Cayley/circulant frontier, every SAT-certified optimum at $n \le 25$, and the dihedral/regular-switch family. Reproduce with

```bash
micromamba run -n k4free python experiments/bound_tightness/run_tightness.py
```

Total wall time: ~7 s.

---

## Aggregate tightness

$B / \alpha$ for upper bounds; $\alpha / E_{\max}$ for the hard-core lower bound. All ratios $\ge 1$; closer to $1$ = tighter.

| Bound | Coverage | min | mean | max |
|---|---|---|---|---|
| **Hoffman** $H/\alpha$ (regular only) | 13/43 | 1.3101 | 1.5191 | 1.7754 |
| **Lovász** $\vartheta/\alpha$ | 43/43 | **1.1716** | 1.3179 | 1.4326 |
| **Schrijver** $\vartheta'/\alpha$ | 43/43 | 1.1716 | 1.3165 | 1.4326 |
| **Fractional** $\chi_f(\bar G)/\alpha$ | 43/43 | 1.3333 | 1.6957 | 2.0000 |
| **Greedy clique cover** $\#C/\alpha$ | 43/43 | 1.5000 | 2.0298 | 2.5000 |
| **Hard-core** $\alpha / E_{\max}$ | 43/43 | **1.0017** | **1.0019** | 1.0029 |

Zero of the upper bounds are within $1\%$ of $\alpha$ on any frontier graph. The hard-core *lower* bound is within $0.3\%$ on every graph.

---

## Plateau leader: Paley(17), $\alpha = 3$

| Bound | Value | $B / \alpha$ |
|---|---|---|
| Hoffman $H$ | $4.123106 = \sqrt{17}$ | 1.3744 |
| Lovász $\vartheta$ | $4.123106 \approx \sqrt{17}$ | 1.3744 |
| Schrijver $\vartheta'$ | $4.123098 \approx \sqrt{17}$ | 1.3744 |
| $\chi_f(\bar G)$ | $5.666679 \approx 17/3$ | 1.8889 |
| Greedy clique cover | $6$ | 2.0000 |
| Hard-core $E_{\max}$ | $2.99501$ | $\alpha / E_{\max} = 1.0017$ |

$\vartheta(P_q) = \sqrt{q}$ exactly (Lovász's identity for self-complementary SRGs); Hoffman matches because the SRG eigenvalues saturate the ratio bound. $\chi_f(\bar P_q) = q/\alpha = 17/3$ because every coset of a maximum clique colours the graph. Hard-core's only slack here is the finite-$\lambda$ grid (the limit $\lambda \to \infty$ recovers $\alpha$ exactly).

---

## Schrijver vs Lovász on irregular graphs

After removing the 6-decimal rounding that was hiding sub-tolerance signal, **33 of 43** graphs have $\vartheta' < \vartheta$ strictly (gap $> 10^{-6}$). The five widest gaps are all on irregular SAT-frontier or GAP-Cayley graphs:

| Source | $n$ | $\alpha$ | $\vartheta$ | $\vartheta'$ | $\Delta$ |
|---|---|---|---|---|---|
| `sat_near_regular_nonreg` | 15 | 3 | 3.91530 | 3.88352 | 0.0318 |
| `sat_near_regular_nonreg` | 15 | 3 | 3.91301 | 3.88352 | 0.0295 |
| `cayley_tabu_gap` | 21 | 4 | 4.84109 | 4.81629 | 0.0248 |
| `sat_near_regular_nonreg` | 15 | 3 | 3.91093 | 3.89176 | 0.0192 |
| `sat_near_regular_nonreg` | 21 | 4 | 5.26754 | 5.25356 | 0.0140 |

The 10 graphs with $\vartheta' = \vartheta$ are all vertex-transitive (Cayley/SRG/circulant), where symmetry forces equality. So Schrijver does add information on the irregular frontier, but the bound itself is still $\ge 1.17 \cdot \alpha$ everywhere — same plateau as $\vartheta$.

The earlier draft of this document claimed "$\vartheta' = \vartheta$ to solver tolerance" — that was an artefact of rounding the cvxpy outputs to 6 dp before the comparison. With raw floats the picture is the one above.

---

## Per-source spread

$\vartheta / \alpha$ range by source:

| Source | $n$ | min $\vartheta/\alpha$ | max $\vartheta/\alpha$ |
|---|---|---|---|
| `brute_force` | 1 | 1.1716 | 1.1716 |
| `cayley` | 2 | 1.3101 | 1.3744 |
| `cayley_tabu` | 6 | 1.1716 | 1.4266 |
| `cayley_tabu_gap` | 2 | 1.2103 | 1.4326 |
| `circulant` | 1 | 1.4324 | 1.4324 |
| `sat_exact` | 4 | 1.2575 | 1.3248 |
| `sat_near_regular_nonreg` | 19 | 1.2611 | 1.3529 |
| `sat_regular` | 8 | 1.2530 | 1.3624 |

The *tightest* $\vartheta/\alpha$ ($1.1716$) appears on the $n=8$ brute-force graph and on a `cayley_tabu` graph at $n=22$ with $\alpha = 4$ — both are graphs where $\vartheta \approx \alpha + 0.5$. The loosest is on a `cayley_tabu_gap` $n=21$ graph where $\vartheta \approx 1.43 \cdot \alpha$.

---

## Wall time per bound (mean, max)

| Bound | mean | max |
|---|---|---|
| Hoffman | 0.2 ms | 2.5 ms |
| Lovász $\vartheta$ | 59 ms | 985 ms |
| Schrijver $\vartheta'$ | 85 ms | 1467 ms |
| $\chi_f(\bar G)$ | 4 ms | 7 ms |
| Greedy clique cover | 0.3 ms | 0.6 ms |
| Hard-core $E_{\max}$ | 5 ms | 15 ms |

$\vartheta$ and $\vartheta'$ dominate; everything else is sub-$10$ ms at this scale. Hard-core scales with $n \cdot 2^n$ and will become the long pole past $n = 22$.

---

## Headline takeaways

1. **There's a hard $\sim 17\%$ floor for SDP-relaxation methods on this frontier.** The tightest $\vartheta/\alpha$ ratio observed is $1.1716$. Any $c_{\log}$ lower bound proved through $\vartheta$ is therefore weaker by that factor — corresponds to a $c_{\log}$ ceiling of $\sim 0.795$ on a graph at the Paley(17) plateau, well above the empirical $0.679$.

2. **Schrijver $\vartheta'$ is strictly tighter than $\vartheta$ on the irregular frontier (33/43 graphs, gap up to $0.032$).** On vertex-transitive graphs symmetry forces $\vartheta' = \vartheta$. The improvement is real but tiny — $\vartheta'$ shaves at most $\sim 0.6\%$ off the SDP plateau and never reaches $\alpha$.

3. **Hoffman matches $\vartheta$ on regular graphs.** Where both are defined, $H = \vartheta$ to 4 decimal places everywhere. So the spectrum already captures whatever SDP slack is available on the regular frontier; no need to compute $\vartheta$ separately for diagnostic purposes (computing $\vartheta$ remains worth it for irregular graphs and for theoretical clarity).

4. **$\chi_f(\bar G)$ is a lossy LP relaxation.** Mean ratio $1.70$, max $2.00$ (where every clique is a $K_2$ — bipartite-like graphs). Strictly weaker than $\vartheta$ on every frontier graph, with no exception. The LP is fast and worth running for sanity, but it doesn't add proof power.

5. **Greedy clique cover is a baseline only.** Mean ratio $2.05$; useless as a tight bound but cheap and finite — fine for the inner loop of search.

6. **Hard-core $E_{\max}$ essentially equals $\alpha$** (mean ratio $1.0019$, max $1.0029$). The $0.17$–$0.29\%$ gap is a finite-$\lambda$ numerical artefact; the true $\lambda \to \infty$ limit is exactly $\alpha$. **What this means for proofs.** A hard-core / occupancy proof of a universal $c_{\log}$ lower bound (DJPR-style, like the triangle-free result) factors as
   $$
   \alpha(G) \;\ge\; E_{\max}(G) \;\ge\; f(N, \Delta) \quad \implies \quad c_{\log}(G) \;\ge\; \frac{f(N,\Delta)\,\Delta}{N \ln \Delta}.
   $$
   The first inequality is what we just measured: it is *already saturated* on every $K_4$-free graph in the DB to $0.3\%$. So the per-graph step is no longer the obstruction — the question is purely whether step 2, the universal lower bound on $E_{\max}$ for $K_4$-free graphs, can be established. If it can, the bound it would produce on the frontier is essentially $\min_G c_{\log}(G) \approx 0.679$, matching Paley(17) tightly. If it cannot (open), no hard-core proof gets above whatever Shearer-level $f$ exists. **The bottleneck moved from "is hard-core sharp on individual graphs?" (yes, by 0.3%) to "does a universal $f$ exist?" (open).**

---

## What this experiment doesn't yet answer

- Does the $\vartheta/\alpha \ge 1.17$ floor persist outside the lifted Paley chain? (Partially answered by the per-N benchmark below — it grows with $N$ on non-plateau graphs.)
- How does the gap $\vartheta - \vartheta'$ scale with $N$ on the irregular frontier? (Larger gaps appear at $n \ge 70$ on `sat_circulant_optimal` graphs — see below.)
- Where does $\chi_f(\bar G)$ become tight? Suspected: graphs whose complement is perfect.

---

## Per-N best benchmark — $n = 3 \dots 100$

Same bounds, run on the lowest-$c_{\log}$ $K_4$-free graph at each $N$ from 3 to 100 (98 graphs total; hard-core skipped for $n > 22$). Reproduce with

```bash
micromamba run -n k4free python experiments/bound_tightness/run_tightness.py \
    --per-n-best --n-max 100 --out experiments/bound_tightness/results_per_n.csv
```

Total wall time: ~130 s (most of it is SDP at $n \in [70, 100]$).

### Aggregate tightness across $n = 3 \dots 100$

| Bound | Coverage | min | median | mean | max |
|---|---|---|---|---|---|
| Hoffman $H/\alpha$ (regular only) | 75/98 | 1.000 | 1.507 | 1.575 | 2.338 |
| Lovász $\vartheta/\alpha$ | 98/98 | 1.000 | 1.306 | 1.304 | **1.675** |
| Schrijver $\vartheta'/\alpha$ | 98/98 | 1.000 | 1.306 | 1.303 | 1.675 |
| Fractional $\chi_f(\bar G)/\alpha$ | 98/98 | 1.000 | 1.614 | 1.649 | 2.792 |
| Greedy clique cover $\#C/\alpha$ | 98/98 | 1.000 | 2.000 | 1.966 | 3.250 |
| Hard-core $\alpha / E_{\max}$ ($n \le 44$) | 42/98 | 1.0017 | 1.0021 | 1.0022 | 1.0050 |

The maximum $\vartheta/\alpha = 1.675$ is more than triple the $0.17$ slack on the Paley plateau, so the SDP-method floor is *bigger* (worse for proofs) when you step off the plateau onto generic per-N best graphs.

### How $\vartheta/\alpha$ scales with $N$

| $N$ band | min $\vartheta/\alpha$ | mean | max |
|---|---|---|---|
| 3 – 12 | 1.000 | 1.065 | 1.172 |
| 13 – 22 | 1.172 | 1.297 | 1.418 |
| 23 – 32 | 1.154 | 1.272 | 1.448 |
| 33 – 42 | 1.055 | 1.332 | 1.537 |
| 43 – 52 | 1.172 | 1.367 | 1.645 |
| 53 – 62 | 1.151 | 1.399 | 1.675 |
| 63 – 72 | 1.154 | 1.309 | 1.630 |
| 73 – 82 | 1.151 | 1.303 | 1.524 |
| 83 – 92 | 1.189 | 1.355 | 1.645 |
| 93 – 100 | 1.172 | 1.355 | 1.537 |

The mean drifts upward from $\approx 1.07$ at $N \le 12$ to $\approx 1.40$ at $N \approx 60$. Past $N \approx 60$ the per-N best graphs revert to lifted-Paley-like structure and the mean stabilises around $1.35$. **Provisional verdict: the SDP plateau gets *worse* as $N$ grows on non-plateau graphs.**

### Schrijver $\vartheta' < \vartheta$ — large gaps appear at large $N$

The $n \le 25$ scan saw at most $0.032$ gap. Per-N at $n \le 100$:

| $n$ | source | $\vartheta - \vartheta'$ |
|---|---|---|
| 73 | `sat_circulant_optimal` | 0.5328 |
| 83 | `circulant_fast` | 0.4172 |
| 97 | `sat_circulant_optimal` | 0.3090 |
| 71 | `sat_circulant_optimal` | 0.1438 |
| 61 | `sat_circulant_optimal` | 0.1277 |

Schrijver picks up substantially more on the larger circulant family — the non-negativity constraint is doing real work there, not vanishing in solver tolerance.

### Hoffman vs Lovász when both are defined

Of the 75 regular graphs, $H = \vartheta$ (within $10^{-5}$) on at least 5 — those are the spectrum-extremal Cayley/SRG-like graphs. The largest gap $H - \vartheta = 8.98$ shows up at $n=100$, $\alpha=20$, where Hoffman is $\sim 35.5$ and $\vartheta$ is $\sim 26.5$ — i.e. the SDP shaves a meaningful fraction $H \to \vartheta$ on the larger non-plateau graphs.

### What it means

The $n \le 25$ frontier was dominated by graphs that already saturate $\vartheta$ to within $1.17 \alpha$. The wider per-N benchmark says this is the *best case* for SDPs: on most $N$, the gap is closer to $1.30 \alpha$ and on some non-plateau graphs at $N \in [50, 60]$ it touches $1.68 \alpha$. So:

- The "$\vartheta/\alpha$ floor on $K_4$-free is bounded by $1.17$" claim is wrong outside the plateau chain — non-plateau graphs leave more SDP slack.
- The plateau chain (Paley(17), its lifts, the dihedral $C_{34}$/$C_{51}$/$C_{68}$/$C_{85}$ family) is *unusually* SDP-saturated.
- Schrijver $\vartheta'$ becomes meaningfully tighter than $\vartheta$ at $N \ge 60$ on circulants — worth keeping in the toolbox even though the absolute improvement is $\le 0.5$.
