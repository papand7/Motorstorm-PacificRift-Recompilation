"""T182 R/B/D statistics from existing run logs. No game launch."""
import csv, glob, json, os, re, statistics as st, collections
ROOT = os.environ.get('MS_GENERATED', 'generated')
ARMS = {'R': ('Rr1', 'r1'), 'B': ('Bb1', 'b1'), 'D': ('Dd1', 'd1')}
NUM = {k: re.compile(k.encode() + rb'=([\d.]+)') for k in (
    'gframe', 'wall_ms', 'records', 'draw_calls', 'verts', 'upload_mb', 'drain_ms', 'draw_cb_ms', 'expand_ms', 'flush_ms',
    'rf_ms', 'record_ms', 'submit_ms', 'wait_ms', 'present_ms', 'other_ms')}
PERF = re.compile(rb'\[rsx-frame-perf\] .*')
TEX = re.compile(rb'\[tex ([\d.]+) n=(\d+) \| pso ([\d.]+) n=(\d+) miss=(\d+) miss_ms=([\d.]+) \| cmd ([\d.]+)\]')
VS = re.compile(rb'vs=(\d+)/(\d+) miss_ms=([\d.]+)')
IX = re.compile(rb'\[vp-indexed\] draws=(\d+) corners=(\d+) verts=(\d+) fallback=(\d+)')

def pct(v, p):
    v = sorted(v)
    return v[min(len(v) - 1, int(len(v) * p))]

def load(tag):
    d = glob.glob(os.path.join(ROOT, 'runs', f'*t182-{tag}'))[-1]
    b = open(os.path.join(d, 'stderr.log'), 'rb').read()
    if b[:2] == b'\xff\xfe':
        b = b.decode('utf-16', 'ignore').encode()
    rows, t = [], 0.0
    for m in PERF.finditer(b):
        l = m[0]
        r = {k: float(x[1]) for k, x in ((k, p.search(l)) for k, p in NUM.items()) if x}
        x, v = TEX.search(l), VS.search(l)
        if 'wall_ms' not in r or not x or not v:
            continue
        r.update(tex=float(x[1]), pso=float(x[3]), pso_n=int(x[4]), pso_miss=int(x[5]), pso_miss_ms=float(x[6]), cmd=float(x[7]),
                 vs_miss=int(v[1]), vs_n=int(v[2]), vs_miss_ms=float(v[3]))
        rows.append(r)
    return d, b, rows

def summary(rows):
    w = [r['wall_ms'] for r in rows]
    s = {'n': len(rows), 'fps': 1000 / st.mean(w), 'mean': st.mean(w), 'p50': st.median(w), 'p95': pct(w, .95), 'p99': pct(w, .99), 'max': max(w)}
    for k in ('records', 'draw_calls', 'verts', 'upload_mb', 'drain_ms', 'expand_ms', 'flush_ms', 'record_ms', 'tex', 'pso', 'cmd', 'rf_ms', 'submit_ms', 'wait_ms', 'present_ms', 'other_ms'):
        s[k] = st.median(r.get(k, 0) for r in rows)
    return s

def show(name, s):
    print(f"{name}: n={s['n']} fps={s['fps']:.2f} mean={s['mean']:.1f} p50={s['p50']:.1f} p95={s['p95']:.1f} p99={s['p99']:.1f} max={s['max']:.0f} | rec={s['records']:.0f} draws={s['draw_calls']:.0f} verts={s['verts']:.0f} up={s['upload_mb']:.1f} | drain={s['drain_ms']:.1f} expand={s['expand_ms']:.1f} flush={s['flush_ms']:.1f} rf={s['rf_ms']:.1f} record={s['record_ms']:.1f} tex={s['tex']:.1f} pso={s['pso']:.1f} cmd={s['cmd']:.1f} submit={s['submit_ms']:.1f} wait={s['wait_ms']:.1f} present={s['present_ms']:.1f} other={s['other_ms']:.1f}")

def steady(rows):
    """Race frames after 20 s of race frames, with no shader miss in the frame or the 5 before."""
    race, t = [], 0.0
    first = next(i for i, r in enumerate(rows) if r['records'] >= 1000)
    last_miss = -99
    for i, r in enumerate(rows[first:]):
        t += r['wall_ms']
        if r['pso_miss'] or r['vs_miss'] or r['pso_miss_ms'] or r['vs_miss_ms']:
            last_miss = i
        r['t'] = t / 1000
        r['clean'] = i - last_miss > 5
        race.append(r)
    return race, [r for r in race if r['records'] >= 1000 and r['t'] >= 20 and r['clean']]

