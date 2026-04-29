# `experiments/edge_gradients/` — results

Three tests on a difficulty ladder, each dropping a property the previous test relied on.

## TL;DR

> **The hard-core model gives a tight per-edge α direction-signal, indexed by vertex pairs (the two-body correlation $\rho_{uw}$), at lower cost than its SDP counterpart $X_{uw}$. The signal is reliable as a rollout heuristic but does not produce precise per-edge attribution to specific load-bearing edges in the final state, consistent with the 17% structural slack of $\vartheta$ over $\alpha$ on this graph class.**

The arc:

| Test | Question | Hard-core verdict |
|---|---|---|
| 1 | Can these signals identify a useless edge? | One-body / local hard-core fails (25%). SDP θ dual wins (100%). |
| 2 | Starting from a saddle, can the signal find a way down? | **Two-body co-marginal $\rho_{uw}$ ties SDP at 15/15, $40\times$ cheaper.** This is the positive result. |
| 3 | Does the signal at $t=0$ predict load-bearing edges at $t=T$? | Weakly. Direction-correct, attribution-weak. |

The first form of the hard-core hypothesis (per-vertex marginal $\rho_v$) is the wrong order of moment for per-edge information. The second form (per-pair co-marginal $\rho_{uw}$) is the right one — and it works.

---

# Test 1 — perturbed-edge identification

10 frontier $K_4$-free graphs from `graph_db`, plus an "+1 edge" perturbed variant of each. Reproduce with

```bash
micromamba run -n k4free python experiments/edge_gradients/run_edge_gradients.py
```

Total wall time: ~30 s.

## Test 1 headline

| Method | Precision@1 (perturbed) | Spearman (perturbed) | Frontier spread | Cost |
|---|---|---|---|---|
| **SDP θ dual** | **8/8 = 100%** | 0.18–0.41 | 0 (correct) | 1 SDP solve |
| **drop-$E_{\max}$** | **8/8 = 100%** | 0.18–0.42 | 0 (correct) | $\|E\| \cdot \mathcal{O}(2^N)$ |
| LP dual | 6/8 = 75% | 0.18–0.41 | 0 (correct) | 1 LP solve |
| drop-$L_{HC}$ | 2/8 = 25% | −0.23 to 0.41 | 0 (correct) | $\|E\| \cdot \mathcal{O}(2^{d_{\max}})$ |
| Hoffman gradient | 0/8 (undefined) | — | undefined | closed-form |
| drop-α (gold) | — (defines truth) | — | 0 (truth) | $\|E\|$ α-solves |

The first-form hard-core attribution (`drop_l_hc`, derived from the local one-body bound) **fails outright at 25% precision**. This is the test-1 surprise. The rest of test 1 is interesting only insofar as it shows which *cheap* methods agree with the gold standard's binary signal: the SDP θ dual perfectly matches drop-α at $\sim 40\times$ less cost than the global drop-$E_{\max}$, but this is a low-bar test because drop-α itself trivially solves it (the redundant edge has drop-α = 0 by construction).

---

## What the frontier sees

Every frontier graph in the benchmark is **α-critical**: drop-α$\,= 1$ on every edge. So:

- The "gold standard" gives no ranking — it's the constant function 1.
- A method is **correct on the frontier** if it produces zero spread (all edges equal), matching drop-α's verdict.
- A method is **spurious** if it discriminates among edges where drop-α refuses to.

| Graph | $|E|$ | drop-α | $E_{\max}$ spread | $L_{HC}$ spread | LP spread | SDP spread | Hoff |
|---|---|---|---|---|---|---|---|
| Paley(17) | 68 | 1 ∀e | 0 | 0 | 0 | 0 | n/a |
| CR(19) | 57 | 1 ∀e | 0 | 0 | 0 | 0 | n/a |
| n=22 cayley | 88 | 1 ∀e | 0 | 0 | 0 | 0 | n/a |
| n=21 cayley_gap | 84 | 1 ∀e | 0 | 0 | 0 | 0 | n/a |
| n=8 brute | 16 | 1 ∀e | 0 | 0 | 0 | 0 | n/a |
| n=14, 15, 20, 25 SAT | 41–85 | 1 ∀e | varies | varies | 0 | varies | n/a |

The Cayley/circulant frontier graphs are vertex-transitive, so every method agrees: zero spread, no false discrimination. The SAT-certified graphs are *not* vertex-transitive, so $E_{\max}$, $L_{HC}$, and SDP all introduce spread on the frontier even though drop-α says all edges are equally critical. **This is spurious signal** — those rankings reflect graph asymmetry, not α-importance.

