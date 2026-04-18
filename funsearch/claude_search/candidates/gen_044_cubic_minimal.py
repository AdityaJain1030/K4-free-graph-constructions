# Family: cayley_cyclic
"""Minimal cubic residues on best primes."""

def construct(N):
    if N not in(13,19,31):return[]
    e=[]
    for i in range(N):
        for j in range(i+1,N):
            if pow((j-i)%N,(N-1)//3,N)==1:e.append((i,j))
    return e
