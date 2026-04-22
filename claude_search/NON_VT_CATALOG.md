# Non-VT K₄-free construction catalog

Your task is **translation, not invention**. Pick an unimplemented entry,
port it to `construct(N)`, evaluate. Do not invent families. Do not start
from "modify Paley". Every entry here is structurally non-vertex-transitive
by construction — no biasing is needed if you stay faithful.

Mark an entry implemented by writing `candidates/gen_NNN_<entry_tag>.py` and
citing it in the header: `# Catalog: <entry_tag>`. One candidate = one
catalog entry, or one explicit perturbation of an implemented entry.

---

## 1. `er_polarity` — Erdős–Rényi polarity graph ER(q)

**Reference:** Erdős, Rényi, Sós (1966). "On a problem of graph theory."
*Studia Sci. Math. Hungar.* 1, 215–235.

**Defined at** N = q² + q + 1 for prime power q: 7, 13, 31, 57, 133, 183, …
(primes q only in the first pass: q ∈ {2, 3, 5, 7, 11, 13}.)

**Construction**

1. Vertices are the q²+q+1 projective points of PG(2, q), represented as
   equivalence-class canonical reps in F_q³ \\ {0} under scalar mult.
2. Edge `p ~ p'` iff `p · p' ≡ 0 (mod q)` and `p ≠ p'` (standard bilinear
   form; drop self-loops from "absolute points" where `p · p = 0`).

**Why non-VT:** Two orbits — `q+1` absolute points (degree q after self-loop
removal) and `q²` non-absolute points (degree q+1). The two orbits are
structurally distinguishable, so no automorphism swaps them. Directly
non-VT without perturbation.

**Why K₄-free:** Standard — ER(q) is C₄-free (any two projective points
determine a unique line, hence ≤ 2 common neighbors is wrong — actually
exactly one common neighbor for distinct non-collinear pairs). C₄-free ⇒ K₄-free.

**Expected scaling:** d ≈ q+1, α ≈ q^{3/2}. c grows as √q / ln q, so not a
record-beater at large q — but a clean non-VT scaffold to perturb.

**Pitfalls:** q = 2 gives N = 7 (Fano). Canonicalize projective points by
scaling the first nonzero coordinate to 1.

---

## 2. `er_polarity_delete_matching` — ER(q) minus a matching

**Reference:** Folklore perturbation; closest published analog is the
"polarity minus ovoid" literature (De Winter et al., 2010).

**Construction**

1. Build ER(q) as in entry #1.
2. On the non-absolute orbit, select a matching of ⌊q²/2⌋ edges by a
   deterministic rule (e.g., pair vertex i with vertex i+q mod q²) and
   **delete** those edges.

**Why non-VT:** The matched vertices have degree q (same as absolute
points), the unmatched ones have degree q+1 — creates a three-orbit
structure. No automorphism of ER(q) preserves an arbitrary matching.

**Why K₄-free:** Deleting edges from a K₄-free graph keeps it K₄-free.

**Expected scaling:** α unchanged or increases by at most |matching|/2;
d_max drops by 0 (if not every vertex is matched) or 1.

---

## 3. `mv_hermitian` — Mattheus–Verstraete Hq*

**Reference:** Mattheus, Verstraete (2024). "The asymptotics of r(4, t)."
*Annals of Mathematics* 199. arXiv:2306.04007.

**Defined at** N = q²(q² − q + 1) for prime q: 12, 63, 525, 2107.
(Start at q=2 → N=12, q=3 → N=63. Avoid q≥5 initially — α is expensive.)

**Construction**

1. Build F_{q²} (use q=p prime and {1, t} basis with t² = non-residue).
2. Unital H ⊂ PG(2, q²): projective points `⟨x, y, z⟩` with
   `x^{q+1} + y^{q+1} + z^{q+1} = 0`. It has q³+1 points.
3. Secants: lines of PG(2, q²) meeting H in exactly q+1 points. There are
   q²(q² − q + 1) secants — these are the vertices.
4. **Base graph Hq**: two secants adjacent iff they meet at a unital point.
   For each unital point p, the secants through p form a "pencil" of q²
   vertices (a clique in Hq).
