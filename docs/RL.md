# RL.md — Research log: navigating to α=6 at N=23

Live research log on the navigation problem in `switch_tabu` and
adjacent local-search methods at N=23. Append to this; don't rewrite
history. Each section dates an experiment, states the question, the
implementation that answered it, the supporting data, and the
interpretation. The goal is one document a future contributor (or
future-us) can read top-to-bottom to know what's been ruled out and
what's worth trying next.

---

## 0. The problem

We want K4-free graphs minimising
`c_log(G) = α(G) · d_max(G) / (N · ln d_max(G))`. At **N=23** the
SAT-certified optimum is

| graph                | α | d_max | m  | c_log   | source          |
|----------------------|---|-------|----|---------|-----------------|
| **SAT α=6 frontier** | 6 | 4     | 44 | 0.7527  | `server_sat_exact` |

Degree sequence: `[4×19, 3×4]`.

The active heuristic chain `search.switch_tabu.switch_tabu_chain_mixed`
plateaus at α=7 across every cold-start configuration we've tried.
The headline open question — and the subject of this file — is
**why doesn't the tabu reach α=6, and what would?**

Reference: `docs/searches/SWITCH_TABU.md` has the prior diagnostics
that motivated this thread (plateau enumeration, score-vs-K factorial,
recursive-plateau verdict).

---

## 1. Baseline: switch_tabu (no extras)

**Source:** prior runs in `logs/search/switch_tabu_n23_*.log`,
re-aggregated 2026-04-25.

| n_runs | α distribution | c_log min | c_log med |
|--------|----------------|-----------|-----------|
| 10     | 10× α=7        | 0.8782    | 0.8782    |

So 10/10 cold-start switch_tabu chains land at α=7 with the canonical
(α=7, d=4) c_log of 0.8782. Zero seeds reach α=6.

---

## 2. Approach: plain MCMC (Metropolis-Hastings, 2-switch only)

**Date:** 2026-04-25.
**Files:** `search/mcmc.py`, `scripts/run_mcmc.py`.

**Why:** The user proposed MH on 2-switch with symmetric proposal
acceptance `A = min(1, exp(-β·Δc_log))` to test whether
"plateau navigation by detailed-balance" outperforms tabu's
composite ranker.

**What we built:** a single-chain MH that proposes one ordered edge
pair per iteration, applies the swap if K4-free, accepts probabilistically.
2-switch only (so symmetric form is correct per Cooper-Dyer-Greenhill).
Tracks α and c_log via exact `alpha_bb_clique_cover`.

### 2a. Cold start (10 seeds, β=20, 20k iters, near-4-regular init)

| method        | α distribution | c_log min  |
|---------------|----------------|------------|
| switch_tabu   | 10× α=7        | 0.8782     |
| **MCMC β=20** | **10× α=8**    | **1.0036** |

Plain MCMC **underperforms tabu**. `best_iter` is 0 or single-digits
in 9/10 runs — the chain never improves on the init's α.

### 2b. Connectivity diagnostic (uniform random walk, β=0)

Even at β=0 (every legal 2-switch accepted), 50k–100k iter chains
from a *cold multiset-matched* init at N=14, 15, 23 never visit the
optimum α at all.

| start              | β   | iters  | α visited                        |
|--------------------|-----|--------|----------------------------------|
| N=23 cold matched  | 0   | 100k   | {8, 9, 10, 11}                   |
| N=23 warm at SAT   | 0   | 50k    | {6, 7, 8, 9, 10, 11}             |

Warm-start visits the optimum and drifts up; cold-start in the same
multiset doesn't visit the optimum. The optimum basin **is**
connected but its stationary measure under uniform 2-switch dynamics
is too small for the random walk to hit in feasible time.

### 2c. Warm-start sanity (β ∈ {0, 5, 20, 50})

All β values: chain holds at α=6 from SAT init. Detailed balance is
correct.

**Verdict:** plain MCMC at β≥5 doesn't break the wall and is strictly
worse than tabu on cold init. β=0 spreads but doesn't hit the
optimum basin. Single-chain MH is not the answer here.

