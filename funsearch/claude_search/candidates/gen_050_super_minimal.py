# Family: crossover
"""Minimal QR+CR attempt: N∈{5,17,19}."""

def construct(N):
    if N==5:e=[(i,j)for i in range(N)for j in range(i+1,N)if pow((j-i)%N,2,N)==1]
    elif N==17:e=[(i,j)for i in range(N)for j in range(i+1,N)if pow((j-i)%N,8,N)==1]
    elif N==19:e=[(i,j)for i in range(N)for j in range(i+1,N)if pow((j-i)%N,6,N)==1]
    else:return[]
    return e
