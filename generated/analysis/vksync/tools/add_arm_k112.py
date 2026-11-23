r"""run_vk.py: Kk112/Kk113 (2026-11-06), exe 71deee8c. Which part of the stable map's per-update change makes
the picture jump (Kk105: 21 jumps, Kk111 RSX_SST_FREEZE=1: 2): Kk112 RSX_SST_FREEZE=2 holds each tile's
size (one rung coarser than its first), Kk113 RSX_SST_FREEZE=3 holds its position. Otherwise Kk108.
usage: py -3 add_arm_k112.py; launch each with RUN_VK_PLAY=1 RUN_VK_RACE_S=150 next to auto_drive.py <tag> 6 3 8"""
import pathlib

root = pathlib.Path(__file__).resolve().parents[4]
ab2 = pathlib.Path(__file__).resolve().parents[1] / 'ab2'
p = ab2 / 'run_vk.py'
s = p.read_text(encoding='utf-8')
if "'Kk112'" in s:
    print('already edited'); raise SystemExit
add = ''
for tag, fz in (('k112', '2'), ('k113', '3')):
    shots = root / 'build' / 'shots' / tag
    shots.mkdir(parents=True, exist_ok=True)
    cap = ab2 / f'shadowcap_{tag}.bin'
    add += (f"K_BY_TAG['{tag}'] = ('r', {{**ARMS['K'][1], 'RSX_HDR': '1', 'RSX_SHADOW_STABLE': '1', 'RSX_SST_TRACE': '1', "
            f"'RSX_SST_FREEZE': '{fz}', 'MSPR_PATCH': 'drs,vfps,mblur', 'RSX_SHADOW_CAP': {str(cap)!r}, "
            f"'RSX_SHADOW_CAP_AFTER': '55', 'RSX_SHADOW_CAP_FRAMES': '600', "
            f"'RSX_SHOTS': {str(shots)!r}, 'RSX_SHOTS_MAX': '600'}})"
            f"   # K{tag}: exe 71deee8c, stable shadows with RSX_SST_FREEZE={fz} (tools/auto_drive.py)\n")
a = "K_BY_TAG['k111'] = "
assert s.count(a) == 1
i = s.index('\n', s.index(a)) + 1
s = s[:i] + add + s[i:]
a = "'Kk110', 'Kk111', 'Yy1']"
assert s.count(a) == 1
s = s.replace(a, "'Kk110', 'Kk111', 'Kk112', 'Kk113', 'Yy1']")
a = 'MAX_LAUNCHES = 161'
assert s.count(a) == 1
s = s.replace(a, 'MAX_LAUNCHES = 163')
p.write_text(s, encoding='utf-8', newline='\n')
print('edited', p.name)
