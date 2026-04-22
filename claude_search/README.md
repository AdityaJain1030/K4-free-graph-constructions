# claude_search — ARCHIVED

> **This experiment is archived. It did not find a sub-Paley construction.**
>
> After 110 evaluations across 10 non-VT graph families, the best result was
> **c = 0.9593** — 41% above the P(17) target of 0.6789. No candidate
> in the run came within striking distance of the target. The candidate
> programs have been moved to `candidates/archive/`. Results are preserved
> in `results.jsonl` and `leaderboard.md` for reference.
>
> See `docs/NON_VT_SEARCH.md` for the full post-mortem: what was tried,
> why each approach failed, and why the non-VT direction was closed.

---

## What this was

An environment where a Claude Code agent evolved graph-construction
functions `construct(N) -> edge_list` targeting **non-VT** K₄-free graphs,
trying to beat the Paley P(17) benchmark of c ≈ 0.6789.

The agent worked through a catalog of 10 non-VT families from the literature
(`NON_VT_CATALOG.md`), writing and evaluating candidates over a single
session (2026-04-22, ~3 hours).

## Why it didn't work

**The seed problem.** Non-VT graph construction requires landing seeds in a
good basin. The 561-bit adjacency space at N=34 has no known structural
parameterisation that places seeds near a sub-0.6789 region. Without that,
any search — LLM-generated or otherwise — explores the wrong neighbourhood.

**The objective mismatch.** This is a "find one good graph in a deterministic
environment" problem. RL-shaped methods (including LLM evolution) optimise
expected return, not max-over-samples. Tabu search with good seeds is the
right tool; the LLM provided no better seeds than random initialisation.

**The competition.** The Cayley/circulant SAT pipeline (currently running)
produces certified improvements at N=43, 47, 62, 71, 73 in a single sweep.
110 LLM evaluations achieved c=0.9593; SAT-over-circulants beat that
routinely within seconds per N.

See `docs/NON_VT_SEARCH.md` §3 for the detailed case.

## Preserved artefacts

| File / dir                  | Contents                                       |
|-----------------------------|------------------------------------------------|
| `results.jsonl`             | Append-only history of all 110 evaluations     |
| `leaderboard.md`            | Final rankings snapshot                        |
| `candidates/archive/`       | All 97 candidate `.py` files (gen_001–gen_096) |
| `insights.md`               | Agent's running mathematical observations      |
| `thoughts.md`               | Agent's per-iteration process notes            |
| `NON_VT_CATALOG.md`         | The 10 literature families the agent worked from |

## Final stats (2026-04-22)

```
Total evaluations:          110
Non-VT candidates:           77 / 110
Stage 2 triggered:           20  (best_c < 1.0 in Stage 1)
Achieved best_c < 1.0:       20
Beat P(17) (c < 0.6789):      0

Best c overall:           0.9593  (gen_037, random d-regular + K4 repair, N=30)
Best non-VT family:       core_periphery  (best=1.3049 after 58 attempts, STALE)

Failure breakdown (per-N evals):
  d_max too low:   40.5%
  crash:            2.8%
  timeout:          1.3%
  not K4-free:      0.3%
```

## Infrastructure notes (if ever reactivated)

The eval/leaderboard pipeline is intact and could be reused with a different
objective (e.g. Cayley-restricted construction, or a different graph property).
The sandbox settings in `.claude/settings.local.json` remain valid.

To re-run from scratch:
```bash
: > results.jsonl
rm -f leaderboard.md logs/run_*.log
# restore candidates from archive if needed
```
