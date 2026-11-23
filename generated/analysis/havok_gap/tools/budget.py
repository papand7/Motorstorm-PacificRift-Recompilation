"""Per-run time budget of Havok images in race windows (cumulative [spu-task-stats] deltas).
usage: py -3 budget.py <tag> [...]   window = race_entry+10s .. last stats (as ab_metrics.py)"""
import json, re, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[4]
AB2 = ROOT / 'generated/analysis/vksync/ab2'
HB = re.compile(r'\[rsx-hb\] ms=(\d+) frames=(\d+)')
TS = re.compile(r'\[spu-task-stats\] seq=(\d+) t_ms=(\d+) img=(\d+) (.*)')
IMGS = {'491898574': 'HK2 collide', '341580667': 'HK1 solve', '308733018': 'HKc?', '406081863': 'HKd?'}
F = ['runs','run_ns','fn_ns','get','put','list','getllar','putllc','putllc_fail','tagupd','mfc_ns','cpu_cyc','fn_tsc']
def parse(kv):
    d = {}
    for k, v in re.findall(r'(\w+)=([\d/]+)', kv):
        if '/' in v: a, b = v.split('/'); d[k] = int(a); d[k+'_b'] = int(b)
        else: d[k] = int(v)
    return d
def one(tag):
    cands = sorted(AB2.glob(f'runtime-{tag}-*'))
    entry = None
    if cands:
        for l in (cands[-1] / 'timeline.jsonl').read_text(errors='replace').splitlines():
            if '"race_entry"' in l: entry = json.loads(l).get('hb_ms'); break
    run = sorted((ROOT / 'generated/runs').glob(f'*-vk-K{tag}'))[-1]
    start = (entry or 0) + 10000
    on = False; a = {}; b = {}; hbs = []
    for l in (run / 'stderr.log').open(errors='replace'):
        m = HB.search(l)
        if m:
            if int(m.group(1)) >= start: on = True; hbs.append((int(m.group(1)), int(m.group(2))))
            continue
        if not on: continue
        m = TS.match(l)
        if m and m.group(3) in IMGS:
            d = parse(m.group(4)); a.setdefault(m.group(3), d); b[m.group(3)] = d
    fps = (hbs[-1][1]-hbs[0][1])*1000.0/(hbs[-1][0]-hbs[0][0]) if len(hbs) > 1 else 0
    print(f'== {tag} fps {fps:.1f}')
    for img, d1 in b.items():
        d0 = a[img]; n = d1['runs'] - d0['runs']
        if n <= 0: continue
        g = lambda k: (d1.get(k,0) - d0.get(k,0))
        cpu_ns = g('cpu_cyc') / (g('fn_tsc')/g('fn_ns'))   # cycle counter at TSC rate -> convert via fn ratio
        print(f' {IMGS[img]:12} n={n:6d} fn={g("fn_ns")/n/1e6:.3f}ms (cpu {g("cpu_cyc")/g("fn_tsc")*100:.1f}%) mfc={g("mfc_ns")/n/1e6:.3f}ms '
              f'rt-nonmfc={(g("fn_ns")-g("mfc_ns"))/n/1e6:.3f}ms get={g("get")/n:.0f} put={g("put")/n:.0f} llar={g("getllar")/n:.0f} '
              f'llc={g("putllc")/n:.0f} llcfail={g("putllc_fail")/n:.1f} tagupd={g("tagupd")/n:.0f} list={g("list")/n:.0f} '
              f'getB={g("get_b")/n:.0f} putB={g("put_b")/n:.0f} mfc_ns/req={g("mfc_ns")/max(1,(g("get")+g("put")+g("getllar")+g("putllc")+g("tagupd"))):.0f}ns '
              f'run-fn={(g("run_ns")-g("fn_ns"))/n/1e3:.0f}us tsc/ns={g("fn_tsc")/g("fn_ns"):.2f}')
for t in sys.argv[1:]: one(t)
