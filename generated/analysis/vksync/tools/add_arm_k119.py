r"""run_vk.py: Kk119/Kk120 (2026-11-06), exe e30226e1 (71deee8c + MSPR_CAM, tools/cam_patch_lifted.py).
Camera shake A/B under vfps, auto-driven (tools/auto_drive.py <tag> 6 3 8), motion blur off, with an
RSX_SHADOW_CAP (camera matrices per frame) and F9 frames: Kk119 the default (shake x0.3), Kk120 MSPR_CAM_SHAKE=1; both log the shake offset.
usage: py -3 add_arm_k119.py; launch each with RUN_VK_PLAY=1 RUN_VK_RACE_S=150"""
import pathlib

root = pathlib.Path(__file__).resolve().parents[4]
ab2 = pathlib.Path(__file__).resolve().parents[1] / 'ab2'
p = ab2 / 'run_vk.py'
s = p.read_text(encoding='utf-8')
if "'Kk119'" in s:
    print('already edited'); raise SystemExit
add = ''
for tag, extra, note in (('k119', '', 'rate fix + shake x0.3 (default)'), ('k120', "'MSPR_CAM_SHAKE': '1', ", 'rate fix + game shake')):
    shots = root / 'build' / 'shots' / tag
    shots.mkdir(parents=True, exist_ok=True)
    cap = ab2 / f'shadowcap_{tag}.bin'
    add += (f"K_BY_TAG['{tag}'] = ('r', {{**ARMS['K'][1], 'RSX_HDR': '1', {extra}'MSPR_PATCH': 'drs,vfps,mblur', "
            f"'RSX_SHADOW_CAP': {str(cap)!r}, 'RSX_SHADOW_CAP_AFTER': '55', 'RSX_SHADOW_CAP_FRAMES': '600', "
            f"'RSX_SHOTS': {str(shots)!r}, 'RSX_SHOTS_MAX': '600'}})"
            f"   # K{tag}: exe e30226e1, {note} (auto-driven)\n")
a = "K_BY_TAG['k118'] = "
assert s.count(a) == 1
i = s.index('\n', s.index(a)) + 1
s = s[:i] + add + s[i:]
a = "'Kk117', 'Kk118', 'Yy1']"
assert s.count(a) == 1
s = s.replace(a, "'Kk117', 'Kk118', 'Kk119', 'Kk120', 'Yy1']")
a = 'MAX_LAUNCHES = 168'
assert s.count(a) == 1
s = s.replace(a, 'MAX_LAUNCHES = 170')
p.write_text(s, encoding='utf-8', newline='\n')
print('edited', p.name)
