"""Add launch Kk15: Kk14 (GPU vertex decode on) on the exe built with MSPR_PPU_INLINE_STORES=ON
(lift header with the T152 page gates), with the inline guest stores on and off by turns
(PS3_VM_STORE_INLINE=1 + MSPR_STORE_INLINE_AB=1; [eng-ab], [vm-gates], [store-ab]).

usage: py -3 add_arm_k15.py <exe sha256>"""
import pathlib
import sys

pin = sys.argv[1]
assert len(pin) == 64, pin
p = pathlib.Path(__file__).resolve().parents[1] / 'ab2' / 'run_vk.py'
s = p.read_bytes().decode('utf-8')
lines = s.split('\n')
i = [k for k, l in enumerate(lines) if l.startswith("ARMS['K'] = ('r', {**ARMS['K'][1], 'RSX_VTX_GPU': '1'})")][0]
eol = '\r' if lines[i].endswith('\r') else ''
new = ("ARMS['K'] = ('r', {**ARMS['K'][1], 'PS3_VM_STORE_INLINE': '1', 'MSPR_STORE_INLINE_AB': '1', "
       "'PS3_CRITICAL_PATH_TRACE': '75:15:{rt}/cpath.txt'})"
       "   # Kk15: exe %s, Kk14 + inline guest stores on and off by turns ([eng-ab], [vm-gates], [store-ab]); critical-path trace cpath.txt" % pin[:8] + eol)
lines.insert(i + 1, new)
s = '\n'.join(lines)


def sub(a, b):
    global s
    assert s.count(a) == 1, (a, s.count(a))
    s = s.replace(a, b)


sub("'Kk14', 'Yy1']", "'Kk14', 'Kk15', 'Yy1']")
sub("MAX_LAUNCHES = 61", "MAX_LAUNCHES = 62")
sub("PIN = 'f240ff32b8795d0e5d526d51c4fd0a3eca31898dcedcc3aded7b40ec2651ffbc'   # ",
    "PIN = '%s'   # MSPR_PPU_INLINE_STORES (Kk15); " % pin)
p.write_bytes(s.encode('utf-8'))
print('ok')
