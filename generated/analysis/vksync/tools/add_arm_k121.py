r"""run_vk.py: Kk121/Kk122 (2026-11-06), exe 340341ea (71deee8c + MSPR_CAM, tools/cam_patch_lifted.py).
Camera shake A/B under vfps, auto-driven (tools/auto_drive.py <tag> 6 3 8), motion blur off, with an
RSX_SHADOW_CAP (camera matrices per frame) and F9 frames: Kk121 the default (shake x0.3), Kk122 MSPR_CAM_SHAKE=1; both log the shake offset.
usage: py -3 add_arm_k121.py; launch each with RUN_VK_PLAY=1 RUN_VK_RACE_S=150"""
import pathlib

root = pathlib.Path(__file__).resolve().parents[4]
ab2 = pathlib.Path(__file__).resolve().parents[1] / 'ab2'
p = ab2 / 'run_vk.py'
s = p.read_text(encoding='utf-8')
if "'Kk121'" in s:
    print('already edited'); raise SystemExit
add = ''
for tag, extra, note in (('k121', '', 'rate fix + shake x0.3 (default)'), ('k122', "'MSPR_CAM_SHAKE': '1', ", 'rate fix + game shake')):
    shots = root / 'build' / 'shots' / tag
    shots.mkdir(parents=True, exist_ok=True)
    cap = ab2 / f'shadowcap_{tag}.bin'
    add += (f"K_BY_TAG['{tag}'] = ('r', {{**ARMS['K'][1], 'RSX_HDR': '1', {extra}'MSPR_PATCH': 'drs,vfps,mblur', "
            f"'RSX_SHADOW_CAP': {str(cap)!r}, 'RSX_SHADOW_CAP_AFTER': '55', 'RSX_SHADOW_CAP_FRAMES': '600', "
            f"'RSX_SHOTS': {str(shots)!r}, 'RSX_SHOTS_MAX': '600'}})"
            f"   # K{tag}: exe 340341ea, {note} (auto-driven)\n")
a = "K_BY_TAG['k120'] = "
assert s.count(a) == 1
i = s.index('\n', s.index(a)) + 1
s = s[:i] + add + s[i:]
a = "'Kk119', 'Kk120', 'Yy1']"
assert s.count(a) == 1
s = s.replace(a, "'Kk119', 'Kk120', 'Kk121', 'Kk122', 'Yy1']")
a = 'MAX_LAUNCHES = 170'
assert s.count(a) == 1
s = s.replace(a, 'MAX_LAUNCHES = 172')
p.write_text(s, encoding='utf-8', newline='\n')
print('edited', p.name)
