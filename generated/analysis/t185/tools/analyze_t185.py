"""T185: read one T185 run (arm Q, N or L) -- task-creation stages, GETLLAR spin episodes and phase-tagged PPU samples
over the steady race window, next to the frame phases (tools/arm_s_t183.py does those; run it with T183_GLOB).
  py -3 generated/analysis/t185/tools/analyze_t185.py <tag, e.g. Qq1> [window_s=55]
No game launch. Race window = the last <window_s> s of the run's [PT] trace."""
import collections, glob, os, re, statistics as S, sys
ROOT = os.environ.get('MS_GENERATED', 'generated')
TAG = sys.argv[1] if len(sys.argv) > 1 else 'Qq1'
WIN = float(sys.argv[2]) if len(sys.argv) > 2 else 55.0
SER = os.environ.get('T185_SERIES', 't185')
RUN = sorted(glob.glob(os.path.join(ROOT, 'runs', f'*{SER}-{TAG}')))[-1]
KV = re.compile(r' (\w+)=([\w.]+)')
PT = re.compile(r'\[PT\] t=(\d+) tid=1 ev=enter .*?fn=0072E1E0')
frames, prof, llar, samp_blocks, cur = [], collections.defaultdict(list), [], [], None
for l in open(os.path.join(RUN, 'stderr.log'), encoding='utf-8', errors='replace'):
    if l.startswith('[PT]'):
        m = PT.match(l)
        if m: frames.append(int(m[1]))
        if cur is not None: cur['t_pt'] = frames[-1] if frames else 0
    elif l.startswith('[spu-create-prof] who='):
        d = dict(KV.findall(l)); d['_t'] = frames[-1] if frames else 0; prof[d['who']].append(d)
    elif l.startswith('[spu-llar-prof] seq='):
        d = dict(KV.findall(l)); llar.append(d)
    elif l.startswith('[samp] --- '):
        cur = {'head': l.strip(), 'rows': [], 'phase': {}, 't_pt': frames[-1] if frames else 0}; samp_blocks.append(cur)
    elif l.startswith('[samp]') and cur is not None:
        m = re.match(r'\[samp\]\s+([\d.]+)%\s+(func_|spu_LS_)([0-9A-F]{8})\s+\((\d+)\)(?:\s+ph=(\S+))?', l)
        if m:
            ph = dict((p.split(':')[0], int(p.split(':')[1])) for p in (m[5] or '').split(',') if ':' in p)
            cur['rows'].append((m[2] + m[3], int(m[4]), ph))
        elif l.startswith('[samp] phase '):
            cur['phase'] = {k: int(v) for k, v in re.findall(r'(\w+)=(\d+)', l[13:])}
if not frames:
    raise SystemExit('no [PT] frame markers')
t1 = frames[-1]; t0 = t1 - WIN * 1e6
nfr = sum(1 for t in frames if t >= t0); ft = WIN * 1000.0 / max(1, nfr)
print(f'run {os.path.basename(RUN)}: {nfr} frames in the last {WIN:.0f} s, {ft:.2f} ms/frame (frame-marker count)')
for who, rows in prof.items():
    rows = [r for r in rows if r['_t'] >= t0]
    if not rows: continue
    calls = sum(int(r['calls']) for r in rows)
    keys = [k for k in rows[0] if k not in ('who', 'seq', 'window_ms', 'calls', '_t')]
    mean = {k: sum(float(r[k]) * int(r['calls']) for r in rows) / calls for k in keys}
    per_frame = calls / nfr
    print(f'[{who}] {calls} calls ({per_frame:.1f}/frame); per call (us), call-weighted over {len(rows)} windows:')
    print('   ' + '  '.join(f'{k}={mean[k]:.1f}' for k in keys))
    stages = [k for k in keys if k not in ('mean_us', 'p50_us', 'p95_us', 'max_us', 'lockwait', 'lockwait_n')]
    print('   ms/frame: ' + '  '.join(f'{k}={mean[k] * per_frame / 1000:.2f}' for k in stages + ['mean_us', 'lockwait']))
# GETLLAR: cumulative per (img, line); delta over the window from the seq nearest t0 (by t_ms the profile keeps).
if llar:
    tmax = max(int(d['t_ms']) for d in llar)
    by = collections.defaultdict(list)
    for d in llar: by[(d['img'], d['line'])].append(d)
    print(f'[llar] delta over the last {WIN:.0f} s of the profile clock (top lines by unchanged GETLLARs):')
    out = []
    for k, v in by.items():
        v.sort(key=lambda d: int(d['seq']))
        a = next((d for d in v if int(d['t_ms']) >= tmax - WIN * 1000), v[0]); b = v[-1]
        dd = {f: float(b[f]) - float(a[f]) for f in ('getllar', 'unchanged', 'putllc', 'episodes', 'spin_iters', 'spin_ms')}
        out.append((dd['unchanged'], k, dd, b['max_iters']))
    for u, k, dd, mx in sorted(out, reverse=True)[:12]:
        print(f'   img={k[0]} line={k[1]} getllar/frame={dd["getllar"] / nfr:.0f} unchanged={dd["unchanged"] / max(1, dd["getllar"]) * 100:.0f}% '
              f'episodes/frame={dd["episodes"] / nfr:.1f} spin_ms/frame={dd["spin_ms"] / nfr:.2f} putllc/frame={dd["putllc"] / nfr:.1f} max_iters={mx}')
# Samples: sum the report blocks inside the window (PS3_SAMPLE_TOP resets each block).
blk = [b for b in samp_blocks if b['t_pt'] >= t0]
if blk:
    tot, ph_tot = collections.Counter(), collections.Counter()
    ph_fn = collections.defaultdict(collections.Counter)
    for b in blk:
        ph_tot.update(b['phase'])
        for fn, n, ph in b['rows']:
            tot[fn] += n
            for p, c in ph.items(): ph_fn[fn][p] += c
    allg = sum(ph_tot.values()) or sum(tot.values())
    print(f'[samp] {len(blk)} reports in the window; tid-1 guest samples {allg}; by phase: ' +
          ', '.join(f'{p}={c} ({c / max(1, allg) * 100:.1f}%)' for p, c in ph_tot.most_common()))
    print('   rank  share  samples  function          phase split (samples)')
    for i, (fn, n) in enumerate(tot.most_common(40), 1):
        print(f'   {i:4d} {n / max(1, allg) * 100:5.1f}% {n:8d}  {fn:16s}  ' + ','.join(f'{p}:{c}' for p, c in ph_fn[fn].most_common()))
    print('   Only the ranked rows of each report are kept; shares are of all tid-1 guest samples in the window.')
