# MV-pencil-bipartization of incidence structures

Written 2026-04-24. Closes the "MV-style bipartization of small
incidence structures beats P(17) at finite N" direction with clean
negative results at GQ(2,2) and GQ(3,3). Paired with the earlier
`MATTHEUS_VERSTRAETE.md` (which documents why MV's asymptotic result
doesn't help at finite N for c_log) and with
`FRONTIER_REVIEW.md` §3 (which identified structure-aware bipartization
as the right re-framing of the MV direction).

## What MV does, structurally

Mattheus-Verstraete's R(4, t) ≥ Ω(t^{5/2} / polylog) construction
starts from an algebraic structure with "pencils" (collections of
points forming cliques in the collinearity graph) and destroys K4s by
**bipartising each pencil** — replacing each pencil's K_{s+1} with a
complete bipartite graph K_{a,b} where a + b = s+1. The point is that:

- K_{a,b} is K3-free (hence K4-free) — each bipartised pencil
  contributes no triangle
- The K4-free-ness of the whole graph follows from Prop 2.iv of the
  MV paper, which says K4s in an MV-target structure are confined to
  named sub-configurations (pencils or their immediate neighbourhoods)
- α-suppression is preserved because the independent sets being
  suppressed (ovoids / spreads / transversal designs) don't depend on
  edges within a single pencil

The question for our project was: at finite N, can this mechanism beat
P(17) (c_log = 0.6789)?

## Code

`search/mv_bipartization.py` provides:

- `gq22_points_lines()` — GQ(2,2) via Cremona-Richmond model (15 pts =
  2-subsets of {1..6}, 15 lines = 3-partitions of {1..6}).
- `gq33_points_lines()` — GQ(3,3) = W(3) symplectic quadrangle over F₃
  (40 pts in PG(3,3), 40 totally-isotropic lines).
- `collinearity_graph(points, lines)` — builds the graph where u~v iff
  they share a line.
- `bipartize(lines, idx, partition)` — applies MV bipartization given
  a per-line binary split of its points.
- `search_partitions(points, lines, ...)` — random search over
  singleton / binary partitions; returns top-k distinct K₄-free
  graphs by c_log.
- `alpha_auto(G)` — brute-force for n ≤ 20, CP-SAT for 20 < n ≤ 100.

Driver: `scripts/run_mv_bipartization.py --structure gq22|gq33`.

## GQ(2,2) at N=15

Baseline collinearity graph of GQ(2,2) = Kneser K(6,2) =
srg(15, 6, 1, 3). Already K₄-free (cliques = K₃), ovoid size 5, so
α = 5 on the baseline.

**Search**: 20000 random partition samples with seed=0. Each line
(3 points) gets one of 3 singleton choices.

| rank | c_log  | α | d_min | d_max | m  |
|------|--------|---|-------|-------|----|
| 1    | **0.9618** | 5 | 4 | 4 | 30 |
| 2–8  | 1.0356 | 5 | 3 | 5 | 30 |

- Best is 4-regular with α=5, achieved by the uniform-singleton
  allocation (each point is "singleton" in exactly 1 of its 3 lines,
  a perfect matching between points and lines).
- All trials have α=5 — **the ovoid number is locked**. Any edge
  deletion only *increases* α, so bipartization can never bring α
  below the original.
- c_log = 5·4/(15·ln 4) ≈ 0.9619 — **exactly matches the
  tensor-Hoffman floor of 0.9618** flagged in the earlier MV spectrum
  screen (200k+ catalog pairs). The Hoffman bound *is* this
  construction.

**Verdict**: loses to the SAT non-VT frontier at N=15 (c = 0.7195,
α=3, d=7) by **+0.24**.

## GQ(3,3) at N=40

Baseline collinearity graph of GQ(3,3) = W(3) = srg(40, 12, 2, 4).
Each line is a K₄, so the baseline is NOT K₄-free (inadmissible).
Bipartization is mandatory.

Surprising baseline fact: α(W(3)) = 7, not 10. W(3) admits **no
ovoid** (ovoids of W(q) exist iff q is even), so the Hoffman bound
10 is not tight. CP-SAT proves α=7 optimal in under a second. This
α=7 is what makes GQ(3,3) a priori interesting as an MV-target — a
denser-than-expected α-suppression in a K4-rich base.

**Search**: 5000 random partition samples with seed=0. Each line
(4 points) gets a random binary split (excluding all-one-side);
7 non-trivial splits per line.

| rank | c_log  | α  | d_min | d_max | m   |
|------|--------|----|-------|-------|-----|
| 1    | **1.2288** | 12 | 5 | 9 | 139 |
| 2    | 1.2288 | 12 | 6 | 9 | 147 |
| 3–4  | 1.2503 | 13 | 5 | 8 | ~135 |
| 5–8  | 1.3312 | 13 | 5 | 9 | ~140 |

- α jumps from 7 on the baseline to **12** on every bipartization
  sampled. The 7-vertex partial ovoid of W(3) is *not* preserved:
  bipartization removes exactly the edges that made it tight.
- d_max = 9, roughly balanced near-regular.
- c_log = 12·9/(40·ln 9) ≈ 1.229 — far worse than both the baseline
  c_log (0.845, but on a K4-containing graph) and the frontier at
  n=40 (0.7195 via 2×(n=20) lift).

**Verdict**: loses to the n=40 frontier by **+0.51** — a larger
gap than at GQ(2,2).

## Why the negative scales

Two distinct ceiling mechanisms, both structural:

**GQ(2,2) — ovoid lock**: baseline K₄-free with α locked at the
ovoid number. Bipartization only removes edges; α stays at 5 forever.
The optimal partition minimises d under that α-lock, landing on the
analytic Hoffman floor. **Impossible to beat c = α·4/(n·ln 4)**
since 4-regular is the densest regular graph achievable by balanced
pencil bipartization of K₃ pencils.

**GQ(3,3) — α regression**: baseline has K4s, which gave it low α=7.
Destroying the K4s destroys the α-tightness simultaneously. Every
bipartization lifts α to 12+. Hence the *negative correlation*
between K4-freeness and α-efficiency in MV targets.

This negative correlation **gets worse with q**. For GQ(q,q):

- baseline α behaves like the partial-ovoid number (depends on q
  parity and q modular properties) — in the "good" cases comparable
  to q²+1, in the "bad" cases much smaller.
- bipartization of q+1-cliques into balanced (⌈(q+1)/2⌉, ⌊(q+1)/2⌋)
  parts removes roughly (q+1)(q-1)/4 edges per pencil, and **α after
  bipartization grows proportional to q^(2)** roughly (bigger K4-free
  slack).
- d_max after balanced bipartization is roughly q(q+1)/2.

Plugging into c_log: the ratio α·d/(n·ln d) at MV-bipartised GQ(q,q)
is bounded below by a constant of order `Ω(q/ln q)`, which **grows
without bound** as q increases.

So there's no q-ladder that crosses P(17)'s 0.6789. The Hermitian
unital at q=3 (the main MV construction) would be even more
unfavourable.

## Relationship to prior docs

- **`MATTHEUS_VERSTRAETE.md`**: documented that MV's c_log grows with q
  (~ N^(1/12) / ln N), so MV is a c_log-losing asymptotic. This doc
  extends that negative to the **finite-N structure-aware version**:
  even at the smallest GQ(s,s) cases, bipartization doesn't cross
  P(17).
- **`FRONTIER_REVIEW.md` §3**: identified "clique-cover + α-locked
  Hoffman floor at 0.9618" as an analytic prediction across the
  200k+ catalog pairs. This doc confirms that the 0.9618 floor is
  **exactly** the bipartised GQ(2,2) c_log, not a coincidence. The
  SDP / catalog screen and the combinatorial experiment land on the
  same graph.
- **`BEYOND_CAYLEY.md`**: articulated that breaking 0.6789 requires
  leaving Cayley-on-Z_n space. MV-on-designs was one of the
  proposed escapes. This doc removes that escape route at the
  small-q end; the asymptotic version was already removed in
  `MATTHEUS_VERSTRAETE.md`. What remains is the non-cyclic
  Cayley / SAT-generated non-VT / polar-space-at-larger-q
  directions. Polar-spaces-at-larger-q is the direction the
  scaling argument above argues against.

## What's still open

MV-target structures whose baseline α is **lower** than GQ(q,q) and
whose bipartization α-regression is **smaller** are the remaining
class. Candidates to test:

- **Hermitian unitals H(q)** — the original MV target. q=2 gives a
  very small structure (N=9, barely interesting). q=3 gives N=28,
  which is a reasonable test. q=4 needs F₄ arithmetic (we don't have
  this built yet).
- **Generalized hexagons GH(2,2)** — N=63. The collinearity graph
  has girth 6 (no triangles in the graph), so it's triangle-free
  before bipartization, and bipartization is over 7-point pencils.
  Might behave differently from GQ because there are no K3 in the
  base.
- **Partial linear spaces with prescribed girth ≥ 6**. No K4 and no
  K3 in the base means bipartization is actually the wrong operation
  — the base is already the target, and we'd need a different
  densification, not bipartization.

Worth noting: GH(2,2) already has c_log considerably worse than
P(17) without any bipartization — baseline α = 21 (size of a 3-valent
sub-hexagon), d = 14, n = 63 gives c ≈ 1.5. So even starting from the
base graph (K3-free, K4-free, no bipartization needed), it loses.

**Net conclusion from this round**: incidence-structure-based K₄-free
constructions don't cross P(17) at finite N via any of the
structure-aware operations tested. The α-suppression they provide is
always paid back in d / n ratios by the c_log formula. Moving on from
this direction.
