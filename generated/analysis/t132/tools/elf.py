# private helper: big-endian PPC64 ELF access for EBOOT.elf
import struct,json,bisect,os
R=os.path.join(os.path.dirname(__file__),'..','..','..','..')
R=os.path.abspath(R)
d=open(os.path.join(R,'generated/decrypted/EBOOT.elf'),'rb').read()
phoff=struct.unpack('>Q',d[0x20:0x28])[0]; phn=struct.unpack('>H',d[0x38:0x3a])[0]
segs=[]
for i in range(phn):
    o=phoff+i*56
    t,f,off,va,pa,fs,ms,al=struct.unpack('>IIQQQQQQ',d[o:o+56])
    if t==1: segs.append((va,off,fs,ms))
def off(a):
    for va,o,fs,ms in segs:
        if va<=a<va+fs: return o+a-va
    return None
def w(a):
    o=off(a); return None if o is None else struct.unpack('>I',d[o:o+4])[0]
def q(a):
    o=off(a); return struct.unpack('>Q',d[o:o+8])[0]
def f32(a): return struct.unpack('>f',d[off(a):off(a)+4])[0]
def f64(a): return struct.unpack('>d',d[off(a):off(a)+8])[0]
fs=json.load(open(os.path.join(R,'generated/analysis/EBOOT.functions.json')))
starts=sorted(int(f['start'],16) for f in fs)
tocs={int(f['start'],16):int(f['toc'],16) for f in fs}
def tocof(a): return tocs[fn(a)]
def fn(a): return starts[bisect.bisect_right(starts,a)-1]
def br(a,x):
    li=x&0x3fffffc
    if li&0x2000000: li-=0x4000000
    return a+li
TOC=0x109fbf0
TEXT_END=0xCC0000
def realstart(a):
    # nearest preceding function entry: word after blr / unconditional b / bctr, skipping nops; then must contain stdu soon
    b=a-4
    while b>0x10200:
        x=w(b)
        if x in (0x4e800020,0x4e800420) or (x>>26==18 and (x&3)==0):
            c=b+4
            while w(c)==0x60000000: c+=4
            if any((w(c+k)>>16) in (0xf821,) or (w(c+k)&0xffff07ff)==0x7c21016a for k in range(0,40,4)) and c<=a: return c
        b-=4
