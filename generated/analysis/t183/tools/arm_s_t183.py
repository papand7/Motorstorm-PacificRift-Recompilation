"""T183 arm S: guest frame phases, SPU task stats deltas, SPURS/syscall/HLE waits and thread CPU over the steady race window.
Reads the one arm S run (generated/runs/*t183-Ss1, generated/analysis/t183/ab/runtime-s1-*). No game launch.
  py -3 generated/analysis/t183/tools/arm_s_t183.py [window_s=55]"""
import collections, glob, json, os, re, statistics as S, sys
ROOT = os.environ.get('MS_GENERATED', 'generated')
WIN = float(sys.argv[1]) if len(sys.argv) > 1 else 55.0
TAG = os.environ.get('T183_TAG', 'Ss1')   # T184: Pp1 = arm P (task pool)
RUN = sorted(glob.glob(os.path.join(ROOT, 'runs', f'*t183-{TAG}')))[-1]
RTD = sorted(glob.glob(os.path.join(ROOT, 'analysis', 't183', 'ab', f'runtime-{TAG[1:]}-*')))[-1]
PT = re.compile(r'\[PT\] t=(\d+) tid=(\d+) ev=(\w+) .*?fn=([0-9A-F]+).*?(?:dur_us=(\d+))?.*? n=(\d+)')
KV = re.compile(r'(\w+)=([\d./]+)')
HAVOK = {'341580667': 'w1 solver', '491898574': 'w2 collide', '308733018': 'w3 raycast', '406081863': 'w4 animation'}
INNER = ('004AACA0', '005F74B0', '00222368')
frames, cur, perf = [], None, []
stats = collections.defaultdict(list)          # img -> [(t_ms, dict)]
busy, scw, hlw = [], [], []
for l in open(os.path.join(RUN, 'stderr.log'), encoding='utf-8', errors='replace'):
    if l.startswith('[PT]'):
        m = PT.match(l)
        if not m or m[2] != '1':
            continue
        t, k, fn = int(m[1]), m[3], m[4]
        if fn == '0072E1E0' and k == 'enter':
            if cur:
                cur['end'] = t; frames.append(cur)
            cur = {'start': t, 'pb0': None, 'pb1': None, 'inner': collections.defaultdict(list)}
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
        elif fn in INNER:
            cur['inner'][fn].append((k, t, int(m[6])))
    elif l.startswith('[rsx-frame-perf]') and cur is not None:
        cur.setdefault('perf', {k: v for k, v in KV.findall(l)})
    elif l.startswith('[spu-task-stats]') and 'img=' in l:
        d = dict(KV.findall(l)); stats[d['img']].append((int(d['t_ms']), d))
    elif l.startswith('[spurs-busy]'):
        busy.append(dict(KV.findall(l)))
    elif l.startswith('[sc-wait]'):
        scw.append(l.strip())
    elif l.startswith('[hle-wait]'):
        hlw.append(l.strip())
tmax = frames[-1]['end']
rows = []
for f in frames:
    if f['start'] < tmax - WIN * 1e6 or not f['pb0']:
        continue
    if not all(k in f for k in ('refx', 'henter', 'hexit', 'senter', 'sexit')):
        continue
    if not (f['refx'] <= f['henter'] <= f['hexit'] <= f['pb0'] <= f['senter']):
        continue
    r = dict(T=(f['end'] - f['start']) / 1e3, ref=(f['refx'] - f['start']) / 1e3, before=(f['henter'] - f['refx']) / 1e3,
             havok=(f['hexit'] - f['henter']) / 1e3, after=(f['pb0'] - f['hexit']) / 1e3, emit=(f['pb1'] - f['pb0']) / 1e3,
             gap=(f['senter'] - f['pb1']) / 1e3, spin=(f['sexit'] - f['senter']) / 1e3, f=f)
    rows.append(r)
print(f'run {os.path.basename(RUN)}; window last {WIN:.0f} s; joined race frames {len(rows)} of {len(frames)}')
T = [r['T'] for r in rows]
def pct(v, p):
    v = sorted(v); return v[min(len(v) - 1, int(p * len(v)))]
