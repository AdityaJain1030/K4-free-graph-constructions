# 4cycle — K₄-free graph constructions

## What this project is about

The whole repository attacks a single open problem in extremal graph theory:

> **Conjecture.** Every K₄-free graph on `N` vertices with max degree `d` has
> an independent set of size at least `c · N · log(d) / d` for some universal
> constant `c > 0`.

The best proved bound (Shearer, 1995) only gives `√log d` instead of `log d`,
and no one has improved it in 30 years. The repository treats the problem
computationally: **find K₄-free graphs that minimize**

```
c = α(G) · d_max / (N · ln(d_max))
```

Small `c` = near-counterexample. The benchmark to beat is the Paley graph
`P(17)` with `c ≈ 0.6789`. Nothing in this repo has beaten it; the work
maps the landscape around it from many angles.

---

## Setup

### 1. Install `micromamba`

```bash
# Linux / WSL2
curl -Ls https://micro.mamba.pm/install.sh | bash
# macOS (bash/zsh)
curl -Ls https://micro.mamba.pm/install.sh | zsh
# Windows — use WSL2; native is unsupported (nauty's autotools build does
# not target MSVC).
```

Restart your shell so `micromamba` is on PATH.

### 2. Create the `k4free` env

```bash
micromamba env create -f environment.yml
```

Installs Python 3.12 + scientific stack (numpy / scipy / matplotlib /
plotly / networkx), the SAT stack (ortools, python-sat), GAP (SmallGroups
backend for Cayley searches), and a C compiler chain.

### 3. Build `nauty`

```bash
micromamba activate k4free
bash scripts/setup_nauty.sh
```

Downloads nauty 2.9.3, builds it inside the env, wires `geng` and
`labelg` onto PATH via a conda activation hook. `geng` drives brute-force
enumeration; `labelg` backs canonical-id computation. `graph_db` refuses
to run without `labelg`.

### 4. Smoke test

```bash
micromamba run -n k4free python scripts/test_search.py    # framework
micromamba run -n k4free python scripts/run_random.py     # random baseline
```

Use `micromamba run -n k4free <cmd>` for one-off invocations without
activating.

---

## Top-level map

| Path | Purpose | Status |
|---|---|---|
| `experiments/` | **Per-question research folders.** Where the actual work lives. | active |
| `search/` | Reusable construction-algorithm classes. Imported by experiments and scripts. | active |
| `graph_db/` + `graphs/` | Unified database of all canonical graphs found, with property cache. | active |
| `utils/` | Shared primitives: α solvers, K₄ check, nauty/geng wrappers, algebra. | active |
| `visualizer/` | Interactive UI over `graph_db`. | active |
| `docs/` | Theory write-ups (`docs/theory/`) and per-search algorithm notes (`docs/searches/`). | active |
| `scripts/` | Driver CLIs and orchestration. **Cesspool — see "Tech debt" below.** | needs cleanup |
| `funsearch/` | FunSearch-style construction evolution. **Partly migrated to experiments/.** | partial migration |
| `openevolve/` | OpenEvolve framework vendor + experiments. **Logs need cleaning.** | needs cleanup |
| `cluster/` | HTCondor submit files and shell launchers. **No management system.** | needs cleanup |
| `cache.db` | SQLite cache of computed properties. Gitignored, rebuilt on demand. | data |
| `reference/` | Pre-`graph_db` historical CP-SAT scans. Used for cross-validation. | archive |
| `logs/` | Run logs (per-search and aggregate). | data |

The single objective behind every folder is `c_log = α · d_max / (N · ln d_max)`.
Each folder asks a different question about how to push this number down.

---

## `experiments/` — research questions, one folder per

This is where most of the substantive work lives. **One subfolder = one
research question, not one technique.** Walk-style algorithms appear in
`random/`, `greedy/`, `local_search/`, `tabusearch/`, `mcmc/` —
siblings because they answer different questions. ML-flavored work
(`ai_search/`, `DQN/`) is split the same way. See
`experiments/README.md` for the full quick-reference table; below is the
short version.

