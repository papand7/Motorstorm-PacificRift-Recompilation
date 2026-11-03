"""T185: per-phase ranking from analyze_t185.py output. ms/frame = fn samples in phase / phase samples x phase ms
(phase ms from arm_s_t183.py). py -3 phase_rank_t185.py analyze_q1.txt phases_q1.txt"""
import re, sys, collections
a, p = open(sys.argv[1]).read(), open(sys.argv[2]).read()
tot = {k: int(v) for k, v in re.findall(r'(\w+)=(\d+) \([\d.]+%\)', a.split('by phase:')[1].split('\n')[0])}
ms = {k: float(v) for k, v in re.findall(r'^\s+(\w+)\s+mean\s+([\d.]+)', p, re.M)}
ms['post'] = ms['after']; ms['pre'] = ms['before']; ms['emit'] = ms['emit'] + ms['gap']
rows = collections.defaultdict(dict)
for m in re.finditer(r'^\s+\d+\s+[\d.]+%\s+\d+\s+(\S+)\s+(\S*)$', a, re.M):
    for ph, c in re.findall(r'(\w+):(\d+)', m[2]): rows[ph][m[1]] = int(c)
for ph in ('havok', 'post', 'emit', 'spin'):
    t = tot.get(ph, 0); cov = sum(rows[ph].values())
    print(f'{ph}: {t} samples = {ms[ph]:.2f} ms/frame; ranked rows cover {cov / max(1, t) * 100:.0f}%')
    for fn, c in sorted(rows[ph].items(), key=lambda x: -x[1])[:12]:
        print(f'   {fn:16s} {c:6d}  {c / t * 100:5.1f}%  {c / t * ms[ph]:5.2f} ms/frame')
