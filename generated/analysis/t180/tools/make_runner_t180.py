#!/usr/bin/env python3
"""T180 single-launch diagnostic runner (needs authorization): t177/ab/run_t177.py with the T180 exe and arm D.
Run from the main checkout copy of generated/analysis/t180/tools.
  py -3 generated/analysis/t180/tools/make_runner_t180.py <exe sha256>
  py -3 generated/analysis/t180/ab/run_t180.py prepare r ; dryrun D x ; launch D d1
Corrections to the T177 runner:
  RACE_STOP was empty, so arms ran to the 205 s cap instead of race + 45 s;
  FORBIDDEN refused the critical-path trace;
  the trace window 150:22 was for the poll arm's race entry;
  cpath_sites.cfg has report=0, so the sampling profile would never be written;
  gate and probe lines were not timestamped by the controller;
  no check of conflicting processes, RAM, VRAM or game data hashes; no guard against a second launch."""
import re, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
pin = (sys.argv[1] if len(sys.argv) > 1 else '').lower()
if not re.fullmatch(r'[0-9a-f]{64}', pin):
    raise SystemExit('usage: make_runner_t180.py <exe sha256 of build/motorstorm-t180>')
t177 = ROOT / 'generated' / 'analysis' / 't177' / 'ab'
src = (t177 / 'run_t177.py').read_text(encoding='utf-8')


def sub(old, new):
    global src
    assert src.count(old) == 1, (old[:70], src.count(old))
    src = src.replace(old, new)


sub("'motorstorm-t177'", "'motorstorm-t180'")
sub("PIN = '86896155d5a6d31a1a36899cf575668ea013a7ce9f8d5a13ecba36c8a72c4113'", f"PIN = '{pin}'")
sub("f't177-{arm}{tag}'", "f't180-{arm}{tag}'")
sub("FORBIDDEN = ('D3D12_DBG',", """ARMS = {'D': ('r', {**_A, _WAKE: _GATE, 'PS3_LOAD_PROBE': '1000', 'PS3_HLE_WAIT_MS': '1000',
                    'PS3_CRITICAL_PATH_TRACE': '10:50:{rt}/cpath.txt'})}
FORBIDDEN = ('D3D12_DBG',""")
sub("'PS3_CRITICAL_PATH_TRACE', 'CELLMARK_IGPU')", "'CELLMARK_IGPU')")
sub("RACE_STOP = {}", "RACE_STOP = {'D': 45.0}")
sub("if line.startswith(('[visual] effective',", "if line.startswith(('[frame-phase]', '[load-probe]', '[lwc-wake]', '[visual] effective',")
sub("    if mode == 'launch':\n        if arm not in ARMS or not tag:", "    env_preflight()   # before the HDD copies\n    if mode == 'launch':\n        if arm not in ARMS or not tag:")
sub("    rtdir.mkdir()\n    (rtdir / 'pad.txt')", "    LOCK.write_text(json.dumps({'tag': tag, 'at': time.strftime('%Y-%m-%dT%H:%M:%S'), 'exe': got}), encoding='utf-8')\n    rtdir.mkdir()\n    (rtdir / 'pad.txt')")
sub("def preflight(hdd1):", '''CONFLICTS = ('ollama', 'llama-server', 'leoffice', 'epicgameslauncher', 'epicwebhelper', 'eadesktop', 'eabackgroundservice', 'godot')
MIN_FREE_RAM_GB, MIN_FREE_VRAM_MB = 16.0, 6000
GAME_DATA = ('original/game/PS3_GAME/USRDIR/EBOOT.BIN', 'original/game/PS3_GAME/PARAM.SFO', 'generated/decrypted/EBOOT.elf')
LOCK = HERE / 'launch_used.json'


def env_preflight():
    """Refuses on any failed check, in dryrun too. Does not close anything. The lock is written just before the launch."""
    fails = []
    if LOCK.exists():
        fails.append(f'one launch only, already used: {LOCK.read_text().strip()}')
    q = subprocess.run(['query', 'session'], capture_output=True, text=True).stdout
    active = [l for l in q.splitlines() if l.startswith('>')]
    if not active or not active[0].startswith('>console'):
        fails.append(f'not a console session: {active}')
    names = subprocess.run(['tasklist', '/FO', 'CSV', '/NH'], capture_output=True, text=True).stdout.lower()
    found = sorted({c for c in CONFLICTS if f'"{c}' in names})
    if found:
        fails.append(f'conflicting processes running: {found}')
    q = '(Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory'
    ram = int(subprocess.run(['powershell', '-NoProfile', '-Command', q], capture_output=True, text=True).stdout.strip()) / (1 << 20)
    if ram < MIN_FREE_RAM_GB:
        fails.append(f'free RAM {ram:.1f} GB < {MIN_FREE_RAM_GB}')
    v = subprocess.run(['nvidia-smi', '--query-gpu=memory.total,memory.used', '--format=csv,noheader,nounits'], capture_output=True, text=True).stdout.split(',')
    vram = int(v[0]) - int(v[1])
    if vram < MIN_FREE_VRAM_MB:
        fails.append(f'free VRAM {vram} MiB < {MIN_FREE_VRAM_MB}')
    data = {p: sha(ROOT / p) for p in GAME_DATA}
    print(f'preflight: free RAM {ram:.1f} GB, free VRAM {vram} MiB, session {active}, data {data}', flush=True)
    if fails:
        raise SystemExit('PREFLIGHT FAIL: ' + '; '.join(fails))


def preflight(hdd1):''')
out = HERE.parent / 'ab'
out.mkdir(exist_ok=True)
cfg = (t177 / 'cpath_sites.cfg').read_text(encoding='utf-8')
assert cfg.count('report=0') == 1
cfg = cfg.replace('report=0', 'profile=5\nreport=5000\ntop=40')
(out / 'cpath_sites.cfg').write_text(cfg, encoding='utf-8')
(out / 'run_t180.py').write_text(src, encoding='utf-8')
print('wrote', out / 'run_t180.py', 'pin', pin)
