"""T183 arm S: place Havok task creation ([taskset] built / [spu_workload] dispatch lines) in the guest frame phases of tid 1
by stderr order between [PT] markers. Steady race window (last 55 s). No game launch."""
import collections, glob, os, re, statistics as S
ROOT = os.environ.get('MS_GENERATED', 'generated')
RUN = sorted(glob.glob(os.path.join(ROOT, 'runs', '*t183-Ss1')))[-1]
PT = re.compile(r'\[PT\] t=(\d+) tid=1 ev=(\w+) .*?fn=([0-9A-F]+)')
IMG = re.compile(r'image=(\d+)')
frames, cur, ph = [], None, None
for l in open(os.path.join(RUN, 'stderr.log'), encoding='utf-8', errors='replace'):
    if l.startswith('[PT]'):
        m = PT.match(l)
        if not m:
            continue
        t, k, fn = int(m[1]), m[2], m[3]
        if fn == '0072E1E0' and k == 'enter':
            if cur: cur['end'] = t; frames.append(cur)
            cur = {'start': t, 'n': collections.Counter()}; ph = 'before'
        elif cur is None: continue
        elif fn == '0030B710': ph = 'havok' if k == 'enter' else 'after'
        elif fn == '0050D868' and ph == 'after': ph = 'emit'
        elif fn == '0050C818': ph = 'spin' if k == 'enter' else 'tail'
    elif cur is not None and (l.startswith('[taskset] built') or 'dispatch HIT' in l):
        m = IMG.search(l)
        cur['n'][(ph, 'built' if l.startswith('[taskset]') else 'dispatch', m[1] if m else '?')] += 1
tmax = frames[-1]['end']
rows = [f for f in frames if f['start'] >= tmax - 55e6]
tot = collections.Counter()
for f in rows: tot.update(f['n'])
print(f'{len(rows)} frames; per-frame counts by (phase, kind, image):')
for k, v in sorted(tot.items(), key=lambda x: -x[1]):
    print(f'  {k[0]:7s} {k[1]:8s} img {k[2]:10s} {v / len(rows):6.2f}')
