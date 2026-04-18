def construct(N):
    """Cayley graph on GF(25)=F_5[x]/(x^2+x+1) with cubic residues as connection set.
    For N=25 this is an 8-regular Cayley graph. Falls back to circulant {2,3,5} otherwise."""
    if N != 25:
        seen = set()
        edges = []
        for i in range(N):
            for s in [2, 3, 5]:
                for j in [(i + s) % N, (i - s) % N]:
                    key = (min(i, j), max(i, j))
                    if key not in seen and key[0] != key[1]:
                        seen.add(key); edges.append(key)
        return edges

    # GF(25): elements (a,b) with a,b in F_5, addition componentwise
    # Multiplication: (a,b)*(c,d) = (ac+4bd, ad+bc+4bd) mod 5  [using x^2=4x+4]
    def mul(u, v):
        a, b = u; c, d = v
        return ((a*c + 4*b*d) % 5, (a*d + b*c + 4*b*d) % 5)

    # Find generator of GF(25)* (order 24) by trying candidates
    def order(g):
        x = g; n = 1
        while x != (1, 0):
            x = mul(x, g); n += 1
            if n > 25: return n
        return n

    gen = None
    for a in range(5):
        for b in range(5):
            if (a, b) == (0, 0): continue
            if order((a, b)) == 24:
                gen = (a, b); break
        if gen: break

    # Compute cubic residues: gen^(3k) for k=0..7, plus additive inverses
    cr = set()
    x = (1, 0)
    for _ in range(8):
        cr.add(x)
        cr.add(((-x[0]) % 5, (-x[1]) % 5))  # additive inverse
        x = mul(mul(mul(x, gen), gen), gen)  # x *= gen^3

    # Map elements to integers: (a,b) -> 5a+b
    idx = {(a, b): 5*a+b for a in range(5) for b in range(5)}

    edges = []
    seen = set()
    elems = [(a, b) for a in range(5) for b in range(5)]
    for u in elems:
        for s in cr:
            v = ((u[0]+s[0])%5, (u[1]+s[1])%5)
            i, j = idx[u], idx[v]
            key = (min(i, j), max(i, j))
            if key not in seen and key[0] != key[1]:
                seen.add(key); edges.append(key)
    return edges
