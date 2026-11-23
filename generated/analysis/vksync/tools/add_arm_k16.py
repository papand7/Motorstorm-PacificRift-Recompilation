"""Add launch Kk16: Kk14 (GPU vertex decode on) on exe 0506ee54 with the frame clock's FIFO kick
on and off by turns (PS3_FRAME_CLOCK_KICK=ab; [eng-ab]): Kk15's critical-path trace showed the
game waiting on the RSX reference at 0x72E5C0 every frame while the drain thread slept in its
4 ms tick. No trace, no inline stores."""
import pathlib

p = pathlib.Path(__file__).resolve().parents[1] / 'ab2' / 'run_vk.py'
s = p.read_bytes().decode('utf-8')
lines = s.split('\n')
i = [k for k, l in enumerate(lines) if l.startswith("ARMS['K'] = ('r', {**ARMS['K'][1], 'PS3_VM_STORE_INLINE': '1'")][0]
eol = '\r' if lines[i].endswith('\r') else ''
new = ("ARMS['K'] = ('r', {**{k: v for k, v in ARMS['K'][1].items() if k not in ('PS3_VM_STORE_INLINE', "
       "'MSPR_STORE_INLINE_AB', 'PS3_CRITICAL_PATH_TRACE')}, 'PS3_FRAME_CLOCK_KICK': 'ab'})"
       "   # Kk16: exe 0506ee54, Kk14 + FIFO kick on and off by turns ([eng-ab])" + eol)
lines.insert(i + 1, new)
s = '\n'.join(lines)


def sub(a, b):
    global s
    assert s.count(a) == 1, (a, s.count(a))
    s = s.replace(a, b)


sub("'Kk15', 'Yy1']", "'Kk15', 'Kk16', 'Yy1']")
sub("MAX_LAUNCHES = 62", "MAX_LAUNCHES = 63")
p.write_bytes(s.encode('utf-8'))
print('ok')
