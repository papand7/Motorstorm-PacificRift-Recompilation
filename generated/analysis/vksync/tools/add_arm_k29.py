"""Add launch Kk29: a repeat of Kk28 (same exe 84ee1a83, PS3_VMX_FAST=ab), to replicate its
in-run A/B (fast paths on 50.20 vs off 51.28 ms a present over 5 race windows).

usage: py -3 add_arm_k29.py"""
import pathlib

p = pathlib.Path(__file__).resolve().parents[1] / 'ab2' / 'run_vk.py'
s = p.read_bytes().decode('utf-8')
lines = s.split('\n')
i = [k for k, l in enumerate(lines) if l.startswith("ARMS['K'] = ('r', {**{k: v for k, v in ARMS['K'][1].items() if k != 'RSX_BE_THREAD'}, 'PS3_VMX_FAST': 'ab'})   # Kk28")][0]
eol = '\r' if lines[i].endswith('\r') else ''
lines.insert(i + 1, "ARMS['K'] = ('r', dict(ARMS['K'][1]))   # Kk29: exe 84ee1a83, a repeat of Kk28" + eol)
s = '\n'.join(lines)


def sub(a, b):
    global s
    assert s.count(a) == 1, (a, s.count(a))
    s = s.replace(a, b)


sub("'Kk27', 'Kk28', 'Yy1']", "'Kk27', 'Kk28', 'Kk29', 'Yy1']")
sub("MAX_LAUNCHES = 75", "MAX_LAUNCHES = 76")
p.write_bytes(s.encode('utf-8'))
print('ok')
