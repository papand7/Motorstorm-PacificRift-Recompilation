# disassemble developer resourceviewer.elf function by symbol name (private analysis helper)
import sys,struct,re,capstone,os
R=os.path.abspath(os.path.join(os.path.dirname(__file__),'..','..','..','..'))
P=os.path.join(R,'generated/analysis/c38/rv/')
d=open(P+'resourceviewer.elf','rb').read()
phoff=struct.unpack('>Q',d[0x20:0x28])[0]; phn=struct.unpack('>H',d[0x38:0x3a])[0]
segs=[]
for i in range(phn):
    o=phoff+i*56; t,f,off_,va,pa,fs,ms,al=struct.unpack('>IIQQQQQQ',d[o:o+56])
    if t==1 and fs: segs.append((va,off_,fs))
def off(a):
    for va,o,fs in segs:
        if va<=a<va+fs: return o+a-va
def w(a): o=off(a); return struct.unpack('>I',d[o:o+4])[0]
def f32(a): o=off(a); return struct.unpack('>f',d[o:o+4])[0]
def f64(a): o=off(a); return struct.unpack('>d',d[o:o+8])[0]
syms={};byaddr={};opd={}
for l in open(P+'symbols.txt',errors='replace'):
    p=l.split(None,3)
    if len(p)<4: continue
    a=int(p[0],16); n=p[3].strip()
    if n.startswith('.'): syms[n[1:]]=a; byaddr.setdefault(a,n[1:])
    elif p[2]=='10': opd[n]=a
import bisect
code=sorted(byaddr)
def name(a):
    i=bisect.bisect_right(code,a)-1
    return byaddr[code[i]]+('+%#x'%(a-code[i]) if a!=code[i] else '')
md=capstone.Cs(capstone.CS_ARCH_PPC,capstone.CS_MODE_64|capstone.CS_MODE_BIG_ENDIAN)
def dis(sym):
    a=syms[sym]; toc=w(opd[sym]+4) if sym in opd else None
    i=bisect.bisect_right(code,a); end=code[i] if i<len(code) else a+0x400
    print('== %s @ %#x toc=%s'%(sym,a,hex(toc) if toc else None))
    for x_a in range(a,end,4):
        x=w(x_a); ins=list(md.disasm(struct.pack('>I',x),x_a))
        s='%s %s'%(ins[0].mnemonic,ins[0].op_str) if ins else '.long'
        c=''; op=x>>26
        if op==18 and x&1:
            li=x&0x3fffffc; li-= 0x4000000 if li&0x2000000 else 0
            t=x_a+li if not x&2 else li; c=name(t)
        if toc and ((x>>16)&31)==2 and op in (48,50,32):
            simm=x&0xffff; simm-=0x10000 if simm&0x8000 else 0; ea=toc+simm
            try: c=('f=%r'%f32(ea)) if op==48 else ('d=%r'%f64(ea)) if op==50 else 'w=%#x'%w(ea)
            except Exception: pass
        print('%08x: %08x  %-40s %s'%(x_a,x,s,c))
if __name__=='__main__':
  for s in sys.argv[1:]:
    if s in syms: dis(s)
    else:
        [dis(k) for k in syms if re.search(s,k)]
