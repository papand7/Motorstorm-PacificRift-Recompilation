"""Add launch Kk40: Kk39 plus PS3_FSTRACE=50 (every 50th lv2 sys_fs_read: fd, offset, size), under
io_rate.py with write rates: Kk39 read 30-44 MB/s (about 2,000 reads/s) through the whole race with
ms2.psarc (fd 5) and the FIOS HDD cache (cache.idx fd 3, cache.dat fd 4) open. Which file, which offsets?

usage: py -3 add_arm_k40.py"""
import pathlib

p = pathlib.Path(__file__).resolve().parents[1] / 'ab2' / 'run_vk.py'
s = p.read_bytes().decode('utf-8')
lines = s.split('\n')
i = [k for k, l in enumerate(lines) if l.startswith("ARMS['K']") and '   # Kk39: ' in l][0]
eol = '\r' if lines[i].endswith('\r') else ''
lines.insert(i + 1, "ARMS['K'] = ('r', {**ARMS['K'][1], 'PS3_FSTRACE': '50'})"
                    "   # Kk40: exe c693e2cb, Kk39 + every 50th lv2 file read logged, under io_rate.py" + eol)
s = '\n'.join(lines)


def sub(a, b):
    global s
    assert s.count(a) == 1, (a, s.count(a))
    s = s.replace(a, b)


sub("'Kk38', 'Kk39', 'Yy1']", "'Kk38', 'Kk39', 'Kk40', 'Yy1']")
sub("MAX_LAUNCHES = 86", "MAX_LAUNCHES = 87")
p.write_bytes(s.encode('utf-8'))
print('ok')
