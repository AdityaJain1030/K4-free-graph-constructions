# Experiment log — K₄-free independence conjecture

A chronological seminar-style tour of everything that has been tried in
this repo, April 2026. Read it top-to-bottom to reconstruct how the
research direction evolved. Each block is:

- **Question** — what were we trying to learn?
- **Approach** — the experiment run, in 1–3 lines.
- **Result** — what came back, and what it forced next.

Null results are flagged explicitly. Where something failed, the
*failure* is the informative artefact — those blocks do more work for
future direction-setting than the small wins do.

The objective throughout is `c(G) = α(G) · d_max(G) / (N · ln d_max(G))`
on K₄-free graphs. The 30-year-open benchmark to beat is
`c(P(17)) ≈ 0.6789` (Paley graph on 17 vertices). Nothing in this repo
has beaten it; the experiments below map the landscape around it.

---

## Phase 0 — Framing and first sanity checks (≈ 2026-04-02)

### Exp 01 — Brute force at N ≤ 10
**Question.** Does exhaustive enumeration at tiny N match the known
Paley/Ramsey optima, and what does `c` look like on the complete
lattice of K₄-free graphs?
**Approach.** `search/brute_force.py`: enumerate canonical K₄-free
graphs at N = 8–10, compute α exactly, record (α, d_max, c).
**Result.** N = 8, d = 4, α = 2 **recovers the Paley case**. Confirms
the metric, the canonical-id machinery, and the α solver on a regime
where every answer is verifiable by hand. Becomes the permanent
correctness anchor: `graphs/brute_force.json`.

### Exp 02 — `axplorer` / PatternBoost direct attack
**Question.** Can DeepMind's PatternBoost (cross-entropy-trained
construction networks) optimize `c` or minimize α at fixed N?
**Approach.** Dropped `axplorer` in as a submodule, ran it against both
the raw c objective and the fixed-d α-minimization subproblem.
**Result.** **Both failed past R(4,4).** The landscape is flat: most
local moves barely perturb α. PatternBoost cannot credit-assign a
two-term objective where one term is NP-hard. Later absorbed into main
repo at 2026-04-11 but effectively retired; documents the "can't reach
there from here with a general-purpose learner" result.

---

## Phase 1 — SAT-exact as the correctness oracle (2026-04-08 → 2026-04-11)

### Exp 03 — SAT-exact sweep at N ≤ 22
**Question.** What is the true optimal `c` at every small N, and how
does it behave?
**Approach.** CP-SAT formulation over (N choose 2) edge bits + K₄
exclusion constraints + α witness set bits; `search/sat_exact.py`.
**Result.** Optimal c values at N = 12..22 recorded in
`graphs/sat_exact.json` (c ≈ 0.72 ± 0.02, no downward trend). Every
N ≤ 22 optimum is regular. All K₄-optimal at these sizes are verified
minima. The SAT pipeline becomes the trusted ground truth the rest of
the repo is measured against.

### Exp 04 — N = 24: sparser wins
**Question.** At N = 24 there are two Ramsey-plausible shapes —
(α=4, d=10) and (α=6, d=4). Which realizes smaller c?
**Approach.** SAT-exact with the near-regular constraint at each
candidate d; compare c.
**Result.** **(α=6, d=4) wins at c ≈ 0.721**, beating (α=4, d=10) at
c ≈ 0.724. Decisive killer of the "optimal α is always Ramsey-floor"
hypothesis. Fragile to the log term: for sparse graphs d/log(d) drops
faster than the α gain costs. Documented in `funsearch/so_far.md §2.2`.

### Exp 05 — HTCondor cluster run, N = 22..31
**Question.** How far can SAT-exact (or near-exact) scale on a cluster?
**Approach.** Parallelized SAT-regular over (n, α, d_max) triples with
HTCondor; see commits 2026-04-09..10.
**Result.** Clean optima through N ≈ 28. Beyond that the SAT solver
stops terminating in the wall-clock budget. `N = 24` was a particular
rabbit hole (timeout bug, fixed 2026-04-11). Takeaway: **N ≈ 30 is the
SAT ceiling** for general-purpose global optimality; any further
progress needs either symmetry reductions or a structured search class.

