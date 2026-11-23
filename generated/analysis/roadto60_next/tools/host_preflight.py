r"""roadto60_next: host check before one A/B race launch. Read-only: lists processes, samples CPU/GPU, checks
free RAM/VRAM/disk, the session and the exe pins. Never launches or closes anything.

usage: py -3 host_preflight.py [--exe <path>=<sha256 prefix>]... [--seconds 10]
Exit 0 = PASS, 1 = FAIL (print says why), 2 = WARN only.
Why this exists: run_ab.py sets RUN_VK_VISUAL_ONLY=1, which turns run_vk.py's CONFLICTS check into a warning,
and CONFLICTS does not list other games or compilers; slowmode/FINDINGS.md showed both cause slow-mode races."""
import argparse
import csv
import hashlib
import io
import re
import shutil
import subprocess
import sys
import time

GAMES = re.compile(r'^(bf\w*|bfbc\w*|nightfire|rpcs3|eldenring|cs2|valorant|steamwebhelper_game)\.exe$', re.I)
BUILD = re.compile(r'^(clang|clang-cl|clang\+\+|cl|link|lld-link|ld\.lld|ninja|cmake|msbuild|cc1|cc1plus|rustc|cargo|'
                   r'gcc|g\+\+|make|mingw32-make|vctip|mspdbsrv)\.exe$', re.I)
OTHER_LOAD = re.compile(r'^(ollama|llama-server|godot\w*|blender|obs64|handbrake\w*|ffmpeg|7z|7zg|winrar|'
                        r'msmpeng_scan_placeholder)\.exe$', re.I)
GAME_EXE = 'MotorStormPacificRiftRecomp.exe'


def tasklist():
    out = subprocess.run(['tasklist', '/FO', 'CSV', '/NH'], capture_output=True, text=True).stdout
    return [row[0] for row in csv.reader(io.StringIO(out)) if row]


def cpu_busy(seconds):
    q = (f"(Get-Counter '\\Processor(_Total)\\% Processor Time' -SampleInterval 1 -MaxSamples {int(seconds)})"
         ".CounterSamples | ForEach-Object { $_.CookedValue }")
    vals = [float(x) for x in subprocess.run(['powershell', '-NoProfile', '-Command', q], capture_output=True,
                                             text=True).stdout.split() if re.match(r'^[\d.]+$', x)]
    return sum(vals) / len(vals) if vals else None


def gpu(samples=5):
    u, used, total = [], 0, 0
    for _ in range(samples):
        r = subprocess.run(['nvidia-smi', '--query-gpu=utilization.gpu,memory.used,memory.total', '--format=csv,noheader,nounits'],
                           capture_output=True, text=True).stdout.split(',')
        if len(r) >= 3:
            u.append(int(r[0])); used, total = int(r[1]), int(r[2])
        time.sleep(1)
    return (sum(u) / len(u) if u else None), total - used


def free_ram_gb():
    q = '(Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory'
    return int(subprocess.run(['powershell', '-NoProfile', '-Command', q], capture_output=True, text=True).stdout.strip()) / (1 << 20)


def session():
    q = subprocess.run(['query', 'session'], capture_output=True, text=True).stdout
    act = [l for l in q.splitlines() if l.startswith('>')]
    return act[0].strip() if act else ''


def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--exe', action='append', default=[])
    ap.add_argument('--seconds', type=int, default=10)
    o = ap.parse_args()
    fails, warns = [], []
    names = tasklist()
    low = {n.lower() for n in names}
    g = sorted({n for n in names if GAMES.match(n)})
    b = sorted({n for n in names if BUILD.match(n)})
    x = sorted({n for n in names if OTHER_LOAD.match(n)})
    if g:
        fails.append(f'other game running: {g}')
    if b:
        fails.append(f'compiler/build process running: {b}')
    if x:
        warns.append(f'other heavy app open: {x}')
    if GAME_EXE.lower() in low:
        fails.append(f'{GAME_EXE} already running')
    busy = cpu_busy(o.seconds)
    if busy is None:
        warns.append('CPU counter unreadable')
    else:
        cores = busy * 12 / 100
        print(f'CPU busy {busy:.1f} % = {cores:.2f} of 12 logical CPUs (idle desktop, before launch)')
        if cores >= 2.5:
            fails.append(f'host not idle: {cores:.2f} busy logical CPUs before launch (limit 2.5)')
        elif cores >= 1.2:
            warns.append(f'host busy {cores:.2f} logical CPUs before launch')
    gu, vfree = gpu()
    print(f'GPU util {gu} %, free VRAM {vfree} MiB')
    if gu is not None and gu >= 15:
        fails.append(f'GPU busy before launch: {gu:.0f} % (limit 15)')
    if vfree < 3000:
        fails.append(f'free VRAM {vfree} MiB < 3000')
    ram = free_ram_gb()
    print(f'free RAM {ram:.1f} GB')
    if ram < 16:
        fails.append(f'free RAM {ram:.1f} GB < 16')
    for d, need in (('C:\\', 12), ('D:\\', 10)):
        try:
            free = shutil.disk_usage(d).free / 1e9
        except OSError:
            continue
        print(f'{d} free {free:.1f} GB')
        if free < need:
            fails.append(f'{d} free {free:.1f} GB < {need} (C: must stay above 8 GB after the per-run HDD copies)')
    s = session()
    print('session:', s)
    if not (s.startswith('>console') or s.startswith('>rdp-tcp#')) or ' Active' not in s:
        fails.append(f'no active console/RDP session: {s!r}')
    for spec in o.exe:
        path, _, pin = spec.rpartition('=')
        try:
            h = sha(path)
        except OSError as e:
            fails.append(f'{path}: {e}')
            continue
        print(f'{path}: {h}')
        if not h.startswith(pin.lower()):
            fails.append(f'{path} sha256 {h[:8]} != pin {pin}')
    for w in warns:
        print('WARN', w)
    for f in fails:
        print('FAIL', f)
    print('PREFLIGHT', 'FAIL' if fails else ('WARN' if warns else 'PASS'))
    sys.exit(1 if fails else (2 if warns else 0))


if __name__ == '__main__':
    main()
