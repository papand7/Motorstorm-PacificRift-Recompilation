"""Add launch Kk34 (a repeat of Kk33 with the unwinding sampler). Kk33: Kk32's configuration without the critical-path trace, to be run under the
inclusive stack sampler (SAMPLE_INCL=1 tools/sample_race.py ab2/sample_k33.json 45 55): which guest
functions, inclusively, fill the main thread's running time (Kk32: 30.7 of 42.8 ms a frame).

usage: py -3 add_arm_k33.py"""
import pathlib

p = pathlib.Path(__file__).resolve().parents[1] / 'ab2' / 'run_vk.py'
s = p.read_bytes().decode('utf-8')
lines = s.split('\n')
i = [k for k, l in enumerate(lines) if '   # Kk32: ' in l and l.startswith("ARMS['K']")][0]
eol = '\r' if lines[i].endswith('\r') else ''
new = ("ARMS['K'] = ('r', dict(ARMS['K'][1]))"
       "   # Kk34: exe f71034a0, a repeat of Kk33 under the unwinding inclusive sampler" + eol)
lines.insert(i + 1, new)
s = '\n'.join(lines)


def sub(a, b):
    global s
    assert s.count(a) == 1, (a, s.count(a))
    s = s.replace(a, b)


sub("'Kk32', 'Kk33', 'Yy1']", "'Kk32', 'Kk33', 'Kk34', 'Yy1']")
sub("MAX_LAUNCHES = 80", "MAX_LAUNCHES = 81")
p.write_bytes(s.encode('utf-8'))
print('ok')
