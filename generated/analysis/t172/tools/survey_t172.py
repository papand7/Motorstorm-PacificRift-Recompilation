"""T172: for each capture: depth switch, box ops, snapshots around them, diff images. Run from t169/tools (PIL). usage: py -3 survey_t172.py"""
import glob, json, re
from pathlib import Path
import numpy as np
from PIL import Image

A = Path('../../').resolve()
OUT = A / 't172' / 'img'
for pat in ('t171/ab/runtime-TA-*', 't169/ab/runtime-D1-*', 't169/ab/runtime-D2-*', 't169/ab/runtime-F1-*', 't169/ab/runtime-F2-*', 't169/ab/runtime-VA-*', 't169/ab/runtime-VB-*', 't169/ab/runtime-VC-*', 't169/ab/runtime-VG-*', 't165/ab/runtime-B3-*'):
    for rt in A.glob(pat):
        argv = json.load(open(rt / 'runner_argv.json')) if (rt / 'runner_argv.json').exists() else []
        ds = [x for x in argv if x.startswith('RSX_DEPTH_STATE') or x.startswith('RSX_STENCIL') or x.startswith('RSX_ZETA')] if (rt / 'runner_argv.json').exists() else []
        if not (rt / 'rsxi' / 'frames').exists():
            print(rt.name, ds, 'no frames'); continue
        for d in sorted((rt / 'rsxi' / 'frames').iterdir()):
            f = glob.glob(str(d / 'events.jsonl*'))[0]
            rows = []
            for l in open(f, encoding='utf-8', errors='replace'):
                try:
                    if l.startswith('{'):
                        rows.append(json.loads(l))
                except ValueError:
                    pass
            ops = [r['op'] for r in rows if (r.get('guest') or {}).get('fp') == '0x022C20C1']
            snaps = sorted(p.name for p in d.glob('snap*_00750000.bmp'))
            print(rt.name, d.name, ds, 'rows', len(rows), 'box ops', (ops[0], ops[-1], len(ops)) if ops else None)
            if not ops:
                continue
            g = next(r['guest'] for r in rows if r.get('op') == ops[0] and r.get('guest'))
            print('   d', g['depth'], 's', g['stencil'], 'cull', g['cull'], 'bl', g['blend_key'], 'refs', [r['guest']['stencil']['ref'] for r in rows if r.get('op') in ops and r.get('guest')][:30])
            def op(n):
                return int(re.search(r'op(\d+)', n)[1])
            a = [n for n in snaps if op(n) < ops[0]]
            b = [n for n in snaps if op(n) >= ops[-1]]
            print('   before', a[-1:] , 'after', b[:1])
            if a and b:
                X = np.asarray(Image.open(d / a[-1]).convert('RGB'), np.int16)
                Y = np.asarray(Image.open(d / b[0]).convert('RGB'), np.int16)
                D = np.abs(Y - X).max(2)
                print('   changed', round(float((D > 3).mean()), 3))
                o = Image.new('RGB', (1280, 1448), (255, 0, 255))
                o.paste(Image.fromarray(np.uint8(Y)), (0, 0))
                o.paste(Image.fromarray(np.uint8(np.clip(D[..., None].repeat(3, 2) * 6, 0, 255))), (0, 728))
                o.save(OUT / f'box_{rt.name[8:10]}_{d.name}.png')
