r"""run_vk.py: Kk146-Kk146 (2026-11-06), exe 4da0378a (d67a8e85 + RSX_RT_REUSE). Ray-traced shadow cost with the GPU
free (BF1943 closed): Kk146 RT on, Kk139 RT off, both at the game's own 30 fps cap (MSPR_PATCH=drs, no vfps). Driven by
tools/gate_at_race.py <tag> <gate> 6 60 (throttle only, no F9 shots). Compare the [rsx-hb] frame rate.
usage: py -3 add_arm_k146.py; launch each with RUN_VK_PLAY=1 RUN_VK_RACE_S=150"""
import pathlib

root = pathlib.Path(__file__).resolve().parents[4]
ab2 = pathlib.Path(__file__).resolve().parents[1] / 'ab2'
p = ab2 / 'run_vk.py'
s = p.read_text(encoding='utf-8')
if "'Kk146'" in s:
    print('already edited'); raise SystemExit
dxc = root / 'build' / 'vulkan-sdk' / 'Bin' / 'dxc.exe'
base = f"**ARMS['K'][1], 'RSX_HDR': '1', 'MSPR_PATCH': 'drs', 'PS3_SIM_PACE': '1', 'MSPR_CAM': '0', 'MSPR_CAM_SHAKE': '1', 'RSX_RT_DXC': {str(dxc)!r}, "
add = ''
for tag, extra, note in (('k146', f"'RSX_RT_SHADOW': '1', 'PS3_TRACE_OFF_FILE': {str(ab2 / 'trace_off_k146')!r}", 'PLAY: world-space RT shadows, original timing, 30 Hz pacer, tracer off at race'),):
    add += f"K_BY_TAG['{tag}'] = ('r', {{{base}{extra}}})   # K{tag}: exe 4da0378a, {note} (fps A/B)\n"
a = "K_BY_TAG['k145'] = "
assert s.count(a) == 1
i = s.index('\n', s.index(a)) + 1
s = s[:i] + add + s[i:]
a = "'Kk144', 'Kk145', 'Yy1']"
assert s.count(a) == 1
s = s.replace(a, "'Kk144', 'Kk145', 'Kk146', 'Yy1']")
a = 'MAX_LAUNCHES = 195'
assert s.count(a) == 1
s = s.replace(a, 'MAX_LAUNCHES = 196')
p.write_text(s, encoding='utf-8', newline='\n')
print('edited', p.name)
