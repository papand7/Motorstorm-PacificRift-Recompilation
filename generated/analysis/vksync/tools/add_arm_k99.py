r"""run_vk.py: Kk99/Kk100 (2026-11-06), exe feba7954. Shadow jump A/B without a player (tools/auto_drive.py holds
the throttle and toggles F9): Kk99 = Kk97 (longer distances, the shadow copy retired on clears only), Kk100 =
Kk98 (+ RSX_ZSNAP_ON_WRITE=1). Frames to build/shots/k99, k100.
usage: py -3 add_arm_k99.py; launch each with RUN_VK_PLAY=1 RUN_VK_RACE_S=120 next to auto_drive.py <tag>"""
import pathlib

root = pathlib.Path(__file__).resolve().parents[4]
p = pathlib.Path(__file__).resolve().parents[1] / 'ab2' / 'run_vk.py'
s = p.read_text(encoding='utf-8')
if "'Kk99'" in s:
    print('already edited'); raise SystemExit
base = ("{**ARMS['K'][1], 'RSX_HDR': '1', 'MSPR_SHADOW_RANGE': '400', 'MSPR_LOD_BIAS': '-1', "
        "'MSPR_CULL_SCALE': '0.5', ")
add = ''
for tag, extra, note in (('k99', '', 'Kk97 auto-driven'), ('k100', "'RSX_ZSNAP_ON_WRITE': '1', ", 'Kk98 auto-driven')):
    shots = root / 'build' / 'shots' / tag
    shots.mkdir(parents=True, exist_ok=True)
    add += (f"K_BY_TAG['{tag}'] = ('r', {base}{extra}'RSX_SHOTS': {str(shots)!r}, 'RSX_SHOTS_MAX': '600'}})"
            f"   # K{tag}: exe feba7954, {note} (shadow jump A/B, tools/auto_drive.py)\n")
a = "K_BY_TAG['k98'] = "
assert s.count(a) == 1
i = s.index('\n', s.index(a)) + 1
s = s[:i] + add + s[i:]
a = "'Kk97', 'Kk98', 'Yy1']"
assert s.count(a) == 1
s = s.replace(a, "'Kk97', 'Kk98', 'Kk99', 'Kk100', 'Yy1']")
a = 'MAX_LAUNCHES = 148'
assert s.count(a) == 1
s = s.replace(a, 'MAX_LAUNCHES = 150')
p.write_text(s, encoding='utf-8', newline='\n')
print('edited', p.name)