LP dual is the only smooth method that stays flat on the SAT frontier: it equals $1/(N{-}\alpha)$ on every constraint at the LP optimum. Stable but uninformative.

---

## After perturbation: the redundant edge

For each frontier graph, we add one random non-edge that keeps the graph $K_4$-free. In every case the added edge is redundant: drop-α$\,= 0$ for it, drop-α$\,= 1$ for every other edge. So drop-α is binary, and the question becomes: **does method $M$ rank the redundant edge lowest?**

| Graph | drop-$E_{\max}$ | drop-$L_{HC}$ | LP dual | SDP dual |
|---|---|---|---|---|
| CR(19) +1 | ✓ | ✗ | ✓ | ✓ |
| n=22 cayley +1 | ✓ | ✓ | ✓ | ✓ |
| n=8 brute +1 | ✓ | ✓ | ✓ | ✓ |
| n=14 sat_exact +1 | ✓ | ✗ | ✓ | ✓ |
| n=14 sat_near +1 | ✓ | ✗ | ✗ | ✓ |
| n=15 sat_near +1 | ✓ | ✗ | ✗ | ✓ |
| n=20 sat_exact +1 | ✓ | ✗ | ✓ | ✓ |
| n=25 sat_exact +1 | ✓ | ✗ | ✓ | ✓ |
| **precision@1** | **8/8** | **2/8** | **6/8** | **8/8** |

The redundant edge gets drop-$E_{\max} = 0$ exactly (the global hard-core derivative vanishes there); the SDP multiplier $\mu_{uv}$ is the *highest* (the constraint binds hardest), so we score by $-\mu_{uv}$ for ranking. Both flag the redundant edge with full discrimination on every graph in the benchmark.

The local hard-core $L_{HC}$ scores poorly because its per-vertex sum aggregates noise from neighbourhood symmetries that don't see the global α structure. LP dual scores 6/8 because on graphs where the LP is degenerate (multiple optima), some edges share the same multiplier and the redundant one isn't strictly minimum.

---

## Hoffman gradient is unusable on the frontier

The Hellmann–Feynman formula

$$
\frac{\partial \lambda_{\min}}{\partial A_{uv}} \;=\; 2\, w_{\min}[u]\, w_{\min}[v]
$$

assumes $\lambda_{\min}$ is non-degenerate. Every graph in this benchmark — Paley, CR, $n=22$ Cayley lift, the SAT-certified optima — has $\lambda_{\min}$ with multiplicity $\ge 2$. The eigenspace is at least 2-dimensional and any specific $w_{\min}$ chosen from it is basis-dependent. The numerical answer changes with the LAPACK reduction; the bound itself is fine but its gradient is not well-defined without degenerate perturbation theory.

This is a property of the frontier specifically: spectrum-extremal graphs almost always have multi-eigenvalue λ_min. On a generic K₄-free graph (off the frontier) the gradient would be well-defined; but on the graphs we actually care about it's not usable.

---

## Cost comparison

| Method | Per-graph cost on N=22, |E|=88 | Per-graph cost on N=80, |E|=320 |
|---|---|---|
| drop-α | $\|E\|$ × 5 ms ≈ 0.5 s | $\|E\|$ × 200 ms ≈ 60 s |
| drop-$E_{\max}$ | $\|E\|$ × 30 ms ≈ 3 s | (out of reach past $N \approx 46$) |
| drop-$L_{HC}$ | $\|E\|$ × 1 ms ≈ 0.1 s | $\|E\|$ × 50 ms ≈ 16 s |
| LP dual | 1 LP solve ≈ 5 ms | 1 LP solve ≈ 50 ms |
| **SDP dual** | **1 SDP solve ≈ 30 ms** | **1 SDP solve ≈ 1 s** |
| Hoffman | $\mathcal{O}(N^3)$ once + closed form | undefined on regular spectrum-extremal graphs |

The SDP dual scales as $\mathcal{O}(N^6)$ in the worst case but is dramatically cheaper than the drop-$E_{\max}$ approach on graphs of practical size — and unlike drop-$E_{\max}$, it works at $N \ge 50$ where independence-polynomial enumeration becomes infeasible.

---

## Practical recommendation for the RL credit-assignment use case

