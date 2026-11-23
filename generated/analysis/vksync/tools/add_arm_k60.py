"""Add launch Kk60: a pass-by-pass capture of race frames for the relighting work (what the scene's
four render targets hold). Kk56's configuration at scale 1 (RSX_RES_SCALE removed, exe 8c01ef18) with
RSX_ENGINE_PASS_DUMP (passes of about two frames, 45 s after the engine's first draw: in the race),
RSX_ENGINE_PASS_DUMP_DRAWS=1 and RSX_ENGINE_SHADER_DUMP into generated/analysis/relight/passes (private).

usage: py -3 add_arm_k60.py"""
import pathlib

root = pathlib.Path(__file__).resolve().parents[4]
out = (root / 'generated' / 'analysis' / 'relight' / 'passes').as_posix()
p = pathlib.Path(__file__).resolve().parents[1] / 'ab2' / 'run_vk.py'
s = p.read_bytes().decode('utf-8')
assert '\r\n' not in s
lines = s.split('\n')
i = [k for k, l in enumerate(lines) if l.startswith("ARMS['K']") and '   # Kk56-Kk59: ' in l][0]
lines.insert(i + 1, "ARMS['K'] = ('r', {**{k: v for k, v in ARMS['K'][1].items() if k != 'RSX_RES_SCALE'}, "
                    "'RSX_ENGINE_PASS_DUMP': '%s', 'RSX_ENGINE_PASS_DUMP_AFTER': '45', 'RSX_ENGINE_PASS_DUMP_MAX': '90', "
                    "'RSX_ENGINE_PASS_DUMP_DRAWS': '1', 'RSX_ENGINE_SHADER_DUMP': '%s'})"
                    "   # Kk60: exe 8c01ef18, pass capture of race frames for relighting" % (out, out))
s = '\n'.join(lines)


def sub(a, b):
    global s
    assert s.count(a) == 1, (a, s.count(a))
    s = s.replace(a, b)


sub("'Kk58', 'Kk59', 'Yy1']", "'Kk58', 'Kk59', 'Kk60', 'Yy1']")
sub("MAX_LAUNCHES = 106", "MAX_LAUNCHES = 107")
p.write_bytes(s.encode('utf-8'))
print('ok')
