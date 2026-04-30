# `experiments/hardcore_local/` — can a strictly local hard-core computation recover α?

## Compute

- **Environment:** `k4free` conda env (numpy, networkx).
- **Typical runtime:** ~5 s for the default 98-graph benchmark.
- **Memory:** trivial (< 100 MB).
- **Parallelism:** single-threaded.

---

## Background

The exact hard-core marginal at vertex $v$,

$$
\rho_v(G,\lambda) \;=\; \mathbb{P}_\mu(v \in I) \;=\; \frac{\lambda \cdot Z(G - N[v],\lambda)}{Z(G,\lambda)},
$$

requires the partition function $Z(G,\lambda)$ of the *whole* graph — a global, $\mathcal{O}(2^N)$ quantity. The bound `hardcore_alpha` in `bound_tightness/` saturates $\alpha(G)$ to within $\sim 0.3\%$ on every $K_4$-free graph in the DB, but at the cost of computing two independence polynomials per vertex. The "hard-core is local" intuition only refers to the *model definition* (edge constraints) and the Markov property (conditional distributions); the unconditional marginal is still global.

The partition inequality $Z(G,\lambda) \le Z(G[N[v]],\lambda) \cdot Z(G - N[v],\lambda)$ rearranges to

$$
\rho_v(G,\lambda) \;\ge\; \frac{\lambda}{Z(G[N[v]],\lambda)} \;=\; \frac{\lambda}{\lambda + Z(T_v,\lambda)},
$$

where $T_v = G[N(v)]$ is the *open* neighbourhood subgraph. Summing,

$$
\alpha(G) \;\ge\; L_{HC}(G) \;=\; \max_{\lambda > 0}\; \sum_{v \in V}\, \frac{\lambda}{\lambda + Z(T_v,\lambda)}.
$$

This is **strictly local**: $\rho_v$ in the bound depends only on the iso class of $T_v$, not on $G$ as a whole. For $K_4$-free $G$ the templates $T_v$ are triangle-free graphs on $d_v$ vertices, of which there are finitely many. In principle one could enumerate every triangle-free type and take the worst-case $\lambda$ to get a *universal* per-degree bound; we tried that direction once (now removed — see "What this experiment doesn't yet answer") and found it cannot beat Shearer.

The bound chain:

$$
\alpha(G) \;\ge\; E_{\max}(G) \;\ge\; L_{HC}(G).
$$

Equality with $E_{\max}$ would require the partition inequality to be tight at every vertex, which in general it is not.

---

## Question

How much of $\alpha(G)$ does a strictly local hard-core computation recover, and what is the gap to the global $E_{\max}$ that needs $Z(G)$?

---

## Approach

1. Take every graph that `experiments/bound_tightness/run_tightness.py` recorded an $E_{\max}$ for (default: `results_per_n.csv`, the per-N best graph at each $N \in [3, 100]$).
2. For each, compute $L_{HC}(G)$ via `utils.alpha_bounds.hardcore_local`. The cost is $\mathcal{O}(N \cdot 2^{d_{\max}})$ — only the *neighbourhood* sizes matter, so this scales to large $N$ provided $d_{\max}$ stays moderate.
3. Score each graph on three ratios:
   - $\alpha / L_{HC}$ — how much $\alpha$ the local bound *misses*.
   - $L_{HC} / E_{\max}$ — how much of the global tight bound the local approximation captures.
   - $\alpha / E_{\max}$ — the global tight bound's slack (already known to be $\le 0.3\%$).

Results land in `results.csv`; digest in `results.md`.

---

## Files

| File | Purpose |
|---|---|
| `run_local.py` | Driver — reads `bound_tightness/results_per_n.csv`, hydrates each graph from `graph_db`, computes $L_{HC}$, writes per-graph CSV. CLI flags `--source`, `--out`. |
| `results.csv` | Per-graph table: graph_id, source, $n$, $\Delta$, $\alpha$, $c_{\log}$, $E_{\max}$, $L_{HC}$, all three ratios, wall time for the local computation. |
| `results.md` | Aggregate stats and the headline answer to the local-recovery question. |

The bound itself is `utils.alpha_bounds.hardcore_local`; `hardcore_alpha` (global) lives in the same module.

---

## Results

See `results.md` for the digest. Headline: the local hard-core bound recovers a *small fraction* of $\alpha$ on the K₄-free frontier — typically 30–50%. The partition inequality is far from tight on these graphs, so locality costs much more than the 0.3% slack of the global $E_{\max}$.

**Status:** active.

---

## Open questions

- [ ] Is the gap $L_{HC} / E_{\max}$ correlated with any structural feature of $G$? (Degree variance, regularity, $T_v$ template diversity?)
- [ ] Does a per-edge (rather than per-vertex) partition inequality, e.g. $Z(G) \le Z(G[A]) Z(G[B])$ with $A, B$ a balanced cut, give a tighter local bound?
- [ ] What does $L_{HC}$ look like on the explicit Paley(17) chain (the c_log plateau)? Same constant fraction of $\alpha$ at every $N$, or a chain-specific signature?
- [ ] A universal-per-$d$ extension via geng-enumerated triangle-free neighbourhood types could be added here; an earlier prototype (`scripts/run_subplan_b.py`, removed) showed it lands below Shearer at $d \le 8$, so this is a closed direction unless paired with a stronger partition inequality.

---

## Theorems that would be nice to prove

- **Conjecture (local-vs-global gap on K₄-free).** There exists a constant $c < 1$ such that for every $K_4$-free $G$,
  $$
  L_{HC}(G) \;\le\; c \cdot E_{\max}(G).
  $$
  *Why it matters:* would formalise the empirical observation that the partition-inequality slack is bounded away from zero on this class — i.e. you genuinely cannot reach $\alpha$ from a local computation, no matter how carefully you tune $\lambda$.

- **Conjecture (Paley plateau invariance).** For the Paley(17) chain $\{P_{17}^{(k)}\}_k$,
  $$
  \frac{L_{HC}(P_{17}^{(k)})}{\alpha(P_{17}^{(k)})} \;=\; \rho^* \quad \text{independent of } k.
  $$
  *Why it matters:* would say the local bound's loss scales identically with the chain's plateau, not faster — a *necessary* condition for any "local hard-core derivation of the plateau" to work.
