# P(17)-lift optimality: a formalizable sub-claim

## Motivation

Empirically, every Cayley construction found by tabu at N ∈ {17, 34, 51, 68, 85}
achieves exactly c = 0.6789 = c(P(17)) and no less. If we can prove that
*no* Cayley graph on 17k vertices achieves c < c(P(17)), then breaking the
Paley floor requires leaving the Cayley / vertex-transitive world. Unlike
the full K₄-free conjecture, this is a finite question for each k and
admits exhaustive verification for small k and tractable restricted proofs
for the general statement.

## Setup

- `P(17) = Cay(Z_17, QR_17)` where QR_17 = {1,2,4,8,9,13,15,16} (the eight
  nonzero quadratic residues mod 17).
- `α(P(17)) = 3`, `d(P(17)) = 8`, so
  `c(P(17)) = 3·8 / (17·ln 8) = 24 / (17·ln 8) ≈ 0.67894`.
- **The k-lift** of P(17): disjoint union of k copies
  `G_k = k · P(17) = Cay(Z_k × Z_17, {0_k} × QR_17)`.
  When `gcd(k, 17) = 1` this is a Cayley graph on `Z_{17k}` via CRT; the
  connection set in `Z_{17k}` is the 2·QR_17 coset (under the CRT map).
  - `|V(G_k)| = 17k`, `α(G_k) = 3k`, `d_max(G_k) = 8`,
    `c(G_k) = (3k)(8) / (17k · ln 8) = c(P(17))`.

## Conjectures

Let `CayMin(Γ)` denote the minimum of `c` over K₄-free Cayley graphs on
group `Γ`.

**Conjecture A** (cyclic).
For every `k ≥ 1` with `gcd(k, 17) = 1`,
  `CayMin(Z_{17k}) = c(P(17))`
and the minimum is attained by the k-lift.

**Conjecture B** (any group).
For every group `Γ` of order `17k` with `gcd(k, 17) = 1`,
  `CayMin(Γ) ≥ c(P(17))`.

**Conjecture C** (vertex-transitive).
Every K₄-free vertex-transitive graph on 17k vertices has c ≥ c(P(17)).

Strength: A ⊂ B ⊂ C. A is the easiest. C is the strongest finite-family
statement short of the full open conjecture. Current evidence (tabu):

- `k = 1..5` (N = 17, 34, 51, 68, 85): tabu finds c = 0.6789 every time,
  no sub-Paley Cayley construction discovered. **Upper-bound side of A
  confirmed** for k ∈ {1,...,5}; lower bound requires proof.

## What would need to be true for A/B/C to be false

If there were a Cayley graph `Cay(Γ, S)` of order 17k with c < 0.6789,
necessarily K₄-free, it would:

- Have `α(G) · d_max(G) < 17k · ln(d_max(G)) · 0.6789`.
- Not be the k-lift of P(17) (since the lift attains equality).
- Have `|S|` either less than 8 (and `α` very small) or greater than 8
  (and `α` smaller relative to d).

Tabu has searched this space at k ≤ 5 and turned up nothing, so any
counter-example to A is at least "not findable by 1-flip Hamming-1 local
search with random restarts."

## Proof strategies

### Exhaustive enumeration (works for small k and cyclic case)

`Cay(Z_n, S)` with `S = -S ⊆ Z_n \ {0}`. Number of symmetric subsets:

- `n = 17` : 2⁸ = 256
- `n = 34` : 2¹⁷ = 131 072
- `n = 51` : 2²⁵ ≈ 34 M
- `n = 68` : 2³³ ≈ 8.6 G

So k ≤ 2 is trivially exhaustive; k = 3 is borderline (needs orbit
reduction under (Z_n)* and a fast K₄ reject); k ≥ 4 requires a smarter
search. For dihedral / non-abelian groups of order 17k, the state spaces
are larger (D_17 at k=2 has 2²⁵ symmetric subsets) and exhaustive
enumeration is out past k=1.

### Eigenvalue / character bounds (Hoffman direction)

For Cayley graphs on abelian Γ, the eigenvalues of `Cay(Γ, S)` are the
character sums `λ_χ = Σ_{s ∈ S} χ(s)` over the characters χ of Γ. The
Hoffman bound gives

  `α(G) ≤ N · |λ_min| / (d + |λ_min|)`

which is an *upper* bound on α. That's the wrong direction for our
conjecture — we want `α ≥ something`. So Hoffman alone cannot prove
A/B/C; it can only rule out Cayley graphs with α too large.

What could work: combine Hoffman with a K₄-free **upper bound** on `d_max`
(if `G` has a K₄-free Cayley structure and small Hoffman α-bound, then
the combination pinches c). This is specific to Cayley / vertex-transitive
settings and has been used by Mantel-style arguments.

### Lovász theta + vertex-transitive symmetry

For vertex-transitive graphs,
  `α(G) = N / θ̄(G) = θ(G)` (Lovász),
so the SDP computes α exactly. Unfortunately θ is still expensive for
large N. But for *the family* of Cayley graphs on Z_{17k} with `|S| ≤ 16`
(say), we could enumerate and compute θ for each, which is polynomial.

