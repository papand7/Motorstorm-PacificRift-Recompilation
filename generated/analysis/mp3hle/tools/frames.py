import sys, struct, glob; sys.path.insert(0,'tools')
from cap import Job
BR=[0,32,40,48,56,64,80,96,112,128,160,192,224,256,320,0]; SR=[44100,48000,32000,0]
def hdr(d,i):
    if i+4>len(d): return None
    h=struct.unpack_from('>I',d,i)[0]
    if (h>>21)&0x7FF!=0x7FF or (h>>19)&3!=3 or (h>>17)&3!=1: return None
    bi=(h>>12)&15; si=(h>>10)&3; pad=(h>>9)&1
    if bi in (0,15) or si==3: return None
    return 144*BR[bi]*1000//SR[si]+pad
def scan(d,rd):
    for i in range(rd,len(d)-4):
        n=hdr(d,i)
        if n and hdr(d,i+n): return i,n
    return None,None
if __name__=='__main__':
    fs=sorted(glob.glob(sys.argv[1]+'/job_*.bin'))
    for f in fs[int(sys.argv[2]):int(sys.argv[3])]:
        j=Job(f); S=j.lin[0x21C00:0x21C60]
        w=[struct.unpack_from('>I',S,i)[0] for i in range(0,0x60,4)]
        puts=[e for e in j.ents if (e['cmd']&0xFF)==0x20 and e['phase']!=0xFFFFFFFF and e['phase']>=0x4000]
        cons=struct.unpack_from('>f',puts[1]['data'],4)[0]
        d=j.lin[0x1FC00:0x21C00]; rd=w[10]
        i,n=scan(d,rd)
        print(f[-9:-4],'rd %4X av %4X S34 %X cons %6.0f  first hdr %s len %s  -> end-rd %s'%(rd,w[11],w[13],cons,hex(i) if i is not None else None,n,(i+n-rd) if i is not None else None), d[rd:rd+4].hex())
