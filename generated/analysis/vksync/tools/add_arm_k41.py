"""Add launch Kk41: Kk40 traced nothing (the reads take the cellFs HLE path, not lv2), so: every cellFs read
logged (FS_READ_ALL=1) and ms2.psarc reads with offsets (PS3_FSLOG_READS=5). Kk40 note: PS3_FSTRACE=50, under
io_rate.py with write rates: Kk39 read 30-44 MB/s (about 2,000 reads/s) through the whole race with
ms2.psarc (fd 5) and the FIOS HDD cache (cache.idx fd 3, cache.dat fd 4) open. Which file, which offsets?

usage: py -3 add_arm_k40.py"""
import pathlib

p = pathlib.Path(__file__).resolve().parents[1] / 'ab2' / 'run_vk.py'
s = p.read_bytes().decode('utf-8')
lines = s.split('\n')
i = [k for k, l in enumerate(lines) if l.startswith("ARMS['K']") and '   # Kk40: ' in l][0]
eol = '\r' if lines[i].endswith('\r') else ''
lines.insert(i + 1, "ARMS['K'] = ('r', {**{k: v for k, v in ARMS['K'][1].items() if k != 'PS3_FSTRACE'}, 'FS_READ_ALL': '1', 'PS3_FSLOG_READS': '5'})"
                    "   # Kk41: exe c693e2cb, Kk39 + every cellFs read logged (FS_READ_ALL), ms2.psarc reads with offsets (PS3_FSLOG_READS=5)" + eol)
s = '\n'.join(lines)


def sub(a, b):
    global s
    assert s.count(a) == 1, (a, s.count(a))
    s = s.replace(a, b)


sub("'Kk39', 'Kk40', 'Yy1']", "'Kk39', 'Kk40', 'Kk41', 'Yy1']")
sub("MAX_LAUNCHES = 87", "MAX_LAUNCHES = 88")
p.write_bytes(s.encode('utf-8'))
print('ok')
