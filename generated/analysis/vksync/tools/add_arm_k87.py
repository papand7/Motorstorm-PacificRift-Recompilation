r"""run_vk.py: Kk87 (2026-11-06), exe b15ff48b (ec5ce88e + a log naming the fragment programs that read the
shadow atlas without the cascade lookup). Kk71's configuration + RSX_SHADOW_STABLE=1, no capture (full speed,
for watching the shadows). usage: py -3 add_arm_k87.py"""
import pathlib

p = pathlib.Path(__file__).resolve().parents[1] / 'ab2' / 'run_vk.py'
s = p.read_text(encoding='utf-8')
if "'Kk87'" in s:
    print('already edited'); raise SystemExit
a = "K_BY_TAG['k86'] = "
assert s.count(a) == 1
i = s.index('\n', s.index(a)) + 1
s = s[:i] + ("K_BY_TAG['k87'] = ('r', {**ARMS['K'][1], 'RSX_SHADOW_STABLE': '1'})"
             "   # Kk87: exe b15ff48b, stable shadows, atlas readers without lookup named\n") + s[i:]
a = "'Kk86', 'Yy1']"
assert s.count(a) == 1
s = s.replace(a, "'Kk86', 'Kk87', 'Yy1']")
a = 'MAX_LAUNCHES = 136'
assert s.count(a) == 1
s = s.replace(a, 'MAX_LAUNCHES = 137')
p.write_text(s, encoding='utf-8', newline='\n')
print('edited', p.name)
