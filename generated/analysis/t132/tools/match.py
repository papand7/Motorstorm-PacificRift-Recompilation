# find retail addresses of developer functions by masked instruction signature
import sys,re,struct
import devdis as D
import elf as E
def mask(x):
    op=x>>26
    if op in (18,16): return x&0xFC000003
    if ((x>>16)&31)==2 and op in (14,15,32,34,36,40,48,50,58,62,38,52,54): return x&0xFFFF0000
    return x
RET=bytes(E.d[E.off(0x10000):E.off(0x10000)+0xCC0000])
# build retail word array once
import array
rw=array.array('I',E.d[0:0xCB0000]); rw.byteswap()
rm=[mask(x) for x in rw]
def find(sym):
    a=D.syms[sym]; i=D.bisect.bisect_right(D.code,a); end=D.code[i]
    sig=[mask(D.w(x)) for x in range(a,end,4)]
    n=min(len(sig),24)
    hits=[]
    first=sig[0]
    for k in range(len(rm)-n):
        if rm[k]==first and rm[k:k+n]==sig[:n]:
            full=sum(1 for j in range(len(sig)) if k+j<len(rm) and rm[k+j]==sig[j])
            hits.append(('%#x'%(k*4+0x10000),'%d/%d'%(full,len(sig))))
    return hits
for s in sys.argv[1:]:
    for k in [k for k in D.syms if re.search(s,k)]:
        print(k, '%#x'%D.syms[k], find(k))
