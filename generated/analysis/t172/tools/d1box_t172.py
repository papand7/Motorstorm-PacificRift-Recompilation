"""T172: the box draws of the richest capture (D1 f005110). Run from t169/tools. usage: py -3 d1box_t172.py"""
import glob, json, sys
from pathlib import Path
sys.path.insert(0, '.')
from rsxi_parse_t169 import read_events

d = glob.glob('../ab/runtime-D1-*/rsxi/frames/f005110')[0]
rows = list(read_events(glob.glob(d + '/events.jsonl*')[0]))
draw = [r for r in rows if r.get('e') == 'draw']
print('draws', len(draw))
box = [r for r in draw if r['guest']['fp'] == '0x022C20C1']
print('box ops', [r['op'] for r in box][:3], len(box), 'cmd', [r['guest']['cmd_offset'] for r in box][:3])
r = box[0]
print('TOP', sorted(r.keys()))
print('GUEST', {k: v for k, v in r['guest'].items() if k not in ('vp_consts', 'fp_consts')})
print('NATIVE', json.dumps(r.get('native'))[:900])
print('TEX', json.dumps(r.get('tex'))[:1400])
print('GEOM', json.dumps(r.get('geom'))[:1200])
print('VPC', json.dumps(r['guest'].get('vp_consts'))[:900])
print('FPC', json.dumps(r['guest'].get('fp_consts'))[:300])
print('REFS', [x['guest']['stencil']['ref'] for x in box])
print('stencil_back', r['guest'].get('stencil_back'), 'ds_key', r['guest']['ds_key'], 'raster', r['guest'].get('raster'))
# stencil writers before the boxes: ref values and ops
sw = {}
for x in draw:
    if x['op'] >= box[0]['op']:
        break
    s = x['guest']['stencil']
    if s['test']:
        sw.setdefault((s['ref'], s['func'], s['mask']), []).append(x['op'])
print('stencil use before boxes', {k: (len(v), v[0]) for k, v in sorted(sw.items())})
print('stencil_back of last opaque', draw[900]['guest'].get('stencil_back'), draw[900]['guest']['stencil'], draw[900]['guest']['ds_key'])
