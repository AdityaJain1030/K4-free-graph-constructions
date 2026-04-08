import itertools
import argparse
import random
import math

# ------------------------------
# Graph building and K4 detection
# ------------------------------

def build_neighbors(n, jumps):
    """Return neighbors as bitmasks for a circulant graph"""
    nbr = [0] * n
    for i in range(n):
        for j in jumps:
            u = (i + j) % n
            v = (i - j) % n
            nbr[i] |= (1 << u)
            nbr[i] |= (1 << v)
    return nbr


def find_k4s(nbr, n):
    """Exact K4 detection using highly optimized bitsets"""
    for a in range(n):
        for b in range(a + 1, n):
            if not (nbr[a] & (1 << b)):
                continue
            
            # Get common neighbors of a and b
            common_ab = nbr[a] & nbr[b]
            
            # We only want c > b, so mask out all bits <= b
            candidates_c = common_ab & ~((1 << (b + 1)) - 1)
            
            # Iterate strictly over valid c vertices
            while candidates_c:
                c = (candidates_c & -candidates_c).bit_length() - 1
                candidates_c &= ~(1 << c) # clear the bit for the next iteration
                
                # Check for a 4th vertex connected to a, b, and c
                common_abc = common_ab & nbr[c] & ~((1 << a) | (1 << b) | (1 << c))
                if common_abc:
                    return True
    return False

# ------------------------------
# Independence number
# ------------------------------

def compute_alpha_exact(nbr, n):
    """Exact MIS via branch and bound"""
    best = [0]

    def branch(candidates, size):
        if candidates == 0:
            best[0] = max(best[0], size)
            return

        # Prune
        if size + candidates.bit_count() <= best[0]:
            return

        # Choose a vertex (lowest index)
        v = (candidates & -candidates).bit_length() - 1

        # Include v
        branch(candidates & ~nbr[v] & ~(1 << v), size + 1)

        # Exclude v
        branch(candidates & ~(1 << v), size)

    branch((1 << n) - 1, 0)
    return best[0]


def compute_alpha_approx(nbr, n, restarts=500):
    """Random greedy MIS approximation"""
    best = 0
    vertices = list(range(n))

    for _ in range(restarts):
        random.shuffle(vertices)
        available = (1 << n) - 1
        size = 0

        for v in vertices:
            if available & (1 << v):
                size += 1
                available &= ~nbr[v] & ~(1 << v)

        best = max(best, size)

    return best


# ------------------------------
# Utility functions
# ------------------------------

def compute_f(nbr, n, log_base=2):
    """Compute f(d) = n * log(d) / d"""
    d = nbr[0].bit_count()

    if d <= 1:
        return 0.0, d

    if log_base == 2:
        logd = math.log2(d)
    else:
        logd = math.log(d)

    return n * logd / d, d


def test_circulant(n, jumps, exact_threshold):
    nbr = build_neighbors(n, jumps)

    if find_k4s(nbr, n):
        return None

    f_val, d = compute_f(nbr, n)
    if f_val == 0:
        return None

    # Always compute exact if small OR if approximation might mislead
    if n <= exact_threshold:
        alpha = compute_alpha_exact(nbr, n)
    else:
        approx = compute_alpha_approx(nbr, n)

        # Safety: recompute exact if result is "interesting"
        if approx <= 0:
            return None

        # optimistic score
        approx_score = f_val / approx

        if approx_score > 0.9:  # near boundary → verify
            alpha = compute_alpha_exact(nbr, n)
        else:
            alpha = approx

    if alpha == 0:
        return None

    score = f_val / alpha
    return score, d, alpha, jumps


# ------------------------------
# Main search
# ------------------------------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--n_min", type=int, default=8)
    parser.add_argument("--n_max", type=int, default=50)
    parser.add_argument("--max_jump_size", type=int, default=4)
    parser.add_argument("--exact_threshold", type=int, default=25)
    parser.add_argument("--top_k", type=int, default=5)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()

    random.seed(args.seed)

    best_c_by_n = {}

    for n in range(args.n_min, args.n_max + 1):
        print(f"\n{'='*50}\nN = {n}")

        # ❗ FIX: avoid duplicate jump n/2
        possible_jumps = list(range(1, (n + 1) // 2))

        results = []

        for num_jumps in range(1, args.max_jump_size + 1):
            combos = list(itertools.combinations(possible_jumps, num_jumps))

            # Optional cap for performance (kept, but now explicit)
            if len(combos) > 5000:
                random.shuffle(combos)
                combos = combos[:5000]

            for jumps in combos:
                result = test_circulant(n, jumps, args.exact_threshold)
                if result:
                    results.append(result)

        if not results:
            print("  No valid graphs found")
            continue

        results.sort(key=lambda x: x[0], reverse=True)

        best_score, best_d, best_alpha, best_jumps = results[0]
        best_c_by_n[n] = best_score

        print(f"  Found {len(results)} valid graphs")
        print(f"  Top {min(args.top_k, len(results))} results:")

        for score, d, alpha, jumps in results[:args.top_k]:
            marker = " *** COUNTEREXAMPLE ***" if score > 1.0 else ""
            print(f"    jumps={jumps}  d={d}  alpha={alpha}  score={score:.6f}{marker}")

    print(f"\n{'='*50}\nBest c by n:")
    for n in sorted(best_c_by_n):
        print(f"  n={n}: c >= {best_c_by_n[n]:.6f}")

    if best_c_by_n:
        print(f"\nGlobal max c ≈ {max(best_c_by_n.values()):.6f}")


if __name__ == "__main__":
    main()
