"""Add launch Kk55: the PGO training race. Kk51's configuration (RSX_RES_SCALE=1.5, no dynamic
resolution, PS3_MAIN_CYCLES=1) on the instrumented exe (build/motorstorm-vkgame-pgogen, pinned with
set_pin.py), with PS3_PGO_WINDOW=60000:140000 and LLVM_PROFILE_FILE in build/pgo/. Launch with
RUN_VK_RACE_S=100 so the window closes before the runner stops the game (the instrumented build runs
slower).

usage: py -3 add_arm_k55.py"""
import pathlib

root = pathlib.Path(__file__).resolve().parents[4]
p = pathlib.Path(__file__).resolve().parents[1] / 'ab2' / 'run_vk.py'
s = p.read_bytes().decode('utf-8')
assert '\r\n' not in s
lines = s.split('\n')
i = [k for k, l in enumerate(lines) if l.startswith("ARMS['K']") and '   # Kk51-Kk54: ' in l][0]
prof = (root / 'build' / 'pgo' / 'ms2-%p.profraw').as_posix()
lines.insert(i + 1, "ARMS['K'] = ('r', {**ARMS['K'][1], 'PS3_PGO_WINDOW': '60000:140000', 'LLVM_PROFILE_FILE': '%s'})"
                    "   # Kk55: the PGO training race on the instrumented exe" % prof)
s = '\n'.join(lines)


def sub(a, b):
    global s
    assert s.count(a) == 1, (a, s.count(a))
    s = s.replace(a, b)


sub("'Kk53', 'Kk54', 'Yy1']", "'Kk53', 'Kk54', 'Kk55', 'Yy1']")
sub("MAX_LAUNCHES = 101", "MAX_LAUNCHES = 102")
p.write_bytes(s.encode('utf-8'))
print('ok')
