# Session log — 2026-04-24

Chronological notes from a session that covered frontier analysis, lift
structure, the DeepMind Ramsey catalog ingest, and a clean negative on
MV-bipartization of small generalized quadrangles.

## Summary of outputs

New docs written this session:
- `docs/theory/LIFT_STRUCTURE.md` — BEATS/TIES/WORSE vs. lift, prime
  cells, mechanism for beating lifts.
- `docs/searches/MV_BIPARTIZATION.md` — GQ(2,2) and GQ(3,3) experiments.
- `docs/searches/DEEPMIND_RAMSEY.md` — 7 ingested Ramsey lower-bound
  constructions from google-research/ramsey_number_bounds.

New scripts:
- `scripts/ingest_deepmind_ramsey.py`
- `scripts/ingest_disjoint_lifts.py`
- `scripts/run_mv_bipartization.py`  (uses `search/mv_bipartization.py`)
- `scripts/run_mv_gq22.py` (earlier, superseded by the generalized runner)
- `scripts/target_n83_a12.py` (killed, kept as a reference for D-range
  targeted SAT drivers)

New graph_db entries:
- `source="deepmind_ramsey"` — 7 graphs (n ∈ {138, 147, 158, 173, 208,
  218, 236}), all tight at their claimed α upper bound.
- `source="disjoint_lift"` — 13 graphs, realizing missing trivial lifts
  at n ∈ {28, 30, 42, 45, 56, 69, 70, 75, 82, 84, 90, 98, 100}.
- `source="mv_bipartization"` — 15 graphs (7 at n=15, 8 at n=40) from
  the GQ experiments; all lose to the frontier but document the MV
  ceiling concretely.

## Chronology

### 1. Frontier analysis at n ≤ 120

Walked through the per-n minimum-c_log row in graph_db and the
connected-only minimum. Categorised every n ∈ [8, 100] into:

- **BEATS** (14 n): the best connected K₄-free graph strictly improves on
  any trivial lift at this n. All are n ≤ 49.
- **TIES** (4 n): connected matches the lift exactly at n ∈ {16, 26, 46,
  58}. All are n = 2·p where p is (near-)prime.
- **WORSE** (46 n): best connected loses to the lift. Dominated by
  cayley_tabu_gap and circulant_fast families.
- **NO_CONN** (7 n): no connected entry in DB at all — lift is
  unchallenged.

Mechanism study (see `docs/theory/LIFT_STRUCTURE.md`):

- BEATS winners trade α-savings (1 to 6 independent vertices less than
  k·α_prime) for higher d (up to +8). The c_log formula
  `α·d/(n·ln d)` rewards this because `d/ln d` is sub-linear.
- Corrected a false intuition: triangle density is **not** the winning
  mechanism. Mantel saturation at BEATS winners is 17–25% of the cap;
  at WORSE graphs (especially "blowup" constructions at n = k·17) it's
  50–75%. Triangle density is the *anti-signal*.
- WORSE cases at n = k·P17 (n=34, 51, 87) are "blowup of P(17)" entries
  that preserve α (k·α) but multiply d by k, producing catastrophic
  loss (+0.34 to +0.77). Never submit a blowup without comparing to the
  disjoint-union of the same cell — the lift always dominates.

### 2. Filled in missing lifts

Found 13 n-values where the best trivial lift was not stored in graph_db
(either no disconnected entry at all, or a suboptimal one). Two
categories:

- **LIFT_MISSING** (n = 30, 45): no disconnected entry, lift of the
  n=15 cell would give c=0.7195 vs current 0.769.
- **LIFT_PARTIAL** (11 n including 28, 42, 56, 69, 70, 75, 82, 84, 90,
  98, 100): disconnected entry exists but is not the best achievable
  cell replication.

