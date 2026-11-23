"""Per-module Wws job cost over a race window from PS3_SPU_WWS_STATS (cumulative [wws-stats] mod lines), private.
usage: py -3 wws_window.py <run tag e.g. ksr48> [<tag> ...]
Window = race_entry + 10 s .. last [rsx-hb] (as spuopt/tools/ab_metrics.py). Module names from the Wws manifest."""
import json, re, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[4]
AB2 = ROOT / 'generated/analysis/vksync/ab2'
MAN = {m['sig'][:16].upper(): m['name'] for m in json.load(open(ROOT / 'generated/spu_raw/wws_reloc/wws_reloc_manifest.json'))}
HB = re.compile(r'^\[rsx-hb\] ms=(\d+) frames=(\d+)')
MOD = re.compile(r'^\[wws-stats\] seq=(\d+) mod ([0-9A-F]{8}) sig ([0-9A-F]{16}) base 0x([0-9A-F]+) n=(\d+) ns=(\d+) max_ns=(\d+) '
                 r'steps=(\d+) aot=(\d+) aot_steps=(\d+) aot_with_steps=(\d+)')
def one(tag):
    rt = sorted(AB2.glob(f'runtime-{tag}-*'))[-1]
    entry = next(json.loads(l)['hb_ms'] for l in (rt / 'timeline.jsonl').read_text(errors='replace').splitlines() if '"race_entry"' in l)
    run = sorted((ROOT / 'generated/runs').glob(f'*-vk-K{tag}'))[-1]
    snaps, hb, cur = [], (0, 0), None
    for l in (run / 'stderr.log').open(errors='replace'):
        m = HB.match(l)
        if m: hb = (int(m.group(1)), int(m.group(2))); continue
        m = MOD.match(l)
        if m:
            seq = int(m.group(1))
            if cur is None or cur['seq'] != seq:
                cur = dict(seq=seq, t=hb[0], fr=hb[1], m={}); snaps.append(cur)
            cur['m'][m.group(3)] = tuple(int(m.group(i)) for i in (5, 6, 8, 11))
    a = next(s for s in snaps if s['t'] >= entry + 10000); b = snaps[-1]
    dt = (b['t'] - a['t']) / 1000.0; fr = b['fr'] - a['fr']
    print(f'== {tag} ({run.name}) window {dt:.1f} s, {fr} frames, {fr/dt:.2f} fps')
    print('module                          jobs/frame  us/job  steps/job  with_steps%  SPU-ms/frame')
    rows, tot = [], 0.0
    for sig, v in b['m'].items():
        u = a['m'].get(sig, (0, 0, 0, 0)); dn, dns, dst, dws = (v[i] - u[i] for i in range(4))
        if dn <= 0: continue
        rows.append((dns / fr / 1e6, MAN.get(sig, sig), dn / fr, dns / dn / 1e3, dst / dn, 100.0 * dws / dn))
        tot += dns / fr / 1e6
    for ms, name, jpf, us, spj, ws in sorted(rows, reverse=True):
        print(f'{name[:31]:31} {jpf:10.2f} {us:7.1f} {spj:10.1f} {ws:11.1f} {ms:13.3f}')
    print(f'{"total":31} {"":10} {"":7} {"":10} {"":11} {tot:13.3f}')
for t in sys.argv[1:]: one(t)
