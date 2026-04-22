# Agent process log

Append-only log of the agent's reasoning per candidate. Counterpart to
`insights.md`:

- `insights.md` captures **mathematical** observations (what the graph
  structure did).
- `thoughts.md` captures **process** — what was tried, what was
  expected, how the result compared.

Format per entry:

```
## gen_NNN_<slug>

**Context**: what prior candidates / insights led here.
**Attempt**: one-sentence description of what this candidate does.
**Expected**: what score/pattern you predicted.
**Observed**: what the eval actually showed.
**Next**: what this result implies for the next candidate.
```

Each paragraph is ≤ 6 lines. Read the tail before writing a new
candidate so you don't retrace a dead branch.
