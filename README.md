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
Mattheus–Verstraete), regularity-based and random/greedy baselines,
evolutionary/LLM search (FunSearch-style), and a unified graph database +
visualizer to compare everything.

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
plotly / networkx), the SAT stack (ortools, python-sat), LLM API clients
(anthropic, google-genai, xai-sdk), and a C compiler chain. See comments
in `environment.yml` for the full list. Takes a few minutes on a fresh
machine.

### 3. Build `nauty` + install `pynauty`

```bash
micromamba activate k4free
bash scripts/setup_nauty.sh
```

This downloads `nauty 2.9.3`, builds it inside the env
(`$CONDA_PREFIX/src`), wires the binaries onto `PATH` via a conda
activation hook, and then `pip install`s `pynauty` against the
just-built library. On macOS it also sets `SDKROOT` to the Xcode SDK
path; if Xcode CLT is missing the script warns and exits cleanly.
`pynauty` is required — `graph_db` uses its canonical sparse6 as the
isomorphism-class id and refuses to run without it.

### 4. Smoke test

```bash
micromamba run -n k4free python scripts/test_search.py    # search framework
micromamba run -n k4free python scripts/run_random.py     # random baseline N=10..30
```

If both complete, the env is healthy.

### Running commands without activating

`micromamba activate k4free` only sticks for the shell session it's
run in. For one-off invocations — or scripts that don't own a shell —
prefix with `micromamba run -n k4free ...` and skip the activation
step entirely.

## Top-level layout

| Path              | Purpose                                                          |
|-------------------|------------------------------------------------------------------|
| `environment.yml` | Conda/micromamba environment for the whole repo                  |
| `cache.db`        | SQLite cache of computed graph properties (gitignored, rebuilt)  |
| `graphs/`         | Committed JSON batches of canonical graphs (one per source)      |
| `logs/search/`    | Per-run / aggregate logs from the `search/` framework            |

---

## SAT / ILP — current pipeline

The active K₄-free CP-SAT pipeline lives in `search/sat_exact.py` +
`scripts/{run_sat_exact,prove_box,verify_optimality,proof_report}.py`.
It handles the full Pareto scan, hard-box optimality proofs, and
certification. See:

- `SAT_EXACT.md` — pipeline walkthrough (model, scan, accelerators,
  prove_box, verify_optimality).
- `SAT_OPTIMIZATION.md` — what sped the solver up, what didn't, open ideas.

## `SAT_old/` — reference implementations + historical infra

Kept as a reference point, not as the active code path.

- `regular_sat/` — reference near-regular (degree-pinned) CP-SAT solver.
  Faster but assumes near-regularity; useful as a smaller model to port
  onto the cluster and as a sanity reference.
- `pareto_reference/` — committed `pareto_n{N}.json` from the original
  unconstrained CP-SAT scanner. Ground-truth `min_c_log` that the new
  solver validates against.
- `claude.summary.md` — theoretical results (α-critical ⇒ near-regular;
  minimise-c ⇔ minimise-|E|; Shearer β-parametrisation of the conjecture).
- `ILP.sub`, `REGULAR_SAT.sub`, `interactive.sub`, `run_cluster.sh`,
  `run_job.sh` — original HTCondor templates, kept for the upcoming
  cluster pipeline.

---

## `funsearch/` — FunSearch-style program evolution

Frames the problem the way DeepMind's FunSearch (Nature 2024) framed cap sets:
evolve graph-**construction algorithms** `construct(N) -> edge_list`, not
graphs. The key trick: K₄-free iff every neighborhood is triangle-free, so the
validity check is local and cheap, and the skeleton handles the constraint
for any priority function.

