import sys
f=sys.argv[1]; k=int(sys.argv[2])
R=[]
for l in open(f):
    if l[0] in '#TH': continue
    p=l.split()
    try: R.append((int(p[0]),int(p[1]),p[2],p[3],float(p[4]),float(p[5])))
    except: pass
fl=sorted(r[4] for r in R if r[0]==9)
a,b=fl[k],fl[k+1]
print('frame',(b-a)/1e3,'ms')
rows=[r for r in R if r[5]>=a and r[4]<b and r[0] in (1,2,26,39,38) and (r[0]!=1 and r[0]!=2 or r[1]==1 or r[1]==12) and (r[0] in(26,39,38) or r[5]-r[4]>=100)]
for r in sorted(rows,key=lambda r:r[4]):
    nm={1:'sc',2:'usleep',26:"job",39:'hktask',38:'hksubmit',7:'rsxdrain'}[r[0]]
    print('%8.3f-%8.3f %-8s who=%-6s a=%s b=%s'%((r[4]-a)/1e3,(r[5]-a)/1e3,nm,r[1],r[2],r[3]))