print(f'frame ms mean {S.mean(T):.2f} median {S.median(T):.2f} p95 {pct(T, .95):.2f} p99 {pct(T, .99):.2f}; fps {1000 / S.mean(T):.2f}; sd {S.pstdev(T):.2f}, se {S.pstdev(T) / len(T) ** .5:.3f}')
for k in ('ref', 'before', 'havok', 'after', 'emit', 'gap', 'spin'):
    v = [r[k] for r in rows]
    print(f'  {k:7s} mean {S.mean(v):6.2f} median {S.median(v):6.2f} sd {S.pstdev(v):5.2f}')
# Traced sites inside the post-Havok window (only while their span limit lasted: consecutive n).
print('inner sites per frame (frames where the site still logged every call):')
for fn in INNER:
    cnt, dur_in, cover = [], [], 0
    for r in rows:
        ev = r['f']['inner'].get(fn, [])
        en = [t for k, t, n in ev if k == 'enter']
        ex = [(t, n) for k, t, n in ev if k == 'exit']
        if not en:
            continue
        ns = [n for k, t, n in ev if k == 'enter']
        if ns[-1] - ns[0] + 1 != len(ns):
            continue
        cover += 1
        f = r['f']
        aft = sum(1 for t in en if f['hexit'] <= t < f['pb0'])
        cnt.append((len(en), aft, sum(1 for t in en if t < f['henter'])))
        dur_in.append(sum((tx - te) for te, (tx, _) in zip(en, ex)) / 1e3)
    if cover:
        print(f'  {fn}: frames {cover}; calls/frame {S.mean(c[0] for c in cnt):.1f} (before Havok {S.mean(c[2] for c in cnt):.1f}, '
              f'in post-Havok window {S.mean(c[1] for c in cnt):.1f}); inclusive ms/frame {S.mean(dur_in):.2f}')
    else:
        print(f'  {fn}: no race frame with a complete span list (limit exhausted)')
# SPU task stats: delta across the window.
t0 = stats[next(iter(HAVOK))][-1][0] - WIN * 1000
nfr = len(rows) and (WIN * 1000 / S.mean(T))
print(f'spu-task-stats delta over the window (~{nfr:.0f} frames at the mean frame time):')
NUMK = ('runs', 'run_ns', 'fn_ns', 'mfc_ns', 'cpu_cyc', 'fn_tsc', 'getllar', 'putllc', 'putllc_fail', 'tagupd', 'list')
tot = collections.Counter()
for img, seq in sorted(stats.items()):
    a = next((d for t, d in seq if t >= t0), None); b = seq[-1][1]
    if not a or a is b:
        continue
    dt_ms = int(b['t_ms']) - int(a['t_ms'])
    fr = dt_ms / S.mean(T)
    d = {k: float(b[k]) - float(a[k]) for k in NUMK}
    for k in ('get', 'put'):
        d[k + '_n'] = float(b[k].split('/')[0]) - float(a[k].split('/')[0])
        d[k + '_b'] = float(b[k].split('/')[1]) - float(a[k].split('/')[1])
    if not d['runs'] and not d['fn_ns']:
        continue
    oncpu = d['cpu_cyc'] / d['fn_tsc'] if d['fn_tsc'] else 0
    fn_ms = d['fn_ns'] / 1e6
    name = HAVOK.get(img, '')
    if name:
        for k in ('runs', 'fn_ns', 'run_ns', 'mfc_ns'):
            tot[k] += d[k]
        tot['on'] += fn_ms * oncpu
    print(f'  img {img} {name:12s} runs/frame {d["runs"] / fr:6.2f}  fn ms/frame {fn_ms / fr:7.2f}  per run {fn_ms / max(1, d["runs"]):6.3f} ms  '
          f'on-CPU {oncpu * 100:5.1f}%  pickup (run-fn) {(d["run_ns"] - d["fn_ns"]) / 1e6 / max(1, d["runs"]) * 1e3:6.1f} us/run  '
          f'mfc {d["mfc_ns"] / max(1, d["fn_ns"]) * 100:4.1f}% of fn  getllar/run {d["getllar"] / max(1, d["runs"]):7.0f}  '
          f'putllc/run {d["putllc"] / max(1, d["runs"]):5.0f} fail {d["putllc_fail"] / max(1, d["putllc"]) * 100:4.1f}%  '
          f'get/run {d["get_n"] / max(1, d["runs"]):6.0f} ({d["get_b"] / max(1, d["get_n"]):.0f} B)  window {dt_ms} ms')
