#!/usr/bin/env python3
"""Fail-closed thermal supervision for a game run (private).

Optional: fast_startup.py uses a Supervisor only with --thermal-guard (off by default).
ACPI zone TZ01 is a firmware zone, not an identified CPU or GPU sensor; this is a
diagnostic, not comprehensive hardware protection.

  1. start(): launches thermal_guard_v3.ps1 for the target's process name and waits
     for its first valid temperature sample. If the guard cannot start or never
     reports a temperature, GuardError is raised and the caller launches nothing.
  2. While the run lasts, a monitor thread kills the target's process tree when
     - the guard process exits (thermal_guard_exited),
     - the guard's CSV heartbeat stops growing for stale_s (thermal_guard_stale:
       a blocked sensor read or a hung guard),
     - max_run_s plus a grace period passes (max_runtime; the runner's own
       --timeout normally stops the run first).
     The guard itself kills on 363 K, an 8 K rise within 12 s, or two samples
     without a reading; the supervisor reports those as thermal_kill.
  3. stop(): ends the guard and returns the stop record.

Only the v3 guard can be used: the script must carry GUARD_MARKER. v1 compared an
empty reading and never killed; v2 needed ~7 s per sample.
"""
import os
import subprocess
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GUARD = ROOT / 'generated' / 'profile' / 'thermal_guard_v3.ps1'
GUARD_MARKER = '# GUARD_VERSION: 3 fail-closed'
MAX_RUN_S = 210.0
NO_WINDOW = 0x08000000


class GuardError(SystemExit):
    pass


def kill_tree_by_name(exe_name: str):
    subprocess.run(['taskkill', '/IM', f'{exe_name}.exe', '/T', '/F'],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=NO_WINDOW)


def kill_tree_by_pid(pid: int):
    subprocess.run(['taskkill', '/PID', str(pid), '/T', '/F'],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=NO_WINDOW)


def check_guard_script(path: Path):
    try:
        head = path.read_text(encoding='utf-8', errors='replace').splitlines()[:1]
    except OSError as e:
        raise GuardError(f'thermal guard not readable: {path} ({e})')
    if head != [GUARD_MARKER]:
        raise GuardError(f'{path.name} is not the fail-closed v3 guard (first line must be {GUARD_MARKER!r})')


class Supervisor:
    def __init__(self, exe_name: str, csv: Path, guard: Path = GUARD, start_timeout_s: float = 20.0,
                 stale_s: float = 6.0, max_run_s: float = MAX_RUN_S, grace_s: float = 15.0,
                 guard_args: tuple = (), poll_s: float = 0.5):
        if max_run_s > MAX_RUN_S:
            raise GuardError(f'max_run_s {max_run_s:g} exceeds {MAX_RUN_S:g}')
        self.exe_name, self.csv, self.guard = exe_name, Path(csv), Path(guard)
        self.start_timeout_s, self.stale_s, self.max_run_s, self.grace_s = start_timeout_s, stale_s, max_run_s, grace_s
        self.guard_args, self.poll_s = list(guard_args), poll_s
        self.proc = None
        self.reason = None          # first stop cause the supervisor saw
        self.detail = ''
        self.kills = []             # KILLED lines written by the guard
        self._stop = threading.Event()
        self._thread = None
        self.started_at = None

    # -- start ------------------------------------------------------------
    def _rows(self):
        try:
            with open(self.csv, encoding='utf-8', errors='replace') as f:
                return f.read().splitlines()[1:]
        except OSError:
            return []

    def start(self):
        check_guard_script(self.guard)
        self.csv.parent.mkdir(parents=True, exist_ok=True)
        if self.csv.exists():
            self.csv.unlink()
        cmd = ['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(self.guard),
               '-Csv', str(self.csv), '-ExeName', self.exe_name,
               '-Seconds', str(int(self.max_run_s + self.grace_s + 30)), *self.guard_args]
        try:
            self.proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                         creationflags=NO_WINDOW)
        except OSError as e:
            raise GuardError(f'thermal guard failed to start: {e}')
        deadline = time.monotonic() + self.start_timeout_s
        while time.monotonic() < deadline:
            for row in self._rows():
                cols = row.split(',')
                try:
                    if len(cols) > 1 and float(cols[1]) > 0:
                        self.started_at = time.monotonic()
                        self._thread = threading.Thread(target=self._monitor, daemon=True)
                        self._thread.start()
                        return self
                except ValueError:
                    pass
            if self.proc.poll() is not None:
                break
            time.sleep(0.2)
        self._end_guard()
        raise GuardError('thermal guard gave no valid temperature reading within '
                         f'{self.start_timeout_s:g} s; nothing was launched')

    # -- monitor ----------------------------------------------------------
    def _trip(self, reason: str, detail: str):
        if self.reason is None:
            self.reason, self.detail = reason, detail
        kill_tree_by_name(self.exe_name)

    def _monitor(self):
        last_size, last_change = -1, time.monotonic()
        while not self._stop.wait(self.poll_s):
            now = time.monotonic()
            for row in self._rows():
                if 'KILLED' in row and row not in self.kills:
                    self.kills.append(row)
                    if self.reason is None:
                        self.reason, self.detail = 'thermal_kill', row.split(',')[-1]
            if self.proc.poll() is not None:
                self._trip('thermal_guard_exited', f'guard exited with code {self.proc.returncode}')
                continue
            try:
                size = os.stat(self.csv).st_size
            except OSError:
                size = -1
            if size != last_size:
                last_size, last_change = size, now
            elif now - last_change > self.stale_s:
                self._trip('thermal_guard_stale', f'no guard sample for {now - last_change:.1f} s')
            if now - self.started_at > self.max_run_s + self.grace_s:
                self._trip('max_runtime', f'supervisor limit {self.max_run_s:g} s + {self.grace_s:g} s grace')

    # -- stop -------------------------------------------------------------
    def _end_guard(self):
        if self.proc and self.proc.poll() is None:
            kill_tree_by_pid(self.proc.pid)
            try:
                self.proc.wait(10)
            except subprocess.TimeoutExpired:
                pass

    def stop(self) -> dict:
        self._stop.set()
        if self._thread:
            self._thread.join(5)
        for row in self._rows():                       # a kill the monitor had not polled yet
            if 'KILLED' in row and row not in self.kills:
                self.kills.append(row)
                if self.reason is None:
                    self.reason, self.detail = 'thermal_kill', row.split(',')[-1]
        self._end_guard()
        temps = []
        for row in self._rows():
            try:
                temps.append(float(row.split(',')[1]))
            except (ValueError, IndexError):
                pass
        return {'guard': self.guard.name, 'guard_marker': GUARD_MARKER, 'csv': str(self.csv),
                'stop_reason': self.reason, 'detail': self.detail, 'kills': self.kills,
                'samples': len(temps), 'tz_min_K': min(temps, default=None), 'tz_max_K': max(temps, default=None)}
