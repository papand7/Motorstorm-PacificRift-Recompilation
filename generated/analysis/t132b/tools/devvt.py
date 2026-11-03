# dump developer-build vtable by class mangled name fragment: python devvt.py N3evo8renderer15RenderSystemATGE
import sys,os
sys.path.insert(0,os.path.dirname(__file__))
from common import *
import devdis as D
from names import demangle
P=os.path.join(D.P,'symbols.txt')
vt={}
opdname={}
for l in open(P,errors='replace'):
    p=l.split(None,3)
    if len(p)<4: continue
    if p[3].startswith('_ZTV'): vt[p[3].strip()]=(int(p[0],16),int(p[1],16))
    if p[2]=='10': opdname[int(p[0],16)]=p[3].strip()
for frag in sys.argv[1:]:
    for k,(a,sz) in vt.items():
        if k=='_ZTV'+frag:
            print('==',k,hex(a),sz)
            for i in range(8,sz,4):
                o=D.w(a+i); n=opdname.get(o,'?')
                print('  +%#05x %s'%(i-8,demangle([n])[0][:110] if n!='?' else hex(o)))
