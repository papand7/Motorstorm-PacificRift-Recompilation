import sys, collections, statistics as st
d = collections.defaultdict(list)
for l in open(sys.argv[1], errors='replace'):
    if l[0] in '#TH': continue
    p = l.split()
    if len(p) != 6: continue
    k = int(p[0]); d[(k, p[2])].append((float(p[5]) - float(p[4]), float(p[4]), p[1], p[3]))
for (k, h), v in sorted(d.items(), key=lambda x: -sum(a[0] for a in x[1])):
    if len(v) < 50: continue
    du = sorted(a[0] for a in v)
    print(f'kind {k} {h} n={len(v)} mean={st.mean(du):.0f}us p50={du[len(du)//2]:.0f} p90={du[int(len(du)*.9)]:.0f} p99={du[int(len(du)*.99)]:.0f} tot_ms={sum(du)/1e3:.0f}')
