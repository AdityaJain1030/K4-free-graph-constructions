# Tabusearch Folder — Analysis & Actionable Insights

## What's in here

| File | Problem solved | Status |
|------|---------------|--------|
| `search_circulants.py` | K4-free circulants on Z_N, minimise c | **Keep — genuinely useful** |
| `k4free_greedy.py` | GRASP+SA minimising c | Weak results (c≈0.83–0.96), redundant with SAT |
| `k4free_tabu.py` | Erdős-Rogers (triangle-free induced subgraph size) | **Wrong problem** — unrelated to c-conjecture |
| `ground_truth.json` | Exact min-c for all (N,d) pairs, N≤10 | Useful reference |
| `output.txt` | Full circulant search results N=8–50 | Keep as data |
| `results/greedy_results.csv` | GRASP+SA runs N=10–40 | Redundant |

---

## Key finding: score formula is inverted

`search_circulants.py` computes:

```
score = N * log2(d) / (d * alpha)
```

This is **1/(c · ln 2)** where c = alpha·d/(N·ln d) is the conjecture constant. So:

- **Higher score → lower c → closer to a counterexample**
- The `*** COUNTEREXAMPLE ***` marker fires when `score > 1.0`, which just means `c < 1/ln2 ≈ 1.44` — a very loose threshold, not a true conjecture violation
- To convert: `c = 1 / (score × ln 2)`

Global best: N=17, jumps=(1,2,4,8), d=8, alpha=3, score=2.125 → **c = 0.679** = Paley graph P(17)

---

## Circulant catalog is genuinely useful (N=8 to 50)

This is a systematic database of K4-free circulant graphs not found elsewhere in the repo. At N=36–50, the SAT solver doesn't reach — these circulants provide the only structured lower bounds on how small c can get in that range.

Notable results (converted to c):

| N | Best jumps | d | alpha | score | c |
|---|-----------|---|-------|-------|---|
| 17 | (1,2,4,8) | 8 | 3 | 2.125 | **0.679** |
| 34 | (2,4,8,16) | 8 | 6 | 2.125 | **0.679** (disjoint union of P17) |
| 43 | (5,17,18,20) etc. | 8 | 10 | 1.6125 | 0.895 |
| 47 | (1,9,10) etc. | 6 | 12 | 1.687 | 0.857 |
| 49 | (5,12,13,17) | 8 | 11 | 1.670 | 0.866 |

None beat P(17) at c=0.679, but the N=40–50 entries are better than the GRASP/random baselines (c≈0.90+).

---

## Bugs and limitations to fix before using at scale

### 1. Random sampling caps at large N
```python
if len(combos) > 5000:
    random.shuffle(combos)
    combos = combos[:5000]
```
At N≥40 with 4 jumps, this silently truncates the search. The result for large N is incomplete — you're seeing the best of a random 5000 subset, not the true best circulant.

**Fix:** Either raise the cap or switch to a smarter enumeration (e.g., prioritise jump sets with large gaps, or use a lattice search over connection multisets).

### 2. Alpha approximation can miss good graphs (N > 25)
For N>25, the script uses random-greedy to estimate alpha and only recomputes exact when `approx_score > 0.9`. Since we want **high** score (small alpha), if the approx **over**-estimates alpha, the score is underestimated and the graph is silently discarded.

**Fix:** Lower the recomputation threshold to `approx_score > 0.7`, or always compute exact alpha for the top-10 candidates per N.

### 3. Only 4 jump sizes tested
For N≥40, d=8 regular circulants need exactly 4 jumps (since degree = 2×|jumps| when all jumps < N/2). To get d=10 or d=12 at larger N you need 5–6 jumps.

**Fix:** Run with `--max_jump_size 5` for N≥40 to explore d=10 graphs.

---

## `k4free_tabu.py` is solving the wrong problem

The tabu search minimises **triangle-free induced subgraph size** (Erdős-Rogers conjecture), not c = alpha·d/(N·log d). These are related but different problems. The one recorded run (N=31, 300 iterations) got score=13 against a bound of 10.3 — not competitive, and not relevant to the main conjecture.

**Recommendation:** If you want tabu search for the c-conjecture, `k4free_greedy.py`'s SA phase is the right skeleton — but it still got c≈0.83 which is far from P(17)'s 0.679.

---

## Actionable next steps

1. **Extend circulant search to N=50–100** with `--max_jump_size 5 --n_max 100`. Remove or raise the 5000 combo cap. This is cheap (bitmask K4 check is fast) and fills the gap where SAT can't reach.

2. **Cross-reference N=25–35 circulant bests vs SAT pareto results.** If the circulant best c matches the SAT-verified optimum for those N, that's strong evidence that the extremal graphs ARE circulants — a structural insight worth writing up.

3. **Extract circulant catalog as a JSON database** (N, jumps, d, alpha, c) for use in the visualisation tools and 2-stage survey baselines. The data is already in `output.txt` — just needs parsing.

4. **For N=34 check**: jumps=(2,4,8,16) achieves score=2.125 → c=0.679. Is this truly a disjoint union of two P(17) copies, or a genuinely different graph? If it's a new construction, it's interesting; if it's just 2×P(17), it's expected.

5. **Kill `k4free_tabu.py`** or clearly label it as Erdős-Rogers-only, distinct from the main conjecture. Its results (`results.json`) are from a single 300-iteration run and are not useful.

6. **Port `ground_truth.json`** into the main SAT results pipeline as the N≤10 reference data — it has exact min-c by (N,d) pair and is a clean ground-truth source for validation.
