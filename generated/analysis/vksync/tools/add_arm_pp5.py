"""run_vk.py: Pp5, the Pp4 PC Settings page test again (Pp4 found the Options page
not swapped: exe 25fe9310 checks the loader's string length instead of a terminator
and logs page loads). Same arm P, same menu walk. LF file. usage: py -3 add_arm_pp5.py"""
import pathlib

p = pathlib.Path(__file__).resolve().parents[1] / 'ab2' / 'run_vk.py'
s = p.read_text(encoding='utf-8')
if "'Pp5'" in s:
    print('already edited'); raise SystemExit
a = "'Kk70', 'Pp4', 'Yy1']"
assert s.count(a) == 1
s = s.replace(a, "'Kk70', 'Pp4', 'Pp5', 'Yy1']")
a = 'MAX_LAUNCHES = 118'
assert s.count(a) == 1
s = s.replace(a, 'MAX_LAUNCHES = 119')
p.write_text(s, encoding='utf-8', newline='\n')
print('edited', p.name)
