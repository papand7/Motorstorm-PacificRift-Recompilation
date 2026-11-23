"""Add launch Kk39: Kk38 without PS3_MAIN_PRIO (Kk37 -0.4 ms, Kk38 +2.6 ms under load: no win), the
plain current configuration on exe c693e2cb, run under tools/io_rate.py: is the FIOS SPU decompressor
(image cbf1b1a1, 67-82% of a core in Kk26-Kk35) decoding what the game reads from disk, or more?

usage: py -3 add_arm_k39.py"""
import pathlib

p = pathlib.Path(__file__).resolve().parents[1] / 'ab2' / 'run_vk.py'
s = p.read_bytes().decode('utf-8')
lines = s.split('\n')
i = [k for k, l in enumerate(lines) if l.startswith("ARMS['K']") and '   # Kk38: ' in l][0]
eol = '\r' if lines[i].endswith('\r') else ''
lines.insert(i + 1, "ARMS['K'] = ('r', {k: v for k, v in ARMS['K'][1].items() if k != 'PS3_MAIN_PRIO'})"
                    "   # Kk39: exe c693e2cb, Kk38 without PS3_MAIN_PRIO, under io_rate.py" + eol)
s = '\n'.join(lines)


def sub(a, b):
    global s
    assert s.count(a) == 1, (a, s.count(a))
    s = s.replace(a, b)


sub("'Kk37', 'Kk38', 'Yy1']", "'Kk37', 'Kk38', 'Kk39', 'Yy1']")
sub("MAX_LAUNCHES = 85", "MAX_LAUNCHES = 86")
p.write_bytes(s.encode('utf-8'))
print('ok')
