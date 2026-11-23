import sys,collections,statistics as st
f=sys.argv[1]
R=collections.defaultdict(list)
for l in open(f):
    if l[0] in '#TH': continue
    p=l.split()
    if len(p)<6: continue
    try: R[int(p[0])].append((int(p[1]),p[2],p[3],float(p[4]),float(p[5])))
    except: pass
flips=sorted(r[3] for r in R[9]); print('frames',len(flips)-1)
def frame_of(t):
    import bisect
    i=bisect.bisect_right(flips,t)-1
    return i if 0<=i<len(flips)-1 else None
main=[(r[3],r[4],r[1] if False else r[1]) for r in R[1]+R[2] if r[0]==1]
# Havok tasks
T=collections.defaultdict(list)
sub=R[38]; run=R[34]; ex=R[39]
print('tasks',len(sub),len(run),len(ex))
# queue delay: kind34 b = dispatch->pickup us
qd=[int(r[2],16) for r in run]
print('task pickup delay us avg %.0f p50 %d p90 %d max %d'%(st.mean(qd),st.median(qd),sorted(qd)[int(.9*len(qd))],max(qd)))
exe=[r[4]-r[3] for r in ex]
print('task exec us avg %.0f p50 %.0f p90 %.0f'%(st.mean(exe),st.median(exe),sorted(exe)[int(.9*len(exe))]))
# by image
img=collections.defaultdict(list)
for r in ex: img[r[1]].append(r[4]-r[3])
for k,v in sorted(img.items(),key=lambda x:-sum(x[1]))[:8]: print(' img',k,'n',len(v),'avg us %.0f'%st.mean(v),'sum ms %.0f'%(sum(v)/1e3))
# per frame task stats
pf=collections.defaultdict(lambda:{'n':0,'q':0,'x':0,'first':1e30,'last':0})
for s in sub:
    i=frame_of(s[3])
    if i is None: continue
    pf[i]['n']+=1; pf[i]['first']=min(pf[i]['first'],s[3])
for r in run:
    i=frame_of(r[3])
    if i is None: continue
    pf[i]['q']+=int(r[2],16); pf[i]['x']+=r[4]-r[3]; pf[i]['last']=max(pf[i]['last'],r[4])
fr=len(flips)-1
print('per frame: tasks %.1f queue-delay sum %.2f ms exec sum %.2f ms'%(sum(v['n'] for v in pf.values())/fr,sum(v['q'] for v in pf.values())/1e3/fr,sum(v['x'] for v in pf.values())/1e3/fr))
# task span = first submit .. last end per frame
sp=[(v['last']-v['first'])/1e3 for v in pf.values() if v['n'] and v['last']>v['first']]
print('task window first-submit..last-end ms avg %.2f'%st.mean(sp))
# lanes: kind 25 by wid
wid=collections.defaultdict(float)
for r in R[25]:
    w=int(r[1],16)&0xff; wid[w]+=(r[4]-r[3])
print('PM residency ms/frame by wid',{k:round(v/1e3/fr,2) for k,v in sorted(wid.items())})
jb=collections.defaultdict(lambda:[0,0.0])
mod={}
for r in R[28]: mod[r[4]]=r[1]
for r in R[26]:
    k=r[1]; jb[k][0]+=1; jb[k][1]+=r[4]-r[3]
print('SPURS jobs/frame %.1f ms/frame %.2f'%(sum(v[0] for v in jb.values())/fr,sum(v[1] for v in jb.values())/1e3/fr))
for k,v in sorted(jb.items(),key=lambda x:-x[1][1])[:8]: print(' job',k,'n/fr %.1f'%(v[0]/fr),'avg us %.0f'%(v[1]/v[0]),'ms/fr %.2f'%(v[1]/1e3/fr))
# concurrency of lanes while main blocked
blk=[(a,b) for a,b,_ in main if b-a>=100]
tot=sum(b-a for a,b in blk)
ev=[]
for r in R[25]: ev+=[(r[3],1),(r[4],-1)]
for r in R[39]: ev+=[(r[3],100),(r[4],-100)]
ev.sort()
# sweep: time in blocked with N lanes, M tasks
import bisect
cnt=collections.Counter(); lanes=0;tasks=0;j=0
pts=ev
for a,b in blk:
    pass
# build step function
times=[e[0] for e in pts]; L=[];T2=[];l=t=0
for tm,d in pts:
    if abs(d)==1: l+=d
    else: t+=d//100
    L.append(l);T2.append(t)
for a,b in blk:
    cur=a;i=bisect.bisect_right(times,a)-1
    while cur<b:
        nxt=times[i+1] if i+1<len(times) else b
        nxt=min(nxt,b)
        ll=L[i] if i>=0 else 0; tt=T2[i] if i>=0 else 0
        cnt[(min(ll,6),min(tt,6))]+=nxt-cur; cur=nxt; i+=1
print('main blocked (>=100us) %.1f ms/frame; split by (lanes in PM, havok tasks running):'%(tot/1e3/fr))
for k,v in sorted(cnt.items(),key=lambda x:-x[1])[:12]: print('  lanes %d tasks %d: %.2f ms/frame'%(k[0],k[1],v/1e3/fr))
