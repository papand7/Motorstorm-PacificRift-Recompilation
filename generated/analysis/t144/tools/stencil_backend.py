"""T144: classify test_t144_stencil_backend's RSXI end-of-frame snapshots (frame 5) per arm.
RT_A 0x08000000: left half tagged 255 then NOTEQUAL 255 white -> RSX: left = clear (32,32,32), right white.
RT_E 0x0A000000: stencil-only clear 64 then EQUAL 64 green -> RSX: all green.
RT_F 0x0A400000: stencil 0 then EQUAL 64 green -> RSX: all clear (black).
Also counts zs_clear events and checks the stencil_back field in the RSXI draw records.
usage: python stencil_backend.py <run_dir>..."""
import sys, os, glob, json, re, collections
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 't137', 'tools'))
from msaa_backend import load


def snap(run, rt):
    f = glob.glob(os.path.join(run, 'rsxi', 'frames', '*', 'snap*_end_*_rt_%s.bmp' % rt)) or \
        glob.glob(os.path.join(run, 'rsxi', 'frames', '*', 'snap*_rt_%s.bmp' % rt))
    return load(sorted(f)[-1]) if f else None


def frac(img, x0, x1, want):
    n = ok = 0
    for y in range(4, img[1] - 4, 7):
        for x in range(x0, x1, 7):
            n += 1; ok += img[2][y][x] == want
    return ok / n if n else 0.0


fix = re.compile(r'(?<![A-Za-z"])-?(nan|inf)\b', re.I)
for run in sys.argv[1:]:
    name = os.path.basename(run.rstrip('/'))
    a, e, f = snap(run, '08000000'), snap(run, '0A000000'), snap(run, '0A400000')
    if not a:
        print('%-12s no RT_A snapshot' % name); continue
    W = 1280
    left_clear = frac(a, 8, W // 2 - 8, (32, 32, 32)); right_white = frac(a, W // 2 + 8, W - 8, (255, 255, 255))
    e_green = frac(e, 8, 504, (0, 255, 0)) if e else -1
    f_black = frac(f, 8, 504, (0, 0, 0)) if f else -1
    ok_a = left_clear > 0.99 and right_white > 0.99
    ok_ef = e_green > 0.99 and f_black > 0.99
    zs = collections.Counter(); back = 0
    for ev in glob.glob(os.path.join(run, 'rsxi', 'frames', '*', 'events.jsonl')):
        for l in open(ev, encoding='utf-8', errors='replace'):
            try: j = json.loads(fix.sub('null', l))
            except Exception: continue
            if j.get('e') == 'zs_clear': zs[(j['mask'], j['stencil'])] += 1
            if j.get('e') == 'draw' and 'stencil_back' in j.get('guest', {}): back += 1
    print('%-12s RT_A left clear %.3f right white %.3f -> %s | RT_E (clear 64, EQUAL 64) green %.3f, RT_F (clear 0) black %.3f -> %s'
          ' | zs_clear %s, draws with stencil_back %d' % (name, left_clear, right_white, 'RSX' if ok_a else 'NOT RSX',
          e_green, f_black, 'RSX' if ok_ef else 'NOT RSX', dict(zs), back))