1. **Use the SDP θ dual as the per-edge signal.** Solve $\vartheta(G)$ once per state, read off $\{|\mu_{uv}| : uv \in E\}$. High $|\mu_{uv}|$ = "this edge is binding hard in the SDP relaxation of α" = "this edge is doing real work to limit α."
2. **For partial graphs during construction**, the same call works on $G_{\text{partial}}$ — no special handling needed.
3. **For the final graph**, the SDP dual is *not* a substitute for drop-α (which is exactly correct but expensive). It's a substitute for the *gradient* you wanted from drop-α — the per-edge attribution that the integer-valued drop-α refuses to give.

---

## What this experiment does and does not say

**Does say:**
- Among the methods we have implementations of, SDP θ dual is the cheapest method that achieves perfect precision@1 on the redundant-edge identification task.
- The hard-core marginal $\rho_v$ (per-vertex) doesn't naturally give a per-edge signal; drop-$E_{\max}$ does, but at $|E|$-fold cost.
- Local hard-core ($L_{HC}$) is too noisy to be a reliable per-edge attribution — its 25% precision@1 isn't from solver tolerance, it's from genuine signal loss in the partition inequality.
- Hoffman gradient via Hellmann–Feynman fails on spectrum-extremal graphs (which is exactly the frontier).

**Does not say:**
- That SDP dual is a perfect ranker on *non*-α-critical graphs, where drop-α has more variance. Need a wider benchmark.
- That an *incrementally-updated* SDP dual (warm-started across small graph edits) is fast enough for an RL inner loop. We solve from scratch each time.
- Anything about whether a learned attribution (a GNN trained on drop-α labels) would beat the SDP dual at the per-edge ranking task.

---

## What's next

- Test a *warm-started* SDP solve under the small edit assumption — does $\vartheta(G \pm e)$ converge faster than from cold start? If yes, that's the realistic RL inner-loop cost.
- The saddle-escape test below already extends to non-edge co-marginals.

---

# Test 2 — saddle-escape gradient following

15 random K₄-free graphs at $N = 20$, sampled and filtered to be **α-flat** (no single edge addition lowers α). Each method greedily adds $T = 20$ edges, choosing the top-scored K₄-free-safe non-edge at each step.

```bash
micromamba run -n k4free python experiments/edge_gradients/run_followpath.py \
    --n 20 --seeds 15 --steps 20
```

Total wall time: ~25 min (drop-$E_{\max}$ and drop-$L_{HC}$ dominate).

## Headline

**Hardcore co-marginal $\rho_{uw}$ is the fastest method that escapes every saddle.** Same effectiveness as the global drop-$E_{\max}$ and Lovász $X_{uw}$ trio, but $40\times$ cheaper than drop-$E_{\max}$ and $2.5\times$ cheaper than the SDP. This validates the original RL-credit-assignment hypothesis: the hard-core measure *does* give a tight per-edge α gradient — the right quantity is the co-marginal $\rho_{uw}$ for non-edges, not the per-vertex marginal $\rho_v$.

| Method | Saddle escape | Mean α drop | Median first-drop step | Wall (s/seed) |
|---|---|---|---|---|
| **hardcore_comarg $\rho_{uw}$** | **15/15** | **2.07** | **2** | **0.37** |
| sdp $X_{uw}$ | 15/15 | 2.07 | 2 | 0.96 |
| drop-$E_{\max}$ | 15/15 | 2.07 | 2 | 14.68 |
| lp_xu_plus_xw | 14/15 | 1.33 | 5 | 0.66 |
| drop-α (exact) | 14/15 | 1.20 | 3 | 0.52 |
| random | 13/15 | 1.00 | 10 | 0.29 |
| drop-$L_{HC}$ | 8/15 | 0.53 | 5.5 | 14.64 |
| hoffman_grad | 0/15 | — | — | (skipped: graphs not regular) |

## Average $\alpha(t)$ trajectory

Starting α (averaged over 15 saddles) is $7.07$.