`scripts/ingest_disjoint_lifts.py` generates k·cell disjoint-union
graphs, validates, and adds to graph_db under `source="disjoint_lift"`.
All 13 ingested and synced. The n=14 cell (α=3, d=6, c=0.7176) and the
n=15 cell (α=3, d=7, c=0.7195) turned out to be the most-missed lift
targets.

Confirms: the frontier really is a tiling of a handful of small
irreducible "prime cells". P(17) at c=0.6789 is the floor; C_8² at
0.7213, 22-cell at 0.6995, and the n=14 / n=15 SAT cells fill in above
it.

### 3. DeepMind Ramsey ingest

User asked to download and ingest K₄-free graphs from
<https://github.com/google-research/google-research/tree/master/ramsey_number_bounds/improved_bounds>.
Seven R(4,s) files parsed, validated K₄-free, verified α equals the
claimed s−1 upper bound, ingested as `source="deepmind_ramsey"`.

All seven have high c_log (0.99–1.24), far above our 0.679 frontier.
This is expected: MV-style Ramsey constructions minimise α/n, not
c_log, and they pay with large d (42–64). Useful as a reference
catalogue of "dense K₄-free extremal" graphs, not as frontier
candidates. See `docs/searches/DEEPMIND_RAMSEY.md`.

### 4. n=83 bounds analysis

Prompted by a parallel GAP-Cayley sweep result `SG_83_1_C83 c_log=0.975
α=13 d=18`. Didn't improve the frontier (current best n=83: α=20, d=8,
c=0.927) but raised the question of how low α can go at n=83.

Analytic bounds (see section of `LIFT_STRUCTURE.md`):
- Ramsey: α ≥ 8 at n=83 (since R(4,8) ≤ 79). α=7 is **provably
  infeasible**.
- Caro-Wei (tight when G is clique-union): α ≥ 4.4 at d=18. Loose for
  K4-free d ≥ 3.
- Shearer (triangle-free): α ≥ 10.06. Not directly applicable (our
  graph has triangles).
- Empirical n^(3/5): α ≈ 14.2 is where Cayley-class K₄-free extremals
  land. The α=13 find sits at 0.92 of this scale — essentially
  saturated on the n^(3/5) curve, not at any theoretical bound.
- MV-scale n^(2/5) ≈ 5.9: much lower, but requires
  Mattheus-Verstraete-style incidence constructions, not Cayley.

Attempted a targeted SAT at (n=83, α=12, D ∈ [2..28]) with the
break-even d-range for c_log improvement. Killed before completion —
CP-SAT on n=83 with tight α caps chews for hours without intermediate
log events; worth running on the server (200GB/32-core) with per-case
budgets ≥ 30 minutes, not locally.

### 5. MV-bipartization of GQ(s,s)

Core experiment of the session. User flagged that the earlier
"sparsify MV" direction was fighting itself: MV's c_log grows with q
(N^(1/12)/ln N → ∞), and edge deletion can only *increase* α in a
K4-free graph. MV is structure-aware — it starts from a K4-rich
algebraic design and bipartises each pencil to destroy K4s while
preserving α-suppression.

The productive question: does MV-style pencil bipartization reach or
beat P(17) at finite N? Smallest test case: **GQ(2,2)** at N=15
(ground truth known: SAT finds c=0.7195, α=3, d=7).

Built `search/mv_bipartization.py`:
- Constructors for GQ(2,2) (Cremona-Richmond / the doily) and GQ(3,3)
  (= W(3), symplectic quadrangle over F₃).
- Random-partition search over binary splits of each pencil.
- K₄-free verification on bipartised graph.
- Exact α via brute-force (n ≤ 20) or CP-SAT (n > 20).

**Results:**

| structure | n  | bipartised best | frontier | gap    | mechanism                      |
|-----------|----|-----------------|----------|--------|--------------------------------|
| GQ(2,2)   | 15 | **c=0.962** (α=5, d=4)  | 0.7195 | +0.24 | ovoid-locked α                 |
| GQ(3,3)   | 40 | **c=1.229** (α=12, d=9) | 0.7195 | +0.51 | bipartization α regression     |

