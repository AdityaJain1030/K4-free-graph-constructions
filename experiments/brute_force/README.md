# `experiments/brute_force/` — exhaustive K₄-free ground truth via geng

## Compute

- **Environment:** k4free conda env (local)
- **Typical runtime:** N≤8 instant; N=9 ~10 s; N=10 ~5–6 min
- **Memory:** ~100 MB (top-k bounded; geng output is streamed)
- **Parallelism:** single-threaded (geng pipes one graph at a time)

---

## Background

nauty's `geng` can enumerate all non-isomorphic graphs on N vertices
with arbitrary constraints. The `-k` flag restricts output to K₄-free
graphs. Each graph is streamed in graph6 format and handed to the scorer
without materialising the full list in memory.

---

## Question

What do the optimal graphs look like for small N?

---

## Approach

For each N, stream every non-isomorphic K₄-free graph from `geng -k`,
compute α via clique-cover B&B, score by `c_log = α · d_max / (N · ln d_max)`,
and print the best graph per (α, d_max) pair.

**Feasibility ceiling: N=10.** Beyond that, geng output is too large for
exhaustive enumeration — use `experiments/SAT/` for certified optima at
larger N.

---

## Files

| File | Purpose |
|---|---|
| `run_brute_force.py` | Driver — sweep N range, enumerate all K₄-free graphs, print best per (α, d_max) |

```bash
# Single N
micromamba run -n k4free python experiments/brute_force/run_brute_force.py --n 8

# Full sweep N=3..10
micromamba run -n k4free python experiments/brute_force/run_brute_force.py \
    --n-min 3 --n-max 10
```

**Requires:** `geng` on PATH (part of nauty/traces).

---

## Results

**Status:** closed

The optimal graph (by `c_log`) per N is persisted to graph_db with
`source=brute_force, filename=brute_force.json`.

| N  | best c_log | α | d_max | d_min | \|E\| | regular |
|----|-----------:|--:|------:|------:|------:|:-------:|
| 3  | 0.9618     | 1 | 2     | 2     | 3     | ✓ |
| 4  | 1.3654     | 2 | 3     | 1     | 4     | · |
| 5  | 1.0923     | 2 | 3     | 1     | 5     | · |
| 6  | 0.9102     | 2 | 3     | 2     | 7     | · |
| 7  | 0.8244     | 2 | 4     | 3     | 11    | · |
| 8  | 0.7213     | 2 | 4     | 4     | 16    | ✓ |
| 9  | 0.9102     | 3 | 3     | 2     | 10    | · |
| 10 | 0.8656     | 3 | 4     | 2     | 14    | · |

**Observations.**
- N=8 is the small-N champion at c_log≈0.7213, achieved by the unique
  4-regular K₄-free graph on 8 vertices (the 3-cube / K₄,₄ family —
  α=2, d_max=4, 16 edges, regular).
- c_log is **non-monotone** in N at this scale: it dips at N=8 then
  bounces back at N=9 (which can't sustain a comparable regular K₄-free
  structure with α=2), and the regular-only N=3 (triangle) is also a
  local minimum.
- **Regularity tracks the optima**: the two regular winners (N=3, N=8)
  are exactly the local minima of the c_log curve. Non-regular optima
  appear when no K₄-free regular graph exists at the right (α, d_max).
- α grows slowly: α=1 only at N=3, α=2 from N=4–8, α=3 from N=9–10.
  Each α-jump increases c_log discontinuously.
- All N=3..10 optima have c_log > Paley(17)'s 0.679 — the small-N
  regime is genuinely harder per vertex than the P(17) construction.

---

## Open questions

- [ ] Does the regularity / c_log alignment continue past N=10?
      (SAT-certified optima are needed to answer for N≥11.)
- [ ] Are the N=8 and N=3 minima part of a larger family of regular
      K₄-free graphs whose c_log dips?

---

## Theorems that would be nice to prove

- **Conjecture:** every local minimum of `c_log` over N is achieved by
  a regular K₄-free graph.
  *Why it matters:* would let us restrict every search at competitive N
  to the regular slice, collapsing the move space dramatically.