### Exp 06 — SAT-regular refactor (two-phase + scan-all-D)
**Question.** Several SAT-regular optima at small N looked worse than
they should — were we stopping at the first feasible D and missing the
real optimum?
**Approach.** Rewrote `search/sat_regular.py` (2026-04-20): iterate D
from Ramsey LB to UB carrying `best_E`; two-phase solve (feasibility,
then Σx ≤ best − 1 with hints) per D; loosen `edge_lex` symmetry to
row-0-only; `symmetry_mode="none"` option.
**Result.** Frontier moved down at several (n, α) pairs — e.g. N = 19,
α = 4 found at 57 edges (was being pruned by the old edge_lex). **Six
new frontier graphs** written to `graphs/sat_regular.json`. Confirms
that the old edge_lex constraint was silently cutting off optima; the
new `sat_regular` is correct where the previous one was just fast.
`memory/project_sat_regular_refactor.md` holds the details.

---

## Phase 2 — Heuristics that didn't work, and the fragility picture

### Exp 07 — Greedy / perturbation search on regular graphs
**Question.** Can simple greedy or PatternBoost-style perturbation
minimize α at fixed (N, d)?
**Approach.** `search/` early greedy routines; batch runs on N ≤ 40.
**Result.** **No.** Landscape is essentially flat for α under
1-perturbations. Documented in the 2026-04-08 commit message and
`funsearch/so_far.md §2.4`. Becomes the canonical "local search doesn't
budge α" baseline that every later method is compared against.

### Exp 08 — Paley perturbations at N > 17
**Question.** Paley graphs are the best known constructions at
prime-power N. Can we perturb P(q) for q > 17 (where P(q) contains K₄)
into K₄-free neighbors that still have small α?
**Approach.** Start from P(q), flip individual edges or switch
2-matchings, K₄-check, compute α. See 2026-04-16 commits.
**Result.** **Catastrophic.** Small perturbations blow up α
drastically. This is the *first* piece of evidence that optimal K₄-free
graphs sit on fragile algebraic ridges, not inside smooth basins. Later
formalized in `FRAGILITY.md`.

### Exp 09 — Fragility probe (random walks)
**Question.** Does the basin of low-c graphs *widen* with N (local
search should scale) or stay scale-invariant (local search is stuck
forever)?
**Approach.** `scripts/run_fragility.py`: seed from db-best at each N,
take 30 independent random single-edge-shift walks, record c at steps
{0, 1, 2, 5, 10, 20, 50, 100}. See `docs/theory/FRAGILITY.md`.
**Result.** Curves fan out by N on the Δ-panel — basin width grows
with N. So PatternBoost-style local search *should* help at large N,
but the fragility at small N is real: the seed's immediate neighborhood
is steep. This partially rescues the heuristic direction at large N,
even though Exp 07–08 ruled it out at small N.

---

## Phase 3 — FunSearch / LLM-in-the-loop (2026-04-16 → 2026-04-17)

All of this lives under `funsearch/`. Top-level docs:
`funsearch/so_far.md`, `summary.md`, `OPENEVOLVE_ANALYSIS.md`.

### Exp 10 — Vertex-by-vertex validation (180 graphs, N = 40/60/80)
**Question.** Is vertex-by-vertex construction with a learned priority
function (FunSearch skeleton) a viable attack?
**Approach.** Build N = 40/60/80 graphs with four structured priority
functions (degree, inverse_degree, balanced, constant) and two random
baselines; SAT-score all 180. Measure proxy-α vs true-α correlation.
**Result.** **Vertex-by-vertex is not viable.** c = 2.9–17.6 across
structured methods — catastrophically bad, produces degenerate
star-like graphs. **Random edge capped** beats all structured methods
2–3× at c ≈ 1.1–1.2. Greedy-MIS proxy correlates with true α at
ρ = 0.99, but SAT turns out to be fast enough (<3s at N = 80) that the
whole surrogate-scoring motivation evaporates. Credit assignment is the
killer — no intermediate α feedback until the graph is complete.

