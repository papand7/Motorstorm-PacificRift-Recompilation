r"""Create a gate file once the newest runtime-<tag>-* notes race_entry; STOP the run `stop_s` later.
usage: py -3 gate_at_race.py <tag> <gate file> [delay_s 3] [stop_s 30]"""
import pathlib, sys, time
ab2 = pathlib.Path(__file__).resolve().parents[1] / 'ab2'
tag, gate = sys.argv[1], pathlib.Path(sys.argv[2])
delay, stop = (float(sys.argv[3]) if len(sys.argv) > 3 else 3.0), (float(sys.argv[4]) if len(sys.argv) > 4 else 30.0)
gate.unlink(missing_ok=True)
t0 = time.time()
while time.time() - t0 < 900:
    ds = sorted(ab2.glob(f'runtime-{tag}-*'))
    if ds and (ds[-1] / 'timeline.jsonl').exists() and 'race_entry' in (ds[-1] / 'timeline.jsonl').read_text(errors='replace'):
        break
    time.sleep(1)
else:
    sys.exit('no race_entry')
time.sleep(delay)
gate.write_text('on\n'); print('gate on', flush=True)
(ds[-1] / 'pad.txt').write_text('0x0200 1000000\n')
time.sleep(stop)
gate.unlink(missing_ok=True)
(ds[-1] / 'STOP').write_text('gate_at_race done\n'); print('STOP', flush=True)
