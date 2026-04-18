# Family: crossover
"""QR+CR crossover, compact form."""

def construct(N):
    if N==17:exp=(N-1)//2
    elif N==19:exp=(N-1)//3
    else:return[]
    e=[]
    for i in range(N):
        for j in range(i+1,N):
            if pow((j-i)%N,exp,N)==1:e.append((i,j))
    return e
