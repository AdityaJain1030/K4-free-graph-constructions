# `experiments/a_critical_bias/` — softmax K₄-free walk biased toward α-critical witnesses

## Compute

- **Environment:** `k4free` conda env, local.
- **Typical runtime:** seconds at N≤20; ~1–5 min/trial at N=30 with `--lb-restarts 4`. Higher `--lb-restarts` or `--audit` (exact CP-SAT post-run check) adds proportionally.
- **Memory:** <500 MB.
- **Parallelism:** single-threaded; trials run sequentially inside one `EdgeFlipWalk`.

---

## Background

Theorem 1 of [`docs/theory/A_CRITICALITY.md`](../../docs/theory/A_CRITICALITY.md) says: for every N ≥ 10, the K₄-free `c_log` minimum is attained by an α-critical graph. SAT searches with an α-critical hard constraint (`search/SAT/sat_a_critical.py`) implement this directly, but at N=30 they have not improved on the `disjoint_lift` row in `graph_db` (c_log=0.7195).

This experiment asks whether a *softer* approach — biasing a random walk toward α-critical regions of K₄-free space, without enforcing it — can navigate around what we suspect are α-critical "islands" (see the conversation thread that motivated this folder; the islands argument is summarised in [`docs/theory/A_CRITICALITY.md`](../../docs/theory/A_CRITICALITY.md) §6 commentary).

The key design choice: per-candidate scoring uses a **cheap structural surrogate** for α-criticality, not the exact `#non-α-critical-edges`. The surrogate is the sum of three counts that *correlate* with α-criticality:

| Component | What it counts | α-critical implication |
|---|---|---|
| `s_min_deg` | vertices with deg < 3 | basic α-critical (Lemma 6) requires deg ≥ 3 |
| `s_twin` | unordered pairs `(u,v)` with `N[u]=N[v]` | basic α-critical = duplication-free = twin-free |
| `s_hajnal` | vertices with deg > N − 2α + 1 (using `α_lb`) | Hajnal cap on α-critical graphs (Lemma 2) |

A graph with all three at zero is *necessarily* basic and Hajnal-compliant — a strong necessary condition for α-criticality. False negatives are tolerated; the exact post-run check (Lemma 4 vertex-local α-criticality test, `--audit`) catches any divergence between surrogate and truth.

True `#non-α-critical-edges` would cost `|E|` `α_lb` calls per state, ~20 s/step at N=30 — infeasible inside the per-candidate scorer. The exact counter lives in `penalties.exact_non_critical_edges` for diagnostic snapshots only.

---

## Question

Does adding a soft α-criticality bias to a c_log-driven add+remove walk produce better K₄-free witnesses than the unbiased version (λ=0)? In particular, can it match or beat `disjoint_lift` at N=30 when seeded from the lift?

---

## Approach

Same scaffolding as `experiments/random/add_remove_edges_weighted.py`: an `EdgeFlipWalk` with the full add+remove valid set proposed at every step, scored by a `batch_score_fn`, selected via softmax with temperature β.

**Score:**

```
energy(G) = c_log_surrogate(G) + λ · pen(G)
score(m)  = -energy(G_after_m)
```

`pen` is the structural surrogate above (default weights `(1, 1, 1)`). `c_log_surrogate` uses `α_lb` with `--lb-restarts` restarts (default 4). At λ=0 the walk reduces to a c_log-only descent (the control).

**Move set:** every K₄-free edge add or remove is a candidate. Adds are filtered through the K₄ check (`utils.graph_props.adding_induces_k4`); removes are unconditional.

**Seeding:**
- `empty` (default): start from the empty graph.
- `from-db`: start from the current best non-SAT-derived K₄-free graph at N (mirrors `cluster_sat._seed_hint_graph`). At N=30 this is the disjoint lift.
- `random-bk`: start from a Bohman–Keevash random saturation fill.

**Stop rules:** `none` (run to `max_steps` / saturation), `edges` (target edge count), `alpha` (CP-SAT every K steps until α drops to a target).

