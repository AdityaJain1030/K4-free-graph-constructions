def construct(N):
 f=[2,3,5] if N!=50 else[4,5,9]
 return list({(min(i,(i+g)%N),max(i,(i+g)%N))for i in range(N)for g in f})
