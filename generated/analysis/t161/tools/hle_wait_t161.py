#!/usr/bin/env python3
"""T161 V2: race-load wait attribution from one run (PROPOSED analysis of an authorised launch).
  py -3 hle_wait_t161.py <run_dir> <ps3recomp_dir> <load_lo_s> <load_hi_s>   prints JSON

Sources (all elapsed wall time unless marked cpu):
  [hle-wait] / [sc-wait]  per-thread per-key sums per 1 s window (window placed by the [rsx-hb] ms= clock);
                          per key: calls, total ms, largest single-window ms (an upper bound for a call
                          only when calls == 1 in that window)
  [PT] ev=hle             every import call >= hle_min_us (2 ms in V2): exact per-call durations ->
                          max, p50/p90/p99 and a histogram, per (tid, import) and per lr call site
  [PT] fn=536A30 exits    the main thread's load-by-path calls; each is overlapped with the same thread's
                          PT hle calls to say how much of it was spent inside imports >= 2 ms
  performance.json        process cpu cores (user + kernel) over the span (cpu, not elapsed)
Categories overlap (a lwcond wait may sit inside a 0x536A30 call, and several threads wait at once):
nothing here is summed across threads or categories into a 'total load time'."""
import bisect, json, re, sys
from collections import defaultdict
from pathlib import Path

HB = re.compile(r'\[rsx-hb\] ms=(\d+)')
WAIT = re.compile(r'\[(sc|hle)-wait\] window_ms=\d+ tid=(\d+) total_ms=[\d.]+(.*)')
KEY = re.compile(r' (sc\d+|nid[0-9A-F]{8})=([\d.]+)ms/(\d+)')
PT_HLE = re.compile(r'\[PT\] t=(\d+) tid=(\d+) ev=hle nid=([0-9A-F]{8}) pc=\w+ lr=(\w+) dur_us=(\d+)')
PT_FN = re.compile(r'\[PT\] t=(\d+) tid=(\d+) ev=exit pc=\w+ lr=\w+ fn=00536A30 site=(\w+) .*?dur_us=(\d+)')
BUCKETS = [(2, 5), (5, 20), (20, 100), (100, 1000), (1000, 1e12)]


def nid_names(pr):
    names = {}
    sys.path.insert(0, str(Path(pr) / 'tools'))
    try:
        import nid_database as n
        names['_db'] = n.get_default_db()   # looked up lazily in name_of()
    except Exception:
        pass
    for f in list(Path(pr, 'runtime').rglob('*.cpp')) + list(Path(pr, 'runtime').rglob('*.c')):
        for m in re.finditer(r'0x([0-9A-Fa-f]{8})u?,\s*"([A-Za-z_][A-Za-z0-9_]*)"', f.read_text(errors='replace')):
            names.setdefault(m.group(1).upper(), m.group(2))
    return names


def name_of(names, nid):
    if nid in names:
        return names[nid]
    db = names.get('_db')
    if db is not None:
        try:
            e = db.lookup_nid(int(nid, 16))
            if e:
                return e[1]
        except Exception:
            pass
    return 'nid' + nid


def pct(v, p):
    v = sorted(v)
    return round(v[min(len(v) - 1, int(p / 100 * len(v)))], 2) if v else None