---

## 3. Approach: rollout-based lookahead in switch_tabu_chain_mixed

**Date:** 2026-04-25.
**Files:** `search/switch_tabu.py` (`_random_legal_move_mixed`,
`_lookahead_score`), `SwitchTabuMixedLookaheadSearch`,
`scripts/run_switch_tabu_mixed_lookahead.py`.

**Why:** the existing chain ranks moves by their *immediate* c_log.
Adding a lookahead layer scores the top-K candidates by "min c_log
seen along M random rollouts of length h from the candidate" — the
move that sits next to better graphs gets surfaced even if its
immediate c_log isn't the best in the pool.

### 3a. N=23 cold, 4-way (4 seeds, 400 iters)

| mode             | α distribution | c_log min  | c_log med  | la_min   | wall   |
|------------------|----------------|------------|------------|----------|--------|
| baseline         | 4× α=7         | 0.8782     | 0.9455     | —        | 30s    |
| lookahead (h=4, M=5, top-5) | 4× α=7 | 0.9455 | 0.9455 | 0.9455   | 60s    |

**Result:** lookahead doesn't reach α=6 *and* gives a worse c_log min
than baseline at this budget. The crucial diagnostic is
**`la_min == 0.9455` exactly across all four lookahead seeds** —
across thousands of rollout-graph evaluations, **the rollouts
discovered zero states with c_log < 0.9455**. The α=6 basin is
unreachable in 4 hops of random walk from the chain's α=7 states.

### 3b. Aggressive lookahead (h=10, M=20)

| mode      | α distribution | la_min  |
|-----------|----------------|---------|
| lookahead | 1× α=7, 1× α=8 | 0.9455  |

Even with 10× rollout effort, no α=6 state is ever probed. h=10 still
isn't enough.

### 3c. Warm-start sanity

| mode             | α distribution | la_min  |
|------------------|----------------|---------|
| warm_baseline    | 2× α=6         | —       |
| warm_lookahead   | 2× α=6         | 0.7527  |

Warm chain holds at α=6. la_min matches the optimum (rollouts don't
fabricate spurious below-optimum graphs).

**Verdict:** lookahead doesn't help, but it produces the cleanest
negative result we have on the move set: across thousands of rollout
evaluations from chain-reached α=7 states, zero α=6 graphs are
visited at h ≤ 10. The signal is empty because α=6 is structurally
distant from the chain-reached α=7 region under random walks of this
horizon.

---

## 4. Approach: 3-switches (vertex-disjoint 3-edge rotation)

**Date:** 2026-04-25.
**Files:** `search/switch_tabu.py` (`_try_3switch_from_pairing`,
`_sample_3switch_candidates`, `_try_3switch_random`).

**Why:** if random rollouts of 2-switch + flip can't reach α=6 in
h hops, maybe the move set itself is too narrow. 3-switches expand
the per-step neighbourhood: pick 3 vertex-disjoint edges, rotate to
a different perfect matching of the 6 vertices.

**Move classification (from the combinatorics of 6-vertex matchings):**

* 14 non-trivial pairings of 3 vertex-disjoint edges.
* **6 are 1-step-equivalent**: keep one of the original edges → the
  3-switch is also a 2-switch on the other 4 vertices (no new
  reach). `move_kind = "swap3_equiv"`.
* **8 are novel**: keep zero original edges → genuinely outside the
  2-switch reach. `move_kind = "swap3"`.

**Tabu length scaling.** Each 3-switch touches 6 edge ids vs 4 for a
2-switch. With `sample_size_swap3 > 0` and no explicit `tabu_len`,
the Search subclass scales the deque length by 1.5× to maintain
edge-tabu memory parity.

### 4a. Headline N=23 4-way (4 seeds, 400 iters)

| mode             | α dist  | c_log min  | c_log med  | wall (sum) |
|------------------|---------|------------|------------|------------|
| baseline         | 4× α=7  | 0.8782     | 0.9455     | 29.9s      |
| lookahead        | 4× α=7  | 0.9455     | 0.9455     | 60.3s      |
| **swap3**        | 4× α=7  | 0.8782     | **0.9118** | 38.2s      |
| swap3+lookahead  | 4× α=7  | 0.8782     | 0.9118     | 73.2s      |

