"""T79: A1' race-window timeline from an armed ftrace (read-only).
Attributes PPU main-thread wait time (kinds 1/2, tid 1) to what the SPUs were doing at the same instant:
the WWS module(s) running (kind 26 spans named by kind 28), or nothing running.
Usage: py -3 -I t79_timeline.py <run dir> [--frames N]  (prints a summary and N sample frames)"""
import bisect, collections, json, re, statistics as st, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
RETAIL = HERE.parents[1] / 't37' / 'retail_jobs.json'
def fnv32(b):
    h = 0x811C9DC5
    for x in b: h = ((h ^ x) * 0x01000193) & 0xFFFFFFFF
    return h
NM = {fnv32(bytes.fromhex(m['sig16'])): m.get('name') or m['sha256'][:12] for m in json.load(open(RETAIL))}
rd = Path(sys.argv[1]); nf = int(sys.argv[sys.argv.index('--frames') + 1]) if '--frames' in sys.argv else 0
L = (rd / 'ftrace.txt').read_text().splitlines()
m = re.search(r'start_us=([\d.]+) end_us=([\d.]+)', L[0]); lo, hi = float(m.group(1)), float(m.group(2))
recs, jobs, last26 = [], [], None
for l in L[1:]:
    p = l.split()
    if p[0] == 'T': continue
    r = (int(p[0]), int(p[1]), int(p[2], 16), int(p[3], 16), float(p[4]), float(p[5]))
    if not lo <= r[4] < hi and r[0] != 26: continue
    if r[0] == 26:
        last26 = [r[4], r[5], r[3] >> 24, None]; jobs.append(last26)
    elif r[0] == 28 and last26 is not None and last26[3] is None:
        last26[3] = NM.get(r[2], f'{r[2]:08x}')
    recs.append(r)
jobs = [j for j in jobs if lo <= j[0] < hi]
flips = sorted(r[4] for r in recs if r[0] == 9)
waits = sorted((r[4], r[5], r[0], r[2], r[3]) for r in recs if r[1] == 1 and r[0] in (1, 2))
# elementary intervals: which job modules are running
ev = sorted([(a, 1, i) for i, (a, b, w, n) in enumerate(jobs)] + [(b, -1, i) for i, (a, b, w, n) in enumerate(jobs)])
times = [e[0] for e in ev]
def running_at(t0, t1):
    """time in [t0,t1) split by the set of running (wid, module)"""
    out = collections.Counter()
    k = bisect.bisect_left(times, t0)
    cur = set(i for i, (a, b, w, n) in enumerate(jobs[:0]))
    # active set at t0: jobs with a < t0 < b (linear scan over a local window is enough here)
    cur = set(i for i in range(max(0, idx_by_start(t0) - 64), idx_by_start(t0)) if jobs[i][0] <= t0 < jobs[i][1])
    t = t0
    while k < len(ev) and ev[k][0] < t1:
        out[frozenset((jobs[i][2], jobs[i][3]) for i in cur)] += ev[k][0] - t
        t = ev[k][0]
        (cur.add if ev[k][1] > 0 else cur.discard)(ev[k][2]); k += 1
    out[frozenset((jobs[i][2], jobs[i][3]) for i in cur)] += t1 - t
    return out
starts = [j[0] for j in jobs]
def idx_by_start(t): return bisect.bisect_right(starts, t)
nfr = len(flips) - 1
agg = collections.Counter(); bylr = collections.Counter()
for a, b, k, x, lr in waits:
    if b <= flips[0] or a >= flips[-1]: continue
    for s, d in running_at(a, b).items():
        key = 'SPU idle (no WWS job running)' if not s else ' + '.join(sorted(f'w{w}:{n}' for w, n in s))
        agg[key] += d; bylr[(lr, 'idle' if not s else 'busy')] += d
tot = sum(agg.values())
print(f'window {lo/1e6:.2f}-{hi/1e6:.2f} s, frames {nfr}, main wait {tot/1e3/nfr:.1f} ms/frame')
print('main-wait time by concurrent SPU activity (ms/frame, share):')
for k, v in agg.most_common(14): print(f'  {v/1e3/nfr:7.2f}  {v/tot:6.1%}  {k}')
print('by wait lr:')
for k, v in sorted(bylr.items(), key=lambda x: -x[1])[:8]: print(f'  {v/1e3/nfr:7.2f}  {hex(k[0])} {k[1]}')
# per-frame SPU busy (union of jobs) and serial job sum
fb, fs, fw = [], [], []
for f0, f1 in zip(flips, flips[1:]):
    occ = running_at(f0, f1)
    fb.append(sum(v for s, v in occ.items() if s) / 1e3)
    fw.append(sum(min(b, f1) - max(a, f0) for a, b, k, x, lr in waits if b > f0 and a < f1) / 1e3)
    fs.append((f1 - f0) / 1e3)
