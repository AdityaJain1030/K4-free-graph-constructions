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
`P(17)` with `c ≈ 0.679`. Heuristic methods plateau around `c ≈ 0.94` because
of degree irregularity.

Different subfolders attack the same objective from different angles:
exact solvers (SAT/ILP), algebraic constructions (circulants, Cayley graphs,
polarity graphs, Mattheus–Verstraete), regularity-based and random/greedy
baselines, evolutionary/LLM search (FunSearch-style), and a unified graph
database + visualizer to compare everything.

---

## Setup

### 1. Install `micromamba`

Pick the one-liner for your platform. No admin rights needed — it
installs to `~/.local/bin` and `~/micromamba`.

```bash
# Linux / WSL2
curl -Ls https://micro.mamba.pm/install.sh | bash

# macOS (bash/zsh)
curl -Ls https://micro.mamba.pm/install.sh | zsh

# Windows — use WSL2 and follow the Linux path. Native Windows is
# unsupported because nauty's autotools build does not target MSVC.
```

Restart your shell (or `source ~/.bashrc`) so `micromamba` is on `PATH`.

### 2. Create the `k4free` env

```bash
micromamba env create -f environment.yml
```

Installs Python 3.12, the scientific stack (numpy / scipy / matplotlib /
plotly / networkx), the SAT stack (ortools, python-sat), GAP
(SmallGroups backend for `cayley_tabu_gap`), LLM API clients
(anthropic, google-genai, xai-sdk), and a C compiler chain. Takes a few
minutes on a fresh machine.

### 3. Build `nauty`

```bash
micromamba activate k4free
bash scripts/setup_nauty.sh
```

This downloads `nauty 2.9.3`, builds it inside the env
(`$CONDA_PREFIX/src`), and wires the binaries onto `PATH` via a conda
activation hook. `geng` drives brute-force enumeration
(`search/brute_force.py`) and `labelg` backs canonical-id computation
(`utils/nauty.canonical_id`). `graph_db` uses labelg's canonical sparse6
as the isomorphism-class id and refuses to run without it.

### 4. Smoke test

```bash
micromamba run -n k4free python scripts/test_search.py    # search framework
micromamba run -n k4free python scripts/run_random.py     # random baseline N=10..30
```

If both complete, the env is healthy.

### Running commands without activating

`micromamba activate k4free` only sticks for the shell session it's run
in. For one-off invocations prefix with `micromamba run -n k4free …`.

## Top-level layout

| Path              | Purpose                                                          |
|-------------------|------------------------------------------------------------------|
| `environment.yml` | Conda/micromamba environment for the whole repo                  |
| `cache.db`        | SQLite cache of computed graph properties (gitignored, rebuilt)  |
| `graphs/`         | Committed JSON batches of canonical graphs (one per source)      |
| `highlights/`     | Curated ~46-graph slice for human review (see below)             |
| `logs/search/`    | Per-run / aggregate logs from the `search/` framework            |

---

## `highlights/` — curated slice for human review

`highlights/` is a hand-picked subset (~46 graphs out of ~1200) chosen
for what a graph theorist would actually want to look at, instead of
the full DB dump. Structure:

- `README.md` — legend (c_log, Hoffman saturation ratio), tier layout,
  how to read a card.
- `TABLE.md` — master curated table (tier, slug, N, α, d_max, c_log,
  α/H) with links to per-graph cards.
- `graphs/<slug>.md` — one card per graph: property table, construction
  metadata as JSON, canonical sparse6, graph_id.
- `s6/<slug>.s6` — bare canonical sparse6 strings, ready for
  `networkx.from_sparse6_bytes` / `labelg` / `dreadnaut`.
- `index.json` — machine-readable manifest consumed by the visualizer.

Tiers (regenerate via `python scripts/build_highlights.py`):

1. Paley(17), CR(19), and N=22 plateau chains (13 graphs, lift-invariant)
2. SAT-certified optima N=10..20 (11 graphs, proven extremal)
3. Cayley / circulant frontier: non-abelian GAP wins + Frobenius F_21 +
   Pareto-optimal circulants at their unique frontier Ns (14 graphs)
4. Classical / published constructions: Brown, Mattheus–Verstraete,
   Clebsch, Shrikhande (5 graphs)
5. Polarity graphs at large N: ER(q) for q ∈ {7, 11, 17, 23} (4 graphs)

Launch the interactive explorer over just the highlights:

```bash
micromamba run -n k4free python visualizer/visualizer.py --highlights
```

Highlights mode sorts by `(tier, c_log)` so Paley(17) lands first, and
the sidebar surfaces the curated slug, tier, label, and significance
note alongside the standard property table.

---

## SAT / ILP — current pipeline

The active K₄-free CP-SAT pipeline lives in `search/sat_exact.py` +
`scripts/{run_sat_exact,prove_box,verify_optimality,proof_report}.py`.
It handles the full Pareto scan, hard-box optimality proofs, and
certification. See:

- `docs/searches/sat/SAT.md` — theoretical foundations (what we're
  actually minimising, near-regular *heuristic* (proved only for
  `N ≤ 35, d ≤ 7` via Caro–Wei — see `docs/theory/REGULARITY.md §2`),
  min c ⇔ min |E|, β-parametrisation of the conjecture).
- `docs/searches/sat/SAT_EXACT.md` — pipeline walkthrough (model, scan,
  accelerators, `prove_box`, `verify_optimality`).
- `docs/searches/sat/SAT_REGULAR.md` — degree-pinned feasibility scan.
- `docs/searches/sat/SAT_OPTIMIZATION.md` — what sped the solver up,
  what didn't.
- `docs/searches/sat/SAT_N20_BENCHMARK.md` — N=20 certification runtime
  benchmark.

Results land in `graphs/{sat_exact,sat_regular,sat_circulant,sat_circulant_optimal,server_sat_exact}.json`
under their own source tags. `reference/{pareto,regular_sat}/` holds
the historical pre-`graph_db` CP-SAT scans kept around for
cross-validation.

## `cluster/` — HTCondor templates

- `cluster/PROOF_PIPELINE.sub` + `cluster/run_job.sh` — submit file +
  launcher for `scripts/run_proof_pipeline.py`. 32 CPUs / 200 GB
  defaults, tuned for the lab server.
- `cluster/CAYLEY_TABU_GAP.sub` + `cluster/run_cayley_tabu_gap.sh` —
  parallel SmallGroups Cayley-tabu sweep (see
  `docs/searches/CAYLEY_TABU_GAP.md`).

---

## `funsearch/` — FunSearch-style program evolution

Frames the problem the way DeepMind's FunSearch (Nature 2024) framed
cap sets: evolve graph-**construction algorithms**
`construct(N) -> edge_list`, not graphs. The key trick: K₄-free iff
every neighborhood is triangle-free, so the validity check is local
and cheap, and the skeleton handles the constraint for any priority
function.

- `summary.md` — problem framing, why FunSearch fits, surrogate-vs-SAT
  scoring tradeoffs, block-decomposition motivation.
- `so_far.md`, `OPENEVOLVE_ANALYSIS.md` — progress notes.
- `claude_search/` — **LLM-in-the-loop optimizer**. A Claude Code agent
  reads `RULES.md`, runs `eval.py` on candidate constructors it writes
  into `candidates/`, and is ranked via `leaderboard.py`. `CLAUDE.md`
  defines the sandbox. `results.jsonl` is the append-only history.
- `openevolve_vendor/` — vendored copy of the OpenEvolve framework.
- `experiments/` — validation / ablation experiments:
  - `initial_validations/` — does SAT scale to N=40–80? does cheap α
    proxy correlate with truth?
  - `baselines/` — random + greedy baselines, comparison plots.
  - `block_decomposition/`, `block_optimal/` — α-critical block
    library, 1-join composition, SAT-verified enrichment rounds.
  - `forced_matching/`, `pair_forced/` — specific construction families.
  - `evo_search/` — best graphs at N=30/40/50/60 from an evolutionary loop.
  - `reachability/`, `selective_crossedge/` — other tactics.

---

## `graph_db/` — Unified graph database

The glue layer for comparing results across solvers. Two stores:

1. `graphs/` folder (committed) — JSON arrays of
   `{id, sparse6, source, metadata?}` records, one file per source.
2. `cache.db` (SQLite, gitignored) — one row per graph with every
   computable property typed (degree sequence, girth, triangles,
   spectral radius, Laplacian spectrum, α, c_log, Lovász θ, Turán
   density, MIS / triangle / high-degree highlight sets, …).

Two public classes for the two use cases:

- **`GraphStore`** — producer path. Bare JSON-folder I/O; no cache
  involvement at write time. `search/base.Search.save` and ad-hoc
  ingest scripts use it.
