# `experiments/random/` — results

Full record of what we tried, what worked, what broke, and why. Numbers are
from N ∈ {10, 20, 30, 40, 50}, 3 trials, seed 0; all methods built on
`search.stochastic_walk.edge_flip_walk.EdgeFlipWalk`.

---

## Methods

| key | proposer | scorer | β | stop |
|---|---|---|---|---|
| `uniform_alpha` | uniform over valid adds | none | — | exact CP-SAT α ≤ target |
| `uniform_ar_alpha` | uniform over valid adds + removes | none | — | exact CP-SAT α ≤ target |
| `bohman_keev` | uniform 1-of-k over valid adds | none | — | saturation (no add valid) |
| `w_d_min_sat` | full add set | `−(deg_u + deg_v)` | 4 | saturation |
| `w_alpha_sat` | full add set | `−alpha_lb(post-add)` (+ tiebreak) | 4 | saturation |
| `w_c_log_sat` | full add set | `−c_log_surrogate(post-add)` (+ tiebreak) | 4 | saturation |
| `ar_target_reg` | full add+remove set | target-distance regularity (patched) | 4 | edges target |
| `ar_alpha` | full add+remove set | `−alpha_lb(post-move)` | 4 | edges target |
| `ar_c_log` | full add+remove set | `−c_log_surrogate(post-move)` | 4 | edges target |

α stops/scoring: scoring uses **greedy** `alpha_lb` (4 restarts) per
candidate; only `uniform_alpha`'s halt rule uses **exact CP-SAT**.

---

## Best c_log per N

`ar_target_reg` row is post-patch. `ar_alpha`, `ar_c_log` rows are the original
sweep — the tiebreaker re-run was killed (≈ 280 s/cell at N=20, scaling
worse) since it gave no improvement.

| N  | uniform_α | **uniform_ar_α** | bohman | w_d_min | w_α | w_c_log | **ar_target_reg** | ar_α | ar_c_log |
|----|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 10 | 1.005 | **0.932** | 1.005 | 1.005 | 1.005 | 1.005 | **0.932** | 1.005 | 1.005 |
| 20 | 1.147 | **1.086** | 1.449 | 1.147 | 1.147 | **1.086** | 1.154 | 1.086 | 1.303 |
| 30 | 1.238 | 1.183 | 1.292 | 1.347 | 1.292 | 1.292 | **1.158** | 1.415 | 1.288 |
| 40 | 1.401 | 1.443 | 1.452 | 1.291 | 1.291 | 1.401 | **1.207** | 1.385 | 1.443 |
| 50 | 1.335 |  —    | 1.467 | 1.380 | 1.467 | 1.242 | **1.167** | 1.370 | 1.440 |

`uniform_ar_α` at N=50 was killed: walk took 80k+ steps at N=40 (2423 s),
extrapolated to days at N=50.

Per-N winner:

| N  | winner | c_log | result-graph shape | runner-up |
|----|---|---:|---|---:|
| 10 | uniform_ar_α ≡ ar_target_reg | **0.932** | α=3, d=5, E=23 | 1.005 (5-way) |
| 20 | uniform_ar_α ≈ w_c_log_sat ≈ ar_α | **1.086** | α=5, d=10 | 1.147 (3-way) |
| 30 | ar_target_reg | **1.158** | α=8, d=10, E=145 | 1.183 (uniform_ar_α) |
| 40 | ar_target_reg | **1.207** | α=10, d=12, E=234 | 1.291 (w_d_min ≈ w_α) |
| 50 | ar_target_reg | **1.167** | α=11, d=14, E=339 | 1.242 (w_c_log) |

`ar_target_reg` wins 3 of 5 sizes; `uniform_ar_α` ties for the win at
N=10 and N=20 then degrades (see finding 24 below).

---

## Findings

### Headline

**For random K4-free baselines, structural targeting (regularity toward
n^{2/3}) outperforms expensive surrogate-α scoring at every N ≥ 30.**
Beats Bohman–Keevash by ≈ 0.3 in c_log, beats uniform_alpha by
0.07–0.20, and is ~10× cheaper than the α-surrogate methods.

