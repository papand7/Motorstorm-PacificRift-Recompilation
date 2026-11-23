r"""run_vk.py: Kk135-Kk137 (2026-11-06), exe aae6d350 (d67a8e85 + RSX_RT_REUSE). Ray-traced shadow cost with the GPU
free (BF1943 closed): Kk135 RT on (BLAS reuse, default), Kk136 RT on, RSX_RT_REUSE=0, Kk137 RT off. Driven by
tools/gate_at_race.py <tag> <gate> 6 60 (throttle only, no F9 shots). Compare the [rsx-hb] frame rate.
usage: py -3 add_arm_k135.py; launch each with RUN_VK_PLAY=1 RUN_VK_RACE_S=150"""
import pathlib

root = pathlib.Path(__file__).resolve().parents[4]
ab2 = pathlib.Path(__file__).resolve().parents[1] / 'ab2'
p = ab2 / 'run_vk.py'
s = p.read_text(encoding='utf-8')
if "'Kk135'" in s:
    print('already edited'); raise SystemExit
dxc = root / 'build' / 'vulkan-sdk' / 'Bin' / 'dxc.exe'
base = f"**ARMS['K'][1], 'RSX_HDR': '1', 'MSPR_PATCH': 'drs,vfps,mblur', 'RSX_RT_DXC': {str(dxc)!r}, "
add = ''
for tag, extra, note in (('k135', "'RSX_RT_SHADOW': '1'", 'RT on, BLAS reuse'),
                         ('k136', "'RSX_RT_SHADOW': '1', 'RSX_RT_REUSE': '0'", 'RT on, no reuse'),
                         ('k137', "'RSX_RT_SHADOW': '0'", 'RT off')):
    add += f"K_BY_TAG['{tag}'] = ('r', {{{base}{extra}}})   # K{tag}: exe aae6d350, {note} (fps A/B)\n"
a = "K_BY_TAG['k134'] = "
assert s.count(a) == 1
i = s.index('\n', s.index(a)) + 1
s = s[:i] + add + s[i:]
a = "'Kk133', 'Kk134', 'Yy1']"
assert s.count(a) == 1
s = s.replace(a, "'Kk133', 'Kk134', 'Kk135', 'Kk136', 'Kk137', 'Yy1']")
a = 'MAX_LAUNCHES = 184'
assert s.count(a) == 1
s = s.replace(a, 'MAX_LAUNCHES = 187')
p.write_text(s, encoding='utf-8', newline='\n')
print('edited', p.name)
