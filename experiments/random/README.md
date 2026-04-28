# `experiments/random/` — random K₄-free edge processes

## Compute

- **Environment:** k4free conda env, local.
- **Typical runtime:** seconds at N≤30 for the cheap methods (uniform, B–K, target_regular). The α / c_log surrogate methods are ~10× slower because every candidate triggers a greedy α-LB probe.
- **Memory:** negligible (<200 MB).
- **Parallelism:** single-threaded; trials run sequentially inside one `EdgeFlipWalk`.

---

## Background

All processes here are built on `search.stochastic_walk.edge_flip_walk.EdgeFlipWalk`, which exposes a single move type `(u, v, is_add)` with K₄-freeness enforced by the walk. Different "processes" differ only in three knobs:

1. **Proposer** — which moves are exposed (adds only, or adds + removes).
2. **Scorer** — how candidates are ranked (uniform, regularity, surrogate-α, surrogate-c_log).
3. **Stop rule** — when to halt (edges target, d_max target, exact α target, saturation).

These runs serve as the unbiased reference point that every smarter searcher in the repo must beat. **All numerical results are in [`RESULTS.md`](RESULTS.md);** this README explains *why* each process exists.

---

## Processes and the intuitions behind them

### `add_edges.py` — uniform add-only with explicit stop

The most basic K₄-free process: pick a uniformly random K₄-safe non-edge, add it, repeat until *some* halt rule fires. The point of the script is to ask **which halt rule produces the best c_log**, since the choice of stop is the only knob.

- `--stop edges`: stop at a target edge count. Naive but the natural reference.
- `--stop d_max`: stop when any vertex hits a target degree.
- `--stop alpha`: stop when α(G) reaches a target — uses **exact CP-SAT** every 5 steps.

Intuition: $c_{\log} = \alpha \cdot d_{\max} / (N \ln d_{\max})$, so the closer your stop rule is to one of those quantities, the less slack you leave at halt. Result (see RESULTS.md): alpha-stop wins by 0.1–0.4 at every N.

### `add_remove_edges.py` — uniform add+remove with explicit stop

The simplest add+remove walk: full valid moveset (adds + removes) exposed to the walk's uniform sampler, no scoring at all. Same `--stop {edges, d_max, alpha}` knobs as `add_edges.py`. The interesting configuration is `--stop alpha`: the walk halts when α drops to a target, and removes give it room to *dodge* a high-$d_{\max}$ plateau before the target hits. An add-only walk hitting the same α target tends to land at higher $d_{\max}$ because once a vertex saturates the local K₄-safe set, the only way forward is to keep stacking edges on lower-degree vertices.

Why include it: it isolates the *value of removes alone*, with no scoring help. If add+remove with no bias still beats add-only at the same α target, removes are intrinsically useful. If not, the gains from `ar_target_reg` come purely from its score, not from move-set richness.

### `bohman_keevash.py` — uniform add-only, no stop

The canonical K₄-free random process from the literature (Bollobás–Riordan 2000; Bohman 2009 lower; Wolfovitz 2010 upper match). Same uniform-add proposer, but **no external stop**: run until no K₄-safe non-edge remains (saturation). Theoretical guarantees a.a.s. (Wolfovitz, [arXiv:1008.4044](../../docs/papers/The%20K4-free%20process.pdf)):

$$|E(M(n))| = \Theta\!\left(n^{8/5}\, (\ln n)^{1/5}\right), \qquad \alpha(M(n)) = O\!\left(n^{3/5}\, (\ln n)^{1/5}\right), \qquad \Delta \approx \tfrac{2|E|}{n} \sim n^{3/5}\,(\ln n)^{1/5}.$$

These match Bohman's matching lower bound on $|E|$ up to constants and tighten Krivelevich's earlier $O(n^{3/5}\,(\ln n)^{1/2})$ on $\alpha$ by a factor $(\ln n)^{3/10}$. See [`docs/processes/BOHMAN_KEEVASH.md`](../../docs/processes/BOHMAN_KEEVASH.md) for a full sweep + scaling plots.

Why include it: it's the strongest *unstructured* random baseline known. Anything we build that doesn't beat B-K isn't really doing anything. `--sweep` fits empirical scaling exponents and verifies theory match.

Intuition for why it's mediocre on c_log: saturation pushes Δ way past the optimal — once a vertex is over its target degree, every additional edge there increases d_max without buying enough α reduction to pay for it.

### `add_edges_weighted.py` — softmax add-only with structural scoring