5. **Hq* (the K₄-free graph)**: for each pencil P, flip an independent fair
   coin for each vertex in P to get bipartition (A_P, B_P); replace the
   pencil's clique with the complete bipartite graph K(A_P, B_P).
6. **Seed all randomness** (`random.seed(N)` or per-construct).

**Why non-VT:** Each pencil's bipartition is independent and random →
no global automorphism permutes pencils coherently. Explicit non-VT.

**Why K₄-free:** Every would-be K₄ has three vertices in some common
pencil (Prop 2.iv). After bipartition, the induced subgraph on any
pencil is bipartite hence triangle-free, so those 3 vertices don't form
a triangle, so no K₄ survives.

**Expected scaling:** N = q²(q² − q + 1), d ≈ q³/2, α ≈ q^{4/3} (log q)^{4/3}.
c grows as q^{1/3} (log q)^{1/3} / 3 — also not a beater, but genuinely
non-VT and published.

**Pitfalls:** Two pencils share ≤ 1 vertex (Prop 2.ii), so per-pencil
bipartition has no conflicts. F_{q²} arithmetic is the trickiest part —
if q=2 verify the unital has 9 points and 28 secants first.

---

## 4. `srg_clebsch_minus_matching` — K₄-free SRG minus a local structure

**Reference:** SRG catalog in `docs/searches/SRG_CATALOG.md`. The Clebsch
graph srg(16, 5, 0, 2) is K₄-free (λ=0, triangle-free — trivially K₄-free)
and has α=5. The Schläfli complement srg(27, 10, 1, 5) is K₄-free
with α=9.

**Defined at** N = 16 (Clebsch), 27 (Schläfli complement). Extend to
srg(40, 12, 2, 4) at N=40.

**Construction**

1. Hard-code the Clebsch graph edge list (adjacency via the 5-cube
   antipodal quotient: vertices are {0,1}⁵ quotiented by
   x ~ x⊕11111, edges `uv` iff Hamming distance(u,v) ∈ {1, 2}). Or use
   the explicit adjacency matrix from any graph-theory text.
2. Delete a matching of size 4–8 edges by a deterministic rule.

**Why non-VT:** Clebsch itself is VT (Aut acts transitively). But a
matching deletion breaks transitivity unless the matching is an orbit
of Aut, which for random matchings it is not. For a deterministic
matching, pick one that is not Aut-invariant.

**Why K₄-free:** Clebsch is triangle-free, so trivially K₄-free; edge
deletion preserves K₄-freeness.

**Expected scaling:** At N=16, d_max drops to 4 on matched vertices;
α may increase from 5 to 6 or 7. c was 1.4 for full Clebsch; perturbation
moves it modestly.

---

## 5. `bohman_keevash_k4_process` — K₄-free random greedy process

**Reference:** Bohman, Keevash (2013). "Dynamic concentration of the
triangle-free process." Arxiv-era analog for K₄: the *K₄-free process*.
See Fiz Pontiveros–Griffiths–Morris (2020) for the related K₃ case.

**Defined at** every N ≥ 7. Stopping rule: the graph becomes K₄-saturated
(no more edges addable).

**Construction**

1. Seed `random.seed(N)` or `random.seed(N * 31 + 7)` for reproducibility.
2. Start with empty graph on N vertices.
3. Enumerate all (i, j) pairs, shuffle.
4. Walk the list: for each pair, add edge (i, j) iff adding it does not
   create a K₄ (check: no common neighbor u, v of (i, j) with u–v an
   edge).
5. Return the final edge list.

**Why non-VT:** Random edge order destroys any possible global symmetry.
With N ≥ 10 the resulting graph is almost surely non-VT (no
graph-theoretic automorphism swaps all pairs).

**Why K₄-free:** By construction — the insertion rule enforces it.

**Expected scaling:** d_max = Θ(√N log N), α = O(√N log N). c ≈ log N /
(constant). Not asymptotically better than Paley, but a baseline to
beat via structured variants.

**Variants:** (a) biased ordering (degree-capped), (b) two-stage: build
a structured base, then K₄-free-process the remaining edges.

---

## 6. `polarity_minus_hyperoval` — ER(q) minus a hyperoval

