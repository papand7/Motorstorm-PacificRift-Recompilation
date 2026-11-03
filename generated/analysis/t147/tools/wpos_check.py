"""T145: pixel checks on test_t145_backend's RSXI end-of-frame snapshots (frame 5).

RT_S 0x08000000 = the scene (vertical grey ramp), RT_L 0x0A000000 = RT_S read through the race's
WPOS lookup, RT_N 0x0B000000 = RT_S read through TC0 (no WPOS). Per arm:
  on, on_gbv, on_all        RT_L == RT_S on every pixel (the guest's bottom-left window)
  on_int                    integer centre: v = (y + 1) / H is the boundary below the pixel's own
                            texel, so RT_L equals RT_S or RT_S one row down on every pixel, and the
                            log shows the integer-centre remap (exact values: the WARP test)
  off, on_unset, on_top     RT_L == RT_S mirrored vertically (SV_Position / a top-left window)
  every arm                 RT_N == RT_S (programs without WPOS reads are unchanged)
usage: python wpos_check.py <run_dir>...   exit 1 on a failed check
"""
import glob, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 't137', 'tools'))
from msaa_backend import load  # noqa: E402


def snap(run, rt):
    f = sorted(glob.glob(os.path.join(run, 'rsxi', 'frames', '*', 'snap*_rt_%s.bmp' % rt)))
    return load(f[-1])[2] if f else None


fails = 0
for run in sys.argv[1:]:
    name = os.path.basename(os.path.normpath(run))
    s, l, n = (snap(run, r) for r in ('08000000', '0A000000', '0B000000'))
    if not (s and l and n):
        print(f'{name}: missing snapshots'); fails += 1; continue
    H, W = len(s), len(s[0])
    ident = sum(l[y][x] == s[y][x] for y in range(H) for x in range(W))
    mirr = sum(l[y][x] == s[H - 1 - y][x] for y in range(H) for x in range(W))
    dn1 = sum(l[y][x] == s[min(y + 1, H - 1)][x] for y in range(H) for x in range(W))
    nid = sum(n[y][x] == s[y][x] for y in range(H) for x in range(W))
    rows = len({s[y][0] for y in range(H)})
    want = {'on': 'ident', 'on_gbv': 'ident', 'on_all': 'ident', 'on_int': 'dn1'}.get(name, 'mirr')
    got = {'ident': ident, 'mirr': mirr, 'dn1': max(ident, dn1)}[want]
    ok = got == W * H and nid == W * H
    if want == 'dn1':   # a boundary lookup: either neighbour, but the integer-centre pipeline must be the one used
        log = open(os.path.join(run, 'err.txt'), encoding='utf-8', errors='replace').read()
        ok = ok and 'centre=integer): 1 read(s) remapped' in log
    fails += not ok
    print(f'{name:9s} {W}x{H} ({rows} distinct rows)  L==S {ident:7d}  L==mirror(S) {mirr:7d}  L==S(y+1) {dn1:7d}'
          f'  N==S {nid:7d}  expect {want}: {"PASS" if ok else "FAIL"}')
print(f'wpos_check: {fails} failure(s)')
sys.exit(1 if fails else 0)
