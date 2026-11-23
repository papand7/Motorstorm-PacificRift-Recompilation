"""Add launch Kk43: the real per-frame cost with the frame-rate cap lifted, toward 60 fps.

At the game's 30 fps lock a frame cannot take less than 33.3 ms. Kk37 already measured 32.5-32.9 ms a
present (the cap), so the true cost is unknown. Kk43 = Kk39's configuration (exe c693e2cb) +
MSPR_PATCH=vfps (RPCS3 patch: variable frame rate, game speed from elapsed time), in a long race
(RUN_VK_RACE_S=300) under io_rate.py, so frames can be read during and after the FIOS background cache
build (about the first 130 s after launch, Kk42).

Runner change: with RUN_VK_RACE_S set, the controller's hard session cap (HARD_KILL_S, 209 s) becomes
RUN_VK_RACE_S + 134 s (the fast_startup timeout + 4 s), as it is 205 + 4 s by default.

usage: py -3 add_arm_k43.py"""
import pathlib

p = pathlib.Path(__file__).resolve().parents[1] / 'ab2' / 'run_vk.py'
s = p.read_bytes().decode('utf-8')
assert '\r\n' not in s   # run_vk.py is an LF file
lines = s.split('\n')
i = [k for k, l in enumerate(lines) if l.startswith("ARMS['K']") and '   # Kk42: ' in l][0]
lines.insert(i + 1, "ARMS['K'] = ('r', {**ARMS['K'][1], 'MSPR_PATCH': 'vfps'})"
                    "   # Kk43: exe c693e2cb, Kk42 + variable frame rate (RPCS3 vfps patch), long race under io_rate.py")
s = '\n'.join(lines)


def sub(a, b):
    global s
    assert s.count(a) == 1, (a, s.count(a))
    s = s.replace(a, b)


sub("'Kk41', 'Kk42', 'Yy1']", "'Kk41', 'Kk42', 'Kk43', 'Yy1']")
sub("MAX_LAUNCHES = 89", "MAX_LAUNCHES = 90")
sub("if LONG_S:\n    RACE_STOP = {a: LONG_S for a in ARMS}\n",
    "if LONG_S:\n    RACE_STOP = {a: LONG_S for a in ARMS}\n"
    "    HARD_KILL_S = LONG_S + 134.0   # Kk43: the long race's own cap (timeout + 4 s)\n")
p.write_bytes(s.encode('utf-8'))
print('ok')
