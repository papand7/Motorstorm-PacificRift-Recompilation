"""Add launch Kk10: the Kk7 configuration (usleep exact, warm SPIR-V cache, memo on, [frame-hist]) on exe 995f0f8d,
under sample_race.py (sample_k10.json): where the RSX thread's time goes now that it gates the frame."""
import pathlib

p = pathlib.Path(__file__).resolve().parents[1] / 'ab2' / 'run_vk.py'
s = p.read_bytes().decode('utf-8')
lines = s.split('\n')
i = [k for k, l in enumerate(lines) if l.startswith("ARMS['K'] = ('r', {**{k: v for k, v in ARMS['K'][1].items() if k != 'PS3_FRAME_CLOCK_KICK'}, 'RSX_PIPE_MEMO': 'ab'})")][0]
eol = '\r' if lines[i].endswith('\r') else ''
new = ("ARMS['K'] = ('r', {**ARMS['K'][1], 'RSX_PIPE_MEMO': '1'})"
       "   # Kk10: exe 995f0f8d, the Kk7 configuration under sample_race.py (sample_k10.json)" + eol)
lines.insert(i + 1, new)
s = '\n'.join(lines)


def sub(a, b):
    global s
    assert s.count(a) == 1, (a, s.count(a))
    s = s.replace(a, b)


sub("'Kk9', 'Yy1']", "'Kk9', 'Kk10', 'Yy1']")
sub("MAX_LAUNCHES = 56", "MAX_LAUNCHES = 57")
p.write_bytes(s.encode('utf-8'))
print('ok')
