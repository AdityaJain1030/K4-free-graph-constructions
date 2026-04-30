# `experiments/`

The empirical / computational arm of the project. Every K₄-free graph
construction, every solver benchmark, every diagnostic run lives here.

**One subfolder = one research question, not one technique.** Walk-style
algorithms appear in `random/`, `greedy/`, `local_search/`, `tabusearch/`
and `mcmc/` — siblings because they answer different questions, not
because they're different paradigms. Folders that look ML-flavored
(`ai_search/`, `DQN/`) are split the same way: `ai_search/` is
LLM-in-the-loop only, `DQN/` is deep RL only.

The single objective behind everything: minimise

```
c_log = α(G) · d_max / (N · ln d_max)
```

over all K₄-free graphs G. Paley(17) with c ≈ 0.679 is the bar; nothing
in this folder has beaten it.

---

## Quick-reference

| Folder | Question | Status |
|---|---|---|
| [`algebraic_explicit/`](algebraic_explicit/) | Which closed-form algebraic graphs sit on the c_log frontier? | active |
| [`alpha/`](alpha/) | How fast and how accurate is each α solver? | active |
| [`a_critical/`](a_critical/) | What does α-criticality force on optimal graphs? | active |
| [`ai_search/`](ai_search/) | Can an LLM-in-the-loop write better K₄-free constructors? | active |
| `brute_force/` | Exhaustive ground truth at small N | **to create** |
| [`cayley/`](cayley/) | Best Cayley / circulant connection sets per N (likely renames to `circulants/`) | active |
| [`decomposition/`](decomposition/) | Can composing small blocks reach SAT-optimal c? | mostly negative |
| [`DQN/`](DQN/) | Deep Q-learning policy for K₄-free edge construction | planned |
| [`fragility/`](fragility/) | Landscape stability of K₄-free graphs: local Δc_log per move, basin volume, barrier-tree topology | tests A/D/E done |
| [`greedy/`](greedy/) | What does a one-step-ahead greedy reach? | active |
| [`local_search/`](local_search/) | Deterministic local descent — no tabu, no randomness | active |
| [`mcmc/`](mcmc/) | Mixed Markov chains over K₄-free graphs | active |
| [`parczyk_pipeline/`](parczyk_pipeline/) | Cayley + tabu (Parczyk Algorithm 2) and its analysis | active |
| [`random/`](random/) | Trivial-baseline floor + randomised constructions | active |
| [`SAT/`](SAT/) | Certified-optimal CP-SAT pipeline + benchmarks | active |
| [`switch/`](switch/) | Move-set comparison (transitional — will be absorbed) | transitional |
| [`tabusearch/`](tabusearch/) | Generic (non-Cayley) tabu | active |
| [`bound_tightness/`](bound_tightness/) | How tight are α ≤ θ ≤ H ≤ … on extremal candidates? | active |
| [`vertex_by_vertex/`](vertex_by_vertex/) | Vertex-priority construction (negative result) | closed |

---

## `algebraic_explicit/` — closed-form algebraic constructions

**Question.** Which classical / algebraic graphs sit on the c_log frontier?

**Owns.**
- **Erdős–Rényi polarity graphs** ER(q) over PG(2,q) for prime and
  prime-power q (via `utils.algebra.field`) — `run.py`. Backed by
  `docs/searches/algebraic/POLARITY.md`.
- **Brown graph** R(3,k), N=125 — `search/brown.py`, `BROWN.md`.
- **Norm-graph family** (C₄-free relatives) — `search/norm_graph.py`,
  `NORM_GRAPH.md`.
- **Mattheus–Verstraete original** — `search/mattheus_verstraete.py`,
  `MATTHEUS_VERSTRAETE.md`.
- **MV bipartization variant** — `scripts/run_mv_bipartization.py`,
  `MV_BIPARTIZATION.md`, `logs/mv_bipartization/`.
- **MV on GQ(2,2)** — `scripts/run_mv_gq22.py`.
- **SRG catalog screen** (McKay enumeration → sub-Paley filter) —
  `experiments/srg_catalog/run.py`, `SRG_CATALOG.md`. **Verdict: exhausted,
  0 sub-Paley hits below P(17).**
