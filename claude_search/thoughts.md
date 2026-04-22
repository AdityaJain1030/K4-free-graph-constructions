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

---

## gen_007–017 checkpoint (catalog ports + degree-cap mutations)

**Context**: Fresh start. Ported NON_VT_CATALOG entries 1–10, then mutated bohman_keevash with degree capping.

**Attempt**: (1) Faithfully port catalog entries at their natural N; (2) Find which family hits N ∈ [30,100]; (3) Mutate greedy K₄-free with cap = √(2N), then cap = √N.

**Expected**: Catalog ports isolate to single N (e.g., ER(7)→N=57, unital→N=91), low coverage. Random greedy is baseline; degree cap reduces α.

**Observed**: Best = gen_017 (K₄-free + cap=√N), c=1.0022 @ N=31, 71 valid N. gen_009 (ER polarity q=7), c=1.0124 @ N=57 competitive. Bohman baseline (no cap) = c=1.2775, capping improves ~20%.

**Next**: Try bipartite seeding (phase 1 = balanced bipartite, phase 2 = add K₄-free edges) or random-order two-phase. Currently ~0.36 above target; need structural shift for final ~30%.

## gen_018–026 checkpoint

**Attempted**: Two-phase with bipartite base (gen_018: c=3.56, worse), cap exponent sweep (gen_019–025), asymmetric-lift v2 (gen_026: c=1.51, worse).

**Result**: Optimal cap exponent is N^0.58–0.62 (gen_023, gen_025, c=1.0117 both). Gen_017 (cap=N^0.5) achieves c=1.0022 @ N=31, best so far.

**Observation**: Degree capping trades d_max reduction for α reduction; optimal balance at exponent ≈0.5-0.6. Further improvements require structural innovation, not parameter tuning.

**Next**: Implement remaining catalog entries (polarity variants at different q, asymmetric_lift with different bases, two-orbit variants) or hybrid approaches (e.g., phase 1 = ER base, phase 2 = greedy with cap).

## gen_027–030 breakthrough (hybrid ER + greedy)

**Context**: Degree capping on greedy K₄-free was saturating around c≈1.0. Tried hybrid approach combining algebraic structure with random greedy.

**Attempt**: (1) Phase 1 = build ER(q) polarity graph (algebraic, non-VT by construction), (2) Phase 2 = add more edges via K₄-free greedy with degree cap.

**Expected**: Algebraic base provides two-orbit structure; greedy phase avoids vt symmetries. Expected moderate improvement.

**Observed**: **BREAKTHROUGH** — gen_027 (ER(5) base + greedy, cap=N^0.55) achieves c=0.9418 @ N=32 with 70 valid N. First candidate to break below 1.0. Gen_028 (looser cap) = 0.9893, gen_029 (tighter cap) = 0.9464. Gen_030 (ER(7) base) = 1.0061, showing ER(5) is optimal base here.

**Next**: Continue with hybrid variants—different ER q values, different cap exponents, other bipartite bases. Target < 0.85 next, then < 0.75.

## Session summary (31 candidates, 27 evaluations)

**Achievements**:
- Ported 6 catalog entries: mv_hermitian (q=3, N=63), unital_incidence (q=3, N=91), er_polarity (q=5,7), bohman_keevash (K₄-greedy), ramsey_two_phase, two_orbit_bipartite.
- Discovered **hybrid ER+greedy** architecture: algebraic phase 1 (ER polarity) + random phase 2 (K₄-free greedy with cap=N^0.55).
- **BREAKTHROUGH**: First candidates to break c < 1.0 (gen_027: c=0.9418 @ N=32, 70 valid N).
- Comprehensive parameter sweep on cap exponents [0.35–0.65]; optimal found at 0.5–0.6 range.

**Key insights**:
1. Pure greedy K₄-free + degree capping saturates at c≈1.0. Algebraic bases essential for further improvement.
2. Hybrid ER(5) base better than ER(7) or unital for this application (likely due to N=31 fitting greedy phase well).
3. Degree cap exponent is critical tuning parameter; N^0.55 optimal for hybrid, N^0.5 for pure greedy.
4. Only 0.25 above target (0.9418 vs 0.6789); final push likely requires three-phase construction or entirely new family.

**Candidates to continue next**:
1. Hybrid variants: test cap ∈ [0.53, 0.57], other ER q, Clebsch/SRG bases.
2. Three-phase: Phase 1 (structure), Phase 2 (greedy), Phase 3 (perturbation).
3. Non-catalog innovation: if above fails, try Cayley graph + greedy, or random Ramsey with structure hints.

## Checkpoint at gen_050 (2026-04-22)

50 candidates written. Best c=0.9593 at N=30 (gen_037, random regular K4-free). All 10 catalog entries have at least one implementation. Now in mutation phase. Key gap: need α≤5 at N=30 with d_max=7; currently at α=8. Next focus: multi-start best-selection, higher-degree RR variants, and SA-guided edge swaps to systematically reduce α. Ramsey theory (R(4,6)≥36) guarantees K4-free graphs with α=5 at N=30 exist — finding them is the bottleneck.
