# list calls in a retail function range with names, vtable slots, strings: python cg.py START [END]
import sys,os,re
sys.path.insert(0,os.path.dirname(__file__))
from names import *
def cstr(a):
    o=off(a)
    if o is None: return None
    s=d[o:o+80].split(b'\0')[0]
    if len(s)>=4 and all(32<=c<127 for c in s): return s.decode()
def calls(a,b,show_str=True):
    out=[];regs={}
    for x_a in range(a,b,4):
        x=w(x_a); op=x>>26; rt=(x>>21)&31; ra=(x>>16)&31; simm=x&0xffff; simm-=0x10000 if simm&0x8000 else 0
        if op==32 and ra!=1: regs[rt]=('lwz',ra,simm,x_a)
        if op==18 and (x&3)==1:
            t,n=name(br(x_a,x)); out.append('%08x: bl   %#x %s'%(x_a,t,n))
        elif x in (0x4e800421,0x4e800021):
            # find mtctr/mtlr source reg, then its load lwz rS,0(rF); rF loaded by lwz rF,OFF(rVT)
            src=None
            for y_a in range(x_a-4,x_a-60,-4):
                y=w(y_a)
                if (y&0xfc1fffff)==0x7c0903a6 or (y&0xfc1fffff)==0x7c0803a6: src=(y>>21)&31;break
            desc='?'
            if src is not None:
                for y_a in range(x_a-4,x_a-80,-4):
                    y=w(y_a)
                    if y>>26==32 and ((y>>21)&31)==src:
                        fr=(y>>16)&31; o1=y&0xffff
                        for z_a in range(y_a-4,y_a-80,-4):
                            z=w(z_a)
                            if z>>26==32 and ((z>>21)&31)==fr:
                                o2=z&0xffff; o2-=0x10000 if o2&0x8000 else 0
                                desc='vslot +%#x (fnptr via lwz r%d,%#x(r%d) @%x)'%(o2,fr,o2,(z>>16)&31,z_a); break
                        break
            out.append('%08x: %s %s'%(x_a,'bctrl' if x==0x4e800421 else 'blrl ',desc))
        elif show_str and ra==2 and op==32:
            try:
                v=w(tocof(x_a)+simm); s=cstr(v) if v else None
                if s: out.append('%08x:   str %r'%(x_a,s))
            except Exception: pass
        elif op==17: out.append('%08x: SYSCALL'%x_a)
    return out
if __name__=='__main__':
    a=int(sys.argv[1],16)
    if len(sys.argv)>2: b=int(sys.argv[2],16)
    else:
        b=fend(a)
    print('== %#x..%#x %s'%(a,b,name(a)[1]))
    print('\n'.join(calls(a,b)))