- **Cyclotomic circulant probe** at p∈{37..89}, orders 4 and 6 —
  `scripts/cyclotomic_circulant_probe.py`. **Verdict: 0 hits below
  P(17); best 0.8145 at p=37 sextic Paley.**
- **DeepMind Ramsey ingest** — `scripts/ingest_deepmind_ramsey.py`,
  `DEEPMIND_RAMSEY.md`. External corpus from the AlphaZero+tabu
  R(4,k) paper. *(Lives here as a low-priority external dataset.)*

## `alpha/` — independence-number solver instrumentation

**Question.** How fast and how accurate is each α solver on the
graphs we actually feed it?

**Owns.**
- `bench_alpha.py` + `ALPHA_PERFORMANCE.md` — runtime per (solver, N).
- `bench_alpha_accuracy.py` + `ALPHA_ACCURACY.md` — α_lb / α_ub /
  greedy-MIS / clique-cover B&B / CP-SAT correctness against truth.
- `generate_graphs.py` — bench corpus generator.
- **Greedy-MIS-as-proxy validation** — `funsearch/experiments/initial_validations/`.
  Spearman ρ=0.99 vs true α at N=40..80; SAT α-eval mean < 0.4 s, max
  2.88 s at N=80. This finding is the reason FunSearch infrastructure
  to *avoid* SAT calls was abandoned.

## `a_critical/` — α-critical theory

**Question.** What does "every edge is essential to α" force on the
structure of optimal K₄-free graphs?

**Broader than `decomposition/`.** This folder owns the *theory* —
α-critical proofs, d_max bounds derived from α-criticality, the
α-critical / α-dropping incompatibility result, and the depth-2 IS-join
counterexample. `decomposition/` owns the *generators* that try to
exploit that theory.

**Headline results so far** (in `funsearch/so_far.md` §3.4, to be
migrated):
- α-critical reduction: optimal graphs must be α-critical (correct,
  proved, but not operationally useful — every search returns
  trimmable graphs).
- α-critical and α-dropping are *mutually exclusive*: an α-critical
  graph has zero α-dropping IS, so iterative IS-join enrichment
  cannot bootstrap.
- Depth-2 counterexample: IS-join α formula breaks at depth ≥ 2;
  gap grows as Θ(depth).

**Open.** d_max bounds — partially in `docs/theory/`, not yet
consolidated.

## `ai_search/` — LLM-in-the-loop only

**Question.** Can a Claude / FunSearch-style LLM agent write K₄-free
constructors that beat human + heuristic search?

**Owns.**
- **Claude-in-loop optimiser** — `claude_search/` (CLAUDE.md, RULES.md,
  eval.py, leaderboard.py, candidates/, results.jsonl, insights.md,
  thoughts.md, NON_VT_CATALOG.md). Append-only history of LLM-written
  candidates and their c_log scores.
- **OpenEvolve analysis** — `funsearch/openevolve_vendor/`,
  `funsearch/OPENEVOLVE_ANALYSIS.md`.
- **Evolutionary loop** — `funsearch/experiments/evo_search/`. Best
  graphs at N=30/40/50/60.
- **FunSearch problem framing** — `funsearch/summary.md`,
  `funsearch/so_far.md`, `funsearch/CATALOGUE.md`. The single
  surviving theoretical contribution: K₄-free ⇔ triangle-free
  neighborhoods, O(d²) per edge.

**Excluded by design.** DRL approaches (DeepMind's AlphaZero+tabu
work, GFlowNets, our own DQN plans) are *not* LLM-in-the-loop and
live elsewhere — DeepMind's data in `algebraic_explicit/`, our DQN
work in `DQN/`.

## `brute_force/` — exhaustive ground truth (to create)

**Question.** What is the actual Pareto frontier at N where exhaustive
enumeration is feasible?

