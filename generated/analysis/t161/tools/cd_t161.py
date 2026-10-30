"""T161 final: C1/D1/C2/D2 summary from existing logs (no new instrumentation).
Per run: race entry (startup_timeline_t161.py), light and heavy windows (bench_t161.py) with the heavy window
matched to the race frames every run reached, process CPU (performance.json), [lwc-wake] totals, FIFO resyncs,
error lines, and the [lwc-wake-fb] fallback rows.
  py -3 cd_t161.py <ab dir> C1 D1 C2 D2 [--json out]"""
import json, re, subprocess, sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ab = Path(sys.argv[1])
tags = [a for a in sys.argv[2:] if not a.startswith('--') and not a.endswith('.json')]
out = sys.argv[sys.argv.index('--json') + 1] if '--json' in sys.argv else None
kv = re.compile(r'(\w+)=(-?[0-9.]+)')


def run_dir(tag):
    t = (ab / f'launch_{tag}.txt').read_text(encoding='utf-8', errors='replace')
    return Path(re.search(r'run_dir=(\S+)', t).group(1)), Path(re.search(r'RTDIR (\S+)', t).group(1))


def py(*a):
    return json.loads(subprocess.run([sys.executable, *map(str, a)], capture_output=True, text=True, check=True).stdout)


info = {}
for tag in tags:
    rd, rt = run_dir(tag)
    first = py(HERE / 'bench_t161.py', rd)
    info[tag] = dict(rd=rd, rt=rt, race_frames=first['race_frames'])
hi = min(v['race_frames'] for v in info.values()) - 1
res = {'heavy_window': [600, hi], 'runs': {}}
for tag in tags:
    rd, rt = info[tag]['rd'], info[tag]['rt']
    b = py(HERE / 'bench_t161.py', rd, '--heavy-lo', 600, '--heavy-hi', hi)
    tl = py(HERE / 'startup_timeline_t161.py', rd, rt)
    perf = json.loads((rd / 'performance.json').read_text(encoding='utf-8'))
    wake, fb_site, fb_reason, errs, resync = Counter(), Counter(), Counter(), Counter(), 0
    for l in open(rd / 'stderr.log', encoding='utf-8', errors='replace'):
        if l.startswith('[lwc-wake] window_ms='):
            for k, v in kv.findall(l):
                if k != 'window_ms':
                    wake[k] += float(v)
        elif l.startswith('[lwc-wake-fb]'):
            d = dict(re.findall(r'(\w+)=(\S+)', l))
            if 'dropped' in d:
                fb_reason['dropped'] += int(d['dropped'])
                continue
            fb_site[(d['tid'], d['cv'], d['lr'], d['site'])] += int(d['n'])
            fb_reason['nosig'] += int(d['nosig'])
            fb_reason['sig_other'] += int(d['sig_other'])
        elif 'FIFO resync' in l:
            resync += 1
        elif re.search(r'\b(FATAL|CRASH|access violation|DEVICE_REMOVED|TDR)\b', l):
            errs[l[:60]] += 1
    res['runs'][tag] = dict(run=str(rd), race_frames=info[tag]['race_frames'], timeline=tl, bench=b,
                            perf_keys=sorted(perf)[:40], wake=dict(wake), fb_reason=dict(fb_reason),
                            fb_top=[[*k, n] for k, n in fb_site.most_common(12)], fifo_resync=resync,
                            errors=dict(errs))
s = json.dumps(res, indent=1, default=str)
if out:
    Path(out).write_text(s, encoding='utf-8')
print(s[:20000])
