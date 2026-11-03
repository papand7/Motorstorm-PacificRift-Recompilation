"""T142: pixel checks on test_t142_backend's RSXI end-of-frame snapshots (frame 5).

RT_A 0x08000000 (scene: magenta outside W x H, grey ramp inside; top-left quarter 0x30 after pass F;
middle half doubled by pass H's feedback), RT_C 0x0A000000 (identity read before F), RT_E 0x0B000000
(coordinates 0..1.25, clamped), RT_G 0x0C000000 (identity read after F). The run's arm name says
which checks apply: *fb* checks feedback, *msaa* skips feedback and allows resolve rounding,
nowin expects the old whole-surface binding (stretch) and only reports.

usage: python sampling_check.py <run_dir>...   exit 1 if a windowed arm fails a check
"""
import glob
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 't137', 'tools'))
from msaa_backend import load  # noqa: E402


def snap(run, rt):
    f = glob.glob(os.path.join(run, 'rsxi', 'frames', '*', 'snap*_end_*_rt_%s.bmp' % rt)) or \
        glob.glob(os.path.join(run, 'rsxi', 'frames', '*', 'snap*_rt_%s.bmp' % rt))
    return load(sorted(f)[-1])[2] if f else None


def tinted(p):   # content is grey (R = G = B); anything magenta-ish came from outside the texture
    return abs(p[0] - p[1]) > 3 or abs(p[2] - p[1]) > 3


fails = 0
for run in sys.argv[1:]:
    name = os.path.basename(run.rstrip('/\\'))
    W = H = None
    for line in open(os.path.join(run, 'err.txt'), encoding='utf-8', errors='replace'):
        if line.startswith('[t142] frame 5:'):
            W, H = (int(v) for v in line.split()[4].split('x'))
    a, c, e, g = (snap(run, r) for r in ('08000000', '0A000000', '0B000000', '0C000000'))
    if not (W and a and c and e and g):
        print(f'{name}: missing frame-5 data or snapshots'); fails += name != 'nowin'; continue
    tol = 2 if 'msaa' in name or 'linear' in name else 0
    q = lambda x, y: x < W // 4 + 2 and y < H // 4 + 2           # pass F's quarter (+ margin)
    qi = lambda x, y: 2 <= x < W // 4 - 2 and 2 <= y < H // 4 - 2
    m = lambda x, y: W // 4 - 2 <= x < (3 * W) // 4 + 2 and H // 4 - 2 <= y < (3 * H) // 4 + 2
    mi = lambda x, y: W // 4 + 2 <= x < (3 * W) // 4 - 2 and H // 4 + 2 <= y < (3 * H) // 4 - 2
    fb = 'msaa' not in name
    px = [(x, y) for y in range(H) for x in range(W)]
    res = {}
    res['C tinted'] = sum(tinted(c[y][x]) for x, y in px)
    res['E tinted'] = sum(tinted(e[y][x]) for x, y in px)
    res['G tinted'] = sum(tinted(g[y][x]) for x, y in px)
    # identity read before F: equals the scene wherever F and H did not change it
    res['C != A'] = sum(max(abs(c[y][x][k] - a[y][x][k]) for k in range(3)) > tol
                        for x, y in px if not q(x, y) and not (fb and m(x, y)))
    # ...and inside F's quarter the ramp (a function of x only: row H-3 of the scene, below F and H)
    res['C quarter != ramp'] = sum(max(abs(c[y][x][k] - a[H - 3][x][k]) for k in range(3)) > tol
                                   for x, y in px if qi(x, y))
    # identity read after F: F's quarter is 0x30, the rest the scene (outside H)
    res['G != A'] = sum(max(abs(g[y][x][k] - a[y][x][k]) for k in range(3)) > tol
                        for x, y in px if not (fb and m(x, y)))
    res['G missed F'] = sum(g[y][x] != (0x30, 0x30, 0x30) for x, y in px if qi(x, y))
    # clamp: past u = 1 (x >= 0.8 W) every column repeats the texture's last column
    x0 = int(0.8 * W) + 2
    res['E not clamped'] = sum(max(abs(e[y][x][k] - e[y][W - 1][k]) for k in range(3)) > tol
                               for y in range(H) for x in range(x0, W))
    if 'fb' in name:   # feedback: the middle is the pre-H scene (= G) added to itself
        res['H feedback'] = sum(max(abs(a[y][x][k] - min(255, 2 * g[y][x][k])) for k in range(3)) > max(tol, 1)
                                for x, y in px if mi(x, y))
    if name == 'win_nogs':   # no guest samplers: units 1..15 WRAP, so the clamp is not the guest's (pre-existing)
        res['E not clamped (WRAP sampler, not checked)'] = res.pop('E not clamped')
    bad = {k: v for k, v in res.items() if v and 'not checked' not in k}
    verdict = 'report only (whole-surface binding)' if name == 'nowin' else ('PASS' if not bad else 'FAIL')
    if name != 'nowin' and bad:
        fails += 1
    print(f'{name:11s} {W}x{H}  {verdict:8s} ' + '  '.join(f'{k}={v}' for k, v in res.items()))
print(f'sampling_check: {fails} failing arm(s)')
sys.exit(1 if fails else 0)