Same uniform-add proposer, but scores candidates by a heuristic and samples via softmax. Three weighting modes ask three different questions:

- `--weight d_min`: prefer adding to *low-degree* endpoints. The simplest regularity bias — push the graph toward an even degree distribution.
- `--weight alpha`: prefer adds that minimise the **greedy α lower bound** on the post-add graph. Directly targets the c_log numerator at every step.
- `--weight c_log`: prefer adds that minimise the **surrogate c_log** post-add (using the same greedy α plus the easy d_max).

These let us answer: "does smarter ranking of *each individual add* beat just stopping at the right time?" Result: mostly no. At saturation the local distinction doesn't propagate — different greedy fills converge to similar c_log.

The α / c_log scorers also revealed a structural problem (see RESULTS finding #11): `alpha_lb` returns *integers*, so many candidates collide on the same value and the softmax can't distinguish them. We added a small degree-tiebreaker (`_TIEBREAK = 0.05`) to break those ties — a 1-degree difference gives ratio $e^{4 \times 0.05} \approx 1.22$, while a 1-unit $\alpha$ step still dominates at $e^{4} \approx 55$.

### `add_remove_edges_weighted.py` — softmax add+remove

Same softmax scoring, but the proposer exposes the **full valid moveset** (adds + removes). The walk can back out of bad adds. This sounds strictly better, but in practice removes thrash unless the score is sharp enough to know which adds were actually wrong.

Three weights:

- `--weight target_regular`: this is the unique weighting that justifies allowing removes. It scores moves by how much they *reduce squared distance to a target degree* $t = n^{2/3}$ (the B–K typical degree). Adds win when both endpoints are below target; removes win when both endpoints are above. The empty graph is *not* an attractor because every vertex pays loss $t^2$ there. **This is the single best random baseline in the repo** — see RESULTS.md.
- `--weight alpha`: same surrogate-α score, now over both add and remove candidates. Doesn't help (removes thrash on integer-α ties), and is computationally painful: ~500 candidates × 1 ms greedy α per step × thousands of steps to hit edge target = ~40 min/cell at N=30.
- `--weight c_log`: same story as `alpha`. Slow and not better.

Why `target_regular` works: a low-$c_{\log}$ K₄-free graph has to be near-$d$-regular (otherwise $d_{\max}$ is bigger than necessary), so directly *targeting* $d$-regularity with a continuous score (squared distance $\ell(d) = (d - t)^2$, not just "low degree wins") gives the walk a smooth gradient toward the right structure — without ever computing $\alpha$. The regularity does the $c_{\log}$ work.

The per-move score is $-\Delta\ell$ where

$$\Delta\ell = 2\delta(d_u + d_v) - 4\delta t + 2, \qquad \delta = \begin{cases}+1 & \text{add}\\-1 & \text{remove}\end{cases}$$

### `compare_all.py` — comparison driver

Runs all 9 method × N combinations and prints a table. Used to produce RESULTS.md. Not a method itself.

---

## Files

| File | What it is |
|---|---|
| `add_edges.py` | Uniform add-only with `--stop {edges, d_max, alpha}`. |
| `add_remove_edges.py` | Uniform add+remove with `--stop {edges, d_max, alpha}`. The unscored add+remove baseline. |
| `bohman_keevash.py` | Uniform add-only, halts at saturation. Single canonical entry point: `--n N` (single-N), `--sweep` (N-range with CSV + plots + best-per-N persistence to `graphs/bohman_keevash.json`), `--sweep --quick` (log-log fit only). |
| `add_edges_weighted.py` | Softmax add-only with `--weight {d_min, alpha, c_log}` and degree tiebreaker on the α / c_log surrogate scores. |
| `add_remove_edges_weighted.py` | Softmax add+remove with `--weight {target_regular, alpha, c_log}`. **`target_regular` is the recommended config** (squared distance to $t = n^{2/3}$). |
| `compare_all.py` | 9-method × 5-N driver used to produce `RESULTS.md`. |
| `RESULTS.md` | Numerical results: best c_log per N for every method, plus detailed findings on what worked, what broke, and why. |

---

## TL;DR

Numbers live in [`RESULTS.md`](RESULTS.md). The headline: **structural targeting (regularity toward $n^{2/3}$) beats every other random baseline at $N \geq 30$**, including expensive surrogate-α scoring and Bohman–Keevash. The lesson is that in the random regime, *what kind of graph you're aiming at* matters more than *how hard you optimize toward α directly*.
