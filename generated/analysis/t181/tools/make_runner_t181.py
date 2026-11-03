#!/usr/bin/env python3
"""T181 test-matrix runner (needs authorization): t180/ab/run_t180.py with the T181 exe and the matrix arms.
  py -3 generated/analysis/t181/tools/make_runner_t181.py <exe sha256>
  py -3 generated/analysis/t181/ab/run_t181.py prepare r ; dryrun R x ; launch R r1
Corrections to the T180 runner:
  arms measure performance: no RSX_PERF_DEEP, frame dumps or other per-frame diagnostics beyond RSX_FRAME_PERF;
  LeOffice and Godot are no longer conflicts (the user cannot close them), and the runner records them;
  the one-launch lock becomes one lock per arm and tag, capped at MAX_LAUNCHES in all;
  runs stop at race + 75 s, past the T170 crash at race + 54 s, so the T173 fix gets tested;
  the config-boot arm presses nothing."""
import re, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
pin = (sys.argv[1] if len(sys.argv) > 1 else '').lower()
if not re.fullmatch(r'[0-9a-f]{64}', pin):
    raise SystemExit('usage: make_runner_t181.py <exe sha256 of build/motorstorm-t181>')
src = (ROOT / 'generated' / 'analysis' / 't180' / 'ab' / 'run_t180.py').read_text(encoding='utf-8')
MAX_LAUNCHES = 10


def sub(old, new):
    global src
    assert src.count(old) == 1, (old[:70], src.count(old))
    src = src.replace(old, new)


sub("'motorstorm-t180'", "'motorstorm-t181'")
sub("PIN = '6018d1f937470f92bbb2e1ceee86e2cb0a628fde50a64bb51faf45ed3a771a01'", f"PIN = '{pin}'")
sub("f't180-{arm}{tag}'", "f't181-{arm}{tag}'")
sub("""ARMS = {'D': ('r', {**_A, _WAKE: _GATE, 'PS3_LOAD_PROBE': '1000', 'PS3_HLE_WAIT_MS': '1000',
                    'PS3_CRITICAL_PATH_TRACE': '10:50:{rt}/cpath.txt'})}""", """_REF = {k: v for k, v in _A.items() if k not in ('RSX_PERF_DEEP', 'PS3_SPU_WWS_STATS', 'PS3_TEX_SNAPSHOT_STATS', 'PS3_SPURS_SCHED_STATS')}
_CAND_A = {**_REF, _WAKE: _GATE}
_FF, _MEMO, _IX = {'RSX_VP_FAST_FETCH': '1'}, {'RSX_FP_SCAN_MEMO': '1'}, {'RSX_VP_INDEXED': '1'}
_CACHE3 = {'RSX_SHADER_CACHE': '3', 'RSX_SHADER_CACHE_DIR': str(HERE / 'shader_cache')}
_CAND_B = {**_CAND_A, **_FF, **_MEMO, **_IX, **_CACHE3}
_CFG_SLOT = '0x0109AD4C:configs/ms2_config.cfg:'
ARMS = {
    'R': ('r', dict(_REF)),                             # T181 reference: lean flags, polling
    'A': ('r', dict(_CAND_A)),                          # candidate A: R + adaptive wake
    'F': ('r', {**_CAND_A, **_FF}),                     # A + fast fetch only
    'M': ('r', {**_CAND_A, **_MEMO}),                   # A + fragment scan memo only
    'X': ('r', {**_CAND_A, **_FF, **_IX}),              # A + fast fetch + indexed (indexed needs fast fetch to gain)
    'B': ('r', dict(_CAND_B)),                          # candidate B, first run fills the shader cache
    'W': ('r', dict(_CAND_B)),                          # candidate B again, warm shader cache
    'V': ('r', {**_CAND_A, 'RSX_POLY_OFFSET': '1', 'RSX_DEPTH_VOLUME': '1'}),   # visual corrections, frame dumps on
    'S': ('r', {**_CAND_A, 'PS3_DEV_GUEST_STR': _CFG_SLOT + 'configs/benchmark_happyJungle.cfg'}),   # config boot probe
    'T': ('r', {**_CAND_A, 'PS3_DEV_GUEST_STR': _CFG_SLOT + 'configs/skill_race.cfg'}),              # config boot probe
}
NO_NAV = ('S', 'T')
QUIET = ('CELLMARK_DUMP', 'PS3_PRESENT_DIAG', 'RSX_VBO_DIAG', 'RSX_TEXREC_STATS', 'RSX_XFER_LOG', 'RF_PHASE_MS', 'SPURS_BUSY_MS', 'PS3_SC_WAIT_MS', 'GCM_STALL_RING')""")
sub("RACE_STOP = {'D': 45.0}", "RACE_STOP = {a: 75.0 for a in ARMS}")
sub("POST_G_MAX_S, CAP_AT_S, STALL_S = 75.0, 185.0, 60.0", "POST_G_MAX_S, CAP_AT_S, STALL_S = 75.0, 200.0, 60.0")
sub("CONFLICTS = ('ollama', 'llama-server', 'leoffice', 'epicgameslauncher', 'epicwebhelper', 'eadesktop', 'eabackgroundservice', 'godot')",
    "CONFLICTS = ('ollama', 'llama-server', 'epicgameslauncher', 'epicwebhelper', 'eadesktop', 'eabackgroundservice')\nOPEN_OK = ('leoffice', 'godot')   # the user keeps these open; recorded, not refused\nMAX_LAUNCHES = %d" % MAX_LAUNCHES)
