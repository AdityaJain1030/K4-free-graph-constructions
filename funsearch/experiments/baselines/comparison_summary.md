# Structural Comparison Summary

## Convergence (rolling mean of c over window=10, threshold=1% relative change)

| method | first converged N | rolling c at converge | rel change |
|--------|-------------------|-----------------------|------------|
| method1 | — (did not converge) | 0.9618 | — |
| method2 | — (did not converge) | 1.0857 | — |
| method2r | — (did not converge) | 1.0857 | — |
| method3 | — (did not converge) | 1.0099 | — |
| method3b | — (did not converge) | 1.0099 | — |
| method4 | — (did not converge) | 1.0099 | — |

## Isomorphism matches (up to pynauty canonical certificate)

Total matches: **49** (of 225 comparisons)

| method1 | method2 | N | c |
|---|---|---|---|
| method1 | method2r | 6 | 0.9102 |
| method1 | method2r | 7 | 1.1703 |
| method2 | method2r | 17 | 1.1315 |
| method2 | method2r | 18 | 1.0687 |
| method2 | method2r | 19 | 1.2149 |
| method2 | method2r | 20 | 1.0857 |
| method3 | method3b | 6 | 0.9102 |
| method3 | method3b | 7 | 1.1703 |
| method3 | method3b | 8 | 1.024 |
| method3 | method3b | 9 | 0.9102 |
| method3 | method3b | 10 | 0.8656 |
| method3 | method3b | 11 | 0.993 |
| method3 | method3b | 12 | 0.9618 |
| method3 | method3b | 13 | 1.0304 |
| method3 | method3b | 15 | 0.9618 |
| method3 | method3b | 16 | 0.9708 |
| method3 | method3b | 17 | 0.9849 |
| method3 | method3b | 18 | 0.9618 |
| method3 | method3b | 19 | 1.063 |
| method3 | method3b | 20 | 1.0099 |
| method3 | method4 | 6 | 0.9102 |
| method3 | method4 | 7 | 1.1703 |
| method3 | method4 | 8 | 1.024 |
| method3 | method4 | 9 | 0.9102 |
| method3 | method4 | 10 | 0.8656 |
| method3 | method4 | 11 | 0.993 |
| method3 | method4 | 12 | 0.9618 |
| method3 | method4 | 13 | 1.0304 |
| method3 | method4 | 14 | 1.0305 |
| method3 | method4 | 15 | 0.9618 |

## Per-pair mean Jaccard (where comparable)

| method1 | method2 | mean Jaccard | N samples |
|---|---|---|---|
| method1 | method2 | 0.213 | 15 |
| method1 | method2r | 0.265 | 15 |
| method1 | method3 | 0.227 | 15 |
| method1 | method3b | 0.230 | 15 |
| method1 | method4 | 0.227 | 15 |
| method2 | method2r | 0.472 | 15 |
| method2 | method3 | 0.207 | 15 |
| method2 | method3b | 0.205 | 15 |
| method2 | method4 | 0.207 | 15 |
| method2r | method3 | 0.216 | 15 |
| method2r | method3b | 0.209 | 15 |
| method2r | method4 | 0.216 | 15 |
| method3 | method3b | 0.946 | 15 |
| method3 | method4 | 1.000 | 15 |
| method3b | method4 | 0.946 | 15 |