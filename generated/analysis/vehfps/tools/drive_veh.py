r"""Throttle-only driver for the vehfps arms (auto_drive.py without the F9 shots): once the newest
vksync/ab2/runtime-<tag>-* notes race_entry, wait `wait_s`, then hold R2 (PAD_FILE mask 0x0200) until the
runner's race stop. usage: py -3 drive_veh.py <tag e.g. veh60> [wait_s 6]"""
import pathlib
import sys
import time

ab2 = pathlib.Path(__file__).resolve().parents[2] / 'vksync' / 'ab2'
tag = sys.argv[1]
wait_s = float(sys.argv[2]) if len(sys.argv) > 2 else 6.0
t0 = time.time()
while time.time() - t0 < 900:
    ds = sorted(ab2.glob(f'runtime-{tag}-*'))
    if ds:
        rt = ds[-1]
        tl = rt / 'timeline.jsonl'
        if tl.exists() and 'race_entry' in tl.read_text(encoding='utf-8', errors='replace'):
            break
    time.sleep(1)
else:
    sys.exit('no race_entry')
print('race entry', rt.name, flush=True)
time.sleep(wait_s)
(rt / 'pad.txt').write_text('0x0200 1000000\n')
print('throttle', flush=True)
