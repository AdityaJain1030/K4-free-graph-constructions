# Scripts Reference

All experiments and utilities in `scripts/`, grouped by purpose.

---

## SAT / Exact Solvers

| Script | What it does |
|--------|-------------|
| `run_sat_exact.py` | CP-SAT exact search over all (α, d_max) boxes for a given N |
| `run_sat_circulant.py` | SAT feasibility sweep restricted to circulant graphs (fast, no α optimization) |
| `run_sat_circulant_exact.py` | Provably optimal K₄-free circulant search via explicit MIS encoding |
| `run_sat_circulant_optimal.py` | SAT + Hoffman eigenvalue constraint + warm-start from fast circulant |
| `run_sat_near_regular_nonreg.py` | Enumerate non-regular, near-regular K₄-free graphs at targeted (n, α) pairs |
| `run_n34_push.py` | Targeted SAT-exact push at N=34, seeded with 2·P(17) |
| `ablate_sat_exact.py` | Ablation: which SATExact optimization flags help, and by how much |
| `bench_sat_regular.py` | Benchmark SATRegular across (n, α) pairs vs reference Pareto |

---

## Optimality Proofs & Verification

| Script | What it does |
|--------|-------------|
| `run_proof_pipeline.py` | End-to-end pipeline: easy scan + hard-box CP-SAT proofs (server workload) |
| `verify_optimality.py` | Classify every (α, d) box as proved infeasible / feasible / open |
| `proof_report.py` | Print proof-status summary report |
| `prove_box.py` | Prove or refute a single specific (n, α, d_max) box |
| `verify_p17_lift.py` | Exhaustive Cayley-on-Z_n check of the P(17) lift conjecture (n=17,34) |
| `verify_dihedral.py` | Exhaustive Cayley-on-D_p lift optimality check |
| `verify_sat_circulant_optimal.py` | Spot-check UNSAT vs TIMEOUT in the SAT+Hoffman sweep |

---

## Cayley Graph Search (Algebraic)

| Script | What it does |
|--------|-------------|
| `run_cayley_tabu.py` | Tabu search over Cayley connection sets on abelian groups |
| `run_cayley_tabu_gap.py` | Same, extended to all SmallGroups via GAP |
| `run_cayley_tabu_gap_parallel.py` | Parallel version of the GAP sweep (server) |
| `run_cayley_tabu_polarity_ns.py` | Cayley tabu seeded from polarity non-symmetric graphs |
| `run_psl_tabu.py` | Tabu on Cayley(PSL(2,q), S) — covers groups above GAP's size cap |
| `bicayley_sweep.py` | Enumerate BiCay(Z_p; R, L) to find bi-Cayleys outside Cayley-on-2p families |
| `cyclotomic_circulant_probe.py` | Targeted probe of cyclotomic circulants at primes p∈{37..89} |
| `build_special_cayley.py` | Hand-construct one graph per algebraic/spectral Cayley family |
| `compare_cayley_tabu.py` | Compare Cayley-tabu DB entries against existing baselines |
| `persist_cayley_tabu.py` | Ingest completed Cayley-tabu sweep outputs into graph_db |

---

## Mattheus-Verstraete (MV) Constructions

| Script | What it does |
|--------|-------------|
| `run_mv_bipartization.py` | MV-pencil-bipartization over chosen incidence structures (GQ(2,2), GQ(3,3)) |
| `run_mv_gq22.py` | Focused experiment: MV bipartization of GQ(2,2) at N=15 |

---

## Tabu / Switch Search (Heuristic)

| Script | What it does |
|--------|-------------|
| `run_switch_tabu.py` | Switch-tabu search (2-switches on near-regular K₄-free graphs) |
| `run_switch_tabu_mixed_lookahead.py` | Switch tabu + rollout lookahead; tests whether it breaks the N=23 α=7 wall |
| `asymmetric_lift_tabu.py` | Tabu on edge perturbations of the 2-lift of P(17) |

---

## N=23 Plateau Diagnostics

A focused sub-campaign diagnosing why tabu search plateaus at α=7 instead of reaching the SAT-certified α=6.

| Script | What it does |
|--------|-------------|
| `diag_n23_plateau.py` | Enumerate all feasible 2-switches from N=23 init; confirm whether α-landscape is flat |
| `diag_n23_recursive_plateau.py` | Recursive plateau at α=7: does surrogate recall change vs the α=9→8 transition? |
| `diag_n23_edit_distance.py` | Measure edge-edit distance between best α=7 and SAT α=6 graph at N=23 |
| `diag_n23_path_to_alpha6.py` | Construct explicit K₄-free edge-move path from α=7 → α=6, trace c_log trajectory |
| `run_n23_ablation.py` | Surrogate vs exact α ranking ablation at N=23 |
| `run_n23_composite.py` | Factorial: (score type) × (top-K) at N=23 |
| `run_n23_factorial.py` | (operator × basin) 2×2 design at N=23 |

