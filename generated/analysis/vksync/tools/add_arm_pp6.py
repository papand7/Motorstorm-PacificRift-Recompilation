"""run_vk.py: Pp6, the PC Settings page test again. Pp5 (exe 25fe9310) showed the
Options path swapped but the original page: the trampoline 0x00752C98 tail-branches
to the loader through g_trampoline_fn, which the caller drained after the hook had
restored the path. Exe with pcmenu_drain() in both hooks. Same arm P, same menu walk.
LF file. usage: py -3 add_arm_pp6.py"""
import pathlib

p = pathlib.Path(__file__).resolve().parents[1] / 'ab2' / 'run_vk.py'
s = p.read_text(encoding='utf-8')
if "'Pp6'" in s:
    print('already edited'); raise SystemExit
a = "'Pp4', 'Pp5', 'Yy1']"
assert s.count(a) == 1
s = s.replace(a, "'Pp4', 'Pp5', 'Pp6', 'Yy1']")
a = 'MAX_LAUNCHES = 119'
assert s.count(a) == 1
s = s.replace(a, 'MAX_LAUNCHES = 120')
p.write_text(s, encoding='utf-8', newline='\n')
print('edited', p.name)
