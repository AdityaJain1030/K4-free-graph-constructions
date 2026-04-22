# Frontier review — state of the problem + next steps

Discussion notes, 2026-04-22. The goal of this document is to capture
where the repo's frontier actually sits, which of our heuristics
survive contact with the data, and what's worth doing before turning
to neural-net methods.

---

## The problem, restated

Minimise

```
c_log(G) = α(G) · d_max(G) / (N · ln d_max(G))
```

over K₄-free graphs. The conjecture claims `c_log ≥ c > 0` for some
absolute constant. Beating `P(17)` at `c_log ≈ 0.6789` is the
practical target; disproving the conjecture means showing a family
with `c_log → 0`.

---

## Frontier audit (from `graph_db`, 710 graphs)

### Best c_log per N, with holder and degree regularity

```
 N | c_log    | source         | alpha | dmax | regular?
---+----------+----------------+-------+------+---------
10 | 0.8656   | circulant      |   3   |   4  | yes
11 | 0.7869   | circulant      |   3   |   4  | yes
12 | 0.7767   | circulant      |   3   |   5  | yes
13 | 0.7728   | cayley         |   3   |   6  | yes
14 | 0.7176   | sat_exact      |   3   |   6  | NO (deg 5,5,6,...,6)
15 | 0.7195   | sat_exact      |   3   |   7  | NO (deg 6,6,6,7,...,7)
16 | 0.7213   | circulant      |   4   |   4  | yes
17 | 0.6789   | cayley (P(17)) |   3   |   8  | yes   ← global min
18 | 0.7441   | circulant      |   4   |   6  | yes
19 | 0.7050   | cayley         |   4   |   6  | yes
20 | 0.7195   | sat_exact      |   4   |   7  | yes
21 | 0.7328   | circulant      |   4   |   8  | yes   ← OPEN: α=4 d=7
22 | 0.6995   | circulant      |   4   |   8  | yes
...
34 | 0.6789   | circulant      |   6   |   8  | yes   ← P(17) blowup
51 | 0.6789   | circulant_fast |   9   |   8  | yes
68 | 0.6789   | circulant_fast |  12   |   8  | yes
85 | 0.6789   | circulant_fast |  15   |   8  | yes
```

### Extremizer families

P(17) is the global minimum across all 710 graphs. Three asymptotic
plateaus repeat:

| Plateau | c_log  | Hit at N                  | Family                     |
|---------|--------|---------------------------|----------------------------|
| A       | 0.6789 | 17, 34, 51, 68, 85         | P(17) and its blowups       |
| B       | 0.6995 | 22, 44, 66, 88             | C(22; …) circulant family   |
| C       | 0.7050 | 19, 38, 57, 76, 95         | C(19; …) circulant family   |

No graph in the DB beats plateau A. The two other plateaus come from
circulant families on N=22 and N=19 and recur at their multiples via
essentially-blowup constructions.

### What the proven-optimal data says about regularity

Of 11 proven-optimal graphs (N=10..20):

- **9 are strictly regular.**
- **N=14 and N=15 are near-regular with degree spread = 1.**
  - N=14: degree sequence `[5, 5, 6, 6, …, 6]` — 2 irregular vertices.
  - N=15: degree sequence `[6, 6, 6, 7, 7, …, 7]` — 3 irregular vertices.
- These are the *only* N where `sat_exact` strictly beats everything
  else. At N=14 SAT beats the best circulant by 0.107; at N=15 by
  0.174. At N=20 SAT ties `cayley_tabu`.

Interpretation: proven optima are **near-regular, not strictly
regular**. In tight boxes the optimum takes degree spread 1 to shave
one or two edges — and circulant / tabu can't reach those constructions
because both restrict to regular Cayley graphs.

### Cayley-tabu marginal contribution past N=40

At N=40..79, `cayley_tabu` vs `circulant_fast`:

- **11 wins** (e.g. N=59 +0.126, N=46 +0.084, N=60 +0.050)
- **21 ties**
- **8 losses**

Tabu reaches non-cyclic Cayley constructions (dihedral, direct
products, elementary abelian) that circulant can't touch. The
frontier wins are genuine, not noise.

### N=21 stubborn box

Proven status for N=21: all boxes closed except **α=4, d=7**.

- If feasible: `c_log = 4·7 / (21 · ln 7) = 0.6853`.
- If infeasible: N=21 frontier stays at 0.7328 (α=4, d=8), already
  held by a circulant.
- A feasible witness at α=4, d=7 would be the **first near-P(17)
  extremizer at a non-multiple of 17**, and structurally new.

---

## Where the earlier heuristics stand

### "Cayley peaks at P(17)"

**Confirmed empirically** within this DB. Not a theorem — there's no
proof that no non-abelian Cayley graph at some large N ever beats
`c_log = 0.6789`.

Why P(17) is hard to beat, theoretically:

