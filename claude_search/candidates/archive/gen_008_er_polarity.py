# Family: polarity
# Catalog: er_polarity
# Parent: none
# Hypothesis: ER(q) at q=7 (N=57) and q=11 (N=133) gives true non-VT with d_max=q+1
# Why non-VT: two orbits — absolute points (degree q) vs non-absolute (degree q+1)

def _is_prime_power(n):
    if n < 2:
        return None
    for p in range(2, n+1):
        if n % p == 0:
            # check if n = p^k
            k, m = 0, n
            while m % p == 0:
                m //= p
                k += 1
            if m == 1:
                return p, k
            break
    return None


def _gf_elements(q):
    """Return list of elements of GF(q) for prime q."""
    return list(range(q))


def construct(N):
    """ER(q) polarity graph: vertices = points of PG(2,q), edge iff p·p'=0.
    Works when N = q^2+q+1 for prime q.
    """
    # Find q
    q = None
    for qq in range(2, 200):
        if qq*qq + qq + 1 == N:
            # Check prime
            if all(qq % d != 0 for d in range(2, qq)):
                q = qq
            break
    if q is None:
        return []

    p = q  # q is prime

    # Points of PG(2,q): triples (x,y,z) in F_q^3\{0}, canonical rep = first nonzero = 1
    points = []
    seen = set()
    for x in range(q):
        for y in range(q):
            for z in range(q):
                if (x, y, z) == (0, 0, 0):
                    continue
                # Canonical: divide by first nonzero
                if x != 0:
                    inv = pow(x, p-2, p)
                    rep = (1, (y * inv) % p, (z * inv) % p)
                elif y != 0:
                    inv = pow(y, p-2, p)
                    rep = (0, 1, (z * inv) % p)
                else:
                    rep = (0, 0, 1)
                if rep not in seen:
                    seen.add(rep)
                    points.append(rep)

    assert len(points) == N, f"Expected {N} points, got {len(points)}"

    pt_idx = {pt: i for i, pt in enumerate(points)}

    # Edge p~p' iff p·p' = 0 (standard dot product in F_q) and p != p'
    # Self-loops: p·p = 0 => absolute points, remove them
    edges = []
    for i in range(N):
        pi = points[i]
        for j in range(i+1, N):
            pj = points[j]
            dot = (pi[0]*pj[0] + pi[1]*pj[1] + pi[2]*pj[2]) % p
            if dot == 0:
                edges.append((i, j))

    return edges


if __name__ == "__main__":
    for q in [2, 3, 5, 7, 11]:
        N = q*q + q + 1
        e = construct(N)
        print(f"q={q}, N={N}: {len(e)} edges")