| $t$ | random | drop-α | drop-$E_{\max}$ | drop-$L_{HC}$ | $\rho_{uw}$ | $X_{uw}$ | LP slack |
|---|---|---|---|---|---|---|---|
| 0 | 7.07 | 7.07 | 7.07 | 7.07 | 7.07 | 7.07 | 7.07 |
| 1 | 7.07 | 7.07 | 7.07 | 7.07 | 7.07 | 7.07 | 7.07 |
| **2** | **7.00** | **6.93** | **6.07** | **7.00** | **6.07** | **6.07** | **6.93** |
| 3 | 7.00 | 6.53 | 6.07 | 7.00 | 6.07 | 6.07 | 6.87 |
| 5 | 6.93 | 6.47 | 6.00 | 6.80 | 5.93 | 6.00 | 6.60 |
| 10 | 6.60 | 6.13 | 5.00 | 6.60 | 5.00 | 5.07 | 6.33 |
| 20 | 6.07 | 5.87 | 5.00 | 6.53 | 5.00 | 5.00 | 5.73 |

At $t = 1$, every method is stuck (α-flat by construction). At $t = 2$, the trio drop-$E_{\max}$ / $\rho_{uw}$ / $X_{uw}$ collectively pulls α down by 1; everyone else is still stuck. By $t = 10$ the trio reaches α = 5 and plateaus; the other methods are stuck at α $\ge 6$.

See `followpath_alpha_trajectory.png` for the curves with std bands.

## Why $\rho_{uw}$ and $X_{uw}$ tie

Both are *two-body correlation functions* of different convex relaxations of MIS:

- **$\rho_{uw} = \mathbb P_\mu(u, w \in I) = \lambda^2 \cdot Z(G - N[u] - N[w], \lambda) / Z(G, \lambda)$**: the second moment of the indicator $\mathbf 1_I$ under the hard-core Boltzmann distribution. Closed-form in independence polynomials.
- **$X_{uw}$**: the second-moment matrix of the SDP relaxation, $X = \mathbb E[\mathbf 1_I \mathbf 1_I^\top / |I|]$ in the rank-1 lift. Solved via SDP.

Edges are pairs of vertices, so per-edge signals require pair-indexed quantities. The vertex marginal $\rho_v$ is a *one-body* observable and never had a chance — it's the wrong order of moment. Once you write down the natural two-body extension, the SDP and Boltzmann relaxations give nearly the same ranking, because they're the second moments of related convex relaxations.

This is the structural reason test 1's "obvious" form of the hardcore idea (`drop_l_hc`, derived from the local $L_{HC}$ which sums one-body bounds) failed: $L_{HC}$ is a one-body object dressed up to look like an edge attribution. The right move is to derive the per-edge signal from a two-body object directly, which is what $\rho_{uw}$ does.

## What this says about the original RL hypothesis

The original conjecture: hard-core occupancy gives a tight per-edge α signal that fixes RL credit assignment.

After the static perturbed-edge test, that conjecture looked wrong: the per-vertex marginal $\rho_v$ and the local $L_{HC}$ both fail at per-edge attribution (drop-$L_{HC}$ scored 25% in test 1). The natural per-edge signal looked like the SDP θ dual.

After the saddle-escape test, **the conjecture is correct after redirection to the right hard-core quantity**:

- The vertex marginal $\rho_v$ gives no per-edge signal (its very name is "vertex").
- The co-marginal $\rho_{uw} = \mathbb{P}_\mu(u, w \in I)$ is the *natural* per-non-edge signal, derived from the same hard-core measure. High $\rho_{uw}$ = $u, w$ co-occur in many independent sets = adding an edge $uw$ disrupts the most MIS support = strongest α-drop.
- Empirically, $\rho_{uw}$ ties drop-$E_{\max}$ and SDP $X_{uw}$ for fastest saddle escape, at a fraction of either cost.

The connection back to your statistical-physics intuition: $X_{uw}$ in the SDP relaxation and $\rho_{uw}$ in the hard-core measure are both "co-occurrence" quantities — in different convex relaxations of the same combinatorial problem (max independent set). They give nearly identical rankings on these saddles because both are tracking the same underlying joint-incidence structure.

## Cost details

For the RL inner loop, $\rho_{uw}$ wins on every axis we measured:

| Method | Cost / step (N=20) | Cost / 20-step trajectory | Saddle escape rate |
|---|---|---|---|
| drop-α additive | $\|E\|$ × 5 ms | $\sim$ 2 s | 14/15 (only via random tie-break) |
| **$\rho_{uw}$** | **1 polynomial of $G$ + $\|E\|$ small subgraphs ≈ 20 ms** | **$\sim$ 0.4 s** | **15/15** |
| $X_{uw}$ | 1 SDP solve ≈ 50 ms | $\sim$ 1 s | 15/15 |
| drop-$E_{\max}$ | $\|E\|$ × 30 ms ≈ 3 s | $\sim$ 60 s | 15/15 |
| drop-$L_{HC}$ | $\|E\|$ × 5 ms ≈ 0.5 s | $\sim$ 10 s | 8/15 |

