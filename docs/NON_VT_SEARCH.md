# Non-VT Search — What Was Tried and What Was Learned

**Status: closed direction** (as of 2026-04-22). This document records why non-VT was
pursued, every attack that was tried, and the evidence that caused this direction to be
shelved in favour of rigorous Cayley/circulant characterisation.

---

## 1. Why non-VT was the natural target

The `c_log` conjecture asks whether every K₄-free graph on N vertices satisfies

$$c_{\log}(G) = \frac{\alpha(G)\,d_{\max}}{N \ln d_{\max}} \;\geq\; c^* > 0$$

for a universal constant c*. The 30-year computational benchmark is P(17) at c ≈ 0.6789.

The theoretical argument for non-VT was clean: for vertex-transitive (VT) graphs,
`θ(G) = α(G)` exactly (Lovász), so the Lovász theta SDP gives no slack. The best
any VT graph can achieve is constrained by this spectral ceiling. Non-VT graphs,
by contrast, can in principle have `α < θ`, which means the SDP's bound is loose and
lower c values are not ruled out structurally. Two small-N SAT results — N=14 and N=15,
where the certified optimum is non-VT and beats the best Cayley by roughly 0.001–0.002 —
gave empirical support to the idea.

The three known extremal "bases" all live in VT/Cayley space:

| N  | Construction            | c_log  | Structure                           |
|----|-------------------------|--------|-------------------------------------|
| 17 | Paley P(17)             | 0.6789 | SRG(17,8,3,4), 3 eigenvalues        |
| 19 | Cubic residues CR(19)   | 0.7050 | 3-class association scheme, 4 eigs  |
| 22 | Circulant C(22;S)       | 0.6995 | Non-algebraic, ~10 eigenvalues, small Aut |

Every larger-N record in the database is a blowup of one of these three. The natural
hypothesis: a non-VT construction might dip below 0.6789 while VT is ceiling-locked.

---

## 2. Attacks that were tried

### 2a. SRG catalog screen (Exp 29)

Screened McKay's full strongly-regular graph catalog for K₄-free members with low c_log.
Result: 0 hits below P(17). The SRG family is too constrained by the parameter conditions
for K₄-freeness to yield anything competitive.

### 2b. Asymmetric lift tabu at N=34 (Exp 28)

Ran the full tabu search over the 561-bit adjacency bitvector at N=34, seeded from
`2·P(17)` (the best-known VT construction). The search could not escape the `2·P(17)`
basin: it is a strict local minimum under 1-flip moves. Diversified restarts landed in
worse basins. Result: null.

### 2c. LLM evolution — claude_search (110 evaluations, 2026-04-22)

The `claude_search/` component ran a Claude Code agent in a loop, writing and evaluating
`construct(N) → edge_list` functions targeting 10 non-VT families from the literature
(`NON_VT_CATALOG.md`). The agent worked through catalog entries and mutations over 110
evaluations.

**Final state:**

| Family              | Best c  | Attempts | Status        |
|---------------------|---------|----------|---------------|
| core_periphery      | 1.3049  | 58       | STALE         |
| random_process      | 1.6320  | 9        | —             |
| polarity            | 1.7264  | 12       | —             |
| asymmetric_lift     | 2.4377  | 9        | —             |
| structure_plus_noise| 2.4349  | 1        | underexplored |
| voltage_partial     | 2.6268  | 2        | underexplored |
| srg_perturbed       | 2.6945  | 1        | underexplored |
| invented            | 2.8298  | 2        | —             |
| crossover           | 2.8410  | 1        | —             |
| two_orbit           | 3.1534  | 3        | —             |
| perturbed_paley     | —       | 0        | UNEXPLORED    |
| sat_seeded          | —       | 0        | UNEXPLORED    |

**Overall best: c = 0.9593** (gen_037, random d-regular + K4 repair at N=30).
This is 41% above the 0.6789 target. No candidate in 110 evaluations came close.

### 2d. Voltage covers (considered, not systematically run)

Double and triple covers of P(17) parameterised by edge voltages (2^68 signings mod
gauge equivalence). Gauge + Aut(P(17)) reduce the space, but the number of equivalence
classes was not computed; the family was explored conceptually by the LLM-evolution
agent (via `voltage_partial`) with no competitive results.

