# McKay SRG catalog files

These are graph6-encoded enumerations from
**Brendan McKay's combinatorial-data archive**:

> <https://users.cecs.anu.edu.au/~bdm/data/graphs.html>

Each file `sr<v><k><λ><μ>.g6` lists every non-isomorphic strongly-regular
graph with parameters `srg(v, k, λ, μ)`, one per line. The catalog is
the result of years of accumulated computer-search by McKay,
Spence, Soicher, Brouwer, and others.

## Files in this directory

| File | (v, k, λ, μ) | Count | Notes |
|---|---|---:|---|
| `sr25832.g6` | (25, 8, 3, 2) | 1 | Schläfli graph complement |
| `sr251256.g6` | (25, 12, 5, 6) | 15 | |
| `sr261034.g6` | (26, 10, 3, 4) | 41 | |
| `sr271015.g6` | (27, 10, 1, 5) | 32 | |
| `sr281264.g6` | (28, 12, 6, 4) | 41 | |
| `sr291467.g6` | (29, 14, 6, 7) | 41 | |
| `sr351668.g6` | (35, 16, 6, 8) | 3,854 | Conference graphs at q = 9, …; mostly non-VT |
| `sr351899.g6` | (35, 18, 9, 9) | 3,854 | |
| `sr361446.g6` | (36, 14, 4, 6) | ~180,000 | Largest class screened |
| `sr401224.g6` | (40, 12, 2, 4) | 28,798 | |

## Re-downloading

If files are missing (e.g. cleaned out for a fresh checkout), grab
them from the source:

```bash
cd experiments/srg_catalog/g6
for f in sr25832.g6 sr251256.g6 sr261034.g6 sr271015.g6 sr281264.g6 \
         sr291467.g6 sr351668.g6 sr351899.g6 sr361446.g6 sr401224.g6; do
  curl -O https://users.cecs.anu.edu.au/~bdm/data/$f
done
```

`run.py` prints these `curl` lines automatically for any class whose
file is missing, so a normal run will tell you exactly what to fetch.

## Citing

If you use these enumerations downstream, cite McKay:

> Brendan D. McKay, *Combinatorial Data*,
> <https://users.cecs.anu.edu.au/~bdm/data/>.

For the underlying isomorph-rejection algorithm:

> B. D. McKay, *Practical graph isomorphism*,
> Congressus Numerantium **30** (1981), 45–87.