- Paley `P(p) = Cay(ℤ_p, QR_p)` for `p ≡ 1 (mod 4)`.
- Exactly 3 eigenvalues — it's strongly regular (`srg(p, (p-1)/2,
  (p-5)/4, (p-1)/4)`).
- Hoffman bound `α ≤ N · (-λ_min) / (d - λ_min)` is tight for
  strongly-regular graphs, so α is exact from the spectrum.
- Self-complementary (`P(p) ≅ P̄(p)`), arc-transitive, and K₄-free
  iff `p ∈ {5, 9, 13, 17}` (only 17 is interesting here).

General Cayley graphs on other groups have more distinct eigenvalues,
so Hoffman loosens, so α gets bigger, so `c_log` gets bigger.
Non-abelian cases are less constrained but less studied — the open
frontier of this heuristic lives there.

### Class inclusions

```
Paley(p)  ⊂  circulant = Cay(ℤ_N, ·)  ⊂  Cayley(any group)  ⊂  vertex-transitive
```

- `CayleyResidueSearch` only hits Paley-like residue graphs at primes.
- `CirculantSearch` exhausts circulants up to N=35.
- `CirculantSearchFast` handles circulants for N=35..~100 with
  multiplier-action dedup.
- `CayleyTabuSearch` reaches the broader Cayley space on non-cyclic
  groups (dihedral, direct products, `ℤ_2^k`, `ℤ_3 × ℤ_2^k`).

### "Regularity is important"

**Near-regular, not strictly regular.** Proven optima at N=14 and
N=15 carry degree spread 1. That's the *only* structural signal
distinguishing SAT-frontier wins from the regular Cayley / circulant
baseline below N=20.

---

## Where to spend the remaining computational budget

### 1. Close more SAT boxes at N=21, 22, 23

- N=21 α=4 d=7 is the single open box. Feasible → new near-P(17)
  extremizer. Infeasible → N=21 frontier certified.
- N=22 already has 0.6995 from circulant. The interesting question is
  whether α=4 d=7 at N=22 (c_log = 0.6530) is feasible — if yes, this
  would be the first graph to beat P(17).
- N=23 similarly has multiple open boxes.

The existing `sat_exact` pipeline is overengineered for this job.
Simplify and reuse it for two narrow purposes:

- **Box closer.** Single `(N, α, d)` feasibility. No scan, no prune,
  no seed — just the aggressive CP-SAT params from `prove_box.py`.
- **Local improver.** Seeded from a tabu Cayley graph, relax the
  Cayley constraint, minimise edges subject to the tabu graph's α.
  SAT's small-improvement pattern at N=14, 15, 20 is the motivating
  evidence that this class of perturbation actually finds frontier
  graphs.

Anything past the Pareto-scan phase of `sat_exact.py` is out of scope
for these two tasks and can be trimmed.

### 2. Extend cayley_tabu past N=77

Tabu contributes frontier hits at N=41, 45, 46, 47, 53, 59, 60, 61,
62, 67, 71. It's *absent* (timeout) at N=77, 78, 79.

Two changes worth making:

- **Frontier-contribution stopping criterion.** Kill tabu when it
  fails to beat circulant_fast for K consecutive N, not when it hits
  wallclock. Currently we lose tabu at exactly the N where
  circulant_fast is also running out of steam, which is the worst
  possible cutoff.
- **Sanity check the B-family.** Plateau B (0.6995) should extend to
  N=110, 132 if the C(22; …) family is really a repeating
  circulant-blowup structure. Cheap to verify from circulant_fast
  alone. A positive result tightens our understanding of the 17-
  vs 22-family split.

### 3. Integrate claudesearch into graph_db

Currently `claude_search/results.jsonl` is its own leaderboard. Its
outputs never reach `cache.db`, so "claudesearch collapses on known
optima" is only visible in eval JSONL, not on the frontier axis.

A one-shot ingest pass (`GraphStore.write` under
`source='claude_search'`) makes its contribution comparable with
every other producer. Worth doing before judging it.

### 4. Big experiments review

After (1)–(3) land, prune the experiments tree. Keep:

- Anything that produced a frontier hit at any N.
- Anything whose negative result is load-bearing (e.g. SRG catalog —
  0 hits, exhausted, memory recorded).
- Anything documenting methodology (baselines, ablations).

Archive:

- Experiments that produced neither frontier movement nor useful
  negative signal.
- Half-finished tactics without a writeup explaining what they
  taught us.

The goal is a lean repo where the frontier audit, the extant
producers, and the experiments-worth-remembering are all visible at
a glance — so the next pass (neural nets, RL, whatever) starts from
a clean map rather than debugging history.

---

## On neural nets, when we get there

**Not**: GNN-as-α-predictor. Your α solver is fast; the bottleneck
is calling it many times, and a GNN call would be the same cost with
worse fidelity. This is a nonstarter.

**Yes, maybe**: GNN-as-neighbor-ranker inside tabu. Score all L
neighbors with a cheap forward pass, exact-solve the top few. Trades
wallclock for a small optimality loss and is the same shape as the
existing `α_lb` surrogate. Training data: the 710-graph DB, plus
tabu trajectories labeled with true α.

**Yes, maybe**: GNN that predicts `Δ(α, d_max)` for Hamming-1
neighbors of a known state. Easier learning problem than cold
prediction because the net learns the local derivative, not the full
function.

**Before any of this**, the batching idea from the inner loop is the
better lever:

- Warm-start α binary search from the parent's α (saves log(N) per
  neighbor).
- Reuse clique-cover partition across neighbors (repair only
  disturbed cliques).
- Process-parallel across neighbors on the 32-core server
  (embarrassingly parallel, ~20× wallclock).

All three are small changes to existing code and dwarf any
incremental-SAT gain we'd get from rebuilding the solver stack.

---

## Documentation needs (for the graph-theorist reader)

A short `docs/theory/CAYLEY_CLASSES.md` covering:

- Definitions: Cayley graph, circulant, Paley.
- The inclusion chain and what each class gives up / gets.
- Spectrum structure per class (k+1 eigenvalues for residue-Cayley
  at prime, 3 for Paley, variable for general Cayley).
- Why Hoffman-tightness implies Paley's empirical extremality, and
  why this is an argument not a proof.
- Non-abelian Cayley as the open direction — what's known, what
  isn't.

This is what the cayley_tabu / circulant distinction should refer
to, rather than repeating the class explanation inline in each
search's README.
