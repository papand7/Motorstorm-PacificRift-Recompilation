"""T171: run_t171.py from t169/ab/run_t169.py. Two arms on one pinned exe, differing only in RSX_SHADER_WINDOW.
usage: py -3 make_runner_t171.py"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
AB = HERE.parent / 'ab'
AB.mkdir(exist_ok=True)
src = (HERE.parents[1] / 't169' / 'ab' / 'run_t169.py').read_text('utf-8')


def sub(old, new, count=1):
    global src
    assert src.count(old) == count, (old[:80], src.count(old))
    src = src.replace(old, new)


i0 = src.index("SRC_EXES = {")
i1 = src.index("HARD_KILL_S = 203.0")
src = src[:i0] + "SRC_EXES = {'t': ROOT / 'build' / 'motorstorm-t171' / 'MotorStormPacificRiftRecomp.exe'}\nPIN = '4450ea1fa8d31bcfd6f24ca9b6018459331dad96d6e4d14989b9511d6d12a8be'\n" + src[i1:]
i0 = src.index("ARMS['A'] = ('t'")
i1 = src.index("VEL_CAP_S = 38.0")
src = src[:i0] + """VEL_RSXI.update({'RSXI_MINDRAWS': '700', 'RSXI_MAX_EVENTS': '4096', 'RSXI_RTS': '00750000,01650000,0243AB00,0BA10000'})
# T171: T169 arm B's set; only RSX_SHADER_WINDOW differs.
BASE = {**ARMS['F'][1], **VEL_RSXI, 'RSX_RT_REINTERP': '0', 'RSX_DEPTH_STATE': '0'}
ARMS = {'A': ('t', {**BASE, 'RSX_SHADER_WINDOW': '0'}), 'B': ('t', {**BASE, 'RSX_SHADER_WINDOW': '1'})}
""" + src[i1:]
i0 = src.index("EXPECT['A'] = EXPECT['F']")
i1 = src.index("RX_SERIOUS = ")
src = src[:i0] + """_E = EXPECT['F'].replace('depth_state=1', 'depth_state=0') + ' rt_reinterp=0 shader_window='
EXPECT = {'A': _E + '0', 'B': _E + '1'}
""" + src[i1:]
sub("RUN_NAME = 't169'", "RUN_NAME = 't171'")
sub("'CELLMARK_DUMP': '16', 'CELLMARK_DUMP_EVERY': '64',", "'CELLMARK_DUMP': '32', 'CELLMARK_DUMP_EVERY': '32',")
sub("f't169-{arm}{tag}'", "f't171-{arm}{tag}'")
sub("run_t169.py launch D|F|A|B|C <tag>", "run_t171.py launch A|B <tag>")
sub("str(HERE.parent / 'tools' / 'dbwin_d3d12_t169.py')", "str(HERE.parents[1] / 't169' / 'tools' / 'dbwin_d3d12_t169.py')")
sub("        h = sha(d / SRC_EXES[x].name)\n", "        h = sha(d / SRC_EXES[x].name)\n        assert h == PIN, h\n")
sub("EXE_SHA = (EXEDIR / f'exe_{x}.sha256').read_text().split()[0]", "EXE_SHA = PIN")
(AB / 'run_t171.py').write_text(src, 'utf-8')
(AB / 'cpath_sites.cfg').write_bytes((HERE.parents[1] / 't169' / 'ab' / 'cpath_sites.cfg').read_bytes())
print('ok')
