# `experiments/fragility/` — landscape stability across N, families, and move-sets

> **Scope note.** `experiments/README.md` currently scopes this folder
> narrowly: "Paley(17) and its perturbations / lifts / blow-ups." This
> README broadens it to *landscape-stability analysis* — the question
> that motivates measuring c_log perturbations in the first place.
> Paley-specific lifts/blow-ups (`scripts/paley_randomized_blowup.py`,
> `verify_p17_lift.py`, etc.) remain inputs to the family comparison
> here but are no longer the whole story; they may eventually move to
> `algebraic_explicit/` as a `paley_lifts/` subfolder. Update the
> `experiments/README.md` quick-reference row when this lands.
>
> **Design note.** An earlier draft (replaced) framed everything around
> trajectory-mean random walks. That collapses four mathematically
> distinct landscape objects into one summary — see §"Background"
> below. The current design measures each object directly.

---

## Compute

- **Environment:** `k4free` conda env (numpy, networkx, ortools for
  exact α, cvxpy/SCS for θ). No cluster needed for the core tests.
- **Typical runtime:**
  - Test E (basin volume): 1000 random K₄-free seeds × greedy descent
    × α-exact verification. ~30 min at N=17, ~2 h at N=22.
  - Test A (Δ-distribution): cheap. ~|E|·|non-neighbour-set| α calls
    per seed. ~1 min for 30 seeds at N=20.
  - Test D (barrier tree): hard. Tractable only at N ≤ 14 where the
    relevant slice of K₄-free graph space is enumerable. Estimated
    1–4 h at N=12, depending on slice depth.
  - Test C (move-set sanity): unchanged from earlier — ~30 min at
    `α=approx`, 4–8 h at `α=exact`.
- **Memory:** trivial (<1 GB) for A/C/E. D needs ~|graphs in slice|² for
  the saddle search — fits in memory at N ≤ 14.
- **Parallelism:** all four tests parallelise over seeds; not yet
  multiprocessed.

---

## Background

### Why measure stability at all

The decision the rest of `experiments/` is waiting on:

> Can local search (`local_search/`, `tabusearch/`, `mcmc/`, `DQN/`,
> `ai_search/`) ever reach a c_log < 0.679 graph at large N, or do
> all wins have to come from algebraic constructions?

The honest version of that question is:

> Do the c_log frontier graphs sit in **basins** that descent can
> reach from random K₄-free starting points, or are they isolated
> attractors with vanishing basins?

That is a **basin-volume** question, not a trajectory question.

### Four landscape objects, only one of which the v0 measured

Different "stability" questions correspond to different mathematical
objects on the K₄-free graph space $\mathcal G_N$ with energy $c_{\log}$
and adjacency given by a chosen move family $M$:

