r"""Drive a run_vk.py race without a player: once the newest runtime-<tag>-* dir notes race_entry, hold R2
(throttle, PAD_FILE mask 0x0200) through its pad.txt, press F9 (RSX_SHOTS on) after `rec` s, F9 again after
`dur` s more, then write STOP. The bike goes straight (no steering), enough to move the camera over the
shadows. usage: py -3 auto_drive.py <tag e.g. k99> [wait_s 6] [rec_s 12] [dur_s 6]"""
import ctypes
import pathlib
import sys
import time

ab2 = pathlib.Path(__file__).resolve().parents[1] / 'ab2'
tag = sys.argv[1]
wait_s, rec_s, dur_s = (float(a) for a in (sys.argv[2:5] + ['6', '12', '6'][len(sys.argv[2:5]):]))


def f9():
    u = ctypes.windll.user32
    u.keybd_event(0x78, 0, 0, 0)
    time.sleep(0.15)   # RSX_SHOTS polls GetAsyncKeyState once a frame
    u.keybd_event(0x78, 0, 2, 0)


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
time.sleep(wait_s)
(rt / 'pad.txt').write_text('0x0200 1000000\n')
print('throttle', flush=True)
time.sleep(rec_s)
f9(); print('F9 on', flush=True)
time.sleep(dur_s)
f9(); print('F9 off', flush=True)
time.sleep(2)
(rt / 'STOP').write_text('auto_drive done\n')
print('STOP', flush=True)
