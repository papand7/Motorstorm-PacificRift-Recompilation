"""T165: game-test runner, derived from performance_next/ab/run_next.py (same route, caps and pinned exe_n).
Differences: arms B/X/S/D, one RSXI capture, and the capture moved early. Race entry varied from 136 to 183 s
in T3/T4/E3/E4 against the 195 s cap, so the controller presses CROSS at race entry + 4 and + 7 s ('Press X to
Skip') to reach the grid, and triggers RSXI at + 10 s (3 frames, 120 apart). VP_CONSTS=512 + GEOM=16 + all units (B1, B2) cost 18 KB per draw
and tripped the game's 4 s GcKernel::Present() Timeout, so the capture is lean. Stops at race entry + 45 s.
  py -3 generated/analysis/t165/tools/make_runner_t165.py
  py -3 generated/analysis/t165/ab/run_t165.py launch B|X|S <tag>"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
AB = HERE.parent / 'ab'
NEXT = HERE.parents[1] / 'performance_next' / 'ab'
src = (NEXT / 'run_next.py').read_text(encoding='utf-8')


def sub(old, new, count=1):
    global src
    assert src.count(old) == count, (old[:80], src.count(old))
    src = src.replace(old, new)


i0, i1 = src.index("ARMS = {"), src.index("RACE_STOP = {")
src = src[:i0] + """EXEDIR = HERE.parents[1] / 'performance_next' / 'ab'   # the pinned exe_n, unchanged
ARMS = {
    'B': ('n', {**ENV_LEAN, **TEXRES}),                                  # T3 arm T: baseline
    'X': ('n', {**ENV_LEAN, **TEXRES, 'RSX_COLOR_XFER': '7'}),           # transfer isolation
    'Y': ('n', {**ENV_LEAN, **TEXRES, 'RSX_COLOR_XFER': '1'}),           # spare: single transfer bit
    'S': ('n', {**ENV_LEAN, **TEXRES, 'RSX_GUEST_SAMPLERS': '15', 'RSX_TEX_MIPS': '1'}),   # samplers only
}
""" + src[i1:]
sub("RACE_STOP = {'E': 150.0, 'T': 150.0}", "RACE_STOP = {a: 45.0 for a in ARMS}")
sub("NAV = {'E': dict(settle_s=1.5, retries=2), 'T': dict(settle_s=1.5, retries=2)}",
    "NAV = {a: dict(settle_s=1.5, retries=2) for a in ARMS}")
sub("RSXI_AT_S = 30.0   # T145: the controller writes rtdir/rsxi_go at race entry + 30 s",
    "RSXI_AT_S = 10.0   # T165: after the skip presses\nSKIP_AT_S = (4.0, 7.0)")
sub("RUN_NAME = 'perfnext'", "RUN_NAME = 't165'")
sub("usage: run_next.py launch E|T <tag>", "usage: run_t165.py launch B|X|Y|S <tag>")
sub("ARM, RUN_NAME = arm, f'perfnext-{arm}{tag}'", "ARM, RUN_NAME = arm, f't165-{arm}{tag}'")
sub("        EXE = HERE / f'exe_{x}' / 'MotorStormPacificRiftRecomp.exe'\n        EXE_SHA = (HERE / f'exe_{x}.sha256').read_text().split()[0]",
    "        EXE = EXEDIR / f'exe_{x}' / 'MotorStormPacificRiftRecomp.exe'\n        EXE_SHA = (EXEDIR / f'exe_{x}.sha256').read_text().split()[0]")
sub("            if not self.nav_manual:\n                self.nav()\n",
    "            if not self.nav_manual:\n                self.nav()\n"
    "            if self.race_t is not None and self.skips < len(SKIP_AT_S) and self.now() - self.race_t >= SKIP_AT_S[self.skips]:\n"
    "                self.skips += 1\n"
    "                self.press(f'flyover skip {self.skips}', CROSS, 20)\n")
sub("        self.race_t = None\n", "        self.race_t = None\n        self.skips = 0\n")
sub("'CELLMARK_DUMP_EVERY': '8'", "'CELLMARK_DUMP_EVERY': '64'")
sub("        'RSX_HEARTBEAT_MS': '1000', 'PS3_TEX_SNAPSHOT': '1',\n",
    "        'RSX_HEARTBEAT_MS': '1000', 'PS3_TEX_SNAPSHOT': '1',\n"
    "        'RSXI': '1', 'RSXI_DIR': str(rtdir / 'rsxi'), 'RSXI_TRIGGER_FILE': str(rtdir / 'rsxi_go'),\n"
    "        'RSXI_COUNT': '3', 'RSXI_STRIDE': '120', 'RSXI_MINDRAWS': '200', 'RSXI_SNAP': 'passes',\n"
    "        'RSXI_MAX_EVENTS': '20000', 'RSXI_MAX_SNAPS': '64', 'RSXI_VP_CONSTS': '48', 'RSXI_UNITS': 'C03F', 'RSXI_GEOM': '1',\n"
    "        'RSX_XFER_LOG': '48', 'RSX_TEXREC_STATS': '1',\n")
AB.mkdir(exist_ok=True)
for name in ('cpath_sites.cfg',):
    (AB / name).write_bytes((NEXT / name).read_bytes())
(AB / 'run_t165.py').write_text(src, encoding='utf-8')
print('wrote', AB / 'run_t165.py')
