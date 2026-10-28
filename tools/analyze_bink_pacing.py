#!/usr/bin/env python3
"""Offline Bink intro pacing analysis of a saved MotorStorm run.

Reads only what the runs already logged, line by line (no whole-file loads):
  --timeline  PS3_VIDEO_STATS_TIMELINE CSV: one row per backend present with
              cumulative flips, vblanks, decoded (Bink SPU frames) and
              content_seq (unique video frames uploaded)
  --log       runner stderr/stdout (repeatable): [vstat], [astat],
              [cellAudio] PortStop/PortStart, SPU task wakes
  --ftrace    PS3_FTRACE text (flip request / present instants)
  --texsnap   texsnap_sampler.py CSV (snapshot counters)

and replays the native Bink skip rule (docs/BINK_PLAYBACK_SCHEDULER.md,
ShouldSkip 0xC6F088 / NextFrame 0xC6ED28) over the logged (time, decoded)
pairs:

  lateness_ms = (now - epoch_t) - (frame - epoch_frame) * 1000 * 1001 / 30000
  late        = lateness > 2000 * 1001 / 30000   (66.7 ms, +0x2C8)
  resync      = lateness > 725                   (+0x338 -> sound pause,
                                                  epoch cleared)

The replay uses the decode counter as the frame number, so it is accurate to
about one frame (the decoder runs one frame ahead of the one shown). It is a
consistency check of the recovered rule against the run, not a substitute for
guest-side instrumentation; missing inputs are listed under "missing".

Output: JSON (default, compact with --summary) or per-present CSV (--csv).
"""
import argparse, csv, json, re, sys

FRAME_MS = 1000.0 * 1001 / 30000          # 29.97 fps intro (FrameRate 30000 / Div 1001)
SKIP_MS = 2000.0 * 1001 / 30000           # +0x2C8: 66.7 ms
RESYNC_MS = 725.0                         # cmpwi 725 at 0xC6F1D8 / 0xC6F030
MAX_SKIPS = 3                             # +0x340 cmplwi 2 -> 3 skips, then show

RX_VSTAT = re.compile(r'\[vstat\] t=(\d+)ms decoded=([\d.]+)/s.*?new_video=([\d.]+)/s.*?'
                      r'torn=(\d+) advance=([\d.]+) flips=([\d.]+)/s vblank=([\d.]+)/s')
RX_WAKES = re.compile(r'SPU task wakes: taskset=(0x[0-9A-Fa-f]+) count=(\d+) t=(\d+)ms')
RX_PORT = re.compile(r'\[cellAudio\] Port(Stop|Start)\(port=(\d+)\)')
RX_ASTAT = re.compile(r'\[astat\].*?drift_ms=([-+\d.]+).*?dropped=(\d+)')


def read_timeline(path):
    rows = []
    with open(path, newline='') as f:
        for r in csv.DictReader(f):
            try:
                rows.append((int(r['t_us']), int(r['present']), int(r['flips']), int(r['vblanks']),
                             int(r['decoded']), int(r['content_seq'])))
            except (KeyError, ValueError):
                continue
    return rows


def read_logs(paths):
    out = {'vstat': [], 'wakes': [], 'port_stop': {}, 'port_start': {}, 'port_order': [],
           'astat_drift': [], 'astat_dropped': 0}
    for p in paths:
        with open(p, errors='replace') as f:
            for line in f:
                if line.startswith('[vstat]'):
                    m = RX_VSTAT.search(line)
                    if m:
                        out['vstat'].append(tuple(float(x) for x in m.groups()))
                elif 'SPU task wakes' in line:
                    m = RX_WAKES.search(line)
                    if m:
                        out['wakes'].append((m.group(1), int(m.group(2)), int(m.group(3))))
                elif line.startswith('[cellAudio] Port'):
                    m = RX_PORT.search(line)
                    if m:
                        d = out['port_stop' if m.group(1) == 'Stop' else 'port_start']
                        d[m.group(2)] = d.get(m.group(2), 0) + 1
                        out['port_order'].append(m.group(1)[2] + m.group(2))
                elif line.startswith('[astat]'):
                    m = RX_ASTAT.search(line)
                    if m:
                        out['astat_drift'].append(float(m.group(1)))
                        out['astat_dropped'] += int(m.group(2))
    return out


