"""Race metrics of run_ab.py launches: fps from race_entry + 10 s to the last [rsx-hb], main-thread
(tid=1) sc-wait ms per s for usleep (sc141) and event-queue receive (sc130), and the SPU task time per
run of each image ([spu-task-stats], cumulative: delta fn_ns / delta runs over the same window).
usage: python ab_metrics.py <tag> [<tag> ...]"""
import json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
AB2 = ROOT / 'generated/analysis/vksync/ab2'
HB = re.compile(r'\[rsx-hb\] ms=(\d+) frames=(\d+)')
SC = re.compile(r'\[sc-wait\] window_ms=(\d+) tid=1 total_ms=[\d.]+ (.*)')
TS = re.compile(r'\[spu-task-stats\] seq=\d+ t_ms=\d+ img=(\d+) runs=(\d+) run_ns=\d+ fn_ns=(\d+)')
IMGS = ('491898574', '341580667', '308733018', '406081863')


def one(tag):
    rt = sorted(AB2.glob(f'runtime-{tag}-*'))[-1]
    entry = None
    for l in (rt / 'timeline.jsonl').read_text(errors='replace').splitlines():
        if '"race_entry"' in l:
            entry = json.loads(l).get('hb_ms')
            break
    run = sorted((ROOT / 'generated/runs').glob(f'*-vk-K{tag}'))[-1]
    lines = (run / 'stderr.log').read_text(errors='replace').splitlines()
    if entry is None:
        return tag, None
    start = entry + 10000
    hb, sc141, sc130, ts0, ts1 = [], [], [], {}, {}
    on = False
    for l in lines:
        m = HB.search(l)
        if m:
            ms, fr = int(m.group(1)), int(m.group(2))
            if ms >= start:
                on = True
                hb.append((ms, fr))
            continue
        if not on:
            continue
        m = SC.search(l)
        if m:
            d = dict((k, float(v)) for k, v in re.findall(r'sc(\d+)=([\d.]+)ms', m.group(2)))
            sc141.append(d.get('141', 0.0)); sc130.append(d.get('130', 0.0))
            continue
        m = TS.search(l)
        if m and m.group(1) in IMGS:
            v = (int(m.group(2)), int(m.group(3)))
            ts0.setdefault(m.group(1), v); ts1[m.group(1)] = v
    if len(hb) < 2:
        return tag, None
    fps = (hb[-1][1] - hb[0][1]) * 1000.0 / (hb[-1][0] - hb[0][0])
    task = {}
    for k in ts0:
        dr, dn = ts1[k][0] - ts0[k][0], ts1[k][1] - ts0[k][1]
        if dr > 0:
            task[k] = (dn / dr / 1e6, dr)
    return tag, dict(entry_ms=entry, window_s=(hb[-1][0] - hb[0][0]) / 1000.0, fps=fps,
                     usleep_ms_s=sum(sc141) / max(1, len(sc141)), evq_ms_s=sum(sc130) / max(1, len(sc130)),
                     task_ms_per_run=task)


for t in sys.argv[1:]:
    tag, m = one(t)
    if not m:
        print(tag, 'no race_entry or no race window')
        continue
    ts = ' '.join(f'{k}={v[0]:.2f}ms/run(x{v[1]})' for k, v in sorted(m['task_ms_per_run'].items()))
    print(f"{tag} entry={m['entry_ms']}ms window={m['window_s']:.0f}s fps={m['fps']:.2f} "
          f"main usleep={m['usleep_ms_s']:.1f}ms/s evq={m['evq_ms_s']:.1f}ms/s | {ts}")
