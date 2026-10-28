#!/usr/bin/env python3
"""MotorStorm wrapper around ps3recomp/tools/startup_runner.py.

  py -3 tools/fast_startup.py --target garage [--profile fast] [--capture-rsx --capture-frames 3]
  py -3 tools/fast_startup.py compare generated/runs/<A> generated/runs/<B>
  py -3 tools/fast_startup.py milestones
  py -3 tools/fast_startup.py rate generated/runs/<run>   (Bink decode frames/s)

Defaults: the trace-hooked build (tracing stays off unless PS3_TRACE is set;
build/motorstorm belongs to another workflow), generated/decrypted/EBOOT.elf,
original/game as the VFS root, runs under generated/runs/ (private). Target
aliases: init, draw, video, decoding, intro-done, garage-request, garage.

Safe stop: with no --target and no --stop-after-next the run stops at the first
garage resource request, and --timeout defaults to and may not exceed 210 s.
Any target past the garage request (anything not in SAFE_TARGETS) needs
--allow-extended, whatever the milestone config says; earlier garage workloads
were followed by unexpected host power losses.

Mandatory on every run, with or without thermal monitoring:
  - the 210 s cap (--timeout), plus an independent hard deadline that kills the
    exe's process tree HARD_GRACE_S later should the runner loop not stop it;
  - a stop at the first GPU watchdog line (GcKernel::Present() Timeout), passed
    to the runner as --stop-on-line so it does not depend on the milestone config;
  - a process-tree kill by image name after every run (no orphans);
  - no retries: --retries and --retry-before are refused;
  - evidence is kept: nothing under generated/runs, the caches or the logs is deleted.

Cache evidence: every run records the size and SHA-256 of each file under
generated/hdd1 (the FIOS cache, font copies) before launch and after the stop,
in <run>/cache_state.json; the game rewrites its FIOS cache while it runs.
--snapshot-cache also copies those files, verified by hash, to
generated/cache-snapshots/<timestamp>/ before launch (about 0.5 GB per run; it
refuses when the disk would keep less than twice that free plus 1 GB). Nothing
is ever deleted or overwritten.

Thermal monitoring is optional and off by default. --thermal-guard runs the v3
guard (tools/thermal_supervisor.py), which polls ACPI \\_TZ.TZ01 and, once asked
for, refuses to launch without a reading. TZ01 is a firmware zone, not an
identified CPU or GPU sensor; ordinary thermal protection is left to the
hardware, firmware and Windows.
"""
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'ps3recomp-int' / 'tools'))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import startup_runner  # noqa: E402

SUPERVISOR = None           # --thermal-guard: thermal_supervisor.Supervisor unless a test substitutes one
GPU_WATCHDOG_LINE = r'GcKernel::Present\(\) Timeout'
HARD_GRACE_S = 15.0
NO_WINDOW = 0x08000000

ALIASES = {'init': 'process_initialized', 'draw': 'first_original_draw', 'video': 'intro_video_opened',
           'decoding': 'intro_video_decoding', 'intro-done': 'intro_video_completed',
           'garage-request': 'garage_resources_requested', 'garage': 'garage_rendering_started'}
DEFAULT_TARGET = 'garage_resources_requested'
SAFE_TARGETS = {'process_initialized', 'first_original_draw', 'intro_video_opened', 'intro_video_decoding',
                'intro_video_completed', 'intro_video_closed', 'psarc_opened', DEFAULT_TARGET}
MAX_TIMEOUT_S = 210.0


