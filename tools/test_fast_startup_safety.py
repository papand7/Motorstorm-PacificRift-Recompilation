#!/usr/bin/env python3
"""fast_startup's safeguards (offline; nothing but dummy processes is launched).

SafeStopTests replace startup_runner.main and the thermal supervisor with fakes.
DummyRunTests drive the real runner with a renamed cmd.exe (and a PING child)
standing in for the game.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fast_startup as fs  # noqa: E402


class TempCache:
    """Point fast_startup's hdd1 and snapshot root at a temp dir (never the real cache)."""

    def setUp(self):
        self.ctmp = tempfile.TemporaryDirectory()
        c = Path(self.ctmp.name)
        self.real_hdd1, self.real_snap = fs.HDD1, fs.SNAPSHOT_ROOT
        fs.HDD1, fs.SNAPSHOT_ROOT = c / 'hdd1', c / 'snapshots'
        fios = fs.HDD1 / 'cache' / 'BLES00000' / 'fios'
        fios.mkdir(parents=True)
        (fios / 'cache.dat').write_bytes(b'D' * 300000)
        (fios / 'cache.idx').write_bytes(b'I' * 1000)
        super().setUp()

    def tearDown(self):
        super().tearDown()
        fs.HDD1, fs.SNAPSHOT_ROOT = self.real_hdd1, self.real_snap
        for p in Path(self.ctmp.name).rglob('*'):           # snapshot copies are read-only
            if p.is_file():
                os.chmod(p, 0o666)
        self.ctmp.cleanup()