- **`DB`** — analysis / visualization path. Combines the store with
  the property cache. Opening a `DB` auto-syncs any new store records
  into the cache.

Files:

- `DESIGN.md`, `USAGE.md`, `EXTENDING.md` — architecture, API, how to
  add a new computed property.
- `db.py` — the `DB` class, `open_db()`, and the auto-sync logic.
- `store.py` — `GraphStore`: JSON batch reader/writer.
- `cache.py`, `schema.sql` — SQLite cache layer + typed column schema.
- `properties.py` — `compute_properties(G, hint)` → full row.
- `encoding.py` — canonical sparse6 + `canonical_id` (SHA-256[:16] of
  canonical form, via nauty's `labelg`).
- `clean.py` — cache rebuild / pruning utilities.

## `graphs/` — The canonical graph store (committed)

JSON batches consumed by `graph_db/`, one file per producing source:

| File | Source tag | What it holds |
|---|---|---|
| `brute_force.json` | `brute_force` | Exact `geng` enumeration, N ≤ 10 |
| `brown.json` | `brown` | Reiman–Brown R(3,k) graph (N=125) |
| `circulant.json` | `circulant` | Exhaustive circulants N ≤ 35 |
| `circulant_fast.json` | `circulant_fast` | Scalable circulant DFS, N up to ~127 |
| `cayley.json` | `cayley` | Residue-class Cayley `Cay(Z_p, R_k)` |
| `cayley_tabu.json` | `cayley_tabu` | Tabu over hand-coded group families |
| `cayley_tabu_gap.json` | `cayley_tabu_gap` | Tabu over every GAP SmallGroup |
| `cyclic_exhaustive_min.json` | `cyclic_exhaustive_min` | Exhaustive cyclic min-α survivors |
| `dihedral_exhaustive_min.json` | `dihedral_exhaustive_min` | Exhaustive dihedral min-α survivors |
| `mattheus_verstraete.json` | `mattheus_verstraete` | Mattheus–Verstraete 2023 R(4,k) family |
| `paley_randomized_blowup.json` | `paley_randomized_blowup` | k=2 random-bipartite blow-up of P(17) |
| `polarity.json` | `polarity` | Erdős–Rényi polarity graphs over PG(2, q) |
| `psl_tabu.json` | `psl_tabu` | Cayley-tabu on PSL(2, q) |
| `random.json` | `random` | Random / randomized-greedy baselines |
| `random_regular_switch.json` | `random_regular_switch` | Near-regular + edge-switch hill-climb |
| `alpha_targeted.json` | `alpha_targeted` | Stochastic local search aimed at α |
| `blowup.json` | `blowup` | Seeded blow-up constructions |
| `regularity.json` | `regularity` | Regularity-partition outputs |
| `sat_circulant.json` | `sat_circulant` | CP-SAT circulant sweep, raw |
| `sat_circulant_optimal.json` | `sat_circulant_optimal` | Pareto-optimal circulants |
| `sat_exact.json` | `sat_exact` | Local CP-SAT certified optima |
| `sat_regular.json` | `sat_regular` | Degree-pinned SAT feasibility witnesses |
| `server_sat_exact.json` | `server_sat_exact` | Cluster-run CP-SAT certified optima |
| `special_cayley.json` | `special_cayley` | Hand-picked algebraic Cayley graphs |
| `srg_catalog.json` | `srg_catalog` | K₄-free survivors from McKay's SRG catalog |

---

## `search/` — Per-N search framework

A lightweight abstraction layer. `base.py` defines an abstract `Search`
class; each subclass implements `_run()` returning `list[nx.Graph]` for
a given `N` (and arbitrary subclass-specific kwargs). `logger.py`
handles per-run logs in `logs/search/`. The framework writes into the
`graph_db` format via `save()`.

- `DESIGN.md` — the spec for the `Search` contract.
- `ADDING_A_SEARCH.md` — playbook / checklist for writing a new search.

Core group machinery used by the Cayley-family searches lives in
`utils/algebra.py`:

- `GroupSpec`, inversion-orbit partitioning, and the hand-coded family
  factories (`Z_n`, `D_n`, `Z_2^k`, `Z_3 × Z_2^k`, `Z_a × Z_b`)
  via `families_of_order(n)`.
- GAP SmallGroups bridge (`families_of_order_gap(n)`) — every group of
  order ≤ 144 with `NumberSmallGroups(n) ≤ 500`.
- `psl2(q)` — `PSL(2, q)` for q prime and q ∈ {4, 8, 9, 16}. Used by
  `scripts/run_psl_tabu.py` and `PSLInvolutionsSearch`.
- `cayley_adj_from_bitvec` / `connection_set_from_bitvec` — turn an
  inversion-orbit bitvector into a Cayley adjacency matrix.

`tabu.py` (under `search/stochastic_walk/`) is the generic bitvec
tabu engine (Parczyk Algorithm 2) that consumes a `GroupSpec`. Used
by `cayley_tabu`, `cayley_tabu_gap`, and `run_psl_tabu.py`.

Algorithm subclasses (per-search notes under `docs/searches/`):

| Module                   | Notes                                        | What it does                                                             |
|--------------------------|----------------------------------------------|--------------------------------------------------------------------------|
| `brute_force.py`         | `docs/searches/BRUTE_FORCE.md`               | Exact enumeration via `nauty geng` (N ≤ 10).                             |
| `circulant.py`           | `docs/searches/circulant/CIRCULANTS.md`      | Exhaustive circulant enumeration for N ≤ 35.                             |
| `circulant_fast.py`      | `docs/searches/circulant/CIRCULANT_FAST.md`  | Scalable K₄-free circulant search (N up to ~127).                        |
| `cayley.py`              | `docs/searches/CAYLEY.md`                    | Residue-class Cayley graphs `Cay(Z_p, R_k)`, k ∈ {2, 3, 6}.              |
| `cayley_tabu.py`         | `docs/searches/CAYLEY_TABU.md`               | Tabu over hand-coded group families' connection sets.                    |
| `cayley_tabu_gap.py`     | `docs/searches/CAYLEY_TABU_GAP.md`           | Same tabu, but over every GAP SmallGroup of order n.                     |
| `regularity.py`          | `docs/searches/regularity/REGULARITY.md`     | Regularity-partition-based construction.                                 |
| `regularity_alpha.py`    | `docs/searches/regularity/REGULARITY_ALPHA.md` | α-optimised regularity variant.                                        |
| `mattheus_verstraete.py` | `docs/searches/MATTHEUS_VERSTRAETE.md`       | Explicit R(4,k) lower-bound family from Mattheus–Verstraete 2023.        |
| `polarity.py`            | `docs/searches/algebraic/POLARITY.md`        | Erdős–Rényi polarity graph ER(q) on PG(2, q). Handles prime and prime-power q via `utils.algebra.field`. |
| `norm_graph.py`          | `docs/searches/algebraic/NORM_GRAPH.md`      | Norm-graph families related to C₄-free extremal constructions.           |
| `brown.py`               | `docs/searches/algebraic/BROWN.md`           | Reiman–Brown R(3,k) lower-bound graph (N=125).                           |
| `blowup.py`              | `docs/searches/BLOWUP.md`                    | Seeded blow-up constructions over a base graph.                          |
| `random.py`              | `docs/searches/RANDOM.md`                    | Random + randomized-greedy baselines.                                    |
| `random_regular_switch.py` | `docs/searches/RANDOM_REGULAR_SWITCH.md`   | Random near-regular seed + degree-preserving edge-switch hill-climb.     |
| `alpha_targeted.py`      | `docs/searches/ALPHA_TARGETED.md`            | Stochastic local search that reduces greedy α directly.                  |
| `sat_exact.py`           | `docs/searches/sat/SAT_EXACT.md`, `docs/searches/sat/SAT_OPTIMIZATION.md` | Certified-optimal K₄-free CP-SAT scan with hard-box proof. |
| `sat_regular.py`         | `docs/searches/sat/SAT_REGULAR.md`           | Degree-pinned CP-SAT feasibility scan (min-edge, one α at a time).       |
| `sat_circulant.py`, `sat_circulant_exact.py` | — | CP-SAT directly over circulant connection-set indicators; the `_exact` variant certifies Pareto-optimality. |

## `scripts/` — Orchestration / helper CLIs

Representative drivers (there are many more — `ls scripts/`):

- **Admin:** `test_search.py` (framework smoke), `db_cli.py` (shell
  DB queries), `open_visualizer.py` (launch tkinter), `setup_nauty.sh`.
- **Per-algorithm drivers:** `run_random.py`, `run_cayley.py`,
  `run_cayley_tabu.py`, `run_cayley_tabu_gap.py`,
  `run_cayley_tabu_gap_parallel.py`, `run_regularity.py`,
  `run_regularity_alpha.py`, `run_mattheus_verstraete.py`,
  `run_random_regular_switch.py`, `run_alpha_targeted.py`,
  `run_brown.py`, `run_blowup.py`, `run_norm_graph.py`,
  `run_polarity.py`, `run_psl_tabu.py` (PSL(2, q)), `run_circulant_fast.py`.
- **SAT drivers:** `run_sat_exact.py`, `run_sat_circulant.py`,
  `run_sat_circulant_exact.py`, `run_sat_circulant_optimal.py`,
  `run_proof_pipeline.py`, `prove_box.py`, `verify_optimality.py`,
  `proof_report.py`, `verify_sat_circulant_optimal.py`.
- **Analysis / hand-curation:** `build_highlights.py` (regenerate
  `highlights/`), `build_special_cayley.py` (classical SRG-Cayley
  ingest), `paley_randomized_blowup.py` (the k=2 random blow-up
  experiment), `frontier_theta.py` (Lovász θ over the frontier),
  `compare_cayley_tabu.py`, `persist_cayley_tabu.py`, `run_sweep_10_40.py`.

## `utils/` — Shared primitives

- `graph_props.py` — computes the typed properties that populate
  `cache.db`. Houses `alpha_exact`, `alpha_cpsat`,
  `alpha_bb_clique_cover`, `is_k4_free`.
- `alpha_surrogate.py` — fast `alpha_lb` / `alpha_ub` for search
  inner loops.
- `nauty.py` — `canonical_id` / `canonical_ids` / `canonical_graph`
  via nauty's `labelg` subprocess, plus `geng` helpers. Mirrors the
  canonical-id logic re-exported from `graph_db/encoding.py`.
- `ramsey.py` — hardcoded Ramsey numbers `R(3,k)`, `R(4,k)` used for
  pre-solve pruning in the SAT solver.

## `visualizer/` — Interactive explorer

- `visualizer.py` — tkinter + matplotlib UI backed by `graph_db`.
  Filters by source, N, c_log, regularity, etc. Highlights: MIS
  vertices, triangles, high-degree vertices, click-to-select
  neighborhood. Layouts: spring, circular, shell, Kamada-Kawai.
  Eigenvalue spectra and degree distribution sidepanels.
  Sidebar reports the Hoffman bound H and the α/H saturation ratio.
  `--highlights` restricts the view to the curated `highlights/`
  slice with slug/tier/label/note enrichment; `--source TAG`
  restricts to one producer; `--manifest PATH` loads a custom
  manifest JSON.
- `plots/` — static and interactive plots over the whole `graph_db`.
  - `plot_n_alpha_dmax.py` — 3D scatter of every cached graph in
    `(N, d_max, α)` with the Caro–Wei floor `α = N/(d_max + 1)` drawn
    as a translucent mesh. Writes a PNG by default; `--html` renders
    a self-contained Plotly WebGL page; `-i` opens a rotatable
    matplotlib window.
  - `images/` — generated output (PNG / HTML).

---

## How the pieces fit together

```
         ┌──────────────────────┐
         │   Search producers   │
         ├──────────────────────┤
   SAT / ILP        ───┐
   sat_regular      ───┤
   circulant*       ───┤
   cayley*          ───┤
   polarity / brown ───┤
   regularity*      ───┼──►  graphs/*.json  (committed batches)
   mattheus_v.      ───┤             │
   random / greedy  ───┤             ▼
   funsearch        ───┤         graph_db
   claude_search    ───┘       (DB auto-sync)
                                     │
                                     ▼
                                 cache.db
                                     │
                                     ├──►  highlights/  (curated subset)
                                     │
                                     ▼
                     visualizer + plots + leaderboards
```

Each producer writes graphs it finds into a `graphs/*.json` batch via
`GraphStore`. Opening a `DB` scans the batch files, computes every
typed property for unseen graphs, and fills `cache.db`. The
visualizer, plots, and any analysis script read from `cache.db` via
`DB.query(...)`, filtered by `source`, `n`, `c_log`, etc. For human
review, `highlights/` snapshots a ~46-graph curated subset with rich
per-graph cards and a manifest the visualizer consumes directly.

The one constant across everything is `c_log = α · d_max / (N · ln(d_max))`.
Every subfolder is ultimately asking: *how low can we push this number?*
