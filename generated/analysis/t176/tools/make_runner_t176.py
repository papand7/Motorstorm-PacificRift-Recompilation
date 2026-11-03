"""T176: run_t176.py from t171/ab/run_t171.py. T171 arm B's flags on one pinned exe; only RSX_POLY_OFFSET differs.
usage: py -3 make_runner_t176.py <exe sha256>"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
AB = HERE.parent / 'ab'
AB.mkdir(exist_ok=True)
pin = sys.argv[1].lower()
assert len(pin) == 64
src = (HERE.parents[1] / 't171' / 'ab' / 'run_t171.py').read_text('utf-8')


def sub(old, new, count=1):
    global src
    assert src.count(old) == count, (old[:80], src.count(old))
    src = src.replace(old, new)


sub("ROOT / 'build' / 'motorstorm-t171' / 'MotorStormPacificRiftRecomp.exe'", "ROOT / 'build' / 'motorstorm-t176' / 'MotorStormPacificRiftRecomp.exe'")
sub("PIN = '4450ea1fa8d31bcfd6f24ca9b6018459331dad96d6e4d14989b9511d6d12a8be'", f"PIN = '{pin}'")
sub("ARMS = {'A': ('t', {**BASE, 'RSX_SHADER_WINDOW': '0'}), 'B': ('t', {**BASE, 'RSX_SHADER_WINDOW': '1'})}",
    "BASE['RSX_SHADER_WINDOW'] = '1'\nARMS = {'A': ('t', {**BASE, 'RSX_POLY_OFFSET': '0'}), 'B': ('t', {**BASE, 'RSX_POLY_OFFSET': '1'})}")
sub("EXPECT = {'A': _E + '0', 'B': _E + '1'}", "EXPECT = {'A': _E + '1', 'B': _E + '1'}")
sub("RUN_NAME = 't171'", "RUN_NAME = 't176'")
sub("f't171-{arm}{tag}'", "f't176-{arm}{tag}'")
sub("run_t171.py launch A|B <tag>", "run_t176.py launch A|B <tag>")
(AB / 'run_t176.py').write_text(src, 'utf-8')
(AB / 'cpath_sites.cfg').write_bytes((HERE.parents[1] / 't171' / 'ab' / 'cpath_sites.cfg').read_bytes())
print('ok')
