"""T169: arms D and F of GAME_VALIDATION_PLAN.md, derived from t165/ab/run_t165.py: same route, flyover skip and arm T environment.
Differences: caps 205 s game / 210 s host; the T169 exe; RSX_VISUAL_PROFILE per arm; c33.x timeline; bounded RSX_VISUAL_DIAG;
the debug layer in both arms with its messages counted by dbwin_d3d12_t169.py; one RSXI frame last (race entry + 25 s, or host 190 s
if earlier), because a capture can trip the 4 s Present timeout that ends a run; a refusal to start in a remote session.
  py -3 generated/analysis/t169/tools/make_runner_t169.py
  py -3 generated/analysis/t169/ab/run_t169.py prepare t ; dryrun D|F ; launch D|F <tag>"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
AB = HERE.parent / 'ab'
T165 = HERE.parents[1] / 't165' / 'ab'
src = (T165 / 'run_t165.py').read_text(encoding='utf-8')
NL = chr(10)


def sub(old, new, count=1):
    global src
    assert src.count(old) == count, (old[:80], src.count(old))
    src = src.replace(old, new)


sub("SRC_EXES = {'n': ROOT / 'build' / 'motorstorm-perfnext-tex' / 'MotorStormPacificRiftRecomp.exe'}",
    "SRC_EXES = {'t': ROOT / 'build' / 'motorstorm-t169' / 'MotorStormPacificRiftRecomp.exe'}")
sub("HARD_KILL_S = 200.0   # as T161 (this slice replaces its line)", "HARD_KILL_S = 203.0   # before the 205 s game cap")
i0, i1 = src.index("EXEDIR = HERE.parents[1]"), src.index("RACE_STOP = {")
src = src[:i0] + """EXEDIR = HERE
VALID = {'D3D12_DBG': '1'}
ARMS = {
    'D': ('t', {**ENV_LEAN, **TEXRES, **VALID, 'RSX_VISUAL_PROFILE': '0x80'}),
    'F': ('t', {**ENV_LEAN, **TEXRES, **VALID, 'RSX_VISUAL_PROFILE': '0x1BF'}),
}
""" + src[i1:]
sub("RSXI_AT_S = 10.0   # T165: after the skip presses", "RSXI_AT_S = 25.0   # T169: after the timing window\nRSXI_LATEST_S = 190.0")
sub("RUN_NAME = 't165'", "RUN_NAME = 't169'")
sub("if self.race_t is not None and self.now() - self.race_t >= RSXI_AT_S and not (self.rt / 'rsxi_go').exists():",
    "if self.race_t is not None and (self.now() - self.race_t >= RSXI_AT_S or self.now() >= RSXI_LATEST_S) and not (self.rt / 'rsxi_go').exists():")
sub("self.note('rsxi_trigger', after_race_s=RSXI_AT_S)", "self.note('rsxi_trigger', after_race_s=round(self.now() - self.race_t, 2))")
sub("'RSXI_COUNT': '3', 'RSXI_STRIDE': '120',", "'RSXI_COUNT': '1', 'RSXI_STRIDE': '120',")
sub("        'RSX_XFER_LOG': '48', 'RSX_TEXREC_STATS': '1',\n",
    "        'RSX_XFER_LOG': '48', 'RSX_TEXREC_STATS': '1',\n"
    "        'RSX_VPC_WATCH': '33', 'RSX_VPC_WATCH_LANE': '0', 'RSX_VPC_WATCH_MS': '250', 'RSX_VPC_WATCH_MAX': '4096',\n"
    "        'RSX_VISUAL_DIAG': '1', 'RSX_VISUAL_DIAG_GO': str(rtdir / 'rsxi_go'), 'RSX_VISUAL_DIAG_MAX': '3000',\n")
sub("'CELLMARK_DUMP': '12', 'CELLMARK_DUMP_EVERY': '64',", "'CELLMARK_DUMP': '16', 'CELLMARK_DUMP_EVERY': '64',")
sub("'--timeout', '195']   # + fast_startup HARD_GRACE_S 15 = 210 s hard deadline", "'--timeout', '205']   # + HARD_GRACE_S 5 (set in main) = 210 s hard deadline")
sub("raise SystemExit('usage: run_t165.py launch B|X|Y|S <tag>')", "raise SystemExit('usage: run_t169.py launch D|F <tag>')")
sub("ARM, RUN_NAME = arm, f't165-{arm}{tag}'", "ARM, RUN_NAME = arm, f't169-{arm}{tag}'")
sub("    fast_startup.MAX_TIMEOUT_S = 195.0" + NL, "    fast_startup.MAX_TIMEOUT_S = 205.0" + NL + "    fast_startup.HARD_GRACE_S = 5.0" + NL)
sub("    got = preflight(HDD1)\n",
    "    got = preflight(HDD1)\n"
    "    remote = subprocess.run(['powershell', '-NoProfile', '-Command', 'Add-Type -AssemblyName System.Windows.Forms; "
    "[System.Windows.Forms.SystemInformation]::TerminalServerSession'], capture_output=True, text=True).stdout.strip()\n"
    "    if remote != 'False':\n"
    "        raise SystemExit(f'PREFLIGHT FAIL: session not verified local ({remote!r})')\n")
sub("    ctl = Controller(ROOT / 'generated' / 'runs', started, rtdir, run_name)\n",
    "    dbw = subprocess.Popen([sys.executable, str(HERE.parent / 'tools' / 'dbwin_d3d12_t169.py'), str(rtdir / 'd3d12_messages.json'), str(rtdir / 'dbw_stop')],\n"
    "                           stdout=open(rtdir / 'dbwin.log', 'w'), stderr=subprocess.STDOUT)\n"
    "    time.sleep(1.0)\n"
    "    ctl = Controller(ROOT / 'generated' / 'runs', started, rtdir, run_name)\n")
sub("    ctl.done.set()\n    leftover =",
    "    ctl.done.set()\n    (rtdir / 'dbw_stop').write_text('stop\\n')\n    dbw.wait(timeout=20)\n    leftover =")
AB.mkdir(exist_ok=True)
(AB / 'cpath_sites.cfg').write_bytes((T165 / 'cpath_sites.cfg').read_bytes())
(AB / 'run_t169.py').write_text(src, encoding='utf-8')
print('wrote', AB / 'run_t169.py')
