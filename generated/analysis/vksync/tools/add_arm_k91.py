r"""run_vk.py: Kk91 (2026-11-06), exe ff7cac19. Kk90's configuration (stable shadows + RSX_HDR=1), a play
session for the user (shadows in motion, HDR look); launch with RUN_VK_RACE_S for a long race.
usage: py -3 add_arm_k91.py"""
import pathlib

p = pathlib.Path(__file__).resolve().parents[1] / 'ab2' / 'run_vk.py'
s = p.read_text(encoding='utf-8')
if "'Kk91'" in s:
    print('already edited'); raise SystemExit
a = "K_BY_TAG['k90'] = "
assert s.count(a) == 1
i = s.index('\n', s.index(a)) + 1
s = s[:i] + ("K_BY_TAG['k91'] = ('r', {**ARMS['K'][1], 'RSX_SHADOW_STABLE': '1', 'RSX_HDR': '1'})"
             "   # Kk91: exe ff7cac19, Kk90 again as a play session\n") + s[i:]
a = "'Kk89', 'Kk90', 'Yy1']"
assert s.count(a) == 1
s = s.replace(a, "'Kk89', 'Kk90', 'Kk91', 'Yy1']")
a = 'MAX_LAUNCHES = 140'
assert s.count(a) == 1
s = s.replace(a, 'MAX_LAUNCHES = 141')
p.write_text(s, encoding='utf-8', newline='\n')
print('edited', p.name)
