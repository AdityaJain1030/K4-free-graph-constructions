# `srg_catalog` — McKay SRG catalog screen

## What this screen is

One-shot ingest of McKay's strongly-regular-graph enumeration. For each
class `srg(v, k, λ, μ)` in `scripts/run_srg_screen.py::SRG_CLASSES`, the
script reads the `.g6` file under `graphs_src/srg_catalog/`, filters to
K₄-free members, computes exact α via `alpha_bb_clique_cover_nx`, ranks
by `c = α·k / (v·ln k)`, and appends survivors to `graphs/srg_catalog.json`
under `source="srg_catalog"`.

Unlike every other entry in `search/`, this isn't a `Search` subclass and
doesn't take an `N` parameter. It's a literature-ingest pipeline —
mirrors the pattern of `run_mattheus_verstraete.py`: import an explicit
external construction family, screen once, persist.

## Why it exists

`BEYOND_CAYLEY.md §3` observes that Lovász θ(G) = α(G) on every
vertex-transitive graph, so VT graphs sit *on* the θ-surface. Generic
graphs have θ(G) > α(G) — they can sit *below* the surface, and small α
is exactly what lowers c. Our Cayley-tabu / circulant / cayley_residue
searches are all VT-constrained by construction, so they structurally
cannot reach the sub-θ region.

The McKay SRG catalog is the largest cheaply-enumerable source of
K₄-free candidates that includes **non-VT** members (e.g. most of
srg(40,12,2,4), all 10 Paulus graphs srg(26,10,3,4), etc.). Screening it
tests whether the theoretical sub-θ headroom actually yields a
sub-Paley graph anywhere in the literature.

Complementary to `docs/theory/PARCZYK_PIPELINE.md` (structured VT search)
and orthogonal to `CAYLEY_TABU.md` (same objective, different search
space).

## The SRG K₄-free filter

For srg(v, k, λ, μ):

- **λ = 0** → K₄-free by construction (triangle-free).
- **λ = 1** → K₄-free by construction (every edge in one triangle, no
  room for a 4th vertex adjacent to all three).
- **λ = 2** → K₄-free iff ω ≤ 3. Must check per graph.
- **λ ≥ 3** → K₄-possible. The bound `ω ≤ 1 − k/s` (Delsarte, with `s`
  the smallest eigenvalue) determines whether any member can be
  K₄-free; most λ ≥ 6 classes have `ω` bound > 3 and are empirically
  all K₄-hit.

The screen does not skip any class by pre-filter; it reports Hoffman α
upper, Delsarte ω upper, and the α-threshold for beating `c_floor` per
class, then runs the per-graph K₄ check anyway. This keeps the screen
honest and generates class-level data even for null classes.

## Classes covered

Filename convention on McKay's site: `sr{v}{k}{λ}{μ}.g6` (digits
concatenated). All files from <https://users.cecs.anu.edu.au/~bdm/data/>.

### Minimal tier

| File            | params          | graphs | why                                         |
|-----------------|-----------------|--------|---------------------------------------------|
| `sr401224.g6`   | srg(40,12,2,4)  |     28 | GQ(3,3) family; Delsarte ω ≤ 4 leaves room  |
| `sr361446.g6`   | srg(36,14,4,6)  |    180 | λ=4 but ω ≤ 4.5 leaves K₄-free possible     |

### Exhaustive tier

| File            | params          | graphs | comment                                  |
|-----------------|-----------------|--------|------------------------------------------|
| `sr351668.g6`   | srg(35,16,6,8)  |  3,854 | λ=6, expected 0 K₄-free                 |
| `sr351899.g6`   | srg(35,18,9,9)  |    227 | conference-like, λ=9                    |
| `sr271015.g6`   | srg(27,10,1,5)  |      1 | unique Schläfli complement              |
| `sr281264.g6`   | srg(28,12,6,4)  |      4 |                                         |
| `sr261034.g6`   | srg(26,10,3,4)  |     10 | 10 Paulus graphs, self-complementary    |
| `sr291467.g6`   | srg(29,14,6,7)  |     41 | conference, expect all K₄               |
| `sr25832.g6`    | srg(25,8,3,2)   |      1 |                                         |
| `sr251256.g6`   | srg(25,12,5,6)  |     15 | conference                              |