| Folder | Question | Status |
|---|---|---|
| `algebraic_explicit/` | Closed-form algebraic graphs on the c_log frontier (polarity, Brown, MV, norm, srg_catalog, cyclotomic, …) | active |
| `alpha/` | α-solver instrumentation: speed, accuracy, surrogate validity | active |
| `a_critical/` | α-critical theory + d_max bounds for optimal K₄-free graphs | active |
| `a_critical_bias/` | α-critical bias sweeps | active |
| `ai_search/` | LLM-in-the-loop construction (claude_search, OpenEvolve, FunSearch) | active |
| `bound_tightness/` | How tight are α ≤ θ ≤ Hoffman / hardcore on extremal candidates? | active |
| `brute_force/` | Exhaustive ground truth at small N (to-create) | planned |
| `cayley/` | Best Cayley / circulant connection sets per N | active |
| `decomposition/` | Composing small blocks (block_decomposition, IS-join) | mostly negative |
| `DQN/` | Deep RL on K₄-free edge construction | planned |
| `edge_gradients/` | Per-edge α signals for RL credit assignment (SDP θ-dual, hard-core ρ_uw) | active |
| **`fragility/`** | **Landscape stability — local Δc_log, basin volume, barrier-tree, SAT failure mode** | **tests A/D/E done** |
| `graph_space_visualization/` | 2D / 3D embeddings of the K₄-free graph space | active |
| `greedy/` | One-step-ahead greedy floor | active |
| `hardcore_local/` | Local hard-core lower bound calibration | active |
| `local_search/` | Deterministic local descent — no tabu, no randomness | active |
| `mcmc/` | Mixed Markov chains over K₄-free graphs | active |
| `parczyk_pipeline/` | Cayley-tabu over GAP SmallGroups + PSL(2, q) | active |
| `random/` | Trivial baseline + Bohman–Keevash random K₄-free process | active |
| `SAT/` | Certified-optimal CP-SAT pipeline + benchmarks | active |
| `srg_catalog/` | McKay SRG catalog screen (N ≤ 40) | closed-negative |
| `switch/` | Move-set comparison (transitional) | will absorb |
| `tabusearch/` | Generic non-Cayley tabu | active |
| `vertex_by_vertex/` | Vertex-priority FunSearch skeleton | closed-negative |

**Headlines and decisions on a per-folder basis live in
`experiments/README.md` and each folder's own `README.md` /
`results.md`.** The fragility folder's results.md is the most
comprehensive recent example.

---

## `graph_db/` + `graphs/` — the data layer

Two stores:

1. **`graphs/` folder (committed)** — JSON arrays of
   `{id, sparse6, source, metadata?}`, one file per producing source
   (~25 source tags as of writing). Read/written via `GraphStore`.
2. **`cache.db` (SQLite, gitignored)** — one row per graph with every
   computable property typed: degree sequence, girth, triangles,
   spectral radius, Laplacian spectrum, α (CP-SAT-exact), c_log,
   Lovász θ, hardcore E_max, MIS / triangle / high-degree highlight
   sets, …

Two public classes:

- **`GraphStore`** (producer path) — bare JSON I/O, no cache involvement
  at write time. `search/base.Search.save` uses it.
- **`DB`** (analysis / visualisation path) — combines store with property
  cache. Opening a `DB` auto-syncs new store records into the cache.

Files: `db.py`, `store.py`, `cache.py`, `schema.sql`, `properties.py`,
`encoding.py` (canonical sparse6 + SHA-256[:16] graph_id via labelg),
`clean.py`. Architecture / API / extension docs in
`graph_db/{DESIGN,USAGE,EXTENDING}.md`.

