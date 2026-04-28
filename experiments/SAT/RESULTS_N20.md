# Empirical results — `SATMinDeg` on $n = 20$

Session of 2026-04-26. Companion to `MIN_DEG.md` (formalism) and
`OPTIMIZATION.md` (joint vs sweep brainstorm). All runs single-worker,
no symmetry breaking, default CP-SAT params.

---

## 1. Litmus sweep — `SATMinDeg(n=20, α ∈ {4, 5, 6})`, 300 s budget each

| α | status | optimality | $D_{\min}$ | obj | best LB | gap | $D$ range | wall | actual α / Δ | $c_{\log}$ | edges |
|--:|------:|-----------:|-----------:|----:|--------:|----:|:---------|-----:|--------------|----------:|------:|
| 4 | SAT | unverified | 7 | 7.0 | 4.0 | 3 | [4, 19] | 300.2 s | 4 / 7 | 0.7195 | 70 |
| 5 | SAT | unverified | 5 | 5.0 | 3.0 | 2 | [3, 19] | 300.3 s | 5 / 5 | 0.7767 | 46 |
| 6 | SAT | unverified | 4 | 4.0 | 3.0 | 1 | [3, 19] | 300.1 s | 6 / 4 | 0.8656 | 39 |

All three incumbents **match the reference Pareto frontier**
(`reference/pareto/pareto_n20.json`) exactly. None of the three
runs proved optimality inside the 300 s budget — the lower bound
stalled at the Caro–Wei floor in every case, identical to the
existing reference's `timeouts` list at the same boxes.

So `SATMinDeg` reproduces the repo's known frontier values
(α = 4 → 0.7195, α = 5 → 0.7767, α = 6 → 0.8656), but inherits the
same boundary-UNSAT wall the reference scan hits.

---

## 2. Find vs. prove split — head-to-head at $(n = 20, α = 4)$

Question: does the optimization wrapper accelerate *finding* the
$D = 7$ witness, relative to a single feasibility solve at the right
$d$?

| Method                               | Time to first $d = 7$ witness |
|--------------------------------------|------------------------------:|
| Box: `SAT(n=20, α=4, d_max=7)`       | **1.87 s**                    |
| MinDeg: incumbent ratchet to $D = 7$ | **2.15 s**                    |

Effectively a tie. MinDeg pays ~15 % overhead because CP-SAT must
ratchet through $D = 11 \to 10 \to 9 \to 8 \to 7$ (each step forcing a
new feasible solution before tightening). The intermediate hops
$D = 11 \to 8$ all land within ~50 ms — CP-SAT's heuristic naturally
hits sparse-graph regions first — and $D = 7$ lands at almost exactly
the same wall as the standalone feasibility solve.

The remaining ~298 s of MinDeg's budget is spent trying to prove
$D \le 6$ infeasible.

---

## 3. The boundary UNSAT wall

The repo *does* have a proven UNSAT certificate for the binding box,
in `logs/optimality_proofs.json`:

```json
{
  "n": 20, "alpha": 4, "d_max": 6,
  "status": "INFEASIBLE",
  "wall_s": 1350.76, "timeout_s": 1800.0,
  "workers": 4, "symmetry_mode": "edge_lex"
}
```

So the proven minimum at $(n = 20, α = 4)$ is $d = 7$,
$c_{\log} = 0.7195$. To get the proof took **1350 s with 4 workers
and `edge_lex` symmetry breaking** — none of which we used in our
`SATMinDeg` runs.

| Setup                                         | Wall | Outcome at $(n=20, α=4, d=6)$ |
|-----------------------------------------------|-----:|-------------------------------|
| 4 workers, edge_lex, time = 1800 s            | 1350 s | UNSAT (proven)              |
| 1 worker, no symmetry, time = 300 s (`SATMinDeg`) | 300 s (timeout) | gap not closed |

**Conclusion.** Our `SATMinDeg` run with weaker compute hit exactly
the same boundary box that took the existing pipeline 1350 s to
crack — it is the same UNSAT proof, packaged differently. The
optimization framing rolls "find witness" and "prove min" into one
solve, but doesn't make the dominant UNSAT step easier.

---

## 4. Cross-row prove cost (existing `optimality_proofs.json`)

For context, the published UNSAT certificates near our row:

| $(n, α, d)$       | status        | wall        | symmetry  |
|-------------------|---------------|------------:|-----------|
| 15, 3, 5          | INFEASIBLE_RAMSEY | 0.0 s   | edge_lex  |
| 12, 3, 4          | INFEASIBLE    | 0.07 s      | edge_lex  |
| **20, 4, 6**      | **INFEASIBLE**| **1350.8 s**| **edge_lex** |
| 21, 4, 7          | TIMEOUT       | 1701 s      | edge_lex  |
| 21, 4, 7          | TIMEOUT       | 3398 s      | chain     |

Reading: the boundary-UNSAT cost grows steeply with $n$, and even at
$n = 21$ the row's binding box is unresolved (over 56 minutes of CPU
each, both symmetry modes).

---

## 5. Takeaway for `SATMinDeg`

`SATMinDeg`'s structural advantages over the sweep — cumulative
learning, single presolve, active dual bounds — pay off only when
several non-trivial $d$-boxes sit between $D_{\text{lo}}$ and the
optimum. On the rows tested here, almost all of the wall time is the
single boundary UNSAT, and that proof happens identically in either
encoding.

**Recommendation:** keep `SATMinDeg` available as a one-call frontier
prober for *unknown* rows (no incumbent yet, no idea of the d-range)
where its optimality-implicit-UNSAT property is convenient. For known
rows, the box-feasibility sweep paired with the recorded UNSAT
certificates remains the right tool.

The right next step is **not** more optimization-mode variants — it
is to bring the proven accelerators from `sat_exact.py` into the new
naive solver. See `NEXT.md`.
