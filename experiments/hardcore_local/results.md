# `experiments/hardcore_local/` — initial results

Same 98 graphs `bound_tightness/run_tightness.py --per-n-best` ran on (one $K_4$-free graph per $N \in [3, 100]$). For each, we now have $L_{HC}(G)$ alongside the global $E_{\max}(G)$ recorded earlier.

```bash
micromamba run -n k4free python experiments/hardcore_local/run_local.py
```

Total wall time: ~3 s (vs ~130 s for the SDP-heavy `bound_tightness` run; the local bound is dominated by the $\mathcal{O}(2^{d_{\max}})$ neighbourhood polynomial, not the SDP solve).

---

## Headline answer

**No — a strictly local hard-core computation does not recover $\alpha$ on the $K_4$-free frontier.** Mean $L_{HC}/\alpha \approx 0.34$; minimum $0.16$. The partition inequality $\rho_v \ge \lambda/(\lambda + Z(T_v,\lambda))$ leaves a factor-of-three gap to the global $E_{\max}$ on average, which itself is within $0.3\%$ of $\alpha$.

---

## Aggregate

| Ratio | $n$ | min | median | mean | max |
|---|---|---|---|---|---|
| $L_{HC} / \alpha$ (local recovery) | 98 | 0.162 | 0.324 | 0.338 | 0.998 |
| $\alpha / L_{HC}$ (local slack) | 98 | 1.002 | 3.085 | 3.321 | **6.17** |
| $\alpha / E_{\max}$ (global slack) | 42 | 1.0017 | 1.0019 | 1.0022 | 1.0050 |
| $L_{HC} / E_{\max}$ (local share of global) | 42 | 0.209 | 0.343 | 0.394 | 1.000 |

So local hard-core captures $\sim 34\%$ of what global hard-core captures, and global hard-core captures $\sim 99.8\%$ of $\alpha$.

---

## Paley(17) plateau chain — $L_{HC}/\alpha$ is exactly lift-invariant

| $N$ | $\alpha$ | $L_{HC}$ | $L_{HC} / \alpha$ | source |
|---|---|---|---|---|
| 17 | 3 | 0.974 | **0.3247** | `cayley` |
| 34 | 6 | 1.948 | **0.3247** | `cayley_tabu` |
| 51 | 9 | 2.923 | **0.3247** | `cayley_tabu` |
| 68 | 12 | 3.897 | **0.3247** | `cayley_tabu` |
| 85 | 15 | 4.871 | **0.3247** | `cayley_tabu_gap` |

The ratio is *constant to four decimal places* along the entire chain — an empirical confirmation of the conjecture in the README. This is exactly what one would expect: every $T_v$ in a Paley-lift graph is the same triangle-free 8-vertex template (the Paley(17) neighbourhood is $C_8$ union a disjoint edge structure inherited from the quadratic residues), and lifts do not change the iso class. So the local sum scales linearly with $N$ and the ratio stays fixed.

If $L_{HC}/\alpha = \rho^*$ on the entire chain, then any *universal* derivation that goes through $L_{HC}$ inherits a factor-$1/\rho^* \approx 3.08$ slack on the chain — i.e. the best $c_{\log}$ lower bound a local hard-core argument can produce on the plateau is at most $0.3247 \cdot 0.679 \approx 0.220$, well below Shearer's $\sim 0.28$ baseline. **Local hard-core alone is not the path to the plateau.**

---

## By N band (sanity: no degradation with N)

| $N$ band | count | min $L_{HC}/\alpha$ | mean | max |
|---|---|---|---|---|
| 3–12 | 10 | 0.343 | 0.587 | 0.998 |
| 13–22 | 10 | 0.283 | 0.340 | 0.473 |
| 23–32 | 10 | 0.223 | 0.364 | 0.476 |
| 33–42 | 10 | 0.208 | 0.310 | 0.413 |
| 43–52 | 10 | 0.201 | 0.291 | 0.473 |
| 53–62 | 10 | 0.186 | 0.279 | 0.433 |
| 63–72 | 10 | 0.162 | 0.336 | 0.476 |
| 73–82 | 10 | 0.208 | 0.293 | 0.433 |
| 83–92 | 10 | 0.196 | 0.273 | 0.359 |
| 93–100 | 8 | 0.197 | 0.294 | 0.473 |

