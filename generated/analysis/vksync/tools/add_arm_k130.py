r"""run_vk.py: Kk130 (2026-11-06), exe beec6355 (340341ea + RSX_RT_SHADOW, libs/video/rsx_vk_rt.h). First ray-traced
sun shadows: casters captured from the shadow pass, receivers ray-query from tc6 (DXC at
build/vulkan-sdk/Bin/dxc.exe). Auto-driven (tools/auto_drive.py k130 6 3 8), motion blur off, F9 frames.
usage: py -3 add_arm_k130.py; launch with RUN_VK_PLAY=1 RUN_VK_RACE_S=150"""
import pathlib

root = pathlib.Path(__file__).resolve().parents[4]
ab2 = pathlib.Path(__file__).resolve().parents[1] / 'ab2'
p = ab2 / 'run_vk.py'
s = p.read_text(encoding='utf-8')
if "'Kk130'" in s:
    print('already edited'); raise SystemExit
shots = root / 'build' / 'shots' / 'k130'
shots.mkdir(parents=True, exist_ok=True)
dxc = root / 'build' / 'vulkan-sdk' / 'Bin' / 'dxc.exe'
add = (f"K_BY_TAG['k130'] = ('r', {{**ARMS['K'][1], 'RSX_HDR': '1', 'MSPR_PATCH': 'drs,vfps,mblur', 'RSX_RT_SHADOW': '0', "
       f"'RSX_RT_DXC': {str(dxc)!r}, 'RSX_SHOTS': {str(shots)!r}, 'RSX_SHOTS_MAX': '600'}})"
       "   # Kk130: exe beec6355, ray-traced sun shadows (CONTROL: RT off, same exe)\n")
a = "K_BY_TAG['k129'] = "
assert s.count(a) == 1
i = s.index('\n', s.index(a)) + 1
s = s[:i] + add + s[i:]
a = "'Kk128', 'Kk129', 'Yy1']"
assert s.count(a) == 1
s = s.replace(a, "'Kk128', 'Kk129', 'Kk130', 'Yy1']")
a = 'MAX_LAUNCHES = 179'
assert s.count(a) == 1
s = s.replace(a, 'MAX_LAUNCHES = 180')
p.write_text(s, encoding='utf-8', newline='\n')
print('edited', p.name)
