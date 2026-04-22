# Mathematical insights — persistent memory for the optimizer

This file is append-only. Write 1–3 lines per evaluation summarizing what
you **learned mathematically**, not what you scored. Read it before choosing
your next family. Do not delete or rewrite existing entries.

---

- **Degree capping in K₄-greedy**: reduces c significantly (gen_011→gen_016→gen_017: 1.2775 → 1.0124 → 1.0022). Tighter cap trades edge density for α reduction; effect diminishes as cap → √N.
- **ER(q) polarity scalings**: at fixed projective N=57 (q=7), c=1.0124; at N=31 (q=5), c=1.0802; algebraic constructions bottleneck on their natural N, isolated from grid unless extended.
- **Bohman–Keevash near target**: random greedy + degree constraint achieves c ≈ 1.0 across [30,100], only ~0.36 above 0.6789 line; further structural innovation (perturbation, bipartite seeding, hybrid phases) needed.
- **Hybrid ER+greedy breakthrough** (gen_027): ER(5) algebraic base (N=31) + greedy phase with cap=N^0.55 achieves c=0.9418 @ N=32, 70 valid N. Bridging structure (ER polarity orbits) + random greedy (non-VT symmetry breaking) reduces c by ~0.1 vs pure greedy.

## 2026-04-22 Session Observations
- ER polarity at N=57 (q=7): c=1.0124, α=15, d_max=8. Best algebraic result.
- Random regular K4-free (gen_037): c=0.9593 @ N=30, α=8, d_max=7. Best overall. RR start naturally gives smaller α than greedy K4-free process.
- Exact-IS hill climbing (gen_030): c=0.9811 @ N=33. Exact α guidance helps vs greedy.
- MV Hermitian at q=3 (N=63): α≈18 vs theoretical ~8. RR approach is more effective in practice.
- To beat 0.6789 at N=30 with d_max=7: need α≤5. Currently at α=8. Gap = 3.
