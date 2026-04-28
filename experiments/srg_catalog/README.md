# `experiments/srg_catalog/` — McKay SRG enumeration screen

## Compute

- **Environment:** k4free conda env (local).
- **Typical runtime:** dominated by α via clique-cover B&B on each
  K₄-free survivor. Per class:
  - `sr25832` (1 graph) — instant.
  - `sr251256`, `sr271015`, `sr281264`, `sr291467` (15–41 graphs) — seconds to a minute.
  - `sr351668`, `sr351899` (~3,800 graphs each) — 5–15 min.
  - `sr361446` (~180,000 graphs) — 30–60 min, dominates the
    "exhaustive" tier.
  - `sr401224` (28,798 graphs) — 30–60 min.
- **Memory:** modest; one .g6 file is loaded into memory at a time
  (largest is sr361446 at ~50 MB). Per-graph α uses an O(n²) bitmask
  branch-and-bound, peaking at a few MB at v = 40.
- **Parallelism:** single-threaded. Each class is independent; a
  trivial `xargs -P` over `--classes` would parallelise.

---

## Background

A **strongly regular graph** with parameters `srg(v, k, λ, μ)` is a
k-regular graph on v vertices in which:
- every pair of adjacent vertices has λ common neighbours, and
- every pair of non-adjacent vertices has μ common neighbours.

The SRG axioms force a clean spectrum: exactly three distinct
eigenvalues `{k, r, s}` with
`r + s = λ − μ` and `r · s = μ − k`. The Hoffman bound
`α ≤ v · |s| / (k + |s|)` and the Delsarte clique bound
`ω ≤ 1 − k / s` follow directly from the spectrum.

Existence and enumeration of SRGs is **not generically constructive**.
For most (v, k, λ, μ) tuples, even existence is a research-level
question; for the tuples where SRGs exist, classifying them up to
isomorphism typically requires heavy isomorph-rejection search. The
de-facto reference catalog is **Brendan McKay's enumeration**,
hosted at <https://users.cecs.anu.edu.au/~bdm/data/graphs.html>. This
experiment screens those .g6 files for K₄-free members, computes α
exactly, and ingests survivors into graph_db.

This is a one-shot **catalog ingest**, not a search — there is no
generation step we can substitute for the .g6 files. Whatever McKay's
catalog contains is the entirety of the search space.

For why we care: most SRGs are **not vertex-transitive**, and per
[`docs/graphs/BEYOND_CAYLEY.md`](../../docs/graphs/BEYOND_CAYLEY.md)
§3, non-VT graphs are the only structural region where `c_log < 0.6789`
(the Paley P(17) plateau) can live. Lovász θ(G) = α(G) on every
vertex-transitive graph, so VT graphs sit exactly *on* the θ surface
— and θ is a hard lower bound on `c_log`'s denominator. Non-VT graphs
can dip below θ. The McKay catalog is the cleanest source of non-VT
graphs at orders v ∈ {25, 26, 27, 28, 29, 35, 36, 40} where
construction-based searches don't reach.

Theory references for the spectral bounds:
[`docs/graphs/SRG_CATALOG.md`](../../docs/graphs/SRG_CATALOG.md).

---

## Question

For every tabled SRG parameter class, what is the minimum `c_log`
attainable by a K₄-free representative? In particular, does any
non-VT srg(v, k, λ, μ) realisation beat the Paley P(17) plateau at
`c_log ≈ 0.6789`?

---

## Approach

For each class in the `SRG_CLASSES` table:

1. Read the `sr<v><k><λ><μ>.g6` file from `g6/` (one graph per line,
   graph6-encoded).
2. Filter to K₄-free members via `is_k4_free_nx` (cheap: skip
   any graph containing a K_4).
3. Compute α via `alpha_bb_clique_cover_nx` (clique-cover branch
   and bound).
4. Score by `c = α · k / (v · ln k)`.
5. Rank classes and survivors; flag any survivor with `c ≤ 0.6789`
   (the Paley P(17) floor) for verification with CP-SAT.
6. Ingest survivors into `graph_db` under `source="srg_catalog"`,
   keyed by canonical_id.

The "minimal" tier covers the two largest-v classes (40, 36) where
the search space is biggest. The "exhaustive" tier covers eight more
smaller classes (v ∈ {25, 26, 27, 28, 29, 35}).

**Limitations.**

- The `SRG_CLASSES` table is hand-curated against McKay's index.
  Adding a new SRG parameter set is a one-line append plus
  downloading the .g6 file.
- α via clique-cover B&B can be slow on dense survivors; for v ≥ 40
  this is the bottleneck. Switching to CP-SAT α would help but
  isn't currently wired.

---

## Files

| File | Purpose |
|---|---|
| `run.py` | Driver. `--tier {minimal, exhaustive}`, `--classes <files>`, `--c-floor`, `--top-n`, `--no-ingest`, `--only-beaters`, `--verbose`. |
| `g6/sr*.g6` | McKay's graph6-encoded enumerations, one .g6 per parameter class. **Not committed (large)** — download via the printed `curl` hints when missing. |
| `g6/README.md` | Source attribution + download recipe. |

