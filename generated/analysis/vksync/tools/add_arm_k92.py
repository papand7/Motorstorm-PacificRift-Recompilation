r"""run_vk.py: Kk92 (2026-11-06), exe e0e31b49 (ff7cac19 + RSX_SHOTS: F9 saves every presented frame as BMP).
Kk91's configuration (stable shadows + HDR) + RSX_SHOTS=build/shots/k92; a play session where the user
captures the shadows going wrong while driving. Launch with RUN_VK_RACE_S for a long race.
usage: py -3 add_arm_k92.py"""
import pathlib

root = pathlib.Path(__file__).resolve().parents[4]
p = pathlib.Path(__file__).resolve().parents[1] / 'ab2' / 'run_vk.py'
s = p.read_text(encoding='utf-8')
if "'Kk92'" in s:
    print('already edited'); raise SystemExit
shots = (root / 'build' / 'shots' / 'k92')
shots.mkdir(parents=True, exist_ok=True)
a = "K_BY_TAG['k91'] = "
assert s.count(a) == 1
i = s.index('\n', s.index(a)) + 1
s = s[:i] + ("K_BY_TAG['k92'] = ('r', {**ARMS['K'][1], 'RSX_SHADOW_STABLE': '1', 'RSX_HDR': '1', "
             f"'RSX_SHOTS': {str(shots)!r}, 'RSX_SHOTS_MAX': '1800'}})"
             "   # Kk92: exe e0e31b49, Kk91 + F9 frame capture\n") + s[i:]
a = "'Kk90', 'Kk91', 'Yy1']"
assert s.count(a) == 1
s = s.replace(a, "'Kk90', 'Kk91', 'Kk92', 'Yy1']")
a = 'MAX_LAUNCHES = 141'
assert s.count(a) == 1
s = s.replace(a, 'MAX_LAUNCHES = 142')
p.write_text(s, encoding='utf-8', newline='\n')
print('edited', p.name, shots)
