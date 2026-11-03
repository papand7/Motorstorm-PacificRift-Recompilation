#!/usr/bin/env python3
"""T190: compare the P/B race runs. Frame rows exactly as t183/tools/arm_s_t183.py (guest tid 1 [PT] frames,
72E1E0 entry to the next; last WIN s of the trace; complete phase order). Per run: frame stats and phases, plus
the [vm-gates] banner, serious-error and reservation-anomaly counts. Pairs: P1-B1, P2-B2, pooled P-B, P1-P2, B1-B2,
with a bootstrap 95 % CI of the mean difference. Also runs arm_s_t183.py per run (SPU task stats, waits, CPU) into logs/.
No game launch.   py -3 generated/analysis/t190/tools/analyze_t190.py [tags=Pp1,Bb1,Pp2,Bb2] [series=t190] [window_s=55]"""
import glob, json, os, random, re, statistics as S, subprocess, sys
ROOT = 'generated'
TAGS = (sys.argv[1] if len(sys.argv) > 1 else 'Pp1,Bb1,Pp2,Bb2').split(',')
SER = sys.argv[2] if len(sys.argv) > 2 else 't190'
WIN = float(sys.argv[3]) if len(sys.argv) > 3 else 55.0
OUT = os.path.join(ROOT, 'analysis', 't190', 'logs')
PT = re.compile(r'\[PT\] t=(\d+) tid=(\d+) ev=(\w+) .*?fn=([0-9A-F]+)')
SERIOUS = re.compile(r'Present\(\) Timeout|DXGI_ERROR_DEVICE|DeviceRemoved|DEVICE_REMOVED|device removed|resynchron|fifo.*(corrupt|resync)', re.I)
ANOM = re.compile(r'\[(ppu-steals-resv|spu-coh[^\]]*|resv[^\]]*)\]|reservation (lost|fail)|PUTLLC.*(timeout|stuck)|\bdeadlock|\bhang\b|\bhung\b', re.I)
KEYS = ('T', 'before', 'havok', 'after', 'emit', 'gap', 'spin')
def frames(run):
    fr, cur = [], None
    for l in open(os.path.join(run, 'stderr.log'), encoding='utf-8', errors='replace'):
        if not l.startswith('[PT]'): continue
        m = PT.match(l)
        if not m or m[2] != '1': continue
        t, k, fn = int(m[1]), m[3], m[4]
        if fn == '0072E1E0' and k == 'enter':
            if cur: cur['end'] = t; fr.append(cur)
            cur = {'start': t, 'pb0': None, 'pb1': None}
        elif not cur: continue
        elif fn == '0072E1E0' and k == 'exit': cur['refx'] = t
        elif fn == '0030B710': cur['h' + k] = t
        elif fn == '0050D868' and k == 'enter': cur['pb0'] = cur['pb0'] or t; cur['pb1'] = t
        elif fn == '0050C818': cur['s' + k] = t
    tmax = fr[-1]['end']; rows = []
    for f in fr:
        if f['start'] < tmax - WIN * 1e6 or not f['pb0']: continue
        if not all(k in f for k in ('refx', 'henter', 'hexit', 'senter', 'sexit')): continue
        if not (f['refx'] <= f['henter'] <= f['hexit'] <= f['pb0'] <= f['senter']): continue
        rows.append(dict(T=(f['end'] - f['start']) / 1e3, before=(f['henter'] - f['refx']) / 1e3, havok=(f['hexit'] - f['henter']) / 1e3,
                         after=(f['pb0'] - f['hexit']) / 1e3, emit=(f['pb1'] - f['pb0']) / 1e3, gap=(f['senter'] - f['pb1']) / 1e3,
                         spin=(f['sexit'] - f['senter']) / 1e3))
    return rows, len(fr), (tmax - fr[0]['start']) / 1e6
def pct(v, p): v = sorted(v); return v[min(len(v) - 1, int(p * len(v)))]
def boot(a, b, n=4000, seed=190):
    r = random.Random(seed); d = []
    for _ in range(n):
        d.append(S.mean(r.choices(b, k=len(b))) - S.mean(r.choices(a, k=len(a))))
    d.sort(); return d[int(.025 * n)], d[int(.975 * n)]