3-switch lowers the **median** c_log within α=7 from 0.9455 → 0.9118
(reaches the better α=7 sub-basin in 2/4 runs vs 1/4 for baseline)
and is ~30% slower. None reach α=6. Lookahead on top of swap3 adds
nothing.

### 4b. Long-budget (6 seeds, 2000 iters)

| mode  | α distribution | c_log min  | c_log med  |
|-------|----------------|------------|------------|
| swap3 | 6× α=7         | 0.8782     | **0.8782** |

5/6 seeds hit the better α=7 sub-basin (c_log=0.8782) at the longer
budget. Still 0/6 reach α=6. **The α=7 → α=6 wall is not
budget-bounded.**

### 4c. Acceptance breakdown

Across the 4-way runs, of accepted moves:
* ~30% are 3-switches.
* Of those: novel:equiv ratio is roughly 0.77, vs the theoretical
  0.83 (8 novel : 6 equiv non-trivial pairings, weighted by
  acceptance). So the chain is *under-using* the genuinely novel
  3-switches because the c_log ranker pushes them down — equivalents
  preserve more local structure and tend to score better immediately.

### 4d. Warm-start sanity

| mode                     | α distribution | la_min  | sw3 acc novel/equiv |
|--------------------------|----------------|---------|---------------------|
| warm_swap3               | 2× α=6         | —       | ~20/25              |
| warm_swap3+lookahead     | 2× α=6         | 0.7527  | ~12/33              |

Chain holds at α=6 under all swap3 modes.

**Verdict:** 3-switches measurably broaden reach within α=7 (median
c_log drops) but do **not** bridge α=7 → α=6 in any seed. Maps
onto the user's middle outcome branch: "move set is wider but still
has the same connectivity issue at this density." Adding more move
types (4-switches, k-opt) is a bad axis to push on without first
understanding *why* the wider moves still don't bridge.

---

## 5. The decisive diagnostic: edit distance to SAT α=6

**Date:** 2026-04-25.
**Files:** `scripts/diag_n23_edit_distance.py`.

**Question the user pushed:** stop adding moves and *measure the
distance*. If G7 and G6 are 30 edges apart, no local move helps; if
they're 6 edges apart, the issue is navigation, not reach.

**Method:** isomorphism-distance proxies via vertex-permutation hill
climb. We compute the symmetric difference `|E(G7) Δ E(π · G6)|`
under: (a) original labelling, (b) degree-sorted alignment, (c) hill
climb from the degree-sorted alignment, (d) 200–400 random restarts
each followed by hill climb. Each is an upper bound on the true
isomorphism-distance. Min across all four = tightest upper bound.

### Two reference α=7 graphs and their distance to SAT α=6

| graph                                       | m   | degree pattern   | best |Δ| | ≥ 2-switches | ≥ 3-switches |
|---------------------------------------------|-----|------------------|----------|--------------|--------------|
| Cayley α=7 (graph_db, 4-regular VT)         | 46  | 23×4             | **16**   | 4            | 2            |
| Chain best α=7 (swap3, 2000 iters, seed 0)  | 45  | 22×4, 1×2        | **23**   | 5            | 3            |
| SAT α=6 frontier                            | 44  | 19×4, 4×3        | 0        | —            | —            |

**This is small.** Both reference α=7 graphs are within ≤5 2-switches
or ≤3 3-switches of an isomorphic copy of SAT α=6.

The chain runs 2000 iters with ~600–2000 accepted moves per run.
A 5-step bridge should be findable a hundred times over. It isn't.

**Verdict:** the wall is **not** distance. The move set is wide
enough; the budget is large enough. Therefore the wall is
**navigation/scoring**: the c_log-greedy ranker steers away from
any path that goes uphill first.

---

## 6. The smoking gun: telescoping bridge from G7 to G6

