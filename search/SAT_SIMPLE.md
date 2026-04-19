# SAT_SIMPLE — Naive `SATExact` draft

Design for the first, deliberately un-optimized `SATExact`. No lazy
cutting planes, no lex-leader, no c_log pruning. Just the three
eager constraints wired into CP-SAT and exposed through the
`Search` ABC.

Purpose: get a correct, understandable baseline onto the
supercomputer. Later phases (see `SAT_PLAN.md`) add optimizations.

---

## 1. The model (all eager)

Variables:

- `x_{i,j}` for every `i < j`, one boolean per potential edge.
  `n · (n-1) / 2` variables total.

Constraints, all added upfront at model-build time:

1. **K₄-free.** For every 4-subset `{a,b,c,d} ⊆ [n]`, the six edges
   inside can't all be present:
   ```
   x_{a,b} + x_{a,c} + x_{a,d} + x_{b,c} + x_{b,d} + x_{c,d} ≤ 5
   ```
   That's `C(n, 4)` clauses.

2. **Max degree.** For every vertex `v`:
   ```
   Σ_{j ≠ v} x_{min(v,j), max(v,j)}  ≤  d_max
   ```
   `n` clauses.

3. **Independence number α.** For every `(α+1)`-subset
   `S ⊆ [n]`, at least one edge inside `S`:
   ```
   Σ_{i < j ∈ S} x_{i,j}  ≥  1
   ```
   `C(n, α+1)` clauses.

No symmetry breaking, no Ramsey pruning, no hint, no lazy cuts.

The model is pure feasibility: no objective. CP-SAT either returns
a feasible assignment or INFEASIBLE (or TIMEOUT).

---

## 2. Two run modes

The class takes `n` plus *optional* `alpha` and `d_max`. Behaviour
forks on whether both are provided:

### Mode A — single box (both `alpha` and `d_max` set)

Build the model once with those caps, solve once, return whatever
graph comes back (or `[]` if INFEASIBLE / TIMEOUT). One SAT call.

Returned graph satisfies `α(G) ≤ alpha` and `d_max(G) ≤ d_max`. Base
class computes `c_log` in `_wrap`.

### Mode B — scan (one or both unset)

Iterate over the missing dimension(s) and call the single-box solver
for each point. Keep the graph with the smallest `c_log` seen so
far (returned as top_k of the base class).

Candidate iteration order, simplest first:

```
for α in range(1, n):              # if `alpha` unset; else fixed
    for d in range(1, n):          # if `d_max` unset; else fixed
        solve_box(n, α, d)
        if FEASIBLE:
            compute c_log; track best; break d-loop (smaller d beats larger)
```

Breaking the inner loop on first feasibility is sound: for fixed α
and increasing d, `α · d / (n · ln d)` is increasing for d ≥ e
(so the first feasible d is the best one at this α). For α=1 or
small n where `d ≤ 2`, `c_log` is `None` — skip.

If both `alpha` and `d_max` are unset, we scan both; if only one is
set, the other is scanned and the fixed one is a constant cap on
every box solve.

---

## 3. `search/sat_simple.py` skeleton

```python
class SATSimple(Search):
    """
    Naive SAT-based K4-free search. No optimizations.

    Two modes, selected by kwargs:
      - both alpha and d_max set  → single SAT solve on that box.
      - otherwise                 → scan α and/or d_max, return best c_log.

    Constraints
    -----------
    alpha     : int | None   — hard; α(G) ≤ alpha. If None, scanned.
    d_max     : int | None   — hard; d_max(G) ≤ d_max. If None, scanned.
    timeout_s : float        — per SAT solve, default 300.
    workers   : int          — CP-SAT num_workers, default 16.
    """
    name = "sat_simple"

    def __init__(
        self,
        n: int,
        *,
        top_k: int = 1,
        verbosity: int = 0,
        parent_logger=None,
        alpha: int | None = None,
        d_max: int | None = None,
        timeout_s: float = 300.0,
        workers: int = 16,
        **kwargs,
    ):
        super().__init__(
            n,
            top_k=top_k, verbosity=verbosity, parent_logger=parent_logger,
            alpha=alpha, d_max=d_max, timeout_s=timeout_s, workers=workers,
            **kwargs,
        )

    def _run(self) -> list[nx.Graph]:
        if self.alpha is not None and self.d_max is not None:
            return self._single_box(self.alpha, self.d_max)
        return self._scan()

    # -- internals --

    def _build_model(self, alpha_cap, d_cap):
        """Build CP-SAT model with eager K4, degree, and α constraints."""
        ...

    def _solve(self, alpha_cap, d_cap):
        """Return ('FEASIBLE', nx.Graph) | ('INFEASIBLE', None) | ('TIMEOUT', None)."""
        ...

    def _single_box(self, alpha_cap, d_cap) -> list[nx.Graph]:
        status, G = self._solve(alpha_cap, d_cap)
        self._log("attempt", level=1, alpha=alpha_cap, d_max=d_cap, status=status)
        if G is None:
            return []
        self._stamp(G)
        G.graph["metadata"] = {
            "alpha_target": alpha_cap,
            "d_max_target": d_cap,
            "status": status,
        }
        return [G]

    def _scan(self) -> list[nx.Graph]:
        alpha_range = [self.alpha] if self.alpha is not None else range(1, self.n)
        out: list[nx.Graph] = []
        for a in alpha_range:
            d_range = [self.d_max] if self.d_max is not None else range(1, self.n)
            for d in d_range:
                status, G = self._solve(a, d)
                self._log("attempt", level=1, alpha=a, d_max=d, status=status)
                if G is None:
                    continue
                self._stamp(G)
                G.graph["metadata"] = {
                    "alpha_target": a, "d_max_target": d, "status": status,
                }
                out.append(G)
                break   # smallest feasible d for this α is the best
        return out
```

