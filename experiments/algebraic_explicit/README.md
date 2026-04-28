# experiments/algebraic_explicit

## Purpose

This folder houses the closed-form algebraic constructions of K₄-free graphs —
families that are fully determined by a single integer parameter q (usually a
prime), with no search or randomness involved. The goal is to evaluate how well
these classical constructions compete against the `c_log` benchmark of P(17) ≈
0.679 and against heuristic searches in the rest of the repo.

These are distinct from the algebraic *search* methods elsewhere (`cayley_tabu`,
`circulant_fast`, etc.) which search *over* algebraically structured spaces.
Here, the construction is explicit: given q, the graph is uniquely defined.

---

## Constructions

| Construction | File | Formula for N | Parameter |
|---|---|---|---|
| Erdős–Rényi polarity ER(q) | `polarity.py` | q²+q+1 | prime q |
| Brown unit-sphere | `brown.py` | q³ | odd prime q ≥ 5 |
| Norm-kernel Cayley | `norm_graph.py` | q²−1 | prime q |
| Power-residue Cayley (Paley/cubic/sextic) | `prime_circulants.py` | p (prime) | prime p, index k∈divisors(p−1) |
| Mattheus–Verstraete Hq* | `mattheus_verstraete.py` | q²(q²−q+1) | prime q ∈ {2,3,5,7} |

---

## Results

### Power-residue Cayley (`prime_circulants`, formerly `cayley`)

Best of the algebraic families. The Paley graph P(17) (k=2, n=17) holds the
overall record and is the benchmark for the whole repo.

| n | k | c_log | α | d_max |
|---|---|---|---|---|
| 17 | 2 (Paley) | **0.6789** | 3 | 8 |
| 19 | 3 (cubic) | 0.7050 | 4 | 6 |
| 13 | 2 (Paley) | 0.7728 | 3 | 6 |
| 37 | 6 (sextic) | 0.8145 | 9 | 6 |
| 31 | 3 (cubic) | 0.8406 | 6 | 10 |
| 67 | 3 (cubic) | 0.8498 | 8 | 22 |

Only k ∈ {2, 3, 6} were swept. All divisors of p−1 should be tried — the
current sweep is incomplete and may be missing lower c_log hits at larger
primes.

### Erdős–Rényi polarity (`polarity`)

C₄-free (hence K₄-free) by construction. Competitive at small N but c_log
grows with q, staying well above the Paley benchmark.

| n | c_log | α | d_max |
|---|---|---|---|
| 73 | 0.9539 | 17 | 9 |
| 57 | 1.0124 | 15 | 8 |
| 31 | 1.0802 | 10 | 6 |

### Mattheus–Verstraete (`mattheus_verstraete`)

Benchmark construction from the literature (arXiv:2306.04007). c_log grows
with q — designed to prove Ramsey bounds, not to minimize c_log. Best is
c_log ≈ 1.395 at n=12. Not competitive for the objective.

### Brown unit-sphere (`brown`)

Only one instance in the DB (n=125, c_log=1.411). Large N and high degree make
α computation expensive. Not competitive.

### Norm-kernel Cayley (`norm_graph`)

No results in the DB yet — construction defined but driver not run. Eligible N:
{3, 8, 24, 48, 120, 168, 288, ...}.

---

## Running

```bash
# All eligible N up to a cap (generated from the algebraic formula)
micromamba run -n k4free python experiments/algebraic_explicit/run.py --construction polarity --max-n 200
micromamba run -n k4free python experiments/algebraic_explicit/run.py --construction prime_circulants --max-n 500

# Specific N values
micromamba run -n k4free python experiments/algebraic_explicit/run.py --construction brown --ns 125 343

# Dry run (no write to graph_db)
micromamba run -n k4free python experiments/algebraic_explicit/run.py --construction polarity --max-n 200 --no-save
```

## Open questions

- **prime_circulants**: only k ∈ {2, 3, 6} tested. Sweeping all divisors of
  p−1 may find lower c_log at large primes.
- **polarity**: prime-power q (q = 4, 8, 9, ...) handled separately in
  `run_polarity_extended.py`, which uses `search/_fq.py` for GF(q) arithmetic.
- **norm_graph**: not yet run; worth comparing against circulant search results
  at the same N values.
