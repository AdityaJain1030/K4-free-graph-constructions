# switch_tabu — design, diagnostics, findings

Seminar-style notes for the 2-switch / mixed-operator tabu work at N=23.
Question/answer format. Each Q is a specific point you'd want to be able
to answer if asked; each A is grounded in what we actually ran.

---

## Background

### Q: What's the search problem?
A: Find a K4-free graph on N vertices that minimises
`c_log = α(G) · d_max / (N · ln d_max)`. The N=23 frontier from SAT-exact
is α=6, d∈{3,4}, c_log = 0.7527. We want a tabu method that can
discover this without an oracle.

### Q: What tabu variants existed before this work?
A: Two:

1. `search/cayley_tabu.py` — tabu over the **orbit bitvector** of a
   Cayley group's connection set. Move = single bit-flip (toggle one
   inversion-orbit in or out of S). Restricted to vertex-transitive
   graphs.
2. `search/random_regular_switch.py` — hill-climb on near-regular K4-free
   graphs using **2-switch moves** (Brualdi–Ryser). No tabu memory, no
   uphill moves, no restart-from-best.

Cayley tabu plateaued at the GAP catalog frontier; switch hill-climb
gets stuck at α-local-minima with no escape mechanism.

### Q: Why a new tabu?
A: The N=23 frontier is **non-vertex-transitive** (α=6 d=[3,4]). Cayley
tabu literally cannot represent it. The hill-climb switch could in
principle but lacks basin-escape. The new tabu combines the move type
of (2) with the memory + restart machinery of (1), generalised to the
edge space.

---

## Design of `search/switch_tabu.py`

### Q: What's the move-table everyone keeps referring to?
A: Three edge-modifying moves with different preservation properties:

| move | edges Δ | per-vertex degree change | edge-count-preserving? | crosses degree multiset? |
|---|---|---|---|---|
| 2-switch | 0 | all four endpoints fixed | yes | no |
| edge-endpoint move (`utils/edge_switch.random_walk_move`) | 0 | v: −1, w: +1 | yes | only by relabelling |
| edge-bitvec flip | ±1 | both endpoints ±1 together | **no** | **yes (k → k±2)** |

This table lives in the docstring of `search/switch_tabu.py:1` so the
distinctions don't get re-confused. Critical because at N=23 the
frontier is at m=44 or m=45 and our random init is at m=46 — only the
edge-bitvec flip can change m.

### Q: What does `switch_tabu_chain` actually do per iteration?
A: Located at `search/switch_tabu.py` (after the candidate samplers).
Pseudocode:

1. Sample a pool of feasible 2-switches (`_sample_candidates`).
   Pre-filter cheap legality (4 distinct endpoints, new edges absent),
   then K4-test the result.
2. Score every candidate: surrogate path uses `alpha_lb`, exact path
   uses `alpha_bb_clique_cover`, composite path uses both.
3. Apply tabu filter on touched edge ids. Aspiration: a tabu move that
   would improve `best` is accepted anyway.
4. Apply the chosen move, append touched edge ids to the tabu deque,
   update `best`, log (k, m, move_kind, pool_size).
5. If `since_improve >= patience`, **ILS restart**: reset state to
   `_perturb(best, perturb_swaps)` and clear the tabu deque.

Three ranker modes are flagged at the call site: `use_exact_score`,
`composite_score`, default surrogate.

### Q: What's the mixed-operator chain?
A: `switch_tabu_chain_mixed` — same loop, but each iteration samples
both 2-switch candidates *and* edge-bitvec-flip candidates
(`_sample_flip_candidates`), gated by a post-move spread cap. The flip
sampler enforces `(d_max − d_min) ≤ spread_cap` after the toggle. This
is the operator that crosses degree multisets.

### Q: What's logged for diagnosis?
A: `SwitchTabuResult` carries:

- `trajectory` — c_log per accepted move
- `k_trajectory` — number of vertices at min-degree post-move
- `m_trajectory` — edge count post-move
- `move_kind_counts` — {'swap': N1, 'flip': N2}
- `pool_sizes` — feasible candidate count per iter
- `alpha_first_reached` — `{α_value: first_iter_at_which_seen}`

These instruments caught the score-drift, the plateau, and the
fragmentation finding without re-running anything.

---

## The factorial designs

### Q: What was the (operator × basin) 2×2?
A: Run by `scripts/run_n23_factorial.py`. Four cells:

|  | basin correct (warm/k-fixed) | basin random (cold) |
|---|---|---|
| pure 2-switch | (3) warm + (1) k-fixed | n/a |
| mixed + flip | (5) warm-mixed | (mixed) cold |