### Exp 11 — IS-join block composition at depth 1
**Question.** Do the SAT-optimal K₄-free graphs at small N *decompose*
as 1-joins of smaller blocks? (If yes → compositional search is in the
right space.)
**Approach.** Library of 83 K₄-free blocks (n ≤ 8) with 593 α-dropping
independent sets; exhaustive depth-1 IS-join composition
(351,649 valid pairs, vectorized, ~5.5 min); SAT-verify the top
candidates.
**Result.** **10/10 depth-1 α formula exact** (Valencia-Leyva theorem
holds). But best composed c at N = 10..21 is **12–25% worse than
SAT-optimal**. SAT-optima at these N do *not* decompose as 1-joins of
small-library blocks. Compositional search is searching in the wrong
neighborhood — at least at small N.

### Exp 12 — Depth-2 counterexample
**Question.** Can we bootstrap: compose at depth 1, verify, add as
first-class blocks, compose at depth 2?
**Approach.** Attempted the enrichment loop. A postdoc constructed a
concrete graph at depth 2 where α_formula underestimates true α,
growing linearly with depth.
**Result.** **Theory-killer.** The α formula is only provably exact at
depth 1. Proposition 7.16 (α-dropping propagation) is *false* in
general; the search objective at depth ≥ 2 becomes adversarially
misaligned (search rewards the broken α computation). Documented in
`funsearch/summary.md`. Enrichment is still possible via SAT-verify +
re-add, but each round requires ~20 SAT calls, which at large N is
where SAT starts to die.

### Exp 13 — Specialized FunSearch experiments (block_decomposition, selective_crossedge, forced_matching, pair_forced, reachability, evo_search)
**Question.** A suite of smaller LLM-driven construction experiments
exploring alternative skeletons (block composition variants,
cross-edge scoring, forced matchings, reachability-guided growth,
evolutionary composition).
**Approach.** Each lives under `funsearch/experiments/<name>/` with a
self-contained `run_experiment.py`. Results collected in
`funsearch/experiments/results_4_16.md`.
**Result.** **No sub-Paley c from any variant.** Best surviving
direction is the block library itself as a reusable resource, not as a
compositional optimizer. See appendix for per-variant notes.

### Exp 14 — `claude_search` v1 (LLM-generated Cayley candidates)
**Question.** Can the LLM propose structured Cayley connection sets
(Paley variants, Kneser, Grassmann, Peisert, GQ-incidence, Mathon,
dihedral, cubic residues, etc.) that beat the known floor?
**Approach.** `claude_search/candidates/` — ≈25 generator
scripts, each producing one parameterized family; scored through the
standard α pipeline.
**Result.** Several reproductions of the Paley floor at algebraic N
(P(17), CR(19), cubic/quartic/sextic residues, Peisert, etc.); no
beater. Same pattern as elsewhere — highly symmetric algebraic
constructions *sit on* the current floor but don't dip below it.

---

## Phase 4 — Cleanup, `graph_db`, algebraic constructions (2026-04-18 → 2026-04-19)

### Exp 15 — graph_db + canonical-id deduplication
**Question.** Across ~15 search sources, how many of the "distinct"
graphs are actually the same graph under relabeling?
**Approach.** Migrate from pynauty to `labelg` (nauty CLI) for
canonical id. Every new record is canonicalized before being written;
`(id, source)` is the dedup key. See 2026-04-21 "moved away from
pynauty" commit.
**Result.** Cross-source collisions revealed (e.g. a Cayley construction
and a circulant witness can land on the same canonical id). The db now
provides idempotent ingest and a cheap `frontier(n=...)` API. Downstream:
every later search's first sanity check is "does my minimizer already
exist under a different source name?"

