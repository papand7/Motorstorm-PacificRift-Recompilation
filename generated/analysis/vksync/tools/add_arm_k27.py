"""Add launch Kk27: Kk25's configuration (RSX_BE_THREAD=ab) on an exe whose vertex constant row
diff compares the whole block once, then rows inline (Kk26's profile: one memcmp call per 16-byte
row, about 15% of the walker with the copies). No profiler.

usage: py -3 add_arm_k27.py <exe sha256>"""
import pathlib
import sys

pin = sys.argv[1]
assert len(pin) == 64, pin
p = pathlib.Path(__file__).resolve().parents[1] / 'ab2' / 'run_vk.py'
s = p.read_bytes().decode('utf-8')
lines = s.split('\n')
i = [k for k, l in enumerate(lines) if l.startswith("ARMS['K'] = ('r', {**ARMS['K'][1], 'RSX_BE_THREAD': '1'})   # Kk26")][0]
eol = '\r' if lines[i].endswith('\r') else ''
new = ("ARMS['K'] = ('r', {**ARMS['K'][1], 'RSX_BE_THREAD': 'ab'})"
       "   # Kk27: exe %s, Kk25's configuration; vertex constant rows compared inline" % pin[:8] + eol)
lines.insert(i + 1, new)
s = '\n'.join(lines)


def sub(a, b):
    global s
    assert s.count(a) == 1, (a, s.count(a))
    s = s.replace(a, b)


sub("'Kk25', 'Kk26', 'Yy1']", "'Kk25', 'Kk26', 'Kk27', 'Yy1']")
sub("MAX_LAUNCHES = 73", "MAX_LAUNCHES = 74")
sub("PIN = '4c22cb5e80cc4e1d41535becff05ddcb9feef0547bdd4dba5f0498e1604ce5ac'   # ",
    "PIN = '%s'   # RSX_BE_THREAD inline row compare (Kk27); " % pin)
p.write_bytes(s.encode('utf-8'))
print('ok')
