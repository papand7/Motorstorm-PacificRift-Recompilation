"""T154: per-module Wws job counters (PS3_SPU_WWS_STATS) of one A/B run, added to its ana JSON.

  py -3 ana_wstat_t154.py <ana_json> <run_dir>      adds "wws_stats" to <ana_json> (in place)

The counters are cumulative; one table is printed at most once a second (when a job closes). The run stops
at race entry + 90 s, so as for [tex-snapshot-stats] the race window is the 6th-last table minus the 81st-last
(about 75 s of race). Rates are per host second of that window; per frame = per second / the run's race fps.
Module names come from the lift's registration TU (identifier bytes)."""
import json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
REG = ROOT / 'generated' / 'spu_raw' / 'wws_reloc_t81c' / 'wws_reloc_register.c'
G = re.compile(r'^\[wws-stats\] seq=(\d+) t_ms=(\d+) jobs=(\d+) lost=(\d+) drop=(\d+) entries resident=(\d+) '
               r'installed=(\d+) unknown=(\d+) mismatch=(\d+) noslot=(\d+) disabled=(\d+) badbase=(\d+) refused=(\d+)')
M = re.compile(r'^\[wws-stats\] seq=(\d+) mod ([0-9A-F]{8}) sig ([0-9A-F]{16}) base 0x([0-9A-F]{5}) n=(\d+) '
               r'ns=(\d+) max_ns=(\d+) steps=(\d+) aot=(\d+) aot_steps=(\d+) aot_with_steps=(\d+) '
               r'base_other=(\d+) res=([0-9/]+)')
GK = ('jobs', 'lost', 'drop', 'resident', 'installed', 'unknown', 'mismatch', 'noslot', 'disabled', 'badbase', 'refused')
MK = ('n', 'ns', 'steps', 'aot', 'aot_steps', 'aot_with_steps', 'base_other')

names = {}
for sig, name in re.findall(r'static const uint8_t sig\[16\] = \{([^}]*)\};.*?/\* ([^*]+?) \*/', REG.read_text(), re.S):
    names[''.join(f'{int(x, 16):02X}' for x in sig.split(',')[:8])] = name.strip()

ana, run_dir = Path(sys.argv[1]), Path(sys.argv[2])
d = json.loads(ana.read_text(encoding='utf-8'))
snaps = {}   # seq -> {'t': ms, 'g': {...}, 'm': {mod: {...}}}
with open(run_dir / 'stderr.log', encoding='utf-8', errors='replace') as f:
    for line in f:
        if not line.startswith('[wws-stats] seq='):
            continue
        g = G.match(line)
        if g:
            snaps.setdefault(int(g[1]), {'m': {}})
            snaps[int(g[1])].update(t=int(g[2]), g=dict(zip(GK, map(int, g.groups()[2:]))))
            continue
        m = M.match(line)
        if m:
            s = snaps.setdefault(int(m[1]), {'m': {}})
            s['m'][m[2]] = dict(zip(MK, (int(m[i]) for i in (5, 6, 8, 9, 10, 11, 12))), sig=m[3], base=m[4],
                                max_ns=int(m[7]), res=[int(v) for v in m[13].split('/')])
seqs = sorted(k for k, v in snaps.items() if 'g' in v)
fps = (d.get('fps') or {}).get('fps')
if len(seqs) < 20 or not fps:
    d['wws_stats'] = {'available': False, 'tables': len(seqs)}
else:
    a, b = snaps[seqs[max(0, len(seqs) - 81)]], snaps[seqs[-6]]
    dt = (b['t'] - a['t']) / 1000.0
    out = {'available': True, 'tables': len(seqs), 'window_s': round(dt, 1), 'fps': fps}
    gd = {k: b['g'][k] - a['g'][k] for k in GK}
    out['per_s'] = {k: round(v / dt, 2) for k, v in gd.items()}
    mods, tot_ns, tot_steps = [], 0, 0
    for k, mb in b['m'].items():
        ma = a['m'].get(k, {kk: 0 for kk in MK})
        x = {kk: mb[kk] - ma.get(kk, 0) for kk in MK}
        if x['n'] <= 0:
            continue
        tot_ns += x['ns']
        tot_steps += x['steps']
        mods.append({'mod': k, 'name': names.get(mb['sig'], '?' + mb['sig']), 'base': mb['base'],
                     'jobs_per_frame': round(x['n'] / dt / fps, 2),
                     'ms_per_frame': round(x['ns'] / 1e6 / dt / fps, 3),
                     'us_per_job': round(x['ns'] / 1e3 / x['n'], 1),
                     'max_us_run': round(mb['max_ns'] / 1e3, 1),
                     'interp_minsn_per_frame': round(x['steps'] / 1e6 / dt / fps, 3),
                     'aot_frac': round(x['aot'] / x['n'], 4),
                     'aot_jobs_with_interp': x['aot_with_steps'], 'base_other': x['base_other']})
    mods.sort(key=lambda r: -r['ms_per_frame'])
    out['job_ms_per_frame'] = round(tot_ns / 1e6 / dt / fps, 2)
    out['interp_minsn_per_frame'] = round(tot_steps / 1e6 / dt / fps, 3)
    out['jobs_per_frame'] = round(gd['jobs'] / dt / fps, 2)
    out['modules'] = mods
    d['wws_stats'] = out
ana.write_text(json.dumps(d, indent=1), encoding='utf-8')
w = d['wws_stats']
print(ana.name, {k: w.get(k) for k in ('available', 'tables', 'job_ms_per_frame', 'jobs_per_frame', 'interp_minsn_per_frame')})
