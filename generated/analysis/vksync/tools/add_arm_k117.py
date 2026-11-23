r"""run_vk.py: Kk117/Kk118 (2026-11-06), exe 3fcc881b (71deee8c + MSPR_CAM, tools/cam_patch_lifted.py).
Camera shake A/B under vfps, auto-driven (tools/auto_drive.py <tag> 6 3 8), motion blur off, with an
RSX_SHADOW_CAP (camera matrices per frame) and F9 frames: Kk117 the rate fix with the Shake activity logged, Kk118 + MSPR_CAM_SHAKE=0.
usage: py -3 add_arm_k117.py; launch each with RUN_VK_PLAY=1 RUN_VK_RACE_S=150"""
import pathlib

root = pathlib.Path(__file__).resolve().parents[4]
ab2 = pathlib.Path(__file__).resolve().parents[1] / 'ab2'
p = ab2 / 'run_vk.py'
s = p.read_text(encoding='utf-8')
if "'Kk117'" in s:
    print('already edited'); raise SystemExit
add = ''
for tag, extra, note in (('k117', '', 'camera rate fix, shake logged'), ('k118', "'MSPR_CAM_SHAKE': '0', ", 'camera rate fix + Shake skipped')):
    shots = root / 'build' / 'shots' / tag
    shots.mkdir(parents=True, exist_ok=True)
    cap = ab2 / f'shadowcap_{tag}.bin'
    add += (f"K_BY_TAG['{tag}'] = ('r', {{**ARMS['K'][1], 'RSX_HDR': '1', {extra}'MSPR_PATCH': 'drs,vfps,mblur', "
            f"'RSX_SHADOW_CAP': {str(cap)!r}, 'RSX_SHADOW_CAP_AFTER': '55', 'RSX_SHADOW_CAP_FRAMES': '600', "
            f"'RSX_SHOTS': {str(shots)!r}, 'RSX_SHOTS_MAX': '600'}})"
            f"   # K{tag}: exe 3fcc881b, {note} (auto-driven)\n")
a = "K_BY_TAG['k116'] = "
assert s.count(a) == 1
i = s.index('\n', s.index(a)) + 1
s = s[:i] + add + s[i:]
a = "'Kk115', 'Kk116', 'Yy1']"
assert s.count(a) == 1
s = s.replace(a, "'Kk115', 'Kk116', 'Kk117', 'Kk118', 'Yy1']")
a = 'MAX_LAUNCHES = 166'
assert s.count(a) == 1
s = s.replace(a, 'MAX_LAUNCHES = 168')
p.write_text(s, encoding='utf-8', newline='\n')
print('edited', p.name)