---

## 3. Why the direction was closed

**Empirical:** The Cayley vs non-Cayley frontier plot (produced from the full graph DB)
shows non-Cayley graphs are 0.2–1.0 c_log units worse than the Cayley frontier at every
N from 16 to 100. The N=14, 15 non-VT wins are genuine but marginal (Δc ≈ 0.001) and
do not extend to larger N. The non-Cayley "frontier" in the DB largely reflects what
random/greedy methods happen to produce, not structured constructions.

**Structural:** To beat 0.6789 at N=30 with d_max=7, you need α ≤ 5. The LLM-evolution
agent was consistently achieving α ≥ 8 at N=30 after 110 iterations. The gap is 3 units
in α, not a rounding issue.

**ML methods do not close the gap:** The Parczyk et al. (2023), Mehrabian et al. (2024),
and FlowBoost papers collectively establish that learning-based methods give
*parity with tabu* on construction problems of this shape at best — not qualitative wins.
The specific failure mode here is that the problem requires finding one good graph in a
huge discrete space, and the right measure is max-over-distribution, not
expected-return. RL objectives are mismatched for this. GFlowNets and FlowBoost show
mean-shift-not-max-shift in practice (basin refinement, not basin escape).

**Seed problem is the real bottleneck:** The basin-escape issue at N=34 (2·P(17) is a
strict local min under 1-flip) and the LLM-evolution null results together establish that
the blocker is not "search is slow" but "there are no known structural parameterisations
of non-VT graph families that place seeds near a sub-0.6789 basin." This is a structural
graph theory question, not a compute or ML question. Current methods cannot generate
useful seeds without structural insight that does not yet exist.

---

## 4. What N=14 and N=15 actually tell us

The certified-optimal graphs at N=14 and N=15 are non-VT and beat the best Cayley by
roughly 0.001. These are genuine small-N non-VT wins, but they are special: they arise
because the c_log minimiser at small N needs specific irregular degree sequences
(degree-spread ≤ 1 but not exactly regular) that SAT can find exhaustively but Cayley
constructions cannot realise. They do not represent a family that extends to large N.
The SAT-certified frontier at N ≤ 20 confirms Paley P(17) is the global optimum at
N=17 — not just the VT optimum. Non-VT does not improve on Paley at N=17.

---

## 5. What the empirical evidence says about the Cayley ceiling

The Cayley frontier plot across N=10–100 is flat: it oscillates in the band [0.68, 0.93],
touching 0.68 at every multiple of 17 (and somewhat higher at 19k and 22k), and
returning to 0.8–0.9 elsewhere. It does not trend upward with N. This flatness is the
main empirical signal: the P(17)-lift construction preserves c_log exactly under blowup
(by construction), and no other Cayley family breaks below 0.6789.

This supports the working conjecture that:

- c* = 0.6789 is the infimum of c_log over all K₄-free graphs (the conjecture holds
  with this specific constant)
- The infimum is realised (or approached) by the Paley family and its lifts
- Any counterexample must be non-VT at large N, in a family with no currently known
  structural parameterisation

---

## 6. Current research direction

Following the closure of non-VT attacks, focus has shifted to:

1. **SAT-over-circulants** — certify the best circulant at each N up to ~300 via a
   CP-SAT model over connection sets (O(N) bits, not O(N²)). Running now on cluster.

2. **Conjectures A/B/C** — prove that P(17)-lift is the unique minimiser over all
   Cayley graphs on 17k vertices (A = cyclic, B = all groups, C = all VT). Verified
   exhaustively at k=1,2,3 for A and k=2 for B (both Z_34 and D_17). Theoretical
   proof for general k is open and non-trivial.

3. **Publication as a frontier/closure result** — the combination of certified optimality
   at N ≤ 20, exhaustive Conjecture B at k=2, and the certified Cayley frontier to N≥300
   is a coherent publishable contribution independent of whether the conjecture is resolved.

Non-VT remains theoretically possible as the locus of any counterexample. It is
*computationally closed* with current methods.
