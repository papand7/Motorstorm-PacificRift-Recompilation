import json,os,sys
sys.path.insert(0,os.path.dirname(__file__))
from common import *
from cg import cstr
V=json.load(open(os.path.join(os.path.dirname(__file__),'..','vtables.json')))
def rtti(vt):
    try:
        ti=w(vt-4)
        if not ti: return None
        nm=w(ti+4); return cstr(nm)
    except Exception: return None
if __name__=='__main__':
    out={k:(rtti(int(k,16)),len(v)) for k,v in V.items()}
    json.dump(out,open(os.path.join(os.path.dirname(__file__),'..','vtable_rtti.json'),'w'),indent=0)
    for k,(n,l) in sorted(out.items(),key=lambda kv:-kv[1][1])[:40]: print(k,l,n)
