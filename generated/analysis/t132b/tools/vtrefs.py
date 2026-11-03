# which vtables are referenced (TOC load or lis/addi) inside function(s) subtree depth N: python vtrefs.py depth FN
import sys,os,collections
sys.path.insert(0,os.path.dirname(__file__))
from common import *
from graph import S,callees
from rtti import V,rtti
import bisect
VT={int(k,16) for k in V}
def endof(a):
    i=bisect.bisect_right(S,a); return S[i] if i<len(S) else a+0x400
def refs(a):
    r=[];hi={}
    for x_a in range(a,endof(a),4):
        x=w(x_a); op=x>>26; rt=(x>>21)&31; ra=(x>>16)&31; si=x&0xffff; si-=0x10000 if si&0x8000 else 0
        v=None
        if op==32 and ra==2:
            try: v=w(tocof(x_a)+si)
            except Exception: pass
        if op==15 and ra==0: hi[rt]=si<<16
        if op==14 and ra in hi: v=(hi[ra]+si)&0xffffffff
        if v is not None:
            for c in (v,v+8):
                if c in VT: r.append((x_a,c,rtti(c)))
    return r
if __name__=='__main__':
    dp=int(sys.argv[1]); a0=int(sys.argv[2],16)
    q=collections.deque([(a0,0)]); seen={a0}
    while q:
        f,d=q.popleft()
        for x_a,c,n in refs(f): print('%#x (fn %#x d%d) vt %#x %s'%(x_a,f,d,c,n))
        if d<dp:
            for s,t in callees.get(f,[]):
                if t not in seen and 0x10200<=t<0xcbdd68: seen.add(t); q.append((t,d+1))
