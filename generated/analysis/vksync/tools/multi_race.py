r"""Drive a run_vk.py arm through several races in a row, quitting each to the menu (the stale-keys repro:
generated/analysis/stalekeys/RESULTS.md). Once the newest runtime-<tag>-* notes race_entry: hold the throttle for
`race_s`, then quit through the pause menu (START, `downs` x DOWN, CROSS, CROSS to confirm), then press CROSS every
`cross_gap` s `crosses` times (the runner's own Festival route takes CROSS on every screen) to start the next race,
hold the throttle again, and so on `races` times; then STOP. Blind by design: the arm's automatic RSX_SHOTS
(every 10 s) show where each step landed; the [stale-keys] lines in stderr show whether a recycled handle met a key.
Masks: START 0x0008, DOWN 0x0040, CROSS 0x4000, throttle (R2) 0x0200.
usage: py -3 multi_race.py <tag e.g. mr1o> [races 4] [race_s 25] [downs 2] [crosses 9] [cross_gap 6.5]"""
import pathlib
import sys
import time

ab2 = pathlib.Path(__file__).resolve().parents[1] / 'ab2'
tag = sys.argv[1]
d = ['4', '25', '2', '9', '6.5']
a = sys.argv[2:7] + d[len(sys.argv[2:7]):]
races, race_s, downs, crosses, cross_gap = int(a[0]), float(a[1]), int(a[2]), int(a[3]), float(a[4])


def pad(rt, mask, polls, note):
    p, tmp = rt / 'pad.txt', rt / 'pad.tmp'
    tmp.write_text(f'0x{mask:04X} {polls}\n')
    tmp.replace(p)
    print(f'{time.strftime("%H:%M:%S")} {note} 0x{mask:04X}', flush=True)


t0 = time.time()
rt = None
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
time.sleep(8)   # the runner's flyover skips (4 s, 7 s)
for n in range(races):
    pad(rt, 0x0200, 1000000, f'race {n + 1}: throttle')
    time.sleep(race_s)
    pad(rt, 0x0000, 2, 'release')
    time.sleep(1.0)
    pad(rt, 0x0008, 6, 'pause (START)')
    time.sleep(2.0)
    for _ in range(downs):
        pad(rt, 0x0040, 6, 'DOWN')
        time.sleep(0.9)
    pad(rt, 0x4000, 6, 'CROSS (quit)')
    time.sleep(2.0)
    pad(rt, 0x4000, 6, 'CROSS (confirm)')
    if n + 1 == races:
        break
    time.sleep(12.0)   # the unload and the menu
    for k in range(crosses):
        pad(rt, 0x4000, 20, f'CROSS {k + 1}/{crosses} toward race {n + 2}')
        time.sleep(cross_gap)
    time.sleep(20.0)   # load and flyover
    pad(rt, 0x4000, 20, 'CROSS (flyover skip)')
    time.sleep(3.0)
    pad(rt, 0x4000, 20, 'CROSS (flyover skip)')
    time.sleep(4.0)
time.sleep(20.0)       # the menu after the last quit (the user saw it rainbow)
(rt / 'STOP').write_text('multi_race done\n')
print('STOP', flush=True)
