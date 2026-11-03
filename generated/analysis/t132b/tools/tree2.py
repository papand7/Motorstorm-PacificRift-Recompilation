# compact recursive callee tree: python tree2.py depth FN [FN...]
import sys,os
sys.path.insert(0,os.path.dirname(__file__))
from cg import calls
from up import nm
from graph import S,f2
import bisect
SKIP={0x434d00,0x73b660,0x7410e0,0x73dad0,0x785df0,0x785c68,0x1b8648,0x7449b8,0x751af8}
def endof(a):
    i=bisect.bisect_right(S,a); return S[i] if i<len(S) else a+0x400
seen=set()
def tree(a,depth,ind,out):
    if a in seen: return
    seen.add(a)
    for l in calls(a,endof(a)):
        if ': bl ' in l:
            t=int(l.split()[2],16)
            if t in SKIP: continue
            rec = depth>0 and 'IMPORT' not in l and t not in seen
            out.append('%s%s -> %s%s'%('  '*ind,l.split(':')[0],nm(t) if 'IMPORT' not in l else l.split(None,3)[3],'' if rec or 'IMPORT' in l else ' *'))
            if rec: tree(t,depth-1,ind+1,out)
        else:
            out.append('  '*ind+l.strip())
if __name__=='__main__':
    dp=int(sys.argv[1])
    for x in sys.argv[2:]:
        a=int(x,16); o=['== '+nm(a)]; tree(a,dp,1,o); print('\n'.join(o))
