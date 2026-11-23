"""Rebuild the LibMP3 input byte stream from captured jobs and relate cumulative consumption to frames."""
import sys, struct, glob; sys.path.insert(0,'tools')
from cap import Job
from frames import hdr
def load(d):
    jobs=[]
    for f in sorted(glob.glob(d+'/job_*.bin')):
        j=Job(f); S=j.lin[0x21C00:0x21C60]
        w=[struct.unpack_from('>I',S,i)[0] for i in range(0,0x60,4)]
        puts=[e for e in j.ents if (e['cmd']&0xFF)==0x20 and e['phase']!=0xFFFFFFFF and e['phase']>=0x4000]
        out=puts[1]['data'][:0x60]
        jobs.append(dict(f=f,w=w,inp=j.lin[0x1FC00:0x21C00],out=out,pcm=puts[0]['data'],cons=struct.unpack_from('>f',out,4)[0]))
    return jobs
if __name__=='__main__':
    jobs=load(sys.argv[1]); start=int(sys.argv[2]) if len(sys.argv)>2 else 1
    stream=bytearray(); cum=[]
    for j in jobs[start:]:
        rd,av=j['w'][10],j['w'][11]; c=int(j['cons'])
        stream+=j['inp'][rd:rd+c]; cum.append(len(stream))
    open(sys.argv[1]+'_stream.mp3','wb').write(stream)
    # frame chain
    H=[]; i=0
    while i<len(stream)-4:
        n=hdr(stream,i)
        if n and (i+n>=len(stream)-4 or hdr(stream,i+n)): H.append((i,n)); i+=n
        else: i+=1
    def mdb(i):
        h=struct.unpack_from('>I',stream,i)[0]; o=i+4+(0 if (h>>16)&1 else 2)
        return (stream[o]<<1)|(stream[o+1]>>7)
    print('stream',len(stream),'frames',len(H),'first',H[:3])
    for k in range(min(40,len(cum))):
        c=cum[k]
        # nearest header after c
        nxt=[h for h in H if h[0]>=c][:1]
        print(k+start, 'cum %6d'%c, 'next hdr', nxt[0][0] if nxt else None, 'gap', (nxt[0][0]-c) if nxt else None, 'mdb', mdb(nxt[0][0]) if nxt else None)
