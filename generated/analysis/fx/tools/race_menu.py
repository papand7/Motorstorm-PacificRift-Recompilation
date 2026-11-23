"""Drive a 1.00 run_vk.py launch (profile save in PS3_GAMEDATA_ROOT) from the main menu into a race: the
runner's nav does not know 1.00's page loader, so this watches the run's stderr rsx-hb lines instead. Once
the menu is up (last_draws >= 35 after 20 s), press CROSS `n` times `gap` s apart (Festival, zone, ticket,
vehicle info, vehicle), wait for the race (last_draws >= 200), hold the throttle `race_s` s, then STOP.
usage: py -3 race_menu.py <tag> [n 8] [gap 5] [race_s 60]"""
import pathlib
import re
import sys
import time

root = pathlib.Path(__file__).resolve().parents[3]
ab2 = root / 'analysis' / 'vksync' / 'ab2'
tag = sys.argv[1]
n = int(sys.argv[2]) if len(sys.argv) > 2 else 8
gap = float(sys.argv[3]) if len(sys.argv) > 3 else 5.0
race_s = float(sys.argv[4]) if len(sys.argv) > 4 else 60.0
HB = re.compile(r'\[rsx-hb\] ms=(\d+) .*last_draws=(\d+)')


def press(rt, mask, polls, why):
    tmp = rt / 'pad.tmp'
    tmp.write_text(f'0x{mask:04X} {polls}\n')
    tmp.replace(rt / 'pad.txt')
    print(f'{time.strftime("%H:%M:%S")} {why} 0x{mask:04X}', flush=True)


def last_hb(run):
    f = run / 'stderr.log'
    if not f.exists():
        return None
    hits = HB.findall(f.read_text(encoding='utf-8', errors='replace')[-20000:])
    return (int(hits[-1][0]), int(hits[-1][1])) if hits else None


def wait_for(run, ok, limit):
    t0 = time.time()
    while time.time() - t0 < limit:
        hb = last_hb(run)
        if hb and ok(*hb):
            return hb
        time.sleep(1)
    return None


t0 = time.time()
rt = run = None
while time.time() - t0 < 600 and not (rt and run):
    ds = sorted(ab2.glob(f'runtime-{tag}-*'))
    rs = sorted((root / 'runs').glob(f'*-vk-K{tag}'))
    if ds and rs and rs[-1].stat().st_mtime >= t0 - 120:
        rt, run = ds[-1], rs[-1]
    time.sleep(1)
if not run:
    sys.exit('no run dir')
if not wait_for(run, lambda ms, d: ms > 20000 and d >= 35, 300):
    sys.exit('no menu')
print('menu', flush=True)
time.sleep(3)
for i in range(n):
    press(rt, 0x4000, 20, f'cross {i + 1}')
    time.sleep(gap)
hb = wait_for(run, lambda ms, d: d >= 200, 180)
if not hb:
    (rt / 'STOP').write_text('race_menu: no race\n')
    sys.exit('no race')
print('race at', hb, flush=True)
time.sleep(8)
press(rt, 0x0200, 1000000, 'throttle held')
time.sleep(race_s)
(rt / 'STOP').write_text('race_menu done\n')
print('STOP', flush=True)
