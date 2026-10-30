"""T169: arms D and F of GAME_VALIDATION_PLAN.md, derived from t165/ab/run_t165.py: same route, flyover skip and arm T environment.
Differences: caps 205 s game / 210 s host; the T169 exe; explicit switches per arm (D2/F2), stop conditions on log lines; c33.x timeline; bounded RSX_VISUAL_DIAG;
the debug layer in both arms with its messages counted by dbwin_d3d12_t169.py; no RSXI; RSX_VISUAL_DIAG lines from race entry + 25 s (or host 190 s
if earlier), because a capture can trip the 4 s Present timeout that ends a run; a refusal to start in a remote session.
  py -3 generated/analysis/t169/tools/make_runner_t169.py
  py -3 generated/analysis/t169/ab/run_t169.py prepare t ; dryrun D|F|A|B|C ; launch D|F|A|B|C <tag>"""
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
    "SRC_EXES = {'t': ROOT / 'build' / 'motorstorm-t169' / 'MotorStormPacificRiftRecomp.exe', 'c': ROOT / 'build' / 'motorstorm-t169' / 'MotorStormPacificRiftRecomp.exe'}")
sub("HARD_KILL_S = 200.0   # as T161 (this slice replaces its line)", "HARD_KILL_S = 203.0   # before the 205 s game cap")
i0, i1 = src.index("EXEDIR = HERE.parents[1]"), src.index("RACE_STOP = {")
src = src[:i0] + """EXEDIR = HERE
VALID = {'D3D12_DBG': '1'}
ARMS = {
    'D': ('t', {**ENV_LEAN, **TEXRES, **VALID, 'RSX_DEPTH_STATE': '1'}),
    'F': ('t', {**ENV_LEAN, **TEXRES, **VALID, 'RSX_COLOR_XFER': '7', 'RSX_GUEST_SAMPLERS': '15', 'RSX_TEX_MIPS': '1', 'RSX_ZETA_EXACT': '1',
                'RSX_RT_WINDOW': '1', 'RSX_RT_FEEDBACK': '1', 'RSX_DEPTH_STATE': '1', 'RSX_MRT_STATE': '1'}),
}
# T169 velocity validation: the F2 set; exe t is ps3recomp 774c81d, exe c 542420e. RSXI only at race entry + VEL_CAP_S, past the timing window.
VEL_RSXI = {'RSXI': '1', 'RSXI_COUNT': '1', 'RSXI_STRIDE': '1', 'RSXI_MINDRAWS': '200', 'RSXI_SNAP': 'passes', 'RSXI_MAX_EVENTS': '0', 'RSXI_MAX_SNAPS': '64',
            'RSXI_VP_CONSTS': '0', 'RSXI_UNITS': '0', 'RSXI_GEOM': '0', 'RSXI_RTS': '01650000,01DD0000,00750000,022D0000'}
ARMS['A'] = ('t', {**ARMS['F'][1], **VEL_RSXI, 'RSX_RT_REINTERP': '0'})
ARMS['B'] = ('t', {**ARMS['A'][1], 'RSX_DEPTH_STATE': '0'})
ARMS['C'] = ('c', {**ARMS['A'][1], 'RSX_RT_REINTERP': '1'})
VEL_CAP_S = 38.0
EXPECT = {'D': 'profile=0x0 xfer=0x0 samplers=0x0 mips=0 zeta_exact=0 rt_window=0 rt_feedback=0 msaa=0 depth_state=1 mrt_state=0',
          'F': 'profile=0x0 xfer=0x7 samplers=0xF mips=1 zeta_exact=1 rt_window=1 rt_feedback=1 msaa=0 depth_state=1 mrt_state=1'}
EXPECT['A'] = EXPECT['F']
EXPECT['B'] = EXPECT['F'].replace('depth_state=1', 'depth_state=0')
EXPECT['C'] = EXPECT['F'] + ' rt_reinterp=1'
RX_SERIOUS = re.compile(r'Present\\(\\) Timeout|DXGI_ERROR_DEVICE|DeviceRemoved|DEVICE_REMOVED|device removed|resynchron|fifo.*(corrupt|resync)', re.I)
""" + src[i1:]
# D2/F2 stop conditions, checked on every log line and every controller tick
sub("    def feed(self, stream, line):\n        now = self.now()\n",
    "    def feed(self, stream, line):\n        now = self.now()\n"
    "        if line.startswith('[visual] effective'):\n"
    "            self.effective = line.strip()\n"
    "            self.note('visual_effective', line=line[:200])\n"
    "            if EXPECT[ARM] not in line:\n"
    "                self.finish('requested switches not effective')\n"
    "                return\n"
    "        if line.startswith('[visual-active]'):\n"
    "            self.note('visual_active', line=line[:400])\n"
    "        if RX_SERIOUS.search(line):\n"
    "            self.note('serious', line=line[:240])\n"
    "            self.finish('serious error: ' + line[:80])\n"
    "            return\n")
