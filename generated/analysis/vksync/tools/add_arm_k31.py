"""Add launch Kk31: Kk30's configuration on the exe with PS3_VMX_FAST on by default (the
PS3_VMX_FAST=ab key removed, so the fast paths run on both sides) and inline guest stores on
and off by turns (PS3_VM_STORE_INLINE=1 + MSPR_STORE_INLINE_AB=1; [eng-ab], [vm-gates],
[store-ab]). Kk15 measured this under the critical-path trace on a loaded PC (48.28 / 48.11 ms);
out-of-line vm_write32/64 were 9.3% of the game thread in Kk26's profile. No profiler, no trace.

usage: py -3 add_arm_k31.py <exe sha256>"""
import pathlib
import sys

pin = sys.argv[1]
assert len(pin) == 64, pin
p = pathlib.Path(__file__).resolve().parents[1] / 'ab2' / 'run_vk.py'
s = p.read_bytes().decode('utf-8')
lines = s.split('\n')
i = [k for k, l in enumerate(lines) if l.startswith("ARMS['K'] = ('r', dict(ARMS['K'][1]))   # Kk30")][0]
eol = '\r' if lines[i].endswith('\r') else ''
new = ("ARMS['K'] = ('r', {**{k: v for k, v in ARMS['K'][1].items() if k != 'PS3_VMX_FAST'}, "
       "'PS3_VM_STORE_INLINE': '1', 'MSPR_STORE_INLINE_AB': '1'})"
       "   # Kk31: exe %s, VMX fast paths on by default + inline guest stores on and off by turns ([eng-ab])"
       % pin[:8] + eol)
lines.insert(i + 1, new)
s = '\n'.join(lines)


def sub(a, b):
    global s
    assert s.count(a) == 1, (a, s.count(a))
    s = s.replace(a, b)


sub("'Kk29', 'Kk30', 'Yy1']", "'Kk29', 'Kk30', 'Kk31', 'Yy1']")
sub("MAX_LAUNCHES = 77", "MAX_LAUNCHES = 78")
sub("PIN = '84ee1a831ce183172dda7a0d58ec062ec08265b48bfc995a46d65316f982b88b'   # ",
    "PIN = '%s'   # PS3_VMX_FAST default on, inline-store A/B (Kk31); " % pin)
p.write_bytes(s.encode('utf-8'))
print('ok')
