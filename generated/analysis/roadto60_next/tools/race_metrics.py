r"""roadto60_next: per-run race metrics for a build A/B, read-only on run data (no game launch).

usage: py -3 race_metrics.py [--json out.json] <tag> [<tag> ...]      e.g. ksr61 ksr63
Inputs per tag (the newest of each): generated/analysis/vksync/ab2/runtime-<tag>-*/ (timeline.jsonl,
cpu.jsonl, gpu.csv, wrapper.log) and generated/runs/*-vk-K<tag>/stderr.log.

Window: race_entry (timeline hb_ms) + 10 s .. last [rsx-hb] (as ab_metrics.py). Reported per run:
- fps over the window (frames delta / ms delta), per-second fps from consecutive [rsx-hb] (mean, sd, p5, min)
- frame time from [frame-hist] blocks (240 drawn presents each) whose preceding [rsx-hb] lies in the window:
  median of block p50 (~median frame time), median of block p90, median and max of block p99, over34 share.
  P95 is NOT logged by the runtime (only p50/p90/p99 per block); p95 is reported as "n/a" unless a PresentMon
  CSV is given in <rtdir>/presentmon.csv (optional, see BUILD_AB_PLAN.md).
- main thread (tid=1) [sc-wait] usleep (sc141) and event-queue (sc130) ms per frame; JobBatchHandler (tid=12)
  usleep calls/s; [hle-wait] tid=1 ms per frame
- [vk-waits] present wait ms per frame (delta over the window), [main-cyc] Mcycles/flip (median)
- [sim-pace] late/overload/lost deltas per minute (timing bookkeeping; see BUILD_AB_PLAN.md for meaning)
- [spu-task-stats] ms/run per Havok image when the run had PS3_SPU_TASK_STATS on (else empty)
- host: game cores, non-game busy cores, sys busy %, other games present, GPU util mean (gpu.csv), and the
  quality gate (REJECT on >= 6 non-game cores, another game present, or GPU util >= 70 % with another game)
- correctness flags: exit status, controller stop reason, leftover process, counts of fatal/Timeout/NOSYS lines,
  new [mfc] REJECTED / [spu-dma] SKIP lines after race entry."""
import json
import re
import statistics as st
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
AB2 = ROOT / 'generated/analysis/vksync/ab2'
RUNS = ROOT / 'generated/runs'
NC = 12
HB = re.compile(r'^\[rsx-hb\] ms=(\d+) frames=(\d+) draw_frames=(\d+) last_draws=(\d+)')
FH = re.compile(r'^\[frame-hist\] p50=([\d.]+) p90=([\d.]+) p99=([\d.]+) max=([\d.]+) ms over34=([\d.]+)% draws=([\d.]+)')
SC = re.compile(r'^\[sc-wait\] window_ms=(\d+) tid=(\d+) total_ms=[\d.]+ (.*)')
HW = re.compile(r'^\[hle-wait\] window_ms=(\d+) tid=1 total_ms=([\d.]+)')
VW = re.compile(r'^\[vk-waits\] .*present=(\d+)/([\d.]+)ms')
MC = re.compile(r'^\[main-cyc\] (\d+) flips, ([\d.]+) Mcycles')
SP = re.compile(r'^\[sim-pace\] steps=(\d+) late=(\d+) overloads=(\d+) lost_ms=(\d+) held_ms=(\d+)')
TS = re.compile(r'^\[spu-task-stats\] seq=\d+ t_ms=\d+ img=(\d+) runs=(\d+) run_ns=\d+ fn_ns=(\d+)')
HAVOK = {'491898574': 'HK2', '341580667': 'HK1', '406081863': 'HKd', '308733018': 'HKc'}
BAD = re.compile(r'[Ff]atal|FATAL|Present\(\) Timeout|NOSYS|[Uu]nhandled exception|ACCESS_VIOLATION|GPU watchdog')   # not [lwc-wake] timeouts=
OTHER_GAME = re.compile(r'^(bf\w*|bfbc\w*|nightfire|.*rpcs3.*|eldenring|cs2|valorant)\.exe$', re.I)