`graphs/` source tags include: `brute_force`, `sat_exact`,
`server_sat_exact`, `sat_regular`, `sat_circulant`, `sat_circulant_optimal`,
`cayley`, `cayley_tabu`, `cayley_tabu_gap`, `circulant`, `circulant_fast`,
`polarity`, `brown`, `mattheus_verstraete`, `norm_graph`, `srg_catalog`,
`disjoint_lift`, `cyclic_exhaustive_min`, `dihedral_exhaustive_min`,
`bohman_keevash`, `random`, `random_regular_switch`, `alpha_targeted`,
`blowup`, `regularity`, `psl_tabu`, `paley_randomized_blowup`,
`special_cayley`, `mv_bipartization`, `deepmind_ramsey`,
`alpha_targeted`, `prime_circulants`, `z11_bicayley_component`. (Some
have only a handful of records; see `db.sources()` for current count.)

---

## `search/` — reusable construction algorithms

A lightweight `Search` abstract base (`base.py`) where each subclass
implements `_run() -> list[nx.Graph]`. `logger.py` handles per-run logs.
Subclasses save into `graph_db` format via `save()`.

**Cayley machinery** lives in `utils/algebra.py`: `GroupSpec`,
inversion-orbit partitioning, hand-coded family factories
(`families_of_order`), GAP SmallGroups bridge
(`families_of_order_gap`), `psl2(q)`,
`cayley_adj_from_bitvec`. The generic bitvec-tabu engine is
`search/stochastic_walk/tabu.py`.

Algorithms (per-search docs in `docs/searches/`):

`brute_force`, `circulant`, `circulant_fast`, `cayley`, `cayley_tabu`,
`cayley_tabu_gap`, `regularity`, `regularity_alpha`,
`mattheus_verstraete`, `polarity`, `norm_graph`, `brown`, `blowup`,
`random`, `random_regular_switch`, `alpha_targeted`, `sat_exact`,
`sat_regular`, `sat_circulant`, `sat_circulant_exact`.

Per-experiment notes are in each `experiments/<topic>/README.md`;
algorithm-internal docs in `docs/searches/`.

---

## `utils/` — shared primitives

- **`graph_props.py`** — typed properties for `cache.db`: `alpha_exact`,
  `alpha_cpsat`, `alpha_bb_clique_cover`, `alpha_approx`, `is_k4_free`,
  `find_k4`, `c_log_value`, `lovasz_theta`, …
- **`alpha_surrogate.py`** — fast `alpha_lb` / `alpha_ub` for inner
  loops.
- **`alpha_bounds.py`** — Hoffman ratio bound, Lovász θ,
  Schrijver θ', χ_f(complement), greedy clique cover, hardcore E_max.
- **`nauty.py`** — `canonical_id`, `canonical_ids` (batched), `geng`
  helper, sparse6 round-trips.
- **`algebra.py`** — group / Cayley primitives (see above).
- **`edge_switch.py`** — degree-preserving switch + slide moves.
- **`ramsey.py`** — hardcoded R(3,k) and proven R(4,k) upper bounds
  used for SAT pre-solve pruning.

---

## `visualizer/`

`visualizer.py` is a tkinter + matplotlib UI backed by `graph_db`.
Filters by source / N / c_log / regularity / etc.; layout choices
(spring, circular, shell, Kamada-Kawai); MIS / triangle / high-degree
highlights; eigenvalue and degree-distribution sidepanels; Hoffman
bound and α/H ratio in the sidebar.

Launch:

```bash
micromamba run -n k4free python visualizer/visualizer.py
```

`--source TAG` restricts to one producer; `--manifest PATH` loads a
custom manifest JSON.

`visualizer/plots/` holds static and interactive over-the-whole-DB
plots (`plot_n_alpha_dmax.py` is the main 3D scatter).

---

## `docs/`

