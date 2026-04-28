# `experiments/<name>/` — [one-line description]

<!--
HOW TO USE THIS TEMPLATE
Copy this file to experiments/<name>/README.md and fill in every section.
Delete sections that genuinely don't apply (e.g. "Open questions" for a
closed negative result). Remove all HTML comments before committing.
-->

## Compute

<!--
Where can this experiment run, and how long does it take?
Be specific so someone can decide whether to run it locally or queue it.
Examples:
  - "Local (k4free env). Single n=30 run: ~2 min. Full sweep n=10..50: ~4 h."
  - "Server only (200 GB / 32-core). Each solve can use all 32 workers.
     Typical wall time: 6–12 h for N=20..30."
  - "Local for N≤20; server recommended for N>20."
-->

- **Environment:** <!-- k4free conda env / dedicated env / cluster -->
- **Typical runtime:** <!-- per-n time and full-sweep time -->
- **Memory:** <!-- peak RSS if notable -->
- **Parallelism:** <!-- single-threaded / multi-worker / cluster sub file -->

---

## Background

<!--
Anything a reader needs to know that is NOT in the top-level README.md.
Skip definitions that are already standard there (c_log, K4-free, Paley(17),
α, θ, Hoffman bound). Only add what's specific to this experiment's domain.
Cross-link to docs/ when a full derivation lives there.
-->

---

## Question

<!--
One sharp sentence. "Does X work?" or "What is the best Y subject to Z?"
This is the sentence that goes in the quick-reference table in README.md.
-->

---

## Approach

<!--
How do you answer the question? Describe the algorithm / construction /
benchmark setup at the level where a reader could re-implement it.
Include:
  - What the search space is (graphs? connection sets? something else?)
  - What oracle or objective is being optimised (c_log? |E|? α? runtime?)
  - Any key design decisions and why they were made
  - Known limitations or assumptions
-->

---

## Files

| File | Purpose |
|---|---|
| `run_<name>.py` | <!-- driver — what it does and what flags matter --> |

<!--
Add rows for every script, result file, plot, or log that lives in this
folder. Reference files in reference/ or logs/ that belong to this
experiment too.
-->

---

## Results

<!--
What did you find? Give numbers where you have them.
  - Best c_log achieved and at which N
  - Comparison to Paley(17) (c ≈ 0.679) and to the random baseline (c ≈ 1.1–1.2)
  - Whether the approach beats, ties, or falls below the SAT-certified optimum
  - Any surprising structure in the winners
If the result is negative, say so explicitly and explain why.
-->

**Status:** <!-- open / closed-positive / closed-negative -->

---

## Open questions

<!--
List specific, actionable follow-ups. Each item should be something a
future session could pick up and run or prove without re-reading this whole
file. Delete this section if the experiment is fully closed.
-->

- [ ] <!-- question 1 -->

---

## Theorems that would be nice to prove

<!--
Conjectures or partial results that the experiment suggests but doesn't
settle. Phrase each as a precise mathematical statement (or as close as
you can get). Include why proving it would be useful to the search.
Delete this section if you have nothing.
-->

- **Conjecture:** <!-- statement -->
  *Why it matters:* <!-- one line -->