Past $N \approx 22$ the ratio plateaus around $0.28$–$0.34$ irrespective of $N$. The $N \le 12$ row is anomalous because tiny graphs with $\alpha = 1$ or $\alpha = 2$ are trivially saturated by any non-degenerate bound — those $L_{HC}/\alpha = 0.998$ rows are $K_5$-shaped objects.

---

## By graph family

| Family | count | min | mean | median | max |
|---|---|---|---|---|---|
| Cayley plateau (incl. Paley chain) | 51 | 0.162 | 0.322 | 0.324 | 0.473 |
| SAT-certified | 17 | 0.189 | 0.269 | 0.234 | 0.476 |
| Circulant | 10 | 0.195 | 0.292 | 0.265 | 0.473 |
| Disjoint lift | 13 | 0.208 | 0.344 | 0.359 | 0.476 |
| Brute force (small $N$) | 7 | 0.473 | 0.672 | 0.642 | 0.998 |

SAT-certified non-regular graphs leave the *most* slack on the local bound (mean $0.269$, lowest median $0.234$). Disjoint lifts inherit their factor structure (each connected component's $T_v$ identical), so the family ratio is constant within each lift family. Cayley plateau lands tightly around $0.32$ — driven by the Paley(17) chain's $0.3247$ contribution.

---

## Cost: why local is fast

| Bound | Per-graph cost | Wall time on $N = 100$ graph |
|---|---|---|
| $E_{\max}$ (global) | $\mathcal{O}(N \cdot 2^N)$ — independence polynomial of $G$ | unreachable past $N \approx 46$ |
| $L_{HC}$ (local) | $\mathcal{O}(N \cdot 2^{d_{\max}})$ — independence polynomial of each $T_v$ | $\sim 50$ ms |

For $d_{\max} = 8$ (the entire Paley plateau), $2^{d_{\max}} = 256$ — tiny, regardless of $N$. So the local bound is the only hard-core-flavoured number we can compute *at all* on the larger graphs in the DB. The cost is genuinely the price of avoiding the global partition function.

---

## What this experiment does and does not say

**Does say:**
- The partition inequality $Z(G) \le Z(G[N[v]]) Z(G - N[v])$ is *not* tight on $K_4$-free frontier graphs. It loses a factor of $\sim 3$ at every vertex.
- The loss is not a finite-$N$ artefact — it is constant in $N$ along the Paley(17) lift chain to four dp.
- A purely local hard-core argument (no information flow beyond a single vertex's neighbourhood) cannot reach $\alpha$ on this class — the slack is structural.

**Does not say:**
- Whether a *less local* method that mixes neighbourhoods (correlation decay, BP fixed-point with multi-step messages) closes the gap. Subplan B's $L_{HC}$ is the cheapest possible locality; better local methods exist.
- Whether the universal-per-$d$ extension (`scripts/run_subplan_b.py --d-enum-max …`) closes the gap by taking the worst-case neighbourhood type rather than the actual one. That's a different question and is the right place to look for a Davies–Jenssen-style $K_4$-free analogue.

---

## What's next

- Port the geng triangle-free enumeration from `run_subplan_b.py` so we can also report the universal $\rho_{\min}(d)$ alongside the per-graph $L_{HC}/\alpha$ — that closes the loop with the universal direction.
- Compare $L_{HC}/\alpha$ versus a tighter local bound (e.g. tree recursion using $T_v$ depth-2 neighbourhoods) and quantify how much locality you have to give up to recover $E_{\max}$.
- Plot $L_{HC}/\alpha$ vs $N$ alongside `tightness_by_n.png`, coloured by family — should show the constant-along-chain signature visually.