Conspicuous absences: Shrikhande srg(16,6,2,2), Clebsch srg(16,5,0,2),
Hoffman–Singleton, Higman–Sims — these are unique graphs on their
parameters and not hosted as `.g6` files on McKay's catalog page. Add
them by direct construction if wanted; they are already dominated by
cheaper-to-beat candidates in other sources, so v1 omits them.

## What the screen actually does

`scripts/run_srg_screen.py::main`:

1. Parse `--tier {minimal, exhaustive}` or `--classes <file>*`.
2. For each class: load `.g6` file; for each graph in file:
   - K₄-check via `utils.graph_props.is_k4_free_nx` (fast bitmask
     common-neighborhood intersection).
   - If K₄-free: α via `alpha_bb_clique_cover_nx` (branch-and-bound with
     clique-cover upper bound; fast on sparse K₄-free at v ≤ 40).
   - Compute `c = c_log_value(α, v, k)`.
3. Print per-class summary (eigenvalues, Hoffman α-upper, Delsarte
   ω-upper, α-threshold for beating `c_floor`, counts, best c per class).
4. Print top-N survivors across all classes, flag any c ≤ c_floor.
5. `ingest()`: canonicalize each survivor via
   `graph_db.encoding.canonical_id` (nauty `labelg`) and `write_batch`
   to `graphs/srg_catalog.json`. Dedup on `(id, source)` so re-running
   is idempotent.

Flags: `--no-ingest` (report only), `--only-beaters` (ingest only
c ≤ floor instead of all K₄-free survivors), `--c-floor` (default 0.6789).

## Results (2026-04-21 run)

**4,361 SRGs screened, 13 K₄-free survivors, 0 beat c = 0.6789.**
Best catalog c = 0.9651 (srg(27,10,1,5), the unique Schläfli
complement). All 13 survivors persisted to `graphs/srg_catalog.json`.

Per-class:

| class          | N     | K₄-free | best c  | note                                         |
|----------------|-------|---------|---------|----------------------------------------------|
| srg(40,12,2,4) |    28 |       1 | 1.2073  | GQ(3,3), α = 10 = Hoffman-tight              |
| srg(36,14,4,6) |   180 |       9 | 1.0315  | all α = 7, near Hoffman (= 8)                |
| srg(35,16,6,8) | 3,854 |       0 | —       | λ = 6 forces K₄ everywhere, as expected      |
| srg(35,18,9,9) |   227 |       0 | —       | λ = 9, totally dense                         |
| srg(27,10,1,5) |     1 |       1 | 0.9651  | Schläfli complement, unique                  |
| srg(26,10,3,4) |    10 |       2 | 1.0022  | 2 of 10 Paulus graphs are K₄-free (see note) |
| srg(28,12,6,4) |     4 |       0 | —       |                                              |
| srg(29,14,6,7) |    41 |       0 | —       | conference, all K₄-hit                       |
| srg(25,8,3,2)  |     1 |       0 | —       |                                              |
| srg(25,12,5,6) |    15 |       0 | —       | conference                                   |

**Empirical pattern confirmed**: every K₄-free SRG survivor in the
catalog hits α at or near Hoffman-tight. SRGs always sit on the
θ-surface (θ = α for VT, and while not every SRG is VT, their highly
symmetric spectrum makes the Hoffman bound nearly sharp on those that
are K₄-free). That's why their c is stuck — the theoretical "non-VT can
dip below θ" headroom does not realise at these finite v.

**Correction to an earlier prediction**: the `R(4,4) = 18` argument
("every self-complementary graph on ≥ 18 vertices contains K₄") was
*over-applied* to the 10 Paulus graphs srg(26,10,3,4). Ramsey's theorem
forces a monochromatic K₄ in *the pair* `(G, \bar G)`, not in `G`
alone. Two Paulus graphs (indices 1 and 2 in the McKay file) are
genuinely K₄-free. Both have α = 6, c = 1.00 — still far above the
Paley floor, so the null-result conclusion stands.