| Object | Question | Mathematical content | Literature |
|---|---|---|---|
| **A. Local differential structure** | "If I perturb $G_0$, what is the *distribution* of one-step changes?" | Empirical measure $\mu_{G_0}^{(M)}(\Delta) = \Pr[c_{\log}(G') - c_{\log}(G_0) = \Delta]$. Tails matter. | Wales, *Energy Landscapes* (CUP 2003) |
| **B. Global basin structure** | "Are the good graphs clustered or isolated?" | **Disconnectivity graph / barrier tree**: nodes = local minima, edge weights = min over $M$-paths of max $c_{\log}$ along path. | Flamm–Hofacker–Stadler (RNA, 2000s); Wolynes (proteins) |
| **C. Algorithmic accessibility (basin volume)** | "If I start a descent at random, how often do I land at $G_0$?" | $\mathrm{Basin}(G_0) = \{G : \mathrm{descent}_M(G) \to G_0\}$; observable is $\Pr[\text{random init} \to G_0]$. | Local-search theory; SAT landscapes |
| **D. Markov chain geometry** | "How connected is $\mathcal G_N$ under $M$?" | Spectral gap $1 - \lambda_2$ of transition matrix; Cheeger's inequality. | Levin–Peres, *Markov Chains and Mixing Times* |

The earlier `docs/theory/FRAGILITY.md` v0 ran a **single random walk
under one move (slide), recorded the trajectory mean** and called the
result "fragility". That is

- a **mean** of object A (throwing away its tails),
- a **proxy** for object D (mixing-time-like via half-life),
- and **does not touch** B or C — which are the decision-relevant ones.

The v0 conclusion ("Δ-curves fan out by N, basin widens") is a
statement about D, not B. We do not yet know whether the c_log frontier
graphs have large basins or small ones.

### What the move-set is

The move family is the adjacency relation defining $\mathcal G_N$.
Different moves give *different* graphs $\mathcal G_N$, hence different
trees, different basin volumes, different spectral gaps. They are not
interchangeable; each is the right choice for a different downstream
algorithm:

| Symbol | Move | Preserves | Used by |
|---|---|---|---|
| `add+del` | $G \pm e$ | nothing | `DQN/`, `ai_search/`, agent-style RL |
| `flip` | $G - e + f$ on disjoint pair | $|E|$ | EdgeFlipWalk in `random/` |
| `slide` | $G - uv + uw$, common $u$ | $\deg(u)$ | v0 fragility (with spread cap) |
| `switch` | $G - e_1 - e_2 + f_1 + f_2$ | full degree sequence | `random_regular_switch`, KTV chain |
| `alg-flip` | toggle inversion-orbit in $S$ for $\mathrm{Cay}(\Gamma, S)$ | group structure | `parczyk_pipeline/` |

Test C runs the same probes under multiple moves to check whether
fragility shape is a property of $G_0$ or of the (graph, move) pair.

### Structural indicators recorded at every seed

To attribute landscape behaviour to structure, every test records the
following at $G_0$:

- **Edge sensitivities** $\Delta_e = \alpha(G - e) - \alpha(G)$ for
  every $e \in E$. Reuses
  `experiments/edge_gradients/edge_methods.py:drop_alpha`. The
  distribution of $\{\Delta_e\}$ is a **local combinatorial object**,
  not a walk; it directly controls the left tail of $\mu_{G_0}^{(\text{del})}$.
- **Edge-criticality fraction** $\rho_c(G) = |\{e : \Delta_e > 0\}| / |E|$.
- **Hoffman saturation** $\alpha / H$ (regular only) — `bound_tightness/`.
- **θ slack** $\vartheta(G) - \alpha(G)$.
- **Move-graph in-degree at $G_0$** for each $M$ — count of legal
  proposals.
- **K₄-margin** — non-edges whose addition creates K₄.

---

## Question

Three questions, each pinned to a specific landscape object.

(a) **Family-stratified differential structure (object A).** *How does
    the one-step Δc_log distribution change with N, controlled for
    family?* Concretely: for each family $\mathcal F$ ∈ {random,
    near-regular hill-climb, Cayley plateau, SAT-certified, brute-force
    optimum, polarity}, what is the shape of $\mu_{G_0}^{(M)}$ — left
    tail (improving directions exist?), right tail (catastrophic
    moves?), entropy?

(b) **α-criticality and tails (object A, structural).** *Does
    α-criticality of $G_0$ control the right tail of
    $\mu_{G_0}^{(\text{del})}$?* The clean version is the trivial
    direction: $\rho_c = 1$ ⇒ every $\Delta_e > 0$ ⇒ the
    deletion-distribution has *no* left tail. The non-trivial
    direction is for `slide`/`switch`: do α-critical seeds have
    heavier positive tails than non-α-critical seeds at the same
    $(N, c_{\log})$?

(c) **Decision-relevant basin volume (object C).** *Are c_log
    frontier graphs reachable by greedy descent from random init?*
    For each frontier seed $G^*$, estimate $\Pr[\mathrm{descent}_M(G_0) = G^*]$
    over random $G_0$. Tiny basin ⇒ local search cannot find $G^*$
    no matter how good the heuristic; large basin ⇒ a learned
    descent rule has a target.

We additionally run object **B** (barrier tree) at small $N$ as a
structural cross-check; object **D** (Markov chain) is now a
*sanity check*, not a main result.

---

## Approach

Tests ordered by decision-relevance. Test E is the headline.

### Test E — basin volume under greedy descent (object C)

The most important test in this folder.

1. Pick frontier targets $G^* \in$ {Paley(17), Cayley plateau winners
   at N ∈ {17, 19, 22}, SAT-certified optima at N ∈ {15, 18, 20},
   Mattheus–Verstraete witness} with their canonical IDs.
2. For each $N$ in the target set, sample random K₄-free graphs at
   matched density (rejection-sampled Erdős–Rényi at $p = 2|E(G^*)|/N(N-1)$,
   or seeded Bohman–Keevash from `experiments/random/`).
3. Run **greedy c_log-descent** under each move family $M \in
   \{\text{add+del}, \text{slide}, \text{switch}\}$ until no
   improving move exists. Verify endpoint with α-exact.
4. Record:
   - endpoint canonical_id
   - did endpoint match $G^*$? a known frontier graph? a new local min?
   - descent length
   - final $c_{\log}$
5. Estimate $\hat p_{M}(G^*) = \frac{\#\{\text{runs ending at } G^*\}}{K}$
   for $K$ = 1000 starts per (move family, N) cell.

**Decision rule.**
- $\hat p \geq 10^{-2}$: large basin, a learned descent rule should
  reach it.
- $\hat p \in [10^{-4}, 10^{-2}]$: small but findable basin; needs
  guided search.
- $\hat p < 10^{-4}$: effectively unreachable from random init;
  algebraic-only.

This is the test the rest of `experiments/` is actually waiting on.

### Test A — local differential structure (object A)

Replaces the v0's trajectory-mean with a proper distributional probe.

For each seed × move family:
1. Enumerate (or uniformly sample 1000) legal moves at $T = 1$.
2. Compute $\Delta_i = c_{\log}(G_0 + \text{move}_i) - c_{\log}(G_0)$
   for each.
3. Report the histogram, plus:
   - $\Pr[\Delta < 0]$ (improving moves exist?)
   - $\Pr[\Delta > \tau]$ for $\tau \in \{0.01, 0.05, 0.1\}$ (catastrophic-move risk)
   - Shannon entropy of binned histogram (anisotropy / flatness)
   - mean (for backwards comparison with v0)
4. For the special case $M = \text{del}$, $\Delta_i$ is exactly the
   sensitivity $\Delta_e$ from §"indicators". So $\rho_c$ falls out
   for free as $\Pr[\Delta_e > 0]$ on the deletion distribution.

Cost is $|E| + |\text{slide moves}| + |\text{switch pairs}| \approx O(N^4)$
α calls per seed, with α via `alpha_approx`. At N=20 this is < 1 min.

### Test D — barrier tree at small N (object B)

The only test that requires near-exhaustive enumeration of a slice of
$\mathcal G_N$.

1. Pin $N$ small (start with $N = 12$). Enumerate all K₄-free graphs
   on $N$ vertices via `geng -X K4` (`search/brute_force.py`),
   restricted to a c_log slice, e.g. $c_{\log} \leq c_{\log}(G^*) + 0.2$.
2. Build the move adjacency graph $\mathcal G_N^{(M)}$ over that
   slice. Use `switch` (degree-preserving, smaller branching) for
   tractability.
3. Identify local minima (no neighbour with strictly lower $c_{\log}$).
4. For each pair $(G_a, G_b)$ of local minima, find the **min-max
   $c_{\log}$ path** in $\mathcal G_N^{(M)}$ — saddle height between
   the two basins. Standard bottleneck shortest path; an MST in the
   weighted complete graph of minima gives the entire dendrogram in
   one shot (Boruvka-style).
5. Render the dendrogram (Flamm–Hofacker–Stadler style):
   `barrier_tree_n12.png`.

**Decision rule.** Disconnected sub-trees with high saddles
separating the global min from a "shoulder" of near-optimal minima
⇒ basins are deep and isolated. One big merged tree
⇒ basins are shallow and connected.

Cost: dominated by the slice size and saddle-search step. Feasible
at N=12, marginal at N=14, infeasible at N=16+ without sampling
heuristics. Sampling shortcut: Wales-style **basin-hopping** (random
perturbation + descent) gives an empirical sample of the tree's
leaves; pair them up via short bottleneck searches.

### Test C — move-set comparison (sanity, object D + cross-test)

Demoted from "main result" to "consistency check" — different moves
give different landscapes, and we want to know which test conclusions
are move-invariant.

For 15 seeds spanning families and α-criticality bins:
1. Run Test A under each $M \in \{\text{add+del}, \text{slide},
   \text{switch}, \text{alg-flip}\}$.
2. Cross-correlate per-seed (left-tail probability under move 1) vs
   (left-tail probability under move 2). High correlation ⇒
   fragility shape is a property of $G_0$, not the move; low ⇒ the
   choice of move matters and Test E should be re-run per move.
3. For Cayley/regular seeds, compute the Davis–Kahan / Weyl bound
   on Hoffman per-edge swap (closed form from $\lambda_{\min}$ and
   eigenvector). Compare to empirical Hoffman shift under switch.
   If they agree to within a constant, **spectral perturbation
   theory predicts Hoffman fragility from $G_0$ alone** — closed-form
   prediction of α fragility on Hoffman-saturated graphs without any
   simulation.

---

## Files

| File | Purpose |
|---|---|
| `move_taxonomy.py` | Shared move primitives: `add`, `del`, `flip`, `slide`, `switch`, `alg_flip`. Wraps existing `utils/edge_switch.py`. |
| `indicators.py` | Per-seed structural metrics: edge sensitivities, $\rho_c$, Hoffman saturation, θ slack, move-graph in-degree, K₄-margin. |
| `run_basin_volume.py` | Test E driver. Random-init descent → endpoint canonicalisation → basin frequency table. Writes `basin_volume.csv`. |
| `run_delta_distribution.py` | Test A driver. Enumerates / samples legal moves, returns histograms. Writes `delta_dist.parquet`. |
| `run_barrier_tree.py` | Test D driver. geng-enumerated slice → bottleneck MST → dendrogram. Writes `barrier_tree_n{N}.json`, `.png`. |
| `run_move_taxonomy.py` | Test C driver. Cross-product of seeds × moves; writes `move_taxonomy.csv`. |
| `plot_basin_volume.py` | Bar/CDF plot of $\hat p_M(G^*)$ per family per N. |
| `plot_delta_distribution.py` | Histogram + tail-overlay plot per (seed, move). |
| `plot_barrier_tree.py` | Dendrogram renderer (matplotlib + plotly). |
| `results.md` | Headlines + numbers once tests run. |
| `data/` | Raw per-seed outputs in JSON / parquet. |

**Inherited / referenced (do not duplicate):**

- `scripts/run_fragility.py`, `docs/theory/FRAGILITY.md`,
  `visualizer/plots/data/fragility.json`,
  `visualizer/plots/images/fragility.png` — v0 (single-family,
  single-move, mean-collapsed). Kept as the prior result this
  experiment supersedes.
- `utils/edge_switch.py` — slide + switch primitives.
- `utils/graph_props.py:alpha_approx`, `alpha_bb_clique_cover`,
  `c_log_value`, `find_k4`.
- `experiments/edge_gradients/edge_methods.py:drop_alpha` — used by
  Test A and indicators.
- `experiments/bound_tightness/` — Hoffman / θ at the seed.
- `docs/theory/A_CRITICALITY.md` — α-critical theorems used in Test A
  hypothesis.
- `search/brute_force.py` (`geng -X K4`) — slice enumeration for Test D.

---

## Status

**open / planning.** README + design only as of 2026-04-29; scripts
and CSVs not yet produced. The v0 trajectory plot
(`visualizer/plots/images/fragility.png`) is the prior result this
will revise.

Recommended ordering for first implementation pass:

1. `indicators.py` + `move_taxonomy.py` (shared infra).
2. **Test A** (`run_delta_distribution.py`) — cheapest, immediately
   informative, replaces v0 directly.
3. **Test E** (`run_basin_volume.py`) — the headline.
4. Test D (`run_barrier_tree.py`) — tractable only at small N; do
   after E gives the strategic answer.
5. Test C (`run_move_taxonomy.py`) — once A and E are running, the
   cross-move sanity check is mechanical.

---

## Open questions

- [ ] Right density to sample random K₄-free seeds at for Test E:
      match $G^*$'s edge count exactly, or sweep $|E|$? Edge-count
      mismatch could cap $\hat p_M(G^*)$ below 1 trivially.
- [ ] In Test E, descent step rule: best-improving (steepest)
      vs first-improving vs randomised greedy? Each defines a
      different basin. Run all three.
- [ ] Test D scaling: where does N have to cap for full enumeration?
      Bohman–Keevash sampling could substitute at N=18–22 if we
      accept missing-leaf risk in the dendrogram.
- [ ] Theory: is there a closed-form basin-volume bound from edge
      sensitivities $\{\Delta_e\}$? A graph with all $\Delta_e$ very
      positive (deeply α-critical) has a basin that contains every
      $G_0 + \epsilon$ with $\epsilon$ small; the question is whether
      the basin extends past 1-step neighbours.
- [ ] Cayley/Paley case: by symmetry, all edges have the same $\Delta_e$
      under group action. Does this force the basin to also be
      symmetric, and what does that say about its size?
- [ ] Mixing-time / spectral-gap estimate (object D) is now optional.
      Skip unless we want to compare to Cheeger constants computed
      directly from the slice.

---

## Theorems that would be nice to prove

- **Conjecture (α-criticality and the deletion-distribution).** If
  $\rho_c(G) = 1$, then $\mu_G^{(\text{del})}(\Delta < 0) = 0$ —
  every deletion strictly decreases α and therefore strictly
  decreases $c_{\log}$ when $d_{\max}$ is preserved.
  *Why it matters:* the cleanest possible link from a static
  invariant to a landscape statement. The non-trivial side is the
  $\rho_c < 1$ regime, where left-tail mass quantifies how much α
  slack the graph carries.

- **Conjecture (Davis–Kahan ⇒ α fragility on Hoffman-saturated graphs).**
  If $G$ is $d$-regular K₄-free with $\alpha(G) = H(G)$, then for
  any switch-move neighbour $G'$,
  $|c_{\log}(G') - c_{\log}(G)| \leq C \cdot d_{\max} / (N \ln d_{\max} \cdot \mathrm{gap}(G))$,
  where $\mathrm{gap}(G)$ is the spectral gap at $\lambda_{\min}$.
  *Why it matters:* spectral-gap-controlled fragility on the
  Cayley/Paley plateau gives a structural reason that any local
  search is forced to leave the plateau before improving — and a
  closed-form predictor of the Δ-distribution under switch.

- **Conjecture (basin volume of frontier graphs decays
  super-polynomially in N).** $\hat p_M(\text{Paley-like-frontier})
  \leq N^{-\omega(1)}$ under random-init greedy descent for any
  edge-local move family $M$.
  *Why it matters:* if true, this is the formal statement that
  *local search cannot reach the c_log frontier at scale*, settling
  the open question that motivates the entire `local_search/` /
  `DQN/` / `ai_search/` family. Paley-style algebraic constructions
  are then the only path.

---

## Literature anchors and search prompts

The four-object decomposition above rests on standard machinery; the
prompts below are sharp queries to run through your internet-connected
Claude session before we commit code, in priority order.

1. **Barrier trees on graph spaces (object B).** *"Have barrier-tree /
   disconnectivity-graph methods (Flamm, Hofacker, Stadler ~2002,
   Klemm–Stadler) been ported from RNA / spin-glass landscapes to
   *graph-valued* state spaces? In particular for Ramsey-type or
   K-free extremal graph problems?"* Answer determines whether Test D
   has a published prior we should follow vs. whether it's a clean
   first.
2. **Basin-volume estimation in combinatorial optimisation (object C).**
   *"What sampling-based estimators of attractor / basin volume are
   standard in SAT, MAX-CUT, or spin-glass landscape analysis? Best
   refs for variance and bias of $\hat p$ from random-restart greedy
   descent."* Should anchor the choice between exact-match-counting
   and importance-weighted estimators in Test E.
3. **PatternBoost basin claims (Charton–Wagner et al.).** *"What
   exactly does the PatternBoost paper measure when it argues local
   transformer-guided search reaches extremal constructions, and how
   does its 'basin' notion line up with object C above?"* Direct
   prior on whether their evidence already answers our Test E
   question for some related extremal problems.
4. **Spectral perturbation on K-free move graphs.** *"Best-known
   per-edge bound on $\lambda_{\min}$ change under a switch move on
   $d$-regular graphs (Davis–Kahan vs Bauer–Fike vs Weyl), and any
   existing application to Hoffman-bound-tight graphs."* Theory
   anchor for the Test C closed-form Hoffman predictor.
5. **Edge-criticality / α-critical post-2020.** *"Has anything
   moved on α-critical theory since Lovász–Plummer (1986) and
   Valencia–Leyva (2007), specifically in the K-free setting?"*
   Anchor for the conjecture relating $\rho_c$ to the
   $\mu_G^{(\text{del})}$ tail.
6. **Mixing time of switch chains on K-free graphs.** *"What is
   known about the spectral gap of the degree-preserving 2-edge
   switch Markov chain restricted to K₄-free graphs (or any
   $H$-free)? Anchor: Tikhomirov–Youssef-style chain-restriction
   bounds."* Lets us calibrate Test C's optional object-D probe.
7. **Cayley + Fourier on the move space.** *"For $\mathrm{Cay}(\Gamma, S)$,
   the connection-set move family `alg-flip` acts on a Boolean cube
   of inversion-orbits. Does representation theory / Fourier on
   $\Gamma$ give a closed form for the spectral gap of this
   sub-chain, in the spirit of Diaconis–Shahshahani?"* Sharper Cayley
   analogue of the Test C theory check.
