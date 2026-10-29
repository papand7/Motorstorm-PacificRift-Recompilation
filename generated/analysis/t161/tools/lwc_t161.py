#!/usr/bin/env python3
"""T161 lwcond diagnostic: main-thread waits and their producers from one run (PS3_LWCOND_TRACE +
window-local PS3_HLE_WAIT_MS).  py -3 lwc_t161.py <run_dir> <ps3recomp_dir> name:lo:hi ...   prints JSON

Clock: [lwc] lines carry now_us (QPC); the [rsx-hb] ms= heartbeat before each gives host s, so
host_s = now_us/1e6 - offset with offset the median over all window lines.
Per phase (host s), all elapsed time (not CPU):
  hle_main      tid 1 [hle-wait] per import: calls, ms (window-local, so complete), plus drops
  lwc_main      tid 1 [lwc] aggregates per (cv, lr): calls, wait ms, episodes, signalled / not
  episodes      tid 1 [lwc-ep] (>= min_ms): count, total s, signalled share, wake lag
                (t1 - last signal) p50/p90, top (cv, lr, bt) and top signaller (tid, lr, sbt)
  signals       [lwc-sig] on the lwconds tid 1 waited on: per signaller tid/lr, n, hit
Episodes and categories overlap across threads; nothing is summed across threads."""
import json, re, statistics, sys
from collections import defaultdict
from pathlib import Path

HB = re.compile(r'\[rsx-hb\] ms=(\d+)')
LWC = re.compile(r'\[lwc\] window_ms=\d+ now_us=(\d+) tid=(\d+) cv=0x(\w+) mtx=0x(\w+) lr=0x(\w+) calls=(\d+) wait_ms=([\d.]+)'
                 r' eps=(\d+) ep_max_ms=([\d.]+) eps_sig=(\d+) eps_nosig=(\d+) over_timeout=(\d+) timeout_us=(\d+) gap_max_us=(\d+)')
EP = re.compile(r'\[lwc-ep\] t0_us=(\d+) t1_us=(\d+) tid=(\d+) cv=0x(\w+) mtx=0x(\w+) lr=0x(\w+) polls=(\d+) dur_us=(\d+)'
                r' wait_us=(\d+) timeout_us=(\d+) sig=(\d+) sig_tid=(\d+) sig_lr=0x(\w+) first_sig_us=(\d+) last_sig_us=(\d+)'
                r' bt=(\S+) sbt=(\S+)')
SIG = re.compile(r'\[lwc-sig\] window_ms=\d+ tid=(\d+) cv=0x(\w+) lr=0x(\w+) kind=(\w+) n=(\d+) hit=(\d+)')
OPEN = re.compile(r'\[lwc-open\] window_ms=\d+ tid=(\d+) cv=0x(\w+) lr=0x(\w+) open_ms=([\d.]+) polls=(\d+) sig=(\d+)')
HW = re.compile(r'\[hle-wait\] window_ms=\d+ tid=(\d+) total_ms=[\d.]+(.*)')
HWD = re.compile(r'\[hle-wait\] window_ms=\d+ dropped=(\d+)(?: late=(\d+))?')
KEY = re.compile(r' nid([0-9A-F]{8})=([\d.]+)ms/(\d+)')
ROWD = re.compile(r' dropped=(\d+)')


def names(pr):
    sys.path.insert(0, str(Path(pr) / 'tools'))
    try:
        import nid_database as n
        db = n.get_default_db()
        return lambda nid: (db.lookup_nid(int(nid, 16)) or (None, 'nid' + nid))[1]
    except Exception:
        return lambda nid: 'nid' + nid


def pct(v, p):
    v = sorted(v)
    return round(v[min(len(v) - 1, int(p / 100 * len(v)))], 2) if v else None


