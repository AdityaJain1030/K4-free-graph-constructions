# Refactor notes

Captured from a working discussion about cleaning up `search/` and the
walk-family abstraction. Nothing here is committed work — it's the plan
to come back to.

---

## TL;DR

1. **`search/` is misnamed.** Only ~50% of its contents are actually
   searches. Rename to `generators/` (or similar) — the contents share
   the property "produces K4-free graph candidates", not "searches."
2. **The `Search` base class is already paradigm-neutral.** Rename is
   cosmetic — base.py has no search-specific logic, just search-flavored
   naming.
3. **Extract a `Walk` parent** for walk-shaped searches. Three concrete
   subclasses (per-edge, 2-switch, bitvec) cover ~7 existing classes.
4. **Don't pre-factor.** Build `SwitchWalkSearch` as a sibling of
   `RandomWalkSearch` first; extract `Walk` after the second concrete
   example exists. The contract design needs two examples to triangulate.

---

## 1. Folder rename: `search/` → `generators/`

### Why

What's actually in `search/`:

| Paradigm | Files | Counts as "search"? |
|---|---|---|
| Walk-family (random/tabu/MCMC) | `random_walk`, `random_regular_switch`, `mcmc`, `switch_tabu`, `bohman_keevash`, `cayley_tabu`, `cayley_tabu_gap`, `alpha_targeted`, `tabu` | yes |
| Enumeration | `circulant`, `circulant_fast`, `brute_force` | yes |
| SAT/ILP | `sat_circulant`, `sat_circulant_exact`, `sat_exact`, `sat_exact_v1`, `sat_near_regular_nonreg`, `sat_regular`, `sat_regular_v1` | yes |
| Algebraic closed-form | `brown`, `cayley` (residue), `mattheus_verstraete`, `norm_graph`, `polarity` | **no** — parameter-driven, no search loop |
| Structural transformation | `blowup`, `mv_bipartization` | **no** — graph-to-graph operators |
| Utilities | `groups`, `groups_gap`, `groups_psl` | **no** — should move to `utils/` |
| Base infra | `base`, `logger` | (infrastructure) |

Algebraic constructions are wrapped in the `Search` base purely for the
framework benefits (timing, c_log scoring, persistence). They don't
"search" anything — they take parameters and return a graph.

### Better name

`generators/` — the unifying property is "generates K4-free graph
candidates." Mechanism (search/construct/transform/enumerate/solve) is
an implementation detail.

### Cost of rename

Cheap. The base class is already paradigm-agnostic (see §2). The change
is mostly find/replace:
- `search/` directory → `generators/`
- `from search import` → `from generators import`
- `Search` class → `Generator` (or keep — see §2)
- `SearchResult` → `GeneratorResult`
- `SearchLogger` → `GeneratorLogger`
- Log event strings `"search_start"` etc. — optional, they're just strings

### Subdivision (after rename)

```
generators/
├── walk/           # Walk parent + concrete walk subclasses
├── algebraic/      # brown, cayley, mattheus_verstraete, norm_graph, polarity
├── enumeration/    # circulant, circulant_fast, brute_force
├── sat/            # sat_*
└── transformation/ # blowup, mv_bipartization
```

Plus `utils/groups/` for the GAP/PSL helpers that don't belong here.

Each sub-folder gets its own thin abstraction parent (e.g.
`AlgebraicConstruction`, `SATSolver`) that sits on top of the shared
`Generator` base.

---

## 2. The base class is already paradigm-neutral

`search/base.py` has no search-specific *logic* — every word "search"
in it is purely cosmetic. The actual operations:

| Operation | What it does | Paradigm? |
|---|---|---|
| `__init__` | stores `n`, `top_k`, `verbosity`, kwargs | Generic |
| `_run()` | subclass produces `list[nx.Graph]` | Generic — works for any graph producer |
| `run()` | times, calls `_run()`, wraps, sorts by c_log, truncates to top_k, logs | Generic |
| `_wrap()` | computes α, d_max, c_log, K4-freeness, timestamps | Generic — graph properties only |
| `_stamp()` / `_elapsed()` | per-graph timing | Generic |
| `save()` | persist to `graph_db` with source tag | Generic |
| `_alpha_of()` | α via clique-cover B&B (overridable) | Generic |

The only search content is **vocabulary** (class name, log strings,
method `_run`). Renaming changes none of the actual behavior.

---

## 3. The `Walk` abstraction — the substantive change

### Motivation

Composability of policies across walk types, not file-count savings.

Right now if you want Δc_log scoring on `CayleyTabuSearch`, you have to
rewrite it. If you want tabu memory on the per-edge walk, you have to
rewrite it. With a shared Walk contract, scorers/samplers/stops/tabu
wrappers written once work on every walk.

### What gets composed for free

