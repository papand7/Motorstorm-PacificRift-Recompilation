# reverse call tree: python up.py TARGET [depth]
import sys,os,json,collections
sys.path.insert(0,os.path.dirname(__file__))
from graph import *
from names import name
R=json.load(open(os.path.join(os.path.dirname(__file__),'..','vtable_rtti.json')))
V=json.load(open(os.path.join(os.path.dirname(__file__),'..','vtables.json')))
VIN=collections.defaultdict(list)
for k,fl in V.items():
    for i,f in enumerate(fl): VIN[int(f,16)].append('%s(%s)+%#x'%(R[k][0] or '?',k,i*4))
def nm(f):
    n=name(f)[1]; v=VIN.get(f)
    return ('%#x %s'%(f,n))+(' [VT '+'; '.join(v[:4])+']' if v else '')
def up(t,depth,ind,seen,out):
    for a,f in callers.get(t,[]):
        out.append('%s<- %#x in %s'%('  '*ind,a,nm(f)))
        if f not in seen and depth>1:
            seen.add(f); up(f,depth-1,ind+1,seen,out)
if __name__=='__main__':
    t=int(sys.argv[1],16); dp=int(sys.argv[2]) if len(sys.argv)>2 else 6
    o=[nm(t)]; up(t,dp,1,set(),o); print('\n'.join(o))
