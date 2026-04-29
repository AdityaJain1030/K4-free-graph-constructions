# `experiments/edge_gradients/` — per-edge α signals for RL credit assignment

## Compute

- **Environment:** `k4free` conda env (cvxpy + SCS, networkx, numpy).
- **Typical runtime:** test 1 (perturbed-edge identification) ~30 s on 18 graphs; test 2 (saddle-escape gradient following) ~25 min on 15 saddles × 8 methods × 20 steps at $N = 20$.
- **Memory:** trivial.
- **Parallelism:** single-threaded.

This experiment runs in two complementary tests; see "Two tests, two questions" below.

---

## Background

We are searching over $K_4$-free graphs to *minimise* the score
$c_{\log}(G) = \alpha(G) \cdot \Delta / (N \ln \Delta)$ — small score = good (the Paley(17) plateau sits at $c_{\log} \approx 0.679$). Search means: take a graph, modify it (add or remove an edge), check whether the score moved. The two factors of the score give very different feedback density:

- $\Delta(G)$ moves smoothly with edge actions; each edge contributes to its endpoints' degrees and gives a clean per-edge attribution.
- $\alpha(G)$ is integer-valued and NP-hard. Most single edge changes don't move it at all. So a search agent gets *zero* reward signal on most steps. This is the classic sparse-reward problem.

**The idea.** Replace the integer $\alpha$ with a continuous "energy function" that gives smooth, edge-by-edge feedback. Even when $\alpha$ doesn't actually move, the energy function moves a little, telling you *this edge mattered more than that one*. The original guess was the hard-core occupancy $E_{\max}$ from statistical mechanics — treat independent sets as a Boltzmann distribution and read off per-edge information from that.

The prior experiment (`experiments/hardcore_local/`) showed the obvious form of that idea — extract the per-vertex marginal $\rho_v(G, \lambda) = \mathbb P(v \in I)$ from the hard-core measure — does not give a per-edge signal at all; it gives a per-*vertex* signal, and the local approximation $L_{HC}$ recovers only ~34% of $\alpha$. This experiment is the calibration that resolves the next question: what *is* the right per-edge hard-core quantity, and does it actually work as a search signal?

### The right object is the two-body correlation, not the one-body marginal

A Boltzmann distribution gives observables at every order. For the hard-core measure $\mu(I) \propto \lambda^{|I|}$:

- One-body (per vertex): $\rho_v = \mathbb P_\mu(v \in I)$.
- Two-body (per pair): $\rho_{uw} = \mathbb P_\mu(u, w \in I) = \lambda^2 \cdot Z(G - N[u] - N[w], \lambda) / Z(G, \lambda)$.

Edges are pairs of vertices, so per-edge information is structurally a two-body quantity. The vertex marginal $\rho_v$ never had a chance to be a per-edge signal — it's the wrong order of moment. The natural per-edge object derived from the same Boltzmann distribution is the co-marginal $\rho_{uw}$.

The same structural pattern shows up on the SDP side: Lovász $\vartheta$'s feasible variable $X$ is the second-moment matrix of an SDP relaxation of the indicator vector of an MIS. $X_{uw}$ is the SDP analog of a two-body correlation function. In the linear programming relaxation, the dual variables $y_{uv}$ on edge constraints $x_u + x_v \le 1$ play the same role at LP order. All three — $\rho_{uw}$, $X_{uw}$, $y_{uv}$ — are different convex relaxations of "how often do $u$ and $w$ co-occupy" the optimum.

This experiment calibrates which of these per-edge quantities actually serve as RL signals on the K₄-free extremal frontier, at what cost, and with what limits.

---

## Three tests, three questions

The three tests sit on a difficulty ladder — each one drops a property the previous test relied on.

**Test 1 — perturbed-edge identification** (`run_edge_gradients.py`, `results.csv`).

For each edge $e \in E(G)$, score how much $\alpha$ depends on it. Run on 10 frontier K₄-free graphs plus a "+1 redundant edge" perturbation of each. The perturbed variants give drop-α a binary signal (1 on every original critical edge, 0 on the redundant one); methods are scored by precision@1 (does the method correctly rank the redundant edge lowest?) and by Spearman against drop-α.

This is the easiest of the three tests because drop-α itself trivially identifies the redundant edge. Test 1 only tells us which *cheap* methods agree with the gold standard's ranking when the gold standard works. The first surprise: the obvious local-hard-core-derived attribution `drop_l_hc` *fails* (25% precision), while the SDP θ dual matches the gold standard at 100% precision and one-fortieth the cost.

