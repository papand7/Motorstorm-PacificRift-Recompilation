"""T137: replay a race RSXI frame's draw order through the RSX_MSAA rules and count the work they
would issue: sample-image rebuilds (expand), window copies, zeta images, resolves, broadcasts.

Rules (rsx_d3d12_backend.c, RSX_MSAA=1): a read of an antialias-3 colour target rebuilds its
sample image when the target is bound now, or was written since the last rebuild; a windowed
read (texture smaller than the 2W x H image) adds a copy when the image changed; a zeta read as
A8R8G8B8 rebuilds its 2W x H image when the zeta was written since (conv_ok rules approximated:
a draw with depth or stencil writes on the bound zeta invalidates it, as RSX_DEPTH_STATE=1 does).

Only units the draw's fragment program fetches count (shaders/fp_*.hlsl beside the frame), as the
replay checks fp_units.

usage: python expand_cost.py <events.jsonl> [W H bytes_per_texel]
"""
import sys, os, re
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 't113', 'tools'))
from ev import events

path = sys.argv[1]
W, H, BPP = (int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4])) if len(sys.argv) > 4 else (1280, 720, 4)
sd = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(path)))), 'shaders')
units = {}
for f in os.listdir(sd) if os.path.isdir(sd) else []:
    if f.startswith('fp_') and f.endswith('.hlsl'):
        h = open(os.path.join(sd, f), encoding='utf-8', errors='replace').read()
        units['0x' + f[3:11].upper()] = set(int(u) for u in re.findall(r'rsx_tex(?:\[(\d+)\]|(\d+))', h) for u in u if u)
aa3 = set(); written = {}; gen = {}; xgen = {}; wgen = {}; zgen = {}; zconv = {}
n = dict(expand=0, expand_bound=0, wincopy=0, zimage=0, draws=0, ms_draws=0, reads=0)
cur = None
for e in events(path):
    if e.get('e') != 'draw': continue
    g = e['guest']; n['draws'] += 1
    aa = (g['rt_fmt'] >> 12) & 0xF
    tg = [g['rt']] + [m for m in g.get('mrt', []) if m != '0x00000000']
    if aa == 3:
        n['ms_draws'] += 1
        for t in tg: aa3.add(t)
    bound = set(tg) if aa == 3 else set()
    for t in e.get('tex', []):
        r = t['req']
        if not r.get('set'): continue
        fu = units.get(g['fp'].upper().replace('0X', '0x'))
        if fu is not None and t['unit'] not in fu: continue
        a = r['addr']
        if t.get('src') == 'rt_exact' and a in aa3:
            n['reads'] += 1
            gen.setdefault(a, 1)
            if a in bound or xgen.get(a) != gen[a]:
                n['expand'] += 1; n['expand_bound'] += a in bound
                xgen[a] = gen[a] if a not in bound else -1
            if (r['w'], r['h']) != (2 * W, H) and wgen.get(a) != (xgen[a], n['expand']):
                n['wincopy'] += 1; wgen[a] = (xgen[a], n['expand'])
        if t.get('src') == 'zeta_as_color' and aa == 3:
            if not zconv.get(a): n['zimage'] += 1; zconv[a] = 1
    # writes after the reads
    for t in bound: gen[t] = gen.get(t, 1) + 1
    if aa == 3 and (g['depth']['write'] and g['depth']['test'] or g['stencil']['test']):
        zconv[g['zeta']] = 0
mb = W * 2 * H * BPP / 1048576.0
print('draws %(draws)d (2-sample %(ms_draws)d); reads of 2-sample targets %(reads)d' % n)
print('sample-image rebuilds %(expand)d (%(expand_bound)d of a target bound at the time); window copies %(wincopy)d; zeta images %(zimage)d' % n)
traffic = (n['expand'] * 3 + n['wincopy'] * 2 + n['zimage'] * 3) * mb   # MS read (2x) + write, copy read+write
print('approx. memory traffic of that work: %.0f MiB per frame (2560x720 RGBA8 image = %.1f MiB)' % (traffic, mb))
