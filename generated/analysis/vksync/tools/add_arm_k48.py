"""Add launch Kk48: Kk47 (RSX_RES_SCALE=1.5, no dynamic resolution) on the texture-pack build with
RSX_TEX_DUMP: every distinct texture of the boot, menus and race written once to build/texdump/ms2
(private: game assets, never committed).

usage: py -3 add_arm_k48.py <exe sha256>"""
import pathlib
import sys

pin = sys.argv[1]
assert len(pin) == 64, pin
root = pathlib.Path(__file__).resolve().parents[4]
p = pathlib.Path(__file__).resolve().parents[1] / 'ab2' / 'run_vk.py'
s = p.read_bytes().decode('utf-8')
assert '\r\n' not in s
lines = s.split('\n')
i = [k for k, l in enumerate(lines) if l.startswith("ARMS['K']") and '   # Kk47: ' in l][0]
dump = (root / 'build' / 'texdump' / 'ms2').as_posix()
lines.insert(i + 1, "ARMS['K'] = ('r', {**ARMS['K'][1], 'RSX_TEX_DUMP': '%s'})"
                    "   # Kk48: exe %s, Kk47 + texture dump" % (dump, pin[:8]))
s = '\n'.join(lines)


def sub(a, b):
    global s
    assert s.count(a) == 1, (a, s.count(a))
    s = s.replace(a, b)


sub("'Kk46', 'Kk47', 'Yy1']", "'Kk46', 'Kk47', 'Kk48', 'Yy1']")
sub("MAX_LAUNCHES = 94", "MAX_LAUNCHES = 95")
sub("PIN = 'c3e350d378e9b2c5a4122c76385687191f8a2d1fc28aff99b6c16a7a935b2fe3'   # ",
    "PIN = '%s'   # texture packs (Kk48); " % pin)
p.write_bytes(s.encode('utf-8'))
print('ok')
