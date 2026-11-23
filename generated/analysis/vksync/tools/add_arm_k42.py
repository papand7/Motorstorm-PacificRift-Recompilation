"""Add launch Kk42 and an opt-in long-race override to run_vk.py.

Kk39-Kk41: from boot the game reads ms2.psarc (4.8 GB) sequentially at about 20 MB/s and writes it into
the FIOS HDD cache (cache.dat), all race long. The game clears that cache at every boot itself
(cellSysCacheMount then cellSysCacheClear, as on a PS3), so FIOS rebuilds it each session. Kk42 races
long enough for that background copy to finish (about 4 min at 20 MB/s) and compares frame times
during and after it, in one run, under io_rate.py. Kk39's configuration (exe c693e2cb).

Runner change: RUN_VK_RACE_S=<s> (environment of run_vk.py, unset = unchanged 75 s / 205 s caps) sets
the race stop to <s> s after race entry and the fast_startup timeout to <s> + 130 s.

usage: py -3 add_arm_k42.py"""
import pathlib

p = pathlib.Path(__file__).resolve().parents[1] / 'ab2' / 'run_vk.py'
s = p.read_bytes().decode('utf-8')
lines = s.split('\n')
i = [k for k, l in enumerate(lines) if l.startswith("ARMS['K']") and '   # Kk41: ' in l][0]
eol = '\r' if lines[i].endswith('\r') else ''
lines.insert(i + 1, "ARMS['K'] = ('r', {k: v for k, v in ARMS['K'][1].items() if k not in ('FS_READ_ALL', 'PS3_FSLOG_READS')})"
                    "   # Kk42: exe c693e2cb, Kk39 config, long race (RUN_VK_RACE_S=300) under io_rate.py" + eol)
s = '\n'.join(lines)


def sub(a, b):
    global s
    assert s.count(a) == 1, (a, s.count(a))
    s = s.replace(a, b)


sub("'Kk40', 'Kk41', 'Yy1']", "'Kk40', 'Kk41', 'Kk42', 'Yy1']")
sub("MAX_LAUNCHES = 88", "MAX_LAUNCHES = 89")
sub("RACE_STOP = {a: 75.0 for a in ARMS}" + eol,
    "RACE_STOP = {a: 75.0 for a in ARMS}" + eol +
    "LONG_S = float(os.environ.get('RUN_VK_RACE_S') or 0)   # Kk42: opt-in long race (race stop, timeout)" + eol +
    "if LONG_S:" + eol +
    "    RACE_STOP = {a: LONG_S for a in ARMS}" + eol)
sub("            '--timeout', '205']",
    "            '--timeout', str(int(LONG_S + 130)) if LONG_S else '205']")
sub("    fast_startup.MAX_TIMEOUT_S = 205.0",
    "    fast_startup.MAX_TIMEOUT_S = LONG_S + 130.0 if LONG_S else 205.0")
p.write_bytes(s.encode('utf-8'))
print('ok')
