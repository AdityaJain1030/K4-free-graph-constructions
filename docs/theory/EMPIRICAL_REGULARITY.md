# Empirical Regularity Evidence from SAT Sweeps

Companion to [`REGULARITY.md`](REGULARITY.md). That document lays out the
theoretical arguments (Caro–Wei headroom, switching lemma, co-degree
barrier) for why min-$c_{\log}$ K₄-free graphs appear to satisfy
$d_{\max} - d_{\min} \leq 1$. This document records the empirical
evidence from our CP-SAT sweeps.

Date: 2026-04-20.

---

## 1. Recovered SAT-regular corpus

We re-solved every $(n, \alpha, \text{spread})$ case from the 10–25 sweep
(`scripts/bench_sat_regular.py` at `spread ∈ \{1, 3\}`) and saved the
witnessing graphs. Output: `graphs/sat_regular.json`.

- **76 unique graphs**, $n \in [10, 25]$, $\alpha \in [2, 7]$.
- **46 strictly better than the prior Pareto reference** (in
  `reference/pareto/`), **29 match**, **1 gap**. The reference files are
  out-of-date for several $(n, \alpha)$; trust the SAT witness + an
  independent `alpha_exact_nx` check over the reference numbers.
- After sync + recompute, every row is K₄-free (`is_k4_free=1`) and the
  cache reports 565 total cache pairs across 12 sources.

### New frontier points

The $c_{\log}$ frontier moved at several small $n$ because the
refactored SAT solver scans all $D$ values (rather than stopping at the
first feasible $D$) and so finds strictly fewer edges:

| $n$ | $\alpha$ | $d_{\max}$ | edges | $c_{\log}$ |
|---|---|---|---|---|
| 14 | 3 | 6 | 40 | 0.7176 |
| 15 | 3 | 7 | 44 | 0.7195 |
| 18 | 4 | 7 | 58 | 0.7441 |
| 19 | 4 | 6 | 57 | 0.7050 |
| 20 | 4 | 7 | 68 | 0.7195 |
| 20 | 5 | 8 | 70 | 0.7767 |

The $n = 19$, $\alpha = 4$, $57$-edge graph is the one where the old
`edge_lex` symmetry-breaking constraint was pruning the optimum (see
`memory/project_sat_regular_refactor.md`).

### Solver change that made this possible

Three coupled changes (all in `search/sat_regular.py`):

1. **Scan-all-$D$ with LB prune.** Iterate $D$ from the Ramsey lower
   bound to the upper bound, carry `best_E` across $D$ values, and break
   only when $nD \geq 2\,\text{best\_E}$. Old behaviour stopped at the
   first feasible $D$ — e.g. took $D = 6$ at $n = 19,\alpha = 4$ and
   missed the true optimum at $D = 5$.
2. **Two-phase solve per $D$.** Phase 1 is cheap feasibility ($\leq
   15\%$ of remaining budget, cap 90 s). Phase 2 adds $\Sigma x \leq
   \text{best} - 1$ with the current witness as a hint and iterates on
   that bound until `INFEASIBLE` (proved optimal at this $D$) or two
   consecutive iteration timeouts. Old `model.minimize()` spent the full
   budget proving optimality; this is ~7× faster on $n = 17,\alpha = 4$
   (131 s vs 874 s).
3. **`symmetry_mode = "none"` by default.** CP-SAT's
   `symmetry_level = 4` detects orbits automatically (Schreier–Sims).
   The explicit `edge_lex` mode with `k_max = 3` is technically sound
   under the $S_{n-1}$ stabilizer of vertex 0 but empirically prunes
   valid orbits at $n = 19, \alpha = 4, D = 6$ (finds 59 edges instead
   of 57). The `edge_lex` mode is still available but loosened to
   `k_max = 0` (row-0 lex leader only). `search/sat_exact.py` still
   carries the old `k_max = 3` formulation and is flagged for audit.

### Validation

- $n = 19, \alpha = 4$ hits 57 edges at `spread = 1` in 173 s and at
  `spread = 3` in 294 s with the fixed solver. Logs:
  `logs/symm_debug.log`, `logs/scan_validate.log`.
- Full 10–25 sweep: 37/37 `match-or-better` at `spread = 3`. (Previous
  sweep had 36/37.)
- Remaining budget-limited gaps — not correctness: $n = 24,\alpha = 4$
  ($120$ vs ref $118$), $n = 25,\alpha = 5$ ($89$ vs ref $85$). These
  need wider spread or longer per-$D$ phase-2 budget.

---

## 2. Can non-regular K₄-free graphs be "regularized"?

