"""T169: is the D2 vehicle speckle the 0xBF velocity misread? Private analysis of the complete T165 B3 frame (f002192, baseline renderer).
Model of the first tap section of the final composite fp 0x02193941 on captured surfaces: colour 0x01DD0000 (with its alpha unavailable in BMP, weight 1)
offset by velocity * 0.03125 * (noise - 0.5), for three velocity buffers:
  wiped     snap19 as host reads it now (op 915 without stencil), bytes as unorm: the D1/F1 baseline
  kept-bad  snap18 where op 914 wrote velocity, else snap19, bytes as unorm: RSX_DEPTH_STATE=1 with the misread (D2)
  kept-ok   same buffer decoded as (half x, half y); y's high byte is alpha, absent from the BMP, so y is 0: the reference for the corrected read
Run from this folder (PIL). usage: py -3 velocity_repro_t169.py"""
import collections, glob, json, sys
from pathlib import Path

import numpy as np
from PIL import Image

from rsxi_parse_t169 import read_events

T = Path(__file__).resolve().parents[1]
F = Path(glob.glob(str(T.parent / 't165/ab/runtime-B3-*/rsxi/frames/f002192'))[0])
load = lambda pat: np.asarray(Image.open(glob.glob(str(F / pat))[0]).convert('RGB'), dtype=np.uint8)
v18, v19 = load('snap18_*'), load('snap19_*')
col = load('snap*_end_op9999_rt_01DD0000.bmp').astype(np.float32)
pre = load('snap11_*').astype(np.float32)

ev = list(read_events(str(F / 'events.jsonl')))
dr = [e for e in ev if e['e'] == 'draw']
print('--- guest state of the velocity pass (ops 597-914) and of all race-frame colour passes')
c = collections.Counter()
for e in dr:
    x = e['guest']
    c[(x['rt'], x['depth']['test'], x['depth']['write'], x['depth']['func'], x['stencil']['test'], x['stencil']['func'], x['alpha'])] += 1
for k, n in c.most_common(14):
    print(n, k)
print('depth funcs on the scene depth', collections.Counter(e['guest']['depth']['func'] for e in dr if e['guest']['zeta'] == '0x00ED0000'))
print('alpha test field', collections.Counter(e['guest']['alpha'] for e in dr))
vp = [e for e in dr if 597 <= int(e['op']) <= 914]
print('velocity pass fps', collections.Counter(e['guest']['fp'] for e in vp).most_common(8))

half = lambda lo, hi: np.nan_to_num(np.frombuffer(((hi.astype(np.uint32) << 8) | lo).astype(np.uint16).tobytes(), dtype=np.float16).reshape(lo.shape).astype(np.float32), nan=0.0, posinf=0.0, neginf=0.0)
written = np.any(v18 != 0, axis=2)
changed = np.any(v18 != v19, axis=2)
print('--- velocity surface bytes')
print('op 914 nonzero %.2f %%, op 915 changed %.2f %%' % (written.mean() * 100, changed.mean() * 100))
for name, m, v in (('tagged, before op 915 (snap18)', written, v18), ('same pixels, after op 915 (snap19)', written, v19), ('untagged, after op 915', ~written, v19)):
    r, g = v[..., 0][m], v[..., 1][m]
    x = half(v[..., 0], v[..., 1])[m]
    print(f'{name}: n={m.sum()} R(x_lo) mean {r.mean():.1f} std {r.std():.1f}; G(x_hi) mean {g.mean():.1f} std {g.std():.1f}; '
          f'unorm |x,y| median {np.median(np.hypot(r, g)) / 255:.3f}; half x median |{np.median(np.abs(x)):.5f}| p99 |{np.percentile(np.abs(x), 99):.4f}|')

h, w = v18.shape[:2]
yy, xx = np.mgrid[0:h, 0:w]


def tap(vx, vy):
    """One colour tap of the composite's blur on a jitter from a repeatable noise (the guest's noise surface 0x02190000 isn't captured as a snapshot)."""
    rng = np.random.default_rng(7)
    n = rng.random((h, w), dtype=np.float32) - 0.5
    ox = np.clip(xx + vx * 0.03125 * n * w, 0, w - 1).astype(int)
    oy = np.clip(yy - vy * 0.03125 * n * h, 0, h - 1).astype(int)
    return col[oy, ox]


kept = v19.copy()
kept[written] = v18[written]
un = lambda v: (v[..., 0] / 255.0, v[..., 1] / 255.0)
out = {'wiped': tap(*un(v19)), 'kept-bad': tap(*un(kept)), 'kept-ok': tap(half(kept[..., 0], kept[..., 1]), np.zeros((h, w), np.float32))}


def speck(a, m):
    y = a @ np.array([.2126, .7152, .0722], np.float32)
    lap = np.abs(y[1:-1, 1:-1] * 4 - y[:-2, 1:-1] - y[2:, 1:-1] - y[1:-1, :-2] - y[1:-1, 2:])
    return float(np.median(lap[m[1:-1, 1:-1]])), float(lap[m[1:-1, 1:-1]].mean())


print('--- reproduction: Laplacian median, mean (speckle) on tagged / untagged pixels')
print('no blur        ', speck(col, written), speck(col, ~written))
for k, a in out.items():
    print(f'{k:15s}', speck(a, written), speck(a, ~written))
    Image.fromarray(a.clip(0, 255).astype('uint8')).save(T / 'img' / f'velrepro_{k}.png')
ys, xs = np.nonzero(written)
print('kept-bad jitter px median/p99', *(np.percentile(np.hypot(*un(kept))[written] * 0.03125 * 0.5 * w, [50, 99]).round(2)), '| kept-ok', *(np.percentile(np.abs(half(kept[..., 0], kept[..., 1]))[written] * 0.03125 * 0.5 * w, [50, 99]).round(3)))
print('share non-finite x', float(np.mean(((kept[..., 1] & 0x7C) == 0x7C)[written])))
print('tagged bbox', xs.min(), xs.max(), ys.min(), ys.max())
b = (max(0, np.percentile(xs, 5).astype(int) - 20), max(0, np.percentile(ys, 5).astype(int) - 20), min(w, np.percentile(xs, 95).astype(int) + 20), min(h, np.percentile(ys, 95).astype(int) + 20))
sheet = Image.new('RGB', ((b[2] - b[0]) * 3 + 8, b[3] - b[1]))
for i, k in enumerate(('wiped', 'kept-bad', 'kept-ok')):
    sheet.paste(Image.fromarray(out[k].clip(0, 255).astype('uint8')).crop(b), (i * (b[2] - b[0] + 4), 0))
sheet.save(T / 'img' / 'velrepro_sheet.png')
Image.fromarray(np.dstack([written * 255] * 3).astype('uint8')).save(T / 'img' / 'velrepro_tagged.png')
print('wrote img/velrepro_sheet.png, crop', b)
