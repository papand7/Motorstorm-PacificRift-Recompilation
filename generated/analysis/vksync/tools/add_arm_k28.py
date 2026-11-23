"""Add launch Kk28: Kk27's configuration without the recording thread (RSX_BE_THREAD off; Kk23-Kk27
were no faster with it) and with the float VMX helpers' x86 fast paths on and off by turns
(PS3_VMX_FAST=ab; [eng-ab], [vmx-fast]). vmaddfp was about 5.5% of the game thread in Kk26's
profile; the fast paths give the per-lane helpers' bits (test_vmx_float_fast.c). No profiler.

usage: py -3 add_arm_k28.py <exe sha256>"""
import pathlib
import sys

pin = sys.argv[1]
assert len(pin) == 64, pin
p = pathlib.Path(__file__).resolve().parents[1] / 'ab2' / 'run_vk.py'
s = p.read_bytes().decode('utf-8')
lines = s.split('\n')
i = [k for k, l in enumerate(lines) if l.startswith("ARMS['K'] = ('r', {**ARMS['K'][1], 'RSX_BE_THREAD': 'ab'})   # Kk27")][0]
eol = '\r' if lines[i].endswith('\r') else ''
new = ("ARMS['K'] = ('r', {**{k: v for k, v in ARMS['K'][1].items() if k != 'RSX_BE_THREAD'}, 'PS3_VMX_FAST': 'ab'})"
       "   # Kk28: exe %s, Kk27 without RSX_BE_THREAD + float VMX fast paths on and off by turns ([eng-ab])" % pin[:8] + eol)
lines.insert(i + 1, new)
s = '\n'.join(lines)


def sub(a, b):
    global s
    assert s.count(a) == 1, (a, s.count(a))
    s = s.replace(a, b)


sub("'Kk26', 'Kk27', 'Yy1']", "'Kk26', 'Kk27', 'Kk28', 'Yy1']")
sub("MAX_LAUNCHES = 74", "MAX_LAUNCHES = 75")
sub("PIN = '5a70e3f8776f2151c70688ad54d857cd9df6183acca66a9f81f2384d792deb08'   # ",
    "PIN = '%s'   # PS3_VMX_FAST (Kk28); " % pin)
p.write_bytes(s.encode('utf-8'))
print('ok')
