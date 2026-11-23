r"""run_vk.py: Kk94 (2026-11-06), exe e0e31b49. Kk93 without RSX_SHADOW_STABLE (the game's own shadows) as a
play session with F9 capture to build/shots/k94, the A/B partner of Kk93's frames. Also: RUN_VK_PLAY drops
--stop-on-fatal too (Kk93 was stopped as fatal_log on the GPU watchdog line).
usage: py -3 add_arm_k94.py; launch with RUN_VK_PLAY=1 RUN_VK_RACE_S=900"""
import pathlib

root = pathlib.Path(__file__).resolve().parents[4]
p = pathlib.Path(__file__).resolve().parents[1] / 'ab2' / 'run_vk.py'
s = p.read_text(encoding='utf-8')
if "'Kk94'" in s:
    print('already edited'); raise SystemExit
shots = (root / 'build' / 'shots' / 'k94')
shots.mkdir(parents=True, exist_ok=True)
a = "K_BY_TAG['k93'] = "
assert s.count(a) == 1
i = s.index('\n', s.index(a)) + 1
s = s[:i] + ("K_BY_TAG['k94'] = ('r', {**ARMS['K'][1], 'RSX_HDR': '1', "
             f"'RSX_SHOTS': {str(shots)!r}, 'RSX_SHOTS_MAX': '1800'}})"
             "   # Kk94: exe e0e31b49, Kk93 without RSX_SHADOW_STABLE (play session, A/B)\n") + s[i:]
a = "'Kk92', 'Kk93', 'Yy1']"
assert s.count(a) == 1
s = s.replace(a, "'Kk92', 'Kk93', 'Kk94', 'Yy1']")
a = 'MAX_LAUNCHES = 143'
assert s.count(a) == 1
s = s.replace(a, 'MAX_LAUNCHES = 144')
a = """        if PLAY and '--stop-on-line' in a:
            j = a.index('--stop-on-line'); del a[j:j + 2]
"""
assert s.count(a) == 1
s = s.replace(a, a + """        if PLAY and '--stop-on-fatal' in a:   # Kk93: the watchdog line also counts as fatal
            a.remove('--stop-on-fatal')
""")
p.write_text(s, encoding='utf-8', newline='\n')
print('edited', p.name, shots)