**Test 2 — saddle-escape gradient following** (`run_followpath.py`, `followpath_results.csv`, `followpath_alpha_trajectory.png`).

Start from a random K₄-free graph $G_0$ chosen to be **α-flat**: no single safe edge addition lowers $\alpha(G_0)$. At step 1, drop-α is identically zero on every candidate — useless. Each method greedily adds $T$ edges, choosing the highest-scored K₄-free-safe non-edge per step. We ask: starting from a state where the gold standard provides no signal, which methods *do* reach a lower-α graph fastest?

This is the actual RL gradient-following question. **This is also where the hard-core hypothesis is vindicated, in the right form**: the two-body co-marginal $\rho_{uw}$ ties drop-$E_{\max}$ and SDP $X_{uw}$ for perfect 15/15 saddle escape, and does so at $40\times$ less cost than drop-$E_{\max}$ and $2.5\times$ less than the SDP.

**Test 3 — global-attribution prediction** (`run_globality.py`, `globality_results.csv`).

Even stronger claim: does the SDP at $t = 0$ identify, *before any move*, which specific edges will be load-bearing in the final graph $G_T$? We measure Spearman correlation between $X_{uw}$ at $t = 0$ and drop-α at $t = T$ on the edges added during a 20-step rollout.

The result here is honest but humbling: the correlation is positive but small (mean Spearman $+0.13$ for SDP vs $+0.04$ for random; the top-1 pick at $t = 0$ is α-critical at $T$ only 1/7 times). The SDP and hard-core gradients are good as **direction signals** ("greedy on this signal escapes saddles") but weak as **attribution signals** ("this specific edge is responsible for the eventual α drop"). Those are two different RL credit-assignment properties; we got the first cleanly and not the second.

---

## How each test was run

### Test 1: perturbed-edge identification

```bash
micromamba run -n k4free python experiments/edge_gradients/run_edge_gradients.py
```

1. Hand-pick 10 lowest-$c_{\log}$ K₄-free graphs in `graph_db` covering Cayley plateau, brute force, sat_exact, sat_near_regular_nonreg.
2. For each frontier graph $G$:
   - Run six edge-attribution methods (drop-α, drop-$E_{\max}$, drop-$L_{HC}$, LP dual, SDP θ dual, Hoffman gradient).
   - Verify that drop-α$\,= 1$ on every edge (these are all α-critical).
3. For each frontier graph, build a "+1 edge" variant: add a random K₄-free-safe non-edge. The added edge has drop-α $= 0$; the original edges keep drop-α $= 1$.
4. Run all six methods on each perturbed graph. Score each method by precision@1 (does it correctly rank the added edge as lowest?) and Spearman correlation with drop-α.

The known weakness of this test: drop-α gives a binary signal on perturbed frontier graphs (one 0, $|E|$ ones), and any method that can compute drop-α will trivially win precision@1. The test is interesting only insofar as it shows which *cheap* methods (LP, SDP, hard-core derivatives) match the gold standard's ranking.

### Test 2: saddle-escape gradient following

```bash
micromamba run -n k4free python experiments/edge_gradients/run_followpath.py \
    --n 20 --seeds 15 --steps 20
```

1. Sample random K₄-free graphs at $N = 20$, density $\approx 0.30$ (target $\sim 57$ edges).
2. Filter to **α-flat** graphs: those where no single K₄-free-safe edge addition lowers α. (At step 1, drop-α-additive returns 0 for every candidate.)
3. Heuristic check: keep only saddles where some 2-edge pair *does* lower α (verified by 40 random pair probes), so the starting graph is genuinely a saddle the methods *could* escape.
4. Sample until 15 such starts are found (typical hit rate $\sim 1/8$ at this density).
5. For each starting graph $G_0$, run each method greedily for $T = 20$ steps:
   - Compute scores for every K₄-free-safe non-edge.
   - Add the highest-scoring non-edge (random tie-break).
   - Record $\alpha(G_t)$.
6. Aggregate per-method: success rate (≥ 1 α-drop in T steps), mean total α drop, median first-drop step, wall time.
7. The plot `followpath_alpha_trajectory.png` shows mean $\alpha(t)$ across saddles per method.

This is the actual gradient-following question — drop-α gives no signal at $t = 1$, so any method that escapes the saddle does so on its own continuous signal, not via the α gold standard.

---

## The methods

### Drop-α (gold standard)

$$
s_{\text{drop-α}}(e) \;=\; \alpha(G - e) - \alpha(G) \;\in\; \{0, 1, 2, \dots\}.
$$

