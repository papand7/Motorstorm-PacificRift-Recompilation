"""T170: heavy-frame stage medians per run, with each run's RSX flags. Natural experiment over existing logs."""
import sys, json, pathlib, re, statistics as st
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import importlib
def parse(run):
    NUM = re.compile(r'([a-z_]+)=(-?[0-9.]+)')
    fr = {}
    for l in open(run / 'stderr.log', errors='replace'):
        if l.startswith('[rsx-frame-perf] gframe='):
            d = {}
            for k, v in NUM.findall(l.replace('[tex ', 'tex_ms=').replace('| pso ', 'pso_ms=').replace('| cmd ', 'cmd_ms=').replace(' n=', ' tn=', 1)):
                d.setdefault(k, float(v))
            fr.setdefault(int(d['gframe']), []).append(d)
    return fr
K = 'wall_ms records verts upload_mb expand_ms tex_ms pso_ms cmd_ms wait_ms'.split()
base = None
for a in sys.argv[1:]:
    run = pathlib.Path(a)
    if not (run / 'manifest.json').exists(): continue
    m = json.load(open(run / 'manifest.json'))
    env = {k: v for k, v in m.get('env', {}).items() if k.startswith(('RSX_', 'RSXI')) and not any(x in k for x in ('DIR', 'GO', 'WATCH', 'LOG', 'HEARTBEAT', 'FRAME_PERF', 'TRIGGER', 'RTS'))}
    fr = parse(run)
    rows = []
    for g, ps in fr.items():
        r = {k: sum(p.get(k, 0) for p in ps) for k in K}
        rows.append(r)
    out = run.name + ' ' + m['exe_sha256'][:8]
    for name, lo, hi in (('L', 1500, 3000), ('H', 5000, 10**9)):
        s = [r for r in rows if lo <= r['records'] < hi and r['wall_ms'] > 0]
        if s:
            out += f" | {name} n={len(s)} " + ' '.join(f"{k.split('_')[0]}={st.median(x[k] for x in s):.1f}" for k in K if k not in ('verts',))
    print(out)
    print('    ', ' '.join(f'{k[4:] if k.startswith("RSX_") else k}={v}' for k, v in sorted(env.items())))