---

## Random / MCMC Search

| Script | What it does |
|--------|-------------|
| `run_mcmc.py` | Metropolis-Hastings chains from cold near-regular inits; compare to switch tabu |
| `run_random_regular_switch.py` | Random regular switch search (Probe 1) across N range |
| `paley_randomized_blowup.py` | Randomized blow-up of P(17) at k=2 with random bipartite fiber edges |
| `run_blowup.py` | Generic blow-up search driver |

---

## Lovász θ / Spectral / Hard-Core Bounds (Sub-plan B)

Three "rungs" of increasingly tight lower/upper bounds on α.

| Script | What it does |
|--------|-------------|
| `run_subplan_b.py` | Rung 0: hard-core occupancy lower bound on α/N via local partition inequality |
| `run_rung2_exact_hardcore.py` | Rung 2: exact hard-core bound via full partition function (tightest possible) |
| `run_rung3_lovasz_theta.py` | Rung 3: Lovász θ SDP as upper bound on α per graph |
| `all_k4free_theta.py` | Compute θ for every graph in DB with known α |
| `all_k4free_theta_analyze.py` | Summarize θ tightness (SDP slack vs actual α) across all sources |
| `cayley_gap_theta.py` | Compute θ for all cayley_tabu_gap records and compare to Hoffman |
| `cayley_gap_theta_analyze.py` | Analyze the Cayley-GAP θ vs Hoffman CSV |
| `frontier_theta.py` | Show α / θ / Hoffman together for the frontier graph at each N |
| `run_alpha_targeted.py` | Targeted α computation on specific graphs |
| `run_fragility.py` | Perturbation fragility: random walk from best graph at each N, measure α stability |

---

## Composition & Structure Screens

| Script | What it does |
|--------|-------------|
| `spectrum_balance_screen.py` | Tensor product G₁⊗G₂ Hoffman predictions; does any pair dip below P(17)? |
| `clique_cover_screen.py` | Clique-cover / MV-analog fingerprint on frontier graphs |
| `check_regularize_nonregular.py` | For each non-regular DB graph: does a regular replacement exist with same (n, α, d_max)? |
| `check_regularize_c_optimal.py` | Same, restricted to frontier (c_log-optimal) non-regular graphs |
| `analyze_c_log_surface.py` | Regression + PCA: does c_log collapse onto a low-dim structural feature surface? |
| `target_n83_a12.py` | Targeted SAT near-regular search at n=83, α=12, d∈[2..28] |
| `run_subplan_b.py` | (also screens all DB graphs with hard-core bound) |

---

## Plots & Visualization

| Script | What it does |
|--------|-------------|
| `plot_cayley_vs_noncayley.py` | c_log vs N: Cayley frontier vs non-Cayley frontier |
| `plot_subplan_b.py` | Hard-core bound tightness scatter, c_log vs N/d, asymptotic extrapolation |
| `plot_rung2.py` | Exact hard-core bound vs actual α and Rung-0 bound |
| `plot_rung3.py` | Lovász θ SDP results |
| `open_visualizer.py` | Launch interactive graph explorer |
| `build_highlights.py` | Emit curated `highlights/` subset of DB for human review |

---

## Data Ingestion & DB Management

| Script | What it does |
|--------|-------------|
| `ingest_deepmind_ramsey.py` | Ingest DeepMind Ramsey R(4,s) K₄-free constructions into DB |
| `ingest_disjoint_lifts.py` | Ingest trivial k-copy disjoint-union lifts for suboptimal N values |
| `recover_sat_regular_graphs.py` | Recover SAT-regular graphs from logs into DB |
| `regen_cache_with_theta.py` | Regenerate DB property cache with θ column |
| `repair_graph_store_n65.py` | One-off repair of the graph store at N=65 |
| `db_cli.py` | Command-line interface: sync, clean, add, query, rm, stats |
| `test_search.py` | Smoke test: brute force n=4..9 + circulant n=8..30, verify DB round-trip |

---

## Prototypes & Misc

| Script | What it does |
|--------|-------------|
| `prototype_sat_circulant.py` | Early prototype of the SAT circulant approach |
| `prototype_sat_circulant_fast.py` | Fast variant prototype |
| `setup_nauty.sh` | Install nauty (canonical graph labeling tool) |
| `open_boxes.json` | Static data: list of open (α, d) boxes needing proofs |
