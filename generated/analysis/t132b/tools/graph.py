# global direct call graph with improved function starts; pickled to ../graph.pkl
import sys,os,pickle,bisect,collections
sys.path.insert(0,os.path.dirname(__file__))
from common import *
from names import resolve
P=os.path.join(os.path.dirname(__file__),'..','graph.pkl')
def build():
    S=set(starts)
    sites=[]
    for a in range(0x10200,0xCBDD68,4):
        x=w(a)
        if x>>26==18 and (x&3)==1:
            t,imp=resolve(br(a,x)); sites.append((a,t))
            if 0x10200<=t<0xCBDD68: S.add(t)
    for o in range(0x107b8c8,0x1097bf0,8):
        f=w(o)
        if 0x10200<=f<0xCBDD68: S.add(f)
    S=sorted(S)
    def f2(a): return S[bisect.bisect_right(S,a)-1]
    callees=collections.defaultdict(list); callers=collections.defaultdict(list)
    for a,t in sites:
        callees[f2(a)].append((a,t)); callers[t].append((a,f2(a)))
    pickle.dump((S,dict(callees),dict(callers)),open(P,'wb'))
if not os.path.exists(P): build()
S,callees,callers=pickle.load(open(P,'rb'))
def f2(a): return S[bisect.bisect_right(S,a)-1]
