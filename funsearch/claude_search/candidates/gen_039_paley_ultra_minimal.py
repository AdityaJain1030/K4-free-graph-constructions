# Family: cayley_cyclic
"""Ultra-minimal Paley. Parent: gen_037.

Baseline: P(17) — the Cayley graph on Z/17Z with connection set =
quadratic residues mod 17. 8-regular, K4-free, α=3, c ≈ 0.6789.
This is the canonical baseline the whole search is trying to beat.
"""

def construct(N):
    if N not in(5,13,17):return[]
    e=[]
    for i in range(N):
        for j in range(i+1,N):
            if pow((j-i)%N,(N-1)//2,N)==1:e.append((i,j))
    return e
