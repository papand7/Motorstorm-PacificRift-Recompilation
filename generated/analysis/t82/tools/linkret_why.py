"""T82: for each PM site the patched rule reclassifies, the conditional predecessor and the write it saw."""
import json, struct, sys
sys.path.insert(0, 'ps3recomp-t82/tools')
import spu_disasm as d, spu_lifter as L
raw = open('generated/spu_raw/wws_job_pm.bin', 'rb').read(); base = 0xA00
ins = [d.spu_decode(struct.unpack_from('>I', raw, o)[0], base + o) for o in range(0, len(raw) - 3, 4)]
idx = {x.addr: i for i, x in enumerate(ins)}
for site in (0x26A8, 0x26C4, 0x2714, 0x271C, 0x28EC):
    rn = int(L._bi_target_reg(ins[idx[site]]))
    j = idx[site] - 1
    while j >= 0 and ins[j].mnemonic not in ('bi', 'br', 'bra', 'iret', 'stop', 'stopd'): j -= 1
    bs = ins[j + 1].addr
    for x in ins:
        if x.mnemonic in L._COND_BR:
            i16 = (x.raw >> 7) & 0xFFFF; i16 -= 0x10000 if i16 & 0x8000 else 0
            t = (x.addr + (i16 << 2)) & 0x3FFFF
            if bs <= t <= site:
                k = idx[x.addr]
                for jj in range(k - 1, max(-1, k - 24), -1):
                    w = ins[jj]
                    if w.mnemonic in ('bi', 'br', 'bra', 'iret', 'stop', 'stopd'): break
                    if w.mnemonic not in L._NO_RT_WRITE and L._dest_reg(w) == rn and not L._is_identity_move(w):
                        print(f'site {site:05X} r{rn} block@{bs:05X}: pred {x.addr:05X} {x.mnemonic} -> {t:05X}; write {w.addr:05X} {w.mnemonic} {w.operands}')
                        break
