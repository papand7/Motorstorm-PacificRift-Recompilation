"""Add launches Kk71-Kk74: PGO A/B uncapped. Kk70's configuration (drs,vfps = variable frame rate,
PS3_MAIN_CYCLES=1) with the route trace (nav_sites.cfg) instead of probe_fps.cfg. Kk71/Kk73 run the
base exe 9531e520, Kk72/Kk74 the profile-optimised build of the same tree
(build/motorstorm-vkgame-pgouse, profile build/pgo/ms2.profdata from Kk55). tools/set_pin.py switches
the pinned exe between launches; then `run_vk.py prepare r`.
LF file. usage: py -3 add_arm_k71.py"""
import pathlib

p = pathlib.Path(__file__).resolve().parents[1] / 'ab2' / 'run_vk.py'
s = p.read_text(encoding='utf-8')
if "'Kk71'" in s:
    print('already edited'); raise SystemExit
k70 = "ARMS['K'] = ('r', {**ARMS['K'][1], 'MSPR_PATCH': 'drs,vfps'})   # Kk70:"
i = s.index('\n', s.index(k70)) + 1
s = s[:i] + ("K_BY_TAG['k70'] = ARMS['K']\n"
             "ARMS['K'] = ('r', {k: v for k, v in ARMS['K'][1].items() if k != 'PS3_TRACE_FILE'})"
             "   # Kk71-Kk74: Kk70 uncapped (drs,vfps), route trace only; base 9531e520 (Kk71, Kk73) vs PGO (Kk72, Kk74)\n") + s[i:]
a = "'Pp4', 'Pp5', 'Pp6', 'Yy1']"
assert s.count(a) == 1
s = s.replace(a, "'Pp4', 'Pp5', 'Pp6', 'Kk71', 'Kk72', 'Kk73', 'Kk74', 'Yy1']")
a = 'MAX_LAUNCHES = 120'
assert s.count(a) == 1
s = s.replace(a, 'MAX_LAUNCHES = 124')
p.write_text(s, encoding='utf-8', newline='\n')
print('edited', p.name)