fr = WIN * 1000 / S.mean(T)
print(f'  Havok 4 images: runs/frame {tot["runs"] / fr:.2f}, task fn ms/frame {tot["fn_ns"] / 1e6 / fr:.2f} '
      f'(on-CPU {tot["on"] / fr:.2f}), mfc ms/frame {tot["mfc_ns"] / 1e6 / fr:.2f}, pickup ms/frame {(tot["run_ns"] - tot["fn_ns"]) / 1e6 / fr:.2f}')
# SPURS kernel lanes: busy per window, last 50 windows.
lanes = collections.defaultdict(list)
for d in busy[-400:]:
    lanes[(d.get('sn'), d.get('wid'))].append(d)
print('spurs-busy (mean over the last windows, per 1000 ms):')
for k, v in sorted(lanes.items()):
    print(f'  sn={k[0]} wid={k[1]} runs {S.mean(float(x["runs"]) for x in v):6.0f} polled {S.mean(float(x["polled"]) for x in v):6.0f} '
          f'busy_ms {S.mean(float(x["busy_ms"]) for x in v):6.1f}  (n={len(v)})')
print('sc-wait last window per tid:')
last = {}
for l in scw:
    m_ = re.search(r'tid=(\d+)', l)
    if m_:
        last[m_[1]] = l
for k in sorted(last, key=int):
    print('  ' + last[k][:220])
print('hle-wait last window per tid:')
last = {}
for l in hlw:
    m_ = re.search(r'tid=(\d+)', l)
    if m_:
        last[m_[1]] = l
for k in sorted(last, key=int):
    print('  ' + last[k][:220])
cpu = [json.loads(l) for l in open(os.path.join(RTD, 'cpu.jsonl'), encoding='utf-8')]
a, b = cpu[-16], cpu[-2]
dt = b['t'] - a['t']
tops = sorted(((b['threads'][k] - a['threads'].get(k, 0)) / dt, k) for k in b['threads'])[::-1]
print('host thread CPU, ms per frame (top 10):', [(k, round(x * S.mean(T), 1)) for x, k in tops[:10]])
print('  live threads sum', round(sum(x for x, _ in tops) * S.mean(T), 1), 'ms/frame;',
      'process', round((b.get('proc_cpu', 0) - a.get('proc_cpu', 0)) / dt * S.mean(T), 1) if 'proc_cpu' in b else '', 'keys', list(b)[:8])
# T184: host thread churn (distinct thread ids seen in the cpu.jsonl samples of the window) and memory.
win = [c for c in cpu if c['t'] >= cpu[-2]['t'] - WIN]
seen = set().union(*(c['threads'] for c in win))
allseen = set().union(*(c['threads'] for c in cpu))
print(f'host threads: {len(seen)} distinct ids in the window samples ({len(win)} samples, {win[-1]["t"] - win[0]["t"]:.0f} s); '
      f'{len(cpu[-2]["threads"])} live at the last sample; {len(allseen)} distinct over the run; '
      f'new ids per sample in the window {S.mean(len(set(b["threads"]) - set(a["threads"])) for a, b in zip(win, win[1:])):.1f}')
ws = [float(l.split('","')[-1].strip().strip('"').replace(' K', '').replace('.', '').replace(',', '')) / 1024
      for l in open(os.path.join(RTD, 'mem.csv'), encoding='utf-8', errors='replace') if l.strip()]
print(f'working set (mem.csv): peak {max(ws):.0f} MB, last {ws[-1]:.0f} MB, samples {len(ws)}')
db, di = win[-1]['sys_busy'] - win[0]['sys_busy'], win[-1]['sys_idle'] - win[0]['sys_idle']
print(f'system CPU busy over the window: {db / (db + di) * 100:.1f}% of all logical CPUs')
