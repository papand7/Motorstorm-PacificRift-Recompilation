r"""run_vk.py: Kk93 (2026-11-06), exe e0e31b49. Kk92's configuration (stable shadows, HDR, F9 frame capture
to build/shots/k93) as a play session: launch with RUN_VK_PLAY=1 RUN_VK_RACE_S=900.
usage: py -3 add_arm_k93.py"""
import pathlib

root = pathlib.Path(__file__).resolve().parents[4]
p = pathlib.Path(__file__).resolve().parents[1] / 'ab2' / 'run_vk.py'
s = p.read_text(encoding='utf-8')
if "'Kk93'" in s:
    print('already edited'); raise SystemExit
shots = (root / 'build' / 'shots' / 'k93')
shots.mkdir(parents=True, exist_ok=True)
a = "K_BY_TAG['k92'] = "
assert s.count(a) == 1
i = s.index('\n', s.index(a)) + 1
s = s[:i] + ("K_BY_TAG['k93'] = ('r', {**ARMS['K'][1], 'RSX_SHADOW_STABLE': '1', 'RSX_HDR': '1', "
             f"'RSX_SHOTS': {str(shots)!r}, 'RSX_SHOTS_MAX': '1800'}})"
             "   # Kk93: exe e0e31b49, Kk92 as a play session (RUN_VK_PLAY=1)\n") + s[i:]
a = "'Kk91', 'Kk92', 'Yy1']"
assert s.count(a) == 1
s = s.replace(a, "'Kk91', 'Kk92', 'Kk93', 'Yy1']")
a = 'MAX_LAUNCHES = 142'
assert s.count(a) == 1
s = s.replace(a, 'MAX_LAUNCHES = 143')
p.write_text(s, encoding='utf-8', newline='\n')
print('edited', p.name, shots)
