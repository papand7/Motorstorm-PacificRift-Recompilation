"""T178: CPU-seconds per host thread and async SPU task busy spans over load phases of a critical-path trace (kind 32 = run-time us, kind 34 = task span).
usage: py -3 load_cpu_t178.py <cpath.txt> name:lo:hi ..."""
import sys
from collections import defaultdict
names, cpu, spu = {}, [], []
for l in open(sys.argv[1], encoding='utf-8', errors='replace'):
    p = l.split()
    if not p: continue
    if p[0] == 'H': names[int(p[1])] = ' '.join(p[5:])
    elif p[0] == '32': cpu.append((int(p[1]), int(p[2], 16), float(p[4]) / 1e6, float(p[5]) / 1e6))
    elif p[0] == '34': spu.append((float(p[4]) / 1e6, float(p[5]) / 1e6, p))
print('kind 34 sample', spu[len(spu)//2][2][:8] if spu else None, 'n', len(spu))
for ph in sys.argv[2:]:
    n, lo, hi = ph.split(':'); lo, hi = float(lo), float(hi)
    per = defaultdict(float)
    for slot, a, t0, t1 in cpu:
        ov = min(t1, hi) - max(t0, lo)
        if ov > 0 and t1 > t0: per[slot] += a / 1e6 * ov / (t1 - t0)
    sp = [(a, b) for a, b, _ in spu if b > lo and a < hi]
    busy = sum(min(b, hi) - max(a, lo) for a, b in sp)
    print(f'{n} [{lo}-{hi}] {hi-lo:.1f}s total_cpu {sum(per.values()):.2f}s; spu-task spans {len(sp)} busy {busy:.2f}s; ' + ', '.join(f'{names.get(s, s)} {v:.2f}' for s, v in sorted(per.items(), key=lambda kv: -kv[1])[:9]))
