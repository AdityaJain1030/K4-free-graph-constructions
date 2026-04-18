def construct(N):
 return[sorted([i,(i+f)%N])for i in range(N)for f in[2,3,5]]