- `summary.md` — problem framing, why FunSearch fits, surrogate-vs-SAT scoring tradeoffs, block-decomposition motivation (α-critical graphs, 1-join composition).
- `so_far.md`, `OPENEVOLVE_ANALYSIS.md` — progress notes.
- `claude_search/` — **LLM-in-the-loop optimizer**. A Claude Code agent reads `RULES.md`, runs `eval.py` on candidate constructors it writes into `candidates/`, and is ranked via `leaderboard.py`. `CLAUDE.md` defines the sandbox (read-only eval infrastructure, write-only `candidates/`). `results.jsonl` is the append-only history.
- `openevolve_vendor/` — vendored copy of the OpenEvolve framework.
- `experiments/` — validation / ablation experiments:
  - `initial_validations/` — does SAT scale to N=40–80? does cheap α proxy correlate with truth?
  - `baselines/` — random + greedy baselines, comparison plots.
  - `block_decomposition/`, `block_optimal/` — α-critical block library, 1-join composition, SAT-verified enrichment rounds.
  - `forced_matching/`, `pair_forced/` — specific construction families.
  - `evo_search/` — best graphs at N=30/40/50/60 from an evolutionary loop.
  - `reachability/`, `selective_crossedge/` — other tactics.

---

## `graph_db/` — Unified graph database

The glue layer for comparing results across solvers. Two stores:

1. `graphs/` folder (committed) — JSON arrays of `{id, sparse6, source, metadata?}` records, one file per source.
2. `cache.db` (SQLite, gitignored) — one row per graph with every computable property typed (degree sequence, girth, triangles, spectral radius, Laplacian spectrum, α, c_log, Turán density, MIS / triangle / high-degree highlight sets, …).

Two public classes for the two use cases:

- **`GraphStore`** — producer path. Bare JSON-folder I/O; no cache involvement at write time. `search/base.Search.save` and ad-hoc ingest scripts use it.
- **`DB`** — analysis / visualization path. Combines the store with the property cache. Opening a `DB` auto-syncs any new store records into the cache, so queries always see every graph with its full column set.

Files:

- `DESIGN.md`, `USAGE.md`, `EXTENDING.md` — architecture + API + how to add a new computed property.
- `db.py` — the `DB` class, `open_db()`, and the auto-sync logic.
- `store.py` — `GraphStore`: JSON batch reader/writer.
- `cache.py`, `schema.sql` — SQLite cache layer + typed column schema.
- `properties.py` — `compute_properties(G, hint)` → full row.
- `encoding.py` — canonical sparse6 + `canonical_id` (SHA-256[:16] of canonical form, via pynauty).
- `clean.py` — cache rebuild / pruning utilities.

## `graphs/` — The canonical graph store (committed)

JSON batches consumed by `graph_db/`, one file per producing source:

- `circulant.json` — circulant catalog from exhaustive `CirculantSearch` (N ≤ 35).
- `cayley.json` — residue-class Cayley graphs `Cay(Z_p, R_k)` for `k ∈ {2, 3, 6}`.
- `mattheus_verstraete.json` — explicit construction from Mattheus–Verstraete 2023.
- `regularity.json` — outputs of regularity-partition-based constructions.
- `random.json` — random/greedy baselines.

SAT/ILP results are not yet wired into `graphs/`; they currently live under
`SAT_old/pareto_reference/` as raw Pareto JSON.

---

## `search/` — Per-N search framework

A lightweight abstraction layer. `base.py` defines an abstract `Search`
class; each subclass implements `_run()` returning `list[nx.Graph]` for a
given `N` (and arbitrary subclass-specific kwargs). `logger.py` handles
per-run logs in `logs/search/`. This is the unified framework new
algorithms plug into, with `c_log` scoring and `save()` writing into the
`graph_db` format.

- `DESIGN.md` — the spec for the `Search` contract.
- `ADDING_A_SEARCH.md` — playbook / checklist for writing a new search.

Algorithm subclasses, each with its own notes file:

