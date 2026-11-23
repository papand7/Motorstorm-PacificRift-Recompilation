"""Frame-step probes for the 60 fps patch issues (slow water, camera shake), no rebuild:
- K arms may name their own PS3_TRACE_FILE (default stays nav_sites.cfg);
- Kk69 (eager readback, 30 fps) also loads probe_fps.cfg: nav sites + water/camera step values;
- Kk70: Kk69 with MSPR_PATCH=drs,vfps (variable frame rate), same probes.
LF file. usage: py -3 add_arm_k70.py"""
import pathlib

p = pathlib.Path(__file__).resolve().parents[1] / 'ab2' / 'run_vk.py'
s = p.read_text(encoding='utf-8')
a = "        envs['PS3_TRACE_FILE'] = str(CFG.parent / 'nav_sites.cfg')\n"
b = ("        envs['PS3_TRACE_FILE'] = ARMS[ARM][1].get('PS3_TRACE_FILE') or str(CFG.parent / 'nav_sites.cfg')"
     "   # Kk69/Kk70: an arm may name its own (probe_fps.cfg)\n")
assert s.count(a) == 1
s = s.replace(a, b)
k69 = "'RSX_RT_READBACK_EAGER': '1'})   # Kk69:"
assert s.count(k69) == 1
s = s.replace(k69, "'RSX_RT_READBACK_EAGER': '1', 'PS3_TRACE_FILE': str(HERE / 'probe_fps.cfg')})   # Kk69:")
i = s.index('\n', s.index(k69.split('}')[0].replace("'1'", "'1', 'PS3_TRACE_FILE'"))) + 1
s = s[:i] + ("ARMS['K'] = ('r', {**ARMS['K'][1], 'MSPR_PATCH': 'drs,vfps'})   # Kk70: exe 2759935a, Kk69 with the "
             "variable frame rate patch: probe_fps.cfg logs the Havok step (buoyancy actions) and the camera step "
             "([r5+0x10] at VehicleView/XYZSplineSmooth) against Kk69's 30 fps values (slow water, camera shake)\n") + s[i:]
a = "'Kk69', 'Yy1']"
assert s.count(a) == 1
s = s.replace(a, "'Kk69', 'Kk70', 'Yy1']")
a = 'MAX_LAUNCHES = 116'
assert s.count(a) == 1
s = s.replace(a, 'MAX_LAUNCHES = 117')
p.write_text(s, encoding='utf-8', newline='\n')
print('edited', p.name)
