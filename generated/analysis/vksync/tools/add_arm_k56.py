"""Add launches Kk56-Kk59: the PGO A/B. Kk51's configuration (RSX_RES_SCALE=1.5, no dynamic
resolution, PS3_MAIN_CYCLES=1), without Kk55's profile window. Kk56/Kk58 run the base exe 8c01ef18,
Kk57/Kk59 the profile-optimised build (build/motorstorm-vkgame-pgouse, profile build/pgo/ms2.profdata
from the Kk55 race). tools/set_pin.py switches the pinned exe between launches.

usage: py -3 add_arm_k56.py"""
import pathlib

p = pathlib.Path(__file__).resolve().parents[1] / 'ab2' / 'run_vk.py'
s = p.read_bytes().decode('utf-8')
assert '\r\n' not in s
lines = s.split('\n')
i = [k for k, l in enumerate(lines) if l.startswith("ARMS['K']") and '   # Kk55: ' in l][0]
lines.insert(i + 1, "ARMS['K'] = ('r', {k: v for k, v in ARMS['K'][1].items() if k not in ('PS3_PGO_WINDOW', 'LLVM_PROFILE_FILE')})"
                    "   # Kk56-Kk59: Kk51's configuration; base exe 8c01ef18 (Kk56, Kk58) vs PGO build (Kk57, Kk59)")
s = '\n'.join(lines)


def sub(a, b):
    global s
    assert s.count(a) == 1, (a, s.count(a))
    s = s.replace(a, b)


sub("'Kk54', 'Kk55', 'Yy1']", "'Kk54', 'Kk55', 'Kk56', 'Kk57', 'Kk58', 'Kk59', 'Yy1']")
sub("MAX_LAUNCHES = 102", "MAX_LAUNCHES = 106")
p.write_bytes(s.encode('utf-8'))
print('ok')