Result: pure 2-switch + correct basin (warm or k-fixed) sits on / fails
to reach α=6. Mixed cold drifts away from frontier multiset (score
gradient pulls m up). Mixed cap=2 reaches α=6 only by drifting to m=68
(wrong c_log). The factorial isolated **operator works, score-as-
descent is wrong, basin matters**.

### Q: What was the (score type × top-K) 2×2?
A: Run by `scripts/run_n23_composite.py`. Four cells, 8 seeds each:

|  | K=6 | K=60 |
|---|---|---|
| surrogate (α_lb) | 7/8 find α=7 | 5/8 |
| composite (exact α, α_lb) | **8/8** | 7/8 |

Median iter to α=7: composite K=6 = 150, surrogate K=60 = 648.
Wall-clock per chain: 4.6s, 9.3s, 9.5s, 9.4s respectively.

The K-confound ("K=6 was structurally underpowered") was refuted —
K=60 is *worse*, not better.

---

## Empirical findings

### Q: Is there really a plateau at α=9?
A: Yes. `scripts/diag_n23_plateau.py` enumerates every feasible 2-switch
from a (m=45, k=2) init and scores each.

```
exact-α distribution at α=9 init:
  α=8:    58  (  4.3%)   ← improvers
  α=9:  1284  ( 94.3%)   ← plateau
  α=10:   20  (  1.5%)
```

94.3% of all moves leave α unchanged. This is the mechanism that breaks
exact-α-only ranking (random walk on the plateau).

### Q: Is α_lb signal or noise?
A: Signal. The cross-tab at α=9 init:

```
exact \ α_lb     α_lb=8    α_lb=9
α=8 (improver)     58        0
α=9 (plateau)     351      933
```

α_lb has **100% recall on improvers** (every improving move scores
α_lb=8). Precision at top of the α_lb=8 bucket is ~14% (58 / 409),
which is 3.3× over the uniform 4.3% baseline. Real signal, low
precision.

### Q: Why is composite K=6 better than composite K=60?
A: Both compute the same exact-α and α_lb on every candidate. Both sort
by (exact α, α_lb). Difference: K=6 restricts the post-aspiration
selection window to the 6 best-ranked; K=60 picks argmin over the whole
pool. K=60 is *strictly greedier* — always picks the best descent
move — and that greediness fails on the α=8 plateau.

The mechanism: at most α=8 states, **all 60 candidates are tied at
α=8**, so K=60 picks based on tiny α_lb differences (effectively a
deterministic walk through the plateau). K=6 forces the chain to
accept moves from a smaller, more variable pool, giving useful
plateau-wandering. The "noise" of K=6 is exactly what lets it wander
to a different α=8 state with α=7 neighbors.

### Q: How did we validate the plateau finding?
A: `scripts/diag_n23_recursive_plateau.py` runs the composite chain
until α=7 is reached, then enumerates from that state. Across 4 seeds:

| seed | α=7 plateau | α=8 worse | **α=6 improvers** |
|---|---|---|---|
| 0 | 140 | 1227 | **0** |
| 1 | 191 | 1180 | **0** |
| 2 | 36 | 1325 | **0** |
| 3 | 138 | 1246 | **0** |

Every α=7 state the chain reaches has zero α=6 improvers in its
2-switch neighbourhood. The recursion from α=9 → α=8 (4.3% improvers)
**does not extend** to α=7 → α=6 (0% from reached states).

### Q: Maybe budget? Did you try longer?
A: Yes. Single chain, composite K=6, 8000 iters from random init:

- Best α = 7 (never α=6)
- Trajectory: 27 visits to α=9, 7818 to α=8, 156 to α=7
- 132 ILS restarts, 1 aspiration

10× budget didn't help. Budget is not the blocker.

### Q: Is α=6 even reachable via 2-switch from any α=7?
A: Yes — but not from the α=7 states the tabu reaches. Enumerating
from the SAT (m=45, k=2) α=6 graph itself:

```
2-switch neighbourhood of SAT α=6:
  α=6:    34  (  2.4%)
  α=7:  1410  ( 97.6%)   ← 1410 distinct α=7 states are 1-hop away
  worse:   0
```

So α=7 ↔ α=6 connectivity is dense — there's a 1410-state α=7
sub-basin adjacent to SAT α=6. The tabu's 156 α=7 visits land in a
**different** region of the α=7 plateau. The plateau is fragmented.

### Q: Could a better tiebreaker than α_lb help?
A: Yes, dramatically — for ranking, not for fixing the plateau. At
α=9 init:

| ranker | top-6 hits | top-20 | top-60 | top-100 |
|---|---|---|---|---|
| α_lb | 0/6 (0%) | 2/20 (10%) | 6/60 (10%) | 16/100 (16%) |
| **E_max** | **6/6 (100%)** | 17/20 (85%) | 34/60 (57%) | 46/100 (46%) |

