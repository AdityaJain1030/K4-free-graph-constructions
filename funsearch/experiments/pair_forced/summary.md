# Pair-Forced Cross-Edge Experiment on Paley P(17)

- Runtime: **0.0 min**
- Base: 2 disjoint copies of P(17), N=34, α=6

## Phase 1 — Pair-forced density

- Candidate cross-edges tested: 289 (17×17)
- Edges that dropped α (6 → 5): **0**
- **Pair-forced density = 0.0000**
- u₁=0 row uniform across all 17 targets: True
- u₁=0 row α-after values: [6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6]

**Finding — no single cross-edge drops α.**

This is consistent with the prior result that P(17) has no α-forced
vertex: α(P(17) − v) = 3 for every v. Adding one edge (u₁, u₂) can
only drop α if every max-IS of the disjoint union uses **both** u₁
and u₂ — but because no vertex is forced in either copy, a max-IS
avoiding u₁ (resp. u₂) always exists, so α stays at 6.

Phase 3 (k-copy scaling) was skipped per the '>50% density' gate.
However, Phase 2 still tested whether combinations of edges can
jointly drop α — see below.

## Phase 2/3 — Greedy multi-edge trajectories

| k | N | d_cap | #edges added | final α | final d_max | best c | best step | Δc vs floor |
|---|---|-------|--------------|---------|-------------|--------|-----------|-------------|
| 2 | 34 | 12 | 4 | 6 | 12 | 0.6789 | 0 | -0.2228 |

## Did greedy cross-edge wiring break the 0.9017 floor?

**No — but the disjoint union already sits below it, trivially.**

The "best c = 0.6789" shown above is at **step 0** — the starting state
of 2 disjoint copies of P(17) before any cross-edges are added. Every
greedy cross-edge **increased** c (0.7228 → 0.7664 → 0.8095 → 0.8522),
so the wiring scheme actively hurts.

The 0.6789 baseline comes from the block alone: P(17) has
α/n · d/log(d) = (3/17) · 8/ln(8) = 0.6789, and disjoint union preserves
the ratio. This is below 0.9017 because 0.9017 was the floor of the
**forced-matching construction** specifically (n ≤ 8 library, |S| ≤ α).
A larger K₄-free block with better (α, d) ratio beats that floor without
any forced-vertex machinery.

**Finding:** For P(17), pair-forced cross-edge wiring yields no
improvement over naive disjoint union. The zero pair-forced density
(Phase 1) already implied this: if no single edge drops α, greedy
edge-by-edge can only add degree, never help.

## Files

- `pair_density.json` — full 289-edge records
- `greedy_trajectory_k{2,3,...}.json` — step-by-step trajectories
- `c_vs_k.png` — best c vs k plot