#!/usr/bin/env python3
"""T194 runner: t190/ab/run_t190.py with the T194 exe (build/motorstorm-t194) and two visual arms.
  P  visual off: T190 arm P env + RSX_ZETA_EXACT=0 RSX_EXP_C38=0 (the old rendering).
  B  visual on:  T190 arm P env + the T194 defaults (zeta exact, EXPERIMENTAL c38 = 1.0)
                 + RSX_COLOR_XFER=7 RSX_SHADER_WINDOW=1 RSX_RT_FEEDBACK=1 RSX_MRT_STATE=1.
Same exe for both. Cap 2 launches, fixed order Pp1 Bb1, no retries. Frame dumps as T190 (CELLMARK_DUMP).
  py -3 generated/analysis/t194/tools/make_runner_t194.py <exe sha256>
  py -3 generated/analysis/t194/ab/run_t194.py prepare r ; envcheck ; dryrun P p1 ; launch P p1"""
import re, shutil, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
pin = (sys.argv[1] if len(sys.argv) > 1 else '').lower()
if not re.fullmatch(r'[0-9a-f]{64}', pin):
    raise SystemExit('usage: make_runner_t194.py <exe sha256 of build/motorstorm-t194>')
src = (ROOT / 'generated/analysis/t190/ab/run_t190.py').read_text(encoding='utf-8')
def sub(old, new):
    global src
    assert src.count(old) == 1, (old[:70], src.count(old))
    src = src.replace(old, new)
sub("'motorstorm-t190'", "'motorstorm-t194'")
sub(re.search(r"PIN = '[0-9a-f]{64}'", src).group(0), f"PIN = '{pin}'")
sub("f't190-{arm}{tag}'", "f't194-{arm}{tag}'")
sub("ARMS = {'P': ARMS['P'], 'B': ('r', {**ARMS['P'][1], 'PS3_VM_STORE_INLINE': '1'})}   # T190: the one switch\n"
    "ORDER = ['Pp1', 'Bb1', 'Pp2', 'Bb2']   # T190: the authorized sequence\n",
    "_VOFF = {'RSX_ZETA_EXACT': '0', 'RSX_EXP_C38': '0'}   # T194: the old rendering\n"
    "_VON = {'RSX_COLOR_XFER': '7', 'RSX_SHADER_WINDOW': '1', 'RSX_RT_FEEDBACK': '1', 'RSX_MRT_STATE': '1'}\n"
    "ARMS = {'P': ('r', {**ARMS['P'][1], **_VOFF}), 'B': ('r', {**ARMS['P'][1], **_VON})}   # T194: visual off / on\n"
    "ORDER = ['Pp1', 'Bb1', 'Pp2', 'Bb2']   # T194: p1/b1 ran without frame dumps; p2/b2 with them\n")
# T194 round 3: leave-one-out from B, one switch off per arm (C c38, F RT feedback, X colour transfer, Z zeta).
sub("ORDER = ['Pp1', 'Bb1', 'Pp2', 'Bb2']   # T194: p1/b1 ran without frame dumps; p2/b2 with them\n",
    "_B = ARMS['B'][1]\n"
    "ARMS.update({'C': ('r', {**_B, 'RSX_EXP_C38': '0'}), 'F': ('r', {**_B, 'RSX_RT_FEEDBACK': '0'}),\n"
    "             'X': ('r', {**_B, 'RSX_COLOR_XFER': '0'}), 'Z': ('r', {**_B, 'RSX_ZETA_EXACT': '0'})})   # T194 round 3\n"
    "ORDER = ['Pp1', 'Bb1', 'Pp2', 'Bb2', 'Cc1', 'Ff1', 'Xx1', 'Zz1']   # T194: p1/b1 no dumps; p2/b2 dumps; round 3 leave-one-out\n")
sub("MAX_LAUNCHES = 4", "MAX_LAUNCHES = 12")
# T194 round 4: B repeated twice (white race start), and a garage pair that holds at the main menu with no
# presses for MENU_HOLD s (the garage scene loads behind it) and then stops: G = B, K = B with c38 off.
sub("    'X': ('r', {**_B, 'RSX_COLOR_XFER': '0'}), 'Z': ('r', {**_B, 'RSX_ZETA_EXACT': '0'})})   # T194 round 3\n",
    "    'X': ('r', {**_B, 'RSX_COLOR_XFER': '0'}), 'Z': ('r', {**_B, 'RSX_ZETA_EXACT': '0'})})   # T194 round 3\n"
    "_GD = {'CELLMARK_DUMP': '24', 'CELLMARK_DUMP_EVERY': '48', 'CELLMARK_DUMP_MINDRAWS': '30'}   # menu frames ~52 draws\n"
    "ARMS.update({'G': ('r', {**_B, **_GD}), 'K': ('r', {**_B, **_GD, 'RSX_EXP_C38': '0'})})   # T194 round 4\n"
    "MENU_HOLD = {'G': 40.0, 'K': 40.0}\n")