def read_ftrace(path):
    """Flip request (kind 9) / present (kind 10) instants, in ms."""
    ev = []
    with open(path) as f:
        for line in f:
            p = line.split()
            if len(p) >= 6 and p[0] in ('9', '10'):
                ev.append((float(p[4]) / 1000.0, 'R' if p[0] == '9' else 'P', int(p[2])))
    ev.sort()
    unmatched = []
    lat = []
    for i, (t, k, buf) in enumerate(ev):
        if k == 'R':
            if i + 1 < len(ev) and ev[i + 1][1] == 'P':
                lat.append(ev[i + 1][0] - t)
            else:
                nxt = next((e for e in ev[i + 1:] if e[1] == 'P'), None)
                unmatched.append({'t_ms': round(t, 1), 'buffer': buf,
                                  'next_present_ms': round(nxt[0], 1) if nxt else None})
    lat.sort()
    return {'requests': sum(1 for e in ev if e[1] == 'R'), 'presents': sum(1 for e in ev if e[1] == 'P'),
            'latency_ms_median': round(lat[len(lat) // 2], 1) if lat else None,
            'latency_ms_max': round(lat[-1], 1) if lat else None,
            'requests_without_own_present': unmatched}


def replay(rows):
    """Per present: observed advance (decoded frames since the previous present)
    and whether it showed a new video frame."""
    out = []
    intro = [r for r in rows if r[4] > 0]
    if not intro:
        return out
    prev_n, prev_seq = intro[0][4], intro[0][5]
    for t_us, present, flips, vbl, n, seq in intro:
        out.append({'t_ms': t_us / 1000.0, 'present': present, 'flips': flips, 'decoded': n,
                    'advance': n - prev_n, 'new': seq - prev_seq})
        prev_n, prev_seq = n, seq
    return out


def skip_runs(per, min_len=5):
    """4:1 stretches: >= min_len consecutive new-frame presents advancing >= 3."""
    shown = [p for p in per if p['new'] > 0]
    runs, i = [], 0
    while i < len(shown):
        if shown[i]['advance'] >= 3:
            j = i
            while j < len(shown) and shown[j]['advance'] >= 3:
                j += 1
            if j - i >= min_len:
                runs.append((i, j))
            i = j
        else:
            i += 1
    return shown, runs


def anchored_lateness(per):
    """Replay the native lateness over the shown presents. The epoch is
    re-armed only where the player resynced: at the end of a 4:1 stretch whose
    replayed lateness reached the resync threshold (less a tolerance for the
    decode counter running up to two frames ahead). A stretch that ends below
    it caught up, and the epoch carries on, as natively. Annotates each present
    with lateness_ms / late and returns per-stretch records."""
    shown, runs = skip_runs(per)
    if not shown:
        return []
    tol = RESYNC_MS - 2 * FRAME_MS - 20
    ends = {e - 1: (a, e) for a, e in runs}
    ep_t, ep_n = shown[0]['t_ms'], shown[0]['decoded']
    t0 = shown[0]['t_ms']
    recs, rearm = [], False
    for k, p in enumerate(shown):
        if rearm:
            ep_t, ep_n, rearm = p['t_ms'], p['decoded'], False
        p['lateness_ms'] = round((p['t_ms'] - ep_t) - (p['decoded'] - ep_n) * FRAME_MS, 1)
        p['late'] = p['lateness_ms'] > SKIP_MS
        if k in ends:
            a, e = ends[k]
            first, dt = shown[a], (p['t_ms'] - shown[a]['t_ms']) / 1000.0
            exit_ = ('end' if e >= len(shown) else          # ran to the end of the movie
                     'resync' if p['lateness_ms'] >= tol else 'catch-up')
            recs.append({'start_s': round((first['t_ms'] - t0) / 1000.0, 1),
                         'end_s': round((p['t_ms'] - t0) / 1000.0, 1),
                         'lateness_enter_ms': first['lateness_ms'], 'lateness_last_ms': p['lateness_ms'],
                         'decode_fps': round((p['decoded'] - first['decoded']) / dt, 2) if dt > 0 else None,
                         'exit': exit_})
            rearm = exit_ == 'resync'
    return recs


def summarize(per, rows, logs, ft, snap):
    s = {}
    if per:
        t0, t1 = per[0]['t_ms'], per[-1]['t_ms']
        dec = per[-1]['decoded'] - per[0]['decoded']
        dur = (t1 - t0) / 1000.0
        shown = [p for p in per if p['new'] > 0]
        s['intro'] = {'seconds': round(dur, 1), 'decoded': dec, 'decoded_fps': round(dec / dur, 2) if dur else None,
                      'unique_shown': sum(p['new'] for p in per),
                      'unique_fps': round(sum(p['new'] for p in per) / dur, 2) if dur else None,
                      'presents_with_new_frame': len(shown)}
        adv = {}
        for p in shown:
            adv[p['advance']] = adv.get(p['advance'], 0) + 1
        s['advance_histogram'] = {str(k): v for k, v in sorted(adv.items())}
        recs = anchored_lateness(per)
        s['skip_stretches'] = recs
        s['resyncs_inferred'] = sum(1 for r in recs if r['exit'] == 'resync')
        s['catchups_inferred'] = sum(1 for r in recs if r['exit'] == 'catch-up')
        agree = tot = 0
        for p in shown:
            if p['advance'] in (1, 4) and 'late' in p:
                tot += 1
                agree += (p['advance'] == 4) == p['late']
        s['rule_agreement'] = {'presents_compared': tot, 'agree': agree,
                               'fraction': round(agree / tot, 3) if tot else None}
        # 1:1 <-> 4:1 transitions (runs of equal mode over shown presents)
        runs, cur, start = [], None, None
        for p in shown:
            mode = '4:1' if p['advance'] >= 3 else '1:1' if p['advance'] == 1 else 'other'
            if mode != cur:
                if cur is not None:
                    runs.append((cur, start, p['t_ms']))
                cur, start = mode, p['t_ms']
        if cur is not None:
            runs.append((cur, start, per[-1]['t_ms']))
        dur_by = {}
        for m, x, y in runs:
            dur_by.setdefault(m, []).append((y - x) / 1000.0)
        s['modes'] = {m: {'stretches': len(v), 'seconds': round(sum(v), 1),
                          'longest_s': round(max(v), 1)} for m, v in dur_by.items()}
        s['transitions'] = len(runs) - 1 if runs else 0
        lat = [p['lateness_ms'] for p in shown if 'lateness_ms' in p]
        s['lateness_ms_max'] = max(lat) if lat else None
        # per-second
        sec = {}
        for p in per:
            k = int((p['t_ms'] - t0) // 1000)
            d = sec.setdefault(k, [None, None, 0])
            d[0] = p['decoded'] if d[0] is None else d[0]
            d[1] = p['decoded']
            d[2] += p['new']
        s['per_second'] = [{'s': k, 'decoded': v[1] - v[0], 'new': v[2]} for k, v in sorted(sec.items())]
    if logs:
        vi = [v for v in logs['vstat'] if v[1] > 0]
        s['vstat_windows'] = {'intro': len(vi),
                              'pure_4to1': sum(1 for v in vi if abs(v[5 - 1] - 4.0) < 0.005),
                              'torn': int(sum(v[3] for v in logs['vstat'])),
                              'vblank_hz_mean': round(sum(v[6] for v in logs['vstat'] if v[6] > 0) /
                                                      max(1, sum(1 for v in logs['vstat'] if v[6] > 0)), 2)}
        o = logs['port_order']
        pairs = sum(1 for x, y in zip(o, o[1:]) if x[0] == 'o' and y[0] == 'a' and x[1:] == y[1:])
        s['audio'] = {'port_stop': logs['port_stop'], 'port_start': logs['port_start'],
                      'stop_start_pairs': pairs,
                      'astat_drift_ms_minmax': [min(logs['astat_drift']), max(logs['astat_drift'])]
                      if logs['astat_drift'] else None, 'dropped': logs['astat_dropped']}
        w = [x for x in logs['wakes'] if x[0].lower() == '0x0135d080']
        s['decode_blocks_fps'] = [round((b[1] - a[1]) * 1000.0 / (b[2] - a[2]), 2)
                                  for a, b in zip(w, w[1:]) if b[2] > a[2]]
    if ft:
        s['ftrace_flips'] = ft
    if snap:
        s['texsnap'] = snap
    s['missing'] = missing(rows, logs, ft, snap)
    return s


def read_snap(path):
    last = None
    with open(path) as f:
        for line in f:
            if line[:1].isdigit():
                last = line.strip().split(',')
    if not last:
        return None
    k = ['t_s', 'seq', 'copies', 'reuses', 'evicted', 'torn', 'failed', 'keys', 'gens', 'max_bytes']
    return dict(zip(k, [float(last[0])] + [int(x) for x in last[1:]]))


def missing(rows, logs, ft, snap):
    m = []
    if not rows:
        m.append('timeline: no per-present CSV (PS3_VIDEO_STATS_TIMELINE)')
    if not ft:
        m.append('ftrace: no flip request/present instants')
    if snap is None:
        m.append('texsnap: no snapshot counters')
    # always missing in existing runs (no instrumentation exists yet)
    m += ['guest Bink clock: lateness is replayed from host time, not read from bink+0x2C0/0x2B4',
          'per-frame decode start/end (DoFrameAsync 0xC70540 / completion poll 0xC70318)',
          'ShouldSkip (0xC6F088) result per frame and skip counter +0x340',
          'resync timestamps (NextFrame 0xC6EED8 path); PortStop/Start lines carry no time',
          'SPU job spans (PS3_FT_SPU_BUSY not emitted for the Bink taskset)',
          'present attempts skipped for has_display=0 (no counter)']
    return m


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--timeline')
    ap.add_argument('--log', action='append', default=[])
    ap.add_argument('--ftrace')
    ap.add_argument('--texsnap')
    ap.add_argument('--summary', action='store_true', help='compact JSON: drop per-second rows')
    ap.add_argument('--csv', help='write the per-present replay here')
    a = ap.parse_args(argv)
    rows = read_timeline(a.timeline) if a.timeline else []
    logs = read_logs(a.log) if a.log else None
    ft = read_ftrace(a.ftrace) if a.ftrace else None
    snap = read_snap(a.texsnap) if a.texsnap else None
    per = replay(rows)
    if a.csv:
        with open(a.csv, 'w', newline='') as f:
            w = csv.writer(f)
            s = summarize(per, rows, logs, ft, snap)
            w.writerow(['t_ms', 'present', 'flips', 'decoded', 'advance', 'new', 'lateness_ms', 'late'])
            for p in per:
                w.writerow([round(p['t_ms'], 1), p['present'], p['flips'], p['decoded'], p['advance'],
                            p['new'], p.get('lateness_ms', ''), int(p.get('late', 0))])
    else:
        s = summarize(per, rows, logs, ft, snap)
    if a.summary:
        s.pop('per_second', None)
        s.pop('decode_blocks_fps', None)
    json.dump(s, sys.stdout, indent=None if a.summary else 1)
    sys.stdout.write('\n')
    return 0


if __name__ == '__main__':
    sys.exit(main())