def pct(xs, q):
    xs = sorted(xs)
    if not xs:
        return None
    k = (len(xs) - 1) * q
    f = int(k)
    return xs[f] if f + 1 >= len(xs) else xs[f] + (xs[f + 1] - xs[f]) * (k - f)


def host(rt, t_start_wall):
    L = [json.loads(l) for l in (rt / 'cpu.jsonl').read_text().splitlines() if l.strip()]
    oc, busy, game, top, others = [], [], [], [], set()
    for a, b in zip(L, L[1:]):
        if b['t'] < t_start_wall:
            continue
        bi, ii = b['sys_busy'] - a['sys_busy'], b['sys_idle'] - a['sys_idle']
        if bi + ii <= 0:
            continue
        u = bi / (bi + ii)
        g = sum(b['threads'].values()) / 100.0
        busy.append(u * 100)
        game.append(g)
        top.append(max(b['threads'].values()) if b['threads'] else 0)
        oc.append(max(0.0, u * NC - g))
        for o in b.get('others', []):
            if OTHER_GAME.match(o[0]) and o[2] > 3:
                others.add(o[0])
    gpu = []
    g = rt / 'gpu.csv'
    if g.exists():
        for l in g.read_text().splitlines():
            p = [x.strip() for x in l.split(',')]
            if len(p) >= 5:
                try:
                    gpu.append(int(p[2].split()[0]))
                except ValueError:
                    pass
    gpu = gpu[len(gpu) // 3:]    # the race part of the run (gpu.csv is sampled every ~15 s from launch)
    m = lambda xs: round(st.mean(xs), 2) if xs else None
    return dict(non_game_cores=m(oc), sys_busy_pct=m(busy), game_cores=m(game), top_thread_pct=m(top),
                gpu_util_pct=m(gpu), other_games=sorted(others))


def one(tag):
    rts = sorted(AB2.glob(f'runtime-{tag}-*'))
    runs = sorted(RUNS.glob(f'*-vk-K{tag}'))
    if not rts or not runs:
        return {'tag': tag, 'error': 'no runtime or run dir'}
    rt, run = rts[-1], runs[-1]
    entry = None
    entry_wall = None
    for l in (rt / 'timeline.jsonl').read_text(errors='replace').splitlines():
        if '"race_entry"' in l:
            j = json.loads(l)
            entry, entry_wall = j.get('hb_ms'), j.get('wall')
            break
    wl = (rt / 'wrapper.log').read_text(errors='replace') if (rt / 'wrapper.log').exists() else ''
    sha = re.search(r'sha256=([0-9a-f]{64})', wl)
    res = {'tag': tag, 'run_dir': str(run), 'runtime_dir': str(rt), 'exe_sha256': sha.group(1) if sha else None}
    m = re.search(r'exit=(\S+) controller_stop=(.*?) run_dir=.* leftover_process=(\w+)', wl)
    if m:
        res.update(exit=m.group(1), controller_stop=m.group(2), leftover=m.group(3))
    if entry is None:
        res['error'] = 'no race_entry'
        return res
    start = entry + 10000
    lines = (run / 'stderr.log').read_text(errors='replace').splitlines()
    hb, fh, sc141, sc130, hw, vw, mc, sp, tid12, ts0, ts1 = [], [], [], [], [], [], [], [], [], {}, {}
    bad_pre = bad_in = rej_in = 0
    on = False
    after_entry = False
    for l in lines:
        mm = HB.match(l)
        if mm:
            ms = int(mm.group(1))
            after_entry = ms >= entry
            if ms >= start:
                on = True
                hb.append((ms, int(mm.group(2)), int(mm.group(3))))
            continue
        if BAD.search(l) and not l.startswith('[sim-pace'):
            if after_entry:
                bad_in += 1
            else:
                bad_pre += 1
        if after_entry and (l.startswith('[mfc] REJECTED') or l.startswith('[spu-dma] SKIP')):
            rej_in += 1
        if not on:
            continue
        mm = FH.match(l)
        if mm:
            fh.append(tuple(float(x) for x in mm.groups()))
            continue
        mm = SC.match(l)
        if mm:
            d = dict((k, (float(v), int(n))) for k, v, n in re.findall(r'sc(\d+)=([\d.]+)ms/(\d+)', mm.group(3)))
            if mm.group(2) == '1':
                sc141.append(d.get('141', (0.0, 0))[0]); sc130.append(d.get('130', (0.0, 0))[0])
            elif mm.group(2) == '12':
                tid12.append(d.get('141', (0.0, 0))[1])
            continue
        mm = HW.match(l)
        if mm:
            hw.append(float(mm.group(2)))
            continue
        mm = VW.match(l)
        if mm:
            vw.append((int(mm.group(1)), float(mm.group(2))))
            continue
        mm = MC.match(l)
        if mm:
            mc.append(float(mm.group(2)))
            continue
        mm = SP.match(l)
        if mm:
            sp.append(tuple(int(x) for x in mm.groups()))
            continue
        mm = TS.match(l)
        if mm and mm.group(1) in HAVOK:
            v = (int(mm.group(2)), int(mm.group(3)))
            ts0.setdefault(mm.group(1), v)
            ts1[mm.group(1)] = v
    if len(hb) < 3:
        res['error'] = 'race window too short'
        return res
    win_s = (hb[-1][0] - hb[0][0]) / 1000.0
    fps = (hb[-1][1] - hb[0][1]) / win_s
    per_s = [(b[1] - a[1]) * 1000.0 / (b[0] - a[0]) for a, b in zip(hb, hb[1:]) if b[0] > a[0]]
    ft = 1000.0 / fps
    r = lambda x, n=2: None if x is None else round(x, n)
    draw_fps = (hb[-1][2] - hb[0][2]) / win_s   # presents that drew (frame-hist counts only these)
    res.update(window_s=r(win_s, 1), fps=r(fps), draw_fps=r(draw_fps), frame_ms_mean=r(ft),
               fps_1s_mean=r(st.mean(per_s)), fps_1s_sd=r(st.pstdev(per_s)), fps_1s_p5=r(pct(per_s, 0.05)),
               fps_1s_min=r(min(per_s)))
    if fh:
        res.update(fh_blocks=len(fh), ft_p50_med=r(st.median(x[0] for x in fh)), ft_p90_med=r(st.median(x[1] for x in fh)),
                   ft_p99_med=r(st.median(x[2] for x in fh)), ft_p99_max=r(max(x[2] for x in fh)),
                   ft_max=r(max(x[3] for x in fh)), over34_pct=r(st.mean(x[4] for x in fh)), draws=r(st.mean(x[5] for x in fh), 0),
                   ft_p95='n/a')
    pm = rt / 'presentmon.csv'
    if pm.exists():
        res.update(presentmon_frame_ms(pm))
    ms_per_frame = lambda per_s_ms: r(st.mean(per_s_ms) / fps) if per_s_ms else None
    res.update(main_usleep_ms_f=ms_per_frame(sc141), main_evq_ms_f=ms_per_frame(sc130), main_hle_ms_f=ms_per_frame(hw),
               handler_polls_s=r(st.mean(tid12), 0) if tid12 else None)
    if len(vw) >= 2:
        res['present_wait_ms_f'] = r((vw[-1][1] - vw[0][1]) / max(1, vw[-1][0] - vw[0][0]))
    if mc:
        res['main_mcyc_flip_med'] = r(st.median(mc), 1)
    if len(sp) >= 2:
        mins = win_s / 60.0
        res.update(simpace_late_per_min=r((sp[-1][1] - sp[0][1]) / mins, 0), simpace_overloads_per_min=r((sp[-1][2] - sp[0][2]) / mins, 0),
                   simpace_lost_ms_per_s=r((sp[-1][3] - sp[0][3]) / win_s, 1))
    task = {}
    for k in ts0:
        dr, dn = ts1[k][0] - ts0[k][0], ts1[k][1] - ts0[k][1]
        if dr > 0:
            task[HAVOK[k]] = {'ms_per_run': r(dn / dr / 1e6, 3), 'runs_per_frame': r(dr / win_s / fps, 2)}
    res['havok_task_stats'] = task
    res['flags'] = {'bad_lines_before_race': bad_pre, 'bad_lines_in_race': bad_in, 'dma_rejects_in_race': rej_in}
    res['host'] = host(rt, (entry_wall or 0) + 10)
    gate = []
    h = res['host']
    if h['non_game_cores'] is not None and h['non_game_cores'] >= 6:
        gate.append('CPU-STARVED')
    elif h['non_game_cores'] is not None and h['non_game_cores'] >= 4:
        gate.append('cpu-weak(>=4 cores)')
    if h['other_games']:
        gate.append('OTHER-GAME:' + ','.join(h['other_games']))
    if h['other_games'] and (h['gpu_util_pct'] or 0) >= 70:
        gate.append('GPU-CONTENDED')
    if bad_in:
        gate.append('ERRORS-IN-RACE')
    if res.get('leftover') == 'True':
        gate.append('LEFTOVER-PROCESS')
    hard = [g for g in gate if g.split(':')[0] in ('CPU-STARVED', 'OTHER-GAME', 'GPU-CONTENDED', 'ERRORS-IN-RACE', 'LEFTOVER-PROCESS')]
    res['quality'] = 'REJECT' if hard else ('WARN' if gate else 'OK')
    res['quality_reasons'] = gate
    return res


def presentmon_frame_ms(p):
    """Optional: a PresentMon 2.x CSV of the game process; MsBetweenPresents (or FrameTime) over the whole file."""
    import csv
    xs = []
    with open(p, newline='') as f:
        rd = csv.DictReader(f)
        col = next((c for c in ('MsBetweenPresents', 'FrameTime', 'msBetweenPresents') if c in (rd.fieldnames or [])), None)
        if not col:
            return {'presentmon': 'no frame-time column'}
        for row in rd:
            try:
                xs.append(float(row[col]))
            except (TypeError, ValueError):
                pass
    if not xs:
        return {'presentmon': 'empty'}
    return {'pm_frames': len(xs), 'pm_p50': round(pct(xs, .5), 2), 'pm_p95': round(pct(xs, .95), 2),
            'pm_p99': round(pct(xs, .99), 2), 'pm_mean': round(st.mean(xs), 2)}


if __name__ == '__main__':
    args = sys.argv[1:]
    out = None
    if args[:1] == ['--json']:
        out, args = Path(args[1]), args[2:]
    rows = [one(t) for t in args]
    cols = ['tag', 'exe_sha256', 'quality', 'fps', 'draw_fps', 'frame_ms_mean', 'fps_1s_sd', 'fps_1s_p5', 'ft_p50_med', 'ft_p90_med',
            'ft_p99_med', 'over34_pct', 'main_usleep_ms_f', 'main_evq_ms_f', 'present_wait_ms_f', 'handler_polls_s']
    print(' | '.join(cols))
    for x in rows:
        if 'error' in x:
            print(x['tag'], 'ERROR', x['error'])
            continue
        v = [str(x.get(c))[:8] if c == 'exe_sha256' else str(x.get(c)) for c in cols]
        print(' | '.join(v), '|', 'cores ng=%s game=%s gpu=%s%%' % (x['host']['non_game_cores'], x['host']['game_cores'], x['host']['gpu_util_pct']),
              '|', ';'.join(x['quality_reasons']), '|', ' '.join(f"{k}={v['ms_per_run']}x{v['runs_per_frame']}" for k, v in x['havok_task_stats'].items()))
    if out:
        out.write_text(json.dumps(rows, indent=1))