def apply_safe_stop(argv: list[str]) -> list[str]:
    """Default to the garage-request stop and the 210 s cap; refuse to go further without opt-in."""
    argv = list(argv)
    for flag in ('--retries', '--retry-before'):
        if flag in argv:
            raise SystemExit(f'{flag}: runs are never retried automatically; each run needs its own go-ahead')
    if '--target' not in argv and '--stop-after-next' not in argv:
        argv += ['--target', DEFAULT_TARGET]
    if '--timeout' in argv:
        t = float(argv[argv.index('--timeout') + 1])
        if t > MAX_TIMEOUT_S:
            raise SystemExit(f'--timeout {t:g} exceeds the {MAX_TIMEOUT_S:g} s safety maximum')
    else:
        argv += ['--timeout', f'{MAX_TIMEOUT_S:g}']
    target = argv[argv.index('--target') + 1] if '--target' in argv else None
    if target is not None and target not in SAFE_TARGETS and '--allow-extended' not in argv:
        raise SystemExit(f'target {target} runs past the garage-request stop; pass --allow-extended')
    return argv


def kill_tree_by_name(exe_name: str) -> bool:
    """taskkill /T /F every process with this image name; True when one was found."""
    r = subprocess.run(['taskkill', '/IM', f'{exe_name}.exe', '/T', '/F'],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=NO_WINDOW)
    return r.returncode == 0


HDD1 = ROOT / 'generated' / 'hdd1'
SNAPSHOT_ROOT = ROOT / 'generated' / 'cache-snapshots'
SNAPSHOT_RESERVE = 1 << 30


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def cache_state(root: Path) -> list[dict]:
    """Size and SHA-256 of every file under root, by relative path."""
    if not root.is_dir():
        return []
    return [{'path': p.relative_to(root).as_posix(), 'size': p.stat().st_size, 'sha256': sha256_file(p)}
            for p in sorted(root.rglob('*')) if p.is_file()]


def cache_changes(before: list[dict], after: list[dict]) -> list[str]:
    b = {e['path']: e for e in before}
    a = {e['path']: e for e in after}
    out = [f'added {p} ({a[p]["size"]} bytes)' for p in sorted(a.keys() - b.keys())]
    out += [f'removed {p}' for p in sorted(b.keys() - a.keys())]
    out += [f'changed {p}: {b[p]["size"]} -> {a[p]["size"]} bytes' for p in sorted(a.keys() & b.keys())
            if a[p]['sha256'] != b[p]['sha256']]
    return out


def snapshot_cache(src: Path, state: list[dict], dest_root: Path = None, free_bytes=None) -> Path:
    """Copy the files in state from src to a new dest_root/<timestamp>/, verify each
    copy's hash, mark the copies read-only and write manifest.json. Never reuses or
    overwrites a directory; refuses (SystemExit) if disk space would run short."""
    dest_root = dest_root or SNAPSHOT_ROOT
    dest_root.mkdir(parents=True, exist_ok=True)
    total = sum(e['size'] for e in state)
    free = free_bytes() if free_bytes else shutil.disk_usage(dest_root).free
    if free - total < total + SNAPSHOT_RESERVE:
        raise SystemExit(f'--snapshot-cache: {total} bytes to copy, {free} free; '
                         f'refusing (needs twice the size plus {SNAPSHOT_RESERVE} bytes free)')
    print(f'cache snapshot: copying {len(state)} files, {total / 1e6:.1f} MB', flush=True)
    stamp = time.strftime('%Y%m%d-%H%M%S')
    dest, n = dest_root / stamp, 1
    while dest.exists():
        n += 1
        dest = dest_root / f'{stamp}-{n}'
    dest.mkdir()
    for e in state:
        to = dest / 'files' / e['path']
        to.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src / e['path'], to)
        if sha256_file(to) != e['sha256']:
            raise SystemExit(f'--snapshot-cache: copy of {e["path"]} does not match its source; nothing launched')
        os.chmod(to, stat.S_IREAD)
    (dest / 'manifest.json').write_text(json.dumps({'source': str(src), 'taken': stamp, 'files': state},
                                                   indent=1), encoding='utf-8')
    return dest


def supervisor_class():
    if SUPERVISOR is not None:
        return SUPERVISOR
    import thermal_supervisor     # only with --thermal-guard
    return thermal_supervisor.Supervisor


CONFIG = ROOT / 'tools' / 'motorstorm_milestones.json'
WAKES = re.compile(r'SPU task wakes: taskset=0x0135D080 count=(\d+) t=(\d+)ms')