def main(rd, pr, lo, hi):
    names = nid_names(pr)
    host_s = 0.0
    win = defaultdict(lambda: [0, 0.0, 0.0])             # (src, tid, key) -> calls, ms, max window ms
    calls = defaultdict(list)                           # (tid, nid) -> [dur_ms]
    sites = defaultdict(list)                           # (tid, nid, lr) -> [dur_ms]
    tid_iv = defaultdict(list)                          # tid -> [(t0_s, t1_s, nid)]
    loads = []
    with open(Path(rd) / 'stderr.log', encoding='utf-8', errors='replace') as f:
        for l in f:
            m = HB.match(l)
            if m:
                host_s = int(m.group(1)) / 1000.0
                continue
            if l.startswith('[PT]'):
                m = PT_HLE.match(l)
                if m:
                    t1 = int(m.group(1)) / 1e6
                    d = int(m.group(5)) / 1e3
                    tid, nid = int(m.group(2)), m.group(3)
                    tid_iv[tid].append((t1 - d / 1e3, t1, nid))
                    if lo <= t1 < hi:
                        calls[(tid, nid)].append(d)
                        sites[(tid, nid, m.group(4))].append(d)
                    continue
                m = PT_FN.match(l)
                if m:
                    t1 = int(m.group(1)) / 1e6
                    loads.append({'t_end_s': round(t1, 2), 'tid': int(m.group(2)), 'site': m.group(3),
                                  'dur_s': int(m.group(4)) / 1e6})
                continue
            m = WAIT.match(l)
            if m and lo <= host_s < hi:
                for k, ms, n in KEY.findall(m.group(3)):
                    key = name_of(names, k[3:]) if k.startswith('nid') else k
                    w = win[(m.group(1), int(m.group(2)), key)]
                    w[0] += int(n); w[1] += float(ms); w[2] = max(w[2], float(ms))
    res = {'span_s': [lo, hi]}
    res['window_sums'] = [
        {'src': s, 'tid': t, 'key': k, 'calls': v[0], 'total_ms': round(v[1], 1), 'max_window_ms': round(v[2], 1)}
        for (s, t, k), v in sorted(win.items(), key=lambda kv: -kv[1][1]) if v[1] >= 50.0][:60]
    res['long_calls'] = []
    for (tid, nid), ds in sorted(calls.items(), key=lambda kv: -sum(kv[1])):
        h = {f'{a}-{b if b < 1e12 else "inf"}ms': sum(1 for d in ds if a <= d < b) for a, b in BUCKETS}
        top = sorted(((lr, len(v), round(sum(v), 1)) for (t2, n2, lr), v in sites.items() if t2 == tid and n2 == nid),
                     key=lambda x: -x[2])[:3]
        res['long_calls'].append({'tid': tid, 'import': name_of(names, nid), 'calls_ge_2ms': len(ds),
                                  'total_ms': round(sum(ds), 1), 'max_ms': round(max(ds), 1),
                                  'p50_ms': pct(ds, 50), 'p90_ms': pct(ds, 90), 'p99_ms': pct(ds, 99),
                                  'hist': h, 'top_lr': top})
    res['long_calls'] = res['long_calls'][:40]
    # 0x536A30 calls in the span, with the main thread's own import time (>= 2 ms) inside each.
    out = []
    for c in loads:
        t1 = c['t_end_s']; t0 = t1 - c['dur_s']
        if not (lo <= t1 < hi) or c['dur_s'] < 0.1:
            continue
        inside = defaultdict(float)
        for a, b, nid in tid_iv[c['tid']]:
            if b > t0 and a < t1:
                inside[name_of(names, nid)] += (min(b, t1) - max(a, t0))
        tot = sum(inside.values())
        out.append({**c, 'dur_s': round(c['dur_s'], 2), 'in_imports_ge_2ms_s': round(tot, 2),
                    'share': round(tot / c['dur_s'], 3) if c['dur_s'] else None,
                    'by_import_s': {k: round(v, 2) for k, v in sorted(inside.items(), key=lambda kv: -kv[1])[:5]}})
    res['load_by_path_536A30'] = {'calls_ge_100ms': len(out), 'total_s': round(sum(c['dur_s'] for c in out), 2),
                                  'calls': out}
    # Process CPU over the span (cpu time, not elapsed).
    try:
        perf = json.load(open(Path(rd) / 'performance.json'))
        smp = [s for s in perf['samples'] if lo <= s['t'] <= hi]
        if len(smp) >= 2:
            a, b = smp[0], smp[-1]
            cpu = (b['cpu_user_s'] + b['cpu_kernel_s']) - (a['cpu_user_s'] + a['cpu_kernel_s'])
            res['process_cpu'] = {'span_s': [a['t'], b['t']], 'cpu_s': round(cpu, 1),
                                  'cores': round(cpu / (b['t'] - a['t']), 2)}
    except Exception as e:
        res['process_cpu'] = {'error': repr(e)}
    print(json.dumps(res, indent=1))


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2], float(sys.argv[3]), float(sys.argv[4]))