Always non-negative — removing an edge can never decrease α. Cost: $|E|$ exact α solves.

### Drop-$E_{\max}$

$$
s_{E_{\max}}(e) \;=\; E_{\max}(G - e) - E_{\max}(G).
$$

Continuous analogue. Cost: $|E|$ global hard-core evaluations (each $\mathcal{O}(N \cdot 2^N)$, so feasible only at $N \le \sim 44$).

### Drop-$L_{HC}$

$$
s_{L_{HC}}(e) \;=\; L_{HC}(G - e) - L_{HC}(G).
$$

Cheap local analogue. Cost: $|E|$ local hard-core evaluations (each $\mathcal{O}(N \cdot 2^{d_{\max}})$).

### LP dual

The LP relaxation of the maximum independent set is

$$
\alpha_{LP}(G) \;=\; \max\, \sum_v x_v \quad \text{s.t.}\quad x_u + x_v \le 1\text{ for } uv \in E,\; x \in [0, 1]^V.
$$

The dual variable $y_{uv} \ge 0$ on the constraint $x_u + x_v \le 1$ is the LP shadow price of that edge: by complementary slackness $y_{uv} > 0$ implies the constraint binds. Cost: one LP solve.

### SDP θ dual

Lovász's $\vartheta$ has a constraint $X_{uv} = 0$ for every edge $uv \in E$. The Lagrange multiplier $\mu_{uv}$ on this constraint is the SDP shadow price. Cost: one SDP solve.

### Hoffman gradient

For $d$-regular $G$, $H(G) = N(-\lambda_{\min}) / (d - \lambda_{\min})$. Hellmann–Feynman gives

$$
\frac{\partial \lambda_{\min}}{\partial A_{uv}} \;=\; 2\, w_{\min}[u]\, w_{\min}[v],
$$

where $w_{\min}$ is the unit eigenvector at $\lambda_{\min}$. Combined with $\partial H / \partial \lambda_{\min}$, this gives a closed-form per-edge gradient.

Caveat: when $\lambda_{\min}$ has multiplicity $\ge 2$, $w_{\min}$ is not unique and Hellmann–Feynman gives a basis-dependent answer. We detect this and return None. Empirically the entire frontier set hits this case (Cayley/SAT graphs are spectrum-saturated).

---

## Files

| File | Purpose |
|---|---|
| `edge_methods.py` | Edge-removal attribution methods used by test 1. |
| `nonedge_methods.py` | Non-edge addition attribution methods (eight total) used by tests 2 and 3. |
| `run_edge_gradients.py` | Test 1 driver — perturbed-edge identification. |
| `run_followpath.py` | Test 2 driver — saddle-escape gradient following. |
| `run_globality.py` | Test 3 driver — global attribution prediction. |
| `plot_followpath.py` | α(t) trajectory plot from test 2 CSV. |
| `results.csv` / `summary.csv` | Test 1 per-edge / per-graph outputs. |
| `followpath_results.csv` / `followpath_summary.csv` | Test 2 outputs. |
| `globality_results.csv` | Test 3 output. |
| `followpath_alpha_trajectory.png` | Trajectory plot. |
| `results.md` | Human-readable digest of all three tests. |

---

## Headlines

See `results.md` for full numbers and per-test discussion. The one-line summary of each test:

1. **Test 1 (perturbed edges):** SDP θ dual hits 100% precision@1 on the redundant-edge identification task and matches drop-$E_{\max}$ at $\sim 40\times$ less cost. Local hard-core (`drop_l_hc`) scores 25% — the obvious local form of the hard-core idea fails outright.
2. **Test 2 (saddle escape):** Hard-core co-marginal $\rho_{uw}$, SDP $X_{uw}$, and drop-$E_{\max}$ all achieve 15/15 perfect saddle escape with mean α drop = 2.07 in 20 steps. $\rho_{uw}$ is fastest at 0.37 s/seed; SDP at 0.96 s/seed; drop-$E_{\max}$ at 14.7 s/seed. Local hard-core lands at 8/15 (worse than random). LP at 14/15 mid-pack. **The hard-core hypothesis is vindicated, but only after redirecting from the one-body marginal $\rho_v$ to the two-body co-marginal $\rho_{uw}$.**
3. **Test 3 (global attribution):** SDP $X_{uw}$ at $t = 0$ correlates only weakly with drop-α at $t = T$ (Spearman $+0.13$ vs random's $+0.04$; top-1 pick α-critical at $T$ only 1/7 times). The signal is direction-correct, not attribution-correct.

---

## What this experiment establishes

> **The hard-core model gives a tight per-edge α direction-signal, indexed by vertex pairs (the two-body correlation $\rho_{uw}$), at lower cost than its SDP counterpart $X_{uw}$. The signal is reliable as a rollout heuristic but does not produce precise per-edge attribution to specific load-bearing edges in the final state, consistent with the 17% structural slack of $\vartheta$ over $\alpha$ on this graph class.**

Three layered findings in this single sentence:

1. **The right hard-core quantity for per-edge information is the two-body co-marginal $\rho_{uw}$, not the one-body marginal $\rho_v$.** This isn't a small technical correction — it's the difference between an object that fails outright (test 1: $L_{HC}$-derivative scores 25%) and one that ties the best methods (test 2: $\rho_{uw}$ at 15/15). Edges are pairs of vertices, so per-edge information requires a pair-indexed quantity. Once stated this is obvious, but the original framing pointed at the wrong object.

2. **$\rho_{uw}$ and $X_{uw}$ are nearly the same object — second-moment quantities of different convex relaxations of MIS.** The Boltzmann two-point function $\rho_{uw}$ and the SDP second-moment $X_{uw}$ rank edges almost identically in the regimes we tested. $\rho_{uw}$ wins on speed because it's a closed-form expression in independence polynomials; $X$ requires an SDP solve. This is a calibration result, not a theoretical breakthrough.

3. **The signal is a good *direction* signal but a weak *attribution* signal.** Greedy on $\rho_{uw}$ or $X_{uw}$ reliably escapes saddles (rollout heuristic). The signal at $t = 0$ does *not* reliably identify the specific edges that will be load-bearing at $t = T$ (per-edge value function). For an RL agent the practical implication is: use these signals to *choose the next move*; do not use them to *credit specific edges* for eventual α drops. The 17% structural slack of $\vartheta$ over $\alpha$ from `bound_tightness/` is the same gap showing up here in a different form — if the SDP gradient gave precise per-edge α attribution, $\vartheta$ would equal $\alpha$ on K₄-free graphs and the frontier wouldn't have a plateau. We know it does. So the slack is structural, not a solver artefact.

The buried surprise from test 3: in 8 of 15 runs no single added edge was α-critical at $G_T$. We added 20 edges, α fell by 2 or 3, but you could remove any one of those 20 without α going back up. **α didn't drop because of any specific edge — it dropped because of the collective density.** Per-edge attribution may be the wrong question for this regime: asking "which raindrop caused the flood." That is a structural fact about the saddle-escape trajectories we ran, not necessarily a universal claim about K₄-free α — but it strongly suggests caution about credit-assignment formulations on these graphs.

---

## Open questions

- [ ] What about *non*-frontier graphs at moderate density — does the precision@1 advantage of the SDP dual hold, or only on the near-α-critical regime?
- [ ] Does the test-3 result change if we run the trajectory using drop-α greedy instead of SDP greedy — i.e. does the choice of trajectory method affect what the t=0 ranking predicts?
- [ ] Larger perturbations (add 5 or 10 edges, not 1): does the rank correlation strengthen at intermediate states?
- [ ] Can the SDP dual or $\rho_{uw}$ be computed *incrementally* as edges are added/removed in search, avoiding a fresh solve per step? An order-of-magnitude inner-loop win is on the table.
- [ ] How does the calibrated $\rho_{uw}$ signal compare to a learned graph-neural-network attribution trained on drop-α labels?
- [ ] Add-and-remove generalisation: now that add-only works, is there a clean "remove a present edge to lower α via the same two-body correlation" formulation?

---

## Theorems that would be nice to prove

- **Conjecture (direction-vs-attribution gap is structural).** For every K₄-free $G$ and every α-flat saddle starting graph $G_0$ with $\alpha(G_0) > \alpha^*$, the Spearman correlation between $X_{uw}(G_0)$ and drop-$\alpha(G_T, \cdot)$ on the SDP-greedy added edges is bounded above by some constant $c < 1$ that depends on the $\vartheta/\alpha$ ratio.
  *Why it matters:* would explain rather than just observe the test-3 weakness. The 17% structural slack would directly imply an upper bound on global per-edge attribution quality from any SDP-derived signal.

- **Conjecture (two-body sufficiency for direction).** For random K₄-free graphs at the saddle-density regime, $\rho_{uw}$-greedy and $X_{uw}$-greedy reach the same final α with probability $1 - o(1)$ as $N \to \infty$.
  *Why it matters:* would justify replacing SDP solves with the cheaper $\rho_{uw}$ in any RL inner loop, with a clean asymptotic guarantee.