**Will own.**
- `search/brute_force.py` — geng-driven enumeration with α via SAT.
- `reference/pareto/` — committed Pareto JSONs at N=3..14.
- `reference/regular_sat/` — degree-pinned ground truth.

Used as the source-of-truth oracle that every other folder validates
against.

## `cayley/` — Cayley graphs over abelian groups

**Question.** Over abelian-group Cayley constructions Cay(Γ, S) at fixed
N, which connection sets minimise c_log?

**Likely renames to `circulants/`** since the abelian case is what
matters in practice; non-abelian Cayley work has migrated to
`parczyk_pipeline/`.

**Owns.**
- **Residue-class Cayley** Cay(Z_p, R_k) for k∈{2,3,6} —
  `search/cayley.py`, `CAYLEY.md`.
- **Exhaustive circulants** N≤35 — `search/circulant.py`, `CIRCULANTS.md`.
- **Scalable circulant DFS** N up to ~127 — `search/circulant_fast.py`,
  `scripts/run_circulant_fast.py`, `CIRCULANT_FAST.md`.
- **Bi-Cayley over Z_17** — `scripts/bicayley_sweep.py`,
  `logs/bicayley_z17*.log`.
- **Hand-curated special Cayley** — `scripts/build_special_cayley.py`,
  `special_cayley.json`.

## `decomposition/` — composing small blocks

**Question.** Can a small K₄-free block library + a composition rule
reach SAT-optimal c?

**Currently in `funsearch/experiments/`, to migrate.**
- **IS-join block library + compositions** — `block_decomposition/`.
  83 blocks at n≤8, 593 α-dropping IS, 351 649 compositions
  vectorised in 5 min 41 s.
- **Block-optimal follow-up** — `block_optimal/`.
- **Forced-matching construction** — `forced_matching/`.
- **Pair-forced construction** — `pair_forced/`.
- **Selective cross-edge (FunSearch Path A)** — `selective_crossedge/`.
  Depth ablations at N=16/20/24.
- **Reachability** — `reachability/`.
- **Composition screen** — `results/composition_screen/`.

**Verdict so far (negative).** SAT-optimal graphs at N=10..22 are *not*
IS-join-decomposable across any of the 2^N partitions tested.
Composition ceilings sit 15–25% above SAT-optimal across N=10..21.
The IS-join bipartite seam is the structural bottleneck.

## `DQN/` — deep Q-learning (planned)

**Question.** Can a learned Q-function over (state = current graph,
action = edge to add/flip) outperform tabu search on c_log?

**Empty placeholder.** Framing in `docs/RL.md` and the four
GFlowNet / AlphaZero papers in `docs/papers/`.

## `fragility/` — landscape stability of K₄-free graphs

**Scope.** Originally narrowly scoped to "P(17) and its perturbations
/ lifts / blow-ups". Broadened on 2026-04-29 to *landscape-stability
analysis*: how does c_log respond to local moves, where does descent
terminate, and what is the barrier-tree topology of the K₄-free graph
space? See `experiments/fragility/README.md` for the four-object
framework (local Δ-distribution, basin volume, barrier tree, Markov
spectral gap) and `experiments/fragility/results.md` for the
consolidated results.

**Owns.**

- **Test A — local Δc_log distribution.** `run_delta_distribution.py`,
  `summarise_delta.py`, `plot_delta_distribution.py`,
  `plot_fragility_vs_n.py`. For each (frontier seed, move family, N)
  enumerate / sample legal moves and report the Δc_log distribution.
  Done for cayley/circulant/SAT/random across N=10..39.
- **Test E — basin volume from random init.** `run_basin_volume.py`,
  `plot_basin_volume.py`. Random K₄-free seed at matched density,
  greedy descent under add+delete, count target hits. **0/200 hits
  at every N=10..22.**
- **Test E variant — basin radius under switch.**
  `run_basin_radius.py`, `plot_basin_radius.py`. Perturb the target
  by K random switches, descend back. Negative under sampled
  best-improving descent at N=30 (0/20 across K).
