"""T70C: the A/B controller's stop decisions on fed log lines, offline. finish() is replaced by a
recorder and the clock by a variable, so nothing is launched or killed. Usage: py -3 t70c_controller_sim.py"""
import importlib.util, sys, tempfile
from pathlib import Path
HERE = Path(__file__).resolve().parents[1] / 'ab'
spec = importlib.util.spec_from_file_location('ab', HERE / 'run_t70_ab.py')
ab = importlib.util.module_from_spec(spec); spec.loader.exec_module(ab)
fails = 0

def sim(lines_at, until):
    with tempfile.TemporaryDirectory() as d:
        c = ab.AbController(Path(d), 0.0, Path(d), 'sim')
        clock = {'t': 0.0}
        c.now = lambda: clock['t']
        why = []
        c.finish = lambda w: (why.append((clock['t'], w)), c.done.set())
        t = 0.0
        while t <= until and not why:
            clock['t'] = t
            for at, line in lines_at:
                if abs(at - t) < 0.05:
                    c.feed('stderr', line)
            c.check_global()
            t = round(t + 0.1, 1)
        c.log.close(); c.tl.close()
        return why[0] if why else None

print(f'window {ab.FTRACE_WINDOW} arm {ab.FTRACE_ARM} ARM_BY_S {ab.ARM_BY_S}')
cases = [('fast start: armed 154.8, written 196.4', [(154.8, '[ftrace] armed at t=154.8 s by fn=329D90 lr=8EE8C: recording t=157.8-196.0 s'),
                                                     (196.4, '[ftrace] wrote 400000 spans (0 dropped) to x')], 'ftrace written', 197.4),
         ('slow start: no race entry by 172 s', [], 'INVALID', 172.0),
         ('armed but never written', [(160.0, '[ftrace] armed at t=160.0 s by fn=329D90 lr=8EE8C: recording')], 'A/B session end', 205.0)]
for what, lines, want, at in cases:
    r = sim(lines, 210)
    ok = r is not None and r[1].startswith(want) and abs(r[0] - at) < 0.15
    fails += not ok
    print(f"[{'PASS' if ok else 'FAIL'}] {what}: stop at {r[0] if r else None} s: {r[1] if r else None}")
sys.exit(1 if fails else 0)
