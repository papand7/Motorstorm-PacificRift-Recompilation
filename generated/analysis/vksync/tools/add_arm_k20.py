"""Add launch Kk20: Kk19's configuration with the fused index pass on and off by turns
(RSX_IDX_FUSED=ab; [eng-ab]). Kk19's profile put the per-draw index work -- a reference per
index, the dense remap, the topology rewrite -- at about a tenth of the RSX thread.

usage: py -3 add_arm_k20.py <exe sha256>"""
import pathlib
import sys

pin = sys.argv[1]
assert len(pin) == 64, pin
p = pathlib.Path(__file__).resolve().parents[1] / 'ab2' / 'run_vk.py'
s = p.read_bytes().decode('utf-8')
lines = s.split('\n')
i = [k for k, l in enumerate(lines) if l.startswith("ARMS['K'] = ('r', {k: v for k, v in ARMS['K'][1].items() if k != 'GCM_FIFO_FAST'})")][0]
eol = '\r' if lines[i].endswith('\r') else ''
new = ("ARMS['K'] = ('r', {**ARMS['K'][1], 'RSX_IDX_FUSED': 'ab'})"
       "   # Kk20: exe %s, Kk19 + the fused index pass on and off by turns ([eng-ab])" % pin[:8] + eol)
lines.insert(i + 1, new)
s = '\n'.join(lines)


def sub(a, b):
    global s
    assert s.count(a) == 1, (a, s.count(a))
    s = s.replace(a, b)


sub("'Kk19', 'Yy1']", "'Kk19', 'Kk20', 'Yy1']")
sub("MAX_LAUNCHES = 66", "MAX_LAUNCHES = 67")
sub("PIN = 'ffc242c3fc79dc2e796d93d17c7fe3936ac4f2ec885125c5f4c2ca86fd713807'   # ",
    "PIN = '%s'   # RSX_IDX_FUSED (Kk20); " % pin)
p.write_bytes(s.encode('utf-8'))
print('ok')
