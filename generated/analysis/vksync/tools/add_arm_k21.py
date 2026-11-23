"""Add launch Kk21: Kk19's configuration (Kk20 without RSX_IDX_FUSED) on exe d9636306, where the
route tracer's hooks are lean (an unselected function entry returns at once; [PT] ev=config ...
lean=1), under sample_race.py with SAMPLE_TOP=1 (sample_k21.json) like Kk19: how much of the
game thread the harness tracing took (Kk19: ppu_trace_enter/ret, thread_for and their atomics
about 12% of its samples), and the frame time without it.

usage: py -3 add_arm_k21.py <exe sha256>"""
import pathlib
import sys

pin = sys.argv[1]
assert len(pin) == 64, pin
p = pathlib.Path(__file__).resolve().parents[1] / 'ab2' / 'run_vk.py'
s = p.read_bytes().decode('utf-8')
lines = s.split('\n')
i = [k for k, l in enumerate(lines) if l.startswith("ARMS['K'] = ('r', {**ARMS['K'][1], 'RSX_IDX_FUSED': 'ab'})")][0]
eol = '\r' if lines[i].endswith('\r') else ''
new = ("ARMS['K'] = ('r', {k: v for k, v in ARMS['K'][1].items() if k != 'RSX_IDX_FUSED'})"
       "   # Kk21: exe %s (lean route-trace hooks), Kk19's configuration under sample_race.py SAMPLE_TOP=1 (sample_k21.json)" % pin[:8] + eol)
lines.insert(i + 1, new)
s = '\n'.join(lines)


def sub(a, b):
    global s
    assert s.count(a) == 1, (a, s.count(a))
    s = s.replace(a, b)


sub("'Kk20', 'Yy1']", "'Kk20', 'Kk21', 'Yy1']")
sub("MAX_LAUNCHES = 67", "MAX_LAUNCHES = 68")
sub("PIN = 'bdeeba1fe71dfa94cec43c747ad08a2d92edbeedfcde0e6c87dfd2cbc5c53b69'   # ",
    "PIN = '%s'   # lean route-trace hooks (Kk21); " % pin)
p.write_bytes(s.encode('utf-8'))
print('ok')
