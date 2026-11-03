"""T169: the two real velocity readers, every cube mask seen in game, rewritten and plain, on WARP. References from struct, not project code.
Private ucode from the VC capture. Run from the root under env_t169.cmd. usage: python real_fp_warp_t169.py"""
import glob, struct, subprocess, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
V = ROOT / 'ps3recomp-t169/libs/video'
SH = Path(glob.glob(str(ROOT / 'generated/analysis/t169/ab/runtime-VC-*/rsxi/shaders'))[0])
half = lambda lo, hi: struct.unpack('<e', bytes((lo, hi)))[0]
DEC, RAW = (half(1, 0x38), half(0, 0x34)), (1 / 255, 0x38 / 255)
fails = 0
with tempfile.TemporaryDirectory() as d:
    exe = Path(d) / 'r.exe'
    r = subprocess.run(['clang-cl', '/nologo', '/O1', '/MD', '/w', '-std:c17', '/D_CRT_SECURE_NO_WARNINGS', f'-I{ROOT / "ps3recomp-t169/include"}', f'-I{V}', str(Path(__file__).with_suffix('.c')), str(V / 'rsx_fp_decompiler.c'),
                        f'/Fe{exe}', f'/Fo{d}\\', '/link', 'd3d11.lib', 'd3dcompiler.lib', 'dxguid.lib'], capture_output=True, text=True)
    if r.returncode:
        print(r.stdout[-2000:], r.stderr[-800:])
        sys.exit(1)
    for fp in ('0074B441', '02193941'):
        for cube in ('0', '8000', 'C000', 'C001', '4010'):
            for ctrl, gamma in (('0', -1), ('40', -1), ('40', 0)):
                for rw, want in ((1, DEC), (0, RAW)):
                    p = subprocess.run([str(exe), str(SH / f'fp_{fp}.ucode'), '1', cube, ctrl, str(gamma), str(rw)], capture_output=True, text=True, timeout=120)
                    o = p.stdout.strip()
                    ok = p.returncode == 0 and 'output' in o
                    if ok:
                        x, y = map(float, o.split('output')[1].split())
                        ok = abs(x - want[0]) < 1e-4 and abs(y - want[1]) < 1e-4
                        sp = 'spell=sep' in o
                        ok = ok and sp == (cube != '0')
                    fails += not ok
                    print('PASS' if ok else 'FAIL', fp, 'cube', cube, 'ctrl', ctrl, 'gamma', gamma, 'rw', rw, 'want %.6f %.6f |' % want, o or p.stderr[:300])
print('real_fp_warp failures:', fails)
sys.exit(1 if fails else 0)