sub("LOCK = HERE / 'launch_used.json'", "LOCK = HERE / 'launches_used.jsonl'")
sub("""    if LOCK.exists():
        fails.append(f'one launch only, already used: {LOCK.read_text().strip()}')
""", """    used = LOCK.read_text().splitlines() if LOCK.exists() else []
    if len(used) >= MAX_LAUNCHES:
        fails.append(f'launch cap {MAX_LAUNCHES} reached')
    if any(json.loads(l)['tag'] == f'{REQ}' for l in used):
        fails.append(f'{REQ} already launched, no retries')
""")
sub("""    print(f'preflight: free RAM {ram:.1f} GB,""", """    print('open, allowed:', sorted({c for c in OPEN_OK if f'"{c}' in names}), flush=True)
    print(f'preflight: free RAM {ram:.1f} GB,""")
sub("    LOCK.write_text(json.dumps({'tag': tag, 'at': time.strftime('%Y-%m-%dT%H:%M:%S'), 'exe': got}), encoding='utf-8')\n",
    "    with LOCK.open('a', encoding='utf-8') as f:\n        f.write(json.dumps({'tag': f'{arm}{tag}', 'at': time.strftime('%Y-%m-%dT%H:%M:%S'), 'exe': got}) + '\\n')\n")
sub("    envs.update({k: v.replace('{rt}', str(rtdir)) for k, v in ARMS[ARM][1].items()})   # the arm keys last\n",
    "    if ARM != 'V':\n        envs = {k: v for k, v in envs.items() if not k.startswith(QUIET)}\n"
    "    if ARM in NO_NAV:\n        envs.pop('PS3_DEV_SKIP_INTRO', None)\n"
    "    envs.update({k: v.replace('{rt}', str(rtdir)) for k, v in ARMS[ARM][1].items()})   # the arm keys last\n")
sub("            self.nav_pol = NavPolicy(max_presses=self.MAX_PRESSES, **NAV[ARM])\n",
    "            self.nav_pol = NavPolicy(max_presses=0 if ARM in NO_NAV else self.MAX_PRESSES, **NAV[ARM])\n")
sub("def main(mode, arm=None, tag=None):\n", "def main(mode, arm=None, tag=None):\n    global REQ\n    REQ = f'{arm}{tag}'\n")
sub("        for a in 'BC':", "        for a in 'BWFMXVST':")
out = HERE.parent / 'ab'
out.mkdir(exist_ok=True)
(out / 'cpath_sites.cfg').write_text((ROOT / 'generated' / 'analysis' / 't180' / 'ab' / 'cpath_sites.cfg').read_text(encoding='utf-8').replace('profile=5\nreport=5000\ntop=40', 'report=0'), encoding='utf-8')
(out / 'run_t181.py').write_text(src, encoding='utf-8')
print('wrote', out / 'run_t181.py', 'pin', pin)