class SafeStopTests(TempCache, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.calls, self.order = [], []
        self.real, self.real_sup, self.real_kill = fs.startup_runner.main, fs.SUPERVISOR, fs.kill_tree_by_name
        test = self

        def runner(argv, defaults=None):
            self.order.append('runner')
            self.calls.append(list(argv))
            return 0

        class FakeSup:
            fail = False
            made = 0

            def __init__(self, exe_name, csv, max_run_s):
                FakeSup.made += 1
                test.sup_args = (exe_name, max_run_s)

            def start(self):
                test.order.append('guard_start')
                if FakeSup.fail:
                    raise SystemExit('no temperature reading')
                return self

            def stop(self):
                test.order.append('guard_stop')
                return {'stop_reason': None, 'detail': '', 'guard': 'fake', 'samples': 0,
                        'tz_min_K': None, 'tz_max_K': None}

        self.FakeSup = FakeSup
        fs.startup_runner.main, fs.SUPERVISOR = runner, FakeSup
        fs.kill_tree_by_name = lambda name: self.order.append('kill_leftovers') or False

    def tearDown(self):
        fs.startup_runner.main, fs.SUPERVISOR = self.real, self.real_sup
        fs.kill_tree_by_name = self.real_kill
        super().tearDown()

    def opt(self, argv, flag):
        return argv[argv.index(flag) + 1] if flag in argv else None

    # 1, 2, 4: normal startup needs no thermal monitor and works with no sensor at all
    def test_thermal_off_by_default(self):
        self.FakeSup.fail = True                            # a missing/failing ACPI sensor
        fs.main([])
        self.assertEqual(self.order, ['runner', 'kill_leftovers'])
        self.assertEqual(self.FakeSup.made, 0)              # never constructed, never polled
        self.assertNotIn('--thermal-guard', self.calls[0])

    def test_thermal_supervisor_not_imported_by_default(self):
        code = ('import sys; sys.path.insert(0, %r); import fast_startup; '
                'print("thermal_supervisor" in sys.modules)') % str(Path(fs.__file__).parent)
        out = subprocess.run([sys.executable, '-c', code], capture_output=True, text=True, timeout=30)
        self.assertEqual(out.stdout.strip(), 'False', out.stderr)

    # 3: explicit opt-in, fail closed once asked for
    def test_thermal_opt_in(self):
        fs.main(['--thermal-guard'])
        self.assertEqual(self.order, ['guard_start', 'runner', 'guard_stop', 'kill_leftovers'])
        self.assertEqual(self.sup_args, ('MotorStormPacificRiftRecomp', 210.0))
        self.assertNotIn('--thermal-guard', self.calls[0])  # wrapper-only flag

    def test_thermal_opt_in_failure_launches_nothing(self):
        self.FakeSup.fail = True
        with self.assertRaises(SystemExit):
            fs.main(['--thermal-guard'])
        self.assertEqual(self.calls, [])
        self.assertEqual(self.order, ['guard_start'])

    def test_real_optional_supervisor_is_v3(self):
        fs.SUPERVISOR = None
        cls = fs.supervisor_class()
        import thermal_supervisor
        self.assertIs(cls, thermal_supervisor.Supervisor)
        self.assertEqual(thermal_supervisor.GUARD.name, 'thermal_guard_v3.ps1')

    # 5: the cap
    def test_default_stops_at_garage_request(self):
        fs.main([])
        self.assertEqual(self.opt(self.calls[0], '--target'), 'garage_resources_requested')
        self.assertEqual(float(self.opt(self.calls[0], '--timeout')), 210.0)
        self.assertNotIn('--allow-extended', self.calls[0])

    def test_timeout_cap(self):
        for argv in (['--timeout', '900'], ['--target', 'garage', '--allow-extended', '--timeout', '211'],
                     ['--thermal-guard', '--timeout', '211']):
            with self.assertRaises(SystemExit):
                fs.main(argv)
        self.assertEqual(self.calls, [])

    def test_hard_deadline_constant(self):
        self.assertEqual(fs.MAX_TIMEOUT_S, 210.0)
        self.assertLessEqual(fs.HARD_GRACE_S, 15.0)

    # 6: GPU watchdog stop without thermal monitoring or a config entry
    def test_gpu_watchdog_stop_always_armed(self):
        for argv in ([], ['--target', 'video'], ['--thermal-guard']):
            self.calls.clear()
            fs.main(argv)
            self.assertEqual(self.opt(self.calls[0], '--stop-on-line'), fs.GPU_WATCHDOG_LINE)

    def test_gpu_watchdog_pattern(self):
        import re
        rx = re.compile(fs.GPU_WATCHDOG_LINE)
        self.assertTrue(rx.search('Gc ERROR: GcKernel::Present() Timeout!'))
        for benign in ('*** Executing GcKernel Timeout Callback - Please wait... ***',
                       'Gc ERROR: GcKernel::Present() ', 'GcKernel::Present() returned', 'Timeout'):
            self.assertFalse(rx.search(benign), benign)

    # 8: extended execution stays opt-in
    def test_alias_garage_request_allowed(self):
        fs.main(['--target', 'garage-request', '--timeout', '120'])
        self.assertEqual(self.opt(self.calls[0], '--target'), 'garage_resources_requested')
        self.assertEqual(self.opt(self.calls[0], '--timeout'), '120')

    def test_past_garage_needs_opt_in(self):
        for argv in (['--target', 'garage'], ['--target', 'garage_archive_read'], ['--target', 'main_menu_visible']):
            with self.assertRaises(SystemExit):
                fs.main(argv)
        self.assertEqual(self.calls, [])

    def test_opt_in_passes_through(self):
        fs.main(['--target', 'garage', '--allow-extended'])
        self.assertEqual(self.opt(self.calls[0], '--target'), 'garage_rendering_started')
        self.assertIn('--allow-extended', self.calls[0])

    def test_stop_after_next_has_no_default_target(self):
        fs.main(['--stop-after-next', 'garage_resources_requested', '--allow-extended'])
        self.assertNotIn('--target', self.calls[0])
        self.assertEqual(float(self.opt(self.calls[0], '--timeout')), 210.0)

    # 9: no retries
    def test_retries_refused(self):
        for argv in (['--retries', '1'], ['--retries', '0'], ['--retry-before', 'intro_video_opened']):
            with self.assertRaises(SystemExit):
                fs.main(argv)
        self.assertEqual(self.calls, [])
        fs.main([])
        self.assertEqual(len(self.calls), 1)                # one run per call

    def test_uses_int_runner(self):
        self.assertIn('ps3recomp-int', str(Path(self.real.__code__.co_filename).resolve()))

    # cache preservation
    def test_no_snapshot_by_default(self):
        fs.main([])
        self.assertFalse(fs.SNAPSHOT_ROOT.exists() and any(fs.SNAPSHOT_ROOT.iterdir()))
        self.assertNotIn('--snapshot-cache', self.calls[0])

    def test_snapshot_before_launch(self):
        def runner(argv, defaults=None):
            snaps = list(fs.SNAPSHOT_ROOT.iterdir())
            self.order.append(f'runner(snapshots={len(snaps)})')
            self.calls.append(list(argv))
            return 0
        fs.startup_runner.main = runner
        before = fs.cache_state(fs.HDD1)
        fs.main(['--snapshot-cache'])
        self.assertEqual(self.order, ['runner(snapshots=1)', 'kill_leftovers'])
        self.assertNotIn('--snapshot-cache', self.calls[0])          # wrapper-only flag
        snap = next(fs.SNAPSHOT_ROOT.iterdir())
        man = json.loads((snap / 'manifest.json').read_text(encoding='utf-8'))
        self.assertEqual(man['files'], before)
        self.assertEqual(fs.cache_state(snap / 'files'), before)     # same sizes and hashes
        self.assertEqual(fs.cache_state(fs.HDD1), before)            # source untouched
        for p in (snap / 'files').rglob('*'):
            if p.is_file():
                self.assertFalse(os.access(p, os.W_OK), f'{p} writable')

    def test_snapshot_refuses_without_space(self):
        state = fs.cache_state(fs.HDD1)
        with self.assertRaises(SystemExit):
            fs.snapshot_cache(fs.HDD1, state, free_bytes=lambda: 2 * 301000 + fs.SNAPSHOT_RESERVE - 1)
        self.assertFalse(fs.SNAPSHOT_ROOT.exists() and any(fs.SNAPSHOT_ROOT.iterdir()))
        real = fs.snapshot_cache
        fs.snapshot_cache = lambda src, st: real(src, st, free_bytes=lambda: 1000)
        try:
            with self.assertRaises(SystemExit):
                fs.main(['--snapshot-cache'])
        finally:
            fs.snapshot_cache = real
        self.assertEqual(self.calls, [])                             # nothing launched

    def test_snapshot_never_overwrites(self):
        state = fs.cache_state(fs.HDD1)
        a = fs.snapshot_cache(fs.HDD1, state)
        b = fs.snapshot_cache(fs.HDD1, state)
        self.assertNotEqual(a, b)
        self.assertEqual(fs.cache_state(a / 'files'), state)
        self.assertEqual(fs.cache_state(b / 'files'), state)

    def test_cache_changes(self):
        before = fs.cache_state(fs.HDD1)
        dat = fs.HDD1 / 'cache' / 'BLES00000' / 'fios' / 'cache.dat'
        dat.write_bytes(b'E' * 200000)                               # the game rewrites its cache
        (fs.HDD1 / 'font.ttf').write_bytes(b'F')
        after = fs.cache_state(fs.HDD1)
        ch = fs.cache_changes(before, after)
        self.assertIn('changed cache/BLES00000/fios/cache.dat: 300000 -> 200000 bytes', ch)
        self.assertIn('added font.ttf (1 bytes)', ch)
        self.assertEqual(fs.cache_changes(after, after), [])


@unittest.skipUnless(os.name == 'nt', 'Windows process tree')
class DummyRunTests(TempCache, unittest.TestCase):
    """The real runner and wrapper against a renamed cmd.exe; no game, no thermal guard."""
    NAME = 'fs_safety_dummy'

    def setUp(self):
        super().setUp()
        self.tmp = tempfile.TemporaryDirectory()
        self.d = Path(self.tmp.name)
        self.exe = self.d / f'{self.NAME}.exe'
        shutil.copy(Path(os.environ.get('SystemRoot', r'C:\Windows')) / 'System32' / 'cmd.exe', self.exe)
        self.runs = self.d / 'runs'
        self.real_sup = fs.SUPERVISOR

        class Boom:
            def __init__(self, *a, **k):
                raise AssertionError('thermal supervisor used without --thermal-guard')
        fs.SUPERVISOR = Boom
        self.real_runs = sorted(p.name for p in (fs.ROOT / 'generated' / 'runs').glob('*'))

    def tearDown(self):
        fs.SUPERVISOR = self.real_sup
        subprocess.run(['taskkill', '/IM', self.exe.name, '/T', '/F'], capture_output=True)
        self.assertEqual(sorted(p.name for p in (fs.ROOT / 'generated' / 'runs').glob('*')), self.real_runs)
        self.tmp.cleanup()
        super().tearDown()

    def run_dummy(self, script, *extra):
        argv = ['--exe', str(self.exe), '--arg', '/c', '--arg', script, '--runs-dir', str(self.runs),
                '--hash-input', str(self.exe), '--sample-s', '0.5', *extra]
        t = time.monotonic()
        code = fs.main(argv)
        run = max(self.runs.iterdir(), key=lambda p: p.stat().st_mtime)
        man = json.loads((run / 'manifest.json').read_text(encoding='utf-8'))
        return code, run, man, time.monotonic() - t

    def alive(self, image):
        out = subprocess.run(['tasklist', '/FI', f'IMAGENAME eq {image}', '/FO', 'CSV', '/NH'],
                             capture_output=True, text=True).stdout
        return image.lower() in out.lower()

    # 6 + 7: fatal GPU watchdog line stops the run, the whole tree goes
    def test_gpu_watchdog_line_stops_and_kills_tree(self):
        script = 'echo Gc ERROR: GcKernel::Present() Timeout!& ping -n 120 127.0.0.1 >nul'
        code, run, man, wall = self.run_dummy(script, '--timeout', '60')
        self.assertEqual(man['termination']['reason'], 'stop_line')
        self.assertIn('GcKernel::Present() Timeout', man['termination']['detail'])
        self.assertLess(wall, 30)
        self.assertNotEqual(code, 0)
        self.assertFalse(self.alive(self.exe.name))
        self.assertFalse(self.alive('PING.EXE'), 'orphaned child')
        sg = json.loads((run / 'safeguards.json').read_text(encoding='utf-8'))
        self.assertEqual(sg['thermal_monitor'], 'off')
        self.assertEqual(sg['retries'], 0)
        self.assertFalse(sg['hard_deadline_fired'])
        self.assertIn('Wrapper safeguards', (run / 'summary.md').read_text(encoding='utf-8'))
        self.assertFalse((run / 'thermal_guard.json').exists())

    # 5 + 7: the timeout stops the run and the tree; a benign line does not stop it
    def test_timeout_kills_tree(self):
        script = 'echo *** Executing GcKernel Timeout Callback - Please wait... ***& ping -n 120 127.0.0.1 >nul'
        code, run, man, wall = self.run_dummy(script, '--timeout', '3')
        self.assertEqual(man['termination']['reason'], 'timeout')
        self.assertLess(wall, 20)
        self.assertFalse(self.alive(self.exe.name))
        self.assertFalse(self.alive('PING.EXE'), 'orphaned child')

    # cache evidence: a run that rewrites the cache is recorded, and the snapshot kept it
    def test_cache_rewrite_recorded_with_snapshot(self):
        dat = fs.HDD1 / 'cache' / 'BLES00000' / 'fios' / 'cache.dat'
        before = fs.cache_state(fs.HDD1)
        self.assertNotIn(' ', str(dat))                             # cmd /c gets it unquoted
        code, run, man, wall = self.run_dummy(f'echo rewritten>{dat}', '--timeout', '20', '--snapshot-cache')
        cs = json.loads((run / 'cache_state.json').read_text(encoding='utf-8'))
        self.assertEqual(cs['before'], before)
        self.assertTrue(any(c.startswith('changed cache/BLES00000/fios/cache.dat') for c in cs['changes']))
        snap = Path(cs['snapshot'])
        self.assertEqual(fs.cache_state(snap / 'files'), before)     # the pre-run cache survives
        sg = json.loads((run / 'safeguards.json').read_text(encoding='utf-8'))
        self.assertEqual(sg['cache_snapshot'], str(snap))
        self.assertIn('## Cache (generated/hdd1)', (run / 'summary.md').read_text(encoding='utf-8'))

    # hard deadline: independent of the runner loop
    def test_hard_deadline_kills_when_runner_hangs(self):
        real_main, real_grace = fs.startup_runner.main, fs.HARD_GRACE_S
        proc = {}

        def hung_runner(argv, defaults=None):
            proc['p'] = subprocess.Popen([str(self.exe), '/c', 'ping -n 120 127.0.0.1 >nul'],
                                         creationflags=0x08000000)
            proc['p'].wait(60)                               # a runner that never stops it
            return 2
        fs.startup_runner.main, fs.HARD_GRACE_S = hung_runner, 1.0
        try:
            t = time.monotonic()
            code = fs.main(['--exe', str(self.exe), '--runs-dir', str(self.runs), '--timeout', '2'])
            wall = time.monotonic() - t
        finally:
            fs.startup_runner.main, fs.HARD_GRACE_S = real_main, real_grace
        self.assertLess(wall, 15)
        self.assertNotEqual(code, 0)
        self.assertFalse(self.alive(self.exe.name))
        self.assertFalse(self.alive('PING.EXE'), 'orphaned child')


if __name__ == '__main__':
    unittest.main(verbosity=1)