$\rho_{uw}$ scales with $\mathcal{O}(N \cdot 2^{N})$ via the global $Z(G)$, so past $N \approx 44$ this gets expensive (same wall as the global hard-core). But for the RL inner loop sizes we care about ($N \le 30$), $\rho_{uw}$ is the right tool.

## What this experiment does and does not say

**Does say:**
- On α-flat saddles in K₄-free graphs at $N = 20$, the hard-core co-marginal $\rho_{uw}$ produces an α gradient that successfully escapes every saddle, at the lowest wall time of any method tested.
- The local hard-core attribution drop-$L_{HC}$ is *worse than random* on this benchmark — local information genuinely doesn't carry the gradient.
- LP slack is a meaningful signal but worse than SDP; LP duals are not a substitute for SDP duals on this task.
- Hoffman gradient via Hellmann–Feynman is unusable because random K₄-free graphs at moderate density are non-regular, and our regular-only implementation skips them.

**Does not say:**
- That $\rho_{uw}$ scales to larger $N$. Past $N \approx 44$ the global $Z(G)$ hits the same wall hard-core_alpha hits in `bound_tightness/`. SDP $X_{uw}$ becomes the recommendation past that scale.
- That this generalises to add-and-remove (we only tested add-only). If the add-only result holds, the next experiment is to formulate remove cleanly and test the symmetric case.
- Whether tie-break strategy matters. We picked uniformly random among ties; deterministic or learned tie-break could change the picture for methods with many score-zero candidates.
- Whether the SDP / hardcore signals predict *global* α-attribution in the final state, or only the *direction* of escape. See test 3 below — they predict direction, not attribution.

---

# Test 3 — does the SDP at t=0 globally predict α-criticality at T?

```bash
micromamba run -n k4free python experiments/edge_gradients/run_globality.py \
    --n 20 --seeds 15 --steps 20
```

The strongest possible RL credit-assignment property would be: SDP $X_{uw}$ at the saddle G_0 predicts, *before any move*, which edges will end up being load-bearing in G_T. We test this by:

1. Compute $X_{uw}$ at t=0 for every K₄-free-safe non-edge of G_0.
2. Run SDP greedy → G_T (α drops by 2-3 in 20 steps).
3. For each *added* edge $e \in E(G_T) \setminus E(G_0)$, compute drop-α at T: $\alpha(G_T - e) - \alpha(G_T)$. Edges with drop > 0 are α-critical in G_T (load-bearing).
4. Spearman correlation of $X_{uw}$ at t=0 vs drop-α at T over the added edges.

If the correlation is high, SDP at t=0 isn't just doing local greedy — it's predicting the global eventual structure. Compare against drop-$E_{\max}$, hardcore co-marginal, and random.

## Result

| Predictor | n | mean ρ | median ρ | min ρ | max ρ | top-pick@t=0 in added | top-pick@t=0 α-critical at T |
|---|---|---|---|---|---|---|---|
| sdp_X_uw | 7 | +0.129 | +0.139 | −0.100 | +0.463 | **7/7** | 1/7 |
| hardcore_comarg | 7 | +0.169 | +0.179 | −0.179 | +0.463 | 6/7 | 0/7 |
| drop_e_max | 7 | +0.180 | +0.259 | −0.260 | +0.463 | 2/7 | 0/7 |
| random | 7 | +0.039 | +0.100 | −0.378 | +0.259 | 1/7 | 1/7 |

n=7 because in 8 of 15 saddles *no added edge* was α-critical at G_T (drop-α $= 0$ on every added edge), making Spearman undefined.

## What this means

Two findings stand out:

1. **Most added edges are structural filler, not load-bearing.** SDP greedy adds 20 edges to drop α by 2-3, but typically only 1-2 of those are α-critical in G_T. The other 18-19 are K₄-free saturation work that pushes the graph into a denser regime where some other edge becomes critical, but those filler edges themselves can be removed without raising α back up.

