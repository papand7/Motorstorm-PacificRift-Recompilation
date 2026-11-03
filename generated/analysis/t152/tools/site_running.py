#!/usr/bin/env python3
"""T152: split the frame thread's RUNNING time (T149 cpath trace) by guest site.

  python site_running.py <cpath.txt> [tid=1]

Running = frame span minus the thread's blocking syscalls (kind 1) and usleeps (kind 2),
the same definition as tools/cpath_report.py. Each guest-site span (kind 35, a = site)
is intersected with the running time; time inside several nested sites is credited to
the innermost (the latest-starting) one. Prints ms per frame.
"""
import collections
import sys

sys.path.insert(0, __import__('os').path.join(__import__('os').path.dirname(__file__)))

FLIP_REQ, SYSCALL, USLEEP, SITE = 9, 1, 2, 35


def union(iv):
    out = []
    for a, b in sorted(iv):
        if b <= a:
            continue
        if out and a <= out[-1][1]:
            out[-1][1] = max(out[-1][1], b)
        else:
            out.append([a, b])
    return out


def minus(x, y):
    out, j = [], 0
    for a, b in x:
        cur = a
        while j < len(y) and y[j][1] <= cur:
            j += 1
        k = j
        while k < len(y) and y[k][0] < b:
            c, d = y[k]
            if c > cur:
                out.append([cur, c])
            cur = max(cur, d)
            k += 1
        if cur < b:
            out.append([cur, b])
    return out


def main():
    path, tid = sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 1
    flips, blocked, sites = [], [], []
    with open(path, encoding='utf-8', errors='replace') as f:
        for line in f:
            p = line.split()
            if len(p) != 6 or not p[0].isdigit():
                continue
            k, who = int(p[0]), int(p[1])
            t0, t1 = float(p[4]) / 1e3, float(p[5]) / 1e3
            if k == FLIP_REQ:
                flips.append(t0)
            elif who == tid and k in (SYSCALL, USLEEP):
                blocked.append((t0, t1))
            elif who == tid and k == SITE:
                sites.append((t0, t1, int(p[2], 16)))
    flips.sort()
    f0, f1 = flips[0], flips[-1]
    nfr = len(flips) - 1
    run = minus([[f0, f1]], union(blocked))
    # elementary intervals: boundaries of running pieces and site spans
    sites = [(max(a, f0), min(b, f1), s) for a, b, s in sites if b > f0 and a < f1]
    ev = collections.defaultdict(list)
    for a, b, s in sites:
        ev[a].append(('+', a, s))
        ev[b].append(('-', a, s))
    # sweep: active set ordered by start; innermost = latest start
    pts = sorted(set([x for r in run for x in r] + list(ev.keys())))
    active = {}
    credit = collections.Counter()
    ri = 0
    total_run = sum(b - a for a, b in run)

    def running_len(a, b):
        nonlocal ri
        while ri < len(run) and run[ri][1] <= a:
            ri += 1
        t, k = 0.0, ri
        while k < len(run) and run[k][0] < b:
            t += max(0.0, min(b, run[k][1]) - max(a, run[k][0]))
            k += 1
        return t

    for i, x in enumerate(pts):
        for op, a, s in ev.get(x, ()):
            key = (a, s)
            if op == '+':
                active[key] = active.get(key, 0) + 1
            else:
                active[key] -= 1
                if not active[key]:
                    del active[key]
        if i + 1 < len(pts):
            y = pts[i + 1]
            r = running_len(x, y)
            if r > 0:
                inner = max(active)[1] if active else None
                credit[inner] += r
    print(f'frames={nfr} window={f1 - f0:.0f} ms frame={(f1 - f0) / nfr:.2f} ms')
    print(f'running per frame: {total_run / nfr:.2f} ms')
    for s, v in credit.most_common():
        name = f'0x{s:06X}' if s is not None else 'outside every traced site'
        print(f'  {name:28s} {v / nfr:7.2f} ms  ({100 * v / total_run:5.1f}%)')


if __name__ == '__main__':
    main()
