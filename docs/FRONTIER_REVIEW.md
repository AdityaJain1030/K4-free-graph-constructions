# Frontier review — state of the problem + next steps

Discussion notes, originally 2026-04-22; refreshed 2026-04-23 to fold
in the GAP SmallGroups sweep, the `sat_circulant_optimal` producer,
and the Lovász θ column. The goal of this document is to capture
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

## Frontier audit (from `graph_db`, 842 unique graphs / 1204 rows)

### Best c_log per N, with a representative holder

Many N-rows are tied across 6+ sources after the latest sweeps; the
`source` column below picks one structurally-representative finder.

```
 N | c_log    | source               | alpha | dmax | regular?
---+----------+----------------------+-------+------+---------
10 | 0.8656   | circulant             |   3   |   4  | yes
11 | 0.7869   | circulant             |   3   |   4  | yes
12 | 0.7767   | circulant             |   3   |   5  | yes
13 | 0.7728   | cayley                |   3   |   6  | yes
14 | 0.7176   | sat_exact             |   3   |   6  | NO (deg 5,5,6,...,6)
15 | 0.7195   | sat_exact             |   3   |   7  | NO (deg 6,6,6,7,...,7)
16 | 0.7213   | circulant             |   4   |   4  | yes
17 | 0.6789   | cayley (P(17))        |   3   |   8  | yes   ← global min
18 | 0.7441   | circulant             |   4   |   6  | yes
19 | 0.7050   | cayley (CR(19))       |   4   |   6  | yes
20 | 0.7195   | sat_exact             |   4   |   7  | yes (tied by cayley_tabu)
21 | 0.7328   | circulant             |   4   |   8  | yes   ← OPEN: α=4 d=7
22 | 0.6995   | circulant (C(22))     |   4   |   8  | yes
...
34 | 0.6789   | circulant             |   6   |   8  | yes   ← P(17) blowup
51 | 0.6789   | circulant_fast        |   9   |   8  | yes
68 | 0.6789   | circulant_fast        |  12   |   8  | yes
85 | 0.6789   | cayley_tabu_gap       |  15   |   8  | yes   ← new (2026-04-23)
```

### Extremizer families

P(17) is the global minimum across all 842 unique graphs. Three
asymptotic plateaus repeat and are now confirmed through higher N:

| Plateau | c_log  | Hit at N                        | Family                      |
|---------|--------|---------------------------------|-----------------------------|
| A       | 0.6789 | 17, 34, 51, 68, 85               | P(17) and its blowups        |
| B       | 0.6995 | 22, 44, 66, 88                   | C(22; …) circulant family    |
| C       | 0.7050 | 19, 38, 57, 76, 95               | CR(19) residue family        |

No graph in the DB beats plateau A. Plateau B is now confirmed to
N=88 (matches the predicted extension in the last review); C extends
cleanly to N=95. Sanity-checking B and C at N=110, 132 remains cheap
and worth doing.

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

### Lovász θ snapshot (new, 2026-04-23)

The cache now stores `lovasz_theta` for every row (1204/1204
populated). For the 100 best-known graphs (min c_log per N, N=10..100):

- **α = θ exactly** on only 4 frontier graphs (N ∈ {4, 5, 9}) — the
  SDP certifies α optimal only at tiny N.
- **θ = H exactly** on 18 frontier graphs, all Paley-like / residue
  chains: P(13), P(17) lift chain {17, 34, 51, 68, 85}, CR(19) chain
  {19, 38, 57, 76, 95}, P(37) chain, plus singletons at N=67, 109,
  125, 127.
- **Nothing below plateau A.** The 5 sub-plateau graphs are exactly
  the P(17) lift chain — all with θ=H=α/0.728.
- Median α/θ on frontier = 0.777, median θ/H = 0.879, median α/H = 0.690.
- Biggest SDP slack at large N: N=99 (θ−α=8.06), N=92 (7.75), N=94,
  98, 89 — cyclic / `sat_circulant_optimal` winners where the α
  solver under-converges. `⌊θ⌋` gives a concrete α-improvement target
  per graph.

### Cayley-class marginal contribution past N=40

The 2026-04-23 GAP SmallGroups sweep (new source `cayley_tabu_gap`,
285 rows, N=10..94) largely supersedes the ad-hoc `cayley_tabu`
comparison. Frontier contributions that require a Cayley construction
(not reachable by `circulant_fast`):

- **5 strict frontier PRs** through N=94 from the GAP sweep:
  N=28 (D₂₈), 36 (S₃×S₃), 40, 80, 92.
