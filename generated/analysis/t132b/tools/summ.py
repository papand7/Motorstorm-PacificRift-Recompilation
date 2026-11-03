# subtree summary: strings, imports, dev names, vtable-member callees. python summ.py depth FN...
import sys,os,collections,bisect
sys.path.insert(0,os.path.dirname(__file__))
from cg import calls
from up import nm,VIN
from names import name
from graph import S,callees
SKIP={0x434d00,0x73b660,0x7410e0,0x73dad0,0x785df0,0x785c68,0x1b8648,0x7449b8}
def endof(a):
    i=bisect.bisect_right(S,a); return S[i] if i<len(S) else a+0x400
def summ(a,depth,maxn=400):
    q=collections.deque([(a,0)]); seen={a}; strs=[];imps=collections.Counter();names=[];n=0
    while q and n<maxn:
        f,d=q.popleft(); n+=1
        nn=name(f)[1]
        if nn and f!=a: names.append('%#x %s'%(f,nn[:90]))
        for l in calls(f,endof(f)):
            if 'str ' in l: strs.append(l.split('str ',1)[1])
            elif ': bl ' in l:
                t=int(l.split()[2],16)
                if 'IMPORT' in l: imps[l.split('IMPORT ')[1]]+=1
                elif t not in seen and t not in SKIP and d<depth:
                    seen.add(t); q.append((t,d+1))
    return n,strs,imps,names
if __name__=='__main__':
    dp=int(sys.argv[1])
    for x in sys.argv[2:]:
        a=int(x,16); n,s,i,nm_=summ(a,dp)
        print('== %s  nodes=%d'%(nm(a),n))
        if i: print('  IMPORTS',dict(i))
        if s: print('  STR',list(dict.fromkeys(s))[:40])
        for k in nm_[:25]: print('  N',k)
