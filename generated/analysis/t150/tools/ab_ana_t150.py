"""T150: one A/B run's renderer evidence as JSON (for the PROPOSED bounded game A/B).

  py -3 ana_t150.py <rtdir> <run_dir>

- race FPS / frame-time spread: t122/ab/ana_t122.py;
- main-thread phases and the critical path: t149/ab/ana_t149.py (cpath_report on <rtdir>/cpath.txt);
- [tex-snapshot-stats] (PS3_TEX_SNAPSHOT_STATS=1000): per-frame captures by answer, MB hashed/copied, ms in
  capture/write-watch/hash/copy, write-watch state, keys; medians over the race windows;
- [rsx-frame-perf] medians over the race: drain, expand, rf, record (tex/pso/cmd), other;
- trace_covers_race: the trace window (host s 175..240) starts at least 10 s after race entry."""
import json, re, statistics as S, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
A = HERE.parents[1]


def run_json(script, *args):
    p = subprocess.run([sys.executable, str(script), *map(str, args)], capture_output=True, text=True)
    try:
        return json.loads(p.stdout[p.stdout.index('{'):])
    except ValueError:
        return {'error': (p.stdout + p.stderr)[-400:]}


def stats_lines(log, tag, rx):
    out = []
    for l in open(log, encoding='utf-8', errors='replace'):
        if l.startswith(tag):
            d = {k: float(v) for k, v in rx.findall(l)}
            for k, r in (('tex', r'\[tex ([0-9.]+)'), ('pso', r'\| pso ([0-9.]+)'), ('cmd', r'\| cmd ([0-9.]+)\]')):
                mm = re.search(r, l)
                if mm:
                    d[k] = float(mm[1])
            out.append(d)
    return out


NUM = re.compile(r'([a-z_]+)=(-?[0-9.]+)')


def medians(rows, keys):
    return {k: round(S.median(r[k] for r in rows if k in r), 3) for k in keys if any(k in r for r in rows)}


if __name__ == '__main__':
    rtdir, run_dir = Path(sys.argv[1]), Path(sys.argv[2])
    log = run_dir / 'stderr.log'
    res = {'run': run_dir.name}
    res['fps'] = {k: v for k, v in run_json(A / 't122/ab/ana_t122.py', run_dir).items()
                  if k in ('frames', 'fps', 'fps_xs', 'frame_ms_p50_p95_p99_max', 'frame_ms_stdev_xs', 'error')}
    t149 = run_json(A / 't149/ab/ana_t149.py', rtdir, run_dir)
    res['phases'] = t149.get('phases')
    c = t149.get('cpath') or {}
    res['cpath'] = {k: c.get(k) for k in ('frame_thread', 'rsx', 'host_cpu_ms', 'critical')}
    ts = stats_lines(log, '[tex-snapshot-stats]', NUM)
    race = ts[-80:-5] if len(ts) > 90 else ts
    res['tex_snapshot'] = medians(race, ['captures', 'epoch_skips', 'ww_skips', 'hash_reuses', 'copies', 'hashed_mb',
                                         'copied_mb', 'allocs', 'total', 'ww', 'hash', 'copy', 'checks', 'dirty_pages',
                                         'state', 'evicted', 'torn', 'failed'])
    res['tex_snapshot']['windows'] = len(race)
    fp = stats_lines(log, '[rsx-frame-perf]', NUM)
    race = fp[-400:]
    res['rsx_frame_perf'] = medians(race, ['wall_ms', 'drain_ms', 'expand_ms', 'rf_ms', 'record_ms', 'tex', 'pso',
                                           'cmd', 'submit_ms', 'wait_ms', 'present_ms', 'other_ms', 'draw_calls'])
    ctl = (rtdir / 'controller.log').read_text(encoding='utf-8', errors='replace') if (rtdir / 'controller.log').exists() else ''
    m = re.findall(r'\[\s*([0-9.]+)\] stop \{"why": "race entry \+ 90 s"\}', ctl)
    entry = float(m[-1]) - 90.0 if m else None
    res['race_entry_s'] = entry
    res['trace_covers_race'] = entry is not None and entry <= 165.0
    print(json.dumps(res, indent=1))