Interpretation (see `docs/searches/MV_BIPARTIZATION.md`):

- **GQ(2,2)**: baseline already K₄-free (cliques = K₃). Bipartization
  only removes edges, so α is locked by the ovoid number = 5 under
  every partition. Optimum is 4-regular (uniform-singleton) which
  matches the **tensor-Hoffman floor of 0.9618** flagged in the
  earlier MV spectrum screen. The Hoffman bound **is** this
  construction.

- **GQ(3,3)**: baseline has K4s (each line is K₄). α on the baseline =
  7 (proved optimal by CP-SAT; W(3) has no ovoid so α < Hoffman=10).
  Bipartization destroys K4s *and simultaneously* inflates α from 7 to
  12+, because the bipartization removes exactly the edges that made
  the α=7 partial-ovoid tight. Structural tension: MV-design
  α-efficiency lives in K4-rich neighbourhoods; destroying K4s
  destroys the efficiency.

**Direction verdict:** the two smallest GQ(s,s) cases both close the
"MV-on-designs beats P(17) at finite N" hypothesis. Scaling argument
says higher q goes the wrong way (q-ladder: gap grows, not shrinks).
Not worth running q ≥ 4 Hermitian unitals or polar spaces for this
purpose. They remain relevant as reference catalogues of K4-rich
structures with sharp α, but not as c_log-frontier candidates.

## Outstanding / loose ends

Things I noticed but didn't act on:

- The **sat_exact n=14, n=15 cells** (α=3, d=6 and α=3, d=7) are
  non-Cayley, non-VT graphs with moderate Mantel saturation (17–21%)
  and are the prime cells for many composite n. They lie in a
  strictly different symmetry class than Cayley-tabu attractors
  (spread=1 vs. spread=0). Any cross-method "sparsifier" porting
  between them won't work — the symmetry classes are disjoint. Noted
  in `LIFT_STRUCTURE.md`.
- The **connected-search gap** at plateau n is closable at n ∈ {24, 36,
  48, 54, 60, 96} where gap < 0.05. Break-even-d targeted SAT at these
  n (on the server) is the tightest remaining Cayley-class question
  below n=100.
- The **visualizer** got a failed attempt at a "type-a-number-to-jump"
  feature: bound digits/Enter/Backspace at the Tk root, which broke
  matplotlib's zoom shortcuts. Reverted. Also tried DPI scaling; also
  reverted. Clean working tree on `visualizer/visualizer.py`. If we
  want this feature we should use a dedicated Entry widget and be
  careful not to collide with matplotlib's keymap.
- **n=100 connected** has c_log=1.202, losing to the 5×(n=20) lift by
  +0.48 — the second-largest WORSE gap. `random_regular_switch` is
  the only connected entry at n=100. A directed search (either Cayley
  over the 49 small groups of order 100, or a SAT near-regular run)
  could close this significantly.

## Reset / next-session cleanup notes

- SESSION_LOG_20260421 covered the Conjecture A verification programme.
  This log (20260424) focuses on frontier / lift / MV-direction
  cleanup. When consolidating:
  - merge `LIFT_STRUCTURE.md` content into `FRONTIER_REVIEW.md` or a
    new `FRONTIER_MECHANICS.md` — it's not really "theory", it's
    empirical structure analysis.
  - `MV_BIPARTIZATION.md` pairs with existing `MATTHEUS_VERSTRAETE.md`
    and `FRONTIER_REVIEW.md` section 3. Consider merging or
    cross-referencing.
  - `DEEPMIND_RAMSEY.md` is a catalog doc — stays standalone under
    `docs/searches/`.
- `scripts/target_n83_a12.py` is a reference for how to drive
  SATNearRegularNonReg with a D-range (the CLI script doesn't expose
  one). Move to `scripts/experimental/` if we add such a folder.