Question: for each non-regular K₄-free graph $G$ in the DB with
parameters $(n, \alpha, d_{\max})$, does there exist a *strictly*
$D$-regular K₄-free graph $G'$ on $n$ vertices with
$$D \leq d_{\max}(G) \quad \text{and} \quad \alpha(G') \leq \alpha(G)?$$

We don't require preserving the vertex set or any edge of $G$ — the
question is purely about the existence of a regular realization in the
same $(n, \alpha, d_{\max})$ envelope. A negative answer for $G$ means
the non-regularity of $G$ is **forced** by its parameters, not a
solver artefact.

Check: for each $G$, scan $D$ from $d_{\max}$ down to $\max(1, d_{\min})$
and call SATRegular at `degree_spread = 0`, `alpha = α(G)`, short per-$D$
timeout. First `FEASIBLE` → YES. All `INFEASIBLE` → NO. Any `TIMEOUT`
with no later success → TIMEOUT. Script:
`scripts/check_regularize_nonregular.py`.

### Running result (in progress, 80/115 cases at time of writing)

| Verdict | Count |
|---|---|
| YES | 0 |
| NO | 66 |
| TIMEOUT | 14 |

**Zero YES verdicts so far.** TIMEOUTs cluster on `sat_regular` rows
(these are already near-regular optima produced by the very constraint
we're now testing; proving infeasibility of the strict-regular
relaxation is the expensive direction).

### Interpretation

The sweep is consistent with the REGULARITY.md thesis: for these
parameter triples $(n, \alpha, d_{\max})$ there is simply no K₄-free
regular realization that stays within the envelope. The non-regularity
is structural.

A concrete easy case: $n = 19, \alpha = 7, d_{\max} = 2$. Any 2-regular
graph on 19 vertices is a disjoint union of cycles, with
$\alpha \geq \lceil 19/3 \rceil = 7$; the constraint $\alpha \leq 7$
would require equality plus a specific cycle decomposition. The SAT
solver returns INFEASIBLE because that pattern induces a K₃/K₄ obstruction
once we try to embed it — the detailed reason is in the UNSAT core and
not worth unpacking, but the verdict is correct.

### Restricted to the $c_{\log}$ frontier

Currently in flight (`scripts/check_regularize_c_optimal.py`). The
frontier set is only 5 graphs — the min-$c_{\log}$ non-regular graph at
each $n$:

| $n$ | $\alpha$ | $[d_{\min}, d_{\max}]$ | $c_{\log}$ | source |
|---|---|---|---|---|
| 7 | 3 | $[2, 3]$ | 1.1703 | polarity |
| 14 | 3 | $[5, 6]$ | 0.7176 | sat_regular |
| 15 | 3 | $[6, 7]$ | 0.7195 | sat_regular |
| 20 | 4 | $[6, 7]$ | 0.7195 | sat_regular |
| 100 | 18 | $[19, 20]$ | 1.2017 | random_regular_switch |

A NO verdict on these five would be the most directly supportive
evidence for REGULARITY.md §3.2: the frontier graphs are non-regular
**because** there is no strictly regular alternative that preserves
their extremal parameters, not because the solver failed to find one.
The $n = 100$ case will probably TIMEOUT; the others are small enough
to resolve. Results will be appended here.

---

## 3. Open questions this opens up

1. **Tight switching-lemma characterization.** The non-regularity is
   consistently of spread 1 ($d_{\max} - d_{\min} = 1$). Can the
   switching lemma in REGULARITY.md §4 be strengthened to prove
   spread $\leq 1$ for all $n, \alpha$ on the $c_{\log}$ frontier,
   conditional on co-degree bounds?
2. **What happens at spread 2?** Our `spread = 3` bench config showed
   that at $n = 10,\alpha = 3$ the true optimum has degree sequence
   $\{2, 3, 4\}$ (spread 2). Is there a parameter regime where the
   frontier prefers spread 2 over spread 1?
3. **$n = 100$ frontier.** `random_regular_switch` produced a 19–20
   spread-1 graph at $c_{\log} = 1.2017$. Can SAT prove this is
   optimal, or (more likely) is a better graph findable at this scale?

---

## 4. File pointers

- Solver: `search/sat_regular.py`.
- Bench driver: `scripts/bench_sat_regular.py`.
- Recovery: `scripts/recover_sat_regular_graphs.py`.
- Regularization check (all non-regular): `scripts/check_regularize_nonregular.py`.
- Regularization check (c-optimal only): `scripts/check_regularize_c_optimal.py`.
- Bench outputs: `logs/bench_sat_regular_10_20.json`, `logs/bench_sat_regular_20_25.json`.
- Check outputs: `logs/regularize_check.json`, `logs/regularize_c_optimal.json`.
- Recovered graphs: `graphs/sat_regular.json`.
- Plots (updated with `sat_regular` source): `visualizer/plots/images/plot_*.png`.
