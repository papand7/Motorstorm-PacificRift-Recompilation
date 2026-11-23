"""Static vs dynamic caster draws in an RSX_FOLDUMP file (56-B records): for the shadow atlas (zeta 0x0B030000), per
draw key (pipeline, attribute-0 address, draw size): frames present, whether its constants above c7 (cbh) and its
vertex stream hash (vbh) ever change. usage: py -3 caster_classes.py foldump.bin"""
import struct, sys, collections
R = struct.Struct('<4I4Q')
b = open(sys.argv[1], 'rb').read()
keys = collections.defaultdict(lambda: {'frames': set(), 'cbh': set(), 'vbh': set(), 'pipe': 0, 'n': 0})
frames = set(); per_frame = collections.Counter()
for o in range(0, len(b) - R.size + 1, R.size):
    f, z, p, n, k, c, cam, v = R.unpack_from(b, o)
    if z != 0x0B030000: continue
    frames.add(f); per_frame[f] += 1
    d = keys[k]; d['frames'].add(f); d['cbh'].add(c); d['vbh'].add(v); d['pipe'] = p; d['n'] = n
nf = len(frames)
print(f'{nf} frames with casters, {sum(per_frame.values())/max(nf,1):.0f} caster draws/frame, {len(keys)} distinct keys')
cls = collections.Counter(); draws = collections.Counter()
for k, d in keys.items():
    fr = len(d['frames'])
    c = 'static' if len(d['cbh']) == 1 and len(d['vbh']) == 1 else ('const-change' if len(d['cbh']) > 1 else 'vb-change')
    if fr < 3: c += ' (<3 frames)'
    cls[c] += 1; draws[c] += fr
for c in sorted(cls): print(f'  {c:28s} keys {cls[c]:6d}  draws {draws[c]:8d} ({100*draws[c]/max(sum(draws.values()),1):.1f}%)')
pc = collections.defaultdict(lambda: collections.Counter())
for k, d in keys.items():
    pc[d['pipe']]['static' if len(d['cbh']) == 1 and len(d['vbh']) == 1 else 'dyn'] += len(d['frames'])
print('pipelines (draws static / dynamic):')
for p, c in sorted(pc.items(), key=lambda kv: -sum(kv[1].values()))[:20]: print(f'  pipe {p:6d}: static {c["static"]:7d} dynamic {c["dyn"]:7d}')
