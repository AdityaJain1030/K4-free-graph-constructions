# Family: polarity
# Catalog: er_polarity
# Parent: gen_008_er_polarity (replace standard bilinear form with twisted non-degenerate form)
# Hypothesis: twisted form x0*y2 + x1*y1 + x2*y0 over PG(2,q) gives non-isomorphic non-VT graph
# Why non-VT: twisted polarity has different absolute-point orbit structure than standard polarity

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

    # Twisted bilinear form: <p, q> = p[0]*q[2] + p[1]*q[1] + p[2]*q[0]
    # This is symmetric and non-degenerate for any q
    edges=[]
    for i in range(N):
        for j in range(i+1,N):
            pi,pj=pts[i],pts[j]
            dot=(pi[0]*pj[2] + pi[1]*pj[1] + pi[2]*pj[0]) % p
            if dot==0:
                edges.append((i,j))
    return edges
