import sys,bisect,collections,statistics as st
f=sys.argv[1]; first=int(sys.argv[2]) if len(sys.argv)>2 else 98
R=collections.defaultdict(list)
for l in open(f):
    if l[0] in '#TH': continue
    p=l.split()
    try: R[int(p[0])].append((int(p[1]),p[2],p[3],float(p[4]),float(p[5])))
    except: pass
fl=sorted(r[3] for r in R[9])
ok=[i for i in range(first,len(fl)-1) if fl[i+1]-fl[i]<50000]
print('race frames used',len(ok),'mean ms %.1f'%(st.mean(fl[i+1]-fl[i] for i in ok)/1e3))
work=[]   # (t0,t1,kind,image,who)
for r in R[39]: work.append((r[3],r[4],'hk',r[1],r[0]))
for r in R[26]:
    if r[1]=='e0a08abe': continue
    work.append((r[3],r[4],'job',r[1],r[0]))
work.sort()
starts=[w[0] for w in work]
waits=[]
for r in R[2]:
    if r[0]==1 and r[2]=='94cca8': waits.append((r[3],r[4],'cv'))
for r in R[1]:
    if r[0]==1 and r[1]=='82' and r[4]-r[3]>=60: waits.append((r[3],r[4],'ev'))
waits.sort()
# merge cv/ev waits closer than 150us
m=[]
for w in waits:
    if m and w[0]-m[-1][1]<150 and m[-1][2]==w[2]: m[-1]=(m[-1][0],max(m[-1][1],w[1]),w[2])
    else: m.append(w)
tot=collections.Counter(); n=collections.Counter(); last=collections.Counter(); lastms=collections.defaultdict(float)
par=[]
nfr=len(ok)
for i in ok:
    a,b=fl[i],fl[i+1]
    for w in m:
        if not(a<=w[0]<b): continue
        # work overlapping [w0-1500? .. w1]: items starting within the wait or up to 1 ms before it (batch start precedes wait by few us)
        ws=[x for x in work if x[0]>=w[0]-100 and x[0]<=w[1]]
        d=w[1]-w[0]; k=w[2]
        n[k]+=1; tot[k+'_wait']+=d
        if not ws: tot[k+'_nowork']+=d; continue
        s=min(x[0] for x in ws); e=max(x[1] for x in ws); e=min(e,w[1]) if e>w[1] else e
        pre=max(s-w[0],0); post=max(w[1]-e,0); ex=max(e-s,0)
        tot[k+'_pre']+=pre; tot[k+'_exec']+=ex; tot[k+'_post']+=post
        busy=sum(min(x[1],w[1])-x[0] for x in ws)
        par.append((k,busy/max(ex,1)))
        lastw=max(ws,key=lambda x:x[1]); last[(lastw[2],lastw[3])]+=1; lastms[(lastw[2],lastw[3])]+=d
print('per frame: waits(count, ms): ',{k:(round(n[k]/nfr,2)) for k in n})
for k in ('cv','ev'):
    print(k,'wait %.2f ms/fr | no work seen %.2f | submit-latency(pre) %.2f | exec window %.2f | completion latency(post) %.2f'%tuple(tot[k+s]/1e3/nfr for s in ('_wait','_nowork','_pre','_exec','_post')))
    ps=[p for kk,p in par if kk==k]
    if ps: print('   mean parallelism inside exec window %.2f (p50 %.2f)'%(st.mean(ps),st.median(ps)))
print('image finishing last in a wait (count, wait ms/frame):')
for k,v in sorted(lastms.items(),key=lambda x:-x[1])[:10]: print('  ',k,last[k],'%.2f'%(v/1e3/nfr))