- **`docs/theory/`** — `INDEPENDENCE_NUMBER.md`, `REGULARITY.md`,
  `A_CRITICALITY.md`, `EMPIRICAL_REGULARITY.md`, `FRAGILITY.md`,
  `HARDCORE_TIGHTNESS.md`, `EXPERIMENT_LOG.md` (chronological
  seminar-style tour), and dated session logs.
- **`docs/searches/`** — algorithm-internal write-ups, one per
  `search/*.py` module. Same hierarchy as `search/`.
- **`docs/papers/`** — vendored PDFs of the load-bearing papers
  (Mattheus–Verstraete 2024, Valencia–Leyva 2007, Bohman–Keevash,
  AlphaZero+tabu, GFlowNet survey, …).

---

## How the pieces fit together

```
                  ┌──────────────────────┐
                  │   experiments/<topic>/   │  research questions, one folder per
                  └──────────┬─────────────┘
                             │
                             │ imports / orchestrates
                             ▼
   ┌──────────┐    ┌────────────────┐    ┌────────────┐
   │ search/  │ +  │   utils/       │ +  │  scripts/  │   reusable infra +
   └────┬─────┘    └────────────────┘    └─────┬──────┘   driver CLIs
        │                                       │
        │ writes graphs                         │ writes graphs
        ▼                                       ▼
              ┌───────────────────────────┐
              │   graphs/*.json (committed)  │
              └─────────────┬───────────────┘
                            │
                            ▼ DB.sync auto-imports
              ┌───────────────────────────┐
              │   cache.db (SQLite)          │
              └─────────────┬───────────────┘
                            │
              ┌─────────────┴───────────────┐
              ▼                              ▼
        visualizer/                     experiments/<analysis>/
                                          (consume DB.query for analysis)
```

---

## Tech debt and migration backlog

The repository has accreted a lot of sub-systems over the last few
weeks; here's the honest state.

### `scripts/` is a cesspool

64 files as of writing, mixing:

- *Stable orchestration drivers* that experiments depend on
  (`run_sat_exact.py`, `run_cayley_tabu_gap_parallel.py`,
  `run_proof_pipeline.py`, etc.) — keep, but they should each be
  attached to the experiment that owns them via cross-link or move.
- *Stuck-N forensic scripts* (`diag_n23_*.py`, `run_n23_*.py`,
  `target_n83_a12.py`, `run_n34_push.py`) — should move to
  `experiments/SAT/stuck_n/` if we want to keep the diagnostic
  history; otherwise prune.
- *One-off ingest scripts* (`ingest_disjoint_lifts.py`,
  `ingest_deepmind_ramsey.py`, `paley_randomized_blowup.py`,
  `build_special_cayley.py`) — should move to whichever experiment
  consumes the data, or to `graph_db/ingest/`.
- *Genuinely throwaway* (legacy debug helpers, superseded probes) —
  delete.

The cleanup should preserve the fact that `setup_nauty.sh`, `db_cli.py`,
`open_visualizer.py`, `test_search.py` need to stay at top-level for
human ergonomics. Everything else is up for relocation.

`SCRIPTS.md` at repo root is a partial inventory but predates several
recent additions; treat as informational, not authoritative.

### `funsearch/` is half-migrated

History: `funsearch/` was the original FunSearch-style umbrella. It has
since split into:

- `experiments/ai_search/` (LLM-in-the-loop work; claude_search lives
  here now in spirit, though physically still at repo root)
- `experiments/decomposition/` (block-library / IS-join composition,
  also still physically in `funsearch/experiments/` and needs the move)

What still lives in `funsearch/` and should be migrated:

- `funsearch/experiments/block_decomposition/`,
  `block_optimal/`, `forced_matching/`, `pair_forced/`,
  `selective_crossedge/`, `reachability/`, `evo_search/` →
  `experiments/decomposition/` or `experiments/ai_search/` per topic.
- `funsearch/{summary,so_far,OPENEVOLVE_ANALYSIS,CATALOGUE}.md` →
  consolidate into the relevant experiment READMEs, or into
  `docs/theory/`.
