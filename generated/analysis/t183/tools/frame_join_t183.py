"""T183: join each [rsx-frame-perf] line to the guest frame whose [PT] spans precede it in the same stderr, and rank what moves frame time.
Steady race window only: last 55 s of the trace, records >= 1000, no shader miss. Pearson r over frames, and the mean of each term.
Also the budget of the render thread against the thread CPU in runtime cpu.jsonl. No game launch."""
import glob, json, os, re, statistics as S, sys
ROOT = os.environ.get('MS_GENERATED', 'generated')
PT = re.compile(r'\[PT\] t=(\d+) tid=1 ev=(\w+) pc=[0-9A-F]+.*?fn=([0-9A-F]+)')
NUM = {k: re.compile(k + r'=([\d.]+)') for k in ('wall_ms', 'records', 'drain_ms', 'expand_ms', 'flush_ms', 'rf_ms', 'record_ms', 'other_ms', 'upload_mb')}
IN_DRAIN = re.compile(r'in_drain ([\d.]+)')
MISS = re.compile(r'vs=(\d+)/.* miss=(\d+) ')
def pearson(a, b):
    ma, mb = S.mean(a), S.mean(b)
    sa = sum((x - ma) ** 2 for x in a) ** .5; sb = sum((y - mb) ** 2 for y in b) ** .5
    return sum((x - ma) * (y - mb) for x, y in zip(a, b)) / (sa * sb) if sa and sb else 0
for tag, rt in (('Rr1', 'r1'), ('Bb1', 'b1'), ('Dd1', 'd1')):
    d = glob.glob(os.path.join(ROOT, 'runs', f'*t182-{tag}'))[-1]
    frames, cur, last = [], None, {}
    for l in open(os.path.join(d, 'stderr.log'), encoding='utf-8', errors='replace'):
        if l.startswith('[PT]'):
            m = PT.match(l)
            if not m:
                continue
            t, k, fn = int(m[1]), m[2], m[3]
            if fn == '0072E1E0' and k == 'enter':
                if cur:
                    cur['end'] = t
                    frames.append(cur)
                cur = {'start': t, 'pb0': None, 'pb1': None}
            elif not cur:
                continue
            elif fn == '0072E1E0' and k == 'exit':
                cur['refx'] = t
            elif fn == '0030B710':
                cur['h' + k] = t
            elif fn == '0050D868' and k == 'enter':
                cur['pb0'] = cur['pb0'] or t; cur['pb1'] = t
            elif fn == '0050C818':
                cur['s' + k] = t
        elif l.startswith('[rsx-frame-perf]') and cur:
            r = {k: float(p.search(l)[1]) for k, p in NUM.items() if p.search(l)}
            mi = MISS.search(l); r['miss'] = (int(mi[1]) + int(mi[2])) if mi else 1
            x = IN_DRAIN.search(l); r['in_drain'] = float(x[1]) if x else 0
            last = cur.setdefault('perf', r)
    if cur:
        pass
    tmax = frames[-1]['end']
    rows = []
    for f in frames:
        p = f.get('perf')
        if not p or f['start'] < tmax - 55e6 or p.get('records', 0) < 1000 or p['miss']:
            continue
        if not all(k in f for k in ('refx', 'henter', 'hexit', 'senter', 'sexit')) or not f['pb0']:
            continue
        if not (f['refx'] <= f['henter'] <= f['hexit'] <= f['pb0'] <= f['senter']):
            continue
        rows.append(dict(T=(f['end'] - f['start']) / 1e3, before=(f['henter'] - f['refx']) / 1e3, havok=(f['hexit'] - f['henter']) / 1e3,
                         after=(f['pb0'] - f['hexit']) / 1e3, emit=(f['pb1'] - f['pb0']) / 1e3, gap=(f['senter'] - f['pb1']) / 1e3,
                         spin=(f['sexit'] - f['senter']) / 1e3, ref=(f['refx'] - f['start']) / 1e3, wall=p['wall_ms'], drain=p['drain_ms'],
                         expand=p['expand_ms'], other=p['other_ms'], rf=p['rf_ms'], indr=p['in_drain'], up=p['upload_mb']))
    print(f'\n== {tag} joined frames {len(rows)}')
    T = [r['T'] for r in rows]
    for k in ('ref', 'before', 'havok', 'after', 'emit', 'gap', 'spin', 'expand', 'drain', 'other', 'up'):
        v = [r[k] for r in rows]
        print(f'  {k:7s} mean {S.mean(v):7.2f}  r(T)={pearson(v, T):+.2f}  sd {S.pstdev(v):5.2f}')
    print(f"  T mean {S.mean(T):.2f}; phases sum {S.mean(sum(r[k] for k in ('ref','before','havok','after','emit','gap','spin')) for r in rows):.2f}; wall mean {S.mean(r['wall'] for r in rows):.2f}")
    busy = [r['drain'] + max(0, r['rf'] - r['indr']) for r in rows]
    print(f'  render thread: drain + passes outside drain {S.mean(busy):.2f} ms, other {S.mean(r["other"] for r in rows):.2f}')
    rtd = glob.glob(os.path.join(ROOT, 'analysis', 't182', 'ab', f'runtime-{rt}-*'))[-1]
    cpu = [json.loads(l) for l in open(os.path.join(rtd, 'cpu.jsonl'), encoding='utf-8')]
    a, b = cpu[-16], cpu[-2]
    dt = b['t'] - a['t']
    top = sorted(((b['threads'][k] - a['threads'].get(k, 0)) / dt, k) for k in b['threads'])[::-1][:8]
    fr = S.mean(T)
    print('  host thread CPU, ms per frame:', [round(x * fr, 1) for x, _ in top], 'sum all live threads', round(sum((b['threads'][k] - a['threads'].get(k, 0)) / dt for k in b['threads']) * fr, 1))
