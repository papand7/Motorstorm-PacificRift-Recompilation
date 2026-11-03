"""T70B: offline inspection of the built WWS-AOT exe (nothing is launched).

1. Every spu_reloc_register_module() call in wws_reloc_register.c: its 16-byte signature and its
   64-bit body hash (little-endian, an immediate or a constant) must occur in the exe image.
2. The ctor's object: wws_reloc_register.c.obj must carry a .CRT$XCU entry (MSVC static init = the
   __attribute__((constructor))), and llvm-nm must list wws_reloc_register_all + 31 wr_ms_*_register.
3. Every per-module object must define its wr_ms_<id>_spu_recomp_register.
4. The off-by-default gates in source: the ctor needs PS3_SPU_WWS_AOT exactly "1"; SPURS_BUSY_MS
   defaults to 0; PS3_FTRACE / PS3_FTRACE_SPUJOB are only read from getenv.
Usage: py -3 inspect_aot_exe.py <exe> <build dir>"""
import re, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
REG = ROOT / 'generated/spu_raw/wws_reloc/wws_reloc_register.c'
NM = ROOT / 'build/llvm/clang+llvm-23.1.3-x86_64-pc-windows-msvc/bin/llvm-nm.exe'
OBJDUMP = NM.with_name('llvm-objdump.exe')
T70 = ROOT / 'ps3recomp-t70'

exe, bdir = Path(sys.argv[1]), Path(sys.argv[2])
img = exe.read_bytes()
src = REG.read_text()
mods = re.findall(r'static const uint8_t sig\[16\] = \{([^}]*)\};.*?spu_begin_image\((\d+)\); (wr_ms_\w+?)_spu_recomp_register\(\);'
                  r'\s*spu_reloc_register_module\(sig, ent, (0x[0-9A-F]+)u, (0x[0-9A-F]+)u, (0x[0-9A-F]+)u, (0x[0-9A-F]+)ull, (\d+)\); \}\s*/\* ([^*]+) \*/', src, re.S)
fail = []
print(f'modules in register.c: {len(mods)}')
for sig, img_id, sym, eo, e16, span, h, img2, name in mods:
    sb = bytes(int(x, 16) for x in sig.split(','))
    hb = int(h, 16).to_bytes(8, 'little')
    ok_s, ok_h = sb in img, hb in img
    if not (ok_s and ok_h):
        fail.append(f'{name}: sig {ok_s} hash {ok_h}')
    print(f'  {name.strip():44s} sig={"Y" if ok_s else "N"} hash={"Y" if ok_h else "N"} entry={e16} span={span}')
if len(mods) != 31:
    fail.append(f'{len(mods)} modules, expected 31')

objs = list(bdir.rglob('wws_reloc_register.c.obj'))
if len(objs) != 1:
    fail.append(f'register obj count {len(objs)}')
else:
    o = objs[0]
    hdr = subprocess.run([str(OBJDUMP), '-h', str(o)], capture_output=True, text=True).stdout
    xcu = '.CRT$XCU' in hdr
    syms = subprocess.run([str(NM), str(o)], capture_output=True, text=True).stdout
    defined_all = re.search(r' T wws_reloc_register_all$', syms, re.M) is not None
    undef = set(re.findall(r' U (wr_ms_\w+_spu_recomp_register)$', syms, re.M))
    print(f'register obj: .CRT$XCU={xcu} wws_reloc_register_all defined={defined_all} wr_ms refs={len(undef)}')
    if not (xcu and defined_all and len(undef) == 31):
        fail.append('register obj')
    have = set()
    for mo in bdir.rglob('*.obj'):
        if 'wws_reloc' not in str(mo) or mo == o:
            continue
        s = subprocess.run([str(NM), '--defined-only', str(mo)], capture_output=True, text=True).stdout
        have |= set(re.findall(r' T (wr_ms_\w+_spu_recomp_register)$', s, re.M))
    print(f'module objs defining the referenced register fns: {len(undef & have)}/31')
    if undef - have:
        fail.append(f'unresolved {sorted(undef - have)}')

ctor = re.search(r'wws_reloc_ctor\(void\)\s*\{(.*?)\n\}', src, re.S).group(1)
gate_aot = 'getenv("PS3_SPU_WWS_AOT")' in ctor and "e[0] == '1' && !e[1]" in ctor
spurs = (T70 / 'libs/spurs/cellSpurs.c').read_text(errors='replace')
gate_busy = 'getenv("SPURS_BUSY_MS"); v = e ? atoi(e) : 0;' in spurs
print(f'gate PS3_SPU_WWS_AOT (exactly "1", else nothing registered): {gate_aot}')
print(f'gate SPURS_BUSY_MS (default 0 = off): {gate_busy}')
for k in (b'PS3_SPU_WWS_AOT', b'PS3_SPU_WWS_AOT_VERIFY', b'PS3_SPU_WWS_AOT_BASES', b'SPURS_BUSY_MS',
          b'PS3_FTRACE_SPUJOB', b'[spurs-busy]', b'[spu-reloc]'):
    print(f'  string {k.decode():24s} in exe: {k in img}')
    if k not in img:
        fail.append(f'string {k}')
if not (gate_aot and gate_busy):
    fail.append('gates')
print('RESULT', 'PASS' if not fail else 'FAIL ' + '; '.join(fail))
sys.exit(0 if not fail else 1)
