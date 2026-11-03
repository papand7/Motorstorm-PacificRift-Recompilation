"""T149: main-thread phases (t134/tools/phases_all.py definitions) for the T145 race runs (one-lane exe, 2026-10-28).
  py -3 phases_t145.py > phases_t145.txt"""
import statistics as S
from pathlib import Path
T = Path(__file__).resolve().parents[2] / 't134' / 'tools' / 'phases_all.py'
g = {'__file__': str(T)}
exec(T.read_text(encoding='utf-8').split('out = {}')[0], g)
for r in sorted((Path(__file__).resolve().parents[3] / 'runs').glob('*-t145-ab-*')):
    rows = g['phases'](r / 'stderr.log') if (r / 'stderr.log').exists() else None
    if not rows:
        print(f'{r.name}: no race frames'); continue
    m = {k: round(S.mean(x[k] for x in rows), 1) for k in ('T', 'ref', 'pre', 'emit', 'gap', 'spin')}
    print(f"{r.name} n={len(rows)} T={m['T']} p50={round(S.median(x['T'] for x in rows), 1)} ref={m['ref']} "
          f"pre={m['pre']} emit={m['emit']} gap={m['gap']} spin={m['spin']}")
