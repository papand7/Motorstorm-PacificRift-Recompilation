"""Add launch Kk37: Kk36 with PS3_MAIN_PRIO=ab instead of PS3_MAIN_CORE (Kk36: the main thread alone on a core was 1.45 ms slower). The rest of this note is Kk36's:
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
i = [k for k, l in enumerate(lines) if l.startswith("ARMS['K']") and '   # Kk36: ' in l][0]
eol = '\r' if lines[i].endswith('\r') else ''
new = ("ARMS['K'] = ('r', {**{k: v for k, v in ARMS['K'][1].items() if k != 'PS3_MAIN_CORE'}, 'PS3_MAIN_PRIO': 'ab'})"
       "   # Kk37: exe %s, Kk35 + main thread at THREAD_PRIORITY_HIGHEST, on and off by turns ([eng-ab])"
       % pin[:8] + eol)
lines.insert(i + 1, new)
s = '\n'.join(lines)


def sub(a, b):
    global s
    assert s.count(a) == 1, (a, s.count(a))
    s = s.replace(a, b)


sub("'Kk35', 'Kk36', 'Yy1']", "'Kk35', 'Kk36', 'Kk37', 'Yy1']")
sub("MAX_LAUNCHES = 83", "MAX_LAUNCHES = 84")
sub("PIN = 'a727f49774bb0a47ad575ca3d9e52e31cf485e2c971300daa7b6a8112617e499'   # ",
    "PIN = '%s'   # PS3_MAIN_PRIO (Kk37); " % pin)
p.write_bytes(s.encode('utf-8'))
print('ok')
