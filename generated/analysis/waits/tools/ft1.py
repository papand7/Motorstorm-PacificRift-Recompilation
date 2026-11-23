import sys,collections
f=sys.argv[1]
names={}
rows=[]
for l in open(f):
    if l.startswith('#'): print(l.strip()); continue
    p=l.split()
    if l.startswith('T '): names[int(p[1])]=' '.join(p[2:]); continue
    if len(p)<6: continue
    try: rows.append((int(p[0]),int(p[1]),p[2],p[3],float(p[4]),float(p[5])))
    except: pass
cnt=collections.Counter(r[0] for r in rows)
print(cnt)
t0=min(r[4] for r in rows); t1=max(r[5] for r in rows)
print((t1-t0)/1e6,'s')
for k in (9,10,8):
    print(k,cnt[k])
# main thread per kind
m=[r for r in rows if r[0] in(1,2) and r[1]==1]
agg=collections.defaultdict(lambda:[0,0.0])
for r in m:
    key=(r[0],r[2],r[3]); agg[key][0]+=1; agg[key][1]+=r[5]-r[4]
span=(t1-t0)/1e3
for k,v in sorted(agg.items(),key=lambda x:-x[1][1])[:20]:
    print(k,v[0],'%.1f ms/s'%(v[1]/1e3/(span/1e3)),'%.0f us avg'%(v[1]/v[0]))