data = {}
for arm, (tag, rt) in ARMS.items():
    d, b, rows = load(tag)
    race, st_rows = steady(rows)
    data[arm] = st_rows
    print(f'\n=== {arm} {os.path.basename(d)} perf_lines={len(rows)} race_span_s={race[-1]["t"]:.1f}')
    show('race(rec>=1000)', summary([r for r in rows if r['records'] >= 1000]))
    show('steady', summary(st_rows))
    print('all-run shader: pso_miss', sum(r['pso_miss'] for r in rows), 'pso_miss_ms %.0f' % sum(r['pso_miss_ms'] for r in rows), 'vs_miss', sum(r['vs_miss'] for r in rows), 'vs_miss_ms %.0f' % sum(r['vs_miss_ms'] for r in rows), 'pso_lookups', sum(r['pso_n'] for r in rows))
    rr = [r for r in rows if r['records'] >= 1000]
    print('race shader: pso_miss', sum(r['pso_miss'] for r in rr), 'pso_miss_ms %.0f' % sum(r['pso_miss_ms'] for r in rr), 'vs_miss', sum(r['vs_miss'] for r in rr), 'vs_miss_ms %.0f' % sum(r['vs_miss_ms'] for r in rr), 'frames_with_miss', sum(1 for r in rr if r['pso_miss'] or r['vs_miss']))
    for lo in range(0, 80, 15):
        seg = [r for r in race if lo <= r['t'] < lo + 15 and r['records'] >= 1000]
        if seg:
            s = summary(seg)
            print(f"  t{lo:>2}-{lo+15}: n={s['n']} fps={s['fps']:.1f} p50={s['p50']:.1f} rec={s['records']:.0f} verts={s['verts']:.0f} up={s['upload_mb']:.1f} expand={s['expand_ms']:.1f} other={s['other_ms']:.1f}")
    ix = IX.findall(b)
    if ix:
        a, c = ix[0], ix[-1]
        print('vp-indexed last', c[0].decode(), 'reuse %.3f' % (int(c[1]) / int(c[2])), 'fallback', c[3].decode(), '(cumulative; first line reuse %.3f)' % (int(a[1]) / int(a[2])))
        if len(ix) > 2:
            m = ix[len(ix) // 2]
            print('  second half reuse %.3f' % ((int(c[1]) - int(m[1])) / max(1, int(c[2]) - int(m[2]))))
    print('[vp-direct]', b.count(b'[vp-direct] on'), '[vp-indexed] on', b.count(b'[vp-indexed] on'))
    for k in (b'unresolved indirect', b'Present() Timeout', b'DEVICE_REMOVED', b'DEVICE_HUNG', b'E_INVALIDARG', b'PSO create', b'CreateGraphicsPipeline'):
        n = b.count(k)
        if n:
            print('  COUNT', k.decode(), n)
    rtd = glob.glob(os.path.join(ROOT, 'analysis', 't182', 'ab', f'runtime-{rt}-*'))[-1]
    ctl = open(os.path.join(rtd, 'controller.log'), encoding='utf-8', errors='replace').read().splitlines()
    for l in ctl:
        if re.search(r'\] (intro_skip|race_entry|stop)\b', l) or 'cross 4' in l or ('race_loader_ret' in l):
            print(' ', re.sub(r'(dur_us=\d+).*', r'\1', l)[:150])
    cpu = [json.loads(l) for l in open(os.path.join(rtd, 'cpu.jsonl'), encoding='utf-8')]
    ent = next(float(l[1:9]) for l in ctl if '] race_entry' in l)
    t0 = cpu[0]['t']
    def cores(a, b_):
        if b_['t'] <= a['t']:
            return 0
        return sum(max(0, v - a['threads'].get(k, 0)) for k, v in b_['threads'].items()) / (b_['t'] - a['t'])
    rc = [x for x in cpu if x['t'] - t0 >= ent]
    lc = [x for x in cpu if x['t'] - t0 < ent]
    print('cpu cores load %.2f race %.2f' % (cores(lc[0], lc[-1]), cores(rc[0], rc[-1])), 'system busy race %.0f%%' % (100 * (rc[-1]['sys_busy'] - rc[0]['sys_busy']) / max(1e-6, rc[-1]['sys_busy'] - rc[0]['sys_busy'] + rc[-1]['sys_idle'] - rc[0]['sys_idle'])),
          'top thread race %.2f' % max(max(0, v - rc[0]['threads'].get(k, 0)) / (rc[-1]['t'] - rc[0]['t']) for k, v in rc[-1]['threads'].items()))
    g = list(csv.reader(open(os.path.join(rtd, 'gpu.csv'), encoding='utf-8')))
    print('gpu util', [x[2].strip() for x in g], 'vram', [x[3].strip() for x in g][-1], 'peak', max(int(x[3].split()[0]) for x in g))
    m = list(csv.reader(open(os.path.join(rtd, 'mem.csv'), encoding='utf-8')))
    print('mem csv peak KiB', max(int(re.sub(r'\D', '', x[4])) for x in m if len(x) > 4))
    print('frames dir', len(os.listdir(os.path.join(rtd, 'frames'))) if os.path.isdir(os.path.join(rtd, 'frames')) else None)
    perf = json.load(open(os.path.join(d, 'performance.json'), encoding='utf-8'))
    print('perf', {k: perf.get(k) for k in ('wall_s', 'cpu_s', 'avg_cores_busy', 'peak_working_set_mb', 'peak_private_mb')})
    cnt = collections.Counter(re.sub(rb'0x[0-9a-fA-F]+|\d+', b'#', l)[:70] for l in b.splitlines())
    data[arm + '_cls'] = cnt

# B vs D, record-matched steady frames: bins of 250 records, min 10 frames per arm.
print('\n=== B vs D matched by records bin')
bins = collections.defaultdict(lambda: {'B': [], 'D': []})
for a in 'BD':
    for r in data[a]:
        bins[int(r['records'] // 250)][a].append(r)
tot = wb = wd = 0
FIELDS = ('wall_ms', 'expand_ms', 'flush_ms', 'upload_mb', 'verts', 'records', 'other_ms', 'record_ms', 'drain_ms', 'cmd', 'tex', 'pso')
acc = {k: [0.0, 0.0] for k in FIELDS}
for k in sorted(bins):
    x, y = bins[k]['B'], bins[k]['D']
    if len(x) < 10 or len(y) < 10:
        continue
    n = min(len(x), len(y))
    tot += n
    print(f"  rec {k*250}-{k*250+250}: B n={len(x)} p50={st.median(r['wall_ms'] for r in x):.1f} exp={st.median(r['expand_ms'] for r in x):.1f} up={st.median(r['upload_mb'] for r in x):.1f} verts={st.median(r['verts'] for r in x):.0f} | D n={len(y)} p50={st.median(r['wall_ms'] for r in y):.1f} exp={st.median(r['expand_ms'] for r in y):.1f} up={st.median(r['upload_mb'] for r in y):.1f} verts={st.median(r['verts'] for r in y):.0f}")
    for f in FIELDS:
        acc[f][0] += n * st.mean(r.get(f, 0) for r in x)
        acc[f][1] += n * st.mean(r.get(f, 0) for r in y)
print('matched weight', tot, 'of B', len(data['B']), 'D', len(data['D']))
for f in FIELDS:
    print(f'  {f}: B {acc[f][0]/tot:.2f} D {acc[f][1]/tot:.2f} delta {100*(acc[f][1]/acc[f][0]-1):+.1f}%')
print('  matched fps: B %.2f D %.2f' % (1000 / (acc['wall_ms'][0] / tot), 1000 / (acc['wall_ms'][1] / tot)))

# Half-run stability: the same B-vs-D delta on the first and second half of each steady window.
for name, sl in (('first half', lambda v: v[:len(v)//2]), ('second half', lambda v: v[len(v)//2:])):
    x, y = sl(data['B']), sl(data['D'])
    print(f"{name}: B p50 {st.median(r['wall_ms'] for r in x):.1f} exp {st.median(r['expand_ms'] for r in x):.1f} | D p50 {st.median(r['wall_ms'] for r in y):.1f} exp {st.median(r['expand_ms'] for r in y):.1f}")

# Log line classes that appear in one arm of B/D only (candidate anomalies).
print('\n=== line classes, count >= 1, present in only one of B/D (top 25)')
b_, d_ = data['B_cls'], data['D_cls']
for k, n in sorted(((k, n) for k, n in (b_ + d_).items() if (k in b_) != (k in d_)), key=lambda z: -z[1])[:25]:
    print(' ', 'B' if k in b_ else 'D', n, k.decode('latin1'))
print('\n=== error-like classes per arm')
for k in sorted(set(data['R_cls']) | set(b_) | set(d_)):
    if re.search(rb'(?i)fail|error|invalid|unresolved|timeout|fatal|nosys|unimpl', k):
        print(' ', data['R_cls'].get(k, 0), b_.get(k, 0), d_.get(k, 0), k.decode('latin1'))
