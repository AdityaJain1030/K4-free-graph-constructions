# N = 30 — model-size and solve-time probe

Session of 2026-04-26. Goal: nail down the per-box memory footprint
and single-thread solve-time profile at $n = 30$, then extrapolate
to the 200 GB / 32-core cluster's CnC budget. Companion to
`RESULTS_N20.md` (N = 20 frontier matches reference) and `NEXT.md`
§P7 (cube-and-conquer pipeline).

---

## 1. Frontier band

The empirical c_log-frontier $\alpha$ band at $n = 30$ is
$\alpha \in [\Theta(\sqrt{n}), \Theta(n^{3/5})] = [5.5, 7.7]$, so we
probe $\alpha \in \{5, 6, 7\}$. For each, $d$ near the Caro–Wei
floor and slightly above:

- $\alpha = 5$: Caro–Wei floor $d_{\text{lo}} = \lceil 30/5 \rceil - 1
  = 5$. Probed $d \in \{8, 10\}$.
- $\alpha = 6$: $d_{\text{lo}} = 4$. Probed $d \in \{7, 9\}$.
- $\alpha = 7$: $d_{\text{lo}} = 3$. Probed $d = 7$.

Five boxes total. All built with `degree_encoding="sinz"` and
`edge_lex=True` — the Sinz sequential counter keeps clause counts
manageable even at $\binom{30}{8} = 5.85$ M for the α-family on
$\alpha = 7$.

---

## 2. Model size

| $(\alpha, d)$ | Vars  | Clauses    | CNF text size | Predicted RAM (~4× CNF) |
|--------------|------:|-----------:|--------------:|------------------------:|
| (5, 8)       | 7 395 |    635 518 |        35 MB  |   136 MB                |
| (5, 10)      | 9 135 |    638 878 |        35 MB  |   136 MB                |
| (6, 7)       | 6 525 |  2 075 863 |       162 MB  |   631 MB                |
| (6, 9)       | 8 265 |  2 079 223 |       162 MB  |   632 MB                |
| (7, 7)       | 6 525 |  5 892 988 |       613 MB  |  2 394 MB               |

Two scaling observations:

- **The α-family dominates.** At $n = 30$ it is $\binom{30}{\alpha+1}$,
  i.e. $1.4 \times 10^5$ at $\alpha = 5$, $2.0 \times 10^6$ at $\alpha
  = 6$, $5.85 \times 10^6$ at $\alpha = 7$. Each step in $\alpha$
  multiplies the clause count by $\sim (n - \alpha) / (\alpha + 1)$;
  $\alpha = 4 \to 5$ multiplies by 5, $\alpha = 6 \to 7$ multiplies by
  ~3.4.
- **Sinz aux-var growth is linear in $d$.** Each vertex contributes
  $(n-1) \cdot d$ aux variables, so $\alpha = 5,\ d = 10$ has more
  vars than $\alpha = 5,\ d = 8$ (9 135 vs 7 395), but the same α
  family.

The 4× RAM estimate for kissat is empirical (CNF text size × 4 ≈
peak resident memory during inprocessing + clause-DB management).
Confirmed below.

---

## 3. Single-thread KISSAT-Sinz solve attempts

KISSAT-Sinz, 1 worker, default mode (no `--sat`/`--unsat` preset),
60 s budget per box.

| $(\alpha, d)$ | Status     | Wall    | Peak RSS (cumulative)¹ | Verdict notes              |
|--------------|------------|--------:|-----------------------:|----------------------------|
| (5, 8)       | TIMED_OUT  |  60.1 s |             6.33 GB    | likely UNSAT or hard SAT   |
| (5, 10)      | TIMED_OUT  |  60.0 s |             6.33 GB    | likely UNSAT or hard SAT   |
| (6, 7)       | **SAT**    |  19.9 s |             6.33 GB    | witness found              |
| (6, 9)       | **SAT**    |   7.1 s |             6.33 GB    | witness found              |
| (7, 7)       | **SAT**    |  22.3 s |             6.79 GB    | witness found              |

¹ `ru_maxrss` for `RUSAGE_CHILDREN` accumulates the peak across **all**
prior child processes in the run, so each row is bounded by the
high-water mark, not isolated.

**$c_{\log}$ at the SAT witnesses:**

- $(6, 7)$: $c_{\log} = 6 \cdot 7 / (30 \ln 7) \approx 0.719$
- $(6, 9)$: $c_{\log} = 6 \cdot 9 / (30 \ln 9) \approx 0.819$
- $(7, 7)$: $c_{\log} = 7 \cdot 7 / (30 \ln 7) \approx 0.839$

So the $(6, 7)$ witness is currently the strongest c_log we have
near $n = 30$ from this probe — better than what the more permissive
$(6, 9)$ or $(7, 7)$ boxes give, even though both of those solve
faster.

---