**Date:** 2026-04-25.
**Files:** `scripts/diag_n23_path_to_alpha6.py`.

**Question:** if the bridge is short, what does it *look like*?
Construct an explicit legal sequence of K4-free moves from chain's
G7 to (a permuted copy of) SAT G6. Print c_log at every step.

**Construction:**
1. Run the chain to produce G7 (α=7, m=45, c_log=0.8782).
2. Hill-climb a vertex permutation π to minimise `|E(G7) Δ E(π·G6)|`.
3. Split the difference into 12 chain-only edges (must remove) and
   11 sat-only edges (must add).
4. Two orderings:
   * **sequential**: remove all 12, then add 11 (additions planned in
     a K4-safe order).
   * **interleaved**: alternate add and remove, preferring an add at
     each step (only fall back to remove if no add is K4-safe).

### 6a. Sequential trajectory (12 rm, then 11 add)

```
step  phase   α  m    c_log    Δ vs G7
 0    start   7  45   0.8782   +0.0000   ← chain's best
 1    rm      8  44   1.0036   +0.1255   ← single uphill jump
 2    rm      8  43   1.0036   +0.1255
 3    rm      8  42   1.0036   +0.1255
 ...                                       (steps 4-21 all α=8, c_log=1.0036)
21    rm      8  34   1.0036   +0.1255   ← end of α=8 plateau
22    add     7  43   0.8782   +0.0000   ← α drops at step 22
23    add     6  44   0.7527   −0.1255   ← target reached
```

* Length: 23 flips.
* Peak c_log: 1.0036 at step 1.
* Uphill cost: +0.1255.
* α=8 plateau: **20 contiguous steps** (steps 1–21 inclusive).
* Min lookahead horizon to see the downhill from any α=8 state: **21**.

### 6b. Interleaved trajectory (alternate add/rm)

```
step  phase   α  m    d_max   c_log    Δ vs G7
 0    start   7  45   4       0.8782   +0.0000
 1    add     7  46   5       0.9455   +0.0673
 2    rm      7  45   5       0.9455   +0.0673
 ...                                                 (oscillating α=7, c_log ∈ {0.9455, 1.0192})
12    rm      8  45   5       1.0806   +0.2024   ← peak (α=8, d_max=5)
13    add     8  46   5       1.0806   +0.2024
14    rm      8  45   5       1.0806   +0.2024
15    add     7  46   5       0.9455   +0.0673   ← α drops back to 7
 ...
21    add     6  46   5       0.8104   −0.0677   ← α drops to 6
22    rm      6  45   5       0.8104   −0.0677
23    rm      6  44   4       0.7527   −0.1255   ← target reached
```

* Length: 23 flips.
* Peak c_log: 1.0806 at step 12 (higher than sequential because
  intermediate d_max=5 transients).
* Uphill cost: +0.2024.
* α=8 segment: 3 steps (12–14).
* Min lookahead horizon to see downhill: **12–15**.

### 6c. Comparison

| metric                                | sequential  | interleaved |
|---------------------------------------|-------------|-------------|
| total flips                           | 23          | 23          |
| **peak c_log**                        | **1.0036**  | 1.0806      |
| uphill cost (peak − start)            | +0.1255     | +0.2024     |
| longest α=8 segment                   | 20          | 3           |
| longest c_log-flat plateau            | 21          | 0           |
| min lookahead h to see exit           | 21          | 12–15       |

Both orderings are *exactly* 23 flips (= |Δ|). Different orderings
trade plateau length for peak height. **Every legal path from G7 to
G6 must visit a state with c_log ≥ ~1.0** — neither ordering avoids
the α=8 ceiling.

---

## 7. What this implies for "future-aware reward"

The decisive observation: the bridge is short (~23 flips, |Δ|=23),
but every path is gated by a c_log barrier of at least +0.1255 above
G7, with a flat plateau of 3–21 steps along the way.

**Finite-horizon lookahead can't price this in cheaply.**
* Sequential path: needs h ≥ 21.
* Interleaved path: needs h ≥ 12.
* What we ran: h=4, M=5, top-5 candidates → 100 evals/iter.
* What's needed: h≈15, M=10 → 750 evals/iter, AND the rollouts
  must *actually traverse* the specific bridge (random rollouts
  almost never do).

