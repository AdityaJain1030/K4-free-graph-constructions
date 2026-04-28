# `RandomRegularSwitchSearch` — random near-regular + edge-switch polish

## What it does

Probe 1 from the landscape study ("Random regular K₄-free generation +
local search").

For each target degree `d` (default: a small sweep around `n^{2/3}`)
and each of `num_trials` independent seeds:

1. Build a random K₄-free graph on `n` vertices by uniformly shuffling
   all vertex pairs and adding each edge subject to a hard degree cap
   `d` and a K₄-freeness check (two passes, same construction as
   `RandomSearch`).
2. Run `num_switches` degree-preserving edge-switch moves
   (`utils.edge_switch.rebalancing_switch`) as a hill-climb. Each move
   is accepted iff the greedy α estimate does not go up and the degree
   spread does not widen.
3. Return the polished graph.

The base class then computes exact α via CP-SAT and rank-truncates to
`top_k` by `c_log`.

## Why it exists

`RandomSearch` caps degree and stops. The **edge-switch step** is what
converts the random-with-cap distribution into a probe of the *local*
landscape around each random seed:

- **Basin width at each `N`.** Run it many times and plot the
  distribution of final `c_log`. Narrow distributions concentrating at
  a low `c` ⇒ wide, benign basin. Wide flat distributions ⇒ rugged.
- **Greedy ceiling curve.** Best polished `c_log` vs `N` is the
  landmark the structured searches need to clear.

## Scoring notes

- During the switch loop we use `alpha_approx` (random greedy restarts,
  `switch_alpha_restarts` default `64`). Exact α per step would dominate
  runtime; a 10–15% greedy α is accurate enough for ranking.
- At scoring time the base class calls `_alpha_of`, which this search
  overrides to `alpha_cpsat` (the same choice `graph_db.properties`
  uses). This matches the rest of the repo's α-solver hygiene: the
  caller names its α solver explicitly.

## Kwargs

| kwarg                   | hard/soft | meaning                                                   |
|-------------------------|-----------|-----------------------------------------------------------|
| `d`                     | soft      | Target degree (cap during build, rebalancing target).     |
| `num_trials`            | -         | Independent random seeds per `d`.                         |
| `num_switches`          | -         | Switch iterations per trial (hill-climb length).          |
| `switch_alpha_restarts` | -         | Greedy-α restarts used to rank candidate switches.        |
| `seed`                  | -         | Base RNG seed.                                            |

## Caveats

- **Switches preserve degree, build does not.** The random build is
  degree-capped, not degree-pinned. Expect degree spread 1–3 at
  completion on all but the smallest `n`. The rebalancing switch
  narrows it but rarely eliminates it.
- **Greedy α is biased upward.** If two candidate switches tie on
  greedy α, we prefer the one that narrows the degree spread. This is
  the only tiebreaker — other local structure is ignored.
- **O(n²) per switch.** `find_k4` is re-run on every candidate
  adjacency. Fine up to `n ≈ 100`; past that the switch loop
  dominates.

## When to reach for it

- Computing the basin-width curve referenced in
  `docs/searches/regularity/REGULARITY_ALPHA.md`.
- Generating seeds for higher-level metaheuristics at `n` past the
  reach of `CirculantSearch`.

## When **not** to reach for it

- You want ground truth — use `SATExact` / `SATRegular`.
- `n < 15` — `BruteForce` is cheaper and optimal.
