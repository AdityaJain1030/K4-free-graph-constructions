# Family: hermitian_pencil
# Catalog: mv_hermitian
# Parent: gen_007_mv_hermitian (conditional expectations bipartition: greedy IS minimization per pencil)
# Hypothesis: CE bipartition achieves theoretical α≈5 at N=63 giving c≈0.5, beating target
# Why non-VT: greedy per-pencil bipartition creates non-uniform orbit structure; no global Aut

def construct(N):
    q = None
    for qq in [2, 3, 5]:
        if qq*qq*(qq*qq - qq + 1) == N: q = qq; break
    if q is None: return []
    p = q; nr = p - 1

    def fmul(x, y):
        a,b=x; c,d=y; return ((a*c+b*d*nr)%p,(a*d+b*c)%p)
    def fpow(x,n):
        r=(1,0)
        while n:
            if n&1: r=fmul(r,x)
            x=fmul(x,x); n>>=1
        return r
    def finv(x): return fpow(x,p*p-2)
    def canonical(pt):
        for c in pt:
            if c!=(0,0): inv=finv(c); return tuple(fmul(inv,cc) for cc in pt)
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
    if len(unital) != q**3+1: return []

    def cross(p1,p2):
        x1,y1,z1=p1; x2,y2,z2=p2
        def sub(a,b): return ((a[0]-b[0])%p,(a[1]-b[1])%p)
        return canonical((sub(fmul(y1,z2),fmul(z1,y2)),sub(fmul(z1,x2),fmul(x1,z2)),sub(fmul(x1,y2),fmul(y1,x2))))
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
    if len(secant_list)!=N: return []

    pencil={}
    for s_idx,ln in enumerate(secant_list):
        for u_idx in secants[ln]:
            pencil.setdefault(u_idx,[]).append(s_idx)

    def greedy_IS_size(adj, N):
        deg=[len(adj[i]) for i in range(N)]
        order=sorted(range(N),key=lambda x: deg[x])
        IS=set(); blocked=set()
        for v in order:
            if v not in blocked: IS.add(v); blocked|=adj[v]
        return len(IS)

    adj = [set() for _ in range(N)]

    for u_idx in sorted(pencil.keys()):
        pen = pencil[u_idx]
        A, B = [], []
        for s_idx in pen:
            # "In A" means s_idx connects to all B members
            # "In B" means s_idx connects to all A members
            # Try putting s_idx in A: add edges s_idx-b for each b in B
            for b in B: adj[s_idx].add(b); adj[b].add(s_idx)
            size_if_A = greedy_IS_size(adj, N)
            for b in B: adj[s_idx].discard(b); adj[b].discard(s_idx)

            # Try putting s_idx in B: add edges s_idx-a for each a in A
            for a in A: adj[s_idx].add(a); adj[a].add(s_idx)
            size_if_B = greedy_IS_size(adj, N)
            for a in A: adj[s_idx].discard(a); adj[a].discard(s_idx)

            if len(A) == 0 or size_if_A <= size_if_B:
                # Put in A (commit edges to B)
                for b in B: adj[s_idx].add(b); adj[b].add(s_idx)
                A.append(s_idx)
            else:
                # Put in B (commit edges to A)
                for a in A: adj[s_idx].add(a); adj[a].add(s_idx)
                B.append(s_idx)

    return [(u,v) for u in range(N) for v in adj[u] if v > u]
