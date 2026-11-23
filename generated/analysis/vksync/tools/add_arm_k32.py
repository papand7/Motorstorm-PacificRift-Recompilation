"""Add launch Kk32: Kk31's configuration without the inline-store A/B (no gain in Kk15 or Kk31) and
with a critical-path trace of 20 race seconds (host s 60..80; race entry is about 36 s), to see
what the frame thread waits on with the current exe (tools/cpath_report.py). No profiler.

usage: py -3 add_arm_k32.py"""
import pathlib

p = pathlib.Path(__file__).resolve().parents[1] / 'ab2' / 'run_vk.py'
s = p.read_bytes().decode('utf-8')
lines = s.split('\n')
i = [k for k, l in enumerate(lines) if l.startswith("ARMS['K'] = ('r', {**{k: v for k, v in ARMS['K'][1].items() if k != 'PS3_VMX_FAST'}, 'PS3_VM_STORE_INLINE'")][0]
eol = '\r' if lines[i].endswith('\r') else ''
new = ("ARMS['K'] = ('r', {**{k: v for k, v in ARMS['K'][1].items() if k not in ('PS3_VM_STORE_INLINE', 'MSPR_STORE_INLINE_AB')}, "
       "'PS3_CRITICAL_PATH_TRACE': '60:20:{rt}/cpath.txt'})"
       "   # Kk32: exe f71034a0, Kk31 without the store A/B + critical-path trace of 20 race seconds" + eol)
lines.insert(i + 1, new)
s = '\n'.join(lines)


def sub(a, b):
    global s
    assert s.count(a) == 1, (a, s.count(a))
    s = s.replace(a, b)


sub("'Kk30', 'Kk31', 'Yy1']", "'Kk30', 'Kk31', 'Kk32', 'Yy1']")
sub("MAX_LAUNCHES = 78", "MAX_LAUNCHES = 79")
p.write_bytes(s.encode('utf-8'))
print('ok')
