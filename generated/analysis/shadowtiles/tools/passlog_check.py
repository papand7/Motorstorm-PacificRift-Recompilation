r"""After an RSX_SHADOW_TILES run: checks the per-pass log (RSX_SHADOW_TILES_LOG csv) for camera independence of the
mapping. Window centre on the texel grid (multiples of 64 texels), anchor/depth anchor changes (should be rare: sun or
track change only), pure camera turns (same camera position, window unchanged), window moves vs camera translation.
usage: py -3 passlog_check.py passlog_st1.csv [texel=0.125]"""
import csv, sys, math
t = float(sys.argv[2]) if len(sys.argv) > 2 else 0.125
rows = list(csv.DictReader(open(sys.argv[1])))
if not rows: sys.exit('empty log')
step = 64 * t
off = sum(1 for r in rows for k in ('c1', 'c2') if abs(float(r[k]) / step - round(float(r[k]) / step)) > 1e-6)
anchors = sum(1 for a, b in zip(rows, rows[1:]) if (a['o1'], a['o2'], a['z0']) != (b['o1'], b['o2'], b['z0']))
sun = sum(1 for a, b in zip(rows, rows[1:]) if (a['dx'], a['dy'], a['dz']) != (b['dx'], b['dy'], b['dz']))
still = moved_still = 0; jumps = []
for a, b in zip(rows, rows[1:]):
    ca = [float(a[k]) for k in ('camx', 'camy', 'camz')]; cb = [float(b[k]) for k in ('camx', 'camy', 'camz')]
    dc = math.dist(ca, cb); dw = math.hypot(float(b['c1']) - float(a['c1']), float(b['c2']) - float(a['c2']))
    if dc < 1e-3:
        still += 1; moved_still += dw > 0
    jumps.append((dw, dc))
mx = max(jumps, key=lambda j: j[0]) if jumps else (0, 0)
print(f'{len(rows)} passes, window centre off the 64-texel grid: {off}, anchor changes {anchors}, sun changes {sun}')
print(f'passes with the camera still: {still}, window moved in {moved_still} of them (must be 0)')
print(f'largest window step {mx[0]:.1f} m (camera moved {mx[1]:.1f} m in that pass)')
