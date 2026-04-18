# Family: crossover
"""Minimal QR+CR: N=17 (QR) + N=19 (CR)."""

def construct(N):
    if N not in(17,19):return[]
    e,x=[],(N-1)//8 if N==17 else(N-1)//6
    for i in range(N):
        for j in range(i+1,N):
            if pow((j-i)%N,x,N)==1:e.append((i,j))
    return e
