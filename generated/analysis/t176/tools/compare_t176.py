"""T176: compare polygon-offset arms A and B from their runtime and run directories.
usage: py -3 compare_t176.py <rtA> <runA> <rtB> <runB>"""
import collections, glob, json, re, statistics, sys
from pathlib import Path


def perf(run):
    ms, up, dc, race = [], [], [], False
    for l in open(Path(run) / 'stderr.log', encoding='utf-8', errors='replace'):
        m = re.match(r'\[rsx-frame-perf\] gframe=(\d+).*wall_ms=([\d.]+).*records=(\d+) draw_calls=(\d+) verts=(\d+) upload_mb=([\d.]+)', l)
        if m and int(m[3]) > 200:
            ms.append(float(m[2])); dc.append(int(m[4])); up.append(float(m[6]))
    q = sorted(ms)
    return dict(frames=len(ms), wall_sum_s=round(sum(ms) / 1000, 1), median_ms=statistics.median(ms), p95_ms=q[int(.95 * len(q))], max_ms=q[-1],
                median_draw_calls=statistics.median(dc), median_upload_mb=statistics.median(up))


def log(run):
    t = open(Path(run) / 'stderr.log', encoding='utf-8', errors='replace').read()
    return dict(poly=sorted(set(re.findall(r'\[rsx-poly-offset\].*', t))), watchdog=t.count('frame clock no progress'),
                psofail=len(re.findall(r'compile FAIL|PSO.*(?:fail|FAIL)', t)), removed=len(re.findall(r'DEVICE_REMOVED|DeviceRemoved', t)),
                indirect=t.count('unresolved indirect call'), eff=re.search(r'\[visual\] effective.*', t)[0])


def rsxi(rt):
    out = {}
    for f in glob.glob(str(Path(rt) / 'rsxi/frames/*/events.jsonl')):
        c = collections.Counter()
        for l in open(f, encoding='utf-8', errors='replace'):
            try: e = json.loads(l)
            except ValueError: continue
            if e.get('e') != 'draw': continue
            g = e['guest']; p = g['raster']['poly_offset']
            c[(g['rt'], g['rt_fmt'], p['fill'], p['scale'], p['bias'])] += 1
        out[Path(f).parent.name] = dict(c)
    return out


def dbg(rt):
    d = json.load(open(Path(rt) / 'd3d12_messages.json'))
    return [(m['severity'], m['id'], m['n'], m['sample'][:90]) for m in d['messages']]


for name, rt, run in (('A', sys.argv[1], sys.argv[2]), ('B', sys.argv[3], sys.argv[4])):
    print('==', name, Path(run).name)
    for k, v in {**perf(run), **log(run)}.items(): print(' ', k, v)
    print('  rsxi', rsxi(rt))
    print('  dbg', dbg(rt))
    print('  ctl', [l.strip()[:110] for l in open(Path(rt) / 'controller.log', errors='replace') if re.search(r'race_entry|vel_capture| stop ', l)])
