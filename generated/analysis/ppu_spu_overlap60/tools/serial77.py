"""Where the SPU-idle (serial) main compute sits: label each compute gap by the NEXT main wait (lr / sc)."""
import sys, collections, bisect
W, J, flips = [], [], []
for line in open(sys.argv[1], encoding="latin-1"):
    if not line[0].isdigit(): continue
    p = line.split()
    if len(p) < 6: continue
    k, who, a, b, t0, t1 = int(p[0]), p[1], p[2], p[3], float(p[4]), float(p[5])
    if k == 9: flips.append(t0)
    elif k == 2 and who == "1" and b in ("94cca8", "72e5c0", "a49ad4", "a48b4c", "a48364"): W.append((t0, t1, "usleep " + b))
    elif k == 1 and who == "1" and a == "82" and t1 - t0 >= 20: W.append((t0, t1, "sem " + b))
    elif k in (26, 39): J.append((t0, t1))
flips.sort(); W.sort(); J.sort()
M = []
for s, e in sorted((s, e) for s, e in J):
    if M and s <= M[-1][1]: M[-1][1] = max(M[-1][1], e)
    else: M.append([s, e])
T0, T1 = flips[0], flips[-1]; n = len(flips) - 1
agg = collections.defaultdict(lambda: [0.0, 0.0, 0])
prev = T0
for s, e, lab in W:
    if s < T0 or e > T1: continue
    if s > prev:
        tot = s - prev; ov = 0.0
        i = bisect.bisect_left([m[1] for m in M], prev)
        while i < len(M) and M[i][0] < s:
            ov += max(0, min(M[i][1], s) - max(M[i][0], prev)); i += 1
        g = agg[lab]; g[0] += tot; g[1] += tot - ov; g[2] += 1
    prev = max(prev, e)
print("compute gap before wait: total / serial(SPU idle) ms per frame, gaps per frame")
for k, v in sorted(agg.items(), key=lambda x: -x[1][1])[:12]:
    print("%-18s %6.2f %6.2f %6.1f" % (k, v[0] / n / 1000, v[1] / n / 1000, v[2] / n))