- **Test D — barrier tree / disconnectivity graph.**
  `run_barrier_tree.py`, `plot_barrier_tree.py`,
  `plot_landscape_scatter.py`. Stream `geng -k`, build move-adjacency
  over a c_log slice, run Kruskal-on-energy. Counts both connected
  components and combinatorial local minima (where best-improving
  descent terminates). Done at N=7..11; N=10/11 with tight thresholds
  isolating the SAT-optimum's c_log shelf.
- **Shared infra.** `move_taxonomy.py` (add/del/flip/slide/switch
  primitives + `sample_n_proposals` for descent), `indicators.py`
  (per-seed structural metrics: edge sensitivities, ρ_c, Hoffman
  saturation, θ slack, K₄-margin).
- **Inherited paley/lift sub-experiments** (still here, but lower
  priority): `scripts/run_fragility.py` (v0 trajectory study,
  superseded by Test A), `scripts/paley_randomized_blowup.py`,
  `scripts/run_blowup.py` + `BLOWUP.md`, `scripts/verify_p17_lift.py`
  + `P17_LIFT_OPTIMALITY.md`, `scripts/verify_dihedral.py`,
  `scripts/ingest_disjoint_lifts.py`, `LIFT_STRUCTURE.md`.

**Headline findings (see `experiments/fragility/results.md` for full
detail and tables).**

1. *Frontier graphs are 4–10× more fragile per move than random*
   K₄-free graphs at the same N (in relative Δc_log / c_log units).
   The order-of-magnitude separation persists at every N tested,
   except the N=35 Cay(Z₅×Z₇) plateau where mean Δ collapses to 0.
2. *Random K₄-free seeds never reach SAT/Cayley/brute_force optima*
   under add+delete descent (0/200 at N=10..22).
3. *The K₄-free move-graph is connected at loose thresholds, but
   has many combinatorial local minima* — 1 → 694 → 5476 at
   N=7 → 8 → 9, ~8× per N step. Test E's failure is the direct
   shadow of this trap count.
4. *SAT failure mode (the punchline)*: at tight thresholds isolating
   the SAT-optimum's c_log shelf, the **shelf itself fragments**.
   At N=10 the (3,4) shelf has 12 disconnected components and the
   SAT optimum sits in the **second-largest** island. **At N=11 the
   SAT optimum is an isolated singleton on its shelf** — no add or
   delete move from it stays on the shelf. Local search using
   K₄-preserving moves has no shelf-internal path to the SAT optimum
   at N ≥ 11. This is the precise structural reason SAT is necessary
   and heuristic search cannot replace it.

**Status.** Tests A and D closed; Test E has a definitive 0/200
result; basin-radius killed under sampling ambiguity. Test C is a
synthesis of A's per-move data, no new sweep planned. Open
follow-ups: extend D to N=12+ with batched-enumerator amortisation,
extend A to polarity / Brown / MV families, the SDP-biased sampler
for basin-radius.

## `greedy/` — degree-aware greedy baselines

**Question.** With one greedy choice per edge / vertex (no
backtracking), what's the best c_log we can get?

**Owns.**
- **Random capped** — `random_capped.py`. Add random K₄-free edges
  until vertices reach a target degree.
- **Regularity-seeded greedy** — `regularity.py`,
  `docs/processes/REGULARITY_SEARCH.md`.
- **α-greedy regularity variant** — `regularity_alpha.py`,
  `docs/processes/REGULARITY_ALPHA.md`.

All three are EdgeFlipWalk-based ports of the deleted
`RandomSearch` / `RegularitySearch` / `RegularityAlphaSearch`
classes (2026-04-27 re-port). See folder README for details.

## `local_search/` — deterministic local descent

**Question.** Without randomness or tabu memory, can a steepest-descent
local search push past the random / greedy ceilings?

**Distinct from `random/`** (no sampling), **`greedy/`** (no
construction-from-scratch), **`tabusearch/`** (no memory), and
**`mcmc/`** (no detailed-balance chain).

**Owns.**
- **α-targeted descent** — `scripts/run_alpha_targeted.py`,
  `ALPHA_TARGETED.md`. Local moves that strictly reduce greedy α.
