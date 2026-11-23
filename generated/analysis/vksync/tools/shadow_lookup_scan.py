r"""For an RSX_SHADOW_CAP file: in each frame's shadow-reading draw (kind 1), find vertex-constant vec4s
that are a combination of ONE axis row of a cascade's world-to-clip matrix (kind 0, c0-c3 columns) plus
its translation row: s * row_axis + t * (0,0,0,1)-row. Such slots are the scene's lookup of that cascade.
usage: py -3 shadow_lookup_scan.py <capture.bin>"""
import sys, collections, math
sys.path.insert(0, __import__('os').path.dirname(__file__))
from shadow_cap import records, vec4s

def mat_rows(c, k=0):
    R = c[k:k + 4]                      # columns -> rows
    return [tuple(R[j][i] for j in range(4)) for i in range(4)]

def fit(v, a, b):
    # least squares v = s*a + t*b
    aa = sum(x * x for x in a); bb = sum(x * x for x in b); ab = sum(x * y for x, y in zip(a, b))
    va = sum(x * y for x, y in zip(v, a)); vb = sum(x * y for x, y in zip(v, b))
    det = aa * bb - ab * ab
    if abs(det) < 1e-20: return None
    s = (va * bb - vb * ab) / det; t = (vb * aa - va * ab) / det
    r = math.sqrt(sum((x - s * p - t * q) ** 2 for x, p, q in zip(v, a, b)))
    n = math.sqrt(sum(x * x for x in v)) or 1
    return s, t, r / n

recs = list(records(sys.argv[1]))
byf = collections.defaultdict(list)
for r in recs: byf[r['frame']].append(r)
hits = collections.Counter()
shown = 0
for f in sorted(byf):
    k0 = [r for r in byf[f] if r['kind'] == 0]; k1 = [r for r in byf[f] if r['kind'] == 1]
    if not k0 or not k1: continue
    sc = vec4s(k1[0]['consts'])
    for ci, r0 in enumerate(k0):
        M = mat_rows(vec4s(r0['consts']))
        for axis in range(3):
            for slot in range(min(len(sc), 512)):
                v = sc[slot]
                if max(abs(x) for x in v) < 1e-9: continue
                q = fit(v, M[axis], M[3])
                if q and q[2] < 1e-4 and abs(q[0]) > 1e-6:
                    hits[(ci, r0['sh'], r0['sv'], axis, slot)] += 1
                    if shown < 12:
                        shown += 1
                        print(f'frame {f} cascade {ci} (scissor {r0["sh"]:08x}/{r0["sv"]:08x}) axis {axis} -> scene c{slot}: s={q[0]:.6g} t={q[1]:.6g}')
print('\ncounts (cascade idx, sh, sv, axis, slot): frames')
for k, n in sorted(hits.items(), key=lambda x: -x[1])[:40]: print(k, n)
print('frames with both kinds:', sum(1 for f in byf if any(r['kind']==0 for r in byf[f]) and any(r['kind']==1 for r in byf[f])))
