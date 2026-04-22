# `CayleyTabuSearch` — tabu over Cayley-graph connection sets

## What it does

For each group `Γ` of order `N` produced by `search.groups.families_of_order`,
tabu-search over the indicator vector of inversion orbits of `Γ \ {e}`.
Each bit toggles one orbit in/out of the connection set `S`; the state
vector has length `L = |inversion_orbits(Γ)|`, which is roughly `(N-1)/2`
for `ℤ_N` and smaller for groups with more self-inverse elements.

The move set is Hamming-1 on the orbit bitvector. At each step, pick the
lowest-cost allowed neighbour (Parczyk et al., arXiv:2206.04036,
Algorithm 2); the tabu list stores the **last ℓ modified bit indices**,
not full states, so membership testing is O(1) and no hashing is needed.
`multi_restart_tabu` drives `n_restarts` independent random starts per
group and keeps the best.

Per-group best surviving bitvector → `Cay(Γ, S)` → K₄-check → base class
scores top-k by exact `c_log` across all groups of that `N`.

## Why it exists alongside `CayleyResidueSearch`

`cayley.py` only builds `Cay(ℤ_p, R_k)` for `k ∈ {2, 3, 6}` at primes
`p ≡ 1 (mod 2k)`. The connection set is fixed by the algebra — a single
graph per `(p, k)`. That covers the Paley / cubic-residue / sextic-residue
extremizers but leaves the rest of the Cayley-graph search space
untouched.

`cayley_tabu.py` is the **general** Cayley search:

- any group `Γ` of order `N` (not just `ℤ_p`),
- any symmetric connection set (not just a residue subgroup),
- any `N` (composite allowed, non-prime explicitly in scope).

So it subsumes `CayleyResidueSearch` in principle and is the entry point
for Cayley-graph exploration past `N = 35`, where exhaustive circulants
are infeasible (see `circulant/CIRCULANTS.md`).

## Supported group families

From `search/groups.py::families_of_order(N)`:

| Family               | When applicable    | Notes                                      |
|----------------------|--------------------|--------------------------------------------|
| `ℤ_N` (cyclic)       | always             | Reproduces the circulant search space.     |
| `D_{N/2}` (dihedral) | `N` even, `N ≥ 4`  | Includes reflections; non-abelian.         |
| `ℤ_a × ℤ_b`          | every `a · b = N`  | Direct products; `a ≤ b`, `a ≥ 2`.         |
| `ℤ_2^k`              | `N = 2^k`, `k ≥ 2` | Elementary abelian.                        |
| `ℤ_3 × ℤ_2^k`        | `N = 3 · 2^k`      | Parczyk's empirical sweet-spot family.     |

Groups are represented as lightweight Python closures (op, inverse)
over hashable elements — no GAP/SageMath dependency. The
`inversion_orbits` of `Γ \ {e}` (orbits under `g ↦ g⁻¹`) are
precomputed and are exactly the atoms the search parametrises over, so
every candidate is automatically symmetric (`S = -S`) and the resulting
Cayley graph is undirected by construction.

## Cost function — surrogate `c_log`

```
cost(bits) = +inf                           if empty S
           = +inf                           if d_max ≤ 1
           = +inf                           if Cay(Γ, S) contains a K₄
           = α_lb · d_max / (N · ln d_max)  otherwise
```

Where `α_lb = utils.alpha_surrogate.alpha_lb(adj, restarts=lb_restarts)`
is random-restart greedy MIS, a **lower bound** on `α(G)`. This makes
the surrogate a lower bound on true `c_log` — optimistic, but:

- graphs with small true `α` tend to have small `α_lb`, so ranking is
  approximately preserved;
- Cayley graphs are vertex-transitive, and for vertex-transitive graphs
  `α_lb` is often exact when a greedy restart happens to start from an
  MIS vertex, so the signal is sharp;
- restarts inside `α_lb` smooth out greedy-MIS variance.

The surrogate is a **ranking signal** only. Final candidates are
re-scored with exact α (see next section).

## Exact α at scoring time

`CayleyTabuSearch._alpha_of` overrides the base default to
`utils.graph_props.alpha_bb_clique_cover` (B&B clique-cover solver)
rather than CP-SAT. Per the repo's α-solver policy: every call site
names its solver explicitly. The choice is deliberate — Cayley graphs
are vertex-transitive and sparse K₄-free, which is the regime where B&B
clique-cover is fastest and doesn't need the CP-SAT hammer.

## Tabu-search defaults and why

| kwarg          | default | notes                                                           |
|----------------|---------|-----------------------------------------------------------------|
| `n_iters`      | 300     | Tabu iterations per restart.                                    |
| `n_restarts`   | 3       | Restarts per group.                                             |
| `tabu_len`     | `L//4`  | Length of the modified-bits deque.                              |
| `lb_restarts`  | 24      | Greedy-MIS restarts per cost eval.                              |
| `time_limit_s` | None    | Wall-clock cap per group; shared across restarts.               |
| `groups`       | None    | Restrict to a list of group names (default: all of `N`).        |

