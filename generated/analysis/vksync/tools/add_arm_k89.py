r"""run_vk.py: Kk89 (2026-11-06), exe 6af3aca9 (ec5ce88e + a log naming the fragment programs that read the
shadow atlas without the cascade lookup). Kk71's configuration + RSX_SHADOW_STABLE=1, no capture (full speed,
for watching the shadows). usage: py -3 add_arm_k89.py"""
import pathlib

p = pathlib.Path(__file__).resolve().parents[1] / 'ab2' / 'run_vk.py'
s = p.read_text(encoding='utf-8')
if "'Kk89'" in s:
    print('already edited'); raise SystemExit
a = "K_BY_TAG['k88'] = "
assert s.count(a) == 1
i = s.index('\n', s.index(a)) + 1
s = s[:i] + ("K_BY_TAG['k89'] = ('r', {**ARMS['K'][1], 'RSX_SHADOW_STABLE': '1'})"
             "   # Kk89: exe 6af3aca9, stable shadows, + vertex-side readers (c4-c7, c45-c51) rewritten\n") + s[i:]
a = "'Kk86', 'Kk87', 'Kk88', 'Yy1']"
assert s.count(a) == 1
s = s.replace(a, "'Kk86', 'Kk87', 'Kk88', 'Kk89', 'Yy1']")
a = 'MAX_LAUNCHES = 138'
assert s.count(a) == 1
s = s.replace(a, 'MAX_LAUNCHES = 139')
p.write_text(s, encoding='utf-8', newline='\n')
print('edited', p.name)
