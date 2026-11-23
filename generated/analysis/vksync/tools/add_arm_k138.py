r"""run_vk.py: Kk138-Kk140 (2026-11-06), exe 7645f190 (d67a8e85 + RSX_RT_REUSE). Ray-traced shadow cost with the GPU
free (BF1943 closed): Kk138 RT on, Kk139 RT off, both at the game's own 30 fps cap (MSPR_PATCH=drs, no vfps). Driven by
tools/gate_at_race.py <tag> <gate> 6 60 (throttle only, no F9 shots). Compare the [rsx-hb] frame rate.
usage: py -3 add_arm_k138.py; launch each with RUN_VK_PLAY=1 RUN_VK_RACE_S=150"""
import pathlib

root = pathlib.Path(__file__).resolve().parents[4]
ab2 = pathlib.Path(__file__).resolve().parents[1] / 'ab2'
p = ab2 / 'run_vk.py'
s = p.read_text(encoding='utf-8')
if "'Kk138'" in s:
    print('already edited'); raise SystemExit
dxc = root / 'build' / 'vulkan-sdk' / 'Bin' / 'dxc.exe'
base = f"**ARMS['K'][1], 'RSX_HDR': '1', 'MSPR_PATCH': 'drs', 'RSX_RT_DXC': {str(dxc)!r}, "
add = ''
for tag, extra, note in (('k138', "'RSX_RT_SHADOW': '1'", 'RT on, 30 fps cap'),
                         ('k139', "'RSX_RT_SHADOW': '0'", 'RT off, 30 fps cap')):
    add += f"K_BY_TAG['{tag}'] = ('r', {{{base}{extra}}})   # K{tag}: exe 7645f190, {note} (fps A/B)\n"
a = "K_BY_TAG['k137'] = "
assert s.count(a) == 1
i = s.index('\n', s.index(a)) + 1
s = s[:i] + add + s[i:]
a = "'Kk136', 'Kk137', 'Yy1']"
assert s.count(a) == 1
s = s.replace(a, "'Kk136', 'Kk137', 'Kk138', 'Kk139', 'Yy1']")
a = 'MAX_LAUNCHES = 187'
assert s.count(a) == 1
s = s.replace(a, 'MAX_LAUNCHES = 189')
p.write_text(s, encoding='utf-8', newline='\n')
print('edited', p.name)
