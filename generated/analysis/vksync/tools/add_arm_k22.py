"""Add launch Kk22: Kk21's configuration with the drain thread's idle wait 1 ms and 4 ms by
turns (PS3_DRAIN_IDLE_MS=ab; [eng-ab]). The game flushes a race frame once; the drain then starts
at the end of the current 4 ms idle wait, and the game waits for that frame's reference. No
profiler (Kk21 had one).

usage: py -3 add_arm_k22.py <exe sha256>"""
import pathlib
import sys

pin = sys.argv[1]
assert len(pin) == 64, pin
p = pathlib.Path(__file__).resolve().parents[1] / 'ab2' / 'run_vk.py'
s = p.read_bytes().decode('utf-8')
lines = s.split('\n')
i = [k for k, l in enumerate(lines) if l.startswith("ARMS['K'] = ('r', {k: v for k, v in ARMS['K'][1].items() if k != 'RSX_IDX_FUSED'})")][0]
eol = '\r' if lines[i].endswith('\r') else ''
new = ("ARMS['K'] = ('r', {**ARMS['K'][1], 'PS3_DRAIN_IDLE_MS': 'ab'})"
       "   # Kk22: exe %s, Kk21 + the drain idle wait 1 ms and 4 ms by turns ([eng-ab])" % pin[:8] + eol)
lines.insert(i + 1, new)
s = '\n'.join(lines)


def sub(a, b):
    global s
    assert s.count(a) == 1, (a, s.count(a))
    s = s.replace(a, b)


sub("'Kk21', 'Yy1']", "'Kk21', 'Kk22', 'Yy1']")
sub("MAX_LAUNCHES = 68", "MAX_LAUNCHES = 69")
sub("PIN = 'd9636306160d87bd9cda219e1ed4b5719f4ac6135efccbfb0f2dae570b8570b2'   # ",
    "PIN = '%s'   # PS3_DRAIN_IDLE_MS (Kk22); " % pin)
p.write_bytes(s.encode('utf-8'))
print('ok')
