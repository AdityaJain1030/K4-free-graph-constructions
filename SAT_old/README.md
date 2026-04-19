# SAT_old — reference implementations and historical infra

Kept around as a reference point for the current pipeline in
`search/sat_exact.py` + `scripts/{run_sat_exact,prove_box,verify_optimality}.py`.

## Contents

- `regular_sat/` — reference implementation of the **degree-pinned CP-SAT
  solver**. Scans degree D upward from the Ramsey lower bound and returns the
  first feasible D. Pinning `deg(v) ∈ {D, D+1}` is a near-regularity
  assumption (unproven but supported by Hajnal's α-critical theorem — see
  `claude.summary.md`). 10–100× faster than the unconstrained solver at the
  same N, but can return INFEASIBLE at a degree a non-regular graph would
  have found feasible. Still useful as a sanity reference and as the reduced
  model to port onto the cluster.
- `pareto_reference/` — committed Pareto JSONs (`pareto_n{N}.json` for
  N=11..35, plus `summary.json`, `low_c_graphs.g6`) produced by the old
  unconstrained CP-SAT scanner. Treated as the ground-truth `min_c_log`
  reference for validating `search/sat_exact.py`. These are not regenerated.
- `claude.summary.md` — theoretical results the current solver relies on:
  α-critical ⇒ near-regular (Hajnal, Lovász–Plummer Ch. 12), minimise-c
  ⇔ minimise-|E|, and the Shearer-exponent β-parametrisation of the
  conjecture. Independent of any solver.
- `ILP.sub`, `REGULAR_SAT.sub`, `interactive.sub`, `run_cluster.sh`,
  `run_job.sh` — HTCondor submit files from the original cluster runs
  (`vision-c23.cs.illinois.edu`). Kept as templates; 80–90% reusable for
  the next cluster pipeline that wraps `sat_exact.py` / `prove_box.py`.
- `env.yml` — the `ILP_pareto_enum` env used on the cluster. The repo
  environment is `environment.yml` at the root (`k4free` env); this one is
  kept only for HTCondor-compatibility reference.

## Running `regular_sat` (reference solver)

```bash
# From the repo root, with the k4free env active.
cd SAT_old
python -m regular_sat.cli single --n 20 --time_limit 600 --workers 4
python -m regular_sat.cli scan   --n_min 12 --n_max 24 --time_limit 1800 --workers 8
pytest regular_sat/tests/ -v
```

Outputs JSON in `SAT_old/regular_sat/results/`.

## Relation to the current pipeline

The unconstrained CP-SAT scanner that produced `pareto_reference/` was the
predecessor of `search/sat_exact.py`. The new solver adds edge-lex symmetry
breaking, c_log-bound pruning, circulant seeding, and certified-optimality
proofs on top of the same K4-free / independence / degree CP-SAT model.
See `SAT_EXACT.md` and `SAT_OPTIMIZATION.md` at the repo root.