sub("    def check_global(self):\n        if self.done.is_set():\n            return True\n",
    "    def check_global(self):\n        if self.done.is_set():\n            return True\n"
    "        if self.now() > 90 and not getattr(self, 'effective', None):\n"
    "            self.finish('no [visual] effective line within 90 s')\n"
    "            return True\n"
    "        if ctypes.windll.user32.GetSystemMetrics(0x1000):\n"
    "            self.finish('session became remote')\n"
    "            return True\n"
    "        if self.now() - getattr(self, 'mem_t', -99) >= 15:\n"
    "            self.mem_t = self.now()\n"
    "            subprocess.Popen(['tasklist', '/FI', 'IMAGENAME eq MotorStormPacificRiftRecomp.exe', '/FO', 'CSV', '/NH'], stdout=open(self.rt / 'mem.csv', 'a'), stderr=subprocess.DEVNULL)\n")
sub("import hashlib, json, os,", "import ctypes, hashlib, json, os,")
sub("RSXI_AT_S = 10.0   # T165: after the skip presses", "RSXI_AT_S = 25.0   # T169: after the timing window\nRSXI_LATEST_S = 190.0")
sub("RUN_NAME = 't165'", "RUN_NAME = 't169'")
sub("if self.race_t is not None and self.now() - self.race_t >= RSXI_AT_S and not (self.rt / 'rsxi_go').exists():",
    "if self.race_t is not None and (self.now() - self.race_t >= RSXI_AT_S or self.now() >= RSXI_LATEST_S) and not (self.rt / 'rsxi_go').exists():")
sub("self.note('rsxi_trigger', after_race_s=RSXI_AT_S)", "self.note('rsxi_trigger', after_race_s=round(self.now() - self.race_t, 2))")
sub("        if self.race_t is not None and self.now() - self.race_t >= RACE_STOP.get(ARM, RACE_STOP_S):\n",
    "        if ARM in 'ABC' and self.race_t is not None and self.now() - self.race_t >= VEL_CAP_S and not (self.rt / 'vel_go').exists():\n"
    "            (self.rt / 'vel_go').write_text('go\\n')\n"
    "            self.note('vel_capture_trigger', after_race_s=round(self.now() - self.race_t, 2))\n"
    "        if self.race_t is not None and self.now() - self.race_t >= RACE_STOP.get(ARM, RACE_STOP_S):\n")
sub("    envs.update({k: v.replace('{rt}', str(rtdir)) for k, v in ARMS[ARM][1].items()})   # the arm keys last\n",
    "    envs.update({k: v.replace('{rt}', str(rtdir)) for k, v in ARMS[ARM][1].items()})   # the arm keys last\n"
    "    if ARM in 'ABC':\n"
    "        envs.update({'RSXI_DIR': str(rtdir / 'rsxi'), 'RSXI_TRIGGER_FILE': str(rtdir / 'vel_go')})\n")
# D2/F2: no RSXI. It tripped the 4 s Present timeout in D1 and F1, and that timeout now cancels the sequence.
j0, j1 = src.index("        'RSXI': '1', 'RSXI_DIR'"), src.index("        'RSX_XFER_LOG': '48'")
src = src[:j0] + src[j1:]
sub("        'RSX_XFER_LOG': '48', 'RSX_TEXREC_STATS': '1',\n",
    "        'RSX_XFER_LOG': '48', 'RSX_TEXREC_STATS': '1',\n"
    "        'RSX_VPC_WATCH': '33', 'RSX_VPC_WATCH_LANE': '0', 'RSX_VPC_WATCH_MS': '250', 'RSX_VPC_WATCH_MAX': '4096',\n"
    "        'RSX_VISUAL_DIAG': '1', 'RSX_VISUAL_DIAG_GO': str(rtdir / 'rsxi_go'), 'RSX_VISUAL_DIAG_MAX': '2000', 'RSX_VISUAL_ACTIVE': '1',\n")
sub("'CELLMARK_DUMP': '12', 'CELLMARK_DUMP_EVERY': '64',", "'CELLMARK_DUMP': '16', 'CELLMARK_DUMP_EVERY': '64',")
sub("'--timeout', '195']   # + fast_startup HARD_GRACE_S 15 = 210 s hard deadline", "'--timeout', '205']   # + HARD_GRACE_S 5 (set in main) = 210 s hard deadline")
sub("raise SystemExit('usage: run_t165.py launch B|X|Y|S <tag>')", "raise SystemExit('usage: run_t169.py launch D|F|A|B|C <tag>')")
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