**Reference:** De Winter, Ihringer, Kamat (2016). "Hyperovals in
PG(2, q) — applications to Ramsey numbers." (Construction technique;
result is well-known in finite geometry.)

**Defined at** N = q² + q + 1 − (q + 2) = q² − 1 for even prime power q.
Primes only: q=2 → N=3 (too small), so this family starts at q=4 which
needs F_{p^k}. **Skip unless F_4 arithmetic is available.** Listed for
completeness.

---

## 7. `ramsey_greedy_triangle_shadow` — two-phase Ramsey construction

**Reference:** Kim (1995) triangle-free-process-style argument,
extended to K₄-free.

**Defined at** every N ≥ 20.

**Construction**

1. Phase 1: build a triangle-free graph G₀ by greedy random edge addition
   rejecting triangles, targeting density ≈ √(ln N / N).
2. Phase 2: starting from G₀, add further edges under the K₄-free
   constraint only (triangles now allowed).
3. Return the final edge list. Seed `random.seed(N * 13)`.

**Why non-VT:** Two-phase random process — no global symmetry survives.

**Why K₄-free:** Phase 1 keeps triangle-free (stronger than K₄-free);
Phase 2 enforces K₄-freeness directly.

**Expected scaling:** Phase 1 yields d ≈ √(N log N); Phase 2 roughly
doubles d_max. Empirically competitive with Paley-scale c only at
medium N.

---

## 8. `two_orbit_bipartite_point_line` — bipartite point–line incidence

**Reference:** Generic "two-orbit" construction, ubiquitous in algebraic
graph theory. See Godsil–Royle *Algebraic Graph Theory* §5.

**Defined at** any N where N = 2m for m ≥ 5, or at specific projective
orders N = 2(q² + q + 1).

**Construction**

1. Split [0, N) into two sides: P = [0, N/2), L = [N/2, N).
2. Deterministic edge rule: for a pair (p ∈ P, ℓ ∈ L), include edge iff
   a (p, ℓ)-specific predicate holds. Options:
   - `hash(p * N + ℓ) % 3 == 0` (hash-based two-orbit).
   - If N = 2(q²+q+1): interpret P as points and L as lines of PG(2, q);
     include (p, ℓ) iff p ∈ ℓ. Standard point-line incidence.
3. No edges within P or within L (bipartite by construction).

**Why non-VT:** Bipartite with the two sides structurally distinct.
Aut at best splits into Aut(P) × Aut(L), never swaps them.

**Why K₄-free:** Bipartite ⇒ triangle-free ⇒ K₄-free.

**Expected scaling:** α ≥ N/2 (one full side is independent), so c
tends to be high. Compensated by narrow d_max. Not a record-beater,
but structurally sound and a natural seed for perturbation (add a few
intra-side edges, break bipartiteness while tracking K₄).

---

## 9. `unital_point_line_incidence` — unital incidence graph

**Reference:** Classical (Wielandt 1964 era). Bipartite incidence graph
of a unital in PG(2, q²).

**Defined at** N = (q³ + 1) + q²(q² − q + 1) for prime q: 37, 217, …
(q=2 → N=9 + 12 = 21; q=3 → N=28 + 63 = 91.)

**Construction**

1. Build the unital H ⊂ PG(2, q²) as in entry #3 step 1–2.
2. Build the secants of H as in entry #3 step 3.
3. Bipartite graph: one side is unital points (|H| = q³ + 1), other side
   is secants. Edge (p, s) iff p ∈ s (p is on line s ∩ H).

**Why non-VT:** Two orbits (points vs lines), structurally distinguishable
by role. The automorphism group of the unital is large but does not swap
points with lines.

**Why K₄-free:** Bipartite. Also: any 4-cycle would require two lines
intersecting in 2 points of the unital, which is forbidden by secant
definition.

**Expected scaling:** d on point-side = q+1, d on line-side = q² points
per secant — wait, secant size is q+1 points. So degree on each side is
q+1. N = (q³ + 1) + q²(q² − q + 1). α ≥ max(|H|, |secants|).

---

## 10. `asymmetric_lift_generic` — asymmetric layer lift of a base graph

**Reference:** Generic technique from voltage-graph theory. See
Gross–Tucker *Topological Graph Theory* Ch. 2.