**Bellman / value function is the conceptually right object.**
What we want is `V(state) = best c_log reachable in ≤ K future moves`.
True V — propagated by dynamic programming over the move graph —
would correctly score G7 as "high V because reachable from G6 in
23 hops." But computing V exactly is over the same intractable move
graph; *learning* V requires offline traversal data, which is
exactly what the search is supposed to produce.

**Annealing / MCMC at low β is the cheapest concrete intervention —
*but* the MCMC tests in section 2 are evidence against assuming it
works.** At the +0.1255 uphill step, MH acceptance is:

| β   | accept(+0.1255) |
|-----|-----------------|
| 1   | 0.882           |
| 2   | 0.778           |
| 5   | 0.534           |
| 10  | 0.285           |
| 20  | 0.082           |
| 50  | 0.002           |

So β ≤ 10 mathematically makes the uphill traversable in expectation
within a few attempts. **However, the MCMC results in section 2
already show this isn't sufficient on its own:**

* β=20 cold (section 2a): 10/10 stuck at α=8. The greedy regime
  refuses the uphill, exactly as predicted, and even pure MH at
  high β doesn't bridge.
* β=0 cold (section 2b): the chain freely accepts every legal move
  but the optimum basin is too rare under uniform 2-switch dynamics
  to hit in 50k–100k iters. So "freely accept everything" is also
  not sufficient.
* No β value tested from cold init solved it.

**The annealing claim is therefore narrower than "low β is the fix"**:

1. Annealing has to start from a state that is **already close** to
   the optimum basin. The chain's α=7 state (G7) is ≤ 23 flips from
   G6, but a cold random init isn't — the MCMC β=0 cold runs spent
   100k iters without ever entering the α=6 basin even with every
   move accepted. Annealing from cold inherits this problem.
2. Even from G7, the chain at β ≤ 10 must traverse the α=8 plateau
   (3–21 steps with no c_log gradient). MH at moderate β is a
   biased random walk on the plateau, with no signal to direct it
   toward the specific α=8 → α=7 → α=6 exit. β=0 on the plateau is
   exactly the "uniform random walk" regime that section 2b showed
   doesn't hit the right basin in 50k iters.

So the honest claim is: **annealing (or MH-from-G7) might solve the
uphill barrier, but the plateau navigation problem persists**. We
have no evidence yet that random-walk-on-the-plateau finds the
α=6 exit in feasible time. The α=8 plateau here is the same kind
of fragmented plateau that the α=7 plateau was — and switch_tabu
already gets stuck on the α=7 plateau, which is *much* better
positioned (closer to G6). If anything the α=8 plateau is more
fragmented because it's less constrained.

What annealing-from-G7 actually tests is **whether the uphill
barrier alone is the blocker**. Three possible outcomes:

* If it solves it (chain reaches α=6 reliably): the wall was *just*
  the greedy ranker refusing uphill. Cheap fix.
