# Family: polarity
# Catalog: er_polarity
# Parent: gen_008_er_polarity (bipartite-augmented ER: add bipartite graph between the two ER orbits)
# Hypothesis: adding K(absolute, non-absolute) bipartite edges increases d_max faster than α at N=57
# Why non-VT: ER two-orbit structure preserved; extra edges don't equalize orbits

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

    # absolute points: p·p = 0
    absolute = [i for i,pt in enumerate(pts) if sum(c*c for c in pt)%p==0]
    non_abs = [i for i in range(N) if i not in set(absolute)]

    adj=[set() for _ in range(N)]
    # ER base edges
    for i in range(N):
        for j in range(i+1,N):
            if sum(pts[i][k]*pts[j][k] for k in range(3))%p==0:
                adj[i].add(j); adj[j].add(i)

    def has_k4(u,v):
        common=list(adj[u]&adj[v])
        for a in range(len(common)):
            for b in range(a+1,len(common)):
                if common[b] in adj[common[a]]: return True
        return False

    # Add cross-orbit edges (absolute-to-non_absolute) that are not already present and K4-free
    import random
    rng=random.Random(N*97+41)
    cross=[(a,b) for a in absolute for b in non_abs if b not in adj[a]]
    rng.shuffle(cross)
    for u,v in cross[:len(cross)//4]:  # add 25% of possible cross edges
        if not has_k4(u,v): adj[u].add(v); adj[v].add(u)

    return [(u,v) for u in range(N) for v in adj[u] if v>u]
