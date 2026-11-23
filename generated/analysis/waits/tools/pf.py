import sys,bisect,collections
f=sys.argv[1]
R=collections.defaultdict(list)
for l in open(f):
    if l[0] in '#TH': continue
    p=l.split()
    try: R[int(p[0])].append((int(p[1]),p[2],p[3],float(p[4]),float(p[5])))
    except: pass
fl=sorted(r[3] for r in R[9])
def fi(t):
    i=bisect.bisect_right(fl,t)-1
    return i if 0<=i<len(fl)-1 else None
rows=collections.defaultdict(lambda:collections.Counter())
for r in R[1]+R[2]:
    if r[0]==1 and r[4]-r[3]>=100:
        i=fi(r[3]); 
        if i is not None: rows[i]['blk']+=r[4]-r[3]
for r in R[39]:
    i=fi(r[3])
    if i is not None: rows[i]['hk']+=r[4]-r[3]; rows[i]['hkn']+=1
for r in R[26]:
    if r[1]=='e0a08abe': continue
    i=fi(r[3])
    if i is not None: rows[i]['job']+=r[4]-r[3]; rows[i]['jobn']+=1
print('i frame_ms blocked_ms hk_ms(n) job_ms(n)')
for i in range(len(fl)-1):
    r=rows[i]; ft=(fl[i+1]-fl[i])/1e3
    print(i,'%.1f'%ft,'%.1f'%(r['blk']/1e3),'%.1f(%d)'%(r['hk']/1e3,r['hkn']),'%.1f(%d)'%(r['job']/1e3,r['jobn']))
