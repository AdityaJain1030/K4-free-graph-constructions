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
exact solvers (SAT/ILP), algebraic constructions (circulants, Cayley graphs),
random and greedy baselines, evolutionary/LLM search (FunSearch-style), and
a unified graph database + visualizer to compare everything.

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
networkx), the SAT stack (ortools, python-sat), and a C compiler
chain. See comments in `environment.yml` for the full list. Takes a
few minutes on a fresh machine.

### 3. Build `nauty` + install `pynauty`

```bash
micromamba activate k4free
bash scripts/setup_nauty.sh
```

This downloads `nauty 2.9.3`, builds it inside the env
(`$CONDA_PREFIX/src`), wires the binaries onto `PATH` via a conda
activation hook, and then `pip install`s `pynauty` against the
just-built library. On macOS it also sets `SDKROOT` to the Xcode SDK
path; if Xcode CLT is missing the script warns and exits cleanly
(the rest of the project still works — `graph_db` falls back to
WL-hash deduplication without `pynauty`).

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

## `SAT/` — Clean entry point for the SAT/ILP solver

A thin README-only folder. Explains the CP-SAT formulation (K₄-free clauses,
independence clauses, degree cardinality constraints, symmetry breaking),
the two solver modes (direct vs lazy cutting planes), Ramsey pre-solve
pruning, warm-starts from Paley-like circulants, and the degree-pinning
strategy used in `regular_sat`.

Points the reader at `SAT_old/` for actual code.

## `SAT_old/` — CP-SAT solver, full implementation

The real solver lives here despite the "_old" suffix.

- `k4free_ilp/` — main CP-SAT Pareto scanner.
  - `ilp_solver.py` — CP-SAT model (K₄ clauses + independence clauses + degree bounds), with both **direct** (all independence clauses upfront) and **lazy cutting-planes** modes.
  - `run_production.py` — outer sweep over `(α_target, d_max)` pairs for N=11–35.
  - `pareto_scanner.py` — binary-search Pareto scanner for small N.
  - `brute_force.py` — exact enumeration via `nauty`'s `geng` for N ≤ 10.
  - `alpha_exact.py`, `k4_check.py` — bitmask MIS branch-and-bound and K₄ detection.
  - `visualize.py` — interactive tkinter Pareto-frontier explorer.
  - `results/` — `pareto_n{N}.json` per N, plus `summary.json` and `low_c_graphs.g6`.
  - `tests/` — pytest; includes the Ramsey sanity check `R(4,3)=9`, `R(4,4)=18`, `R(4,5)=25`.
- `regular_sat/` — faster variant that **pins degree** to a single `D` (or `{D, D+1}` near-regular). Scans `D` upward from Ramsey lower bound; first feasible `D` terminates. 10–100× faster than the full Pareto sweep but bakes in a near-regularity assumption.
- `paley_enumeration/` — Paley-graph / circulant exploration, a plot (`c_vs_N.png`), and CSV of circulant results.
- `logs/`, `scripts/`, `run_cluster.sh`, `run_job.sh`, `*.sub` (HTCondor) — cluster job infrastructure.
- `claude.summary.md` — running notes / summary from previous Claude sessions.

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

The glue layer for comparing results across solvers.

- `DESIGN.md` — full design doc. Two stores:
  1. `graphs/` folder (committed) — JSON arrays of `{id, sparse6, source, metadata?}` records, one file per batch.
  2. `cache.db` (SQLite, gitignored) — one row per graph with every computable property typed (degree sequence, girth, triangles, spectral radius, Laplacian spectrum, α, c_log, Turán density, MIS / triangle / high-degree highlight sets, …).
- `store.py` — `GraphStore`: reads `graphs/`, writes `cache.db`.
- `properties.py` — `compute_properties(G, hint)` → full row.
- `verify.py`, `api.py` — verification + query API.
- Deduplicates by canonical sparse6 via pynauty (required).

## `graphs/` — The canonical graph store (committed)

Just JSON batches consumed by `graph_db/`:

- `brute_force.json` — small-N brute-force enumeration results.
- `circulant.json` — circulant catalog (N=8–50).
- `sat_pareto_ilp.json` — Pareto frontier graphs from the SAT/ILP runs.

---

## `search/` — Per-N search framework

A lightweight abstraction layer. `base.py` defines an abstract `Search`
class; subclasses (`brute_force.py`, `circulant.py`, `random.py`)
implement `_run()` returning `list[nx.Graph]` for a given `N`.
`logger.py` handles per-run logs in `logs/search/`. Meant to be the
unified framework new algorithms plug into, with `c_log` scoring and
`save()` writing into the `graph_db` format.

- `DESIGN.md` — the spec for the `Search` contract.
- `ADDING_A_SEARCH.md` — playbook / checklist for writing a new search.
- `CIRCULANTS.md`, `BRUTE_FORCE.md`, `RANDOM.md` — per-algorithm notes:
  intuition, caveats, when to use / when not to.

## `scripts/` — Orchestration / helper CLIs

- `open_visualizer.py` — launch the tkinter visualizer.
- `setup_nauty.sh` — build `nauty`/`geng` (required for brute force on N≥8).

## `utils/` — Shared primitives

- `graph_props.py` — computes the typed properties that populate `cache.db`.
- `pynauty.py` — canonical sparse6 via the `nauty` binary (when available).
- `ramsey.py` — hardcoded Ramsey numbers `R(3,k)`, `R(4,k)` used for pre-solve pruning in the SAT solver.

## `visualizer/` — Interactive explorer

`visualizer.py` — tkinter + matplotlib UI backed by `graph_db`. Filters by
source, N, c_log, regularity, etc. Highlights: MIS vertices, triangles,
high-degree vertices, click-to-select neighborhood. Layouts: spring,
circular, shell, Kamada-Kawai. Eigenvalue spectra and degree distribution
sidepanels.

---

## How the pieces fit together

```
         ┌──────────────────────┐
         │   Search producers   │
         ├──────────────────────┤
   SAT / ILP      ───┐
   regular_sat    ───┤
   circulants     ───┼──►  graphs/*.json  (committed batches)
   random         ───┤             │
   funsearch      ───┤             ▼
   claude_search  ───┘        graph_db
                              (properties.py)
                                    │
                                    ▼
                               cache.db
                                    │
                                    ▼
                           visualizer  +  leaderboards
```

Each producer writes graphs it finds into a `graphs/*.json` batch. On
startup, `graph_db` scans the batch files, computes every typed property
for unseen graphs, and fills `cache.db`. The visualizer and any analysis
script reads from `cache.db`, filtered by `source`, `n`, `c_log`, etc.

The one constant across everything is `c_log = α · d_max / (N · ln(d_max))`.
Every subfolder is ultimately asking: *how low can we push this number?*
