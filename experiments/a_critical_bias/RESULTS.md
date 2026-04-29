# `experiments/a_critical_bias/` — RESULTS

## Headline

**The structural surrogate (min-deg + twin-pair + Hajnal violations) is too coarse to drive a c_log walk past random-baseline territory and never produces an α-critical witness.** Adding the bias does shrink audit failures by ~50% at the right λ, but offers no c_log advantage over an unbiased walk.

| λ | best c_log (N=20) | α-critical / 3 | median audit fails |
|---|---|---|---|
| 0.0 (control) | **1.2288** | 0/3 | 7 |
| 0.01 | 1.4336 | 0/3 | 12 |
| 0.1 | **1.2288** | 0/3 | **4** |
| 1.0 | **1.2288** | 0/3 | 5 |
| 10.0 | **1.2288** | 0/3 | 8 |

Four of five λ tie at c_log=1.2288; λ=0.01 is strictly worse. No λ produces an α-critical graph (always ≥4 vertex-level Lemma-4 failures even with the audit being the *necessary-only* equality check, not the full edge test).

For reference: the `disjoint_lift` row in graph_db at N=20 has c_log=0.6995. The α-critical-biased walk is ~75% off the frontier — random-baseline territory.

---

## Configuration

- **Driver**: `add_remove_a_critical.py`
- **Seed**: empty graph
- **N**: 20
- **β**: 4 (softmax)
- **Trials per λ**: 3
- **Max steps per trial**: 3000
- **Audit**: necessary-only Lemma 4 equality check (`α(G\N[v]) = α(G)−1` for each v) — not the full edge α-criticality test. See "Audit caveat" below.

CSV: `results/lambda_sweep_n20_beta4.0.csv` (15 rows: 5 λ × 3 trials).

---

## Why λ doesn't help on c_log

Per-trial breakdown shows the walk easily reaches **surrogate=zero** (`min_deg_v=0, twin=0, haj=0`) at any λ ≥ 0.1. Once there, the structural penalty contributes nothing — its gradient is flat. The c_log surrogate alone takes over, and the walk's remaining behavior is identical to the unbiased control. Hence the c_log tie.

λ=0.01 is the failure mode of "small bias breaks the gradient": penalty is too small to commit to surrogate-zero structure, but large enough to slightly perturb the c_log scoring. The walk ends up at α=7 instead of α=6, with 9–13 audit failures — strictly worse than no bias.

λ=10 over-commits: the penalty dominates, the walk spends moves on cosmetic structural fixes that aren't tracking true α-criticality, and audit failures climb back up.

The sweet spot for audit (λ=0.1) gives 4 median failures vs 7 for the control — the bias *does* reduce structural distance to α-critical at the right weight, but the basic + Hajnal correlates plateau before the walk reaches a true α-critical graph.

---

## What this confirms

This is a clean **case 2** from the design discussion: c_log gain is incidental (the surrogate just enforces basic + Hajnal compliance, which is mostly a regularity bias) and the surrogate is too weak to navigate α-critical islands. The headline take from the conversation thread:

> A graph satisfies all three structural correlates (min-deg ≥ 3, twin-free, Hajnal-compliant) without being α-critical. This was theoretical-necessary-not-sufficient; the data now confirms it's empirical too.

---

## Audit caveat

The audit only checks part (i) of Lemma 4 — `α(G\N[v]) = α(G)−1` for every v. This is *necessary* for α-criticality but not *sufficient*; the maximality clause (part ii) encodes the per-edge α-criticality and isn't checked. So `is_a_critical=False` is sound (graph is provably not α-critical), but `is_a_critical=True` would be unverified. In this run nothing passed even the equality check, so the conclusion (no α-critical witnesses) holds. A future iteration should add the per-edge audit (~|E| CP-SAT calls) for ground-truth verification.

---

## Recommended next steps

The basic structural surrogate has been explored to the bottom. To push further, two directions:

### (a) `s_lemma4` proxy — sharper surrogate

Replace (or augment) the basic counters with a direct proxy of vertex-α-criticality:

```
s_lemma4(G) = #{ v : α_lb(G \ N[v]) ≠ α_lb(G) − 1 }
```

Cost: `N` α_lb calls per state, ~20× the current per-step cost at N=20. Empirically the basic surrogate plateaus at ~4–8 audit failures; `s_lemma4` directly measures this number, so the gradient stays informative all the way to α-critical.

If this works, the walk should land on graphs with audit failures = 0 — *truly α-critical*. The c_log improvement is the open question.

### (b) Tabu over the existing scorer

Tabu's diversification is what fails on disconnected α-critical islands. Even with the basic surrogate, a tabu walk that escapes local minima (rather than re-running greedy from scratch) might break out of the c_log plateau. This stays on the existing scorer but adds the missing exploration pressure.

### (c) Try `--seed-graph from-db` at N=20

Untested in this sweep. Starting from the lift seed at N=20 (c_log=0.6995) might let the walk *locally improve* a near-frontier graph, even if it can't reach the frontier from empty. This separates "can the bias improve a good seed" from "can the bias find a good seed from scratch" — they may have different answers.

(a) is the most direct fix. (c) is the cheapest sanity check. (b) is the right move only if (a) and (c) both still leave audit failures at ≥1.