Base class handles: sorting the returned graphs by `c_log`, keeping
`top_k`, computing `α`, `d_max`, `c_log`, `is_k4_free`, logging,
and persistence.

---

## 4. What the scan actually returns

Because we `return` every feasible graph from the scan (one per α),
base class sorts by `c_log` ascending and keeps `top_k`. With
`top_k=1` (default), the caller gets **one** graph: the one with
the lowest `c_log` across all `(α, min_feasible_d)` points probed.

To see the whole per-α frontier, set `top_k=n` (or some big number).

---

## 5. What this draft does *not* do

No lazy K₄ cuts → K₄ clauses blow up past N ≈ 25. Known.
No lazy α cuts → α clauses blow up past N ≈ 25. Known.
No symmetry breaking → search tree is N! redundant. Known.
No Ramsey pruning → wastes time on trivially-infeasible boxes. Known.
No warm start → solver starts from scratch each box.
No `c_bound` pruning → scans whole rectangle, not just below c*.

All of the above are tracked in `SAT_PLAN.md`. The point of
`SATSimple` is to have a correctness baseline that's small enough to
read, not a fast solver.

---

## 6. Eval plan and bounds

### Target: N = 10 … 25, on this laptop

Deliberately capped. Not because the model *can't* go higher —
memory analysis says a 20 GB machine fits N=30–32 for α ≤ 6, and
the supercomputer fits N=40 at α ≤ 6 — but because the whole
point of this first pass is a **local baseline** we can iterate on.

Reasoning (from the user, recorded here so future edits don't drift):

> I essentially just want to have a baseline that we can reach on
> this computer, and then optimize it more and more while keeping
> exactness, and then I'll push it to the supercomputer.

Consequences of that reasoning for this file:

- **Don't design for N=40 yet.** Every optimization in `SAT_PLAN.md`
  (lazy K₄, lazy α, lex-leader, Ramsey pruning, c_log pruning) will
  be added *incrementally* against the same N ≤ 25 eval set. Each
  one has to preserve exactness and either match or beat the prior
  version's best `c_log` at every N in 10..25. When the laptop
  version of the optimized solver returns in seconds at N=25, then
  it's time to push the next phase to the supercomputer and extend
  the N range.
- **Eval must be fast enough to run repeatedly.** A full
  N=10..25 scan needs to complete in a single sitting so we can
  iterate. Target: under ~1 hour on this laptop for the naive
  version; much faster for each successive optimization.
- **Exactness is non-negotiable.** Every reported `c_log` at every
  N must match a certified optimal (or explicitly be marked as a
  TIMEOUT-produced upper bound, with the matching box recorded so
  the next run can retry). No silent heuristics.

### Per-N expectations on this laptop

| N range | Expected outcome                                               | Per-box timeout |
|---------|----------------------------------------------------------------|-----------------|
| 10–14   | Full scan fast (<1 s/box). Match `BruteForce` exactly.         | 60 s            |
| 15–18   | Full scan in seconds. Match `SAT_old/results/pareto_n{N}.json`.| 60 s            |
| 19–22   | Full scan in minutes. Still should match `SAT_old` Paretos.    | 180 s           |
| 23–25   | Partial — some boxes TIMEOUT. Best `c_log` is a valid upper    | 300 s           |
|         | bound; flag the TIMEOUT boxes so we know what the later        |                 |
|         | optimizations need to solve.                                   |                 |

N > 25 is explicitly out of scope for the naive version. That's
what the `SAT_PLAN.md` phases are for, and they run on the
supercomputer.

### Concrete eval checks (run in order)

1. `SATSimple(n=10)` — best `c_log` equals `BruteForce(n=10)`.
2. `SATSimple(n=15, alpha=3, d_max=6)` — returns the same feasible
   graph family as `SAT_old/k4free_ilp/results/pareto_n15.json`.
3. `SATSimple(n=20)` — scan; best `c_log` equals `pareto_n20.json`.
4. `SATSimple(n=22)` — scan; best `c_log` equals `pareto_n22.json`.
5. `SATSimple(n=25)` — scan; partial results expected. Record every
   TIMEOUT `(α, d)` box with its timeout value. The first job of
   each subsequent optimization is to turn those TIMEOUTs into
   FEASIBLE / INFEASIBLE.

### What counts as "baseline established"

- All five checks above run end-to-end without crashing.
- Checks 1–4 produce `c_log` equal to the `SAT_old` Pareto JSONs
  (to within floating-point rounding).
- Check 5 produces a partial frontier plus a list of TIMEOUT boxes
  that the next optimization phase will target.

Only once that holds do we move on to lazy α, lazy K₄, etc.

---

## 7. CLI driver (`scripts/run_sat_simple.py`)

Mirrors `scripts/run_random.py`:

```
python -m scripts.run_sat_simple --n 20
python -m scripts.run_sat_simple --n 25 --alpha 5
python -m scripts.run_sat_simple --n 18 --alpha 3 --d-max 6
```

Prints a small summary table (n, best_alpha, best_d, best_c_log,
elapsed, solves_run) and optionally saves to `graph_db` with
`--save`.

---

## 8. Next steps after this draft

Once `SATSimple` is in and validated:

- Swap eager α constraints for the lazy cutting-plane loop. That's
  the single change that gets us past N=25.
- Then lazy K₄.
- Then the rest of the phases in `SAT_PLAN.md`.

Keep `SATSimple` in the repo as a reference implementation. It's the
"is the base class correctly wired" oracle for every later SAT
variant.
