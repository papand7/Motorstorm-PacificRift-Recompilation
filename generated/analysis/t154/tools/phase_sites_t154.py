"""T154: the PPU wait sites and the Wws job counters, split by content phase (see phase_match_t154.py).

  py -3 phase_sites_t154.py <run_dir> ...       prints JSON

Race frame 0 = first [rsx-frame-perf] with draw_calls >= 200 (guest frame G0). Guest frame -> RSX pass from
[rsx-frame-perf] (gframe=, pass=; the heavy phase runs 4 passes per guest frame), pass -> host ms from the
[rsx-hb] heartbeat (frames= counts passes, ms= host ms since start, as PT t= is host us since start),
linearly interpolated. Windows: light = race frames 40..500, heavy = 600..<common end>.
- PT exit records ([PT] ... ev=exit fn=<site> dur_us=) per window: calls, mean ms, and ms per guest frame
  (sum / frames in the window).
- [wws-stats] tables (QPC ms) are put on the same clock by the offset between the last table and the last
  heartbeat (within about 1 s); job counters per window: jobs/frame, job ms/frame, us/job, interpreted Minsn/frame,
  and the five most expensive modules."""
import bisect, json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
REG = ROOT / 'generated' / 'spu_raw' / 'wws_reloc_t81c' / 'wws_reloc_register.c'
names = {''.join(f'{int(x, 16):02X}' for x in s.split(',')[:8]): n.strip() for s, n in
         re.findall(r'static const uint8_t sig\[16\] = \{([^}]*)\};.*?/\* ([^*]+?) \*/', REG.read_text(), re.S)}
SITES = {'0050C818': 'Wws spin', '0072E1E0': 'ref throttle', '0030B710': 'Havok wait', '00736770': 'PUT flush'}
PT = re.compile(r'^\[PT\] t=(\d+) tid=\d+ ev=exit .*?fn=([0-9A-F]{8}) .*?dur_us=(\d+)')
HB = re.compile(r'^\[rsx-hb\] ms=(\d+) frames=(\d+)')
FP = re.compile(r'^\[rsx-frame-perf\] gframe=(\d+) pass=(\d+) .*?draw_calls=(\d+)')
WG = re.compile(r'^\[wws-stats\] seq=(\d+) t_ms=(\d+) jobs=(\d+)')
WM = re.compile(r'^\[wws-stats\] seq=(\d+) mod ([0-9A-F]{8}) sig ([0-9A-F]{16}) base 0x[0-9A-F]{5} n=(\d+) ns=(\d+) '
                r'max_ns=\d+ steps=(\d+) aot=(\d+)')


def parse(rd):
    hb, fp, pt, wt, wm = [], [], [], {}, {}
    for l in open(rd / 'stderr.log', encoding='utf-8', errors='replace'):
        if l.startswith('[PT] t='):
            m = PT.match(l)
            if m and m[2] in SITES:
                pt.append((int(m[1]) / 1000.0, m[2], int(m[3]) / 1000.0))
        elif l.startswith('[rsx-hb]'):
            m = HB.match(l)
            if m: hb.append((int(m[2]), int(m[1])))
        elif l.startswith('[rsx-frame-perf] gframe='):
            m = FP.match(l)
            if m: fp.append((int(m[1]), int(m[3]), int(m[2])))
        elif l.startswith('[wws-stats] seq='):
            m = WG.match(l)
            if m: wt[int(m[1])] = int(m[2])
            m = WM.match(l)
            if m: wm.setdefault(int(m[1]), {})[m[2]] = (m[3], int(m[4]), int(m[5]), int(m[6]), int(m[7]))
    return hb, fp, pt, wt, wm


def ms_at(hb, frame):
    fr = [f for f, _ in hb]
    i = bisect.bisect_left(fr, frame)
    i = min(max(i, 1), len(hb) - 1)
    (f0, t0), (f1, t1) = hb[i - 1], hb[i]
    return t0 + (t1 - t0) * (frame - f0) / max(1, f1 - f0)


data = {Path(a).name: parse(Path(a)) for a in sys.argv[1:]}
g0 = {k: next(g for g, d, _ in v[1] if d >= 200) for k, v in data.items()}
end = min(v[1][-1][0] - g0[k] for k, v in data.items()) - 1
out = {'common_race_frames': end}
for k, (hb, fp, pt, wt, wm) in data.items():
    gpass = {g: p for g, _, p in fp}
    off = max(wt.values()) - hb[-1][1]   # QPC ms - heartbeat ms
    o = {}
    for seg, (a, b) in {'light': (40, 500), 'heavy': (600, end)}.items():
        ta, tb = ms_at(hb, gpass[g0[k] + a]), ms_at(hb, gpass[g0[k] + b])
        nf = b - a
        s = {'frames': nf, 'host_s': round((tb - ta) / 1000, 1), 'fps': round(nf / ((tb - ta) / 1000), 2)}
        for site, nm in SITES.items():
            r = [d for t, f, d in pt if f == site and ta <= t < tb]
            s[nm] = {'calls': len(r), 'mean_ms': round(sum(r) / len(r), 2) if r else None,
                     'ms_per_frame': round(sum(r) / nf, 2) if r else None}
        seqs = sorted(q for q, t in wt.items() if ta + off <= t <= tb + off and q in wm)
        if len(seqs) >= 2:
            A, B = wm[seqs[0]], wm[seqs[-1]]
            span_f = nf * (wt[seqs[-1]] - wt[seqs[0]]) / (tb - ta)   # frames covered by the two tables
            mods, J, NS, ST = [], 0, 0, 0
            for mk, (sig, n, ns, st, aot) in B.items():
                a0 = A.get(mk, (sig, 0, 0, 0, 0))
                dn, dns, dst, dao = n - a0[1], ns - a0[2], st - a0[3], aot - a0[4]
                if dn <= 0: continue
                J += dn; NS += dns; ST += dst
                mods.append((names.get(sig, sig), round(dns / 1e6 / span_f, 2), round(dn / span_f, 1),
                             round(dns / 1e3 / dn, 1), round(dao / dn, 3)))
            mods.sort(key=lambda m: -m[1])
            s['wws'] = {'tables': len(seqs), 'jobs_per_frame': round(J / span_f, 1),
                        'job_ms_per_frame': round(NS / 1e6 / span_f, 1), 'us_per_job': round(NS / 1e3 / J, 1),
                        'interp_minsn_per_frame': round(ST / 1e6 / span_f, 2),
                        'top': [dict(zip(('module', 'ms_per_frame', 'jobs_per_frame', 'us_per_job', 'aot_frac'), m))
                                for m in mods[:8]]}
        o[seg] = s
    out[k] = o
print(json.dumps(out, indent=1))
