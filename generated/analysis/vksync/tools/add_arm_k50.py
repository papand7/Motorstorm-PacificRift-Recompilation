"""Add launch Kk50: Kk49 without the texture pack (RSX_RES_SCALE=1.5, no dynamic resolution; exe
c131cfd4), run under the inclusive sampler on the 8 busiest threads (SAMPLE_INCL=1 SAMPLE_THREADS=8):
every function seen running, for a link order file (tools/make_order.py) that packs the hot code.

usage: py -3 add_arm_k50.py"""
import pathlib

p = pathlib.Path(__file__).resolve().parents[1] / 'ab2' / 'run_vk.py'
s = p.read_bytes().decode('utf-8')
assert '\r\n' not in s
lines = s.split('\n')
i = [k for k, l in enumerate(lines) if l.startswith("ARMS['K']") and '   # Kk49: ' in l][0]
lines.insert(i + 1, "ARMS['K'] = ('r', {k: v for k, v in ARMS['K'][1].items() if k != 'RSX_TEX_PACK'})"
                    "   # Kk50: exe c131cfd4, Kk49 without the pack, under the inclusive sampler (8 threads)")
s = '\n'.join(lines)


def sub(a, b):
    global s
    assert s.count(a) == 1, (a, s.count(a))
    s = s.replace(a, b)


sub("'Kk48', 'Kk49', 'Yy1']", "'Kk48', 'Kk49', 'Kk50', 'Yy1']")
sub("MAX_LAUNCHES = 96", "MAX_LAUNCHES = 97")
p.write_bytes(s.encode('utf-8'))
print('ok')
