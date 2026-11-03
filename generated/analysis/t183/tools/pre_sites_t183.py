"""T183: split the PRE phase on guest tid 1 using the trace sites still under their line limit, from T182 run logs. No game launch.
4AACA0, 5F74B0, 7284A0 and 4B63F0 have low trace limits, so this covers only the race frames reached before each limit; it says so per site.
Also lists the top-level order of site spans in one mid-window frame, and the render-thread CPU budget."""
import bisect, collections, glob, json, os, re, statistics as S, sys
ROOT = os.environ.get('MS_GENERATED', 'generated')
RX = re.compile(r'\[PT\] t=(\d+) tid=(\d+) ev=(\w+) pc=[0-9A-F]+.*?fn=([0-9A-F]+)')
SITES = ('004AACA0', '005F74B0', '0030B710', '007284A0', '00222368', '00736770', '004B63F0')
for tag in sys.argv[1:] or ('Rr1', 'Bb1', 'Dd1'):
    d = glob.glob(os.path.join(ROOT, 'runs', f'*t182-{tag}'))[-1]
    ev = []
    for l in open(os.path.join(d, 'stderr.log'), encoding='utf-8', errors='replace'):
        if l.startswith('[PT] t='):
            m = RX.match(l)
            if m and m[2] == '1':
                ev.append((int(m[1]), m[3], m[4]))
    op, by = collections.defaultdict(list), collections.defaultdict(list)
    for t, k, fn in ev:
        if k == 'enter':
            op[fn].append(t)
        elif op[fn]:
            by[fn].append((op[fn].pop(), t))
    for k in by:
        by[k].sort()
    tmax = ev[-1][0]
    ent = [a for a, b in by['0072E1E0']]
    def within(fn, a, b):
        L = by[fn]; i = bisect.bisect_left(L, (a, 0)); o = []
        while i < len(L) and L[i][0] < b:
            o.append(L[i]); i += 1
        return o
    print(f'\n== {tag} end {tmax/1e6:.1f}s frames={len(ent)}')
    for s in SITES:
        if by[s]:
            print(f'  {s}: spans={len(by[s])} last_start={by[s][-1][0]/1e6:.1f}s ({(tmax-by[s][-1][0])/1e6:.1f}s before end)')
    # Frames with PRE >= 25 ms: race frames, up to the last 4AACA0 span.
    rows = collections.defaultdict(list)
    lim = min(by['004AACA0'][-1][0], by['005F74B0'][-1][0])
    sample = None
    for a, b in zip(ent, ent[1:]):
        if b > lim:
            break
        ref, pb = within('0072E1E0', a, b), within('0050D868', a, b)
        if not ref or not pb:
            continue
        rx = ref[0][1]; pre = pb[0][0] - rx
        if pre < 25000:
            continue
        rows['pre'].append(pre); rows['T'].append(b - a)
        spans = []
        for s in SITES:
            w = within(s, rx, pb[0][0])
            tot, end = 0, -1
            for x, y in sorted(w):
                if y > end:
                    tot += y - max(x, end); end = y
            rows[s].append(tot); rows['n' + s].append(len(w)); spans += [(x, y, s) for x, y in w]
        sample = (rx, pb[0][0], sorted(spans))
    print(f"  race frames before the limit: {len(rows['pre'])}")
    if rows['pre']:
        print(f"  T mean {S.mean(rows['T'])/1e3:.2f} pre mean {S.mean(rows['pre'])/1e3:.2f}")
        for s in SITES:
            print(f"   {s}: mean {S.mean(rows[s])/1e3:6.2f} ms calls {S.mean(rows['n'+s]):5.1f}")
    if sample:
        rx, e, sp = sample
        print('  sample PRE', round((e - rx) / 1e3, 2), 'ms:', [(round((x - rx) / 1e3, 2), round((y - x) / 1e3, 2), s[2:]) for x, y, s in sp][:30])
