"""Add launch Kk49: Kk48 without the dump and with the upscaled pack (RSX_TEX_PACK=build/texpack/ms2,
made by texpack.py from Kk48's dump: Real-ESRGAN 4x, at most 2048 a side, BC1/BC3 with mips).
Pictures against Kk47 (the same race at 1.5x, original textures).

usage: py -3 add_arm_k49.py"""
import pathlib

root = pathlib.Path(__file__).resolve().parents[4]
p = pathlib.Path(__file__).resolve().parents[1] / 'ab2' / 'run_vk.py'
s = p.read_bytes().decode('utf-8')
assert '\r\n' not in s
lines = s.split('\n')
i = [k for k, l in enumerate(lines) if l.startswith("ARMS['K']") and '   # Kk48: ' in l][0]
pack = (root / 'build' / 'texpack' / 'ms2').as_posix()
lines.insert(i + 1, "ARMS['K'] = ('r', {**{k: v for k, v in ARMS['K'][1].items() if k != 'RSX_TEX_DUMP'}, "
                    "'RSX_TEX_PACK': '%s'})   # Kk49: exe c131cfd4, Kk48 with the upscaled pack instead of the dump"
                    % pack)
s = '\n'.join(lines)


def sub(a, b):
    global s
    assert s.count(a) == 1, (a, s.count(a))
    s = s.replace(a, b)


sub("'Kk47', 'Kk48', 'Yy1']", "'Kk47', 'Kk48', 'Kk49', 'Yy1']")
sub("MAX_LAUNCHES = 95", "MAX_LAUNCHES = 96")
p.write_bytes(s.encode('utf-8'))
print('ok')
