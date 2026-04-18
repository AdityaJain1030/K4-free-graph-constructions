# Family: cayley_cyclic
"""5th power residues mod 11, 41; quartic (4th) mod 13, 17."""

def construct(N):
    if N==11:exp=(N-1)//5
    elif N==13:exp=(N-1)//4
    elif N==17:exp=(N-1)//4
    elif N==41:exp=(N-1)//5
    else:return[]
    e=[]
    for i in range(N):
        for j in range(i+1,N):
            if pow((j-i)%N,exp,N)==1:e.append((i,j))
    return e
