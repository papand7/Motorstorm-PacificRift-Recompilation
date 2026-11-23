# Private: run the port's redraw (test_pc_prompts.exe preview mode) on every table texture from the GUI packs,
# check that the C hash finds each one and that nothing is drawn past the icon's own rect, and write
# before/after PNGs to prompts/preview/ (one row per label tried).
import sys, os, struct, glob, subprocess, re
import numpy as np
from PIL import Image
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..', '..'))
sys.path.insert(0, os.path.join(HERE, '..', 'scratch'))
from pack import parse
from dumptex import dxt5

EXE = os.path.join(ROOT, 'build', 'prompts_test', 'test_pc_prompts.exe')
GUI = os.path.join(ROOT, 'generated', 'analysis', 't30', 'frontend', 'gui_all')
OUT = os.path.join(HERE, '..', 'preview')
# the user's keys first, then the long names
USER = {'PCPR_CROSS': 'ENTER', 'PCPR_CIRCLE': 'X', 'PCPR_SQUARE': 'Q', 'PCPR_TRIANGLE': 'E', 'PCPR_START': 'P',
        'PCPR_SELECT': 'C', 'PCPR_L1': '1', 'PCPR_R1': '3', 'PCPR_LEFT': 'LEFT', 'PCPR_RIGHT': 'RIGHT'}
EXTRA = ['CTRL', 'ESC', 'SPACE', 'SHIFT', 'BKSP', 'F12']

src = open(os.path.join(ROOT, 'port-vkgame', 'pc_prompts.h')).read()
table = re.findall(r'\{\s*(\d+),\s*(\d+),\s*0x([0-9A-F]+)ull,\s*(PCPR_\w+),\s*(\d),\s*([\d.]+)f,\s*([\d.]+)f,\s*(\d+),\s*(\d+),', src)
os.makedirs(OUT, exist_ok=True)
want = {int(h, 16): (i, int(w), int(hh), b, int(cl), float(cx), float(cy), int(rw), int(rh))
        for i, (w, hh, h, b, cl, cx, cy, rw, rh) in enumerate(table)}


def fnv(b):
    x = 0xcbf29ce484222325
    for c in b:
        x ^= c; x = (x * 0x100000001b3) & 0xFFFFFFFFFFFFFFFF
    return x


def comp(a):
    t = Image.fromarray(np.ascontiguousarray(a), 'RGBA')
    bg = Image.new('RGBA', t.size, (40, 90, 40, 255)); bg.alpha_composite(t)
    return bg


done = set()
rows = []
bad = 0
for f in sorted(glob.glob(os.path.join(GUI, '*.gui'))):
    d = open(f, 'rb').read()
    try:
        r = parse(d)
    except Exception:
        continue
    if not r: continue
    for e in r['ents']:
        n = e['names'][0]
        if not n.endswith('.dds'): continue
        o = e['off']
        w, h = struct.unpack_from('>HH', d, o + 0x1C)
        if struct.unpack_from('>H', d, o + 0x22)[0] != 0x0B: continue
        if not any(v[1] == w and v[2] == h for v in want.values()): continue
        l0 = ((w + 3) // 4) * ((h + 3) // 4) * 16
        data = d[o + 43:o + 43 + l0]
        hv = fnv(data)
        if hv not in want or hv in done: continue
        done.add(hv)
        idx, _, _, b, clear, cx, cy, rw, rh = want[hv]
        before = dxt5(data, w, h)
        # outside the rect (1 texel of anti-aliasing allowed)
        yy, xx = np.mgrid[0:h, 0:w]
        outside = (xx + 0.5 < cx - rw / 2 - 1) | (xx + 0.5 > cx + rw / 2 + 1) | (yy + 0.5 < cy - rh / 2 - 1) | (yy + 0.5 > cy + rh / 2 + 1)
        tiles = [comp(before)]
        for lab in [USER[b]] + EXTRA:
            inp = os.path.join(OUT, 'in.bin'); outp = os.path.join(OUT, 'out.bin')
            open(inp, 'wb').write(data)
            p = subprocess.run([EXE, inp, str(w), str(h), str(idx), lab, outp], capture_output=True, text=True)
            after = dxt5(open(outp, 'rb').read(), w, h)
            if clear:
                leak = int(((after[:, :, 3] > 8) & outside).sum())
            else:
                diff = np.abs(after.astype(int) - before.astype(int)).max(axis=2)
                # BC3 re-encoding of a block the cap touches may shift neighbours a little; a cap edge is a big change
                leak = int(((diff > 60) & outside).sum())
            if leak: bad += 1
            rows.append((idx, n, lab, p.returncode, leak))
            tiles.append(comp(after))
        im = Image.new('RGB', (w, (h + 4) * len(tiles)), (255, 0, 255))
        for k, t in enumerate(tiles): im.paste(t.convert('RGB'), (0, k * (h + 4)))
        im.save(os.path.join(OUT, '%02d_%s.png' % (idx, n[:-4].replace(' ', '_'))))
for r_ in sorted(rows):
    if r_[4] or r_[3]: print('LEAK/ERR', r_)
print('textures found', len(done), 'of', len(want), '; renders', len(rows), '; with texels past the rect:', bad)
