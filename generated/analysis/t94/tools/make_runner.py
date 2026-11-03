"""T94: derive run_t94.py from t87/t87b/run_t87b.py. Every edit is an exact, asserted replacement.
Changes: T94 exe/paths, RSXI frame capture removed (no --capture-* args, no RSXI_* env, controller capture is a
no-op), T94 diagnostics added (RF_PHASE_MS=200 VPVB_GROW_AT_FRAME_END=1 RSX_VBO_DIAG=1; VP_NOFIXPROJ=1 kept).
Navigation, intro-skip check (GCM_STALL_INTRO), stall snapshot, caps (205 s session, 210 s host) unchanged."""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
T94 = HERE.parent
src = (T94.parent / 't87' / 't87b' / 'run_t87b.py').read_text(encoding='utf-8')
sha = sys.argv[1]
assert len(sha) == 64

R = [
    ('"""T87B: t87/run_t87.py', '"""T94: t87/t87b/run_t87b.py with the T94 exe (ps3recomp-t94 8ea1437 = T87B 07db971 + T91 12fb461/00bf2c4\n'
     '+ T92 0882c81), RSXI frame capture off, RF_PHASE_MS=200 VPVB_GROW_AT_FRAME_END=1 RSX_VBO_DIAG=1. One launch.\n\n'
     'T87B: t87/run_t87.py'),
    ("ROOT = HERE.parents[3]", "ROOT = HERE.parents[2]"),
    ("'motorstorm-t87b-stall'", "'motorstorm-t94-diag'"),
    ("# the T87B stall-capture exe pin, used read-only", "# the T94 integrated diagnostic exe pin, used read-only"),
    ("EXE_SHA = 'b026075c038b3c499ce5ea6d19972688940913ba3267970b9d8a8ffebfbb5ac3'", f"EXE_SHA = '{sha}'"),
    ("CFG = HERE / 'pb_stall_t87b.cfg'", "CFG = HERE / 'pb_stall_t94.cfg'   # byte-identical copy of t87b/pb_stall_t87b.cfg"),
    ("RUN_NAME = 't87b-race-stall'", "RUN_NAME = 't94-race-diag'"),
    ("(HERE.parents[1] / 't30' / 'loader'", "(HERE.parents[0] / 't30' / 'loader'"),
    # RSXI frame capture disabled: the controller never writes rsxi.trigger and never waits for a capture.
    ("    def capture(self, why):\n        if self.capture_sent or not self.run_dir:\n            return\n",
     "    def capture(self, why):\n        self.note('capture_disabled', why=why)   # T94: RSXI frame capture off\n        return\n"),
    ("        if not self.capture_sent:\n            self.capture(why)\n            self.wait_capture(30)\n", ""),
    ("                self.capture('race intro: 25 s after PostLevelLoad marker 0x8C2A0')\n                self.wait_capture(40)\n"
     "                self.finish('RSXI race capture taken (no driving)')\n",
     "                self.capture_sent = True\n                self.note('race_intro_25s')   # T94: no capture; keep running to the cap\n"),
    ("        'RSX_HEARTBEAT_MS': '1000', 'PS3_TEX_SNAPSHOT': '1', 'RSXI_MAX_MB': '512',",
     "        'RSX_HEARTBEAT_MS': '1000', 'PS3_TEX_SNAPSHOT': '1',"),
    ("        'RSXI_RTS': '00750000,01650000,07B78D80,0B830000,02195900,00ED0000,01DD0000,07EBA600',\n", ""),
    ("        'RSXI_MAX_SNAPS': '64', 'RSXI_OCC': '160-260', 'RSXI_GEOM': '8', 'RSXI_VP_CONSTS': '512',\n",
     "        # T94: T91 phase timing + frame-end growth, T92 first-overflow record\n"
     "        'RF_PHASE_MS': '200', 'VPVB_GROW_AT_FRAME_END': '1', 'RSX_VBO_DIAG': '1',\n"),
    ("            '--timeout', '210',\n"
     "            '--capture-rsx', '--capture-at', 'depth_surface_created', '--capture-delay', '400',\n"
     "            '--capture-frames', '3', '--capture-mindraws', '200', '--capture-snap', 'passes',\n"
     "            '--capture-timeout', '120']",
     "            '--timeout', '210']"),
]
for a, b in R:
    assert src.count(a) == 1, a[:80]
    src = src.replace(a, b)
for bad in ("'RSXI_", "'--capture-", 't87b-race-stall', 'b026075c'):
    assert bad not in src, bad
(T94 / 'run_t94.py').write_text(src, encoding='utf-8')
print('wrote run_t94.py')
