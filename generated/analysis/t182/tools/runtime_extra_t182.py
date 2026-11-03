"""T182 follow-up checks from existing run logs: frame quantization, worst frames, R vs B matching, frame phases. No game launch."""
import glob, os, re, statistics as st, collections
ROOT = os.path.join(os.environ.get('MS_GENERATED', 'generated'), 'runs')
PF = re.compile(rb'\[rsx-frame-perf\] gframe=(\d+) .*?wall_ms=([\d.]+).*?records=(\d+).*?upload_mb=([\d.]+).*?drain_ms=([\d.]+).*?expand_ms=([\d.]+).*?flush_ms=([\d.]+).*?miss=(\d+) miss_ms=([\d.]+).*?other_ms=([\d.]+)')
data = {}
for tag in ('Rr1', 'Bb1', 'Dd1'):
    d = glob.glob(os.path.join(ROOT, f'*t182-{tag}'))[-1]
    b = open(os.path.join(d, 'stderr.log'), 'rb').read()
    rows = [dict(g=int(m[1]), w=float(m[2]), r=int(m[3]), up=float(m[4]), dr=float(m[5]), e=float(m[6]), f=float(m[7]), miss=int(m[8]), mm=float(m[9]), o=float(m[10])) for m in PF.finditer(b)]
    race = [r for r in rows if r['r'] >= 1000]
    data[tag] = race[len(race) // 4:]
    print('==', tag, 'lines', len(rows), 'race', len(race))
    h = collections.Counter(int(r['w'] // 4) * 4 for r in data[tag])
    print(' wall hist 4ms:', {k: h[k] for k in sorted(h) if h[k] >= 5})
    print(' worst:', [(r['g'], round(r['w']), r['r'], r['miss'], round(r['mm'])) for r in sorted(race, key=lambda z: -z['w'])[:5]])
    print(' stall lines', b.count(b'[stall]'), 'first:', [l[:110] for l in b.splitlines() if l.startswith(b'[stall]')][:2])
    fp = [l for l in b.splitlines() if l.startswith(b'[frame-phase]')]
    print(' frame-phase lines', len(fp), [l[:230] for l in fp[-2:]])
    lr = [l for l in b.splitlines() if b'ev=exit' in l and b'fn=0008EA00' in l and b'dur_us' in l][:1]
    print(' loader dur_us', re.search(rb'dur_us=(\d+)', lr[0])[1] if lr else None)
for x, y in (('Rr1', 'Bb1'), ('Bb1', 'Dd1')):
    bins = collections.defaultdict(lambda: ([], []))
    for i, t in enumerate((x, y)):
        for r in data[t]:
            bins[r['r'] // 250][i].append(r)
    tot, acc = 0, collections.Counter()
    for a, c in bins.values():
        if len(a) >= 10 and len(c) >= 10:
            n = min(len(a), len(c)); tot += n
            for k in ('w', 'e', 'f', 'up', 'dr', 'o'):
                acc[k + '0'] += n * st.mean(r[k] for r in a); acc[k + '1'] += n * st.mean(r[k] for r in c)
    print(x, y, 'matched', tot, {k: (round(acc[k + '0'] / tot, 1), round(acc[k + '1'] / tot, 1)) for k in ('w', 'e', 'f', 'up', 'dr', 'o')})