### Exp 16 — Mattheus–Verstraete Hermitian-unital construction ingest
**Question.** How does the 2024 explicit `r(4, t) = Ω(t³/log⁴ t)`
construction score under our `c_log` metric?
**Approach.** `search/mattheus_verstraete.py`: build `Hq*` for q ∈
{2,3,4,5}; per-pencil bipartite flip; α via SAT.
**Result.** c_log ≈ 1.9 at N = 63 (q=3), ≈ 2.3 at N = 525 (q=5).
**Grows with q**, as predicted by the paper's bounds. Well above SAT's
best in the same N range. Not a beater; present in the db as a named
literature baseline (`source='mattheus_verstraete'`), per
`docs/searches/MATTHEUS_VERSTRAETE.md`.

### Exp 17 — Paley / circulant / cubic-residue catalog
**Question.** What does the full family of small-`c` Cayley-on-Z_n
constructions look like when fully enumerated at each N?
**Approach.** `search/circulant.py` and `search/circulant_fast.py`:
symmetric subsets of Z_n (|S| even, -S = S), K₄-filter, α solve; faster
variant uses bitmask K₄ pre-check. Populates `graphs/circulant.json`
and `graphs/circulant_fast.json`.
**Result.** P(17) floor recovered at N = 17. Cubic-residue CR(19) at
c = 0.7050 (N = 19) emerges as the second-best Cayley-on-Z_n floor.
**Non-algebraic N = 22 family** (c = 0.6995) is the surprise —
`Cay(Z_22, {1,2,8,9} ∪ {13,14,20,21})`, not obviously algebraic but
structurally a lift candidate. These three families become the spine
of all subsequent P(17)-lift work.

---

## Phase 5 — Structured large-N searches (2026-04-19 → 2026-04-20)

### Exp 18 — `random_regular_switch`
**Question.** Can Markov-chain 2-switches on random regular K₄-free
graphs at large N find low-c attractors?
**Approach.** `search/random_regular_switch.py`: seed random d-regular
graph, repeatedly pick two edges {ab, cd} and swap to {ac, bd} if
result stays K₄-free; record c per sampled graph.
**Result.** Populates `graphs/random_regular_switch.json`. Useful as a
**random-regular baseline** at large N where SAT is infeasible.
c ≈ 1.0–1.2 typical — worse than Cayley at the same N, as expected
(symmetry is where the win is).

### Exp 19 — `alpha_targeted`
**Question.** Given a target α value, what's the smallest d that makes
a K₄-free graph of (N, d, α) exist, and can we construct it?
**Approach.** SAT-regular with an α-upper-bound as a constraint; scan
d. Populates `graphs/alpha_targeted.json`.
**Result.** Matches Ramsey feasibility predictions where checkable.
Useful for populating rare (n, α) cells that unconstrained SAT tends
to skip because a suboptimal-c witness is easier to find.

### Exp 20 — `blowup` (disjoint union)
**Question.** Does taking k disjoint copies of a good small-N graph
preserve c? (It *does*, trivially — but is there any N where the
blow-up beats the best known at that N?)
**Approach.** `search/algebraic_explicit/blowup.py`: for every db graph G of order n,
write k·G at order kn for k up to some bound; record c (which equals
c(G) exactly).
**Result.** Null by design at every N. Present in `graphs/blowup.json`
because it gives a cheap, exact entry at every N = k·n that saves a
more expensive search from re-finding the same floor. This is the
formal analogue of Conjecture A's upper bound in construction form.

### Exp 21 — Empirical regularity evidence (2026-04-20)
**Question.** `REGULARITY.md` argues min-c K₄-free graphs should
satisfy `d_max − d_min ≤ 1`. Does the SAT corpus confirm this?
**Approach.** Re-solve every (n, α, spread) cell at spread ∈ {1, 3}
for n ∈ [10, 25]; compare to reference/pareto.
**Result.** **76 unique graphs, 46 strictly better than the prior
Pareto reference, 29 match, 1 gap.** Every row K₄-free after the
sync. Empirical `d_max − d_min ≤ 1` holds on the full corpus; the "1
gap" is a stale reference file, not a counterexample. Regularity is
not just a heuristic — it's provably tight on the recovered optima.
Documented in `docs/theory/EMPIRICAL_REGULARITY.md`.

---

## Phase 6 — Parczyk-style Cayley tabu (2026-04-21)