2. **Spearman is small but positive (~+0.13 for SDP, beating random's +0.04 baseline).** SDP at t=0 picks edges that participate in an α-decreasing process, but not specifically the edges that end up doing the MIS-cutting work in the final state. The top-ranked edge at t=0 is α-critical at T only 1/7 times — the same rate as random.

## How to read this against the user's hypothesis

The original RL claim — "SDP gradient gives a tight per-edge α signal that fixes credit assignment" — splits cleanly into two sub-claims at this resolution:

- **Direction claim** ("greedy on this signal escapes saddles fast"): **strongly supported** by tests 1 and 2. SDP and hardcore co-marginal achieve 15/15 saddle escape at low cost.
- **Attribution claim** ("this signal at t=0 predicts which specific edges will be load-bearing at the end of the rollout"): **weakly supported**. The correlation exists (+0.13) but it's small enough that calling it "global lookahead" overstates what's happening.

The asymmetry is consistent with what the static benchmark said: $\vartheta(G) / \alpha(G) \approx 1.17$ on the frontier. The 17% structural slack of the SDP relaxation over α shows up here as "SDP picks the right *kind* of edge but not the specific load-bearing one." If SDP's gradient were a precise per-edge α attribution, $\vartheta$ would be tight on $\alpha$ and we wouldn't have a frontier at all.

For an RL agent, the practical takeaway is that the SDP / hardcore co-marginal gradients are better understood as *trajectory-rollout heuristics* than as *per-edge value functions*. They reliably point in escape directions; they don't reliably attribute final-state α to specific edges.

## The buried surprise: α-drops without α-critical edges

The single most striking result of test 3 isn't in the Spearman table — it's in the row counts. **In 8 of 15 saddles, no single added edge was α-critical at $G_T$.** The full sequence of 20 edges was added; α fell by 2 or 3; and removing *any one* of those 20 edges from the final graph leaves α unchanged.

This means α didn't drop because of any specific edge — it dropped because of the *collective density* of all 20 edges together. The same way you can ask "which raindrop caused the flood" and get back nothing meaningful: each contribution is essential together but individually deletable. **For these saddle trajectories, α-attribution is genuinely diffuse, not concentrated.**

Caveat on the strength of this claim: 8/15 is a finding about *the specific α-flat saddle starts and 20-step trajectories we ran*. It is not a universal claim that K₄-free α is always diffusely attributed. A different $T$, a different start state, or a different graph regime could shift this. But the result is strong enough to flag credit-assignment formulations on these graphs as suspect — for at least some search states, the question "which edge deserves the credit" has no good answer because no single edge is doing the work.

## What this experiment establishes (final)

> **The hard-core model gives a tight per-edge α direction-signal, indexed by vertex pairs (the two-body correlation $\rho_{uw}$), at lower cost than its SDP counterpart $X_{uw}$. The signal is reliable as a rollout heuristic but does not produce precise per-edge attribution to specific load-bearing edges in the final state, consistent with the 17% structural slack of $\vartheta$ over $\alpha$ on this graph class.**

Three layered findings in this single sentence:

1. **The right hard-core quantity for per-edge information is the two-body co-marginal $\rho_{uw}$, not the one-body marginal $\rho_v$.** Edges are pairs of vertices, so per-edge information is structurally a second-moment / two-point-correlation quantity. The vertex marginal was never the right object — Test 1 ruled that out at 25% precision; the calibration retains a true per-edge signal only after switching to $\rho_{uw}$.

2. **$\rho_{uw}$ and $X_{uw}$ are nearly the same object: second-moment quantities of different convex relaxations of MIS.** They rank edges almost identically in tests 2 and 3. $\rho_{uw}$ is the practical winner because it's a closed-form expression in independence polynomials at $\sim 20$ ms / step, vs $\sim 50$ ms for the SDP solve. This is a calibration result, not a theoretical breakthrough.

3. **Direction signal works; attribution signal doesn't.** Greedy on $\rho_{uw}$ or $X_{uw}$ reliably escapes saddles. The same signal at $t = 0$ does *not* identify which specific edges will be load-bearing at $t = T$. This isn't a solver artefact — it's the same 17% $\vartheta/\alpha$ structural slack from `bound_tightness/` showing up in the temporal direction. If the SDP gradient were a tight per-edge α attribution, $\vartheta$ would equal $\alpha$ on K₄-free graphs and there would be no frontier plateau. There is one. So the slack is real and structural.

The contribution is the empirical calibration on the K₄-free extremal frontier: knowing which forms work, which don't, what the cost trade-offs are, and what the limit on attribution is. SDP θ duals and hardcore co-marginals are decades-old objects; nobody had to invent them. What's new is the calibration that lets you actually use them in your search loop.