def decode_rate(run_dir: Path) -> str | None:
    """Bink decode rate from cellSpurs' every-256-wakes line (present in every
    profile). One wake of the Bink taskset per decoded frame: the diagnostic
    profile counted 3160 for the 3159-frame intro."""
    try:
        text = (run_dir / 'stderr.log').read_text(encoding='utf-8', errors='replace')
    except OSError:
        return None
    pts = [(int(n), int(t)) for n, t in WAKES.findall(text)]
    if len(pts) < 2:
        return None
    (n0, t0), (n1, t1) = pts[0], pts[-1]
    fps = (n1 - n0) * 1000.0 / max(1, t1 - t0)
    steps = [(b[0] - a[0]) * 1000.0 / max(1, b[1] - a[1]) for a, b in zip(pts, pts[1:])]
    return (f'Bink decode: {fps:.2f} frames/s over frames {n0}-{n1} ({(t1 - t0) / 1000:.1f} s); '
            f'per 256-frame block {min(steps):.2f}-{max(steps):.2f} frames/s')


def main(argv):
    if not argv or argv[0] not in ('run', 'compare', 'milestones', 'rate'):
        argv = ['run', *argv]
    if argv[0] == 'rate':
        for d in argv[1:]:
            print(f'{d}: {decode_rate(Path(d)) or "no Bink decode lines"}')
        return 0
    if argv[0] == 'milestones':
        return startup_runner.main(['milestones', '--config', str(CONFIG)])
    if argv[0] == 'compare':
        return startup_runner.main(argv)
    for flag in ('--target', '--capture-at'):
        if flag in argv:
            i = argv.index(flag) + 1
            argv[i] = ALIASES.get(argv[i], argv[i])
    thermal = '--thermal-guard' in argv
    snapshot = '--snapshot-cache' in argv
    argv = [a for a in argv if a not in ('--thermal-guard', '--snapshot-cache')]
    argv = apply_safe_stop(argv)
    argv += ['--stop-on-line', GPU_WATCHDOG_LINE]
    elf = ROOT / 'generated' / 'decrypted' / 'EBOOT.elf'
    defaults = {
        'config': CONFIG,
        'exe': str(ROOT / 'build' / 'motorstorm-trace' / 'MotorStormPacificRiftRecomp.exe'),
        'runs_dir': str(ROOT / 'generated' / 'runs'),
        'hidden': True,
    }
    if '--arg' not in argv:
        argv += ['--arg', str(elf)]
    if '--hash-input' not in argv:
        argv += ['--hash-input', str(elf)]
    # /dev_hdd1 is the game's writable cache (FIOS cache, font copies). Keep it
    # out of the extracted disc tree.
    hdd1 = HDD1
    hdd1.mkdir(parents=True, exist_ok=True)
    # /dev_hdd0 likewise: without a root cellGame's content root falls back to
    # the VFS root and creates original/game/game/BLES00000/USRDIR.
    hdd0 = ROOT / 'generated' / 'hdd0'
    hdd0.mkdir(parents=True, exist_ok=True)
    env = [f"PS3_VFS_ROOT={ROOT / 'original' / 'game'}", f"PS3_HDD1_ROOT={hdd1}",
           f"PS3_HDD0_ROOT={hdd0}"]
    for e in env:
        argv += ['--env', e]
    exe = Path(argv[argv.index('--exe') + 1]) if '--exe' in argv else Path(defaults['exe'])
    timeout = float(argv[argv.index('--timeout') + 1])
    # Cache evidence before anything is launched (a failed snapshot launches nothing).
    cache_before = cache_state(hdd1)
    snap_dir = snapshot_cache(hdd1, cache_before) if snapshot else None
    if snap_dir:
        print(f'cache snapshot: {snap_dir}', flush=True)
    started = time.time()
    sup, guard = None, None
    if thermal:
        guard_csv = ROOT / 'generated' / 'profile' / 'guard' / f'{time.strftime("%Y%m%d-%H%M%S")}-thermal.csv'
        print(f'thermal monitor: ON (guard v3, ACPI TZ01, {guard_csv})', flush=True)
        # Asked for, so fail closed: GuardError (a SystemExit) ends this call with nothing launched.
        sup = supervisor_class()(exe.stem, guard_csv, max_run_s=timeout).start()
    else:
        print('thermal monitor: off (default; --thermal-guard enables it)', flush=True)
    fired = threading.Event()

    def hard_deadline():
        fired.set()
        kill_tree_by_name(exe.stem)
    timer = threading.Timer(timeout + HARD_GRACE_S, hard_deadline)
    timer.daemon = True
    timer.start()
    try:
        code = startup_runner.main(argv, defaults)
    finally:
        timer.cancel()
        if sup is not None:
            guard = sup.stop()
        leftovers = kill_tree_by_name(exe.stem)      # nothing outlives the run
    cache_after = cache_state(hdd1)
    changes = cache_changes(cache_before, cache_after)
    safeguards = {'timeout_s': timeout, 'hard_deadline_s': timeout + HARD_GRACE_S,
                  'hard_deadline_fired': fired.is_set(), 'stop_on_line': [GPU_WATCHDOG_LINE],
                  'leftover_processes_killed': leftovers, 'retries': 0,
                  'thermal_monitor': 'on' if thermal else 'off',
                  'cache_snapshot': str(snap_dir) if snap_dir else None}
    if fired.is_set():
        print(f'hard deadline: process tree killed at {timeout + HARD_GRACE_S:g} s', flush=True)
        code = code or 3
    if guard and guard['stop_reason']:
        print(f"thermal supervisor stop: {guard['stop_reason']}: {guard['detail']}", flush=True)
        code = code or 3
    runs = Path(argv[argv.index('--runs-dir') + 1]) if '--runs-dir' in argv else Path(defaults['runs_dir'])
    new = [d for d in runs.glob('*') if d.is_dir() and d.stat().st_mtime >= started - 1]
    if new:
        run_dir = max(new, key=lambda d: d.stat().st_mtime)
        (run_dir / 'safeguards.json').write_text(json.dumps(safeguards, indent=1), encoding='utf-8')
        with open(run_dir / 'summary.md', 'a', encoding='utf-8') as f:
            f.write(f"\n## Wrapper safeguards\n\ntimeout {timeout:g} s; hard deadline "
                    f"{'FIRED' if fired.is_set() else 'not reached'}; GPU watchdog stop armed; "
                    f"leftover processes killed: {leftovers}; thermal monitor {safeguards['thermal_monitor']}\n")
        (run_dir / 'cache_state.json').write_text(json.dumps(
            {'root': str(hdd1), 'snapshot': safeguards['cache_snapshot'], 'before': cache_before,
             'after': cache_after, 'changes': changes}, indent=1), encoding='utf-8')
        with open(run_dir / 'summary.md', 'a', encoding='utf-8') as f:
            f.write(f"\n## Cache (generated/hdd1)\n\nsnapshot: {safeguards['cache_snapshot'] or 'none'}; "
                    f"changes: {'; '.join(changes) or 'none'}\n")
        if guard:
            (run_dir / 'thermal_guard.json').write_text(json.dumps(guard, indent=1), encoding='utf-8')
            with open(run_dir / 'summary.md', 'a', encoding='utf-8') as f:
                f.write(f"\n## Thermal supervisor\n\nguard {guard['guard']}, {guard['samples']} samples, "
                        f"{guard['tz_min_K']}-{guard['tz_max_K']} K; stop: {guard['stop_reason'] or 'none'} "
                        f"{guard['detail']}\n")
        rate = decode_rate(run_dir)
        if rate:
            print(rate, flush=True)
            with open(run_dir / 'summary.md', 'a', encoding='utf-8') as f:
                f.write(f'\n## Decode rate\n\n{rate}\n')
    return code


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
