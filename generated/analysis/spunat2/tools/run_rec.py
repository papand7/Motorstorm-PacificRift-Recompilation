r"""One 1.00 race with the SPU task recorder (PS3_SPU_TASKREC) on the private build
build/<bd>/MotorStormPacificRiftRecomp.exe, through vksync/ab2/run_vk.py (its preflight refuses to
start if another MotorStorm or launcher is running). The exe slot is private (this directory's
exe_v/), so another worker's ab2/exe_v is never touched.

usage: py -3 run_rec.py <tag> <build dir name> <rec dir> [images=491898574,341580667] [every=5] [max=12]
The recorder is armed once the race starts (race_entry in the timeline -> trigger file); the run is
stopped (STOP file) when every image has its recordings or 150 s after race entry."""
import hashlib, shutil, sys, threading, time
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[2]
AB2 = ROOT / 'generated' / 'analysis' / 'vksync' / 'ab2'
sys.path.insert(0, str(AB2))
tag, bd, recdir = sys.argv[1], sys.argv[2], Path(sys.argv[3]).resolve()
images = (sys.argv[4] if len(sys.argv) > 4 else '491898574,341580667')
every = sys.argv[5] if len(sys.argv) > 5 else '5'
mx = int(sys.argv[6]) if len(sys.argv) > 6 else 12
recdir.mkdir(parents=True, exist_ok=True)
trigger = recdir / 'TRIGGER'
trigger.unlink(missing_ok=True)

exe_src = ROOT / 'build' / bd / 'MotorStormPacificRiftRecomp.exe'
slot = HERE / 'exe_v'
slot.mkdir(exist_ok=True)
shutil.copy2(exe_src, slot / 'MotorStormPacificRiftRecomp.exe')
h = hashlib.sha256((slot / 'MotorStormPacificRiftRecomp.exe').read_bytes()).hexdigest()
(HERE / 'exe_v.sha256').write_text(h + '\n')
print('exe', h, flush=True)

import run_vk  # noqa: E402
run_vk.EXEDIR = HERE
run_vk.KEEP_100 = tuple(run_vk.KEEP_100) + (tag,)
run_vk.K_BY_TAG[tag] = ('v', {**run_vk.K_BY_TAG['k3070'][1],
                              'PS3_TRACE_OFF_FILE': str(AB2 / ('trace_off_' + tag)),
                              'PS3_SPU_TASKREC': str(recdir),
                              'PS3_SPU_TASKREC_IMG': images,
                              'PS3_SPU_TASKREC_TRIGGER': str(trigger),
                              'PS3_SPU_TASKREC_AFTER_MS': '3000',
                              'PS3_SPU_TASKREC_EVERY': every,
                              'PS3_SPU_TASKREC_MAX': str(mx)})
nimg = len(images.split(','))


def watcher():
    t0 = time.time()
    rt = None
    while time.time() - t0 < 400:
        ds = sorted(AB2.glob(f'runtime-{tag}-*'))
        if ds and (ds[-1] / 'timeline.jsonl').exists():
            rt = ds[-1]
            if 'race_entry' in (rt / 'timeline.jsonl').read_text(errors='replace'):
                break
        time.sleep(1)
    else:
        print('watcher: no race_entry', flush=True)
        return
    trigger.write_text('race\n')
    print('watcher: race entry, recorder armed', flush=True)
    t1 = time.time()
    while time.time() - t1 < 150:
        if len(list(recdir.glob('rec_*.bin'))) >= nimg * mx:
            time.sleep(15)   # let the last recordings close
            break
        time.sleep(2)
    (rt / 'STOP').write_text('recordings done\n')
    print('watcher: STOP', len(list(recdir.glob('rec_*.bin'))), 'recordings', flush=True)


threading.Thread(target=watcher, daemon=True).start()
sys.exit(run_vk.main('launch', 'K', tag))
