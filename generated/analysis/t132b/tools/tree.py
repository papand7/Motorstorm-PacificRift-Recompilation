# recursive call tree (direct bl only, vslots listed), strings; python tree.py FN depth
import sys,os
sys.path.insert(0,os.path.dirname(__file__))
from cg import *
seen=set()
LIB=set()
def tree(a,depth,ind=0,out=None):
    b=fend(a,0x6000)
    hdr='%s%#x %s'%('  '*ind,a,name(a)[1])
    if a in seen:
        out.append(hdr+' (seen)'); return
    seen.add(a); out.append(hdr)
    for l in calls(a,b):
        if ': bl ' in l:
            t=int(l.split()[2],16)
            if 'IMPORT' in l or depth<=0 or t in (0x434d00,0x73b660,0x7410e0,0x73dad0,0x785df0,0x785c68,0x1b8648,0x7449b8):
                out.append('  '*(ind+1)+l.strip())
            else:
                out.append('  '*(ind+1)+'@'+l.split(':')[0]); tree(t,depth-1,ind+1,out)
        else: out.append('  '*(ind+1)+l.strip())
if __name__=='__main__':
    o=[]; tree(int(sys.argv[1],16),int(sys.argv[2]),0,o); print('\n'.join(o))
