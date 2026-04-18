"""Adaptive circulant: use {1,2} for most N, {1} for primes. Parent: gen_002."""

def is_prime(n):
    if n < 2: return False
    if n == 2: return True
    if n % 2 == 0: return False
    for i in range(3, int(n**0.5) + 1, 2):
        if n % i == 0:
            return False
    return True

def construct(N: int) -> list[tuple[int, int]]:
    # Use sparser connection set for primes
    if is_prime(N):
        offsets = [1]
    else:
        offsets = [1, 2]

    edges = []
    for i in range(N):
        for offset in offsets:
            j = (i + offset) % N
            if i < j:
                edges.append((i, j))
            else:
                edges.append((j, i))

    return list(set(edges))