- **Near-regular seed + edge-switch hill-climb** —
  `scripts/run_random_regular_switch.py`, `RANDOM_REGULAR_SWITCH.md`.
- **(some)** P(17) per-N analysis where the mechanism is local
  perturbation rather than algebraic lift — see `fragility/`.

## `mcmc/` — Markov-chain edge sampling

**Question.** Does a properly mixed Markov chain over K₄-free graphs
find anything heuristic search misses?

**Owns.**
- **MCMC** — `scripts/run_mcmc.py`.
- **Stochastic-walk theory** — `docs/theory/STOCHASTIC_WALK.md`.

## `parczyk_pipeline/` — Cayley + tabu (Parczyk Algorithm 2)

**Question.** Over the orbit space of Cayley connection sets, can
Parczyk-style tabu beat exhaustive enumeration, and at which N?

**This is the dedicated home for *Cayley-tabu* — distinct from generic
tabu in `tabusearch/`.** The pipeline is: pick a group → enumerate
inversion-orbit-respecting connection sets → tabu-search → SAT-verify
→ promote to graph_db.

**Owns.**
- **Hand-coded group families** (Z_n, D_n, Z_2^k, Z_3 × Z_2^k,
  Z_a × Z_b) — `scripts/run_cayley_tabu.py`, `CAYLEY_TABU.md`.
- **GAP SmallGroups full sweep** order ≤ 144, NumberSmallGroups ≤ 500
  — `scripts/run_cayley_tabu_gap.py`, `_parallel.py`,
  `cluster/CAYLEY_TABU_GAP.sub`, `CAYLEY_TABU_GAP.md`.
  **Verdict:** 5 PRs found; α / Hoffman / θ invariant across lifts;
  Hoffman-saturated on the 8 spectrum-eligible graphs (memory
  2026-04-23).
- **Per-N breakdown** — `CAYLEY_TABU_GAP_PER_N.md`.
- **Polarity-N targeted Cayley** — `scripts/run_cayley_tabu_polarity_ns.py`,
  `logs/cayley_tabu_polarity_ns/`.
- **PSL(2,q) Cayley** — `scripts/run_psl_tabu.py`,
  `utils/algebra.py` (the `psl2` factory), `logs/psl_tabu/`.
- **Asymmetric lift tabu** — `scripts/asymmetric_lift_tabu.py`,
  `logs/asymmetric_lift_tabu/`.
- **Persistence + comparison utilities** —
  `scripts/persist_cayley_tabu.py`, `compare_cayley_tabu.py`.
- **Pipeline write-up** — `docs/theory/PARCZYK_PIPELINE.md`.

## `random/` — random baselines and randomised constructions

**Question.** How low does c_log go with no structure at all? — the
floor that every other approach must beat.

**Owns (baselines).**
- `baseline_random.py`, `baseline_random_efw.py` (edge-flip-walk variant).
- `baseline_weighted_random.py`, `baseline_weighted_random_efw.py`.
- `sweep_configs.py`, `sweep_configs_efw.py`, `SWEEP_RESULTS.md`,
  `THEORY.md`.

**Owns (randomised constructions classified as "random").**
- **Bohman–Keevash sweep** — `docs/processes/BOHMAN_KEEVASH.md`,
  `experiments/random/bohman_keevash.py` (`--sweep`),
  `experiments/random/results/bohman_keevash_sweep.csv`. The canonical pseudorandom
  K₄-free generator.

**Headline.** Random edge addition with a degree cap: c ≈ 1.1–1.2 at
N=40..80, roughly flat. The trivial baseline.

## `SAT/` — certified-optimal CP-SAT pipeline

**Question.** What is the *certified* min-c K₄-free graph at each N,
and how far up the N axis can the solver reach?

**Already populated.** Existing files:
- `SAT.md` — theoretical foundations (min c ⇔ min |E|,
  near-regular heuristic, β-parametrisation).
- `OPTIMIZATION.md`, `MIN_DEG.md` — solver-acceleration ablations,
  branch-on-min-degree heuristic.
