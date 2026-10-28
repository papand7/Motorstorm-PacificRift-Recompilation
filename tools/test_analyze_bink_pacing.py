#!/usr/bin/env python3
"""Deterministic test of tools/analyze_bink_pacing.py on a synthetic run that
follows the native Bink rule (docs/BINK_PLAYBACK_SCHEDULER.md): a decoder at
28.4 fps plays 1:1 until two frames late, then 4:1 until 725 ms late, then
resyncs (audio Stop/Start, epoch cleared), and a 31 fps stretch catches up."""
import csv, io, json, os, sys, tempfile, contextlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import analyze_bink_pacing as A

FR = A.FRAME_MS


def simulate(segments):
    """segments: list of decode fps per second. Returns timeline rows and the
    number of resyncs the native rule performs."""
    t, n, seq, present, flips = 1_000_000.0, 0, 0, 0, 0   # ms
    epoch_t, epoch_n, skips, resyncs = None, 0, 0, 0
    rows = []
    for fps in segments:
        for _ in range(int(fps)):
            t += 1000.0 / fps
            n += 1
            if epoch_t is None:
                epoch_t, epoch_n = t, n
            late = (t - epoch_t) - (n - epoch_n) * FR
            if late > A.RESYNC_MS:
                resyncs += 1
                epoch_t, epoch_n = t, n            # cleared, re-armed this frame
                late = 0
            if late > A.SKIP_MS and skips < A.MAX_SKIPS:
                skips += 1                          # decoded, not drawn
                continue
            skips = 0
            present += 1; flips += 1; seq += 1
            rows.append((int(t * 1000), present, flips, present * 2, n, seq))
    return rows, resyncs


def main():
    segs = [28.4] * 16 + [31.0] * 8 + [28.4] * 30 + [29.0] * 2
    rows, resyncs = simulate(segs)
    d = tempfile.mkdtemp()
    tl = os.path.join(d, 't.csv')
    with open(tl, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['t_us', 'present', 'flips', 'vblanks', 'decoded', 'video', 'new', 'stale',
                    'content_seq', 'present_us', 'fence_us'])
        for t_us, p, fl, vb, n, seq in rows:
            w.writerow([t_us, p, fl, vb, n, 1, 1, 0, seq, 1000, 10])
    log = os.path.join(d, 'stdout.log')
    with open(log, 'w') as f:
        f.write('[cellAudio] PortStart(port=1)\n')
        for _ in range(resyncs):
            f.write('[cellAudio] PortStop(port=1)\n[cellAudio] PortStart(port=1)\n')
        f.write('[cellAudio] PortStop(port=1)\n[cellAudio] PortClose(port=1)\n')
    ft = os.path.join(d, 'ft.txt')
    with open(ft, 'w') as f:
        f.write('# ps3_ftrace\n9 0 0 0 1000.0 1000.0\n10 0 0 0 1008.0 1009.0\n'
                '9 0 1 0 2000.0 2000.0\n9 0 0 0 3000.0 3000.0\n10 0 0 0 3006.0 3007.0\n')
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        A.main(['--timeline', tl, '--log', log, '--ftrace', ft, '--summary'])
    s = json.loads(out.getvalue())
    checks = 0

    def check(cond, msg):
        nonlocal checks
        checks += 1
        if not cond:
            print('FAIL:', msg, file=sys.stderr)
            sys.exit(1)

    check(resyncs >= 2, 'simulation must resync')
    check(s['resyncs_inferred'] == resyncs, f"inferred {s['resyncs_inferred']} != {resyncs}")
    check(s['audio']['stop_start_pairs'] == resyncs, 'stop/start pairs exclude the final stop')
    check(s['catchups_inferred'] >= 1, 'the 31 fps stretch catches up')
    check(s['rule_agreement']['fraction'] >= 0.9, 'replayed rule agrees with the simulated one')
    h = s['advance_histogram']
    check((h.get('1', 0) + h.get('4', 0)) >= 0.95 * sum(h.values()), 'advances are 1:1 or 4:1')
    check('4:1' in s['modes'] and '1:1' in s['modes'], 'both modes present')
    check(abs(s['intro']['decoded_fps'] - 28.6) < 0.5, 'decode rate')
    for r in s['skip_stretches']:
        if r['exit'] == 'resync':
            check(r['lateness_last_ms'] > A.RESYNC_MS - 3 * FR, 'resync stretches end near 725 ms')
    check(s['ftrace_flips']['requests'] == 3 and s['ftrace_flips']['presents'] == 2, 'ftrace counts')
    check(len(s['ftrace_flips']['requests_without_own_present']) == 1, 'one coalesced request')
    check(s['ftrace_flips']['requests_without_own_present'][0]['next_present_ms'] == 3.0,   # ftrace is in us
          'next present after the coalesced request')
    check(any('ShouldSkip' in m for m in s['missing']), 'missing instrumentation listed')
    print(f'{checks} analyze_bink_pacing checks PASS')


if __name__ == '__main__':
    main()
