# Beyond Cayley: what proving P(17)-lift optimality tells us about beating 0.6789

Companion to `P17_LIFT_OPTIMALITY.md`. Captures the research-strategy
implications of Conjectures A/B/C (proven exhaustively for k ∈ {1, 2}
in the cyclic case). Written 2026-04-21 for later reference.

## 1. Two claims that are easy to conflate

**Claim (empirical):** Cyclic / Cayley graphs minimize c in the db.

**Claim (conjectured):** Cyclic / Cayley graphs on 17k vertices
cannot achieve c < c(P(17)) = 0.6789.

The first is an artefact of search bias: we run Cayley-only search
(circulant, cayley, cayley_tabu) at almost every N. We rarely run
exhaustive non-Cayley search. The one regime where we do — SAT-exact
at small N — already shows **non-Cayley strictly beats Cayley**:

| N  | SAT-exact c | best Cayley c | Δ       |
|----|-------------|---------------|---------|
| 14 | 0.7176      | 0.7194        | +0.0018 |
| 15 | 0.7195      | 0.7212        | +0.0017 |

So non-Cayley wins at finite N is an observed phenomenon, not a
theoretical one. The empirical "Cayley best" is a *search artefact*.

## 2. What proving Conjecture A/B/C implies

If we prove Cayley graphs on 17k vertices have c ≥ 0.6789, then:

> Beating 0.6789 at N = 17k requires a **non-vertex-transitive**
> K₄-free graph.

This is a *directional* result, not a constructive one. It does not
say such graphs exist. It says: if you want to beat P(17), stop
searching Cayley / VT space at 17k — it's provably exhausted.

## 3. Why non-VT graphs should have headroom

There is a clean reason to expect non-VT graphs can undercut VT ones
on c:

**Lovász theta identity.** For any vertex-transitive G,
  `θ(G) = α(G)`.
That is, the Lovász SDP is *tight* on VT graphs.

For generic (non-VT) G, typically `θ(G) > α(G)` — the SDP is a loose
upper bound, and the true α is strictly smaller than the symmetry
would allow. Smaller α at fixed d is precisely what lowers c. So:

- VT graphs sit *on* the θ-surface.
- Non-VT graphs can sit *below* the θ-surface.
- c minimization lives where α is smallest.
- Therefore non-VT space has points strictly below the VT floor.

The open question is whether those points are K₄-free. For N=14 and
N=15 empirically yes (SAT found them). For N=17, A-true would say no
in Cayley; non-Cayley is still unchecked.

Concretely, for P(17) itself: Hoffman's eigenvalue bound is tight
(`α(P(17)) = 3 = (17+√17)/... integer rounded`). Any perturbation of
P(17) that breaks vertex-transitivity relaxes Hoffman by a
non-vanishing amount — i.e., the new graph's eigenvalues don't cleanly
govern α, and α could be smaller.

## 4. Specific search strategy shifts

If Conjecture A/B/C are proved (or strongly expected):

1. **Stop Cayley tabu at 17k.** 17, 34, 51, 68, 85 all share the
   ceiling; further compute there is wasted.

2. **Focus non-Cayley search on 17k.** Highest-value targets: N=34
   (smallest non-trivial), then 51, 68, 85. If any of these break
   0.6789 via SAT / full-bitvector tabu / PatternBoost, you have
   both a new best c AND an explicit witness that the VT ceiling is
   not the true ceiling.

3. **The "directional clarity" payoff.** Every non-trivial search at
   17k should be non-VT. This changes the composition of the
   project's compute budget — no more Cayley restarts at those N.

4. **Generalize the exhaustive argument.** The proof technique
   (orbit-reduced enumeration + α-certification) extends:
   - Other group families of the same order (e.g. D_17 at N=34).
   - Other bad-N groups (Z_19k for CR(19), etc).
   - Eventually: a *framework* for certifying VT-ceilings at any N.

