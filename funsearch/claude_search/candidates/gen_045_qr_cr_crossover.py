# Family: crossover
"""QR at N=17 + CR at N=19. Hybrid minimal."""

def construct(N):
    if N not in(5,17,19):return[]
    e=[]
    for i in range(N):
        for j in range(i+1,N):
            diff=(j-i)%N
            if N==5:
                test=pow(diff,2,N)==1
            elif N==17:
                test=pow(diff,8,N)==1
            else:
                test=pow(diff,6,N)==1
            if test:e.append((i,j))
    return e