| Module                   | Notes                       | What it does                                                             |
|--------------------------|-----------------------------|--------------------------------------------------------------------------|
| `brute_force.py`         | `BRUTE_FORCE.md`            | Exact enumeration via `nauty geng` (N ≤ 10).                             |
| `circulant.py`           | `CIRCULANTS.md`             | Exhaustive circulant enumeration for N ≤ 35.                             |
| `cayley.py`              | `CAYLEY.md`                 | Residue-class Cayley graphs `Cay(Z_p, R_k)`, k ∈ {2, 3, 6}.              |
| `regularity.py`          | `REGULARITY.md`             | Regularity-partition-based construction.                                 |
| `regularity_alpha.py`    | `REGULARITY_ALPHA.md`       | α-optimised regularity variant.                                          |
| `mattheus_verstraete.py` | `MATTHEUS_VERSTRAETE.md`    | Explicit R(4,k) lower-bound family from Mattheus–Verstraete 2023.        |
| `random.py`              | `RANDOM.md`                 | Random + randomized-greedy baselines.                                    |

The SAT search lives in `search/sat_exact.py`; see `SAT_EXACT.md` and
`SAT_OPTIMIZATION.md` at the repo root for the pipeline walkthrough.

## `scripts/` — Orchestration / helper CLIs

- `test_search.py` — smoke test for the `Search` framework.
- `db_cli.py` — query / inspect `graph_db` from the shell.
- `open_visualizer.py` — launch the tkinter visualizer.
- `setup_nauty.sh` — build `nauty`/`geng` and install `pynauty`.
- `run_random.py`, `run_cayley.py`, `run_regularity.py`, `run_regularity_alpha.py`, `run_mattheus_verstraete.py` — per-algorithm sweep drivers.
- `run_sweep_10_40.py` — unified driver that runs every non-SAT search across N=10..40.

## `utils/` — Shared primitives

- `graph_props.py` — computes the typed properties that populate `cache.db`.
- `pynauty.py` — pynauty availability check + `canonical_id` + `geng` helpers (`find_geng`, `graphs_via_geng`). Mirrors the canonical-id logic in `graph_db/encoding.py`.
- `ramsey.py` — hardcoded Ramsey numbers `R(3,k)`, `R(4,k)` used for pre-solve pruning in the SAT solver.

## `visualizer/` — Interactive explorer

- `visualizer.py` — tkinter + matplotlib UI backed by `graph_db`. Filters by
  source, N, c_log, regularity, etc. Highlights: MIS vertices, triangles,
  high-degree vertices, click-to-select neighborhood. Layouts: spring,
  circular, shell, Kamada-Kawai. Eigenvalue spectra and degree distribution
  sidepanels.
- `plots/` — static and interactive plots over the whole `graph_db`.
  - `plot_n_alpha_dmax.py` — 3D scatter of every cached graph in
    `(N, d_max, α)` with the Caro–Wei floor `α = N/(d_max + 1)` drawn
    as a translucent mesh. Writes a PNG by default; `--html` renders
    a self-contained Plotly WebGL page that opens in the browser
    (smooth on WSL2); `-i` opens a rotatable matplotlib window.
  - `images/` — generated output (PNG / HTML).

---

## How the pieces fit together

```
         ┌──────────────────────┐
         │   Search producers   │
         ├──────────────────────┤
   SAT / ILP        ───┐
   regular_sat      ───┤
   circulant        ───┤
   cayley           ───┤
   regularity       ───┼──►  graphs/*.json  (committed batches)
   mattheus_v.      ───┤             │
   random / greedy  ───┤             ▼
   funsearch        ───┤         graph_db
   claude_search    ───┘       (DB auto-sync)
                                     │
                                     ▼
                                 cache.db
                                     │
                                     ▼
                     visualizer + plots + leaderboards
```

Each producer writes graphs it finds into a `graphs/*.json` batch via
`GraphStore`. Opening a `DB` scans the batch files, computes every typed
property for unseen graphs, and fills `cache.db`. The visualizer, plots,
and any analysis script read from `cache.db` via `DB.query(...)`,
filtered by `source`, `n`, `c_log`, etc.

The one constant across everything is `c_log = α · d_max / (N · ln(d_max))`.
Every subfolder is ultimately asking: *how low can we push this number?*
