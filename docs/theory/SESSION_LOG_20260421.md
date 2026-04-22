# Session log — 2026-04-21

Chronological log of what was done this session, for later reading.
Covers: extending Conjecture-A exhaustive verification beyond P(17), adding
db persistence, and preparing the D_17 run.

## Prior state (entering this session)

From earlier in the day (already documented in `P17_LIFT_OPTIMALITY.md`):

- Built `scripts/verify_p17_lift.py`: exhaustive cyclic Cayley verifier using
  bitmask enumeration + inline lex-min (Z_n)*-orbit pruning.
- Ran it at N=17, 34, 51. In each case: **unique minimizer up to (Z_n)*
  action is the k-lift of P(17)**. c = 0.678915 exact.
- Conjecture A (cyclic case) confirmed at k=1, 2, 3 for the P(17) family.
- `BEYOND_CAYLEY.md` captured implications: directional proof that breaking
  0.6789 at 17k requires leaving Cayley-on-Z_n space.

Also running in background: `scripts/run_cayley_tabu.py --n-lo 68 --n-hi 100`
(PID 28860, started 13:00).

## What happened this session

### 1. Noticed `scan()` wasn't persisting

`verify_p17_lift.py` originally returned a dict and only printed. User caught
this: "the scan saves any of the new found graphs to the database right".
Answer was no. Added `--save-db` flag + `_save_minimizers_to_db()` that
converts the adj matrix to a networkx Graph and calls
`GraphStore.add_graph(..., source='cyclic_exhaustive_min', ...)` with full
metadata (connection_set, α, d_max, c_log, orbit counts, certificate).

### 2. Swept adjacent lift-tower families

Database query for low-c small-N cyclic Cayley entries revealed three
lift-tower families worth exhaustive verification:

