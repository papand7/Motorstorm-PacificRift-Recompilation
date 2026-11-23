"""Add launch Kk9: Kk7 (usleep exact, warm SPIR-V cache, [frame-hist], no kick) with the program memo on and off
by turns (RSX_PIPE_MEMO=ab), exe 995f0f8d: does RSX-thread time still move the frame?"""
import pathlib

p = pathlib.Path(__file__).resolve().parents[1] / 'ab2' / 'run_vk.py'
s = p.read_bytes().decode('utf-8')
lines = s.split('\n')
i = [k for k, l in enumerate(lines) if l.startswith("ARMS['K'] = ('r', {**ARMS['K'][1], 'PS3_FRAME_CLOCK_KICK': 'ab'})")][0]
eol = '\r' if lines[i].endswith('\r') else ''
new = ("ARMS['K'] = ('r', {**{k: v for k, v in ARMS['K'][1].items() if k != 'PS3_FRAME_CLOCK_KICK'}, 'RSX_PIPE_MEMO': 'ab'})"
       "   # Kk9: exe 995f0f8d, Kk7 + program memo on and off by turns ([eng-ab])" + eol)
lines.insert(i + 1, new)
s = '\n'.join(lines)


def sub(a, b):
    global s
    assert s.count(a) == 1, (a, s.count(a))
    s = s.replace(a, b)


sub("'Kk8', 'Yy1']", "'Kk8', 'Kk9', 'Yy1']")
sub("MAX_LAUNCHES = 55", "MAX_LAUNCHES = 56")
p.write_bytes(s.encode('utf-8'))
print('ok')