| Policy | Works on (under shared contract) |
|---|---|
| `score_fn = -Δc_log` | per-edge walk, 2-switch walk, Cayley bitvec walk |
| `stop_fn = "α ≤ target"` | all walks (operates on materialised graph) |
| `tabu(score_fn, ℓ)` wrapper | all walks (just needs moves to be hashable) |
| `importance_sampler(weight_fn)` | all walks |
| `simulated_annealing(beta_schedule)` | all walks (β is search-level) |

### What does NOT compose for free

Mixing move types within one walk (e.g. "Cayley with edge
perturbations") still requires a bespoke walk class — one that
enumerates the union moveset, validates both types, applies both. But
the abstraction makes that bespoke class small (~50 lines) instead of a
~200-line ad hoc reimplementation.

### Proposed contract

```python
class Walk(Generator, Generic[StateT, MoveT]):
    @abstractmethod
    def initial_state(self) -> StateT: ...
    @abstractmethod
    def enumerate_moves(self, state: StateT) -> Iterable[MoveT]: ...
    @abstractmethod
    def is_valid(self, state: StateT, move: MoveT) -> bool: ...
    @abstractmethod
    def apply(self, state: StateT, move: MoveT) -> None: ...
    @abstractmethod
    def unapply(self, state: StateT, move: MoveT) -> None: ...   # for scoring
    @abstractmethod
    def to_graph(self, state: StateT) -> nx.Graph: ...

    # Optional — falls back to full re-validation if not overridden
    def update_valid_mask(self, state, move, mask) -> None: ...

    # Inherited — the entire walk loop body (score, softmax, sample, apply)
```

`State` and `Move` are opaque types. Policies (scorers, samplers, stops)
take `(state, move, info, context)` but interact with state only via
`to_graph` / `apply` / `unapply`.

### Concrete subclasses

| Walk | StateT | MoveT |
|---|---|---|
| `RandomWalkSearch` | `np.ndarray` (adj) | `(u, v, is_add)` |
| `SwitchWalkSearch` | `np.ndarray` (adj) | `(a, b, c, d)` (2-switch) |
| `BitvecWalkSearch` | `np.ndarray` (1D bool) | `int` (bit index) |

### The catch: `update_valid_mask`

For per-edge walks: `O(|N(a)∪N(b)|·n)` updates after add/remove (already
implemented).

For 2-switch: similar locality argument over 4 vertices, but with
revalidation of K4-safety on the ~4 affected edges. Not yet derived in
this discussion.

For bitvec/Cayley: each bit flip affects the K4-safety of every other
bit (since the materialised Cayley graph changes globally). Probably no
clean local update — fall back to full re-check (`O(k)` bit checks per
step, where k = number of bits = number of generators).

If `update_valid_mask` doesn't have a clean implementation for some
walk type, the engine falls back to full re-enumeration. The
abstraction tolerates this — it's just a knob.

---

## 4. What can be eliminated

Under `Walk` + `RandomWalkSearch` + `SwitchWalkSearch` + `BitvecWalkSearch`:

### Deleted (~6 remaining files; bohman_keevash already gone)

| File | Folds into |
|---|---|
| `random_regular_switch.py` | `SwitchWalkSearch` + greedy α-reducing scorer + degree-spread stop |
| `mcmc.py` | `SwitchWalkSearch` + Metropolis acceptance (β-controlled softmax already does this) |
| `switch_tabu.py` | `SwitchWalkSearch` + tabu policy (closure-based score_fn) |
| `alpha_targeted.py` | `SwitchWalkSearch` variant with paired-swap moves; could be its own concrete walk |
| `cayley_tabu.py` | `BitvecWalkSearch` + Cayley state interpretation + tabu wrapper |
| `cayley_tabu_gap.py` | `BitvecWalkSearch` + GAP-group state source + tabu |
| `tabu.py` | Disappears — becomes a generic `tabu_wrapper(score_fn)` policy that works on any Walk |

### Added (~2 files)

| File | Role |
|---|---|
| `walk.py` (or `walk/__init__.py`) | `Walk` abstract parent class |
| `switch_walk.py` | Concrete `SwitchWalkSearch` |
| `bitvec_walk.py` | Concrete `BitvecWalkSearch` |

### Net file count

Of ~30 files in `search/`: ~7 deleted, ~3 added, ~22 untouched. Modest
reduction; bigger consistency win.

### Cannot be replaced

These remain because they're a different paradigm:

- **Algebraic (5)**: `brown`, `cayley` (residue), `mattheus_verstraete`,
  `norm_graph`, `polarity` — closed-form, no search
- **Enumeration (3)**: `circulant`, `circulant_fast`, `brute_force` —
  exhaustive, not Markov walks
- **SAT (7)**: all `sat_*` — solver-driven
- **Transformation (2)**: `blowup`, `mv_bipartization` — graph-to-graph
- **Utilities (3)**: `groups`, `groups_gap`, `groups_psl` — should move
  to `utils/`
- **Infrastructure (2)**: `base`, `logger` — must stay

---

## 5. Why specific searches don't fit `RandomWalkSearch`

### CayleyTabu — different state granularity

- **State**: bitvec of inversion-orbit indicators, length ≈ (n-1)/2
- **Move**: flip one bit → atomically adds/removes **n edges** (the
  whole Z_n orbit of that generator) from the graph
- **RandomWalk**: state is adjacency matrix; each move flips exactly one
  edge

You can't represent "Cayley graph with `(0,1)` an edge but `(1,2)` not"
in CayleyTabu — that state is structurally forbidden. RandomWalk has no
way to enforce that and no way to flip n edges atomically.

Tabu memory itself is easy (closure-based score_fn). The orbit-level
moveset is the structural blocker.

### 2-switch family — different move type

`MCMC`, `RandomRegularSwitch`, `SwitchTabu`, `AlphaTargeted` all use
4-vertex 2-switches `(a,b)(c,d) → (a,c)(b,d)` (or paired add+remove).
Move shape is a 4-tuple, not `(u, v, is_add)`. Same problem — different
move type needs a different concrete walk class.

---

## 6. Order of operations

**Now / next**:
1. Leave `RandomWalkSearch` as-is.
2. When you start needing 2-switch behavior, build `SwitchWalkSearch`
   as a sibling class (copy-paste the structure of `RandomWalkSearch`).

**At the second concrete walk**:
3. Notice that ~80% of the loop body is duplicated between `RandomWalk`
   and `SwitchWalk`. Extract `Walk` as a parent class. Lock in the
   contract from two concrete examples (right number to triangulate).

**After the contract is stable**:
4. Port `CayleyTabu` and `CayleyTabuGap` onto `BitvecWalkSearch`.
5. Port the other 2-switch classes onto `SwitchWalkSearch`.
6. Delete the obsolete originals (the ~7 files in §4).

**Once the walk family is consolidated**:
7. Rename `search/` → `generators/`.
8. Optionally subdivide into `walk/`, `algebraic/`, `enumeration/`,
   `sat/`, `transformation/`.
9. Move `groups*` utilities to `utils/`.

**Parallel track (independent)**:
- Add a `AlgebraicConstruction` thin parent for the 5 closed-form
  classes — same parameter-sweep + closed-form-generate shape. Same
  argument as Walk: 5 concrete examples sharing a structure earns a
  parent. Different abstraction project, similar logic.

---

## 7. Open questions / things to verify

1. **Does `update_valid_mask` have a clean local form for 2-switch?**
   I haven't worked out the locality argument. The naive form is "the
   four endpoints `{a, b, c, d}` and their neighborhoods" but the
   actual affected validity set may be larger because changing two
   edges simultaneously can create K4s in unexpected places.

2. **Is the `MoveT` opaque-type discipline strict enough?** Can a
   policy author write a generic `tabu(score_fn, ℓ)` wrapper that works
   for any Move type assuming only hashability? If yes, perfect. If
   the wrapper needs to inspect move shape (e.g. for "edge identity"
   in a 2-switch), the abstraction leaks slightly.

3. **What's the right base name?** `Generator` is honest. `Producer`
   is awkward. `Method` is too generic. `Construction` is wrong for
   walks/SAT. Open.

4. **Should `_run()` rename to `_generate()`?** Probably yes for
   honesty, but it's invasive. Could leave as-is.

5. **Backward-compat shim for `search.X` imports?** For the rename,
   we could leave a thin `search/__init__.py` that re-exports from
   `generators/` for one release cycle. Or just rip the bandaid off.
   The codebase is internal/research so probably the latter.

---

## 8. What was already done (for context)

This refactor discussion was triggered by a series of cleanups already
in the repo:

- `search/random_walk.py` was rewritten as a clean per-edge walk
  template with `score_fn`, `batch_score_fn`, `sample_fn`, `stop_fn`
  hooks. β=∞ greedy supported. `valid_mask` updated incrementally via
  the `N(a) ∪ N(b) ∪ {a,b}` locality argument.
- `search/random.py`, `search/regularity.py`,
  `search/regularity_alpha.py`, `search/bohman_keevash.py` were deleted.
  Their behaviors are now expressed as `RandomWalkSearch` policies (the
  first three in `experiments/greedy/`; B-K is literally the default
  config of `RandomWalkSearch`).
- The deleted-class docs in `docs/searches/` got "MOVED" redirect
  notes pointing to `experiments/greedy/` or to `RandomWalkSearch`.
- `scripts/run_bohman_keevash_sweep.py` deleted along with the class.
- `experiments/random/baseline_random.py`, `baseline_weighted_random.py`,
  and `sweep_configs.py` exist as the random-walk-policy experiment
  surface.

So `RandomWalkSearch` is the first concrete walk and the prototype
for the contract. `SwitchWalkSearch` will be the second; that's where
`Walk` extraction starts to make sense.