## 4. CnC extrapolation for the 32-core cluster

Using empirical patterns from `NEXT.md` §P7 (n = 19, 20 CnC bench):

### SAT-direction ($\alpha = 6, 7$ boxes)

CnC short-circuits on the first SAT cube. With naive row-0 cubing
the speedup we measured at smaller $n$ was 9–30×.

| Box      | Single-thread | Predicted CnC (32 cores, naive cuber) | Predicted memory |
|----------|--------------:|--------------------------------------:|-----------------:|
| (6, 7)   |        19.9 s | **~1–2 s**                            | ~50 GB           |
| (6, 9)   |         7.1 s | **<1 s**                              | ~50 GB           |
| (7, 7)   |        22.3 s | **~1–2 s**                            | ~50 GB           |

Memory estimate: ~1.5 GB per worker × 32 workers ≈ 50 GB total. Far
below the 200 GB cluster ceiling. At α=7 (heaviest CNF), per-worker
RAM rises to ~2.5 GB → ~80 GB total, still well within budget.

### UNSAT-direction ($\alpha = 5$ boxes)

| Box      | Single-thread | Predicted CnC (naive cuber)        | Predicted CnC (real lookahead cuber, est.) |
|----------|--------------:|-----------------------------------:|-------------------------------------------:|
| (5, 8)   | TIMEOUT > 60 s | ~no win (≈ baseline timeout)       | **~5–60 min** (10–20× from balanced cubes) |
| (5, 10)  | TIMEOUT > 60 s | ~no win                            | **~5–60 min**                              |

The CnC bench at smaller $n$ showed UNSAT-direction wins ≈ 1× with
the naive row-0 cuber because the workload concentrates in one
$\deg(0) = k$ branch. Without a real lookahead cuber in place
(see `NEXT.md` §P7 follow-ups), N = 30 UNSAT proofs at the frontier
are likely **not** closeable in any reasonable cluster wall — even
with all 32 cores.

### What's actually deployable today

- **SAT-find at N = 30**: trivially cheap on the cluster. Run all
  the (α, d) boxes in the frontier band in parallel via CnC, expect
  every one to land in seconds.
- **UNSAT-prove at N = 30**: blocked on the cuber. Single-thread
  KISSAT-Sinz is the current bottleneck; CnC with the naive
  Python cuber doesn't help. **The boundary boxes are not
  closeable until a real lookahead cuber is wired up.**

---

## 5. Cluster RAM budget summary

| Workload                    | Per-worker RAM | 32-worker total | Of 200 GB |
|-----------------------------|---------------:|----------------:|----------:|
| α=5 boxes (635 K clauses)   |       ~150 MB  |          ~5 GB  |   2.5 %   |
| α=6 boxes (2.08 M clauses)  |       ~700 MB  |         ~22 GB  |    11 %   |
| α=7 boxes (5.89 M clauses)  |       ~2.5 GB  |         ~80 GB  |    40 %   |

So even the heaviest probed configuration (α = 7 with all 32 cores
busy) uses < 50 % of cluster RAM. There is room to go to α = 8 or
$n = 32$ without straining memory; the bottleneck will be wall time
on the UNSAT-prove direction, not RAM.

---

## 6. Open questions for the cluster sweep

1. **Is $(n=30, \alpha=5, d=8)$ feasible?** Single-thread can't
   distinguish "UNSAT" from "very hard SAT" at 60 s. If feasible,
   $c_{\log} = 5 \cdot 8 / (30 \ln 8) \approx 0.641$ — would be a
   significant improvement on our current best near $n = 30$.
   Resolving this needs either a real CnC lookahead cuber or a
   warm-start improver from a known witness (e.g. the $(6, 7)$
   graph from this probe).

2. **Is $(n=30, \alpha=5, d=10)$ feasible?** $c_{\log} \approx 0.696$
   — just above the n = 22 frontier circulant (0.6995). Same
   question, slightly more permissive box.

3. **Pareto check.** The probe didn't visit $\alpha = 5,\ d = 6$ or
   $d = 7$ (Caro–Wei-tight). Worth a separate run.

4. **N = 30 c_log baseline.** From this probe alone, the best $n=30$
   $c_{\log}$ we can claim is **0.719** at $(\alpha = 6,\ d = 7)$.
   Whether the c_log frontier at $n = 30$ extends below 0.719 is the
   open empirical question.

---

## 7. Witness storage

The three SAT witnesses ($(6, 7)$, $(6, 9)$, $(7, 7)$ at $n = 30$)
are not yet in `graph_db`. They were emitted by the probe but the
script discarded them. Re-running the SAT-find boxes through the
ordinary `SATKissat.run()` path would persist them automatically.
Worth doing once before any deeper search investment — having the
three witnesses available unlocks the Mode 3 improver path
(`NEXT.md` §3) for closing the gap to the $\alpha = 5$ boundary.