runs, data = {}, {}
for tag in TAGS:
    g = sorted(glob.glob(os.path.join(ROOT, 'runs', f'*{SER}-{tag}')))
    if not g: print(f'{tag}: no run'); continue
    run = g[-1]; runs[tag] = run
    rows, nall, span = frames(run)
    txt = open(os.path.join(run, 'stderr.log'), encoding='utf-8', errors='replace').read()
    so = os.path.join(run, 'stdout.log')
    txt_o = open(so, encoding='utf-8', errors='replace').read() if os.path.exists(so) else ''
    gates = [l for l in (txt + txt_o).splitlines() if l.startswith('[vm-gates]')]
    data[tag] = rows
    print(f'== {tag}: {os.path.basename(run)}  joined {len(rows)} of {nall} frames, trace span {span:.1f} s')
    print('   vm-gates:', gates or 'none')
    print('   serious-error lines:', len(SERIOUS.findall(txt + txt_o)), ' reservation-anomaly lines:', len(ANOM.findall(txt + txt_o)))
    if not rows: continue
    T = [r['T'] for r in rows]
    print(f'   frame ms mean {S.mean(T):.2f} median {S.median(T):.2f} p5 {pct(T, .05):.2f} p95 {pct(T, .95):.2f} p99 {pct(T, .99):.2f} '
          f'max {max(T):.2f} sd {S.pstdev(T):.2f} cv {S.pstdev(T) / S.mean(T) * 100:.1f}%  fps {1000 / S.mean(T):.2f}')
    print('   phases mean (median):', '  '.join(f'{k} {S.mean(r[k] for r in rows):.2f} ({S.median(r[k] for r in rows):.2f})' for k in KEYS[1:]))
    hist = [0] * 8
    for t in T: hist[min(7, max(0, int((t - 55) // 5)))] += 1
    print('   histogram (<60, 60-65, ... ,>=85 ms):', hist)
    env = dict(os.environ, T183_SERIES=SER, T183_TAG=tag, MS_GENERATED=ROOT)
    p = subprocess.run([sys.executable, os.path.join(ROOT, 'analysis/t183/tools/arm_s_t183.py'), str(int(WIN))], env=env, capture_output=True, text=True)
    open(os.path.join(OUT, f'arm_{tag}.txt'), 'w', encoding='utf-8').write(p.stdout + p.stderr)
def cmp(a, b, label):
    if not all(x in data and data[x] for x in a + b): print(f'{label}: missing'); return
    A = [r for x in a for r in data[x]]; B = [r for x in b for r in data[x]]
    print(f'-- {label}')
    for k in KEYS:
        va, vb = [r[k] for r in A], [r[k] for r in B]
        lo, hi = boot(va, vb)
        print(f'   {k:6s} {S.mean(va):7.2f} -> {S.mean(vb):7.2f} ms  d {S.mean(vb) - S.mean(va):+6.2f} ms ({(S.mean(vb) / S.mean(va) - 1) * 100:+5.1f}%)  '
              f'95% CI [{lo:+.2f}, {hi:+.2f}]  median d {S.median(vb) - S.median(va):+.2f}')
    print(f'   fps {1000 / S.mean(r["T"] for r in A):.2f} -> {1000 / S.mean(r["T"] for r in B):.2f}; '
          f'sd {S.pstdev(r["T"] for r in A):.2f} -> {S.pstdev(r["T"] for r in B):.2f}')
print()
cmp(['Pp1'], ['Bb1'], 'P1 -> B1'); cmp(['Pp2'], ['Bb2'], 'P2 -> B2'); cmp(['Pp1', 'Pp2'], ['Bb1', 'Bb2'], 'pooled P -> B')
cmp(['Pp1'], ['Pp2'], 'drift P1 -> P2'); cmp(['Bb1'], ['Bb2'], 'repeat B1 -> B2')
