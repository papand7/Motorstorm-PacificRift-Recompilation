# disassemble VA range with annotations: python dis.py START END
import sys,json,capstone
from elf import *
S={int(k,16):(v[1] or v[0]+'?') for k,v in json.load(open(os.path.join(R,'generated/analysis/garage_menu/stubs.json'))).items()}
md=capstone.Cs(capstone.CS_ARCH_PPC,capstone.CS_MODE_64|capstone.CS_MODE_BIG_ENDIAN)
def tgt(t):
    if t in S: return S[t]
    if w(t)==0xf8410028 and w(t+12)>>26==18:
        f=br(t+12,w(t+12)); return 'xtoc->%#x'%f+(' '+S[f] if f in S else '')
    return ''
def dis(a,b):
    out=[]
    for i in (ii for aa in range(a,b,4) for ii in (list(md.disasm(d[off(aa):off(aa)+4],aa)) or [type('X',(),{'address':aa,'mnemonic':'.long','op_str':''})()])):
        x=w(i.address); c=''
        if x>>26==18:
            t=br(i.address,x); c=tgt(t)
            if t in starts_set: c+=' [fn]'
        op=x>>26; ra=(x>>16)&31
        simm=x&0xffff; simm=simm-0x10000 if simm&0x8000 else simm
        if ra==2 and op in (48,50,32,58):  # lfs lfd lwz ld
            ea=tocof(i.address)+simm
            try:
                if op==48: c='TOC[%d]=%#x f=%r'%(simm,w(ea),f32(ea))
                elif op==50: c='TOC[%d] d=%r'%(simm,f64(ea))
                elif op==32: c='TOC[%d]=%#x'%(simm,w(ea))
                else: c='TOC[%d]=%#x'%(simm,q(ea))
            except Exception as e: c='TOC[%d]'%simm
        if op==17: c='SYSCALL'
        out.append('%08x: %08x  %-8s %-30s %s'%(i.address,x,i.mnemonic,i.op_str,c))
    return out
starts_set=set(starts)
if __name__=='__main__':
    a=int(sys.argv[1],16); b=int(sys.argv[2],16)
    print('\n'.join(dis(a,b)))
