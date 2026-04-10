# K₄-Free Graph Pareto Frontier Explorer

CP-SAT ILP solver for finding Pareto-optimal (α, d_max) tradeoffs in K₄-free graphs, with an interactive visualizer.

Given n vertices, we search for K₄-free graphs that minimize both the independence number α and the maximum degree d_max. The key metric is `c_log = α · d_max / (n · log(d_max))`, related to Ramsey multiplicity bounds.

## Setup

### 1. Create the environment

```bash
micromamba create -f env.yml
micromamba activate ILP_pareto_enum
```

### 2. Install nauty (required for brute-force enumeration on n ≥ 8)

```bash
micromamba run -n ILP_pareto_enum bash scripts/setup_nauty.sh
```

This downloads, builds, and adds `geng` to PATH within the environment. Only needed if you plan to run the brute-force scanner.

## Scripts

All commands assume the working directory is `SAT/` and the environment is active. You can either activate the environment or prefix commands with `micromamba run -n ILP_pareto_enum`.

### Brute-force Pareto frontier (n = 3–10)

Enumerates all graphs (or non-isomorphic graphs via `geng` for n ≥ 8), filters K₄-free ones, and computes the exact Pareto frontier.

```bash
python -m k4free_ilp.brute_force
```

Outputs `k4free_ilp/results/brute_force_n{3..10}.json`.

### ILP Pareto scanner (small n)

Runs the CP-SAT solver for specific n values using binary search over (α, d_max) pairs. Good for quick single-n runs.

```bash
python -m k4free_ilp.pareto_scanner          # default: n=4..15
python -m k4free_ilp.pareto_scanner 12 14 16  # specific n values
```

Outputs `k4free_ilp/results/ilp_pareto_n{N}.json`.

### Production sweep (n = 11–35)

Optimized scanner with Ramsey-based search pruning, monotonicity bounds, configurable parallelism, and trend analysis.

```bash
python -m k4free_ilp.run_production                # run all n=11..35
python -m k4free_ilp.run_production 20 25 30       # specific n values
python -m k4free_ilp.run_production --dry-run      # show search plan without solving
python -m k4free_ilp.run_production --workers 4    # CP-SAT solver threads (default: 8)
python -m k4free_ilp.run_production --timeout 900  # per-query time limit in seconds
python -m k4free_ilp.run_production --parallel 2   # run 2 n values concurrently
python -m k4free_ilp.run_production -v             # verbose (show timeouts/infeasible)
python -m k4free_ilp.run_production -vv            # extra verbose (log every query)
```

Outputs `k4free_ilp/results/pareto_n{N}.json`, `summary.json`, and `low_c_graphs.g6`.

### Interactive visualizer

Browse Pareto frontier graphs with draggable nodes, highlight modes, graph metrics, degree distributions, and eigenvalue spectra.

```bash
python -m k4free_ilp.visualize
python -m k4free_ilp.visualize --results-dir path/to/results  # custom results dir
```

Controls:
- **Arrow keys**: Left/Right to browse Pareto points, Up/Down to change n
- **Drag nodes** to reposition them on the canvas
- **Drag the sash** (gray bar) between left and right panes to resize
- **Layout selector**: Spring (default), Circular, Shell, Kamada-Kawai
- **Highlights**: toggle Max Independent Set, Triangles, High-degree vertices, Click-to-select neighborhood

### Tests

```bash
pytest k4free_ilp/tests/ -v
```

| Test | What it checks |
|------|----------------|
| `test_core.py` | K₄ detection, exact α computation, Petersen graph |
| `test_ilp_vs_brute.py` | ILP Pareto frontiers match brute-force for n=4..10 |
| `test_ramsey.py` | Solver agrees with known R(4,3)=9, R(4,4)=18, R(4,5)=25 |

## Project structure

```
SAT/
├── k4free_ilp/
│   ├── ilp_solver.py       # CP-SAT model builder + solver (direct & lazy cutting planes)
│   ├── pareto_scanner.py   # Binary-search Pareto frontier scanner
│   ├── run_production.py   # Production sweep with pruning & parallelism
│   ├── brute_force.py      # Exact enumeration for small n (uses nauty geng)
│   ├── visualize.py        # Interactive tkinter + matplotlib graph explorer
│   ├── alpha_exact.py      # Exact MIS via bitmask branch-and-bound
│   ├── k4_check.py         # K₄ detection via bitmask neighbor intersection
│   ├── graph_io.py         # graph6 encoding, edge list conversion, JSON export
│   ├── results/            # Computed Pareto frontier JSON files
│   └── tests/              # pytest suite
├── scripts/
│   └── setup_nauty.sh      # Build nauty/geng inside the conda environment
├── env.yml                 # Micromamba environment specification
└── README.md
```

## Results format

Each `pareto_n{N}.json` contains:

```json
{
  "n": 24,
  "pareto_frontier": [
    {
      "alpha": 4,
      "d_max": 8,
      "c_log": 0.6416,
      "edges": [[0,1], [0,2], ...],
      "g6": "W?...",
      "solve_time": 12.345,
      "method": "direct_enumeration"
    }
  ],
  "min_c_log": 0.6416,
  "timeouts": [],
  "total_time": 45.678
}
```
