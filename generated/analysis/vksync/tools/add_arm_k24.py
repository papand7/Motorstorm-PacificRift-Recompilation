"""Add launch Kk24: Kk23's configuration (RSX_BE_THREAD=ab) on an exe whose recording thread
has a 4 MB ring (in the CPU's 32 MB L3; Kk23's 64 MB one went through DRAM at about 47 MB a
present), queues a vertex constant block as the rows that changed, and reports the bytes each
call queued ([be-thread]).

usage: py -3 add_arm_k24.py <exe sha256>"""
import pathlib
import sys

pin = sys.argv[1]
assert len(pin) == 64, pin
p = pathlib.Path(__file__).resolve().parents[1] / 'ab2' / 'run_vk.py'
s = p.read_bytes().decode('utf-8')
lines = s.split('\n')
i = [k for k, l in enumerate(lines) if l.startswith("ARMS['K'] = ('r', {**{k: v for k, v in ARMS['K'][1].items() if k != 'PS3_DRAIN_IDLE_MS'}, 'RSX_BE_THREAD': 'ab'})")][0]
eol = '\r' if lines[i].endswith('\r') else ''
new = ("ARMS['K'] = ('r', dict(ARMS['K'][1]))"
       "   # Kk24: exe %s, Kk23's configuration; 4 MB ring, vertex constant rows, bytes by call" % pin[:8] + eol)
lines.insert(i + 1, new)
s = '\n'.join(lines)


def sub(a, b):
    global s
    assert s.count(a) == 1, (a, s.count(a))
    s = s.replace(a, b)


sub("'Kk22', 'Kk23', 'Yy1']", "'Kk22', 'Kk23', 'Kk24', 'Yy1']")
sub("MAX_LAUNCHES = 70", "MAX_LAUNCHES = 71")
sub("PIN = '5ee39ea9d386a775f53f37ee063ca8a5a92ebcd42a3ede841247160d20b9b735'   # ",
    "PIN = '%s'   # RSX_BE_THREAD 4 MB ring (Kk24); " % pin)
p.write_bytes(s.encode('utf-8'))
print('ok')