- The older `cayley_tabu` run still holds several ties at N=41..76
  (dihedral, direct products, elementary abelian) that circulant
  can't touch. Those wins are genuine, not noise.

Where `cayley_tabu_gap` *loses* to `circulant_fast` on the same N
(N ∈ {31, 37, 43, 47, 49, 50, 53, 67, 69, 70, 74, 81, 83, 90, 91}),
the pattern is always tabu-on-C_N losing to exhaustive cyclotomic
structure. Warm-seeding would fix this but compromises the "unaided
Cayley reach" question; deferred.

The single visible high-N hole is **N=79**, where frontier sits at
0.8796 from `sat_circulant_optimal` (α=16, d=10). No Cayley
construction in the DB reaches N=79.

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

**Now near-certain within the Cayley class we can search.** The
2026-04-23 GAP sweep covered all SmallGroups up to the MAX_GROUPS
ceiling, and the Hoffman + θ analysis is damning:

- Of 285 `cayley_tabu_gap` records, only 8 have spectrum permitting
  sub-P(17). All 8 are Hoffman-saturated or sit on a named plateau.
  **No further tabu budget on the current SmallGroups pool can break
  P(17).**
- θ(G) computed for all 285 confirms the verdict under the tighter
  SDP ceiling: θ < H for 87.7% of Cayley graphs, so Hoffman is a
  loose bound most of the time, but α/θ stays invariant along lift
  chains (same plateau fingerprint as α/H).
- SDP-derived `c_log` ceilings (θ · d / (N · ln d)) are **all above
  0.95** for GAP frontier winners. None of them can beat P(17) under
  any SDP argument.
- The cyclotomic circulant probe (2026-04-22, p ∈ {37, 41, 61, 73,
  89}, orders 4 and 6, 182 configs, 48 K₄-free) produced 0 hits
  below plateau A. Best: sextic Paley at p=37, `c_log = 0.8145`.

Why P(17) is hard to beat, theoretically:

- Paley `P(p) = Cay(ℤ_p, QR_p)` for `p ≡ 1 (mod 4)`.
- Exactly 3 eigenvalues — it's strongly regular (`srg(p, (p-1)/2,
  (p-5)/4, (p-1)/4)`).
- Hoffman bound is tight in the ratio sense on SRGs with these
  parameters.
- Self-complementary (`P(p) ≅ P̄(p)`), arc-transitive, and K₄-free
  iff `p ∈ {5, 9, 13, 17}` (only 17 is interesting here).

General Cayley graphs have more distinct eigenvalues, so Hoffman
loosens, so α gets bigger, so `c_log` gets bigger. The empirically
open seam is **Cayley(G, S) for G above the current SmallGroups
ceiling** or **simple-group Cayley** (A₅ at N=60, S₅ at N=120,
PSL(2, q)) — groups whose irreducible representations produce
spectra not already enumerated.

### Class inclusions

```
Paley(p)  ⊂  circulant = Cay(ℤ_N, ·)  ⊂  Cayley(any group)  ⊂  vertex-transitive
```

- `CayleyResidueSearch` only hits Paley-like residue graphs at primes.
- `CirculantSearch` exhausts circulants up to N=35.
- `CirculantSearchFast` handles circulants for N=35..~100 with
  multiplier-action dedup.
- `SatCirculantOptimal` proves circulant-class optimality by SAT on
  regular circulants at N ≤ 100.
- `CayleyTabuSearch` reaches the broader Cayley space on non-cyclic
  groups (dihedral, direct products, `ℤ_2^k`, `ℤ_3 × ℤ_2^k`).
- `CayleyTabuGAP` (new, 2026-04-23) extends tabu to all SmallGroups
  via GAP, including Frobenius `ℤ_7 ⋊ ℤ_3` and other non-abelians
  that the hand-coded tabu missed.

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

### 2. Push Cayley search past the SmallGroups ceiling

The "extend `cayley_tabu` past N=77" recommendation from the previous
review is largely *done* — `cayley_tabu_gap` now covers N=10..94
including N=77, 78 on Frobenius and other non-cyclic groups. What's
left is narrower and sharper:

- **N=79 remains a gap.** Best 0.8796 from `sat_circulant_optimal`;
  no Cayley hit at all. Either a circulant of N=79 exists below
  plateau, or the hole tells us something about 79 specifically.
- **Groups that produce new spectra.** Per the GAP verdict, further
  budget on current SmallGroups cannot beat P(17). Spend tabu
  instead on simple groups (A₅ at N=60, S₅ at N=120), PSL(2, q),
  or primes beyond the existing `MAX_GROUPS_PER_N=500` cap.
- **B-family sanity check at N=110, 132** and C-family at N=114.
  Cheap from `circulant_fast` alone — resolves whether the plateau
  extensions saturate or break.

### 3. Integrate claudesearch into graph_db

Currently `claude_search/results.jsonl` is its own leaderboard. Its
outputs never reach `cache.db` (confirmed: 0 rows with any
`claude_search*` source), so "claudesearch collapses on known optima"
is only visible in eval JSONL, not on the frontier axis.

A one-shot ingest pass (`GraphStore.write` under
`source='claude_search'`) makes its contribution comparable with
every other producer. Worth doing before judging it.

### 4. Big experiments review

After (1)–(3) land, prune the experiments tree. Keep:

- Anything that produced a frontier hit at any N.
- Anything whose negative result is load-bearing: **SRG catalog**
  (McKay SRG enumeration exhausted, 0 sub-Paley hits — 2026-04-21);
  **cyclotomic probe** (0 hits below P(17) at p ∈ {37..89} — 2026-04-22);
  **GAP SmallGroups sweep** (Hoffman/θ-saturated on all spectrum-
  eligible Cayley graphs — 2026-04-23); **composition screens** (see
  below).
- Anything documenting methodology (baselines, ablations).

#### Composition screens (2026-04-23)

Two screens ran against the prompt "can we combine existing K₄-free
graphs into a sub-plateau-A construction?" — both closed within the
current catalog, but the two negatives have different shapes.

**Spectrum-balance screen (`scripts/spectrum_balance_screen.py`) — a
quantitative wall.** For every pair of regular K₄-free graphs in the
DB (636 unique, 202,560 pairs), computed the Hoffman-predicted c_log
of the tensor product using `λ_min(G₁⊗G₂) = min(λᵢ·μⱼ)`. The best
predicted c_log is **0.9618** (C₁₂ ⊗ C₁₂); P(17) ⊗ anything bottoms
out at 1.92. Zero pairs dip below plateau A. This is consistent with
the analytic prediction that `c_log^tensor ≳ Θ(1/ln d)` for K₄-free-
preserving tensors — the 0.9618 number is the back-of-envelope
calculation, not a surprise. The screen's load-bearing value is the
falsifiable bar: **any future tensor-based proposal over factors
from the existing catalog has to clear 0.9618 just to reach the
tensor-Hoffman floor.**

**Clique-cover screen (`scripts/clique_cover_screen.py`) — a
structural absence.** For the 26 at- and near-plateau graphs
(c_log ≤ 0.72), enumerated maximum cliques and pairwise
intersections. Every frontier graph has ω=3 (triangles), and **zero
of 26 have the spread property** (max cliques pairwise meeting in
≤1 vertex) that MV-style random bipartization requires. P(17) is the
paradigm case: SRG(17, 8, 3, 4), so every edge sits in exactly λ=3
triangles, and 204 pairs of triangles share an edge — the triangle
structure is maximally overlapping, the *opposite* of a unital /
spread. The complement view is the same: P(17) is self-complementary,
2·P(17)'s complement has ω=6 with 4624 max independent sets, none
spread.

What this does *not* show: that the MV mechanism is dead. It shows
the MV-eligible raw material is **not in the K₄-free catalog at
all** — which matches where the original MV construction lives
(Hermitian unital, ω=q, K₄-rich). The active follow-up is the
`non_k4_free_clique_structured` direction mentioned above: add
unitals, generalized quadrangles, and small polar spaces to
`graph_db`, then run MV-bipartization on those. The screen is
evidence that you have to leave the catalog to find MV structure,
not evidence that MV doesn't work.

Scope caveat: both screens are conclusive only *within the K₄-free
catalog as it stands*. Algebraic products over non-K₄-free factors
(the actual MV setting) are untouched, and that's the live seam.

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
existing `α_lb` surrogate. Training data: the 842-graph DB, plus
tabu trajectories labeled with true α. Especially relevant for the
non-SmallGroups Cayley direction (simple groups, PSL(2, q)) where
exhaustive enumeration is out of reach.

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
- Non-abelian Cayley outside the SmallGroups ceiling as the open
  direction — what's known, what isn't.

This is what the `cayley_tabu` / `cayley_tabu_gap` / `circulant`
distinction should refer to, rather than repeating the class
explanation inline in each search's README.
