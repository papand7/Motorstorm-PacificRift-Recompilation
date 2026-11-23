"""Add launch Kk18: the Kk14 configuration (Kk17's) on exe 1e7da189 with the FIFO walker's packet
fast path on and off by turns (GCM_FIFO_FAST=ab; [eng-ab], [fifo-fast]). Kk15's trace put the RSX
drain on the frame's critical path; the walker's per-word loop is its largest single cost.

usage: py -3 add_arm_k18.py <exe sha256>"""
import pathlib
import sys

pin = sys.argv[1]
assert len(pin) == 64, pin
p = pathlib.Path(__file__).resolve().parents[1] / 'ab2' / 'run_vk.py'
s = p.read_bytes().decode('utf-8')
lines = s.split('\n')
i = [k for k, l in enumerate(lines) if l.startswith("ARMS['K'] = ('r', {k: v for k, v in ARMS['K'][1].items() if k != 'PS3_FRAME_CLOCK_KICK'})")][0]
eol = '\r' if lines[i].endswith('\r') else ''
new = ("ARMS['K'] = ('r', {**ARMS['K'][1], 'GCM_FIFO_FAST': 'ab'})"
       "   # Kk18: exe %s, Kk17 + the walker's packet fast path on and off by turns ([eng-ab], [fifo-fast])" % pin[:8] + eol)
lines.insert(i + 1, new)
s = '\n'.join(lines)


def sub(a, b):
    global s
    assert s.count(a) == 1, (a, s.count(a))
    s = s.replace(a, b)


sub("'Kk17', 'Yy1']", "'Kk17', 'Kk18', 'Yy1']")
sub("MAX_LAUNCHES = 64", "MAX_LAUNCHES = 65")
sub("PIN = '0506ee54c05a8e0fb6bbd64ac25bde6dbf95b0e858724d3cdbefe62e81416f8e'   # ",
    "PIN = '%s'   # GCM_FIFO_FAST (Kk18); " % pin)
p.write_bytes(s.encode('utf-8'))
print('ok')
