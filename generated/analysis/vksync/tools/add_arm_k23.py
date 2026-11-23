"""Add launch Kk23: Kk21's configuration (Kk22 without PS3_DRAIN_IDLE_MS) with the draw engine's
backend calls on a recording thread on and off by turns (RSX_BE_THREAD=ab; [eng-ab], [be-thread]):
does the walker reach the guest's reference sooner, and the frame end sooner, when the Vulkan
recording runs beside it? No profiler.

usage: py -3 add_arm_k23.py <exe sha256>"""
import pathlib
import sys

pin = sys.argv[1]
assert len(pin) == 64, pin
p = pathlib.Path(__file__).resolve().parents[1] / 'ab2' / 'run_vk.py'
s = p.read_bytes().decode('utf-8')
lines = s.split('\n')
i = [k for k, l in enumerate(lines) if l.startswith("ARMS['K'] = ('r', {**ARMS['K'][1], 'PS3_DRAIN_IDLE_MS': 'ab'})")][0]
eol = '\r' if lines[i].endswith('\r') else ''
new = ("ARMS['K'] = ('r', {**{k: v for k, v in ARMS['K'][1].items() if k != 'PS3_DRAIN_IDLE_MS'}, 'RSX_BE_THREAD': 'ab'})"
       "   # Kk23: exe %s, Kk21 + backend calls on a recording thread on and off by turns ([eng-ab], [be-thread])" % pin[:8] + eol)
lines.insert(i + 1, new)
s = '\n'.join(lines)


def sub(a, b):
    global s
    assert s.count(a) == 1, (a, s.count(a))
    s = s.replace(a, b)


sub("'Kk21', 'Kk22', 'Yy1']", "'Kk21', 'Kk22', 'Kk23', 'Yy1']")
sub("MAX_LAUNCHES = 69", "MAX_LAUNCHES = 70")
sub("PIN = '8114242dfefd1ecd8bffdcfa8e27e5e0e0f84f4d8b875d2785820b2727fc3c15'   # ",
    "PIN = '%s'   # RSX_BE_THREAD (Kk23); " % pin)
p.write_bytes(s.encode('utf-8'))
print('ok')
