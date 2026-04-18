def construct(N):
 return list({(min(i,(i+f)%N),max(i,(i+f)%N))for i in range(N)for f in[1,5,6]})
