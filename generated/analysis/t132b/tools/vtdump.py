# dump vtable slots: python vtdump.py VT [maxslot_hex]
import sys,os,json
sys.path.insert(0,os.path.dirname(__file__))
from cg import *
from rtti import rtti,V
def strs(a):
    b=fend(a,0x3000); r=[]
    for l in calls(a,b):
        if 'str ' in l: r.append(l.split('str ',1)[1])
    return r
def slots(vt):
    return V['%#x'%vt]
if __name__=='__main__':
    vt=int(sys.argv[1],16); mx=int(sys.argv[2],16) if len(sys.argv)>2 else 0x1000
    print('vtable %#x %s'%(vt,rtti(vt)))
    for i,f in enumerate(slots(vt)):
        if i*4>mx: break
        f=int(f,16); n=name(f)[1]; s=strs(f)[:3]
        print('  +%#05x %#x %s %s'%(i*4,f,n,s if s else ''))
