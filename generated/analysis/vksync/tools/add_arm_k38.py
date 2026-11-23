"""Add launch Kk38: a repeat of Kk37 (exe c693e2cb, PS3_MAIN_PRIO=ab), to replicate its in-run A/B
(main thread at THREAD_PRIORITY_HIGHEST 32.50 vs normal 32.88 ms a present, 9 race windows).

usage: py -3 add_arm_k38.py"""
import pathlib

p = pathlib.Path(__file__).resolve().parents[1] / 'ab2' / 'run_vk.py'
s = p.read_bytes().decode('utf-8')
lines = s.split('\n')
i = [k for k, l in enumerate(lines) if l.startswith("ARMS['K']") and '   # Kk37: ' in l][0]
eol = '\r' if lines[i].endswith('\r') else ''
lines.insert(i + 1, "ARMS['K'] = ('r', dict(ARMS['K'][1]))   # Kk38: exe c693e2cb, a repeat of Kk37" + eol)
s = '\n'.join(lines)


def sub(a, b):
    global s
    assert s.count(a) == 1, (a, s.count(a))
    s = s.replace(a, b)


sub("'Kk36', 'Kk37', 'Yy1']", "'Kk36', 'Kk37', 'Kk38', 'Yy1']")
sub("MAX_LAUNCHES = 84", "MAX_LAUNCHES = 85")
p.write_bytes(s.encode('utf-8'))
print('ok')
