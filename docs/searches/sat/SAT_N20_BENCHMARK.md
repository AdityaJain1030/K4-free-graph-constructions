# Proven-optimal K₄-free c-minimisers, N = 10..20

`graphs/sat_optimal_proven.json` holds one witness per N in 10..20, each
certified-optimal by the full SAT pipeline (scan → targeted prove_box →
verify_optimality). This is the immutable benchmark that N=20 optimisation
experiments in `SAT_OPTIMIZATION.md` and `logs/sat_exact_n20_sweep.json`
score against.

| n  | c*       | α | d_max |
|----|----------|---|-------|
| 10 | 0.865617 | 3 | 4     |
| 11 | 0.786925 | 3 | 4     |
| 12 | 0.776669 | 3 | 5     |
| 13 | 0.772769 | 3 | 6     |
| 14 | 0.717571 | 3 | 6     |
| 15 | 0.719458 | 3 | 7     |
| 16 | 0.721348 | 4 | 4     |
| 17 | 0.678915 | 3 | 8     |
| 18 | 0.744148 | 4 | 6     |
| 19 | 0.704982 | 4 | 6     |
| 20 | 0.719458 | 4 | 7     |

The N=17 witness is the Paley graph P(17); N=20 is the `c_log`-tied
result at α=4, d=7 with the hard box α=4, d=6 proved INFEASIBLE in
`logs/optimality_proofs.json` (1350.76 s, 4 CP-SAT workers).

## Reproducing

```bash
# 1. Scan + save every (n, α, d_max) box for N=10..20
micromamba run -n k4free python scripts/run_sat_exact.py \
    --n-min 10 --n-max 20 --save --timeout 120

# 2. Close any TIMEOUT boxes (historically only n=20 α=4 d=6, at 1350 s)
#    — skip if scan_from_ramsey_floor + c_log_prune already closed every
#    box in step 1.

# 3. Gate: must exit 0.
micromamba run -n k4free python scripts/proof_report.py --n-min 10 --n-max 20

# 4. Refresh the cache and rebuild the benchmark JSON.
micromamba run -n k4free python scripts/db_cli.py sync
micromamba run -n k4free python - <<'PY'
import json, math, sys
sys.path.insert(0, '.')
from graph_db.encoding import sparse6_to_nx
from utils.graph_props import is_k4_free_nx, alpha_exact_nx

out = []
for r in json.load(open('graphs/sat_exact.json')):
    G = sparse6_to_nx(r['sparse6'])
    n = G.number_of_nodes()
    d_max = max(dict(G.degree()).values())
    alpha, _ = alpha_exact_nx(G)
    c_log = alpha * d_max / (n * math.log(d_max))
    assert is_k4_free_nx(G)
    out.append({
        'n': n, 'c_log': round(c_log, 6), 'alpha': int(alpha),
        'd_max': int(d_max), 'sparse6': r['sparse6'],
        'source': 'sat_exact', 'proved': True,
    })
out.sort(key=lambda x: x['n'])
json.dump(out, open('graphs/sat_optimal_proven.json', 'w'), indent=2)
PY
```

## Consumers

- `scripts/ablate_sat_exact.py` — cross-checks candidate configs against
  `c*` at each N (currently a hardcoded `REFERENCE_C_LOG` table; long-term
  should load from this JSON instead).
- `logs/sat_exact_n20_sweep.json` — per-config N=20 benchmark run.
- Anyone probing N=21+ — these witnesses are the seed set for `c_star`
  initialisation in `sat_exact.seed_from_circulant` and its successors.
