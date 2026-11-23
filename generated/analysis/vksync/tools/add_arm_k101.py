r"""run_vk.py: Kk101/Kk102 (2026-11-06), exe feba7954, game distances (no MSPR_DIST). Why RSX_SHADOW_STABLE=1
made shadows jump while driving (user, Kk93): auto-driven (tools/auto_drive.py), F9 frames plus an
RSX_SHADOW_CAP of 600 frames from 55 s (race entry ~47 s, throttle ~53 s). Kk101 = stable on, Kk102 = off.
usage: py -3 add_arm_k101.py; launch each with RUN_VK_PLAY=1 RUN_VK_RACE_S=150 next to auto_drive.py <tag>"""
import pathlib

root = pathlib.Path(__file__).resolve().parents[4]
ab2 = pathlib.Path(__file__).resolve().parents[1] / 'ab2'
p = ab2 / 'run_vk.py'
s = p.read_text(encoding='utf-8')
if "'Kk101'" in s:
    print('already edited'); raise SystemExit
add = ''
for tag, extra, note in (('k101', "'RSX_SHADOW_STABLE': '1', ", 'stable shadows'), ('k102', '', 'game shadows')):
    shots = root / 'build' / 'shots' / tag
    shots.mkdir(parents=True, exist_ok=True)
    cap = ab2 / f'shadowcap_{tag}.bin'
    add += (f"K_BY_TAG['{tag}'] = ('r', {{**ARMS['K'][1], 'RSX_HDR': '1', {extra}'RSX_SHADOW_CAP': {str(cap)!r}, "
            f"'RSX_SHADOW_CAP_AFTER': '55', 'RSX_SHADOW_CAP_FRAMES': '600', "
            f"'RSX_SHOTS': {str(shots)!r}, 'RSX_SHOTS_MAX': '600'}})"
            f"   # K{tag}: exe feba7954, {note} in motion (tools/auto_drive.py)\n")
a = "K_BY_TAG['k100'] = "
assert s.count(a) == 1
i = s.index('\n', s.index(a)) + 1
s = s[:i] + add + s[i:]
a = "'Kk99', 'Kk100', 'Yy1']"
assert s.count(a) == 1
s = s.replace(a, "'Kk99', 'Kk100', 'Kk101', 'Kk102', 'Yy1']")
a = 'MAX_LAUNCHES = 150'
assert s.count(a) == 1
s = s.replace(a, 'MAX_LAUNCHES = 152')
p.write_text(s, encoding='utf-8', newline='\n')
print('edited', p.name)