## What this closes

The literature-catalogued SRG space at v ≤ 40 does **not** contain a
sub-0.6789 K₄-free graph. Any future attack via "find an SRG that beats
Paley" would need either:

- an SRG at v > 40 not yet in the catalog, **or**
- a non-SRG graph (i.e. drop strong regularity; accept that α may no
  longer be Hoffman-tight, which is exactly the headroom we want).

The second is the natural next step. Candidates per `BEYOND_CAYLEY.md §4`:

- **SAT-exact at N = 17, 34, 51.** Proves global (not just VT) minimum.
- **Asymmetric P(17)-lifts.** Take `k · P(17)`, add a small number of
  cross-layer edges to break vertex-transitivity. No longer Cayley,
  keeps most of the P(17) structure.
- **Full-bitvector tabu at N ∈ {17, 34}** without the Cayley symmetry
  restriction.

## Caveats — read before re-running

### 1. Don't re-run at these orders

The McKay catalog is static and the screen is exhaustive over what
McKay publishes. Re-running produces the same 13 survivors. Use
`--only-beaters` + a tighter `--c-floor` if you want to re-screen with
a different target.

### 2. `graphs_src/` is gitignored

Raw `.g6` files live under `graphs_src/srg_catalog/` and are not
versioned — they are third-party data and the script re-downloads on
demand. Only the derived `graphs/srg_catalog.json` is committed.

### 3. `alpha_bb_clique_cover` scales poorly past v ≈ 50

Fine for all current SRG classes (v ≤ 40). Adding catalog classes at
v ≥ 64 (e.g. srg(64,18,2,6)) would need an α-time budget check or
CP-SAT fallback.

### 4. Catalog does not cover unique/sporadic srg

Shrikhande, Clebsch, Hoffman–Singleton, Gewirtz, Higman–Sims, etc. are
not on McKay's file list (they're noted as unique and hosted elsewhere).
If we wanted full literature coverage, construct them directly and
ingest under `source="srg_sporadic"` as a sibling one-shot script. None
are expected to beat P(17) — see the c-value table in the user-analysis
conversation preserved in `BEYOND_CAYLEY.md`.

## When to reach for it

- You want to check whether a newly-announced SRG catalog extension
  (new v, or a previously-thought-complete class reopened) contains a
  sub-Paley K₄-free graph.
- You want a clean, citable negative baseline for "no SRG beats P(17)
  at v ≤ 40".
- You are verifying that `graph_db` canonical-id deduplication correctly
  collapses SRG survivors that also appear under `source='cayley'` or
  `'circulant'` (e.g. the GQ(3,3) might be reachable as a Cayley graph
  on some order-40 group).

## When **not** to reach for it

- You want to *beat* 0.6789. The screen's answer is no, it can't.
- You want non-VT graphs at v > 40. McKay doesn't publish them and
  exhaustive SRG enumeration is open past v ≈ 64 anyway.
- You want irregular or sparse graphs. SRGs are exactly-regular by
  definition.

## Open questions

1. **Is every K₄-free SRG at v ≤ 40 exactly Hoffman-tight?** The 13
   survivors are all Hoffman-tight or one below (e.g. srg(36,14,4,6)
   α = 7, Hoffman = 8). A "generic" SRG with α < Hoffman would be
   surprising and worth isolating if one exists in a larger catalog.

2. **Does the GQ(3,3) survivor appear under any other source?** It's
   the unique K₄-free srg(40,12,2,4); some of its automorphism group
   quotients might be circulants. Worth a `graph_db` cross-source
   lookup on `id = 03a364de57c3...`.

3. **Paulus K₄-free classes beyond v = 26?** The analogous conference
   construction at v = 37, 41, 45, … may contain K₄-free members that
   aren't in McKay's file (which only lists the strict conference
   class). Low priority — they'd inherit the same Hoffman-tight
   pattern.
