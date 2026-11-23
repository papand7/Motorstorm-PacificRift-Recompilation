"""Add launch Kk8: Kk7 (usleep exact, warm SPIR-V cache, [frame-hist]) + the frame clock's FIFO kick on and
off by turns (PS3_FRAME_CLOCK_KICK=ab), exe 995f0f8d, whose [eng-ab] counts only presents that drew."""
import pathlib

p = pathlib.Path(__file__).resolve().parents[1] / 'ab2' / 'run_vk.py'
s = p.read_bytes().decode('utf-8')
lines = s.split('\n')
i = [k for k, l in enumerate(lines) if l.startswith("ARMS['K'] = ('r', {**ARMS['Z'][1], 'PS3_USLEEP_SPIN': '2', 'RSX_FRAME_HIST': '1', 'PS3RECOMP_SPIRV_CACHE'")][0]
eol = '\r' if lines[i].endswith('\r') else ''
new = ("ARMS['K'] = ('r', {**ARMS['K'][1], 'PS3_FRAME_CLOCK_KICK': 'ab'})"
       "   # Kk8: exe 995f0f8d, Kk7 + the FIFO kick on and off by turns ([eng-ab] over presents that drew)" + eol)
lines.insert(i + 1, new)
s = '\n'.join(lines)


def sub(a, b):
    global s
    assert s.count(a) == 1, (a, s.count(a))
    s = s.replace(a, b)


sub("'Kk7', 'Yy1']", "'Kk7', 'Kk8', 'Yy1']")
sub("MAX_LAUNCHES = 54", "MAX_LAUNCHES = 55")
sub("PIN = '8eea85c1d40fe037f99b15c6b86279cdd4d43809adb9e44f02ec346fe0206cd2'   # ",
    "PIN = '995f0f8db2e7285945779220b80573bb52c2ff193e8693d5cfd0238ce4fc0c12'   # [eng-ab] drawing presents (Kk8); ")
p.write_bytes(s.encode('utf-8'))
print('ok')