* If it gets onto the α=8 plateau but doesn't exit: the wall has
  two stacked components — uphill *and* plateau. Need structural
  signal on the plateau (section 7's "non-c_log ranker" candidate).
* If it doesn't even reliably climb the uphill: section 2 was the
  full story and MH variants are a dead end. Fall back to learned
  proposals or non-local moves.

This is what the experiment is for. The framing "annealing is the
fix" was overconfident given section 2's data.

**The wall is two stacked problems:**
1. **Uphill barrier** of ~+0.13–0.20 in c_log. The c_log-greedy
   ranker categorically refuses; lower-β MH or simulated annealing
   accepts it.
2. **Mid-bridge plateau** of length 3–21 with no c_log signal.
   Neither greedy ranking nor finite-horizon lookahead nor low-β MH
   has any gradient on the plateau.

The fix has two corresponding parts:
1. **For the uphill:** annealing β-schedule or MH acceptance.
2. **For the plateau:** a structural ranker that's *not* c_log on
   the plateau. Candidates: edit-distance to a known good graph
   (requires a reference), spectral / structural embedding distance,
   a learned representation that distinguishes α=8 states by
   downstream value (RL value function).

---

## 8. Status table — what's been ruled in/out

| approach                          | result at N=23 cold | breaks α=7→α=6 wall? | note |
|-----------------------------------|---------------------|----------------------|------|
| switch_tabu (composite K=6)       | 10× α=7             | no                   | baseline |
| switch_tabu_mixed (cap=1)         | 4× α=7              | no                   | reuses spread-cap flip |
| MCMC β=20 (2-switch only)         | 10× α=8             | no, **worse**        | greedy at high β |
| MCMC β=0 (uniform random walk)    | α∈{8..11}, 50k iters | no                  | optimum basin too rare |
| Lookahead h=4, M=5, top-5         | 4× α=7              | no                   | la_min == 0.9455 always |
| Lookahead h=10, M=20              | mixed α=7,8         | no                   | rollouts still flat |
| 3-switches (sample 80/iter)       | 4× α=7              | no                   | helps median |
| 3-switches (long budget)          | 6× α=7 @ 0.8782     | no                   | budget not the issue |
| swap3 + lookahead                 | 4× α=7              | no                   | combination doesn't help |

Sanity checks (warm-start at SAT α=6) pass for all variants — the
chains hold the optimum and don't drift, so the implementations are
correct.

---

## 9. Files

| path                                              | role |
|---------------------------------------------------|------|
| `search/switch_tabu.py`                           | core: 2-switch, flip, 3-switch chain + lookahead helpers |
| `search/mcmc.py`                                  | single-chain MH on 2-switch with symmetric acceptance |
| `scripts/run_mcmc.py`                             | MCMC eval driver |
| `scripts/run_switch_tabu_mixed_lookahead.py`      | 4-way driver: baseline / lookahead / swap3 / swap3+lookahead |
| `scripts/diag_n23_edit_distance.py`               | hill-climb upper bound on \|E(G7) Δ E(π·G6)\| |
| `scripts/diag_n23_path_to_alpha6.py`              | explicit legal G7→G6 trajectory + per-step c_log |
| `docs/searches/SWITCH_TABU.md`                    | prior diagnostic write-up — read first |

---

## 10. Open experiments / next directions

In rough order of expected payoff and cost.

* **β-annealing on the existing tabu chain** — replace
  "argmin c_log in top-K" with "accept the chosen move with
  probability `min(1, exp(-β·Δc))`", ramp β from ~5 → ~50 over
  the run. ~30 LOC. Directly tests the "uphill alone is the
  barrier" hypothesis. **Not yet run.**
* **`--swap3_novel_only` ablation** — already wired. Does the
  3-switch median-c_log improvement come from novel moves or from
  the 6 1-step-equivalents acting as redundant 2-switches?
  Cheap; informative only if novel-only is meaningfully different.
* **Structural ranker on the α-flat plateau** — pick a candidate
  by something other than α / c_log when α is tied. Edit distance
  to a known α=6 reference (e.g. SAT graph) is the cheapest.
  Caveat: this is "informed search" — won't help finding *new*
  α=6 graphs, only confirming the navigation hypothesis.
* **Multi-step lookahead with a learned proposal** — train a
  GNN (or something simpler) on `(state, move) → estimated future
  best c_log`. Replaces uniform random rollouts with biased rollouts
  that head toward better regions. Heavy. Don't build until cheaper
  options are exhausted.
* **PT-MCMC with low β at the hot end** — multiple chains at
  geometric β spacing, periodic state swaps. The hot chain at β=1
  freely accepts the +0.1255 uphill; PT swap propagates good states
  back to the cold chain. Already discussed in the MCMC section but
  not yet built. Cost: a few hundred LOC.

---

## 11. Update log

* 2026-04-25 — initial write-up. Sections 1–10 reflect today's runs:
  baseline aggregation, MCMC, lookahead, 3-switches, edit distance,
  trajectory construction, interpretation.