- `RESULTS_N20.md`, `RESULTS_N30.md` — per-N certified results.
- `bench_joint_vs_sweep.py` — joint-vs-Pareto-sweep timing.
- `NEXT.md` — open optimisation directions.

**To migrate from `scripts/`.**
- **Main exact pipeline** — `search/sat_exact.py`,
  `scripts/run_sat_exact.py`, `SAT_EXACT.md`.
- **Proof pipeline** — `run_proof_pipeline.py`, `prove_box.py`,
  `verify_optimality.py`, `proof_report.py`. Cluster submit file
  stays in `cluster/PROOF_PIPELINE.sub`.
- **N=20 benchmark** — `SAT_N20_BENCHMARK.md`.
- **Optimization ablations** — `ablate_sat_exact.py`,
  `logs/sat_exact_ablation.json`.
- **Regular-pin benchmark** — `bench_sat_regular.py`,
  `SAT_REGULAR.md`, `logs/bench_sat_regular*.{log,json,stdout}`.
- **Near-regular non-regular** — `run_sat_near_regular_nonreg.py`,
  `report_sat_near_regular_nonreg.py`, `SAT_NEAR_REGULAR_NONREG.md`.
  Memory 2026-04-24: 130 non-VT iso on N=14..25; 55 tie frontier;
  0 beat.
- **SAT over circulant indicators** — `run_sat_circulant.py`,
  `prototype_sat_circulant{,_fast}.py`.
- **Pareto-optimal circulants** — `run_sat_circulant_exact.py`,
  `run_sat_circulant_optimal.py`, `verify_sat_circulant_optimal.py`.
- **Recovery utilities** — `recover_sat_regular_graphs.py`.
- **Regularize checks** — `check_regularize_c_optimal.py`,
  `check_regularize_nonregular.py`,
  `logs/regularize_c_optimal.{json,log}`,
  `logs/regularize_check.{json,log}`.
- **Symmetry breaking / edge-lex** — memory `project_edge_lex_audit`
  2026-04-21: k_max rows ≥ 1 sound but 2000× slower at boundary
  boxes; default dropped to 0. `sat_exact.py` still has the old
  edge_lex (flagged).
- **Stuck-N forensics.** `diag_n23_*.py` (×4),
  `run_n23_{ablation,composite,factorial}.py`, `run_n34_push.py`,
  `target_n83_a12.py`, `logs/n19_a4_retry.stdout`. These all
  diagnose specific N values where SAT (or near-regular SAT) hit
  a wall. Open: may split into `experiments/stuck_n/` if they
  grow further.

## `switch/` — move-set comparison (transitional)

Currently holds `compare_switch.py` only. Will be absorbed into the
four-folder taxonomy (`random/`, `greedy/`, `local_search/`,
`tabusearch/`) once each move-set's analysis is folded into the
folder that uses it.

## `tabusearch/` — generic (non-Cayley) tabu

**Question.** On the move space of edge swaps and 2-switches over
arbitrary K₄-free graphs (not just Cayley orbits), how good is plain
tabu?

**Owns.**
- **Edge / 2-switch tabu** — `scripts/run_switch_tabu.py`, `SWITCH_TABU.md`.
- **Mixed move-set + lookahead** —
  `scripts/run_switch_tabu_mixed_lookahead.py`.
- (Shares `search/tabu.py` — generic bitvec tabu — with
  `parczyk_pipeline/`.)

## `bound_tightness/` — how tight are the known bounds?

**Question.** Given the chain α ≤ θ' ≤ θ ≤ χ_f(Ḡ), and α ≤ H for regular
graphs, how close to equality do extremal candidates sit, and where is
the slack? Also includes the hard-core *lower* bound E_max as the
counterpart for benchmarking.

**Owns.**
- **Per-graph driver** — `bound_tightness/run_tightness.py` runs every
  bound (Hoffman, Lovász θ, Schrijver θ', χ_f(Ḡ), greedy clique cover,
  hard-core E_max) against the canonical implementations in
  `utils/alpha_bounds.py`. CLI flags `--c-max`, `--n-max`,
  `--per-n-best`, `--hardcore-n-max`.