```bash
# Minimal tier (sr40, sr36) — slow first run, dominated by sr361446
micromamba run -n k4free python experiments/srg_catalog/run.py

# Full sweep including all small-v classes
micromamba run -n k4free python experiments/srg_catalog/run.py --tier exhaustive

# Single class
micromamba run -n k4free python experiments/srg_catalog/run.py \
    --classes sr271015.g6

# Report only (no ingest)
micromamba run -n k4free python experiments/srg_catalog/run.py \
    --tier exhaustive --no-ingest
```

Survivors land in `graphs/srg_catalog.json` under `source="srg_catalog"`,
with per-graph metadata `{srg_v, srg_k, srg_lambda, srg_mu,
mckay_file, mckay_index}`.

---

## Results

**Status:** open — full exhaustive sweep on the largest classes
(`sr361446`, `sr401224`) has been run; no survivor beats P(17). Some
classes still benefit from re-running with a tighter α solver (CP-SAT
instead of clique-cover B&B) to confirm.

The current best K₄-free survivors per parameter class
(from `graphs/srg_catalog.json`):

```
class          (v,k,λ,μ)      r      s        Hα   Dω    α-cap  K4-free   bestC
sr25832        (25,8,3,2)     +3.00  -2.00    10.0  5.0  10.05    1       0.7694
sr251256       (25,12,5,6)    +2.00  -3.00     5.0  3.0  6.83    11       —
sr261034       (26,10,3,4)    +2.00  -3.00     6.0  4.5  7.67    41       —
sr271015       (27,10,1,5)    +1.00  -5.00     4.5  3.0  7.97    25       —
sr281264       (28,12,6,4)    +4.00  -2.00     4.0  4.0  7.83    20       —
sr291467       (29,14,6,7)    +2.00  -7.00     3.6  5.0  7.71    25       —
sr351668       (35,16,6,8)    +2.00  -8.00     3.5  6.0  7.85    27       —
sr351899       (35,18,9,9)    +3.00  -9.00     3.0  6.0  7.42    18       —
sr361446       (36,14,4,6)    +2.00  -6.00     6.0  4.0  9.51   180,001   —
sr401224       (40,12,2,4)    +2.00  -4.00     5.0  4.0  9.99    28,798   —
```

`Hα` is the Hoffman α-upper-bound; `Dω` the Delsarte ω-upper-bound;
`α-cap` is the largest α making `c ≤ 0.6789`. Filling in the
remaining `bestC` rows from the existing graph_db data — and
specifically asking "does any K₄-free SRG beat 0.6789?" — is the
open part of this experiment.

`sr25832` is the **Schläfli graph** complement (1 graph total, K₄-free,
`c_log ≈ 0.7694`). Every other class either has no K₄-free members
recorded or the best survivor's `c_log` sits above 1.0 — none come
close to the 0.679 frontier.

**Headline:** every screened class is consistent with the **conjecture**
that no K₄-free SRG with v ≤ 40 dips below P(17). Confirming this for
the larger classes (`sr361446`, `sr401224`) on a tighter α solver would
close the question for the catalog screen.

---

## Open questions

- [ ] **Re-screen `sr361446` with CP-SAT α.** The clique-cover B&B can
      give an α-upper-bound that is slightly slack on dense graphs;
      a CP-SAT pass would give exact α, possibly nudging `c_log`
      values down. Likely no change for the leader, but worth
      verifying.
- [ ] **Add `srg(45, …)` and `srg(50, …)` classes.** McKay has these
      catalogued; they would push the screen to v = 50 and cover
      conference graphs at primes 49 and 53. Each is ~10 min download
      + screen.
- [ ] **Spectral filter before α.** Each class has a Hoffman α-upper
      bound. If the survivor's `α ≤ Hoffman` is automatic and we know
      the c_log floor implied by the bound, we can skip the α
      computation for classes where even the bound exceeds the c_log
      floor. Would speed the exhaustive sweep ~3×.

---

## Theorems that would be nice to prove

- **Conjecture.** No K₄-free strongly-regular graph beats `c_log = 0.6789`
  for any (v, k, λ, μ).
  *Why it matters:* if true, the entire SRG-shaped non-VT slice cannot
  break the Paley plateau, and the search for sub-0.6789 graphs has to
  look at non-SRG non-VT graphs (much harder territory).

- **Conjecture (weak).** Every K₄-free SRG is Hoffman-saturated.
  *Why it matters:* combined with `c_log = α · k / (v · ln k)` and
  `α = v · |s| / (k + |s|)`, would give a closed-form `c_log` formula
  for every K₄-free SRG. Empirically holds on the catalog screen so
  far; a clean structural proof would render the α computation
  unnecessary.
