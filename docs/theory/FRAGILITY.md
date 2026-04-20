# Probe 2 — perturbation fragility across N

## Question

How fast does c_log degrade when we randomly perturb a best-known graph
at each N? If fragility shrinks with N, the basin of good graphs is
*widening* and local search (PatternBoost) should scale well. If
fragility is N-independent, the landscape is scale-invariant and local
search won't help at large N.

## Procedure

Implemented in `scripts/run_fragility.py`, plotted by
`visualizer/plots/plot_fragility.py`.

For each target N:

1. Pick the cached K₄-free graph with the smallest c_log (`db.frontier`
   with `is_k4_free=1, n=n`).
2. Launch `--trials` independent random walks (default 30).
3. At each walk step: pick a random edge `uv`, pick a random non-neighbour
   `w` of `u`, propose `G' = G - uv + uw`. Accept iff `G'` is K₄-free
   and the degree spread `d_max − d_min ≤ 2`. The acceptance rule
   *never* looks at c_log — this is a walk, not a climb.
4. Record c_log at steps `[0, 1, 2, 5, 10, 20, 50, 100]` and average
   across trials.

α at recorded steps defaults to `alpha_approx` (greedy, fast) because
a full sweep does ~94 × 30 × 8 ≈ 22k α evaluations. Switch to
`--alpha exact` for a narrow N range when precise numbers matter.

## Primitive

`utils.edge_switch.random_walk_move(adj, rng, *, max_degree_spread=2)` —
single-edge degree-shifting move. Not degree-preserving (unlike
`random_switch`, which swaps two disjoint edges); the spread cap keeps
the walk near-regular.

## Output

- `visualizer/plots/data/fragility.json` — raw trajectories.
- `visualizer/plots/images/fragility.png` — two-panel plot:
  - left: absolute c_log vs step, one line per N, viridis by N.
  - right: Δ c_log from step 0 on log-x. This is where basin-widening
    is legible: small-N (purple) and large-N (yellow) curves at
    different heights ⇒ basin width scales with N.

## Reading the plot

- Curves **fan out by N** (small-N lines sit higher than large-N
  lines on the Δ panel) ⇒ **basin widens with N**. PatternBoost
  should help more at large N.
- Curves **parallel** across N ⇒ scale-invariant landscape, no
  scaling win from local search.
- Occasional flat lines (Δ ≈ 0): the seed has a very tight degree
  spread (e.g. a 2-regular cycle) and almost every move violates the
  `≤ 2` spread cap. These are near-rigid graphs, not landscape signal.

## Run

```
micromamba run -n k4free python scripts/run_fragility.py \
    --trials 30 --steps 100 --alpha approx
micromamba run -n k4free python visualizer/plots/plot_fragility.py
```

Targeted run for a few N values:

```
micromamba run -n k4free python scripts/run_fragility.py \
    --ns 20 40 60 80 100 --trials 100 --alpha exact
```
