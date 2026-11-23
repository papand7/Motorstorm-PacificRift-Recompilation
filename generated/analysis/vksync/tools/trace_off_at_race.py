r"""Write the PS3_TRACE_OFF_FILE once the newest runtime-<tag>-* notes race_entry (no input: a play session).
usage: py -3 trace_off_at_race.py <tag> <off file> [delay_s 3]"""
import pathlib, sys, time
ab2 = pathlib.Path(__file__).resolve().parents[1] / 'ab2'
tag, off = sys.argv[1], pathlib.Path(sys.argv[2])
delay = float(sys.argv[3]) if len(sys.argv) > 3 else 3.0
off.unlink(missing_ok=True)
t0 = time.time()
while time.time() - t0 < 1800:
    ds = sorted(ab2.glob(f'runtime-{tag}-*'))
    if ds and (ds[-1] / 'timeline.jsonl').exists() and 'race_entry' in (ds[-1] / 'timeline.jsonl').read_text(errors='replace'):
        time.sleep(delay)
        off.write_text('race\n')
        print('tracer off', flush=True)
        break
    time.sleep(1)