- **P(17)** at N=17, 34, 51, (68)
- **N=22 family** at N=22, 44, (66): base = `Cay(Z_22, {1,2,8,9,13,14,20,21})`,
  c = 0.6995. *Not* algebraic (11 ≡ 3 mod 4 so P(11) doesn't exist).
- **CR(19)** at N=19, 38, (57): base = `Cay(Z_19, {1,7,8,11,12,18})` (cubic
  residues), c = 0.7050.

Ran `verify_p17_lift.py --save-db` at N ∈ {17, 19, 22, 34, 38, 44, 51}.
All yielded unique (Z_n)*-orbit minimizers matching the k-lift of the
base. Seven records now persisted under `source='cyclic_exhaustive_min'`.

### 3. Updated `BEYOND_CAYLEY.md`

Added an "Other lift-tower families" subsection (section 7) with a
summary table. Current confirmed Conjecture A coverage:

| Family | Base N | d | c     | k verified |
|--------|--------|---|-------|-----------|
| P(17)  | 17     | 8 | 0.6789 | 1, 2, 3   |
| N=22   | 22     | 8 | 0.6995 | 1, 2      |
| CR(19) | 19     | 6 | 0.7050 | 1, 2      |

Beyond that: k=4 P(17) (N=68, 2^33 subsets) and k=3 N=22 family (N=66,
2^32 subsets) exceed the plain-exhaustive budget. k=3 CR(19) (N=57,
2^28) is borderline feasible (~2h).

### 4. User redirected the next step

User's observation (quoted here so the context is clear): marginal info
content of another cyclic k is low because the k-lift mechanism is the
same across families; the proper next move is either (a) the character-
theoretic proof of A for all k (likely 2–5 pages), or (b) closing
**Conjecture B** (all groups of order 17k, not just cyclic) by running
the non-abelian groups at N=34 and N=51.

Decision: (b). D_17 at N=34 is the only non-abelian group of order 34;
Z_17 ⋊ Z_3 is the only non-abelian group of order 51 (since 3 | 17-1).
If both return ≥ 0.6789, **Conjecture B is proved exhaustively at k=2
and k=3** — a strict strengthening beyond what's already done.

### 5. Wrote `scripts/verify_dihedral.py` (not yet run)

Exhaustive D_p verifier. Key structure:

- Element indexing: rotations r^i → indices 0..p-1; reflections s·r^j →
  indices p..2p-1. Identity r^0 = 0.
- Symmetric subset bitmask: pairs {i, p-i} for i = 1..(p-1)/2 (rotation
  inverses) + one bit per reflection (self-inverse). Total slots
  (3p-1)/2, giving 2^{(3p-1)/2} symmetric subsets. For p=17: 2^25 =
  33,554,432.
- Aut(D_p) = Hol(Z_p) = Z_p ⋊ Z_p* of order p(p-1) = 272 for p=17.
  φ_{u,v}(r^i) = r^{u·i}, φ_{u,v}(s·r^j) = s·r^{v + u·j}.
- Lex-min orbit pruning identical in spirit to verify_p17_lift.py: for
  each mask, compute all 272 φ·mask and skip unless the mask is the
  smallest in its orbit.
- D_p is CI (Babai) for p odd prime, so Aut(D_p) orbits = graph-iso
  classes of Cay(D_p, ·).
- Same α solver (`alpha_bb_clique_cover`) and K₄-free check as cyclic.
- `--save-db` writes under `source='dihedral_exhaustive_min'`.
- Includes a "P(17)-lift on D_17 as rotation-only" check: if the
  minimizer orbit contains the subset {r^x : x ∈ QR_17}, that confirms
  D_17 is not beating cyclic.

Smoke-test plan: run at p=5 (D_5, 2^7 = 128 subsets, seconds) before the
full D_17 job.

### 6. What's currently running / pending

- **cayley_tabu sweep** (PID 28860): N=68..100, currently on N=77
  (started 13:00, ETA ~4–5h total). Throughput will pick up now that
  the N=51 exhaustive released its CPU.
- **verify_dihedral.py D_17 run**: prepared but **not yet launched**.
  Held until tabu sweep completes to avoid halving throughput again.
  Expected runtime for D_17: 20–60 min (123K orbit reps, most rejected
  quickly on K₄; ~1% α-computed).
- **verify Z_17⋊Z_3 at N=51**: not yet scripted; same technique but
  different group structure (semidirect 17:3, order 51, different
  Aut). Will write after D_17 returns clean.

## Key files touched this session

- `scripts/verify_p17_lift.py` — added `--save-db`, `_save_minimizers_to_db`
- `scripts/verify_dihedral.py` — new; D_p exhaustive verifier (not yet run)
- `docs/theory/BEYOND_CAYLEY.md` — Section 7 family table updated, k=3
  P(17) result added
- graph_db: 7 new records under `source='cyclic_exhaustive_min'` at
  N ∈ {17, 19, 22, 34, 38, 44, 51}

## Next actions (ordered)

1. Wait for cayley_tabu sweep to free CPU (~4h).
2. Smoke-test `verify_dihedral.py --p 5` (seconds).
3. Run `verify_dihedral.py --p 17 --save-db` (~30 min).
   - **If min c ≥ 0.6789:** Conjecture B closed at k=2 for P(17). Write note.
   - **If min c < 0.6789:** new Cayley construction found on non-abelian
     order-34 group — far more interesting. Investigate.
4. Write `verify_nonabelian_51.py` for Z_17⋊Z_3 (only other non-abelian
   group of order 51). Run exhaustive.
5. Optionally: character-theoretic proof of A for all k (family-
   independent). Probably 2–5 page note.

## Addendum — asymmetric lift tabu (later in session)

After the main planning, user asked for concrete non-VT experiments on
N=34. Wrote and ran `scripts/asymmetric_lift_tabu.py`:

- **Cross-only mode (289-bit)**: neighborhood is only (i, 17+j) cross-
  layer edges, warm-started with no cross edges (base = 2·P(17)). Ran
  5 min, 8 restarts. No sub-P(17) hit; stuck because a single cross
  edge raises d from 8→9 while α stays at 6, so c increases.

- **Full mode (561-bit)**: neighborhood is every edge of the 34-graph.
  Warm-started with x = indicator of 2·P(17) edges, so tabu can also
  REMOVE intra-copy edges. Ran 326s, 8 restarts, 300 iters each.
  - Restart 0 (cold from 2·P(17)): no improving 1-flip move exists.
    **2·P(17) is a strict local minimum under 1-flip in the full
    561-bit space.**
  - Restarts 1–7 (diversified by 1..6 random flips): landed in an
    (α=6, d=9, c=0.7228) basin with 139 edges, or in K₄-hit regions.
    None broke below 0.6789.
  - Global best over all 8 restarts: c=0.6789 (returned to 2·P(17)).

**Takeaway.** 1-flip tabu cannot escape 2·P(17). The next-basin
floor sits at c ≈ 0.7228 (α=6, d=9, +3 edges). Beating 0.6789 on N=34
would require one of:
(a) multi-flip moves (2-opt, 3-opt) to simultaneously drop α and d,
(b) a structurally different warm start (not 2·P(17)), e.g. a random
    3-edge-colouring quotient or a Ramsey-guided construction,
(c) SAT-exact over the full 561-bit space with c<0.6789 as the target
    constraint — expensive but decisive.

No DB record was persisted (guarded on `c < 0.70`, which the run's
global best — equal to P(17) itself — did not satisfy as a new graph).

## Addendum — D_17 exhaustive (later in session)

After killing the stuck cayley_tabu N=77 (user call), ran
`verify_dihedral.py --p 17 --save-db` on the freed CPU.

**Result** (340.5s total, 2²⁵ subsets):
- 131,659 Aut(D_17)-orbits
- 5,724 K₄-free orbits
- **Unique minimizer** at c = 0.678915, S = {r³, r⁵, r⁶, r⁷, r¹⁰, r¹¹, r¹², r¹⁴}
  — this is {r^x : x ∈ NQR_17}, which is Aut(D_17)-equivalent to the QR_17
  rotation lift (NQR = u·QR for some u ∈ Z_17*, and φ_{u,0} ∈ Aut(D_17)
  maps one to the other). So the minimizer is the rotation-only k=2 lift
  of P(17), consistent with being Cayley-on-Z_34 rather than exploiting
  D_17's reflections.
- 1 DB record persisted under `source='dihedral_exhaustive_min'`.

**Implication — Conjecture B closed at k=2 for order 34.** The only
two groups of order 34 are Z_34 (cyclic, verified earlier this session)
and D_17 (dihedral, verified now). Both admit the P(17)-lift as their
unique c-minimizer up to automorphism. **No non-abelian Cayley graph on
34 vertices beats P(17).**

Remaining for Conjecture B at k=3 (order 51): Z_17 ⋊ Z_3 (only non-
abelian group of order 51 since 3 | 17−1). Cyclic case already done.
Script not yet written.

## Addendum — SRG catalog screen (evening session)

User-driven follow-on: after the asymmetric lift tabu showed that
non-VT attacks on N=34 need structural diversity, we screened the
largest cheaply-enumerable non-VT source — McKay's strongly-regular-
graph catalog. Full write-up in `docs/searches/SRG_CATALOG.md`.

### Pipeline

- `scripts/run_srg_screen.py`: one-shot ingest. For each class in
  `SRG_CLASSES`, parse the `.g6` file, filter K₄-free (bitmask), run
  `alpha_bb_clique_cover_nx`, rank by c, `write_batch` to
  `graphs/srg_catalog.json`. Pre-computes eigenvalues, Hoffman α-upper,
  and Delsarte ω-upper per class as sanity context (no pre-filter).
- Raw `.g6` files under `graphs_src/srg_catalog/` (added to
  `.gitignore` as third-party data).

### Coverage

Two tiers. Minimal = `sr401224.g6` + `sr361446.g6` (the two classes
flagged in the research trawl as most likely K₄-free with sub-Paley α).
Exhaustive adds sr35*, sr27*, sr26*, sr28*, sr29*, sr25* — everything
McKay publishes at v ≤ 40.

### Results

- **4,361 graphs screened, 13 K₄-free survivors, 0 beat 0.6789.**
- Best catalog c = 0.9651 (srg(27,10,1,5), unique Schläfli complement).
- Pattern: every K₄-free survivor is Hoffman-tight or 1-below on α.
  SRGs tighten Hoffman by their spectrum, so even the non-VT SRGs
  (e.g. 2 of 10 Paulus graphs) don't realize the §3 sub-θ headroom.
- Correction to earlier analysis in the conversation: the
  `R(4,4) = 18` argument was over-applied to Paulus graphs — it forces
  K₄ in the (G, \bar G) pair, not in G alone. Two Paulus members are
  genuinely K₄-free (α = 6, c = 1.00).

### What this closes

SRG-based attacks at v ≤ 40 are empirically exhausted. `BEYOND_CAYLEY.md`
§9 captures the implication: remaining non-VT directions are
unaffected (SAT-exact at N=17/34, asymmetric lifts with multi-flip
moves, full-bitvector tabu with non-P(17) warm starts).

### Files touched (this addendum)

- `scripts/run_srg_screen.py` — new driver
- `docs/searches/SRG_CATALOG.md` — new per-search doc
- `docs/theory/BEYOND_CAYLEY.md` — §9 added
- `README.md` — `srg_catalog.json` and driver listed
- `.gitignore` — `graphs_src/` added
- `graphs/srg_catalog.json` — 13 records under `source='srg_catalog'`
