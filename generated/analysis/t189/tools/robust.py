import json, statistics as S, sys
rows=[json.loads(l) for l in open(sys.argv[1]) if l.startswith('{')]
t=[r for r in rows if 'A' in r]
rob=[r for r in t if max(r['cv_'+v] for v in ('A','B','C','C2','D'))<=0.05]
print(f'timed {len(t)} robust {len(rob)} mismatches {sum(not r["same"] for r in rows)}')
for name, sel in (('all', t), ('robust', rob)):
    if not sel: continue
    g={v: S.geometric_mean([r['A']/r[v] for r in sel]) for v in ('B','C','C2','D')}
    db=S.geometric_mean([r['B']/r['D'] for r in sel])
    lo={v: min(r['A']/r[v] for r in sel) for v in ('B','C','C2','D')}; hi={v: max(r['A']/r[v] for r in sel) for v in ('B','C','C2','D')}
    print(name, ' '.join(f'{v}/A={g[v]:.3f}[{lo[v]:.2f},{hi[v]:.2f}]' for v in g), f'D/B={db:.3f}')