def main(rd, pr, phases):
    nm = names(pr)
    host_s, offs = 0.0, []
    lwc, sigs, hw, opens, eps = [], [], [], [], []
    hw_drop = []
    with open(Path(rd) / 'stderr.log', encoding='utf-8', errors='replace') as f:
        for l in f:
            if l.startswith('[rsx-hb]'):
                m = HB.match(l)
                if m: host_s = int(m.group(1)) / 1000.0
            elif l.startswith('[lwc] '):
                m = LWC.match(l)
                if m:
                    offs.append(int(m.group(1)) / 1e6 - host_s)
                    lwc.append((host_s, int(m.group(2)), m.group(3), m.group(4), m.group(5), int(m.group(6)), float(m.group(7)),
                                int(m.group(8)), float(m.group(9)), int(m.group(10)), int(m.group(11)), int(m.group(12)),
                                int(m.group(13)), int(m.group(14))))
            elif l.startswith('[lwc-ep]'):
                m = EP.match(l)
                if m: eps.append(m.groups())
            elif l.startswith('[lwc-sig]'):
                m = SIG.match(l)
                if m: sigs.append((host_s, int(m.group(1)), m.group(2), m.group(3), m.group(4), int(m.group(5)), int(m.group(6))))
            elif l.startswith('[lwc-open]'):
                m = OPEN.match(l)
                if m: opens.append((host_s, int(m.group(1)), m.group(2), m.group(3), float(m.group(4)), int(m.group(5)), int(m.group(6))))
            elif l.startswith('[hle-wait]'):
                m = HW.match(l)
                if m:
                    d = ROWD.search(m.group(2))
                    hw.append((host_s, int(m.group(1)), KEY.findall(m.group(2)), int(d.group(1)) if d else 0))
                else:
                    m = HWD.match(l)
                    if m: hw_drop.append((host_s, int(m.group(1)), int(m.group(2) or 0)))
    off = statistics.median(offs) if offs else 0.0
    res = {'clock_offset_s': round(off, 3), 'phases': []}
    for ph in phases:
        name, lo, hi = ph.split(':'); lo, hi = float(lo), float(hi)
        r = {'phase': name, 'span_s': [lo, hi]}
        # tid 1 imports
        agg = defaultdict(lambda: [0, 0.0]); rowd = 0
        for t, tid, keys, d in hw:
            if tid == 1 and lo <= t < hi:
                rowd += d
                for nid, ms, n in keys:
                    a = agg[nm(nid)]; a[0] += int(n); a[1] += float(ms)
        r['hle_main'] = {'imports': [{'import': k, 'calls': v[0], 'ms': round(v[1], 1)}
                                     for k, v in sorted(agg.items(), key=lambda kv: -kv[1][1])[:10]],
                         'row_dropped': rowd,
                         'table_dropped': sum(d for t, d, _ in hw_drop if lo <= t < hi),
                         'late': sum(x for t, _, x in hw_drop if lo <= t < hi)}
        # tid 1 lwcond aggregates
        la = defaultdict(lambda: [0, 0.0, 0, 0, 0, 0, 0.0, 0, 0, 0])
        cvs = set()
        for (t, tid, cv, mtx, lr, calls, wms, ne, epmax, es, en, ot, to, gap) in lwc:
            if tid == 1 and lo <= t < hi:
                a = la[(cv, mtx, lr)]
                a[0] += calls; a[1] += wms; a[2] += ne; a[3] += es; a[4] += en; a[5] += ot
                a[6] = max(a[6], epmax); a[7] = to; a[8] = max(a[8], gap)
                cvs.add(cv)
        r['lwc_main'] = [{'cv': k[0], 'mtx': k[1], 'lr': k[2], 'calls': v[0], 'wait_ms': round(v[1], 1), 'eps': v[2],
                          'eps_sig': v[3], 'eps_nosig': v[4], 'over_timeout': v[5], 'ep_max_ms': v[6],
                          'timeout_us': v[7], 'gap_max_us': v[8]}
                         for k, v in sorted(la.items(), key=lambda kv: -kv[1][1])[:8]]
        # tid 1 episodes
        E = []
        for g in eps:
            t1 = int(g[1]) / 1e6 - off
            if int(g[2]) == 1 and lo <= t1 < hi:
                E.append(dict(t0=int(g[0]) / 1e6 - off, t1=t1, cv=g[3], lr=g[5], polls=int(g[6]), dur=int(g[7]) / 1e6,
                              to=int(g[9]), sig=int(g[10]), stid=int(g[11]), slr=g[12],
                              lag=(int(g[1]) - int(g[14])) / 1e3 if int(g[10]) else None, bt=g[15], sbt=g[16]))
        by_site = defaultdict(lambda: [0, 0.0]); by_sig = defaultdict(lambda: [0, 0.0])
        for e in E:
            s = by_site[(e['cv'], e['lr'], e['bt'])]; s[0] += 1; s[1] += e['dur']
            k = (e['stid'], e['slr'], e['sbt']) if e['sig'] else ('none', '', '')
            s = by_sig[k]; s[0] += 1; s[1] += e['dur']
        lags = [e['lag'] for e in E if e['lag'] is not None]
        r['episodes'] = {'n': len(E), 'total_s': round(sum(e['dur'] for e in E), 2),
                         'signalled': sum(1 for e in E if e['sig']), 'polls': sum(e['polls'] for e in E),
                         'dur_ms_p50': pct([e['dur'] * 1e3 for e in E], 50), 'dur_ms_p90': pct([e['dur'] * 1e3 for e in E], 90),
                         'dur_ms_max': round(max((e['dur'] * 1e3 for e in E), default=0), 1),
                         'wake_lag_ms_p50': pct(lags, 50), 'wake_lag_ms_p90': pct(lags, 90),
                         'top_sites': [{'cv': k[0], 'lr': k[1], 'bt': k[2], 'n': v[0], 's': round(v[1], 2)}
                                       for k, v in sorted(by_site.items(), key=lambda kv: -kv[1][1])[:6]],
                         'signallers': [{'tid': k[0], 'lr': k[1], 'sbt': k[2], 'eps': v[0], 's': round(v[1], 2)}
                                        for k, v in sorted(by_sig.items(), key=lambda kv: -kv[1][1])[:6]]}
        # signals on the main thread's lwconds
        sg = defaultdict(lambda: [0, 0])
        for (t, tid, cv, lr, kind, n, hit) in sigs:
            if cv in cvs and lo <= t < hi:
                a = sg[(tid, cv, lr, kind)]; a[0] += n; a[1] += hit
        r['signals_on_main_cvs'] = [{'tid': k[0], 'cv': k[1], 'lr': k[2], 'kind': k[3], 'n': v[0], 'hit': v[1]}
                                    for k, v in sorted(sg.items(), key=lambda kv: -kv[1][0])[:10]]
        r['open_main_max_ms'] = max((o[4] for o in opens if o[1] == 1 and lo <= o[0] < hi), default=0)
        res['phases'].append(r)
    print(json.dumps(res, indent=1))


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2], sys.argv[3:])
