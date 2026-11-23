r"""run_vk.py: Kk143 (2026-11-07), exe 2f57e3d8. User (Kk141 play): almost no shadows with RSX_RT_SHADOW=1.
Auto-driven RT race with a pass dump from 62 s (ab2/passdump_k143) to see the scene passes; original timing
(MSPR_PATCH=drs, PS3_SIM_PACE=1, MSPR_CAM=0, MSPR_CAM_SHAKE=1).
usage: py -3 add_arm_k143.py; launch with RUN_VK_PLAY=1 RUN_VK_RACE_S=150 next to gate_at_race.py k143 <gate> 6 60"""
import pathlib

root = pathlib.Path(__file__).resolve().parents[4]
ab2 = pathlib.Path(__file__).resolve().parents[1] / 'ab2'
p = ab2 / 'run_vk.py'
s = p.read_text(encoding='utf-8')
if "'Kk143'" in s:
    print('already edited'); raise SystemExit
dxc = root / 'build' / 'vulkan-sdk' / 'Bin' / 'dxc.exe'
pd = ab2 / 'passdump_k143'
pd.mkdir(exist_ok=True)
add = (f"K_BY_TAG['k143'] = ('r', {{**ARMS['K'][1], 'RSX_HDR': '1', 'MSPR_PATCH': 'drs', 'PS3_SIM_PACE': '1', 'MSPR_CAM': '0', "
       f"'MSPR_CAM_SHAKE': '1', 'RSX_RT_SHADOW': '1', 'RSX_RT_DIR': '+1', 'RSX_RT_DXC': {str(dxc)!r}, "
       f"'RSX_ENGINE_PASS_DUMP': {str(pd)!r}, 'RSX_ENGINE_PASS_DUMP_AFTER': '62', 'RSX_ENGINE_PASS_DUMP_MAX': '120'}})"
       "   # Kk143: exe 2f57e3d8, RT shadows + pass dump (rays towards +z)\n")
a = "K_BY_TAG['k142'] = "
assert s.count(a) == 1
i = s.index('\n', s.index(a)) + 1
s = s[:i] + add + s[i:]
a = "'Kk141', 'Kk142', 'Yy1']"
assert s.count(a) == 1
s = s.replace(a, "'Kk141', 'Kk142', 'Kk143', 'Yy1']")
a = 'MAX_LAUNCHES = 192'
assert s.count(a) == 1
s = s.replace(a, 'MAX_LAUNCHES = 193')
p.write_text(s, encoding='utf-8', newline='\n')
print('edited', p.name)
