r"""run_vk.py: Kk134 (2026-11-06), exe d67a8e85 (340341ea + RSX_RT_SHADOW, libs/video/rsx_vk_rt.h). First ray-traced
sun shadows: casters captured from the shadow pass, receivers ray-query from tc6 (DXC at
build/vulkan-sdk/Bin/dxc.exe). Auto-driven (tools/auto_drive.py k134 6 3 8), motion blur off, F9 frames.
usage: py -3 add_arm_k134.py; launch with RUN_VK_PLAY=1 RUN_VK_RACE_S=150"""
import pathlib

root = pathlib.Path(__file__).resolve().parents[4]
ab2 = pathlib.Path(__file__).resolve().parents[1] / 'ab2'
p = ab2 / 'run_vk.py'
s = p.read_text(encoding='utf-8')
if "'Kk134'" in s:
    print('already edited'); raise SystemExit
shots = root / 'build' / 'shots' / 'k134'
shots.mkdir(parents=True, exist_ok=True)
dxc = root / 'build' / 'vulkan-sdk' / 'Bin' / 'dxc.exe'
add = (f"K_BY_TAG['k134'] = ('r', {{**ARMS['K'][1], 'RSX_HDR': '1', 'MSPR_PATCH': 'drs,vfps,mblur', 'RSX_RT_SHADOW': '1', "
       f"'RSX_RT_DXC': {str(dxc)!r}, 'RSX_SHOTS': {str(shots)!r}, 'RSX_SHOTS_MAX': '600'}})"
       "   # Kk134: exe d67a8e85, ray-traced sun shadows (window snips instead of F9)\n")
a = "K_BY_TAG['k133'] = "
assert s.count(a) == 1
i = s.index('\n', s.index(a)) + 1
s = s[:i] + add + s[i:]
a = "'Kk132', 'Kk133', 'Yy1']"
assert s.count(a) == 1
s = s.replace(a, "'Kk132', 'Kk133', 'Kk134', 'Yy1']")
a = 'MAX_LAUNCHES = 183'
assert s.count(a) == 1
s = s.replace(a, 'MAX_LAUNCHES = 184')
p.write_text(s, encoding='utf-8', newline='\n')
print('edited', p.name)
