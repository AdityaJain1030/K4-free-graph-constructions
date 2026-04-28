# `CirculantSearch` — intuition, caveats, scope

## What a circulant is

A circulant `C(n, S)` has vertex set `Z_n` and edges `{i, (i±j) mod n}`
for every `j` in a connection set `S ⊆ {1, ..., n/2}`. Every circulant
is **vertex-transitive** and **regular** — degree `2|S|`, or `2|S|-1`
when `n` is even and `n/2 ∈ S`.

That structure is the point: an adversarial graph for the Shearer /
log-d conjecture has to be (approximately) regular — degree irregularity
is what lets local greedy arguments find a big independent set. Enforcing
regularity is hard for SAT / heuristic searches; circulants give it for
free. Vertex-transitivity also collapses α(G): every vertex has the same
local view, so an MIS built greedily from any starting point behaves the
same, and the symmetry lets you reason about α from jump structure
alone.

## Why it's the strongest baseline we have

The whole repo's benchmark — **c ≈ 0.679** — is `P(17)`, the Paley
graph on 17 vertices, which is a circulant with jumps `(1, 2, 4, 8)`
(the quadratic residues mod 17). No SAT run, no metaheuristic, no
LLM-guided search has beaten it. The circulant family is the richest
construction space we can enumerate exhaustively.

Notable results (from the N=8..50 sweep):

| N  | jumps            | d  | α  | c     | Note                               |
|----|------------------|----|----|-------|------------------------------------|
| 17 | (1, 2, 4, 8)     | 8  | 3  | 0.679 | Paley P(17) — global best          |
| 34 | (2, 4, 8, 16)    | 8  | 6  | 0.679 | Almost certainly two disjoint P(17) |
| 47 | (1, 9, 10)       | 6  | 12 | 0.857 |                                    |
| 49 | (5, 12, 13, 17)  | 8  | 11 | 0.866 |                                    |

At N=40..50 the SAT solver can't reach optimality in reasonable time,
so these circulants are the only structured lower bounds on how small
`c` can get in that range.

## What the search actually does

`CirculantSearch._run()` enumerates every non-empty `S ⊆ {1, ..., n//2}`
(or only size-`k` subsets if `connection_set_size=k`), builds `C(n, S)`,
keeps the K₄-free ones, and returns them. The base class scores each by
`c_log = α · d_max / (n · ln d_max)` and keeps the top_k.

Validity (K₄-free) uses `utils.graph_props.is_k4_free_nx` — a bitmask
search over common-neighborhood intersections. α is computed exactly
by bitmask branch-and-bound (`utils.graph_props.alpha_exact`).

## Caveats — read before scaling up

### 1. Combinatorial blowup

There are `2^(n/2) - 1` non-empty connection sets. For `n ≥ 40` this
is huge. An earlier stand-alone enumerator capped it at 5000 random
samples, which **silently truncated** the search — large-N results
from that script were "best of a random subsample," not true bests.
The script has since been deleted; don't reintroduce that pattern
here.

`CirculantSearch` currently enumerates **everything** via
`itertools.combinations`. Fine for `n ≤ 35` or so; for larger `n`
you'll want either:
- `connection_set_size=k` to restrict `|S|`, or
- a smarter sampler (e.g. prefer large-gap `S`, or iterate by multiset
  structure).

### 2. α-approximation pitfalls (historical)

The legacy script used random-greedy to estimate α at `n > 25` and only
recomputed exact α when the *approximate* score crossed a threshold.
Because we want a **small** α, over-estimating α meant the candidate
looked worse than it was and got silently discarded.

`CirculantSearch` does **not** fall into this trap — it always calls
`alpha_exact`. Cost: at `n ≈ 30+` α can get expensive on dense
K₄-free circulants; watch for it if you widen the range.

### 3. Score-sign inversion (historical)

The legacy enumerator printed `score = n · log2(d) / (d · α)`, which
is `1 / (c · ln 2)`. Its "counterexample" marker fired when
`score > 1`, i.e. `c < 1/ln 2 ≈ 1.44` — a loose threshold, not a real
conjecture violation. `CirculantSearch` reports `c_log` directly; no
sign-flipping. Anything claiming a counterexample in old notes below
`c = 1.44` was false-positive noise.

### 4. Known global optima hide in specific constructions

`P(p)` (Paley, prime `p ≡ 1 mod 4`) is always a candidate worth
checking first — `n=17` is the one that wins so far. Other worth-checking
families: *quadratic-residue circulants* at prime `n`, and
*union-of-arithmetic-progression* jumps at composite `n`. If you're
debugging why `CirculantSearch` doesn't recover a known graph, start by
checking whether its jump set is even in the enumeration.

## When to reach for it

- You need a strong, structured candidate at a given `n`.
- You want to populate `graphs/circulant.json` as a benchmark for
  other searches to beat.
- You want ground-truth data at `n ≤ 35` (fast, exhaustive).

## When **not** to reach for it

- Very large `n` without a size restriction — enumeration is infeasible.
- You want irregular or near-regular non-symmetric constructions —
  by definition circulants don't cover that space.
- You're hoping for a counterexample via a radically different
  structure than Paley — the circulant space is well-explored; the
  interesting stuff lives elsewhere (block constructions, SAT-optimal
  frontier extensions, LLM-generated families).

## Open questions

1. At `n = 34`, `jumps = (2, 4, 8, 16)` also hits `c = 0.679`. Is it a
   disjoint union of two `P(17)` copies, or something else? If the
   latter, it's a genuinely new construction worth studying.
2. Does the circulant-best at `n ∈ [25, 35]` match the SAT-verified
   optimum? If it does, that's evidence the extremal graph *is*
   circulant for those `n` — a real structural result.
3. For `n ∈ [40, 100]`, can a restricted enumeration (say `|S| ≤ 6`)
   or a smarter sampler find a circulant with `c < 0.68`?
