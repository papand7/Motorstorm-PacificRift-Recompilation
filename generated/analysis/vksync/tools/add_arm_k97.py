r"""run_vk.py: Kk97 (2026-11-06), exe feba7954 (5d38fff4 + MSPR_DIST in the parser's second lifted entry func_00360DD8; in Kk96 only the shadow range applied). Kk94 (HDR, the
game's own shadows, F9 capture to build/shots/k97) with longer distances: shadow range 400 (game 200),
lodBias -1 on every group, cull thresholds halved. A play session: does the user see farther shadows,
objects and finer LODs? usage: py -3 add_arm_k97.py; launch with RUN_VK_PLAY=1 RUN_VK_RACE_S=900"""
import pathlib

root = pathlib.Path(__file__).resolve().parents[4]
p = pathlib.Path(__file__).resolve().parents[1] / 'ab2' / 'run_vk.py'
s = p.read_text(encoding='utf-8')
if "'Kk97'" in s:
    print('already edited'); raise SystemExit
shots = (root / 'build' / 'shots' / 'k97')
shots.mkdir(parents=True, exist_ok=True)
a = "K_BY_TAG['k96'] = "
assert s.count(a) == 1
i = s.index('\n', s.index(a)) + 1
s = s[:i] + ("K_BY_TAG['k97'] = ('r', {**ARMS['K'][1], 'RSX_HDR': '1', 'MSPR_SHADOW_RANGE': '400', "
             "'MSPR_LOD_BIAS': '-1', 'MSPR_CULL_SCALE': '0.5', "
             f"'RSX_SHOTS': {str(shots)!r}, 'RSX_SHOTS_MAX': '1800'}})"
             "   # Kk97: exe feba7954, Kk94 + longer shadow/LOD/draw distances (MSPR_DIST)\n") + s[i:]
a = "'Kk95', 'Kk96', 'Yy1']"
assert s.count(a) == 1
s = s.replace(a, "'Kk95', 'Kk96', 'Kk97', 'Yy1']")
a = 'MAX_LAUNCHES = 146'
assert s.count(a) == 1
s = s.replace(a, 'MAX_LAUNCHES = 147')
p.write_text(s, encoding='utf-8', newline='\n')
print('edited', p.name, shots)