- **Per-graph CSV** — `bound_tightness/results.csv` (frontier scan
  c_log ≤ 0.74) and `bound_tightness/results_per_n.csv` (top-1 per N
  up to N=100). Columns: graph_id, source, n, d_max, α, c_log, every
  bound value, every bound's wall time, every tightness ratio.
- **Plots** — `bound_tightness/plot_tightness.py` produces
  `tightness_by_n.png` and `tightness_by_clog.png`, scatter plus
  per-family median trend coloured by graph family (Cayley plateau,
  SAT-certified, circulant, disjoint lift, brute force).
- **Digest** — `bound_tightness/results.md`.

**Related (kept distinct from per-graph bounds).**
- **Local-hard-core calibration** — `experiments/hardcore_local/`.
  Establishes that the local lower bound $L_{HC}$ recovers only ~34% of
  α on the K₄-free frontier, ruling out neighbourhood-only hard-core
  arguments as a path to the plateau.
- **Tensor-product Hoffman screen** — `scripts/spectrum_balance_screen.py`.
  Predicts Hoffman of G₁ ⊗ G₂ from factor spectra; constructive screen
  for compositions, not a per-graph bound.
- **Clique-cover fingerprint** — `scripts/clique_cover_screen.py`.
  Max-clique pair-intersection histogram and "spread" flag — structural
  fingerprint, not an α bound.
- **c_log surface analysis** — `scripts/analyze_c_log_surface.py`.
  Regression / PCA over the Hoffman column.
- **Hoffman comparison** — `docs/hoffman_comparison.md`.

## `vertex_by_vertex/` — vertex-priority construction (closed)

**Question.** Can a `priority(vertex_index) → graph` skeleton (FunSearch
cap-set style) work for K₄-free graphs?

**Verdict: no.** Sequential vertex addition produces star-like graphs
(d_max = N−1, c > 10) regardless of priority function. Even
`inverse_degree`, the best structured choice, gives c ≈ 2.9–4.6
increasing with N. See `funsearch/so_far.md` §4.1.

This folder stays as a documented negative result so the same idea
isn't re-attempted.

---

## Migration backlog

What is **not yet** physically in `experiments/` but is conceptually
owned by it:

- Most `scripts/run_*.py` still drive `search/*` modules from
  `scripts/`. Each is listed under its destination folder above;
  physical relocation is pending.
- `funsearch/experiments/` is still the live tree for
  `decomposition/`, parts of `ai_search/`, parts of `alpha/`. Listed
  above; relocation pending.
- `cluster/` files (`PROOF_PIPELINE.sub`, `CAYLEY_TABU_GAP.sub`,
  `run_*.sh`) **stay in `cluster/`** by topic decision. Each
  experiment README links to the cluster file it depends on.
- Infrastructure that is *not* an experiment stays in `scripts/` /
  `highlights/` / `graph_db/`: `repair_graph_store_n65.py`,
  `db_cli.py`, `open_visualizer.py`.
- Theory write-ups in `docs/theory/` (`BEYOND_CAYLEY.md`,
  `EMPIRICAL_REGULARITY.md`, `EXPERIMENT_LOG.md`,
  `SESSION_LOG_*`, …) stay in `docs/`. Each topic README references
  the theory docs it builds on.
- `experiments/switch/` is transitional and will be split.

---

## How to add a new experiment

1. Pick the folder whose **question** your experiment answers, not
   the technique it uses. When in doubt, look for the verdict line
   in each topic above; if your verdict belongs alongside one of
   those, that's the home.
2. If no folder fits, propose a new sibling — folders are topics, so
   a genuinely new question gets a new folder cheaply.
3. Each folder must have a `README.md` with: question, approach,
   owned files, verdict (or "open"), pointer to the underlying
   theory doc in `docs/`.
4. Persist results in `graph_db` via `GraphStore` (canonical sparse6
   keyed). Analysis CSVs are fine in-folder; raw graph batches go
   to `graphs/`.