- `funsearch/openevolve_vendor/` → already separate (see below).

`claude_search/` at repo root (the LLM-in-the-loop optimiser with
RULES.md, candidates/, leaderboard.py) was lifted out of `funsearch/`
and is currently active.

### `openevolve/` has accumulated logs

`openevolve/` is the vendored OpenEvolve framework (kept as-is
upstream). Our use of it has produced:

- Run logs in subdirectories that should be cleaned periodically.
- Custom configs in `openevolve/configs/` that ought to live alongside
  the experiment that produced them.

Need a cleanup pass: archive old logs, move configs near their
experiments, add `.gitignore` rules for transient run output.

### `cluster/` has no management system

Currently 4 submit files × 4 launchers, manually edited per run:

- `PROOF_PIPELINE.sub` + `run_job.sh` — SAT proof pipeline
- `CAYLEY_TABU_GAP.sub` + `run_cayley_tabu_gap.sh` — GAP Cayley sweep
- `SAT_BOX.sub` + `run_sat_box.sh` — single SAT box prover
- `VLLM_SERVE.sub` + `run_vllm.sh` — vLLM endpoint for LLM agents

Missing: a routine for queue management, run-result persistence,
re-submission on failure, log aggregation. The current pattern is
"edit submit file, hand-launch, find output by hand." Sufficient for
the current rate of runs but won't scale.

### `docs/` is not fact-checked

Many write-ups in `docs/theory/` and `docs/searches/` were drafted
LLM-assisted and have not been audited line by line. The current state:

- **Wrong / exaggerated claims** exist in several theorem statements,
  proof sketches, and "what we proved" summaries. Treat any
  formal-looking statement as a *conjecture under review* until it's
  been hand-checked.
- **AI-slop sections** — flowery overviews, restated obvious points,
  cargo-culted notation — should be cut. The doc is supposed to be
  a research log, not a tutorial.
- **Stale claims** that haven't been updated as the experiments
  evolved. Some "results" reference scripts that have been deleted or
  superseded; some conjectures have been settled (positive or
  negative) without the doc reflecting it.
- **Irrelevant material** — vendored derivations of standard results,
  off-topic asides, pre-pivot direction-setting that no longer
  matches the current research goal.

What's reliable enough to cite right now (manually checked or backed
by code-verifiable results):

- `experiments/<topic>/results.md` files — written from real run
  output, current.
- `docs/theory/EXPERIMENT_LOG.md` — chronological seminar tour,
  mostly faithful but verify any specific number against the source
  experiment.
- `docs/theory/A_CRITICALITY.md` — the structural lemmas with
  external citations (Erdős–Gallai, Hajnal, Andrásfai–Surányi,
  Lovász–Plummer, Wessel) are correct; the c_log-specific
  reductions (Theorem 1, defect machinery applied to our problem)
  are repo-local and have not been independently checked.
- `docs/papers/` PDFs are vendored upstream papers — those are fine.

The cleanup should run alongside the `scripts/` and `funsearch/`
migrations: each experiment's results.md is the new source of truth,
and the corresponding `docs/searches/` and `docs/theory/` docs need
to be either pruned to the verified core or rewritten against the
experiment's findings.

### Other loose ends

- `cluster_sat/` — appears to overlap with `cluster/`; status unclear,
  candidate for merge or removal.
- `graphs_src/` — looks like an alternate / legacy source tree;
  candidate for merge or removal.
- `results/` — generic top-level results bucket; should probably move
  contents into the relevant `experiments/<topic>/results/`.
- `cayley_tabu_gap.json`, `sat_exact.json` at repo root —
  stragglers that should be in `graphs/`.
- `side_note.md`, `side_note2.md` — personal scratchpads; either move
  to `docs/scratch/` or remove.
- `REFACTOR.md` — predates this README; review for staleness.

A focused cleanup pass should land before the next major experiment
rotation.
