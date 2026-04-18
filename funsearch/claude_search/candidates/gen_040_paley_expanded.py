"""Paley on larger set of primes. Parent: gen_039."""

def construct(N):
    # Primes ≡ 1 mod 4: try all in a larger range
    if N not in(5,13,17,29,37,41,53):return[]
    e=[]
    for i in range(N):
        for j in range(i+1,N):
            if pow((j-i)%N,(N-1)//2,N)==1:e.append((i,j))
    return e
