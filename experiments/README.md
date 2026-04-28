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
| [`fragility/`](fragility/) | Paley(17) and its perturbations / lifts / blow-ups, run on every useful N | active |
| [`greedy/`](greedy/) | What does a one-step-ahead greedy reach? | active |
| [`local_search/`](local_search/) | Deterministic local descent — no tabu, no randomness | active |
| [`mcmc/`](mcmc/) | Mixed Markov chains over K₄-free graphs | active |
| [`parczyk_pipeline/`](parczyk_pipeline/) | Cayley + tabu (Parczyk Algorithm 2) and its analysis | active |
| [`random/`](random/) | Trivial-baseline floor + randomised constructions | active |
| [`SAT/`](SAT/) | Certified-optimal CP-SAT pipeline + benchmarks | active |
| [`switch/`](switch/) | Move-set comparison (transitional — will be absorbed) | transitional |
| [`tabusearch/`](tabusearch/) | Generic (non-Cayley) tabu | active |
| [`upper_bound_tightness/`](upper_bound_tightness/) | How tight are α ≤ θ ≤ H ≤ … on extremal candidates? | active |
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
- **Cayley vs non-Cayley comparison plot** — `scripts/plot_cayley_vs_noncayley.py`.

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

## `fragility/` — Paley(17) and its neighborhood

**Question.** P(17) with c ≈ 0.679 is the champion. What happens to c
when we perturb / lift / blow it up, and does this generalise to
every "useful" N?

**Owns.**
- **Paley perturbation collapse** — `scripts/run_fragility.py`,
  `FRAGILITY.md`. Small edge perturbations catastrophically increase α.
- **Paley randomised k=2 blow-up** — `scripts/paley_randomized_blowup.py`,
  `paley_randomized_blowup.json`, `logs/paley_blowup.log`.
- **General blow-up** — `scripts/run_blowup.py`, `BLOWUP.md`.
- **P(17) lift verification** — `scripts/verify_p17_lift.py`,
  `P17_LIFT_OPTIMALITY.md`, `logs/verify_p17_lift/`.
- **Dihedral lift verification** — `scripts/verify_dihedral.py`,
  `logs/verify_dihedral_p17_*.log`.
- **Disjoint-lift ingestion** — `scripts/ingest_disjoint_lifts.py`.
- **Lift structure write-up** — `LIFT_STRUCTURE.md`.

**Planned expansion.** Run the full perturbation / lift / blow-up
analysis at every N where Paley(17) is structurally relevant
(chain N ∈ {17..22}, Cayley lifts at higher orders, dihedral /
bicirculant lifts). Some per-N analysis may live in `local_search/`
instead — the split is by mechanism (algebraic lift vs local
perturbation).

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

## `upper_bound_tightness/` — how tight are the known bounds?

**Question.** Given the chain α ≤ θ ≤ Hoffman ≤ …, how close to equality
do extremal candidates sit, and where is the slack?

**Owns.**
- **Hardcore method tightness (rung 2)** —
  `scripts/run_rung2_exact_hardcore.py`, `plot_rung2.py`,
  `results/hardcore_tightness.csv`, `experiments/random/results/bk_hardcore_exact.csv`,
  `docs/theory/HARDCORE_TIGHTNESS.md`.
- **Lovász θ exhaustive on small K₄-free** —
  `scripts/all_k4free_theta.py`, `all_k4free_theta_analyze.py`,
  `results/all_k4free_theta.csv`.
- **θ on the cached frontier** — `scripts/frontier_theta.py`. Memory
  2026-04-23: `lovasz_theta` column added to graph_db; 18/100
  frontier graphs spectrum-saturated; only the P(17) chain sits
  below the plateau.
- **θ across the GAP-Cayley sweep (rung 3)** —
  `scripts/cayley_gap_theta.py`, `cayley_gap_theta_analyze.py`,
  `run_rung3_lovasz_theta.py`, `plot_rung3.py`,
  `results/cayley_gap_theta.csv`. Memory 2026-04-23: 87.7% have θ < H.
- **Subplan B** — `scripts/run_subplan_b.py`, `plot_subplan_b.py`,
  `docs/theory/SUBPLAN_B.md`.
- **Hoffman comparison** — `docs/hoffman_comparison.md`.
- **Structural screens** (filter graphs whose bounds *could* be tight):
  - `scripts/clique_cover_screen.py`
  - `scripts/spectrum_balance_screen.py`
  - `scripts/analyze_c_log_surface.py`

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
  `highlights/` / `graph_db/`: `build_highlights.py`,
  `repair_graph_store_n65.py`, `regen_cache_with_theta.py`,
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
