"""Add launch Kk25: Kk24's configuration (RSX_BE_THREAD=ab) on an exe whose ring keeps the words
both threads write on cache lines of their own and stores head/tail every 16/32 calls rather than
every call (Kk24: the walker took 15% more cycles with the thread on; false sharing suspected).

usage: py -3 add_arm_k25.py <exe sha256>"""
import pathlib
import sys

pin = sys.argv[1]
assert len(pin) == 64, pin
p = pathlib.Path(__file__).resolve().parents[1] / 'ab2' / 'run_vk.py'
s = p.read_bytes().decode('utf-8')
lines = s.split('\n')
i = [k for k, l in enumerate(lines) if l.startswith("ARMS['K'] = ('r', dict(ARMS['K'][1]))   # Kk24")][0]
eol = '\r' if lines[i].endswith('\r') else ''
new = ("ARMS['K'] = ('r', dict(ARMS['K'][1]))"
       "   # Kk25: exe %s, Kk24's configuration; shared words on lines of their own, head/tail every 16/32 calls" % pin[:8] + eol)
lines.insert(i + 1, new)
s = '\n'.join(lines)


def sub(a, b):
    global s
    assert s.count(a) == 1, (a, s.count(a))
    s = s.replace(a, b)


sub("'Kk23', 'Kk24', 'Yy1']", "'Kk23', 'Kk24', 'Kk25', 'Yy1']")
sub("MAX_LAUNCHES = 71", "MAX_LAUNCHES = 72")
sub("PIN = '70a9077aee5ac905f7cf4f82ea4f27fb7dc24dd61492568a34644ac202eaf418'   # ",
    "PIN = '%s'   # RSX_BE_THREAD lines of their own (Kk25); " % pin)
p.write_bytes(s.encode('utf-8'))
print('ok')