### Exp 22 — `cayley_tabu` across group families, N ∈ [10, 67]
**Question.** What floors does structured tabu reach across the
standard group families (cyclic, dihedral, direct product, abelian,
small non-abelian) at N out of SAT range?
**Approach.** `search/cayley_tabu.py`: Hamming-1 tabu over inversion
orbit bits of Γ, K₄-rejection, α via `alpha_bb_clique_cover`. Search
over every group of order N up to N = 67. See `CAYLEY_TABU.md`.
**Result.** **9 matches + 30 novel graphs** persisted to
`graphs/cayley_tabu.json`. Z₂-lifts reproduce the Paley floor at
N = 34, 51 exactly (no dip below 0.6789). No new beaters at any N.
First empirical hint that the P(17) floor is *locked* at 17k.

### Exp 23 — `cayley_tabu` sweep N = 68..100 (running)
**Question.** Does the P(17) floor continue to appear as the Cayley
minimum at N = 68, 85 (further 17k multiples), and what do non-17k N
produce?
**Approach.** PID 28860, started 13:00 on 2026-04-21, ETA ~4–5 h total.
**Result.** In progress (on N = 77 at time of this write-up). Drives
the 17k-specific lift-optimality questions in Phase 7.

---

## Phase 7 — P(17)-lift optimality, cyclic exhaustive proofs (2026-04-21)

Setup doc: `docs/theory/P17_LIFT_OPTIMALITY.md`. Three nested
conjectures:

- **A (cyclic)**: `CayMin(Z_{17k}) = c(P(17))`.
- **B (any group)**: every Cayley graph on a group of order 17k has
  c ≥ c(P(17)).
- **C (vertex-transitive)**: every K₄-free VT graph on 17k vertices
  has c ≥ c(P(17)).

A ⊂ B ⊂ C in strength.

### Exp 24 — Conjecture A exhaustive at k = 1, 2, 3 (N = 17, 34, 51)
**Question.** Is the k-lift of P(17) the unique cyclic minimizer on
Z_{17k} up to (Z_{17k})* action?
**Approach.** `scripts/verify_p17_lift.py`: bitmask enumeration of all
symmetric subsets of Z_n, lex-min orbit pruning under the
multiplicative group, K₄-reject, exact α. N = 17 (2⁸ subsets), 34 (2¹⁷),
51 (2²⁵ ≈ 34M).
**Result.** **Unique minimizer at every k verified.** 15 K₄-free orbits
at N = 17, 1338 at N = 34, 41162 at N = 51. c = 0.678915 exact in all
three cases. Conjecture A **proved exhaustively at k ∈ {1, 2, 3}**.
Records persisted under `source='cyclic_exhaustive_min'`.

### Exp 25 — Lift-tower family extension (N = 19, 22 and lifts)
**Question.** Is the lift-tower phenomenon specific to P(17) (algebraic),
or does it hold for any base-N c-floor construction?
**Approach.** Same exhaustive driver, applied to
`CR(19) = Cay(Z_19, {1,7,8,11,12,18})` (c = 0.7050) at N = 19, 38, and
the non-algebraic `Cay(Z_22, {1,2,8,9,13,14,20,21})` (c = 0.6995) at
N = 22, 44.
**Result.** **Same pattern holds.** The k-lift is the unique cyclic
minimizer on Z_{kN} for every base and every tractable k. So the
lift-tower structure is **not specific to algebraic constructions** —
it's a general feature of cyclic-minimizer floors. Table in
`BEYOND_CAYLEY.md §7`. Total: 7 exhaustive-minimum records under
`source='cyclic_exhaustive_min'`.

### Exp 26 — Dihedral verifier D_17 at N = 34 (built, not yet run)
**Question.** Does the non-abelian group of order 34 (D_17) admit a
sub-Paley Cayley construction? If yes → new beater, first in history.
If no → Conjecture B closed at k = 2.
**Approach.** `scripts/verify_dihedral.py`: symmetric-subset bitmask on
D_p with rotation/reflection splitting (2²⁵ subsets for p = 17);
orbit-reduce under Aut(D_p) = Hol(Z_p) (|Hol(Z_17)| = 272); α+K₄ as
before. Includes the "P(17)-lift embedded as rotation-only" check.
**Result.** **Pending.** Smoke test at p = 5 queued; full D_17 run
held until Exp 23 (cayley_tabu sweep) frees CPU. Expected runtime
20–60 min. Two-branch stopping rule: min c ≥ 0.6789 ⇒ Conjecture B
closed at k = 2; min c < 0.6789 ⇒ first construction to beat Paley.

