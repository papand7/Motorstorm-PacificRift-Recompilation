"""T183: main-thread (guest tid 1) frame phases from the [PT] lines already in the T182 run logs. No game launch.
Frame = 72E1E0 entry to the next. ref = 72E1E0 duration. pre = ref exit -> first 50D868. emit = first -> last 50D868.
gap = last 50D868 -> 50C818 entry. spin = 50C818 duration. rest = spin exit -> next frame.
Nested spans inside pre: top-level durations of the in-frame wait sites, unioned so nested calls are not double counted."""
import glob, os, re, statistics as S, sys, collections
ROOT = os.environ.get('MS_GENERATED', 'generated')
RX = re.compile(r'\[PT\] t=(\d+) tid=(\d+) ev=(\w+) pc=[0-9A-F]+.*?fn=([0-9A-F]+)')
WAITS = ('004AACA0', '005F74B0', '0030B710', '007284A0', '00222368', '00536A30', '00736770', '004B63F0')
SPAWN = 'dispatch HIT (async)'
ENDED = 'HOST_RUN_ENDED'

def spans(ev):
    """(fn, start, end) for matched enter/exit on tid 1, innermost pairing per fn."""
    open_, out = collections.defaultdict(list), []
    for t, kind, fn in ev:
        if kind == 'enter':
            open_[fn].append(t)
        elif open_[fn]:
            out.append((fn, open_[fn].pop(), t))
    return out

def union(iv):
    tot, end = 0, -1
    for a, b in sorted(iv):
        if b > end:
            tot += b - max(a, end)
            end = b
    return tot

for tag in sys.argv[1:] or ('Rr1', 'Bb1', 'Dd1'):
    d = glob.glob(os.path.join(ROOT, 'runs', f'*t182-{tag}'))[-1]
    ev, other, marks = [], collections.Counter(), []
    tlast = 0
    for l in open(os.path.join(d, 'stderr.log'), encoding='utf-8', errors='replace'):
        if l.startswith('[PT] t='):
            m = RX.match(l)
            if m:
                tlast = int(m[1])
                if m[2] == '1':
                    ev.append((tlast, m[3], m[4]))
                else:
                    other[m[2]] += 1
        elif SPAWN in l:
            marks.append((tlast, 'spawn'))
        elif ENDED in l:
            marks.append((tlast, 'end'))
    tmax = ev[-1][0]
    t0, t1 = tmax - 55e6, tmax - 1e6
    sp = spans(ev)
    ent = sorted(a for fn, a, b in sp if fn == '0072E1E0' and t0 <= a <= t1)
    by = collections.defaultdict(list)
    for fn, a, b in sp:
        by[fn].append((a, b))
    for k in by:
        by[k].sort()
    rows = []
    import bisect
    def within(fn, a, b):
        L = by[fn]
        i = bisect.bisect_left(L, (a, 0))
        o = []
        while i < len(L) and L[i][0] < b:
            o.append(L[i])
            i += 1
        return o
    for a, b in zip(ent, ent[1:]):
        ref = within('0072E1E0', a, b)
        pb = within('0050D868', a, b)
        spin = within('0050C818', a, b)
        if not ref or not pb or not spin:
            continue
        rx = ref[0][1]
        r = dict(T=b - a, ref=ref[0][1] - ref[0][0], pre=pb[0][0] - rx, emit=pb[-1][0] - pb[0][0], gap=spin[0][0] - pb[-1][0],
                 spin=spin[0][1] - spin[0][0], rest=b - spin[0][1], pbs=len(pb), pb_us=union(pb))
        for w in WAITS:
            s = within(w, rx, pb[0][0])
            r['pre_' + w] = union(s)
            r['n_' + w] = len(s)
            e = within(w, pb[0][0], spin[0][0])
            r['emit_' + w] = union(e)
        rows.append(r)
    print(f'\n== {tag} frames={len(rows)} trace_end_s={tmax/1e6:.1f} span lines other tids={dict(other)}')
    for k in ('T', 'ref', 'pre', 'emit', 'gap', 'spin', 'rest', 'pb_us'):
        v = [x[k] for x in rows]
        print(f'  {k:6s} mean={S.mean(v)/1e3:7.2f} p50={S.median(v)/1e3:7.2f} p95={sorted(v)[int(len(v)*.95)]/1e3:7.2f}')
    print('  executepushbuffer calls/frame', round(S.mean(x['pbs'] for x in rows), 1))
    for w in WAITS:
        pre = [x['pre_' + w] for x in rows]
        em = [x['emit_' + w] for x in rows]
        print(f"  {w}: pre mean={S.mean(pre)/1e3:6.2f} calls={S.mean(x['n_'+w] for x in rows):5.1f} | emit mean={S.mean(em)/1e3:6.2f} last-span-end ok" if sum(pre) + sum(em) else f'  {w}: none in window')
    print('  spawn lines in window', sum(1 for t, k in marks if k == 'spawn' and t0 <= t <= t1), 'per frame %.1f' % (sum(1 for t, k in marks if k == 'spawn' and t0 <= t <= t1) / max(1, len(rows))))