sub("ORDER = ['Pp1', 'Bb1', 'Pp2', 'Bb2', 'Cc1', 'Ff1', 'Xx1', 'Zz1']",
    "ORDER = ['Pp1', 'Bb1', 'Pp2', 'Bb2', 'Cc1', 'Ff1', 'Xx1', 'Zz1', 'Bb3', 'Bb4', 'Gg1', 'Kk1']")
sub("        pol = self.nav_pol\n",
    "        pol = self.nav_pol\n"
    "        if ARM in MENU_HOLD:   # T194: no presses; check_global stops the run after the hold\n"
    "            return\n")
sub("        if (self.rt / 'STOP').exists():\n",
    "        if ARM in MENU_HOLD and self.menu_page_t is not None and self.now() - self.menu_page_t >= MENU_HOLD[ARM]:\n"
    "            self.finish(f'main menu + {MENU_HOLD[ARM]:.0f} s (garage hold)')\n"
    "            return True\n"
    "        if (self.rt / 'STOP').exists():\n")
# T194 round 2: RSX_SHADER_WINDOW is default ON in this tree, so arm P sets it to 0 for the old rendering;
# frame dumps (CELLMARK_DUMP*) stay on in every arm (the QUIET filter used to drop them outside arm V).
sub("_VOFF = {'RSX_ZETA_EXACT': '0', 'RSX_EXP_C38': '0'}", "_VOFF = {'RSX_ZETA_EXACT': '0', 'RSX_EXP_C38': '0', 'RSX_SHADER_WINDOW': '0'}")
sub("QUIET = ('CELLMARK_DUMP', ", "QUIET = (")
# T194: RDP is the user's normal way in. Launch from a console OR an RDP session; the kind is recorded in the
# lock and every arm must use the same kind (RDP changes D3D12 presentation, so FPS is not comparable with
# console runs; frame dumps are taken from guest render targets). The run stops if the kind changes mid-run.
sub("    if not active or not active[0].startswith('>console'):\n"
    "        fails.append(f'not a console session: {active}')\n",
    "    kind = session_kind()\n"
    "    if kind is None:\n"
    "        fails.append(f'not a console or RDP session: {active}')\n"
    "    kinds = {json.loads(l).get('session', 'console') for l in used}\n"
    "    if kind and kinds and kinds != {kind}:\n"
    "        fails.append(f'session kind {kind} differs from the earlier arms {sorted(kinds)}: not comparable')\n")
sub("def env_preflight():\n",
    "def session_kind():\n"
    "    q = subprocess.run(['query', 'session'], capture_output=True, text=True).stdout\n"
    "    a = [l for l in q.splitlines() if l.startswith('>')]\n"
    "    return 'console' if a and a[0].startswith('>console') else 'rdp' if a and a[0].startswith('>rdp-tcp') else None\n"
    "\n\n"
    "def env_preflight():\n")
sub("    if remote != 'False':\n"
    "        raise SystemExit(f'PREFLIGHT FAIL: session not verified local ({remote!r})')\n",
    "    if remote != ('True' if session_kind() == 'rdp' else 'False'):\n"
    "        raise SystemExit(f'PREFLIGHT FAIL: TerminalServerSession {remote!r} does not match the session kind {session_kind()}')\n"
    "    START_REMOTE[0] = remote == 'True'\n")
sub("        if ctypes.windll.user32.GetSystemMetrics(0x1000):\n"
    "            self.finish('session became remote')\n",
    "        if bool(ctypes.windll.user32.GetSystemMetrics(0x1000)) != START_REMOTE[0]:\n"
    "            self.finish('session kind changed (console <-> remote)')\n")
sub("LOCK = HERE / 'launches_used.jsonl'\n", "LOCK = HERE / 'launches_used.jsonl'\nSTART_REMOTE = [False]   # T194: remote state at launch\n")
sub("'at': time.strftime('%Y-%m-%dT%H:%M:%S'), 'exe': got}",
    "'at': time.strftime('%Y-%m-%dT%H:%M:%S'), 'exe': got, 'session': session_kind()}")
out = HERE.parent / 'ab'; out.mkdir(exist_ok=True)
for f in ('cpath_sites.cfg',):
    (out / f).write_text((ROOT / 'generated/analysis/t190/ab' / f).read_text(encoding='utf-8'), encoding='utf-8')
if not (out / 'shader_cache').exists():
    shutil.copytree(ROOT / 'generated/analysis/t190/ab/shader_cache', out / 'shader_cache')
(out / 'run_t194.py').write_text(src, encoding='utf-8')
print('wrote', out / 'run_t194.py')
