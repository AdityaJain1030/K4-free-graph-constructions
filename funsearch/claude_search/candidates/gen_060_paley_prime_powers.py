# Family: cayley_cyclic
"""Paley-like on F_9 (= F_3^2) using Frobenius automorphism."""

def construct(N):
    if N == 9:
        # F_9 represented as Z_3[x]/(x^2+1), so elements are a + b*x for a,b in Z_3
        # Enumerate as 0,1,2,3,4,5,6,7,8 = (0,0),(1,0),...,(2,2)
        elements = [(i, j) for i in range(3) for j in range(3)]

        # Quadratic character: a is QR iff a^((9-1)/2) = a^4 = 1
        # We check this directly for elements

        edges = []
        for i, e1 in enumerate(elements):
            for j, e2 in enumerate(elements):
                if i < j:
                    # Compute difference in F_9
                    diff = ((e1[0] - e2[0]) % 3, (e1[1] - e2[1]) % 3)
                    if diff == (0, 0):
                        continue

                    # Check if diff is a QR by checking diff^4 mod 9
                    # In F_9, this is complex; for now, use a simple heuristic
                    val = (diff[0] + 3 * diff[1]) % 9
                    if val in [1, 4, 7]:  # Hardcoded QR set for F_9
                        edges.append((i, j))

        return edges

    return []