**β = ∞ greedy ablation:** the framework already supports greedy via `beta=float("inf")` in the underlying softmax (`search/stochastic_walk/walk.py:_select`). The `sweep_beta.py` driver includes it as a first-class point in the sweep.

**Audit:** `--audit` runs an exact post-run check on each trial's final graph using Lemma 4's vertex-local form: for each vertex `v`, compute `α(G[V\\N[v]])` exactly via CP-SAT and check it equals `α(G) − 1`. Reports `is_a_critical` and `n_non_critical_v` (number of vertices that fail the test). This is the single source of truth for "did the walk actually reach an α-critical witness?".

---

## Files

| File | Purpose |
|---|---|
| `add_remove_a_critical.py` | Main driver. Single-config run with all knobs as flags. Use `--lam`, `--beta`, `--stop`, `--seed-graph`, `--audit`. Pass `--beta inf` for greedy. |
| `penalties.py` | Surrogate components (`s_min_deg`, `s_twin`, `s_hajnal`), combined `surrogate_penalty`, and the slow `exact_non_critical_edges` for audit-style use. |
| `sweep_lambda.py` | λ-ablation at fixed (N, β). Defaults `λ ∈ {0, 0.01, 0.1, 1, 10}`. Writes `results/lambda_sweep_n{N}_beta{β}.csv`. |
| `sweep_beta.py` | β-ablation at fixed (N, λ). Defaults `β ∈ {1, 2, 4, 8, ∞}`. Writes `results/beta_sweep_n{N}_lam{λ}.csv`. |
| `sweep_n.py` | N-ablation at fixed (λ, β). Defaults `N ∈ {15, 20, 25, 30}`. Writes `results/n_sweep_lam{λ}_beta{β}.csv`. |
| `results/` | CSV outputs from sweeps. |

---

## Results

**Status:** closed-negative on the basic surrogate; see [`RESULTS.md`](RESULTS.md) for the full breakdown.

Headline: at N=20, β=4, empty seed, none of the five λ values improve over the unbiased control on c_log (four tie at c_log=1.2288, λ=0.01 is strictly worse), and **no λ produces an α-critical witness** — every trial has ≥4 vertex-level Lemma-4 audit failures. The bias does shrink audit failures by ~50% at λ=0.1, but at no c_log advantage.

Mechanism: the walk easily reaches `surrogate = 0` (basic + Hajnal compliance) at any moderate λ, after which the penalty gradient flattens and the walk reverts to c_log-only behavior. The basic structural correlates are *necessary but not sufficient* for α-criticality — empirically too coarse to drive the walk into the actually-α-critical region.

Recommended next step: replace the basic surrogate with the sharper `s_lemma4` proxy `#{v : α_lb(G\N[v]) ≠ α_lb(G) − 1}`. See `RESULTS.md` for details.

---

## Open questions

- [ ] At N=20, does any λ > 0 improve best c_log over the λ=0 control? (run `sweep_lambda.py --n 20 --beta 4 --audit`)
- [ ] Greedy (β=∞) vs softmax (β=4) — does greedy collapse to local minima or actually exploit the bias more cleanly? (run `sweep_beta.py --n 20 --lam 1.0`)
- [ ] At N=30, can `--seed-graph from-db` plus any bias setting *improve* on `disjoint_lift` (c_log=0.7195)? This is the headline question; cheap to test once the lower-N sweeps tune (λ, β).
- [ ] Does the structural surrogate match the exact α-criticality count? Cross-check by running `--audit` and comparing `n_non_critical_v` (exact) with `n_min_deg + n_twin + n_hajnal` (surrogate) — if they diverge often, the surrogate is misleading and we need a different penalty.

---

## Theorems that would be nice to prove

- **Conjecture (islands):** For every N ≥ 15, there exist α-critical K₄-free graphs `G₁, G₂` at the same N with `c_log(G₁) ≈ c_log(G₂)` such that no path of single-edge K₄-free flips between them keeps every intermediate α-critical.
  *Why it matters:* would formally rule out strategy (A) from the conversation (strict α-critical-only walk) and justify spending tabu effort on diversification rather than constraint encoding.
