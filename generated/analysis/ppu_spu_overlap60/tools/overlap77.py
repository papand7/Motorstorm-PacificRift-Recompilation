"""ppu_spu_overlap60: split main-thread NON-WAIT time (compute) of a Kksr77 critical-path trace by whether SPU work is running.
usage: py -3 overlap77.py <trace>   (kinds as in roadto60_next/tools/cp77.py)"""
import sys, bisect, collections
waits, jobs, flips = [], [], []
for line in open(sys.argv[1], encoding="latin-1"):
    if not line[0].isdigit(): continue
    p = line.split()
    if len(p) < 6: continue
    k, who, a, b, t0, t1 = int(p[0]), p[1], p[2], p[3], float(p[4]), float(p[5])
    if k == 9: flips.append(t0)
    elif k == 2 and who == "1" and b in ("94cca8", "72e5c0", "a49ad4", "a48b4c", "a48364"): waits.append((t0, t1))
    elif k == 1 and who == "1" and a == "82" and t1 - t0 >= 20: waits.append((t0, t1))
    elif k in (26, 39): jobs.append((t0, t1))
flips.sort(); waits.sort(); jobs.sort()
def union(iv):
    out = []
    for s, e in sorted(iv):
        if out and s <= out[-1][1]: out[-1][1] = max(out[-1][1], e)
        else: out.append([s, e])
    return out
W = union(waits); J = union(jobs)
def inter(A, B):  # total overlap of two sorted disjoint lists
    i = j = 0; tot = 0.0
    while i < len(A) and j < len(B):
        s = max(A[i][0], B[j][0]); e = min(A[i][1], B[j][1])
        if e > s: tot += e - s
        if A[i][1] < B[j][1]: i += 1
        else: j += 1
    return tot
T0, T1 = flips[0], flips[-1]; n = len(flips) - 1
clip = lambda L: [[max(s, T0), min(e, T1)] for s, e in L if e > T0 and s < T1]
W = clip(W); J = clip(J)
tot = T1 - T0
wait = sum(e - s for s, e in W)
spu_busy = sum(e - s for s, e in J)
# compute = complement of W
C, prev = [], T0
for s, e in W:
    if s > prev: C.append([prev, s])
    prev = max(prev, e)
if prev < T1: C.append([prev, T1])
comp = sum(e - s for s, e in C)
comp_spu = inter(C, J)
wait_spu = inter(W, J)
f = lambda x: round(x / n / 1000.0, 2)
print("frames", n, "frame_ms", f(tot))
print("main waiting ms/frame", f(wait), " of which SPU active", f(wait_spu), "SPU idle", f(wait - wait_spu))
print("main compute ms/frame", f(comp), " of which SPU active (overlap)", f(comp_spu), "SPU idle", f(comp - comp_spu))
print("SPU any-work-active ms/frame", f(sum(e - s for s, e in J)))
print("SPU idle while main computes = serial PPU time (no overlap):", f(comp - comp_spu))