5. **Concrete experimental benchmark.** Run SAT-exact at N=34 with a
   budget big enough to certify whether c < 0.679 exists anywhere in
   the full (34 choose 2) = 561-bit edge space. If yes → new record
   and counter to any "VT is globally best" folk belief. If no →
   strong evidence Conjecture B/C extends to the full non-VT family
   at N=34.

## 5. What A/B/C proofs do NOT settle

- **Asymptotic c.** The lim inf of c as N → ∞ might be strictly below
  0.6789, achievable only by non-Cayley-for-large-N sequences. A-C at
  finite N are compatible with this.

- **Non-Paley Cayley at non-17k N.** Conjecture A at k=1..5 is about
  multiples of 17. At N=19k, CR(19) (c=0.7050) plays the analogous
  role; a separate A'-B'-C' for 19k is needed. Similarly for any
  Cayley family that sits at a c-floor.

- **Asymmetric lifts.** Take k·P(17) and add a small number of
  cross-layer edges to break vertex-transitivity. The result is no
  longer Cayley but retains most of the P(17) structure. A/B/C say
  nothing about this space. It's a plausible place to find sub-0.6789
  hits.

- **Non-ZVT vertex-transitive graphs.** A/B are about Cayley. C is
  about VT. "Non-Cayley VT" — e.g., Higman-Sims, Petersen-type graphs
  built from pairs — is not covered by A/B but is by C.

## 6. The honest upshot

Proving A/B/C does not tell us how to beat Paley. It tells us:

- *Where* to stop looking: group-invariant graphs at multiples of 17.
- *Where* to start looking: non-VT graphs, especially at N=34 first.
- *What* benchmark to run: SAT-exact / full-bitvector search at N=34
  with a definitive stopping rule (c = 0.6789 is the target to beat).

The theorem removes a search direction and sharpens the frontier. The
breakthrough construction (if it exists) is still combinatorial and
has to be found.

## 7. Current status of A/B/C proofs

From `P17_LIFT_OPTIMALITY.md` Results section:

- **A verified for k=1 (N=17)** — 15 K₄-free orbits, P(17) the unique
  minimizer at c = 0.6789.
- **A verified for k=2 (N=34, cyclic Z_34 only)** — 1,338 K₄-free
  orbits, k=2 lift of P(17) the unique minimizer.
- **A verified for k=3 (N=51, Z_51)** — 41,162 K₄-free orbits, k=3
  lift of P(17) the unique minimizer.
- **D_17 at N=34** (other group of order 34) — **exhaustively
  verified 2026-04-21** via `scripts/verify_dihedral.py`. 2²⁵ symmetric
  subsets, 131,659 Aut(D_17)-orbits (|Aut| = 272), 5,724 K₄-free,
  **unique c-minimizer at 0.678915** = rotation-only k=2 lift of P(17).
  Combined with cyclic k=2, this closes **Conjecture B at k=2** for
  order 34: both groups of order 34 have the P(17)-lift as unique
  minimizer. 340s runtime.
- **Conjecture B at k=3 (N=51) — closed trivially, 2026-04-23.** There
  is no non-abelian group of order 51: |G|=51=3·17, Sylow-17 normal,
  and φ: Z_3 → Aut(Z_17)=Z_16 must be trivial since 3 ∤ 16, so G = Z_51
  (verified independently via GAP: `NrSmallGroups(51) = 1`, structure
  `C51`). The cyclic-Z_51 exhaustive verification (41,162 K₄-free
  orbits, P(17)-lift the unique minimizer) therefore closes B at k=3.
  Earlier drafts of this doc and `P17_LIFT_OPTIMALITY.md` claimed a
  "Z_17 ⋊ Z_3" as a second group of order 51 — that was a factual
  error; corrected here.
- **B at other orders, C** — require flag algebra / SDP work. Out of
  current scope.

### Other lift-tower families

The same exhaustive-verification technique applies to any cyclic
Cayley family where a "base" construction lifts cleanly via CRT.
Three families verified so far (source='cyclic_exhaustive_min' in
graph_db):

