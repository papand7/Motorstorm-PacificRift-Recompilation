"""List the MFC commands and channel ops of a task recording (spu_taskrec.h v1)."""
import struct, sys
CMD = {0x40:'PUT',0x20:'PUT',0x24:'PUTL',0x40:'GET',0x44:'GETL',0xD0:'GETLLAR',0xB4:'PUTLLC',0xB0:'PUTLLUC',0xB8:'PUTQLLUC',0x21:'PUTB',0x22:'PUTF',0x41:'GETB',0x42:'GETF'}
CH = {16:'LSA',17:'EAH',18:'EAL',19:'SIZE',20:'TAG',21:'CMD',22:'TAGMASK',23:'TAGUPD',24:'TAGSTAT',27:'ATOMSTAT',0:'EVSTAT',1:'EVMASK',2:'EVACK',8:'DEC_W',9:'DEC_R'}
EV = struct.Struct('<II4IQQ16I II')
for path in sys.argv[1:]:
    b = open(path,'rb').read(); p = 16 + 64 + 2048 + 262144
    regs = {}; out = []
    while True:
        k, ch, *rest = EV.unpack_from(b, p); p += EV.size
        v = rest[0:4]; nl = rest[-2]
        if k == 6: break
        p += nl * 20
        if k == 5: p += 2048
        name = {1:'wrch',2:'rdch',3:'rchcnt',4:'sys',5:'sysend'}[k]
        if k == 1 and ch in (16,17,18,19,20): regs[CH[ch]] = v[0]
        if k == 1 and ch == 21:
            out.append(f"{CMD.get(v[0]&0xFF,hex(v[0]))} ea={regs.get('EAH',0):X}:{regs.get('EAL',0):08X} lsa={regs.get('LSA',0):05X} size={regs.get('SIZE',0):X} lines={nl}")
        elif k == 2 and ch == 27: out.append(f"  atomstat={v[0]}")
        elif k in (2,3) and ch not in (27,):
            out.append(f"  {name} {CH.get(ch,ch)}={v[0]:X} lines={nl}")
        elif k == 4: out.append(f"  SYSCALL r3={v[0]:X}")
    print('==', path, len(out)); print('\n'.join(out))
