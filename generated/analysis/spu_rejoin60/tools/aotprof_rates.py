"""Per-site rates of [spu-aot-prof] (PS3_SPU_AOT_PROF cumulative dumps) over a race window (private).
usage: py -3 aotprof_rates.py <stderr.log> <t0_ms> <t1_ms>
Each dump is timestamped by the last [rsx-hb] ms= line before it; deltas are taken between the first dump at or
after t0 and the last dump at or before t1. Frames from [rsx-hb] frames= over the same span."""
import re, sys
HB = re.compile(r'^\[rsx-hb\] ms=(\d+) frames=(\d+)')
HD = re.compile(r'^\[spu-aot-prof\] sites (\d+) dropped (\d+) \|(.*)$')
EN = re.compile(r'^\[spu-aot-prof\]\s+(\S+)\s+img=(-?\d+) pc=0x([0-9A-F]+) n=(\d+) steps=(\d+) us=(\d+)')
log, t0, t1 = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
dumps, cur, hb = [], None, (0, 0)
for l in open(log, errors='replace'):
    m = HB.match(l)
    if m: hb = (int(m.group(1)), int(m.group(2))); continue
    m = HD.match(l)
    if m:
        cur = dict(t=hb[0], fr=hb[1], tot=m.group(3), e={}); dumps.append(cur); continue
    m = EN.match(l)
    if m and cur is not None:
        cur['e'][(m.group(1), int(m.group(2)), int(m.group(3), 16))] = tuple(int(x) for x in m.groups()[3:])
a = next(d for d in dumps if d['t'] >= t0); b = [d for d in dumps if d['t'] <= t1][-1]
dt = (b['t'] - a['t']) / 1000.0; fr = b['fr'] - a['fr']
print(f'window {a["t"]}..{b["t"]} ms = {dt:.1f} s, {fr} frames ({fr/dt:.2f} fps)')
def tot(d):
    out = {}
    for r, n, s, u in re.findall(r' (\S+) n=(\d+) steps=(\d+) us=(\d+)', d['tot']): out[r] = (int(n), int(s), int(u))
    return out
ta, tb = tot(a), tot(b)
print('reason       n/s        n/frame   steps/s       us/s (host time in microstep+interp)')
for r in tb:
    dn, ds, du = (tb[r][i] - ta.get(r, (0, 0, 0))[i] for i in range(3))
    print(f'{r:12} {dn/dt:10.0f} {dn/fr:9.2f} {ds/dt:13.0f} {du/dt:10.0f}')
print('top sites (only sites listed in both dumps; the dump lists the top 24 by steps):')
rows = []
for k, v in b['e'].items():
    if k in a['e']:
        d = [v[i] - a['e'][k][i] for i in range(3)]
        rows.append((k, d))
rows.sort(key=lambda x: (-x[1][2], -x[1][0]))
print('reason      image        pc       n/frame   steps/n     us/s    ns/event')
for (r, img, pc), (dn, ds, du) in rows:
    print(f'{r:11} {img:11d} 0x{pc:05X} {dn/fr:9.2f} {ds/max(dn,1):9.1f} {du/dt:8.0f} {du*1000/max(dn,1):9.0f}')
