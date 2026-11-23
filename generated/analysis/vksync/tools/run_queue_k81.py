r"""Runs the queued arms Kk81-Kk86 one after another (run at the PC's console, not over Remote Desktop:
run_vk.py refuses an RDP session). For each: pin its exe (set_pin.py), prepare, dry run, launch. Stops at
the first failure. Afterwards the build exe is the latest (ec5ce88e) again.
  Kk81/Kk83 base 9531e520, Kk82/Kk84 PGO 8df22c49 (quiet PGO A/B, Kk71 configuration)
  Kk85 20ba7377 with MSPR_PATCH unset (default drs)
  Kk86 ec5ce88e with RSX_SHADOW_STABLE=1 + shadow capture
Close SSX, Nightfire, BF1943 and the Epic launcher first.
usage: py -3 run_queue_k81.py [first_tag]   (e.g. k84 to resume)"""
import pathlib, subprocess, sys

ROOT = pathlib.Path(__file__).resolve().parents[4]
AB2 = ROOT / 'generated' / 'analysis' / 'vksync' / 'ab2'
TOOLS = AB2.parent / 'tools'
VK = ROOT / 'build' / 'motorstorm-vkgame'
KEEP = VK / 'MotorStormPacificRiftRecomp.exe.keep-'
PGO = ROOT / 'build' / 'motorstorm-vkgame-pgouse' / 'MotorStormPacificRiftRecomp.exe'
QUEUE = [('k81', f'{KEEP}9531e520', 'base 9531e520 (Kk81 quiet PGO A/B)'),
         ('k82', str(PGO), 'PGO 8df22c49 (Kk82 quiet PGO A/B)'),
         ('k83', f'{KEEP}9531e520', 'base 9531e520 (Kk83 quiet PGO A/B)'),
         ('k84', str(PGO), 'PGO 8df22c49 (Kk84 quiet PGO A/B)'),
         ('k85', f'{KEEP}20ba7377', 'exe 20ba7377, MSPR_PATCH unset (Kk85 default drs)'),
         ('k86', f'{KEEP}ec5ce88e', 'exe ec5ce88e: 20ba7377 + RSX_SHADOW_STABLE (Kk86)')]


def run(*a):
    print('>', ' '.join(a), flush=True)
    return subprocess.run([sys.executable, *a], cwd=AB2).returncode


start = sys.argv[1] if len(sys.argv) > 1 else 'k81'
todo = QUEUE[[t for t, _, _ in QUEUE].index(start):]
try:
    for tag, exe, note in todo:
        if run(str(TOOLS / 'set_pin.py'), exe, note) or run('run_vk.py', 'prepare', 'r'):
            raise SystemExit(f'{tag}: pin/prepare failed')
        if run('run_vk.py', 'dryrun', 'K', tag):
            raise SystemExit(f'{tag}: dry run refused (see PREFLIGHT above)')
        rc = run('run_vk.py', 'launch', 'K', tag)
        print(f'{tag}: exit {rc}', flush=True)
        if rc not in (0,):
            raise SystemExit(f'{tag}: launch exit {rc}; stopping')
finally:
    subprocess.run([sys.executable, str(TOOLS / 'set_pin.py'), f'{KEEP}ec5ce88e',
                    'exe ec5ce88e: 20ba7377 + RSX_SHADOW_STABLE (restored after the Kk81-Kk86 queue)'], cwd=AB2)