### Exp 27 — Z_17 ⋊ Z_3 at N = 51 (not needed, 2026-04-23)
**Question.** Same as Exp 26 for any non-abelian group of order 51.
**Approach.** None — the premise was wrong. There is no non-abelian
group of order 51: Aut(Z_17) = Z_16 has no element of order 3 since
3 ∤ 16, so every φ: Z_3 → Aut(Z_17) is trivial and G = Z_51 (cyclic).
GAP confirms: `NrSmallGroups(51) = 1`, structure `C51`.
**Result.** **Conjecture B closed at k=3 trivially** by the cyclic-Z_51
exhaustive verification already in the DB (`source='cyclic_exhaustive_min'`,
41,162 K₄-free orbits, unique minimizer = k=3 lift of P(17)). No
verification script needed.

---

## Phase 8 — Non-vertex-transitive attacks (2026-04-21)

`BEYOND_CAYLEY.md` argues that θ(G) = α(G) for every VT graph, so VT
graphs sit *on* the Lovász θ-surface — any sub-Paley c must live
below it, i.e. in non-VT space. Two attempts so far.

### Exp 28 — Asymmetric lift tabu at N = 34 (null)
**Question.** Can a 1-flip tabu search escape 2·P(17) by adding /
removing a few cross-layer edges (breaking vertex-transitivity)?
**Approach.** `scripts/asymmetric_lift_tabu.py`, two modes:
(a) cross-only 289-bit neighborhood warm-started at 2·P(17),
(b) full 561-bit neighborhood with the same warm start. 8 restarts,
300 iters each, 326 s total.
**Result.** **No escape.** 2·P(17) is a strict local minimum under
1-flip in the full 561-bit space. Next-basin floor is
(α=6, d=9, c=0.7228), strictly worse. Takeaway: beating 0.6789 at
N = 34 needs either multi-flip moves (2-opt, 3-opt), a
structurally-different warm start, or SAT-exact over the full
561-bit space with c < 0.6789 as target. No DB record (guarded on
c < 0.70, which the global best — equal to P(17) — didn't clear as a
new graph).

### Exp 29 — McKay SRG catalog screen (null)
**Question.** The SRG catalog is the largest cheaply-enumerable
non-VT source (most members of srg(40,12,2,4), all Paulus graphs,
etc.). Does *anything* in it beat c = 0.6789?
**Approach.** `experiments/srg_catalog/run.py`: for each of 10 SRG
classes (v ≤ 40, minimal then exhaustive tier), parse `.g6`, filter
K₄-free via bitmask common-neighborhood intersection, α via
`alpha_bb_clique_cover_nx`, ingest survivors to
`graphs/srg_catalog.json`. Raw `.g6` under `experiments/srg_catalog/g6/`
(gitignored).
**Result.** **4,361 graphs screened, 13 K₄-free survivors, 0 beat
0.6789.** Best catalog c = 0.9651 (srg(27,10,1,5), Schläfli
complement). Empirical pattern across all 13 survivors: **every
K₄-free SRG sits at or near Hoffman-tight α** — strong regularity
tightens the Hoffman bound, so even the non-VT SRGs (2 of 10 Paulus
graphs) don't realize the §3 sub-θ headroom in practice. SRG-based
attacks at v ≤ 40 are empirically exhausted. Documented in
`docs/searches/SRG_CATALOG.md`. Minor correction logged there too:
the "R(4,4) = 18 ⇒ Paulus contains K₄" argument forces K₄ in the
pair (G, Ḡ), not in G alone — two Paulus members really are
K₄-free.

