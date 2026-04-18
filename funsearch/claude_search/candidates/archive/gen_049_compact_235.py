def construct(N):
 e=set()
 for i in range(N):
  for f in[2,3,5]:e.add((min(i,(i+f)%N),max(i,(i+f)%N)))
 return list(e)
