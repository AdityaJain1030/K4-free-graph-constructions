def construct(N: int) -> list[tuple[int, int]]:
    """Cayley graph on dihedral group D_{n/2}."""
    if N < 4:
        return []

    n = N // 2
    if 2 * n != N:
        return []

    edges = set()

    # D_n: vertices 0..n-1 (rotations r^i) and n..2n-1 (reflections r^i * s)
    # Connection set: {s, sr, sr^{-1}} to maintain regularity

    for i in range(n):
        # s: rotation -> reflection
        edges.add((i, n + i))

        # sr: rotation -> reflection of next
        edges.add((i, n + (i + 1) % n))

        # sr^{-1}: rotation -> reflection of prev
        edges.add((i, n + (i - 1) % n))

        # Within reflections: multiply by rotation
        for j in range(n):
            if i != j:
                # sr^j: reflection of i -> reflection of j
                edges.add((n + i, n + ((i + j) % n)))

    return list(edges)
