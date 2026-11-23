"""Add launch Kk36: Kk35's configuration on exe a727f497 with the guest main thread alone on one
physical core (SMT sibling unused by the process, every other thread off that core) on and off by
turns (PS3_MAIN_CORE=ab; [eng-ab], [main-core]). Kk32-Kk35: about nine busy host threads share
6 cores / 12 logical processors, several of them spinning; the main thread's game code sets the
frame. No profiler, no trace.

usage: py -3 add_arm_k36.py <exe sha256>"""
import pathlib
import sys

pin = sys.argv[1]
assert len(pin) == 64, pin
p = pathlib.Path(__file__).resolve().parents[1] / 'ab2' / 'run_vk.py'
s = p.read_bytes().decode('utf-8')
lines = s.split('\n')
i = [k for k, l in enumerate(lines) if l.startswith("ARMS['K']") and '   # Kk35: ' in l][0]
eol = '\r' if lines[i].endswith('\r') else ''
new = ("ARMS['K'] = ('r', {**ARMS['K'][1], 'PS3_MAIN_CORE': 'ab'})"
       "   # Kk36: exe %s, Kk35 + main thread alone on a physical core, on and off by turns ([eng-ab])"
       % pin[:8] + eol)
lines.insert(i + 1, new)
s = '\n'.join(lines)


def sub(a, b):
    global s
    assert s.count(a) == 1, (a, s.count(a))
    s = s.replace(a, b)


sub("'Kk34', 'Kk35', 'Yy1']", "'Kk34', 'Kk35', 'Kk36', 'Yy1']")
sub("MAX_LAUNCHES = 82", "MAX_LAUNCHES = 83")
sub("PIN = 'f71034a0cb7c5f43e879bf879bd77da7b809b4fe13cb1877ebf9413144a05396'   # ",
    "PIN = '%s'   # PS3_MAIN_CORE (Kk36); " % pin)
p.write_bytes(s.encode('utf-8'))
print('ok')