Two non-obvious choices baked into `search/tabu.py`:

- **Sparse random init.** Starting states pick only 1–3 bits rather
  than `L/2`. Dense random starts tend to be K₄-full for Cayley-graph
  cost functions, leaving every Hamming-1 neighbour also K₄-full and
  stalling the search immediately. Sparse init sidesteps this.
- **Random kick on all-infeasible neighbourhoods.** If every allowed
  flip is `+inf`, take a random allowed flip anyway so the search
  doesn't freeze in an infeasible pocket.

## Metadata attached per graph

```
{
  "group": "<Γ.name>",
  "connection_set": [...],      # list of group elements in S
  "surrogate_c_log": <float>,   # α_lb · d_max / (N·ln d_max)
  "tabu_n_iters": <int>,
  "tabu_best_iter": <int>,
}
```

`surrogate_c_log` is retained for diagnostics — compare against the
exact `c_log` (stored canonically in `cache.db` by `DB.sync`) to see
how tight the `α_lb` bound was.

## Driver

```
micromamba run -n k4free python scripts/run_cayley_tabu.py \
    --n-lo 10 --n-hi 40 \
    --n-iters 300 --n-restarts 3 \
    --time-limit 90 --top-k 3
```

Writes to `graphs/cayley_tabu.json` via `GraphStore` under
`source='cayley_tabu'`. The `--better-only` flag reads the existing
best-per-N from the db and skips persistence when the new run doesn't
improve it. Ad-hoc re-ingest from `results/cayley_tabu/` is available
via `scripts/persist_cayley_tabu.py`.

`scripts/compare_cayley_tabu.py` writes `results/cayley_tabu/comparison.md`
— a per-N table of best `cayley_tabu` c_log vs best non-tabu baseline,
with verdicts (`tabu BEATS baseline` / `match` / `baseline better` /
`no baseline`) and source attribution.

## Caveats

### 1. Surrogate can mis-rank

`α_lb ≤ α`, so two graphs with the same `α_lb` may differ in true `α`.
Top-k by surrogate is then re-sorted by exact α at the end, but graphs
with a *sharp* true `α` slightly above the surrogate can be pruned
before they ever reach the exact re-score. If a promising group is
missing from `cayley_tabu.json`, raise `top_k` before raising
`n_iters` / `n_restarts`.

### 2. Cost is O(L) per step

Every Hamming-1 neighbour triggers a fresh adjacency build
(`cayley_adj_from_bitvec`), a K₄-check, and a greedy-MIS bracket. The
K₄-check and MIS are the cost — both O(N²) to O(N³). For `L` up to
~25 (e.g. `N=50` cyclic) and `n_iters=300, n_restarts=3`, each group
costs a few seconds to a minute. `time_limit_s` is the safety valve;
groups with many orbits (dihedral, direct products) hit it first.

### 3. Overlap with `CirculantSearchFast`

`ℤ_N` is always in the family list, so every cyclic Cayley graph this
search finds is also reachable by `CirculantSearchFast` (for `N` past
the exhaustive `CirculantSearch` cutoff). Dedup is by
`(canonical_id, source)`, so the same graph may appear under both
sources — by design. The value of `cayley_tabu` at cyclic `N` is the
algebraic metadata (`group`, `connection_set`), not graph novelty.

### 4. Tabu ≠ optimum

Tabu gives a local optimum under Hamming-1 moves on orbits. It does
**not** certify anything. For optimality at a given `(N, α)` use
`SATExact` / `SATRegular`. For Cayley graphs specifically, the
comparison in `results/cayley_tabu/comparison.md` is the operational
proxy — it just tells you whether the tabu result is worse/better than
the best non-tabu graph currently in the db, not whether it's
globally optimal.

### 5. Families are a chosen subset, not all groups of order N

`families_of_order` enumerates only the families listed in the table
above. Small groups outside that list (`S_3` at `N=6`, non-abelian
orders > 8 past `D_m`, the quaternion group `Q_8`, etc.) are not
searched. The choice is deliberate — Parczyk et al.'s sweet spot plus
the classical extremizers — but means this search does not claim to
cover "all Cayley graphs on N vertices."

## When to reach for it

- You want Cayley-graph candidates for `N ∈ [35, ~100]` where
  `CirculantSearch` can't run exhaustively and `CayleyResidueSearch`
  only hits primes.
- You want non-abelian Cayley-graph candidates (dihedral,
  direct-product non-cyclic).
- You're probing whether small groups beyond `ℤ_p` give better
  residue-like extremizers at composite `N`.

## When **not** to reach for it

- `N ≤ 35`, cyclic-only — `CirculantSearch` already enumerates that
  space exhaustively.
- Primes with residue-graph interest — `CayleyResidueSearch` builds
  `Cay(ℤ_p, R_k)` deterministically in O(1) per prime, no search loop.
- You need optimality — use `SATExact` / `SATRegular`.
