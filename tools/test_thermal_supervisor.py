#!/usr/bin/env python3
"""Thermal supervisor + guard v3 against a dummy process tree (no game launch).

The dummy is a renamed cmd.exe copy running a PING child, so tree kills are
visible. The guard reads its temperature from a file (-TzFile) the test edits.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import thermal_supervisor as ts  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / 'generated' / 'runs'
NAME = 'tg_sup_dummy'
NO_WINDOW = 0x08000000


def alive(pid: int) -> bool:
    out = subprocess.run(['tasklist', '/FI', f'PID eq {pid}', '/NH'], capture_output=True, text=True).stdout
    return str(pid) in out


def children(pid: int) -> list[int]:
    out = subprocess.run(['powershell', '-NoProfile', '-Command',
                          f"(Get-CimInstance Win32_Process -Filter 'ParentProcessId={pid}').ProcessId"],
                         capture_output=True, text=True).stdout
    return [int(x) for x in out.split() if x.isdigit()]


def named_left() -> int:
    out = subprocess.run(['tasklist', '/FI', f'IMAGENAME eq {NAME}.exe', '/NH'], capture_output=True, text=True).stdout
    return out.count(f'{NAME}.exe')


class SupervisorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runs_before = sorted(os.listdir(RUNS)) if RUNS.exists() else []
        cls.tmp = Path(tempfile.mkdtemp(prefix='tsup_'))
        cls.dummy = cls.tmp / f'{NAME}.exe'
        shutil.copy(Path(os.environ['WINDIR']) / 'System32' / 'cmd.exe', cls.dummy)

    @classmethod
    def tearDownClass(cls):
        ts.kill_tree_by_name(NAME)
        shutil.rmtree(cls.tmp, ignore_errors=True)
        after = sorted(os.listdir(RUNS)) if RUNS.exists() else []
        assert after == cls.runs_before, 'a test created a run directory'

    def setUp(self):
        self.tz = self.tmp / f'{self._testMethodName}.tz'
        self.csv = self.tmp / f'{self._testMethodName}.csv'
        self.sup = None
        self.target = None

    def tearDown(self):
        if self.sup:
            self.sup.stop()
        if self.target and self.target.poll() is None:
            ts.kill_tree_by_pid(self.target.pid)
        self.assertEqual(named_left(), 0, 'dummy left running')
        if self.sup and self.sup.proc:
            self.assertIsNotNone(self.sup.proc.poll(), 'guard left running')

    def set_tz(self, v):
        self.tz.write_text(v + '\n')

    def start(self, tz='330', **kw):
        self.set_tz(tz)
        args = kw.pop('guard_args', ())
        self.sup = ts.Supervisor(NAME, self.csv, guard_args=('-TzFile', str(self.tz), *args),
                                 start_timeout_s=kw.pop('start_timeout_s', 15), **kw)
        return self.sup.start()

    def launch(self):
        self.assertEqual(named_left(), 0)
        self.target = subprocess.Popen([str(self.dummy), '/c', 'ping -n 300 127.0.0.1 >nul'], creationflags=NO_WINDOW)
        for _ in range(20):
            kids = children(self.target.pid)
            if kids:
                return kids
            time.sleep(0.3)
        self.fail('dummy child not seen')

    def wait_dead(self, kids, limit=20):
        t = time.monotonic()
        while time.monotonic() - t < limit:
            if self.target.poll() is not None and not any(alive(k) for k in kids):
                return time.monotonic() - t
            time.sleep(0.5)
        self.fail('dummy tree still alive')

    # 1 -- the guard reports a temperature before the target may start
    def test_start_waits_for_first_valid_sample(self):
        self.start('330')
        rows = self.csv.read_text(encoding='utf-8').splitlines()[1:]
        self.assertTrue(any(r.split(',')[1] == '330' for r in rows))
        self.assertEqual(named_left(), 0)
        kids = self.launch()
        time.sleep(5)
        self.assertIsNone(self.target.poll())                       # normal temperature: no kill
        res = self.sup.stop()
        self.assertIsNone(res['stop_reason'])
        self.assertGreaterEqual(res['samples'], 4)                  # ~1 s cadence

    # 2 -- startup failures launch nothing
    def test_start_fails_without_reading(self):
        with self.assertRaises(ts.GuardError):
            self.start('', start_timeout_s=5)
        self.assertIsNotNone(self.sup.proc.poll())

    def test_start_rejects_old_guards(self):
        for g in ('thermal_guard.ps1', 'thermal_guard_v2.ps1', 'missing.ps1'):
            sup = ts.Supervisor(NAME, self.csv, guard=ROOT / 'generated' / 'profile' / g)
            with self.assertRaises(ts.GuardError):
                sup.start()
            self.assertIsNone(sup.proc)                             # never even started

    # 3 -- guard dies -> target tree killed
    def test_guard_exit_kills_target(self):
        self.start('330')
        kids = self.launch()
        ts.kill_tree_by_pid(self.sup.proc.pid)
        self.wait_dead(kids, 10)
        self.assertEqual(self.sup.stop()['stop_reason'], 'thermal_guard_exited')

    # 4 -- stale heartbeat (blocked sensor) and invalid readings
    def test_stale_guard_kills_target(self):
        self.start('330', stale_s=4, guard_args=('-TestHangAfterS', '4'))
        kids = self.launch()
        self.wait_dead(kids, 20)
        self.assertEqual(self.sup.stop()['stop_reason'], 'thermal_guard_stale')

    def test_invalid_reading_kills_target(self):
        self.start('330')
        kids = self.launch()
        self.set_tz('n/a')
        self.wait_dead(kids, 15)
        res = self.sup.stop()
        self.assertEqual(res['stop_reason'], 'thermal_kill')
        self.assertIn('no temperature reading', res['detail'])

    # 5 -- 363 K kills the whole tree
    def test_limit_kills_tree(self):
        self.start('358')
        kids = self.launch()
        self.set_tz('363')
        took = self.wait_dead(kids, 15)
        res = self.sup.stop()
        self.assertEqual((res['stop_reason'], res['detail']), ('thermal_kill', 'KILLED at tz=363'))
        self.assertLess(took, 5)

    def test_362_does_not_kill(self):
        self.start('355')
        self.launch()
        self.set_tz('362')
        time.sleep(6)
        self.assertIsNone(self.target.poll())
        self.assertIsNone(self.sup.stop()['stop_reason'])

    # 6 -- rapid rise at the real 1 s cadence
    def test_rapid_rise(self):
        self.start('330')
        kids = self.launch()
        time.sleep(2)
        self.set_tz('338')
        self.wait_dead(kids, 15)
        res = self.sup.stop()
        self.assertEqual(res['stop_reason'], 'thermal_kill')
        self.assertIn('rapid rise 330->338', res['detail'])

    # 7 -- maximum duration
    def test_max_runtime(self):
        self.start('330', max_run_s=4, grace_s=1)
        kids = self.launch()
        took = self.wait_dead(kids, 15)
        self.assertEqual(self.sup.stop()['stop_reason'], 'max_runtime')
        self.assertLess(took, 10)

    def test_max_runtime_cap(self):
        with self.assertRaises(ts.GuardError):
            ts.Supervisor(NAME, self.csv, max_run_s=211)


if __name__ == '__main__':
    unittest.main(verbosity=2)