print(f'per frame median: frame {st.median(fs):.1f} ms, SPU busy (any job) {st.median(fb):.1f} ms, main wait {st.median(fw):.1f} ms')
mods = collections.defaultdict(float)
for a, b, w, n in jobs: mods[(w, n)] += b - a
print('job time per frame by module (ms):', ', '.join(f'w{w}:{n}={v/1e3/nfr:.1f}' for (w, n), v in sorted(mods.items(), key=lambda x: -x[1])[:10]))
for fi in range(min(nf, nfr)):
    f0, f1 = flips[100 + fi], flips[101 + fi]
    print(f'--- frame {100+fi}: {f0/1e3:.1f}..{f1/1e3:.1f} ms ({(f1-f0)/1e3:.1f} ms)')
    items = [(a, b, f'main wait lr={lr:x}') for a, b, k, x, lr in waits if b > f0 and a < f1]
    items += [(a, b, f'w{w} {n}') for a, b, w, n in jobs if b > f0 and a < f1]
    # compress consecutive same-label items
    out = []
    for a, b, lab in sorted(items):
        if out and out[-1][2] == lab and a - out[-1][1] < 500: out[-1][1] = b; out[-1][3] += 1
        else: out.append([a, b, lab, 1])
    for a, b, lab, c in out:
        print(f'   {(a-f0)/1e3:7.2f} {(b-f0)/1e3:7.2f} {lab} x{c}')
if '--flipgate' in sys.argv:
    for name in ('renderablejob', 'pvsjob', 'vehiclephysics'):
        ends = sorted(b for a, b, w, n in jobs if n == name)
        lag = []
        for f in flips[1:]:
            k = bisect.bisect_right(ends, f) - 1
            if k >= 0: lag.append((f - ends[k]) / 1e3)
        print(f'flip - last {name} end before it: median {st.median(lag):.2f} ms, p10 {sorted(lag)[len(lag)//10]:.2f}, p90 {sorted(lag)[9*len(lag)//10]:.2f}')
    # serial chain per frame: union busy of WWS jobs, and job-to-job gaps inside bursts
    gaps = []
    js = sorted(jobs)
    for (a0, b0, w0, n0), (a1, b1, w1, n1) in zip(js, js[1:]):
        if 0 <= a1 - b0 < 2000: gaps.append(a1 - b0)
    print(f'job-to-job gaps < 2 ms: n={len(gaps)} ({len(gaps)/nfr:.0f}/frame), median {st.median(gaps):.0f} us, sum {sum(gaps)/1e3/nfr:.1f} ms/frame')
if '--causal' in sys.argv:
    ep = sorted((a, b) for a, b, k, x, lr in waits if lr == 0x94cca8 and b - a > 5000)
    ends = sorted((b, w, n) for a, b, w, n in jobs); eb = [e[0] for e in ends]
    st_ = sorted((a, w, n) for a, b, w, n in jobs); sa = [s[0] for s in st_]
    lag, nxt, who = [], [], collections.Counter()
    for a, b in ep:
        k = bisect.bisect_right(eb, b) - 1
        if k < 0: continue
        lag.append(b - eb[k]); who[(ends[k][1], ends[k][2])] += 1
        w = ends[k][1]
        j = bisect.bisect_right(sa, b)
        while j < len(st_) and st_[j][1] != w: j += 1
        if j < len(st_): nxt.append(st_[j][0] - b)
    print(f'main 0x94cca8 waits > 5 ms: {len(ep)} ({len(ep)/nfr:.1f}/frame), total {sum(b-a for a,b in ep)/1e3/nfr:.1f} ms/frame')
    print(f'  wake - last job end: median {st.median(lag):.0f} us, p90 {sorted(lag)[9*len(lag)//10]:.0f} us')
    print(f'  last job before wake: {who.most_common(6)}')
    print(f'  next job of that workload after wake: median {st.median(nxt)/1e3:.2f} ms, p10 {sorted(nxt)[len(nxt)//10]/1e3:.2f} ms')
