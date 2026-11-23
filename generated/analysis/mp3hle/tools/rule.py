import sys, struct; sys.path.insert(0,'tools')
from recon import load
from frames import hdr
jobs=load(sys.argv[1])[1:]
stream=bytearray(); cum=[]; avs=[]
for j in jobs:
    rd,av=j['w'][10],j['w'][11]; c=int(j['cons']); stream+=j['inp'][rd:rd+c]; cum.append(len(stream)); avs.append(av)
H=[]; i=0
while i<len(stream)-4:
    n=hdr(stream,i)
    if n and (i+n>=len(stream)-4 or hdr(stream,i+n)): H.append(i); i+=n
    else: i+=1
H.append(len(stream))
# hypothesis: cum_k = H[k+a] + b  -> find a,b minimizing mismatches over non-limited jobs
best=None
for a in range(-2,4):
  for b in range(-1200,1200):
    m=0; tot=0
    for k,c in enumerate(cum):
        if k+a<0 or k+a>=len(H): continue
        if avs[k] <= (cum[k]-(cum[k-1] if k else 0)): continue  # input-limited job
        tot+=1; m+= (c != H[k+a]+b)
    if tot and (best is None or m<best[0]): best=(m,tot,a,b)
print('best (mismatch,total,a,b)',best)
m,tot,a,b=best
for k,c in enumerate(cum[:60]):
    lim = avs[k] <= (cum[k]-(cum[k-1] if k else 0))
    print(k, c, H[k+a]+b if 0<=k+a<len(H) else None, 'LIMIT' if lim else '', 'ok' if 0<=k+a<len(H) and c==H[k+a]+b else 'X')
print('--- diff model')
L=[H[i+1]-H[i] for i in range(len(H)-1)]
for s in range(-3,4):
    ok=tot=0
    for k in range(1,len(cum)):
        if avs[k] <= cum[k]-cum[k-1] or avs[k-1] <= cum[k-1]-cum[k-2]: continue
        if not (0<=k+s<len(L)): continue
        tot+=1; ok+= (cum[k]-cum[k-1]==L[k+s])
    print('shift',s,ok,'/',tot)
