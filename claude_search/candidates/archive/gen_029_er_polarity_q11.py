# Family: polarity
# Catalog: er_polarity
# Parent: gen_008_er_polarity (q=11, N=133, only evaluated in Stage 2 if Stage 1 has best_c < 1.0)
# Hypothesis: ER(11) at N=133 has c = α*d_max/(N*ln(d_max)) which may be < 1.0 at this larger N
# Why non-VT: two-orbit structure (absolute vs non-absolute) at q=11, same as all ER(q)

def construct(N):
    q=None
    for qq in range(2,200):
        if qq*qq+qq+1==N and all(qq%d!=0 for d in range(2,qq)): q=qq; break
    if not q: return []
    p=q
    seen={}; pts=[]
    for x in range(q):
        for y in range(q):
            for z in range(q):
                if (x,y,z)==(0,0,0): continue
                if x!=0: iv=pow(x,p-2,p); rep=(1,(y*iv)%p,(z*iv)%p)
                elif y!=0: iv=pow(y,p-2,p); rep=(0,1,(z*iv)%p)
                else: rep=(0,0,1)
                if rep not in seen: seen[rep]=len(pts); pts.append(rep)
    edges=[]
    for i in range(N):
        for j in range(i+1,N):
            if sum(pts[i][k]*pts[j][k] for k in range(3))%p==0:
                edges.append((i,j))
    return edges
