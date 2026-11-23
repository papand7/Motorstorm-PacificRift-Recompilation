r"""One 1.00 race launch for the SPU A/B (Kksr3..): the given exe in this directory's private exe slot
(exe_v/), so ab2/exe_v is never touched, the K3070 configuration (task stats, sc-wait), driven into a
race by generated/analysis/fx/tools/race_menu.py. RUN_VK_VISUAL_ONLY=1 (approved by the user: the EA
background service stays running for every arm).

usage: py -3 run_ab.py <tag> <exe path> [race_s 60] [extra env "K=V;K=V"]"""
import hashlib, os, shutil, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[2]
AB2 = ROOT / 'generated' / 'analysis' / 'vksync' / 'ab2'
sys.path.insert(0, str(AB2))
tag, exe_src = sys.argv[1], Path(sys.argv[2]).resolve()
race_s = sys.argv[3] if len(sys.argv) > 3 else '60'
extra = dict(kv.split('=', 1) for kv in (sys.argv[4].split(';') if len(sys.argv) > 4 else []) if '=' in kv)

slot = HERE / 'exe_v'
slot.mkdir(exist_ok=True)
shutil.copy2(exe_src, slot / 'MotorStormPacificRiftRecomp.exe')
h = hashlib.sha256((slot / 'MotorStormPacificRiftRecomp.exe').read_bytes()).hexdigest()
(HERE / 'exe_v.sha256').write_text(h + '\n')
print('exe', exe_src, h, flush=True)

os.environ['RUN_VK_VISUAL_ONLY'] = '1'
import run_vk  # noqa: E402
run_vk.EXEDIR = HERE
run_vk.KEEP_100 = tuple(run_vk.KEEP_100) + (tag,)
run_vk.K_BY_TAG[tag] = ('v', {**run_vk.K_BY_TAG['k3070'][1],
                              'PS3_TRACE_OFF_FILE': str(AB2 / ('trace_off_' + tag)), **extra})
drv = subprocess.Popen([sys.executable, str(ROOT / 'generated/analysis/fx/tools/race_menu.py'), tag, '8', '5', race_s],
                       stdout=open(HERE / 'logs' / f'race_menu_{tag}.txt', 'w'), stderr=subprocess.STDOUT)
rc = run_vk.main('launch', 'K', tag)
try:
    drv.wait(timeout=60)
except subprocess.TimeoutExpired:
    drv.kill()
print('race_menu rc', drv.returncode, flush=True)
sys.exit(rc)
