def construct(N):
 return list({(min(i,j:=(i+f)%N),max(i,j))for i in range(N)for f in[2,3,5]})