**Defined at** N = k · m for any k ≥ 2 and m = the base graph's size.
Do **not** use Paley as the base. Use: ER(q) (entry #1), Clebsch, or
the K₄-free greedy base from entry #5 at a fixed small m.

**Construction**

1. Pick a non-VT base graph G₀ on m vertices from another catalog entry.
2. Build k disjoint copies of G₀ on [0, m), [m, 2m), …, [(k−1)m, km).
3. Add cross-layer edges according to a *non-uniform* rule — e.g.:
   only between layers i and i+1 (mod k), and only for specific
   vertex pairs determined by a deterministic hash.
4. Check K₄-freeness after each cross-edge; skip any edge that would
   create a K₄.

**Why non-VT:** Non-uniform cross-edges break any potential global
automorphism cycling layers. If the base G₀ is already non-VT, the lift
inherits that property.

**Why K₄-free:** Guarded by the on-the-fly check.

**Expected scaling:** d_max ≈ (G₀'s d_max) + (cross-edge count per
vertex). α can drop relative to k · α(G₀) if cross-edges are dense
enough to "stitch" layer independent sets.

---

## Priority by high-N promise (TARGET N ≥ 34)

The previous Haiku run produced a best `c ≈ 0.88` at **N = 7** —
useless for breaking the record because the Paley threshold is a
large-N statement. Small-N wins don't generalize and aren't what the
0.6789 line cares about. **Your candidate must support N ≥ 34 with a
finite c to count as a "real" port.**

Rated by realistic "can produce c < 1.0 at some N ≥ 34" potential:

| Priority | Entry                              | Why                                                        |
|----------|------------------------------------|------------------------------------------------------------|
| HIGH     | `asymmetric_lift_generic` (#10)    | Only family with tunable N ≥ 34 + non-trivial α reduction |
| HIGH     | `mv_hermitian` (#3) at q=3, N=63   | Published non-VT, α well-studied, N = 63 medium            |
| HIGH     | `unital_point_line_incidence` (#9) | Bipartite, N=91 supported, natural large-N                 |
| MED      | `er_polarity` (#1) at q ≥ 7        | N=57, 133, 183 — larger q is where α/N drops               |
| MED      | `er_polarity_delete_matching` (#2) | ER + perturbation; only useful if #1 port works at N ≥ 57  |
| MED      | `ramsey_greedy_triangle_shadow` (#7)| Covers every N ≥ 20 but c tends above 1.0 at large N      |
| LOW      | `bohman_keevash_k4_process` (#5)   | Works at every N but empirical c ≥ 1.05 at N ≥ 34          |
| LOW      | `srg_clebsch_minus_matching` (#4)  | Only defined at N ∈ {16, 27, 40}; small-N only             |
| LOW      | `two_orbit_bipartite_point_line` (#8)| Bipartite forces α ≥ N/2, high c by construction          |

**Work order (revised):** `mv_hermitian q=3` → `unital_point_line_incidence q=2,3` →
`er_polarity q=7,11` → `asymmetric_lift_generic` with ER or unital as base →
`er_polarity_delete_matching` as a perturbation → `ramsey_greedy_triangle_shadow` →
rest as time allows.

## Hard rules

1. **No trivial seed sweeps.** Changing `random.seed(N)` to `random.seed(N*7)`
   and calling it a new candidate is not allowed. Two candidates in the
   same family must differ **structurally** — different edge rule,
   different algebraic base, different perturbation mechanism. If your
   mutation is "same code, different seed", don't write it.
2. **Candidate must support N ≥ 34.** If your construction only produces
   d_max ≥ 2 at N ≤ 20, don't submit it. It may reproduce a known small-N
   result but cannot beat the 0.6789 line.
3. **At most 2 candidates per catalog entry before moving on.** Port once,
   optionally perturb once with a specific structural hypothesis, then
   move to the next entry. Don't exhaust seed variations.
4. **Mutation requires a specific hypothesis.** `# Parent: gen_NNN (changed
   random seed)` is banned. `# Parent: gen_NNN (replaced uniform pencil
   bipartition with size-imbalanced 1:2 split to reduce α)` is OK.