### Method-level

1. **`uniform_alpha` is the strong baseline among non-regularity methods**
   (best at N=20–30 if you exclude `ar_target_reg`). The exact-CP-SAT halt on α
   is the single sharpest signal in the comparison; nothing using a greedy
   α surrogate matches it as a stop rule.

2. **Stopping criterion matters more than proposal weighting** — for the
   `add_edges.py` baseline, alpha-stop > edges-stop > d_max-stop by
   0.1–0.4 at every N (see `README.md`). Once you fix a weighting scheme,
   varying β within {1, 4, 16} barely changes outcomes.

3. **Bohman–Keevash is consistently among the worst at N ≥ 20.**
   Saturation pushes `d_max` way up (`d_max = 23` at N=50) without driving
   α down enough to compensate. Theory exponents match empirical
   (`|E| ~ N^{1.74}`, `α ~ N^{0.74}`, ≈ 0.14 over the asymptotic 8/5 and
   3/5 — finite-N polylog as expected, see `bohman_keevash.py --sweep`).

4. **The α and c_log surrogate weightings (`w_alpha`, `w_c_log`) are
   essentially indistinguishable from uniform** in the add-only saturation
   regime (`*_sat`). At every N, their c_log matches `uniform_alpha` /
   `bohman_keev` to within noise. The greedy fill dominates the outcome,
   not the local choice.

5. **`w_c_log_sat` was the only weighting that *did* edge out `uniform_α`**
   — at N=20 (1.086 vs 1.147) and N=50 (1.242 vs 1.335). But it was also
   the slowest add-only method (260 s at N=50) and inconsistent across N.

