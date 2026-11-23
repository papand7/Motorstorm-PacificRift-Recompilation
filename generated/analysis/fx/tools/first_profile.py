"""Make a 1.00 profile save in a run_vk.py launch with a fresh save folder (PS3_GAMEDATA_ROOT): once the
newest runtime-<tag>-* notes race_entry (the garage's "Choose Your Driver", 600+ draws), accept the driver
(UP to Yes, CROSS), then press CROSS every `gap` s, `n` times, through the first-run screens, then STOP.
Writes through the run's pad.txt (PAD_FILE). usage: py -3 first_profile.py <tag> [n 8] [gap 6]"""
import pathlib
import sys
import time

ab2 = pathlib.Path(__file__).resolve().parents[2] / 'vksync' / 'ab2'
tag = sys.argv[1]
n = int(sys.argv[2]) if len(sys.argv) > 2 else 8
gap = float(sys.argv[3]) if len(sys.argv) > 3 else 6.0


def press(rt, mask, polls, why):
    tmp = rt / 'pad.tmp'
    tmp.write_text(f'0x{mask:04X} {polls}\n')
    tmp.replace(rt / 'pad.txt')
    print(f'{time.strftime("%H:%M:%S")} {why} 0x{mask:04X}', flush=True)


t0 = time.time()
while time.time() - t0 < 600:
    ds = sorted(ab2.glob(f'runtime-{tag}-*'))
    if ds and (ds[-1] / 'timeline.jsonl').exists() and 'race_entry' in (ds[-1] / 'timeline.jsonl').read_text(
            encoding='utf-8', errors='replace'):
        rt = ds[-1]
        break
    time.sleep(1)
else:
    sys.exit('no garage')
time.sleep(4)
press(rt, 0x0010, 6, 'up (Yes)')
time.sleep(1.5)
press(rt, 0x4000, 20, 'cross (accept driver)')
for i in range(n):
    time.sleep(gap)
    press(rt, 0x4000, 20, f'cross {i + 1}')
time.sleep(10)
(rt / 'STOP').write_text('first_profile done\n')
print('STOP', flush=True)
