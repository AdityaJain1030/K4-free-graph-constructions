# SAT_NEAR_REGULAR_NONREG — non-Cayley enumerator

`search/sat_near_regular_nonreg.py` is a CP-SAT enumerator that
returns **K4-free, near-regular, strictly non-regular** graphs at a
fixed `(n, α)`. The point of the "strictly non-regular" constraint
is that every Cayley graph (and therefore every circulant) is forced
d-regular by construction, so any d-regular graph is *automatically*
excluded from the feasible region. What comes out is guaranteed
non-Cayley data.

## Why this exists

Our Cayley/circulant frontier is essentially saturated — see the
`cayley_tabu_gap` sweep (285 rows, full SmallGroups enumeration) and
`frontier_theta` (18 of 100 frontier graphs spectrum-saturated). The
remaining low-hanging fruit sits *outside* Cayley space.

Concrete evidence: at n = 14, 15, 23 the best graphs on our frontier
come from `sat_exact` / `server_sat_exact` and are **non-VT,
near-regular-but-not-regular**:

| n  | c_log  | deg seq                     | source          |
|----|--------|-----------------------------|-----------------|
| 14 | 0.7176 | 12 × deg-6, 2 × deg-5       | sat_exact       |
| 15 | 0.7195 | 12 × deg-7, 3 × deg-6       | sat_exact       |
| 23 | 0.7527 | 19 × deg-4, 4 × deg-3       | server_sat_exact|

No d-regular Cayley graph can land at any of those points (n=15 is
the cleanest argument — 7-regular on 15 vertices is parity-forbidden
since 15·7 is odd). A Cayley tabu search will never find them; this
solver is built to sweep the neighbourhood systematically.

## The model

For fixed `D`:

| constraint        | encoding                                                           | purpose                           |
|-------------------|--------------------------------------------------------------------|-----------------------------------|
| edge vars         | bool `x[i,j]` for `i < j`                                          | the graph                         |
| K4-free           | `bool_or([¬x[·,·]] × 6)` per 4-set                                 | no K4                             |
| near-regular      | aux bool `y[v]`; `Σ_u x[v,u] == D + y[v]`                          | `deg(v) ∈ {D, D+1}`               |
| **non-regular**   | `1 ≤ Σ_v y[v] ≤ n-1`                                               | at least one deg-D and one deg-(D+1) |
| α ≤ alpha         | direct (per (α+1)-subset bool_or) or lazy cuts                     | independence bound                |
| blocking          | one bool_or per already-enumerated labeled solution                 | iso enumeration                   |

Symmetry breaking defaults to **`chain`** — `y[i] ≥ y[i+1]`, i.e. all
deg-(D+1) vertices listed first. This canonicalises the
two-block partition and cuts iso-orbit size without the
row-0-lex gotchas documented in `sat_regular`. Optional
`edge_lex` on row 0 is available but off by default.

## Enumeration loop

Per feasible `D`:

```
while iso_found < max_iso_per_D and labeled < max_labeled_per_D:
    solve model  (with all current blocking clauses)
    if unsat:          break
    if α(G) > α:       add α cut; continue          # lazy mode only
    record G;          block this labeled edge-set
    canonicalise G;    if new iso class, emit
```

Labeled solutions are blocked by a single `bool_or` over flipped
literals; iso-dedup is via `utils.nauty.canonical_id` (one `labelg`
subprocess per graph, cheap relative to a full CP-SAT solve).

The outer `D`-scan has three modes:

| scan_mode       | behaviour                                                  |
|-----------------|------------------------------------------------------------|
| `first`         | stop at the first `D` with ≥1 iso class (default — min-edge region) |
| `k_after_first` | first + k more D values (see `scan_extra_D`)               |
| `all`           | scan `[d_lo, d_hi]` exhaustively                           |

## When to reach for it

- You want many non-VT K4-free graphs at a fixed `(n, α)` — for
  building datasets, feeding a learned model, or sanity-checking
  that the Cayley frontier is locally extremal.
- You want to confirm or refute that the `sat_exact` non-VT winner
  at some `n` is *unique* inside its (D, D+1) band.
- You suspect a hole between the best Cayley and the best overall
  graph at some `n` — this solver searches exactly that hole.

## When NOT to reach for it

- You want the certified min-edge K4-free graph per se — use
  `sat_regular` or `sat_exact`; this solver *excludes* regular
  solutions and so may return a strictly worse graph than
  `sat_regular` at the same `(n, α)` (the d-regular optimum is
  unreachable here by design).
- You want graphs that might be Cayley — by construction, none are.
- Large `n, α` where `C(n, α+1)` blows direct α past the lazy
  threshold AND the iso-orbit is so large that labeled enumeration
  saturates `max_labeled_per_D` without progress. Start small and
  ramp `max_labeled_per_D` / `per_D_timeout_s` only if you see the
  "iso_new" log events slowing.

## Cross-checks

- Every returned graph passes `is_k4_free_nx` (base class does this
  automatically).
- Every returned graph is strictly non-regular (model constraint).
- Every returned graph is therefore non-Cayley (Cayley ⇒ d-regular).
  This is guaranteed by the model, not by a post-filter.
- `canonical_id(G)` is stored in metadata as `iso_canonical_id` and
  matches `graph_id` in `graph_db` on save.

## Params — what to tune and what to leave

| param               | default | tune when                                             |
|---------------------|---------|--------------------------------------------------------|
| `alpha`             | —       | always. choose per-`n` from the DB frontier.          |
| `D`                 | None    | set to override the Ramsey floor scan.                |
| `scan_mode`         | `first` | set `all` if you want a full (D, iso)-matrix.         |
| `max_iso_per_D`     | 20      | raise only if every slot fills every time.            |
| `max_labeled_per_D` | 200     | raise if you see many iso_dup events before cap.      |
| `per_D_timeout_s`   | timeout_s/4 | raise for large `n` (≥ 24 with α ≥ 5).            |
| `symmetry_mode`     | `chain` | leave alone unless benchmarking.                       |

## Known limits

- **Only catches non-regular iso classes.** Non-Cayley-but-regular
  graphs do exist (rare but they do) and are missed here. To get
  those too, drop the `sum(y) ≥ 1 ∧ ≤ n-1` constraints and post-filter
  outputs for non-VT via `pynauty`. The model then reduces to
  `sat_regular` with enumeration.
- **Only catches the "first feasible D" band by default.** With
  `scan_mode="first"` we stop at the min-edge region. For diversity
  across degree bands use `scan_mode="all"`; the cost is roughly
  linear in `d_hi − d_lo`.
- **Iso-orbit blowup.** For `(n, α, D)` where the iso orbit is
  enormous the labeled-solution cap hits before `max_iso_per_D`
  fills. Raise `max_labeled_per_D`, or live with partial coverage.

## Where results land

Results are persisted to `graph_db` under `source="sat_near_regular_nonreg"`
with metadata `{D, alpha_cap, iso_canonical_id, solution_rank,
method, scan_mode, symmetry_mode}`. Query with:

```python
from graph_db import DB
with DB() as db:
    rows = db.query(source="sat_near_regular_nonreg",
                    order_by=["n", "c_log", "solution_rank"])
```

Cross-sourced iso classes (same `graph_id` under multiple `source`
tags) are normal — any `sat_exact` non-VT winner will also appear
here at rank ≥ 1.