### Flag algebra (Razborov, out of current session scope)

Certified lower bound on c for vertex-transitive K₄-free graphs via
SDP over subgraph densities, restricted to the vertex-transitive
simplex. Would prove Conjecture C directly. Weeks of build.

## Plan of attack (this session)

1. **k = 1 (N = 17):** exhaustive, 256 subsets. Sanity check that P(17)
   (and its Paley cousins under the (Z_17)* action) hit c = 0.6789 and
   everything else is worse or K₄-full. `scripts/verify_p17_lift.py`.

2. **k = 2 (N = 34, cyclic):** exhaustive over Z_34, 2¹⁷ symmetric
   subsets, ~minutes with the K₄ reject + clique-cover α. If the k-lift
   of P(17) is the unique min (modulo automorphism), Conjecture A is
   confirmed for k=2.

3. **k = 2 (N = 34, dihedral D_17):** 2²⁵ subsets, exhaustive is out.
   Run tabu with large restart budget (done already — no sub-0.6789 hit
   at N=34) and treat as empirical evidence for B.

4. **k = 3 (N = 51, cyclic Z_51):** orbit-reduced enumeration. 2²⁵
   total; (Z_51)* has φ(51) = 32 units so ~10⁶ orbit reps. Feasible
   overnight.

5. **Beyond:** flag-algebra build if results from 1-4 are clean.

## Expected outcomes

Most likely: A is verified exhaustively for k ∈ {1, 2, 3}, giving a
finite but substantive confirmation that cyclic Cayley graphs on small
17k do not beat Paley. B and C require restricted SDP / flag-algebra
work beyond this session.

Low-probability but high-value: an exhaustive search at k=2 or k=3
turns up a Cayley graph with c < c(P(17)). That would be a new
construction immediately, and tabu's 0.6789 ceiling is a search-budget
artifact, not a structural wall.

## Results (2026-04-21)

Run via `scripts/verify_p17_lift.py --n {N}`.

### k = 1 (N = 17, Z_17)

- 256 symmetric subsets total → 36 orbits under (Z_17)*-action.
- 15 orbits yield K₄-free Cayley graphs.
- **Unique minimizer**: S = {1,2,4,8,9,13,15,16} (the QR_17 set, P(17)).
  α = 3, d_max = 8, c = 0.678915.
- **Conjecture A verified at k = 1**: P(17) is the strict minimum c
  among cyclic Cayley graphs on Z_17.

### k = 2 (N = 34, Z_34)

- 131,072 symmetric subsets total → 16,460 orbits under (Z_34)*.
- 1,338 orbits yield K₄-free Cayley graphs.
- **Unique minimizer** (up to (Z_34)* action): S = {2,4,8,16,18,26,30,32}.
  α = 6, d_max = 8, c = 0.678915. This is exactly the CRT image of
  {0}×QR_17 in Z_34 — the k=2 lift of P(17).
- **Conjecture A verified at k = 2** (cyclic case): no cyclic Cayley
  graph on Z_34 beats P(17)'s c.
- Total runtime: ~5 s (single-threaded).

### k = 3 (N = 51, Z_51)

- 33,554,432 symmetric subsets total → 2,105,419 orbits under (Z_51)*
  (|(Z_51)*| = 32).
- 41,162 orbits yield K₄-free Cayley graphs.
- **Unique minimizer**: S = {9, 15, 18, 21, 30, 33, 36, 42}, the CRT
  image of {0}×QR_17 in Z_51 (the k=3 lift).
  α = 9, d_max = 8, c = 0.678915.
- **Conjecture A verified at k = 3** (cyclic case).
- Runtime: 34 min (single-threaded, inline lex-min orbit pruning).

### Open

- k = 2, D_17: 2²⁵ subsets, exhaustively verified 2026-04-21 via
  `scripts/verify_dihedral.py` — unique c-minimizer = rotation-only
  k=2 lift of P(17) at 0.6789. Closes Conjecture B at k=2 (combined
  with cyclic Z_34).
- k = 3, order 51: **no non-abelian group exists** (|Aut(Z_17)|=16,
  3∤16, so Z_17⋊Z_3 is trivial and the only group is cyclic Z_51;
  GAP confirms `NrSmallGroups(51)=1`). Cyclic Z_51 is already
  exhaustively verified, so B at k=3 is closed.
- k ≥ 4 (cyclic): 2³³+ subsets — feasible with multiprocessing +
  tighter K₄ reject, probably hours.

### Upshot

At k ∈ {1, 2, 3}, the ceiling c = 0.6789 we see in tabu is NOT a
search-budget artifact. It is the strict minimum over the full
exponential space for every group of order 17k at these k (cyclic
Z_n exhaustively at all three, plus D_17 at k=2 and the triviality
argument at k=3). At each of N = 17, 34, 51 the unique minimizer
(up to the relevant Aut-action) is exactly the k-lift of P(17).
Breaking below 0.6789 at any of these N requires a non-Cayley /
non-vertex-transitive construction. This is the first lower-bound
proof of Paley-optimality in any specific family for our problem.