| Family | Base N | d | c     | k verified |
|--------|--------|---|-------|-----------|
| P(17)  | 17     | 8 | 0.6789 | k ∈ {1, 2, 3}|
| N=22   | 22     | 8 | 0.6995 | k ∈ {1, 2}    |
| CR(19) | 19     | 6 | 0.7050 | k ∈ {1, 2}    |

**P(17)** is the Paley graph on Z_17 (QR_17). **CR(19)** is the
cubic-residue Cayley graph on Z_19 ({1,7,8,11,12,18}). **N=22** is
*not* algebraic — base is `Cay(Z_22, {1,2,8,9} ∪ {13,14,20,21})`.
N=22 isn't a Paley N (11 ≡ 3 mod 4 so P(11) doesn't exist), yet the
k-lift phenomenon still holds exactly. So the lift-tower structure
isn't specific to algebraic constructions.

For each family and each verified k, the result is: the k-lift of
the base is the **unique cyclic minimizer on Z_{kN}** up to (Z_{kN})*
action. This is a strict lower bound — no sub-family-c cyclic
Cayley construction exists at those orders.

**Not verified (yet):** k ≥ 3 for N=22 (N=66, 2³² subsets, too big
for plain exhaustive), k ≥ 3 for CR(19) (N=57, 2²⁸, borderline),
k ≥ 4 for P(17) (N=68, 2³³, too big).

So the k-lift phenomenon isn't unique to Paley — any c-floor
construction at base N is a candidate for the same exhaustive
verification at 2N, 3N, ... within budget. The per-family
Conjecture A is the natural statement and is confirmed for all
three above at every tractable k.

## 8. Recommended next actions (ordered by cost vs. payoff)

1. **Finish N=51 cyclic exhaustive.** Already running. Free data point.
2. **Exhaustive D_17 at N=34.** Symmetry-reduced enumeration — probably
   feasible with 30M orbits and tabu-style pruning. Would close B for
   N=34.
3. **SAT-exact at N=17.** Prove c(P(17)) = 0.6789 is the global minimum
   (not just Cayley) at N=17. Small enough that full SAT over (17
   choose 2) = 136 bits is fast with vertex_transitive=False.
4. **SAT-exact at N=34, 51** as scaling allows. This is the direct
   test of "does non-VT beat Cayley here."
5. **If SAT breaks 0.6789 at any 17k:** new construction, new c-floor.
6. **If SAT matches 0.6789 at N=17, 34, 51:** very strong evidence for
   Conjecture C at those N; time to invest in flag algebra for a clean
   proof.

The whole thing is cheap to start and has a clear stopping rule at
each stage.

## 9. Update: SRG catalog screened (2026-04-21) — null

Follow-up experiment complementing §4. Screened McKay's full
strongly-regular-graph enumeration (10 classes, 4,361 graphs) for
K₄-free members beating 0.6789. See `docs/searches/SRG_CATALOG.md` for
the full write-up. Summary:

- 13 K₄-free survivors across all 10 classes.
- **0 beat c = 0.6789.** Best catalog c = 0.9651 (unique Schläfli
  complement, srg(27,10,1,5)).
- Every K₄-free survivor sits at or near Hoffman-tight α — exactly the
  theoretical prediction: strong regularity itself tightens Hoffman,
  so even the non-VT SRGs (e.g. 2 of 10 Paulus graphs) don't dip below
  the θ-surface in practice.

What this closes: SRG-based attacks on P(17) at v ≤ 40 are
empirically exhausted. The non-VT headroom argued in §3 is *real* but
does not realize inside the SRG class. Remaining non-VT directions —
SAT-exact at N=17/34 (§8 step 3–4), asymmetric P(17)-lifts (§5 bullet
3), full-bitvector tabu — are unaffected and remain the active
targets. Survivors persisted under `source='srg_catalog'` for
cross-referencing.
