"""Add launches Kk6 and Kk7: arm Z + guest usleep exact all run (PS3_USLEEP_SPIN=2) + [frame-hist] +
a SPIR-V cache kept across runs (PS3RECOMP_SPIRV_CACHE), exe 8eea85c1 ([vk-compile]). Kk6 fills the cache
(compile cost in the race), Kk7 runs warm (is 30 fps held without translation stalls?)."""
import pathlib

p = pathlib.Path(__file__).resolve().parents[1] / 'ab2' / 'run_vk.py'
s = p.read_bytes().decode('utf-8')
lines = s.split('\n')
i = [k for k, l in enumerate(lines) if l.startswith("ARMS['K'] = ('r', {**ARMS['Z'][1], 'PS3_USLEEP_SPIN': '2', 'RSX_FRAME_HIST': '1'})")][0]
eol = '\r' if lines[i].endswith('\r') else ''
new = ("ARMS['K'] = ('r', {**ARMS['Z'][1], 'PS3_USLEEP_SPIN': '2', 'RSX_FRAME_HIST': '1', "
       "'PS3RECOMP_SPIRV_CACHE': str(HERE / 'spirv_cache')})"
       "   # Kk6/Kk7: exe 8eea85c1, Kk5 + SPIR-V cache across runs ([vk-compile]); Kk6 cold, Kk7 warm" + eol)
lines.insert(i + 1, new)
s = '\n'.join(lines)


def sub(a, b):
    global s
    assert s.count(a) == 1, (a, s.count(a))
    s = s.replace(a, b)


sub("'Kk5', 'Yy1']", "'Kk5', 'Kk6', 'Kk7', 'Yy1']")
sub("MAX_LAUNCHES = 52", "MAX_LAUNCHES = 54")
sub("PIN = 'f4a436b7f794eb9561650fa67b0c214721b92c719ec0e7a86c75cc1b3db86069'   # ",
    "PIN = '8eea85c1d40fe037f99b15c6b86279cdd4d43809adb9e44f02ec346fe0206cd2'   # [vk-compile] (Kk6/Kk7); ")
p.write_bytes(s.encode('utf-8'))
print('ok')
