r"""run_vk.py: Kk128 (2026-11-06), exe beec6355 (340341ea + RSX_RT_SHADOW, libs/video/rsx_vk_rt.h). First ray-traced
sun shadows: casters captured from the shadow pass, receivers ray-query from tc6 (DXC at
build/vulkan-sdk/Bin/dxc.exe). Auto-driven (tools/auto_drive.py k128 6 3 8), motion blur off, F9 frames.
usage: py -3 add_arm_k128.py; launch with RUN_VK_PLAY=1 RUN_VK_RACE_S=150"""
import pathlib

root = pathlib.Path(__file__).resolve().parents[4]
ab2 = pathlib.Path(__file__).resolve().parents[1] / 'ab2'
p = ab2 / 'run_vk.py'
s = p.read_text(encoding='utf-8')
if "'Kk128'" in s:
    print('already edited'); raise SystemExit
shots = root / 'build' / 'shots' / 'k128'
shots.mkdir(parents=True, exist_ok=True)
dxc = root / 'build' / 'vulkan-sdk' / 'Bin' / 'dxc.exe'
add = (f"K_BY_TAG['k128'] = ('r', {{**ARMS['K'][1], 'RSX_HDR': '1', 'MSPR_PATCH': 'drs,vfps,mblur', 'RSX_RT_SHADOW': '1', "
       f"'RSX_RT_DXC': {str(dxc)!r}, 'RSX_SHOTS': {str(shots)!r}, 'RSX_SHOTS_MAX': '600'}})"
       "   # Kk128: exe beec6355, ray-traced sun shadows (ray start fixed)\n")
a = "K_BY_TAG['k127'] = "
assert s.count(a) == 1
i = s.index('\n', s.index(a)) + 1
s = s[:i] + add + s[i:]
a = "'Kk126', 'Kk127', 'Yy1']"
assert s.count(a) == 1
s = s.replace(a, "'Kk126', 'Kk127', 'Kk128', 'Yy1']")
a = 'MAX_LAUNCHES = 177'
assert s.count(a) == 1
s = s.replace(a, 'MAX_LAUNCHES = 178')
p.write_text(s, encoding='utf-8', newline='\n')
print('edited', p.name)
