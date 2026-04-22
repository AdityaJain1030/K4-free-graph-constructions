# Family: incidence_bipartite
# Catalog: unital_point_line_incidence
# Parent: gen_009_unital_incidence (add K4-free intra-side edges to raise d_max and reduce α)
# Hypothesis: unital bipartite graph + K4-free intra-side edges makes α smaller relative to d_max
# Why non-VT: bipartite base has two orbits; intra-side edges break bipartiteness while preserving orbit distinction

import random

def construct(N):
    """Unital incidence graph (q=3, N=91) augmented with K4-free intra-side edges."""
    q = None
    for qq in [2, 3, 5]:
        if (qq**3+1) + qq**2*(qq**2-qq+1) == N: q=qq; break
    if not q: return []
    p=q; nr=p-1

    def fmul(x,y):
        a,b=x; c,d=y
        return ((a*c+b*d*nr)%p,(a*d+b*c)%p)
    def fpow(x,n):
        r=(1,0)
        while n:
            if n&1: r=fmul(r,x)
            x=fmul(x,x); n>>=1
        return r
    def finv(x): return fpow(x,p*p-2)
    def fconj(x): return (x[0],(-x[1])%p)

    def canonical(pt):
        for c in pt:
            if c!=(0,0):
                inv=finv(c); return tuple(fmul(inv,cc) for cc in pt)
        return None

    elems=[(a,b) for a in range(p) for b in range(p)]
    seen={}; pg_pts=[]
    for e0 in elems:
        for e1 in elems:
            for e2 in elems:
                if e0==(0,0) and e1==(0,0) and e2==(0,0): continue
                cp=canonical((e0,e1,e2))
                if cp not in seen:
                    seen[cp]=len(pg_pts); pg_pts.append(cp)

    def hval(pt): return tuple((sum(fpow(c,q+1)[k] for c in pt)%p) for k in range(2))
    unital=[i for i,pt in enumerate(pg_pts) if hval(pt)==(0,0)]
    n_pts=q**3+1
    if len(unital)!=n_pts: return []

    def cross(p1,p2):
        x1,y1,z1=p1; x2,y2,z2=p2
        def sub(a,b): return ((a[0]-b[0])%p,(a[1]-b[1])%p)
        nx=sub(fmul(y1,z2),fmul(z1,y2)); ny=sub(fmul(z1,x2),fmul(x1,z2)); nz=sub(fmul(x1,y2),fmul(y1,x2))
        return canonical((nx,ny,nz))
    def on_line(ln,pt):
        r=[0,0]
        for li,pi in zip(ln,pt):
            pr=fmul(li,pi); r[0]=(r[0]+pr[0])%p; r[1]=(r[1]+pr[1])%p
        return r==[0,0]

    secant_dict={}
    for i in range(len(unital)):
        for j in range(i+1,len(unital)):
            ln=cross(pg_pts[unital[i]],pg_pts[unital[j]])
            if ln and ln not in secant_dict: secant_dict[ln]=set()
    for u_idx in unital:
        for ln in secant_dict:
            if on_line(ln,pg_pts[u_idx]): secant_dict[ln].add(u_idx)
    secants={ln:s for ln,s in secant_dict.items() if len(s)==q+1}
    secant_list=list(secants.keys())
    n_sec=q**2*(q**2-q+1)
    if len(secant_list)!=n_sec: return []

    adj=[set() for _ in range(N)]
    for s_idx,ln in enumerate(secant_list):
        for u_local,u_global in enumerate(unital):
            if u_global in secants[ln]:
                adj[u_local].add(n_pts+s_idx); adj[n_pts+s_idx].add(u_local)

    def has_k4(u,v):
        common=list(adj[u]&adj[v])
        for a in range(len(common)):
            for b in range(a+1,len(common)):
                if common[b] in adj[common[a]]: return True
        return False

    rng=random.Random(N*37+19)
    # Add K4-free intra-point edges
    pts_list=list(range(n_pts)); rng.shuffle(pts_list)
    for i in range(0,len(pts_list)-1,2):
        u,v=pts_list[i],pts_list[i+1]
        if not has_k4(u,v): adj[u].add(v); adj[v].add(u)

    return [(u,v) for u in range(N) for v in adj[u] if v>u]
