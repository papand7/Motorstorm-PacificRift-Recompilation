r"""run_vk.py: Kk98 (2026-11-06), exe feba7954. Kk97 + RSX_ZSNAP_ON_WRITE=1: the shadow atlas copy the readers sample
is retired on every depth write, not only on a clear (HYPOTHESIS: a stale copy makes the shadows jump while
driving, Kk97 frames 22595-22602). Play session, F9 capture to build/shots/k98.
usage: py -3 add_arm_k98.py; launch with RUN_VK_PLAY=1 RUN_VK_RACE_S=900"""
import pathlib

root = pathlib.Path(__file__).resolve().parents[4]
p = pathlib.Path(__file__).resolve().parents[1] / 'ab2' / 'run_vk.py'
s = p.read_text(encoding='utf-8')
if "'Kk98'" in s:
    print('already edited'); raise SystemExit
shots = (root / 'build' / 'shots' / 'k98')
shots.mkdir(parents=True, exist_ok=True)
a = "K_BY_TAG['k97'] = "
assert s.count(a) == 1
i = s.index('\n', s.index(a)) + 1
s = s[:i] + ("K_BY_TAG['k98'] = ('r', {**ARMS['K'][1], 'RSX_HDR': '1', 'MSPR_SHADOW_RANGE': '400', "
             "'MSPR_LOD_BIAS': '-1', 'MSPR_CULL_SCALE': '0.5', 'RSX_ZSNAP_ON_WRITE': '1', "
             f"'RSX_SHOTS': {str(shots)!r}, 'RSX_SHOTS_MAX': '1800'}})"
             "   # Kk98: exe feba7954, Kk97 + RSX_ZSNAP_ON_WRITE (shadow jump A/B)\n") + s[i:]
a = "'Kk96', 'Kk97', 'Yy1']"
assert s.count(a) == 1
s = s.replace(a, "'Kk96', 'Kk97', 'Kk98', 'Yy1']")
a = 'MAX_LAUNCHES = 147'
assert s.count(a) == 1
s = s.replace(a, 'MAX_LAUNCHES = 148')
p.write_text(s, encoding='utf-8', newline='\n')
print('edited', p.name, shots)
