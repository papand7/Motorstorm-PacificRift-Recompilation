"""Add launches Kk51-Kk54: the hot-code link order A/B. Kk50's configuration (RSX_RES_SCALE=1.5, no
dynamic resolution) + PS3_MAIN_CYCLES=1 ([main-cyc]: guest main thread CPU cycles per flip).
Kk51/Kk53 run the base exe 8c01ef18, Kk52/Kk54 the same objects relinked with order_k50.txt
(tools/relink_order.cmd). The runner pins one exe at a time: tools/set_pin.py switches it.

usage: py -3 add_arm_k51.py"""
import pathlib

p = pathlib.Path(__file__).resolve().parents[1] / 'ab2' / 'run_vk.py'
s = p.read_bytes().decode('utf-8')
assert '\r\n' not in s
lines = s.split('\n')
i = [k for k, l in enumerate(lines) if l.startswith("ARMS['K']") and '   # Kk50: ' in l][0]
lines.insert(i + 1, "ARMS['K'] = ('r', {**ARMS['K'][1], 'PS3_MAIN_CYCLES': '1'})"
                    "   # Kk51-Kk54: Kk50 + [main-cyc]; base exe 8c01ef18 (Kk51, Kk53) vs hot-code order (Kk52, Kk54)")
s = '\n'.join(lines)


def sub(a, b):
    global s
    assert s.count(a) == 1, (a, s.count(a))
    s = s.replace(a, b)


sub("'Kk49', 'Kk50', 'Yy1']", "'Kk49', 'Kk50', 'Kk51', 'Kk52', 'Kk53', 'Kk54', 'Yy1']")
sub("MAX_LAUNCHES = 97", "MAX_LAUNCHES = 101")
p.write_bytes(s.encode('utf-8'))
print('ok')
