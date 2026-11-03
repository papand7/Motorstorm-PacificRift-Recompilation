import sys, struct
sys.path.insert(0, 'ps3recomp-t82/tools')
import spu_disasm as d
raw = open('generated/spu_raw/wws_job_pm.bin', 'rb').read(); base = 0xA00
lo, hi = int(sys.argv[1], 16), int(sys.argv[2], 16)
for a in range(lo, hi, 4):
    w = struct.unpack_from('>I', raw, a - base)[0]
    i = d.spu_decode(w, a)
    print(f'{a:05X}: {w:08X}  {i.mnemonic} {i.operands}')