E_max (exact hard-core E[|I|] from `scripts/run_rung2_exact_hardcore.py`)
is a deterministic, much higher-precision ranker than α_lb. Cost:
~10ms/candidate at N=23.

But — E_max ranks the *current pool* better. It cannot manufacture
improvers when the current state has zero α=6 neighbours, which is
the actual blocker at α=7.

---

## Architectural diagnosis

### Q: What's the integrated reading?
A: The descent has three tiers at N=23:

1. **α=9 → α=8**: easy. 4.3% improvers. Median 1 iter with composite.
2. **α=8 → α=7**: plateau-walk-with-improvers-in-pool. Most α=8 states
   have zero α=7 neighbours, but enough are 1-hop adjacent that random
   sampling stumbles through them. Median 150 iters with composite K=6.
3. **α=7 → α=6**: plateau-walk where most α=7 states are 0-improver
   dead ends and the α=6-adjacent α=7 sub-basin is small and far. Not
   found in 8000 iters.

The barrier is **not** ranking quality. E_max would be a free win for
faster descent at tier 1 and 2 but cannot solve tier 3, which is a
*navigation* problem on a fragmented plateau.

### Q: What kinds of method would solve tier 3?
A: Three plausible directions:

1. **Multi-hop ranker**: a score that estimates "best α reachable from
   this state in h hops" rather than "α of this state". A GNN with
   message-passing depth h is exactly this. The cavity-decay argument
   in `docs/theory/REGULARITY.md` says 3–4 layers gives access to the
   neighbourhood structure that determines α.
2. **Mixed operator with constrained region**: 2-switch + edge-bitvec
   flip with `|m − m_init| ≤ 1` so the chain can cross to the other
   frontier multiset (m=44, k=4) without drifting to m=68. Prevents
   the score-drift seen in unconstrained mixed cap=2 runs.
3. **Annealing-style acceptance**: explicit β-temperature on plateau
   moves. Currently stochasticity comes from K-size + pre-sort
   shuffle + ILS perturb, none independently tunable. β makes the
   exploration/exploitation tradeoff explicit and would let us test
   whether plateau navigation is conquerable by annealing alone before
   investing in a GNN.

### Q: What does this say about scaling to N=30+?
A: The N=23 validation, intended to confirm the method works, instead
identified its limit. The method finds α=7 reliably and α=6 not at all.
At N=30 the plateau structure is plausibly worse (more states, more
fragmentation), so the same machinery scaled larger won't get us there.
Whatever fixes tier 3 at N=23 (multi-hop signal, constrained mixed
operator, annealing) is the ingredient that makes the method scale.
Without it we have a fast α=7-finder, not a frontier-finder.

---

## What we did NOT do

- **N=30 plateau diagnostic**: deferred. The user's priority was
  "make sure the method works at N=23 first". It doesn't fully work,
  so generalisation check is moot until tier 3 is fixed.
- **False-positive structure of α_lb**: deferred. Only useful as
  GNN architectural prior; defer until a GNN is being built.
- **E_max wired into the chain as a tiebreaker**: benchmarked
  standalone (top-K precision) but not integrated as a fifth
  factorial cell. Easy bolt-on (one flag in the composite branch)
  if budget allows.
- **Annealing β acceptance**: discussed but not implemented.

---

## Files

| path | role |
|---|---|
| `search/switch_tabu.py` | core: `switch_tabu_chain`, `switch_tabu_chain_mixed`, `SwitchTabuSearch`, candidate samplers, multiset init, k/m/pool/alpha_first_reached instrumentation |
| `scripts/run_switch_tabu.py` | initial multi-N (17, 20, 22) runner with cold/warm modes |
| `scripts/run_n23_factorial.py` | (3) warm + (1) k-fixed + (mixed cap=1) + (mixed cap=2). Operator × basin design |
| `scripts/run_n23_ablation.py` | surrogate vs exact vs wider-K, plus warm-mixed cap=2 |
| `scripts/run_n23_composite.py` | (score × K) factorial, 8 seeds each |
| `scripts/diag_n23_plateau.py` | full enumeration of 2-switch neighbourhood at α=9 init |
| `scripts/diag_n23_recursive_plateau.py` | enumeration at α=7 reached state (4 seeds) |

The chain entry points are pure functions — anything that builds an
adjacency matrix and a `np.random.Generator` can drive them. The
`Search` subclass plugs into base.py for graph_db persistence; not used
in the diagnostic runs above (we wanted the raw chain results, not the
top-k filtered SearchResults).