### Exp 30 — SAT-exact at N = 17, 34 without VT constraint (queued)
**Question.** Does dropping the VT constraint and running SAT-exact
over the full (N choose 2)-bit space produce anything below 0.6789
at N ∈ {17, 34}?
**Approach.** `search/sat_exact.py` with `vertex_transitive=False` at
N = 17 (136 bits — feasible); same at N = 34 (561 bits — tight
budget, needs cluster).
**Result.** **Not yet run.** Clean stopping rule: match 0.6789 at both
⇒ very strong evidence for Conjecture C at small k; break 0.6789 at
either ⇒ new global minimum.

---

## Phase 9 — What's on deck (as of 2026-04-21 evening)

Ordered by cost-vs-payoff in `BEYOND_CAYLEY.md §8`:

1. Wait for `cayley_tabu` N = 68..100 sweep (Exp 23) to free CPU.
2. Smoke-test `verify_dihedral.py --p 5` (seconds).
3. Full D_17 exhaustive (Exp 26). **Either closes B at k=2 or breaks
   Paley.**
4. ~~Write + run Z_17 ⋊ Z_3 verifier at N = 51 (Exp 27).~~ Dropped
   2026-04-23: no such group exists; B at k=3 closed by cyclic Z_51.
5. SAT-exact at N = 17 full-bitvector (Exp 30, small-N half).
6. SAT-exact at N = 34 on the 200 GB server (Exp 30, big-N half).
7. Asymmetric lift tabu with multi-flip moves (follow-up to Exp 28).
8. If SAT matches 0.6789 at 17, 34, 51: start the flag-algebra /
   character-theoretic proof of Conjecture A for all k (estimated 2–5
   page note).

The landscape is well-mapped; the remaining questions are sharp and
each has a definitive stopping rule.

---

## Appendix — FunSearch sub-experiments, in brief

Each lives under `funsearch/experiments/<name>/`.

- **`baselines/`** — vertex-by-vertex and random-edge-capped sanity
  runs. Baseline for Exp 10.
- **`initial_validations/`** — cheap probes for SAT throughput and
  proxy-α rank correlation at N = 40/60/80. Feeds Exp 10.
- **`block_decomposition/`** — depth-1 IS-join composition over an
  83-block library; Exp 11.
- **`block_optimal/`** — probe whether the SAT-optima at small N are
  themselves 1-joins of library blocks (they aren't; see Exp 11).
- **`selective_crossedge/`** — LLM-proposed rules for which cross
  edges to keep when composing; variants of Exp 11. No beater.
- **`forced_matching/`** — enforce a perfect matching in the IS-join
  bipartite connector; tighter K₄-control, weaker α. No beater.
- **`pair_forced/`** — pair-level forcing during composition. Failed
  to lower c below depth-1 plain.
- **`reachability/`** — guide LLM construction by α-reachability
  signals during the build. Inconclusive; credit assignment still
  dominates (Exp 12 theme).
- **`evo_search/`** — evolutionary composition over the block library
  with FunSearch-style islands. Best run matches Exp 11's depth-1
  floor, doesn't exceed it.

Full summaries in `funsearch/experiments/results_4_16.md` and
`funsearch/summary.md`.

---

## How to read this log

- **Null results dominate.** That's the point — the shape of the
  landscape only becomes legible after the easy attacks fail. Each
  null result in Phase 2–4 was a direction-narrowing step that made
  Phase 5–7 possible.
- **"c = 0.6789 reproduced" is not a null result** at large N — it's
  evidence toward Conjecture A/B/C that the Paley floor is the
  Cayley/VT ceiling at 17k.
- **"c > 0.6789" is not a failure** for a non-VT method — Exp 29's
  empirical Hoffman-tight pattern on SRGs is a *theorem-adjacent*
  observation worth recording even though no beater emerged.
- **Every block above persists its output** to either `graphs/*.json`
  (canonical via `graph_db`) or a `docs/` write-up. There is no
  throwaway run; the repo state *is* the experimental record.
- **The live frontier question**, as of 2026-04-21, is Exp 26
  (D_17 at N = 34). It has a clean binary outcome that either closes
  Conjecture B at k = 2 or breaks the 30-year Paley floor.
