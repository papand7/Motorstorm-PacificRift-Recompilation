r"""run_vk.py: Kmr1o / Kmr1 (2026-11-23), the stale-keys repro (generated/analysis/stalekeys/RESULTS.md).
exe_sk = build/stalekeys-link (ppucc2 objects + rsx_vulkan_backend.c with RSX_VK_STALE_KEYS), the user's play
configuration (Enhanced lighting, GI, dynamic lights, world-fixed shadows, FSR 3.1 performance, cockpit camera,
async readback ring, texture cache). Kmr1o: RSX_VK_STALE_KEYS=0 (the old caches: expect [stale-keys] "kept for a
recycled" lines and noisy shots after a race reload); Kmr1: the fix on (expect "rebuilt for ... a value a destroyed
image had", clean shots). Both driven by tools/multi_race.py <tag> 4 25 2 and launched with RUN_VK_RACE_S=480.
Inserted before Klt5t. usage: py -3 add_arm_mr.py"""
import hashlib
import pathlib
import shutil

root = pathlib.Path(__file__).resolve().parents[4]
ab2 = pathlib.Path(__file__).resolve().parents[1] / 'ab2'
p = ab2 / 'run_vk.py'
s = p.read_text(encoding='utf-8')
if "'Kmr1o'" in s:
    print('already edited'); raise SystemExit
src = root / 'build' / 'stalekeys-link' / 'MotorStormPacificRiftRecomp.exe'
d = ab2 / 'exe_sk'
d.mkdir(exist_ok=True)
shutil.copy2(src, d / 'MotorStormPacificRiftRecomp.exe')
h = hashlib.sha256((d / 'MotorStormPacificRiftRecomp.exe').read_bytes()).hexdigest()
(ab2 / 'exe_sk.sha256').write_text(h + '\n')
print('exe_sk', h)
shots = root / 'build' / 'shots'
base = ("**ARMS['K'][1], 'RSX_HDR': '0', 'MSPR_PATCH': 'drs,vfps,mblur,audiothread', 'PS3_SIM_PACE_HZ': '30', "
        "'MSPR_CAM_MODE': '0', 'RSX_FSR_MODE': '3', 'RSX_FSR': 'performance', 'RSX_LIGHTING': '1', 'RSX_SHADOW_TILES': '1', "
        "'RSX_SHADOW_TILES_STATIC': '1', 'RSX_FX_GI': '1', 'RSX_FX_DYNLIGHTS': '1', 'RSX_RT_READBACK_ASYNC': '1', "
        "'RSX_TEX_BORDER': '1', 'MSPR_LOD_BIAS': '-2', 'MSPR_CULL_SCALE': '0.25', 'RSX_TEX_CACHE': '1', "
        "'RSX_TEX_BUDGET_MB': '1024', 'RSX_VK_MEM_RECYCLE': '1', 'RSX_GPU_REINTERP': '1', "
        "'RSX_SHOTS_FROM': '1500', 'RSX_SHOTS_EVERY': '300', 'RSX_SHOTS_MAX': '120', ")
add = ''
for tag, extra, note in (
        ('mr1o', "'RSX_VK_STALE_KEYS': '0', ", 'old handle-keyed caches (RSX_VK_STALE_KEYS=0): the repro'),
        ('mr1', '', 'the fix (RSX_VK_STALE_KEYS on, default)')):
    add += (f"K_BY_TAG['{tag}'] = ('sk', {{{base}{extra}'RSX_SHOTS': {str(shots / tag)!r}}})   "
            f"# K{tag}: exe_sk {h[:8]}, four races quit to the menu, {note} (stalekeys/RESULTS.md)\n")
a = "K_BY_TAG['fs1o'] = "
assert s.count(a) == 1
i = s.index('\n', s.index(a)) + 1
s = s[:i] + add + s[i:]
a = "'Kfs1o', 'Klt5t',"
assert s.count(a) == 1
s = s.replace(a, "'Kfs1o', 'Kmr1o', 'Kmr1', 'Klt5t',")
p.write_text(s, encoding='utf-8', newline='\n')
print('edited', p.name)
