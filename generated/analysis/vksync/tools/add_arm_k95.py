r"""run_vk.py: Kk95 (2026-11-06), exe e0e31b49. Kk94 with the game's motion blur off (MSPR_PATCH=drs,mblur), a
play session with F9 capture to build/shots/k95: do the ghost copies trailing the player's vehicle (Kk93
frames 3244-3247) go away? At rest (passdump_k80 passes 038/039) the dust depth matches the main depth.
usage: py -3 add_arm_k95.py; launch with RUN_VK_PLAY=1 RUN_VK_RACE_S=900"""
import pathlib

root = pathlib.Path(__file__).resolve().parents[4]
p = pathlib.Path(__file__).resolve().parents[1] / 'ab2' / 'run_vk.py'
s = p.read_text(encoding='utf-8')
if "'Kk95'" in s:
    print('already edited'); raise SystemExit
shots = (root / 'build' / 'shots' / 'k95')
shots.mkdir(parents=True, exist_ok=True)
a = "K_BY_TAG['k94'] = "
assert s.count(a) == 1
i = s.index('\n', s.index(a)) + 1
s = s[:i] + ("K_BY_TAG['k95'] = ('r', {**ARMS['K'][1], 'RSX_HDR': '1', 'MSPR_PATCH': 'drs,mblur', "
             f"'RSX_SHOTS': {str(shots)!r}, 'RSX_SHOTS_MAX': '1800'}})"
             "   # Kk95: exe e0e31b49, Kk94 with motion blur off (vehicle ghosts A/B)\n") + s[i:]
a = "'Kk93', 'Kk94', 'Yy1']"
assert s.count(a) == 1
s = s.replace(a, "'Kk93', 'Kk94', 'Kk95', 'Yy1']")
a = 'MAX_LAUNCHES = 144'
assert s.count(a) == 1
s = s.replace(a, 'MAX_LAUNCHES = 145')
p.write_text(s, encoding='utf-8', newline='\n')
print('edited', p.name, shots)
