# `AlphaTargetedSearch` — stochastic local search that attacks α directly

## What it does

Method 2 from the landscape study ("Stochastic local search with
α-targeting"). Sibling of `RandomRegularSwitchSearch` (rrs), but the
move set is different: instead of rewiring to shrink a greedy-α proxy
as a side effect, this search picks two vertices **inside the current
greedy MIS** and forces them together.

For each target degree `d` (default: a small band around `n^{2/3}`)
and each of `num_trials` independent seeds:

1. Build a random K₄-free graph on `n` vertices with a hard degree cap
   `d` (identical construction to rrs).
2. Compute a greedy MIS `I` via `alpha_approx_set` (random-restart
   greedy, same algorithm as `utils.graph_props.alpha_approx` with the
   winning set recorded).
3. Propose an α-reducing move:
   - pick `u, v ∈ I` (they are non-adjacent by definition of `I`);
   - pick an edge `(x, y) ∈ E(G)` with `{x, y} ∩ {u, v} = ∅`, weighted
     toward endpoints at high degree so the swap compensates the
     `+1` on `u, v`;
   - propose `G' = G + uv − xy`.
4. Accept iff
   - `G'` is K₄-free,
   - `d_max − d_min ≤ max_degree_spread` (cap relaxes to the initial
     spread if already larger), and
   - `alpha_approx(G') < alpha_approx(G)`.
5. Continue for `num_steps` attempts or until `stall_cap` consecutive
   proposals fail.
6. Return the polished graph; base class scores exact α via CP-SAT.

## Why it exists

Greedy methods that optimise edge density or degree balance only reach
the independence number **indirectly**. rrs's inner loop uses greedy α
to *rank* switches but it's still a degree-preserving rewiring — the
gradient on α is whatever the rewiring happens to expose.

`AlphaTargetedSearch` makes the α gradient explicit:

- Adding `uv` with `u, v ∈ I` *definitionally* destroys `I` as an
  independent set. Any MIS of `G'` must drop at least one of `{u, v}`.
- If the rest of the graph around `I` is not a near-pending vertex to
  substitute in, the MIS of `G'` strictly shrinks.
- The compensating removal `xy` keeps the edge count constant and the
  degrees within the spread cap.

This matches the design the study calls for: "directly attacking the
independent set" instead of optimising `c_log` through edge density.

## Scoring notes

- Inside the descent we use `alpha_approx_set` (seeded,
  `alpha_restarts` default `64`). Exact α per step would dominate
  runtime on `n ≥ 50`; the `alpha_approx` vs exact gap is ≤ 1 across
  our dataset (see `visualizer/plots/images/plot_08_alpha_proxy.png`),
  so the greedy proxy is reliable for step-level decisions.
- At scoring time the base class calls `_alpha_of`, which this search
  overrides to `alpha_cpsat` — same choice as rrs and
  `graph_db.properties`. Per the repo's α-solver policy: every call
  site names its solver explicitly.

## Kwargs

| kwarg                 | hard/soft | meaning                                                    |
|-----------------------|-----------|------------------------------------------------------------|
| `d`                   | soft      | Target degree cap during build (and stepwise target).      |
| `num_trials`          | -         | Independent random seeds per `d`.                          |
| `num_steps`           | -         | Max α-reducing move attempts per trial.                    |
| `stall_cap`           | -         | Early-stop after this many consecutive failed proposals.   |
| `alpha_restarts`      | -         | Greedy-α restarts per call (both initial MIS and each eval)|
| `pair_attempts`       | -         | Pairs `(u, v) ∈ I × I` tried per step.                     |
| `remove_attempts`     | -         | Removal edges tried per `(u, v)` pair.                     |
| `max_degree_spread`   | -         | Hard cap on `d_max − d_min` (relaxes to initial spread).   |
| `seed`                | -         | Base RNG seed.                                             |

## Caveats

- **The move is not degree-preserving.** Adding `uv` and removing `xy`
  shifts degree by `±1` at four vertices. With the default spread cap
  of `2`, each accepted step can push `d_max` up by 1. Because
  `c_log ∝ d / ln(d)`, a smaller α combined with a larger `d_max` can
  leave `c_log` flat or worse — see the empirical table below.
- **Weighted removal is a heuristic, not a guarantee.** We sample
  removal edges with probability proportional to the sum of endpoint
  degrees. This biases away from `(u, v)` but doesn't enforce that the
  removed edge's endpoints are the current `d_max` vertices.
- **Greedy α is the step rule.** A move that reduces greedy α but not
  exact α is still accepted. In practice exact and greedy agree ≥ 99%
  of the time (Plot 8), so this is tolerable.
- **O(n³) per step** in the worst case from `find_k4` on every
  candidate. Comfortable to `n ≈ 100`.

## Empirical scaling (N ≤ 100, seed=1, preset `local100`)

From a head-to-head vs `RandomRegularSwitchSearch` on the same N grid:

```
  N    rrs c_log α  d      αt c_log α  d
 20    0.8993  5  7      0.9618  5  8
 30    0.9558  7  9      1.0134  7 10
 40    1.0322  9 11      1.0322  9 11
 50    1.1150 11 13      1.1150 11 13
 60    1.1078 12 15      1.1078 12 15
 70    1.1542 14 16      1.2001 14 17
 80    1.1677 15 18      1.1677 15 18
100    1.2017 18 20      1.2099 17 22
```

- **N=40–80 (except 70):** αt and rrs land on identical polished
  graphs. Both descents converge to the same local optimum at these
  sizes.
- **N=100:** αt **does** reduce α (17 vs rrs's 18) — the design goal
  is met — but `d_max` grows from 20 to 22, and `c_log` is marginally
  worse.
- **N ≤ 30:** αt matches rrs on α but pays one extra unit of `d_max`,
  so `c_log` lands above rrs.

**Interpretation.** The α-targeting primitive does what it says on the
box — it reduces the independence number in cases where rrs's
degree-preserving moves cannot. But the ±1 degree-spread cost of the
non-degree-preserving swap eats the α gain on the `c_log` metric. The
method is a **building block**, not a standalone winner.

## When to reach for it

- You want to probe whether α-reduction is even *possible* from a
  given seed — this primitive gives you a direct gradient on α that
  rrs doesn't.
- You're building a hybrid that alternates αt moves (to escape α
  plateaus) with rrs moves (to tighten degrees afterward). The two
  move sets are complementary.
- As a sanity check on how much αt can push α down if allowed to
  inflate `d_max` — useful for calibrating the degree-spread cap.

## When **not** to reach for it

- You want the current best `c_log` at a given N — reach for
  `CirculantSearchFast` or `CirculantSearch` first; they dominate both
  rrs and αt across the Ns covered above.
- You need optimality proofs — use `SATExact` / `SATRegular`.
- `n < 15` — `BruteForce` is cheaper and optimal.

## Driver

```
micromamba run -n k4free python scripts/run_alpha_targeted.py --preset local100
```

Presets: `quick` (N=15…30, cheap), `default` (N=20…40, 4 trials),
`local100` (N=20…100, 4 trials, 200 steps), `large` (server-only, 10
trials, 400 steps). See `scripts/run_alpha_targeted.py` for flag
surface.
