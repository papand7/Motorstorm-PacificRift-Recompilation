r"""run_vk.py: Kk90 (2026-11-06), exe ff7cac19 (6af3aca9 + the RSX_HDR present: HDR10 swapchain, SDR frame
stretched to the monitor's peak). Kk89's configuration (stable shadows) + RSX_HDR=1.
usage: py -3 add_arm_k90.py"""
import pathlib

p = pathlib.Path(__file__).resolve().parents[1] / 'ab2' / 'run_vk.py'
s = p.read_text(encoding='utf-8')
if "'Kk90'" in s:
    print('already edited'); raise SystemExit
a = "K_BY_TAG['k89'] = "
assert s.count(a) == 1
i = s.index('\n', s.index(a)) + 1
s = s[:i] + ("K_BY_TAG['k90'] = ('r', {**ARMS['K'][1], 'RSX_SHADOW_STABLE': '1', 'RSX_HDR': '1'})"
             "   # Kk90: exe ff7cac19, stable shadows + HDR10 present\n") + s[i:]
a = "'Kk86', 'Kk87', 'Kk88', 'Kk89', 'Yy1']"
assert s.count(a) == 1
s = s.replace(a, "'Kk86', 'Kk87', 'Kk88', 'Kk89', 'Kk90', 'Yy1']")
a = 'MAX_LAUNCHES = 139'
assert s.count(a) == 1
s = s.replace(a, 'MAX_LAUNCHES = 140')
p.write_text(s, encoding='utf-8', newline='\n')
print('edited', p.name)
