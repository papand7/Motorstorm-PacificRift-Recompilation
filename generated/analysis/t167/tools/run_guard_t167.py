#!/usr/bin/env python3
"""T167: the stop conditions of a benchmark sequence. A launch script runs this before and after every launch and stops on exit 1.

  py -3 run_guard_t167.py pre  --exe <exe> --sha <pinned sha256> [--allow-remote]
  py -3 run_guard_t167.py post --run-dir <run> --controller <controller.log> --exit-code <n>
                               [--min-race-frames 500] [--min-heavy-frames 100] [--max-slow-pct 1.0]

pre:  executable hash; a remote session (T167: Present can hold the queue about 84 ms per frame in one, so timings are invalid).
post: unexpected exit code; termination other than the wall-clock cap; GcKernel::Present() Timeout; a controller error;
      device removal; Present failures; FIFO resyncs; no race_entry marker; too few race or heavy frames; too many frames in
      the 84 ms mode. Prints every failure, one per line. T162 continued after B1 because it only looked for a controller error.
"""
import argparse, hashlib, re, sys
from pathlib import Path


def sha256(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def is_remote_session():
    import ctypes
    return ctypes.windll.user32.GetSystemMetrics(0x1000) != 0    # SM_REMOTESESSION


def pre_failures(exe, sha, remote, allow_remote=False):
    out = []
    if not Path(exe).exists():
        out.append(f'executable missing: {exe}')
    elif sha256(exe).lower() != sha.lower():
        out.append(f'executable hash mismatch: {sha256(exe)} != {sha}')
    if remote and not allow_remote:
        out.append('remote session: GPU waits of about 84 ms are possible, timings are not comparable')
    return out


def read(p):
    p = Path(p)
    return p.read_text(encoding='utf-8', errors='replace') if p.exists() else ''


def race_frames(err):
    """Guest frames from the first with at least 200 draws (bench_t161), plus the 84 ms mode's share of all frames."""
    gframes, race, slow, n = set(), False, 0, 0
    for l in err.splitlines():
        if not l.startswith('[rsx-frame-perf] gframe='):
            continue
        n += 1
        m = re.search(r' wait_ms=([\d.]+)', l)
        slow += bool(m and float(m.group(1)) > 50.0)
        d = re.search(r'draw_calls=(\d+)', l)
        race = race or bool(d and int(d.group(1)) >= 200)
        if race:
            gframes.add(re.search(r'gframe=(\d+)', l).group(1))
    return len(gframes), 100.0 * slow / n if n else 0.0


def post_failures(run_dir, controller, exit_code, min_race=500, min_heavy=100, max_slow=1.0, expected_exit=(0,)):
    run_dir = Path(run_dir)
    err, out, summary, ctl = read(run_dir / 'stderr.log'), read(run_dir / 'stdout.log'), read(run_dir / 'summary.md'), read(controller)
    fails = []
    if exit_code not in expected_exit:
        fails.append(f'unexpected exit code {exit_code}')
    if not err:
        fails.append('no stderr.log')
    m = re.search(r'termination: (.*)', summary)
    if not m:
        fails.append('no termination line in summary.md')
    elif 'timeout' not in m.group(1) or 'stop_line' in m.group(1):
        fails.append(f'termination: {m.group(1).strip()[:100]}')
    if 'GcKernel::Present() Timeout' in out + err:
        fails.append('GcKernel::Present() Timeout')
    if re.search(r'^\[\s*[\d.]+\] (controller_)?error\b', ctl, re.M) or 'Traceback (most recent call last)' in ctl:
        fails.append('controller error')
    removed = [x for x in re.findall(r'removed=(0x[0-9A-Fa-f]+)', out + err) if int(x, 16)]
    if removed or 'DXGI_ERROR_DEVICE' in out + err:
        fails.append(f'D3D12 device removal ({removed[0] if removed else "DXGI_ERROR_DEVICE"})')
    if '[D3D12] Present failed' in out + err:
        fails.append('Present failed')
    resync = (out + err).count('FIFO resync')
    if resync:
        fails.append(f'{resync} FIFO resync(s)')
    if 'race_entry' not in ctl:
        fails.append('no race_entry marker')
    rf, slow = race_frames(err)
    if rf < min_race:
        fails.append(f'{rf} race frames, need {min_race}')
    elif min_heavy and rf < 600 + min_heavy:
        fails.append(f'{max(rf - 600, 0)} heavy frames, need {min_heavy}')
    if slow > max_slow:
        fails.append(f'{slow:.1f}% of frames in the 84 ms GPU-wait mode, limit {max_slow}%')
    return fails


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('mode', choices=('pre', 'post'))
    ap.add_argument('--exe')
    ap.add_argument('--sha')
    ap.add_argument('--allow-remote', action='store_true')
    ap.add_argument('--run-dir')
    ap.add_argument('--controller')
    ap.add_argument('--exit-code', type=int, default=0)
    ap.add_argument('--min-race-frames', type=int, default=500)
    ap.add_argument('--min-heavy-frames', type=int, default=100)
    ap.add_argument('--max-slow-pct', type=float, default=1.0)
    a = ap.parse_args()
    if a.mode == 'pre':
        f = pre_failures(a.exe, a.sha, is_remote_session(), a.allow_remote)
    else:
        f = post_failures(a.run_dir, a.controller, a.exit_code, a.min_race_frames, a.min_heavy_frames, a.max_slow_pct)
    for x in f:
        print('STOP:', x)
    print('guard:', 'STOP' if f else 'ok')
    return 1 if f else 0


if __name__ == '__main__':
    sys.exit(main())