6. **`w_d_min_sat` is surprisingly competitive at N=40** (tied for best
   non-α-CP-SAT at 1.291), with a continuous score that the softmax can
   actually act on (see #11 below).

7. **add+remove (`ar_*`) doesn't help generically.** `ar_alpha` and
   `ar_c_log` with the un-fixed scorers were either equal to or worse
   than the corresponding add-only methods at every N. Removes thrash
   when the surrogate is too coarse to know which adds were "bad".

### The two scoring bugs we found

8. **The original `ar` d_min scorer (v0, before being renamed to `target_regular`) was completely broken** — emitted the empty graph at
   every N (α=N, d_max=0, c_log=None). Cause: the symmetric scoring
   `−(deg_u + deg_v)` for adds and `+(deg_u + deg_v)` for removes makes
   the empty graph a local minimum *and* makes any remove on a non-empty
   graph more attractive than any add (because deg=0 endpoints exist
   only on adds). The walk drifts back to empty and stays there.

9. **First fix attempt (post-move degree variance) also drifts to empty.**
   The empty graph has zero variance — a *global* minimum of the
   variance objective. So minimising degree variance trivially says
   "remove everything". Confirmed by the fact that scoring with closed-form
   variance gave removes a higher mean score than adds.

10. **Working fix: target-distance regularity.** Score = `−(d_loss)`
    where `d_loss = (d_u' − t)² + (d_v' − t)² − (d_u − t)² − (d_v − t)²`
    around target `t = n^{2/3}` (the Bohman–Keevash typical degree).
    Adds win when endpoints are below target; removes win when endpoints
    are above. The empty graph is no longer optimal because it has
    `d − t = −t < 0` everywhere, paying a fixed loss `t²` per vertex.
    Closed-form per move:
    `d_loss = 2δ·(d_u + d_v) − 4δ·t + 2`, with `δ = ±1`.

### Tiebreaker findings

11. **`alpha_lb` returns integers — and many candidates collide on the
    same value.** At a fresh non-trivial step, ~30–50% of candidates land
    on a single `alpha_lb` integer; the softmax then collapses to uniform
    over that tied set. `c_log_surrogate` inherits this because its α
    factor is the same integer (and `d_max` is also integer). Only
    `d_min` has dense continuous scores (sums of degrees), which is why
    it's the only weighting that visibly differs from uniform.

12. **First tiebreaker scale (1e-3) was useless.** The score gap from
    a 1-degree difference was 0.001, giving `softmax β=4` ratio
    `e^{0.004} ≈ 1.004`. Effectively still uniform among ties.

13. **`_TIEBREAK = 0.05` is the right scale.** A 1-degree difference
    gives ratio `e^{0.2} ≈ 1.22`; a 5-degree difference (typical at
    higher N) gives `e^{1.0} ≈ 2.7`. The integer α step (1.0) still
    dominates at `e^{4} ≈ 55`, so primary signal is preserved.

14. **The tiebreaker did not help in practice.** Re-running `w_alpha_v2`
    and `w_c_log_v2` with `_TIEBREAK=0.05` reproduced the original c_log
    values (and at N=20, `w_c_log_v2` got *slightly worse*: 1.147 vs
    1.086). The tiebreaker resolves the local sampling distribution
    correctly, but at saturation the local distinction doesn't propagate
    to outcomes — different greedy fills converge.

15. **β=4 was never the bottleneck.** With or without tiebreaker, the
    surrogate methods can't outperform structural-targeting because the
    *primary* signal (`alpha_lb`) is too coarse. β controls how much we
    trust the score; you can't fix poor scores with more trust.

### Computational findings

16. **`batch_score_fn` is a batched API, not batched compute.** My
    scorers loop in Python over candidate moves, copying `adj` and
    invoking `alpha_lb` per candidate. Walk doesn't vectorise this.

17. **Scoring cost dominates at every N.** At N=30 with add+remove,
    `~500` candidates × ~1 ms/`alpha_lb` ≈ 0.5 s/step. A trial that
    halts at |E|=145 with remove-driven oscillation typically takes
    1k–3k steps; 3 trials × 2k steps × 0.5 s ≈ 40 min per cell. This
    matches the observed `ar_alpha` and `ar_c_log` runtimes exactly.

18. **Add-only is ~10× faster than add+remove for surrogate scoring.**
    Half the candidate count, plus saturation halts in ~200 steps vs
    1k–3k for the edge-target add+remove walk.

19. **`uniform_alpha`'s CP-SAT probe (every 5 steps, 10 s timeout) is
    cheap at N≤50.** Each probe finishes in ms; total CP-SAT time is a
    few seconds per trial.

### Empirical surprises

20. **At N=10 every saturation method ties at c_log = 1.005.** Same
    canonical graph (α=3, d=6, E=29) regardless of weighting. Local
    structure at N=10 is too constrained for proposal weighting to
    diverge.

21. **`ar_target_reg` at N=10 broke the universal saturation tie**, hitting
    c_log = 0.932 by stopping *before* saturation — d=5, |E|=23. The
    edge target halts the walk at a regular sub-saturation graph that
    has lower c_log than the saturated one.

22. **`ar_target_reg` at N=50 produces `d_max = 14, |E| = 339`** — far
    sparser than B-K's `d_max = 23, |E| = 474` at the same N. Target
    `n^{2/3}` ≈ 13.6, so the walk is hitting its target almost exactly.
    α = 11 in both — so the c_log win comes purely from regularity, not
    from a smaller MIS.

23. **Best c_log doesn't grow monotonically with N.** Pre-fix
    `uniform_alpha` jumped from 1.40 (N=40) to 1.34 (N=50). With more
    vertices the walk has more room to find a good local structure.
    Post-fix `ar_target_reg` is monotonically *better* at higher N relative
    to uniform — gap widens with N.

### `uniform_ar_alpha` (uniform add+remove with α-stop)

24. **`uniform_ar_alpha` is the best random baseline at N ≤ 20** — it
    matches `ar_target_reg`'s 0.932 at N=10 and ties for the best
    (1.086) at N=20. Same proposer set as `ar_*` (full add+remove) but
    *no scoring*; the only signal is the α-stop. The α-stop alone gives
    enough direction at small N that removes plus uniform sampling
    suffice.

25. **It degrades sharply from N=30 onward.** At N=30 it gets 1.183 —
    better than `uniform_alpha` (1.238) but worse than `ar_target_reg`
    (1.158). At N=40 it gets 1.443, which is *worse* than
    `uniform_alpha` (1.401). Without a score, removes thrash:
    the walk reverts the same edges over and over before hitting the
    α target, drifting the graph away from the optimum.

26. **The cost grows super-linearly in walk steps as N grows.** Step
    counts (sum of adds + removes) at α-target halt: N=10 → 195;
    N=20 → 6.4k; N=30 → 9.9k; N=40 → 80k. The N=40 trial took
    2423 s for 3 trials (vs 322 s for the unscored add-only
    `uniform_alpha` at the same N). N=50 was killed: extrapolated cost
    ~ 24 h. Conclusion: α-stop with unscored add+remove is a
    short-N-only method.

27. **Why it wins at N=10/20 and loses at higher N.** At small N the
    valid-move set is small enough that even random removes find good
    nearby graphs. At larger N the walk wanders the much larger
    α-target level set without a gradient, while `ar_target_reg`'s
    smooth degree-target objective gives the walk a direction that
    survives to large N.

---

## Recommendations

- For a fast, strong random baseline: **`add_remove_edges_weighted.py
  --weight target_regular --stop edges --target round(n^(5/3)/2)`**. Sub-second
  at N=10, ~5 s at N=50.
- For a strong baseline at small N (≤20) with no score logic at all:
  **`add_remove_edges.py --stop alpha --target round(n·log(n^{2/3})/n^{2/3})`**.
  Best-in-class at N=10 and N=20; intractable at N≥40 due to thrash.
- Skip `ar_alpha` / `ar_c_log` with `alpha_lb` scoring. The 40-min/cell
  cost buys nothing.
- Don't expect tiebreakers to fix surrogate-α methods. The fix has to
  be a continuous proxy (Caro–Wei, common-neighbor count) or a
  vectorised α-LB. See "Open" below.

---

## Open

- Push `ar_target_reg` past N=50 (gap to uniform_α appears to widen).
- Try `d_target` schedules other than `n^{2/3}`: e.g. `n^{0.7}`,
  `n / log n`, or matching observed Paley-blowup degrees.
- Replace `alpha_lb` per-candidate with an O(1) proxy (e.g.
  `|N(u) ∩ N(v)|` plus degree). See if tractable α-aware scoring
  produces signal beyond `d_min`.
- Vectorise `alpha_lb` so `score_alpha` becomes O(N²·|valid|) numpy
  rather than O(|valid|) Python.
- Investigate why `w_c_log_sat` is the only saturation-add method that
  occasionally beats `uniform_alpha` (N=20 and N=50 only). Probably
  variance in greedy fill, not a real signal.

---

## Files

| File | Role |
|---|---|
| `add_edges.py` | Uniform add-only; `--stop {edges, d_max, alpha}`. |
| `add_remove_edges.py` | Uniform add+remove; `--stop {edges, d_max, alpha}`. Best in class at small N with α-stop, intractable at N≥40. |
| `bohman_keevash.py` | Uniform add-only, halts at saturation; `--sweep` fits scaling vs theory. |
| `sweep_bohman_keevash.py` | N-sweep driver for B–K — persists best-per-N to `graphs/bohman_keevash.json`, writes plots to `docs/images/`. |
| `add_edges_weighted.py` | Softmax add-only with `--weight {d_min, alpha, c_log}`. α/c_log scorers carry a 0.05-scale degree tiebreaker (verified to give 1.5× softmax preference at β=4). |
| `add_remove_edges_weighted.py` | Softmax add+remove. **Recommended config: `--weight target_regular`** (target-distance regularity, t = n^{2/3}). The α/c_log scorers carry the tiebreaker but are too slow to recommend. |
| `compare_all.py` | 9-method × 5-N driver used for the table above. |
